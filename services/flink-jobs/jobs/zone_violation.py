"""
Job Flink : Détection de violations de zones interdites.
Alerte si un objet tracké entre dans un polygone virtuel défini comme zone interdite.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pyflink.common import SimpleStringSchema, WatermarkStrategy
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

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_DETECTIONS", "detections")
TOPIC_OUT = os.getenv("TOPIC_EVENTS", "events")

DEFAULT_ZONES = [
    [(0, 0), (300, 0), (300, 200), (0, 200)],
]


def load_zones() -> list[list[tuple[float, float]]]:
    raw = os.getenv("FORBIDDEN_ZONES")
    if not raw:
        return DEFAULT_ZONES
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_ZONES


FORBIDDEN_ZONES = load_zones()


# ── Algorithme point-dans-polygone (Ray Casting) ────────────────────────────────
def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    n = len(polygon)
    result = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            result = not result
        j = i
    return result


def in_any_forbidden_zone(x: float, y: float) -> int | None:
    for idx, zone in enumerate(FORBIDDEN_ZONES):
        if point_in_polygon(x, y, zone):
            return idx
    return None


# ── Modèles de données ──────────────────────────────────────────────────────────
@dataclass
class Detection:
    object_id: str
    label: str
    x: float
    y: float
    confidence: float
    timestamp: int

    @staticmethod
    def from_json(raw: str) -> Detection:
        d = json.loads(raw)
        return Detection(
            object_id=str(d["object_id"]),
            label=d.get("label", "unknown"),
            x=float(d["x"]),
            y=float(d["y"]),
            confidence=float(d.get("confidence", 1.0)),
            timestamp=int(d["timestamp"]),
        )


# ── Fonctions Flink ─────────────────────────────────────────────────────────────
class ParseDetection(MapFunction):
    def map(self, raw: str) -> Detection:
        try:
            return Detection.from_json(raw)
        except (KeyError, ValueError, json.JSONDecodeError):
            return Detection("__invalid__", "unknown", 0.0, 0.0, 0.0, 0)


class ZoneViolationDetector(KeyedProcessFunction):
    def open(self, runtime_context: Any) -> None:
        descriptor = ValueStateDescriptor("in_zone", Types.BOOLEAN())
        self.in_zone_state = runtime_context.get_state(descriptor)

    def process_element(self, detection: Detection, _ctx: Any, out: Any) -> None:
        if detection.object_id == "__invalid__":
            return

        zone_idx = in_any_forbidden_zone(detection.x, detection.y)
        was_in_zone = self.in_zone_state.value() or False

        if zone_idx is not None and not was_in_zone:
            alert = {
                "type": "ZONE_VIOLATION",
                "object_id": detection.object_id,
                "label": detection.label,
                "x": detection.x,
                "y": detection.y,
                "zone_id": zone_idx,
                "timestamp": detection.timestamp,
            }
            out.collect(json.dumps(alert))
            self.in_zone_state.update(True)

        elif zone_idx is None and was_in_zone:
            self.in_zone_state.update(False)


# ── Pipeline principal ──────────────────────────────────────────────────────────
def build_pipeline(env: StreamExecutionEnvironment) -> None:
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_topics(TOPIC_IN)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    stream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "kafka-detections-source",
    )

    alerts = (
        stream.map(ParseDetection(), output_type=Types.PICKLED_BYTE_ARRAY())
        .filter(lambda d: d.object_id != "__invalid__")
        .key_by(lambda d: d.object_id)
        .process(ZoneViolationDetector(), output_type=Types.STRING())
    )

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(KAFKA_BROKER)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(TOPIC_OUT)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .build()
    )

    alerts.sink_to(sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    build_pipeline(env)
    env.execute("logivision-zone-violation")


if __name__ == "__main__":
    main()
