"""Job Flink: Enrich detections with zone info. Reads 'detections', writes 'tracks'."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from pyflink.common import WatermarkStrategy
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import MapFunction

from jobs.avro_utils import AvroDeserializationSchema, AvroSerializationSchema

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_DETECTIONS", "detections")
TOPIC_OUT = os.getenv("TOPIC_TRACKS", "tracks")

# Zones: {name: [(x1,y1), (x2,y2), ...]} in pixel coordinates
DEFAULT_ZONES = {
    "zone_entree": [(0, 0), (200, 0), (200, 300), (0, 300)],
    "zone_stockage": [(200, 0), (500, 0), (500, 300), (200, 300)],
    "zone_expedition": [(500, 0), (800, 0), (800, 300), (500, 300)],
}


def load_zones() -> dict[str, list[tuple[float, float]]]:
    raw = os.getenv("ZONES_JSON")
    return json.loads(raw) if raw else DEFAULT_ZONES


ZONES = load_zones()


# ── Geometry ────────────────────────────────────────────────────────────────────
def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def get_zone_name(x: float, y: float) -> str:
    for name, poly in ZONES.items():
        if point_in_polygon(x, y, poly):
            return name
    return "unknown"


# ── Flink Functions ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EnrichedTrack:
    track_id: str
    label: str
    x: float
    y: float
    confidence: float
    timestamp_ms: int
    zone: str
    frame_id: str
    camera_id: str

    def to_avro(self) -> dict:
        return {
            "track_id": self.track_id,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "timestamp_ms": self.timestamp_ms,
            "zone": self.zone,
            "frame_id": self.frame_id,
            "camera_id": self.camera_id,
        }


class EnrichDetection(MapFunction):
    """Flatten frame-level detections into per-object tracks with zone info."""

    def map(self, detection_msg: dict | None) -> list[dict] | None:
        if detection_msg is None or "_error" in detection_msg:
            return None

        frame_id = detection_msg.get("frame_id", "unknown")
        camera_id = detection_msg.get("camera_id", "unknown")
        timestamp_ms = detection_msg.get("timestamp_ms", 0)

        tracks = []
        for det in detection_msg.get("detections", []):
            cx = (det.get("x1", 0.0) + det.get("x2", 0.0)) / 2.0
            cy = (det.get("y1", 0.0) + det.get("y2", 0.0)) / 2.0

            track = EnrichedTrack(
                track_id=f"{camera_id}:{det.get('class_id', 0)}:{int(cx)}:{int(cy)}",
                label=det.get("class_name", "unknown"),
                x=cx,
                y=cy,
                confidence=det.get("confidence", 0.0),
                timestamp_ms=timestamp_ms,
                zone=get_zone_name(cx, cy),
                frame_id=frame_id,
                camera_id=camera_id,
            )
            tracks.append(track.to_avro())

        return tracks


class FlattenTracks(MapFunction):
    """Flatten list of tracks into individual records for Kafka sink."""

    def map(self, tracks: list[dict] | None) -> dict | None:
        if not tracks:
            return None
        # Flink will call this per-element if we use flat_map, but KafkaSink
        # needs one record at a time. We'll use a flat_map approach instead.
        return tracks[0] if tracks else None


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

    stream = env.from_source(
        source,
        WatermarkStrategy.for_monotonous_timestamps(),
        "kafka-detections-source",
    )

    # Flatten frame-level batch into individual track records
    tracks = stream.flat_map(
        lambda msg: msg if isinstance(msg, list) else [],
        output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
    )

    enriched = tracks.map(
        EnrichDetection(),
        output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
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

    enriched.sink_to(sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(int(os.getenv("FLINK_PARALLELISM", "1")))
    build_pipeline(env)
    env.execute("logivision-detection-enrichment")


if __name__ == "__main__":
    main()
