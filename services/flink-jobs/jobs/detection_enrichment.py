"""
Job Flink : Enrichissement des détections.
Lit le topic 'detections', ajoute l'ID de zone géographique et publie dans 'tracks'.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from pyflink.common import SimpleStringSchema, WatermarkStrategy
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import MapFunction

# ── Configuration ───────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_IN = os.getenv("TOPIC_DETECTIONS", "detections")
TOPIC_OUT = os.getenv("TOPIC_TRACKS", "tracks")

# Zones nommées : dict { nom_zone: polygone }
# Chaque polygone = liste de (x, y)
DEFAULT_NAMED_ZONES: dict[str, list[tuple[float, float]]] = {
    "zone_entree": [(0, 0), (200, 0), (200, 300), (0, 300)],
    "zone_stockage": [(200, 0), (500, 0), (500, 300), (200, 300)],
    "zone_expedition": [(500, 0), (800, 0), (800, 300), (500, 300)],
}


def load_named_zones() -> dict[str, list[tuple[float, float]]]:
    raw = os.getenv("NAMED_ZONES")
    if not raw:
        return DEFAULT_NAMED_ZONES
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_NAMED_ZONES


NAMED_ZONES = load_named_zones()


# ── Algorithme point-dans-polygone ──────────────────────────────────────────────
def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def get_zone_name(x: float, y: float) -> str:
    """Renvoie le nom de la zone où se trouve le point, ou 'unknown'."""
    for zone_name, polygon in NAMED_ZONES.items():
        if point_in_polygon(x, y, polygon):
            return zone_name
    return "unknown"


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
class Track:
    """Détection enrichie avec la zone géographique."""

    object_id: str
    label: str
    x: float
    y: float
    confidence: float
    timestamp: int
    zone: str  # nom de la zone où se trouve l'objet

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ── Fonction Flink ──────────────────────────────────────────────────────────────
class EnrichDetection(MapFunction):
    """
    Transforme une Detection en Track :
    ajoute le nom de la zone géographique selon la position (x, y).
    """

    def map(self, raw: str) -> str:
        try:
            det = Detection.from_json(raw)
        except (KeyError, ValueError, json.JSONDecodeError):
            return json.dumps({"error": "invalid_detection", "raw": raw[:100]})

        zone = get_zone_name(det.x, det.y)

        track = Track(
            object_id=det.object_id,
            label=det.label,
            x=det.x,
            y=det.y,
            confidence=det.confidence,
            timestamp=det.timestamp,
            zone=zone,
        )
        return track.to_json()


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

    enriched = stream.map(EnrichDetection(), output_type=Types.STRING())

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

    enriched.sink_to(sink)


def main() -> None:
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    build_pipeline(env)
    env.execute("logivision-detection-enrichment")


if __name__ == "__main__":
    main()
