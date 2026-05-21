"""Job Flink: Detect stationary objects. Alert if no movement > threshold."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

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
TOPIC_IN = os.getenv("TOPIC_TRACKS", "tracks")  # Now reads tracks, not raw detections
TOPIC_OUT = os.getenv("TOPIC_EVENTS", "events")
STATIONARY_SEC = int(os.getenv("STATIONARY_THRESHOLD_SEC", "300"))
MOVEMENT_PX = float(os.getenv("MOVEMENT_THRESHOLD_PX", "15.0"))
COOLDOWN_SEC = int(os.getenv("STATIONARY_COOLDOWN_SEC", "60"))


# ── State ───────────────────────────────────────────────────────────────────────
@dataclass
class TrackState:
    first_seen_ms: int
    last_x: float
    last_y: float
    alerted_at_ms: int = 0  # 0 = never alerted


class StationaryDetector(KeyedProcessFunction):
    def open(self, runtime_context: Any) -> None:
        descriptor = ValueStateDescriptor("track_state", Types.PICKLED_BYTE_ARRAY())
        self.state = runtime_context.get_state(descriptor)

    def process_element(self, track: dict, _ctx: Any, out: Any) -> None:
        track_id = track.get("track_id", "unknown")
        x = float(track.get("x", 0.0))
        y = float(track.get("y", 0.0))
        ts = int(track.get("timestamp_ms", 0))

        current: TrackState | None = self.state.value()

        if current is None:
            self.state.update(TrackState(first_seen_ms=ts, last_x=x, last_y=y))
            return

        distance = ((x - current.last_x) ** 2 + (y - current.last_y) ** 2) ** 0.5

        if distance > MOVEMENT_PX:
            # Object moved — reset state but preserve alert cooldown
            self.state.update(
                TrackState(
                    first_seen_ms=ts,
                    last_x=x,
                    last_y=y,
                    alerted_at_ms=current.alerted_at_ms,
                )
            )
            return

        elapsed_sec = (ts - current.first_seen_ms) / 1000.0

        if elapsed_sec >= STATIONARY_SEC and (
            current.alerted_at_ms == 0 or (ts - current.alerted_at_ms) >= COOLDOWN_SEC * 1000
        ):
            event = {
                "event_id": f"{track_id}:{ts}",
                "event_type": "stationary_object",
                "severity": "warning",
                "timestamp_ms": ts,
                "camera_id": track.get("camera_id"),
                "track_id": track_id,
                "payload": {
                    "duration_sec": str(int(elapsed_sec)),
                    "label": track.get("label", "unknown"),
                    "zone": track.get("zone", "unknown"),
                },
            }
            out.collect(event)
            current.alerted_at_ms = ts
            self.state.update(current)


class ParseTrack(MapFunction):
    def map(self, msg: dict | None) -> dict | None:
        if msg is None or "_error" in msg:
            return None
        return msg


# ── Pipeline ────────────────────────────────────────────────────────────────────
def build_pipeline(env: StreamExecutionEnvironment) -> None:
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_topics(TOPIC_IN)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(AvroDeserializationSchema("Track"))
        .build()
    )

    watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(
        Duration.of_seconds(5)
    ).with_idleness(Duration.of_seconds(30))

    stream = env.from_source(source, watermark_strategy, "kafka-tracks-source")

    alerts = (
        stream.map(ParseTrack(), output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()))
        .filter(lambda t: t is not None)
        .key_by(lambda t: t.get("track_id", "unknown"))
        .process(
            StationaryDetector(), output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY())
        )
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(TOPIC_OUT)
            .set_value_serialization_schema(AvroSerializationSchema("Event"))
            .build()
        )
        .build()
    )

    alerts.sink_to(sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(int(os.getenv("FLINK_PARALLELISM", "1")))
    build_pipeline(env)
    env.execute("logivision-stationary-detection")


if __name__ == "__main__":
    main()
