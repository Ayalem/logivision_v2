"""
Job Flink : Agrégation des KPIs.
Compte le nombre de colis détectés par fenêtre de 1 min / 5 min / 1 heure.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pyflink.common import Duration, SimpleStringSchema, WatermarkStrategy
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import TimestampAssigner
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import AggregateFunction, MapFunction, ProcessWindowFunction
from pyflink.datastream.window import TumblingEventTimeWindows

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_DETECTIONS", "detections")
TOPIC_OUT = os.getenv("TOPIC_KPIS", "kpis")


# ── Modèles de données ──────────────────────────────────────────────────────────
@dataclass
class Detection:
    object_id: str
    label: str
    timestamp: int

    @staticmethod
    def from_json(raw: str) -> Detection:
        d = json.loads(raw)
        return Detection(
            object_id=str(d["object_id"]),
            label=d.get("label", "unknown"),
            timestamp=int(d["timestamp"]),
        )


# ── Fonctions Flink ─────────────────────────────────────────────────────────────
class ParseDetection(MapFunction):
    def map(self, raw: str) -> Detection:
        try:
            return Detection.from_json(raw)
        except (KeyError, ValueError, json.JSONDecodeError):
            return Detection("__invalid__", "unknown", 0)


class DetectionTimestampAssigner(TimestampAssigner):
    """Indique à Flink quel champ utiliser comme timestamp pour les fenêtres."""

    def extract_timestamp(self, detection: Detection, _record_timestamp: int) -> int:
        return detection.timestamp


class CountAggregate(AggregateFunction):
    """Compte le nombre de détections dans la fenêtre."""

    def create_accumulator(self) -> int:
        return 0

    def add(self, _value: Detection, accumulator: int) -> int:
        return accumulator + 1

    def get_result(self, accumulator: int) -> int:
        return accumulator

    def merge(self, a: int, b: int) -> int:
        return a + b


class KpiWindowProcessor(ProcessWindowFunction):
    """Formate le résultat de la fenêtre en message JSON."""

    def process(
        self,
        key: str,
        context: Any,
        counts: Iterable[int],
        out: Any,
    ) -> None:
        count = next(iter(counts))
        window = context.window()
        kpi = {
            "label": key,
            "count": count,
            "window_start": window.start,
            "window_end": window.end,
            "window_sec": (window.end - window.start) // 1000,
        }
        out.collect(json.dumps(kpi))


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

    watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(
        Duration.of_seconds(5)
    ).with_timestamp_assigner(DetectionTimestampAssigner())

    stream = (
        env.from_source(source, watermark_strategy, "kafka-detections-source")
        .map(ParseDetection(), output_type=Types.PICKLED_BYTE_ARRAY())
        .filter(lambda d: d.object_id != "__invalid__")
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

    # Fenêtre 1 minute
    (
        stream.key_by(lambda d: d.label)
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(1)))
        .aggregate(
            CountAggregate(),
            KpiWindowProcessor(),
            accumulator_type=Types.LONG(),
            output_type=Types.STRING(),
        )
        .sink_to(sink)
    )

    # Fenêtre 5 minutes
    (
        stream.key_by(lambda d: d.label)
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(5)))
        .aggregate(
            CountAggregate(),
            KpiWindowProcessor(),
            accumulator_type=Types.LONG(),
            output_type=Types.STRING(),
        )
        .sink_to(sink)
    )

    # Fenêtre 1 heure
    (
        stream.key_by(lambda d: d.label)
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(60)))
        .aggregate(
            CountAggregate(),
            KpiWindowProcessor(),
            accumulator_type=Types.LONG(),
            output_type=Types.STRING(),
        )
        .sink_to(sink)
    )


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    build_pipeline(env)
    env.execute("logivision-kpi-aggregator")


if __name__ == "__main__":
    main()
