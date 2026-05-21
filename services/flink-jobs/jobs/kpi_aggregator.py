"""Job Flink: Aggregate KPIs and sink to ClickHouse + Kafka."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

from pyflink.common import Duration, WatermarkStrategy
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import TimestampAssigner
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.jdbc import JdbcConnectionOptions, JdbcExecutionOptions, JdbcSink
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import AggregateFunction, MapFunction, ProcessWindowFunction
from pyflink.datastream.window import TumblingEventTimeWindows

from jobs.avro_utils import AvroDeserializationSchema, AvroSerializationSchema

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_TRACKS", "tracks")
TOPIC_OUT = os.getenv("TOPIC_KPIS", "kpis")

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "jdbc:clickhouse://localhost:8123/default")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")


# ── Models ──────────────────────────────────────────────────────────────────────
class ParseTrack(MapFunction):
    def map(self, msg: dict | None) -> dict | None:
        if msg is None or "_error" in msg:
            return None
        return {
            "label": msg.get("label", "unknown"),
            "timestamp_ms": int(msg.get("timestamp_ms", 0)),
        }


class TrackTimestampAssigner(TimestampAssigner):
    def extract_timestamp(self, track: dict, _record_timestamp: int) -> int:
        return track["timestamp_ms"]


class CountAggregate(AggregateFunction):
    def create_accumulator(self) -> int:
        return 0

    def add(self, _value: dict, accumulator: int) -> int:
        return accumulator + 1

    def get_result(self, accumulator: int) -> int:
        return accumulator

    def merge(self, a: int, b: int) -> int:
        return a + b


class KpiFormatter(ProcessWindowFunction):
    def process(self, key: str, context: Any, counts: Iterable[int], out: Any) -> None:
        count = next(iter(counts))
        window = context.window()
        kpi = {
            "label": key,
            "count": count,
            "window_start": window.start,
            "window_end": window.end,
            "window_sec": (window.end - window.start) // 1000,
        }
        out.collect(kpi)


# ── ClickHouse SQL ──────────────────────────────────────────────────────────────
CLICKHOUSE_INSERT_SQL = """
    INSERT INTO kpi_detections (label, count, window_start, window_end, window_sec)
    VALUES (?, ?, ?, ?, ?)
"""


def create_clickhouse_sink() -> Any:
    return JdbcSink.sink(
        CLICKHOUSE_INSERT_SQL,
        JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
        .with_url(CLICKHOUSE_URL)
        .with_driver_name("com.clickhouse.jdbc.ClickHouseDriver")
        .with_user_name(CLICKHOUSE_USER)
        .with_password(CLICKHOUSE_PASSWORD)
        .build(),
        JdbcExecutionOptions.builder().with_batch_size(100).with_batch_interval_ms(1000).build(),
    )


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
    ).with_timestamp_assigner(TrackTimestampAssigner())

    stream = (
        env.from_source(source, watermark_strategy, "kafka-tracks-source")
        .map(ParseTrack(), output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()))
        .filter(lambda t: t is not None)
    )

    # Kafka sink for real-time consumers
    kafka_sink = (
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

    # ClickHouse sink for analytics
    ch_sink = create_clickhouse_sink()

    # 1-minute window → both sinks
    w1 = (
        stream.key_by(lambda t: t["label"])
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(1)))
        .aggregate(
            CountAggregate(),
            KpiFormatter(),
            accumulator_type=Types.LONG(),
            output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
        )
    )
    w1.sink_to(kafka_sink)
    w1.add_sink(ch_sink)

    # 5-minute window → Kafka only (ClickHouse can aggregate from 1-min)
    w5 = (
        stream.key_by(lambda t: t["label"])
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(5)))
        .aggregate(
            CountAggregate(),
            KpiFormatter(),
            accumulator_type=Types.LONG(),
            output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
        )
    )
    w5.sink_to(kafka_sink)

    # 1-hour window → Kafka only
    w60 = (
        stream.key_by(lambda t: t["label"])
        .window(TumblingEventTimeWindows.of(Duration.of_minutes(60)))
        .aggregate(
            CountAggregate(),
            KpiFormatter(),
            accumulator_type=Types.LONG(),
            output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()),
        )
    )
    w60.sink_to(kafka_sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(int(os.getenv("FLINK_PARALLELISM", "1")))
    build_pipeline(env)
    env.execute("logivision-kpi-aggregator")


if __name__ == "__main__":
    main()
