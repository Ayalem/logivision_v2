"""Job Flink: ByteTrack multi-object tracking. Reads 'detections', writes 'tracks'."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from pyflink.common import Duration, WatermarkStrategy
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import KeyedProcessFunction, MapFunction
from pyflink.datastream.state import ValueStateDescriptor

from jobs.avro_utils import AvroDeserializationSchema, AvroSerializationSchema

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_DETECTIONS", "detections")
TOPIC_OUT = os.getenv("TOPIC_TRACKS", "tracks")

# ByteTrack parameters
TRACK_BUFFER = int(os.getenv("TRACK_BUFFER", "30"))  # frames to keep lost tracks
TRACK_THRESH = float(os.getenv("TRACK_THRESH", "0.5"))
HIGH_THRESH = float(os.getenv("HIGH_THRESH", "0.6"))
MATCH_THRESH = float(os.getenv("MATCH_THRESH", "0.8"))


# ── Simple ByteTrack implementation (pure Python, no GPU needed) ────────────────
@dataclass
class STrack:
    """Simple track state for CPU-only tracking."""

    track_id: int
    tlbr: np.ndarray  # [top, left, bottom, right]
    score: float
    frame_id: int
    start_frame: int
    tracklet_len: int = 0

    def predict(self) -> None:
        # Simple constant velocity prediction (no Kalman filter for CPU)
        pass

    def update(self, new_tlbr: np.ndarray, score: float, frame_id: int) -> None:
        self.tlbr = new_tlbr
        self.score = score
        self.frame_id = frame_id
        self.tracklet_len += 1


class ByteTrack:
    """Lightweight ByteTrack for CPU inference."""

    def __init__(self, track_thresh: float = 0.5, match_thresh: float = 0.8) -> None:
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.tracks: list[STrack] = []
        self.lost_tracks: list[STrack] = []
        self.removed_tracks: list[STrack] = []
        self.next_id = 1

    def update(self, detections: list[dict], frame_id: int) -> list[STrack]:
        if not detections:
            # Mark all tracks as lost
            self.lost_tracks.extend(self.tracks)
            self.tracks = []
            return []

        # Convert to tlbr format
        dets = []
        for d in detections:
            tlbr = np.array([d["y1"], d["x1"], d["y2"], d["x2"]])
            dets.append((tlbr, d["confidence"]))

        # Split into high/low confidence
        high_dets = [(t, s) for t, s in dets if s >= self.track_thresh]
        low_dets = [(t, s) for t, s in dets if s < self.track_thresh]

        # Match high confidence detections to existing tracks (IoU)
        matched, unmatched_tracks, unmatched_dets = self._match(self.tracks, high_dets)

        # Update matched tracks
        for track_idx, det_idx in matched:
            self.tracks[track_idx].update(high_dets[det_idx][0], high_dets[det_idx][1], frame_id)

        # Match remaining tracks to low confidence detections
        matched_low, unmatched_tracks_low, _ = self._match(
            [self.tracks[i] for i in unmatched_tracks], low_dets
        )

        # Update matched low-confidence
        for track_local_idx, det_idx in matched_low:
            track_idx = unmatched_tracks[track_local_idx]
            self.tracks[track_idx].update(low_dets[det_idx][0], low_dets[det_idx][1], frame_id)

        # Mark unmatched tracks as lost
        for i in unmatched_tracks_low:
            self.lost_tracks.append(self.tracks[unmatched_tracks[i]])

        # Create new tracks for unmatched high-confidence detections
        for i in unmatched_dets:
            new_track = STrack(
                track_id=self.next_id,
                tlbr=high_dets[i][0],
                score=high_dets[i][1],
                frame_id=frame_id,
                start_frame=frame_id,
            )
            self.tracks.append(new_track)
            self.next_id += 1

        # Remove lost tracks that have been lost too long
        self.lost_tracks = [t for t in self.lost_tracks if frame_id - t.frame_id <= TRACK_BUFFER]

        # Return active tracks
        return [t for t in self.tracks if t.tracklet_len > 1]

    def _match(
        self, tracks: list[STrack], detections: list[tuple[np.ndarray, float]]
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Greedy IoU matching."""
        if not tracks or not detections:
            return [], list(range(len(tracks))), list(range(len(detections)))

        # Compute IoU matrix
        iou_matrix = np.zeros((len(tracks), len(detections)))
        for i, track in enumerate(tracks):
            for j, (det_tlbr, _) in enumerate(detections):
                iou_matrix[i, j] = self._iou(track.tlbr, det_tlbr)

        # Greedy assignment
        matched = []
        unmatched_tracks = list(range(len(tracks)))
        unmatched_dets = list(range(len(detections)))

        while True:
            if iou_matrix.size == 0:
                break
            max_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
            max_iou = iou_matrix[max_idx]
            if max_iou < self.match_thresh:
                break

            ti, di = max_idx
            matched.append((unmatched_tracks[ti], unmatched_dets[di]))
            iou_matrix = np.delete(iou_matrix, ti, axis=0)
            iou_matrix = np.delete(iou_matrix, di, axis=1)
            unmatched_tracks.pop(ti)
            unmatched_dets.pop(di)

        return matched, unmatched_tracks, unmatched_dets

    @staticmethod
    def _iou(a: np.ndarray, b: np.ndarray) -> float:
        """Compute IoU between two boxes in tlbr format."""
        area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
        area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])

        inter_y1 = max(a[0], b[0])
        inter_x1 = max(a[1], b[1])
        inter_y2 = min(a[2], b[2])
        inter_x2 = min(a[3], b[3])

        inter_area = max(0, inter_y2 - inter_y1) * max(0, inter_x2 - inter_x1)
        union_area = area_a + area_b - inter_area
        return inter_area / union_area if union_area > 0 else 0.0


# ── Flink Functions ─────────────────────────────────────────────────────────────
class ParseDetection(MapFunction):
    def map(self, msg: dict | None) -> dict | None:
        if msg is None or "_error" in msg:
            return None
        return msg


class ByteTrackProcessor(KeyedProcessFunction):
    """Per-camera ByteTrack stateful processor."""

    def open(self, runtime_context: Any) -> None:
        # State: ByteTrack instance serialized as pickle
        track_descriptor = ValueStateDescriptor("tracker", Types.PICKLED_BYTE_ARRAY())
        self.tracker_state = runtime_context.get_state(track_descriptor)

        # Frame counter for this camera
        frame_descriptor = ValueStateDescriptor("frame_counter", Types.LONG())
        self.frame_counter = runtime_context.get_state(frame_descriptor)

    def process_element(self, detection_msg: dict, _ctx: Any, out: Any) -> None:
        camera_id = detection_msg.get("camera_id", "unknown")
        timestamp_ms = int(detection_msg.get("timestamp_ms", 0))
        frame_id = detection_msg.get("frame_id", "unknown")

        # Restore or create tracker
        tracker: ByteTrack | None = self.tracker_state.value()
        if tracker is None:
            tracker = ByteTrack(track_thresh=TRACK_THRESH, match_thresh=MATCH_THRESH)

        # Get frame counter
        counter = self.frame_counter.value() or 0
        counter += 1
        self.frame_counter.update(counter)

        # Run tracking
        detections = detection_msg.get("detections", [])
        tracks = tracker.update(detections, counter)

        # Output tracks
        for track in tracks:
            out_track = {
                "track_id": f"{camera_id}:{track.track_id}",
                "label": "box",  # Could map from class_id
                "x": float((track.tlbr[1] + track.tlbr[3]) / 2),  # centroid x
                "y": float((track.tlbr[0] + track.tlbr[2]) / 2),  # centroid y
                "confidence": float(track.score),
                "timestamp_ms": timestamp_ms,
                "zone": "unknown",  # Will be enriched downstream
                "frame_id": frame_id,
                "camera_id": camera_id,
            }
            out.collect(out_track)

        # Save state
        self.tracker_state.update(tracker)


# ── Pipeline ────────────────────────────────────────────────────────────────────
def build_pipeline(env: StreamExecutionEnvironment) -> None:
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_topics(TOPIC_IN)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(AvroDeserializationSchema("Detection"))
        .build()
    )

    watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(
        Duration.of_seconds(5)
    ).with_idleness(Duration.of_seconds(30))

    stream = env.from_source(source, watermark_strategy, "kafka-detections-source")

    tracks = (
        stream.map(
            ParseDetection(), output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY())
        )
        .filter(lambda m: m is not None)
        .key_by(lambda m: m.get("camera_id", "unknown"))
        .process(
            ByteTrackProcessor(), output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY())
        )
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(TOPIC_OUT)
            .set_value_serialization_schema(AvroSerializationSchema("Track"))
            .build()
        )
        .build()
    )

    tracks.sink_to(sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(int(os.getenv("FLINK_PARALLELISM", "1")))
    build_pipeline(env)
    env.execute("logivision-byte-tracker")


if __name__ == "__main__":
    main()
