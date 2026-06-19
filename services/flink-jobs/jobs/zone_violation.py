"""
Job Flink CEP : Détection de violations de zones interdites.

Ce job écoute le topic Kafka "tracks" et déclenche une alerte
si les coordonnées d'un objet (colis, personne) croisent
une zone interdite définie par un polygone virtuel.

Définition des zones dans FORBIDDEN_ZONES ci-dessous.

Utilisation :
    python services/flink-jobs/jobs/zone_violation.py
"""

import json
import logging
import os
import time
from typing import Iterator

from pyflink.common import Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    FlinkKafkaConsumer,
    FlinkKafkaProducer,
)
from pyflink.datastream.functions import FlatMapFunction, RuntimeContext

# Pour les calculs géométriques (point dans polygone)
# Si shapely n'est pas disponible, on utilise notre propre implémentation
try:
    from shapely.geometry import Point, Polygon
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False
    logging.warning("Shapely non disponible, utilisation de l'algorithme maison")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "tracks"
OUTPUT_TOPIC = "events"
CONSUMER_GROUP = "flink-zone-violation"

# ─────────────────────────────────────────────
# ZONES INTERDITES
#
# Chaque zone est définie par :
# - id : identifiant unique
# - name : nom lisible
# - camera_id : caméra concernée ("*" = toutes)
# - polygon : liste de points (x, y) en pixels
#             Les coordonnées dépendent de la résolution de la caméra
#
# Pour une caméra 640×480 :
#   (0,0) = coin supérieur gauche
#   (640, 480) = coin inférieur droit
# ─────────────────────────────────────────────

FORBIDDEN_ZONES = [
    {
        "id": "zone_electrical_room",
        "name": "Salle électrique",
        "camera_id": "*",  # S'applique à toutes les caméras
        "polygon": [
            (50, 50),
            (200, 50),
            (200, 150),
            (50, 150),
        ],
        "applies_to_classes": ["person"],  # Seulement les personnes
    },
    {
        "id": "zone_forklift_path",
        "name": "Couloir chariots élévateurs",
        "camera_id": "camera_01",
        "polygon": [
            (280, 0),
            (360, 0),
            (360, 480),
            (280, 480),
        ],
        "applies_to_classes": ["person"],
    },
    {
        "id": "zone_fire_exit",
        "name": "Issue de secours — zone dégagée obligatoire",
        "camera_id": "*",
        "polygon": [
            (500, 350),
            (640, 350),
            (640, 480),
            (500, 480),
        ],
        "applies_to_classes": ["box", "pallet"],  # Pas de colis devant la sortie
    },
]


# ─────────────────────────────────────────────
# ALGORITHME "POINT DANS POLYGONE"
# (implémentation maison si shapely absent)
# ─────────────────────────────────────────────

def point_in_polygon_ray_casting(x: float, y: float, polygon: list[tuple]) -> bool:
    """
    Vérifie si le point (x, y) est dans le polygone.
    
    Algorithme de ray casting :
    - On trace un rayon horizontal depuis le point vers la droite
    - On compte combien de fois il croise les côtés du polygone
    - Si le nombre est impair → le point est à l'intérieur
    
    Args:
        x, y : coordonnées du point à tester
        polygon : liste de (x, y) définissant le polygone
    
    Returns:
        True si le point est dans le polygone
    """
    n = len(polygon)
    inside = False
    
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        
        # Le rayon croise-t-il ce côté ?
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        
        j = i
    
    return inside


def is_point_in_zone(x: float, y: float, polygon: list[tuple]) -> bool:
    """
    Vérifie si le point (x, y) est dans la zone interdite.
    Utilise Shapely si disponible (plus robuste), sinon l'algo maison.
    """
    if HAS_SHAPELY:
        point = Point(x, y)
        zone_polygon = Polygon(polygon)
        return zone_polygon.contains(point)
    else:
        return point_in_polygon_ray_casting(x, y, polygon)


# ─────────────────────────────────────────────
# FONCTION PRINCIPALE DE DÉTECTION
# ─────────────────────────────────────────────

class ZoneViolationDetector(FlatMapFunction):
    """
    Pour chaque message de tracking, vérifie si l'objet
    est dans une zone interdite.
    
    FlatMapFunction : pour un input, peut produire 0 ou N outputs.
    - 0 si pas de violation
    - 1 alerte par zone violée
    """
    
    def open(self, runtime_context: RuntimeContext):
        """Appelé une fois au démarrage du job."""
        logger.info(
            f"🔍 ZoneViolationDetector initialisé avec "
            f"{len(FORBIDDEN_ZONES)} zones configurées"
        )
        for zone in FORBIDDEN_ZONES:
            logger.info(f"   Zone: {zone['name']} ({zone['id']})")
    
    def flat_map(self, track_message: str) -> Iterator[str]:
        """
        Analyse un message de tracking et émet des alertes si nécessaire.
        
        Args:
            track_message : JSON brut depuis le topic "tracks"
        
        Yields:
            JSON d'alerte pour chaque violation détectée
        """
        # Parser le message JSON
        try:
            track = json.loads(track_message)
        except json.JSONDecodeError as e:
            logger.error(f"Message invalide : {e}")
            return  # Ignorer ce message
        
        # Vérifier les champs obligatoires
        required = ["track_id", "camera_id", "x_center", "y_center", "class_name"]
        for field in required:
            if field not in track:
                logger.warning(f"Champ manquant '{field}' dans : {track_message[:100]}")
                return
        
        # Extraire les coordonnées du centre de l'objet
        track_id = track["track_id"]
        camera_id = track["camera_id"]
        x = float(track["x_center"])
        y = float(track["y_center"])
        class_name = track["class_name"]
        timestamp_ms = track.get("timestamp_ms", int(time.time() * 1000))
        
        # Vérifier chaque zone interdite
        for zone in FORBIDDEN_ZONES:
            
            # 1. Vérifier si cette zone s'applique à cette caméra
            if zone["camera_id"] != "*" and zone["camera_id"] != camera_id:
                continue  # Cette zone ne concerne pas cette caméra
            
            # 2. Vérifier si cette zone s'applique à ce type d'objet
            applies_to = zone.get("applies_to_classes", ["box", "person", "pallet"])
            if class_name not in applies_to:
                continue  # Cette zone ne concerne pas ce type d'objet
            
            # 3. Vérifier si l'objet est dans la zone
            if is_point_in_zone(x, y, zone["polygon"]):
                
                logger.warning(
                    f"🚨 VIOLATION ZONE INTERDITE ! "
                    f"Objet {track_id} ({class_name}) "
                    f"dans '{zone['name']}' "
                    f"[caméra {camera_id}] "
                    f"position ({x:.0f}, {y:.0f})"
                )
                
                # Créer l'événement d'alerte
                alert_event = {
                    "event_id": f"zone_violation_{track_id}_{zone['id']}_{timestamp_ms}",
                    "type": "zone_violation",
                    "severity": "high",
                    "camera_id": camera_id,
                    "payload": {
                        "track_id": track_id,
                        "class_name": class_name,
                        "zone_id": zone["id"],
                        "zone_name": zone["name"],
                        "object_x": x,
                        "object_y": y,
                        "timestamp_ms": timestamp_ms,
                        "message": (
                            f"L'objet {track_id} ({class_name}) "
                            f"a été détecté dans la zone interdite "
                            f"'{zone['name']}'"
                        ),
                    },
                    "generated_at_ms": int(time.time() * 1000),
                }
                
                yield json.dumps(alert_event)


# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────

def main():
    logger.info("🚀 Démarrage du job Zone Violation Detector")
    logger.info(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"   Topic entrée: {INPUT_TOPIC}")
    logger.info(f"   Topic sortie: {OUTPUT_TOPIC}")
    logger.info(f"   Zones configurées: {len(FORBIDDEN_ZONES)}")
    
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    
    # Source Kafka
    kafka_source = FlinkKafkaConsumer(
        topics=INPUT_TOPIC,
        deserialization_schema=SimpleStringSchema(),
        properties={
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "latest",
        },
    )
    
    # Sink Kafka
    kafka_sink = FlinkKafkaProducer(
        topic=OUTPUT_TOPIC,
        serialization_schema=SimpleStringSchema(),
        producer_config={"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS},
    )
    
    # Pipeline :
    # tracks Kafka → détecter violation → events Kafka
    (
        env
        .add_source(kafka_source)
        .flat_map(
            ZoneViolationDetector(),
            output_type=Types.STRING(),
        )
        .add_sink(kafka_sink)
    )
    
    logger.info("  Exécution du pipeline...")
    env.execute("LOGIVISION Zone Violation Detector")


if __name__ == "__main__":
    main()