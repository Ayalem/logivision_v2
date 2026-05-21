"""
Job Flink : Détection de colis stationnaires.
Alerte si un objet tracké ne bouge pas pendant plus de STATIONARY_THRESHOLD_SEC secondes.
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
STATIONARY_THRESHOLD_SEC = int(os.getenv("STATIONARY_THRESHOLD_SEC", "300"))
MOVEMENT_THRESHOLD_PX = float(os.getenv("MOVEMENT_THRESHOLD_PX", "15.0"))


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


@dataclass
class StationaryState:
    first_seen_ts: int
    last_x: float
    last_y: float
    alerted: bool = False


# ── Fonctions Flink ─────────────────────────────────────────────────────────────
class ParseDetection(MapFunction):
    def map(self, raw: str) -> Detection:
        try:
            return Detection.from_json(raw)
        except (KeyError, ValueError, json.JSONDecodeError):
            return Detection("__invalid__", "unknown", 0.0, 0.0, 0.0, 0)


class StationaryDetector(KeyedProcessFunction):
    def open(self, runtime_context: Any) -> None:
        descriptor = ValueStateDescriptor("stationary_state", Types.PICKLED_BYTE_ARRAY())
        self.state = runtime_context.get_state(descriptor)

    def process_element(self, detection: Detection, _ctx: Any, out: Any) -> None:
        if detection.object_id == "__invalid__":
            return

        current: StationaryState | None = self.state.value()
        now_ms = detection.timestamp

        if current is None:
            self.state.update(
                StationaryState(
                    first_seen_ts=now_ms,
                    last_x=detection.x,
                    last_y=detection.y,
                )
            )
            return

        distance = (
            (detection.x - current.last_x) ** 2 + (detection.y - current.last_y) ** 2
        ) ** 0.5

        if distance > MOVEMENT_THRESHOLD_PX:
            self.state.update(
                StationaryState(
                    first_seen_ts=now_ms,
                    last_x=detection.x,
                    last_y=detection.y,
                )
            )
            return

        elapsed_sec = (now_ms - current.first_seen_ts) / 1000.0

        if elapsed_sec >= STATIONARY_THRESHOLD_SEC and not current.alerted:
            alert = {
                "type": "STATIONARY_OBJECT",
                "object_id": detection.object_id,
                "label": detection.label,
                "x": detection.x,
                "y": detection.y,
                "duration_sec": round(elapsed_sec, 1),
                "timestamp": now_ms,
            }
            out.collect(json.dumps(alert))
            self.state.update(
                StationaryState(
                    first_seen_ts=current.first_seen_ts,
                    last_x=detection.x,
                    last_y=detection.y,
                    alerted=True,
                )
            )


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
        .process(StationaryDetector(), output_type=Types.STRING())
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
    env.execute("logivision-stationary-detection")


if __name__ == "__main__":
    main()
