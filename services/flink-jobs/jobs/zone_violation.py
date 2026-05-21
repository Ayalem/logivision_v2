"""Job Flink: Detect zone violations. Alert on entry to forbidden zones."""

from __future__ import annotations

import json
import os
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
TOPIC_IN = os.getenv("TOPIC_TRACKS", "tracks")
TOPIC_OUT = os.getenv("TOPIC_EVENTS", "events")

DEFAULT_ZONES = [[(0, 0), (300, 0), (300, 200), (0, 200)]]


def load_zones() -> list[list[tuple[float, float]]]:
    raw = os.getenv("FORBIDDEN_ZONES_JSON")
    return json.loads(raw) if raw else DEFAULT_ZONES


FORBIDDEN_ZONES = load_zones()


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


def in_forbidden_zone(x: float, y: float) -> int | None:
    for idx, zone in enumerate(FORBIDDEN_ZONES):
        if point_in_polygon(x, y, zone):
            return idx
    return None


# ── Flink Functions ─────────────────────────────────────────────────────────────
class ParseTrack(MapFunction):
    def map(self, msg: dict | None) -> dict | None:
        if msg is None or "_error" in msg:
            return None
        return msg


class ZoneViolationDetector(KeyedProcessFunction):
    def open(self, runtime_context: Any) -> None:
        descriptor = ValueStateDescriptor("was_in_zone", Types.BOOLEAN())
        self.was_in_zone = runtime_context.get_state(descriptor)

    def process_element(self, track: dict, _ctx: Any, out: Any) -> None:
        track_id = track.get("track_id", "unknown")
        x = float(track.get("x", 0.0))
        y = float(track.get("y", 0.0))
        ts = int(track.get("timestamp_ms", 0))

        zone_idx = in_forbidden_zone(x, y)
        was_inside = self.was_in_zone.value() or False

        if zone_idx is not None and not was_inside:
            event = {
                "event_id": f"{track_id}:{ts}",
                "event_type": "zone_violation",
                "severity": "critical",
                "timestamp_ms": ts,
                "camera_id": track.get("camera_id"),
                "track_id": track_id,
                "payload": {
                    "zone_id": str(zone_idx),
                    "label": track.get("label", "unknown"),
                    "zone": track.get("zone", "unknown"),
                },
            }
            out.collect(event)
            self.was_in_zone.update(True)

        elif zone_idx is None and was_inside:
            self.was_in_zone.update(False)


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
            ZoneViolationDetector(),
            output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
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
    env.execute("logivision-zone-violation")


if __name__ == "__main__":
    main()
