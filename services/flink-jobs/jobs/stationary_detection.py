"""
Job Flink CEP : Détection de colis stationnaires.

Ce job écoute le topic Kafka "tracks" et déclenche une alerte
si un objet (colis, personne) n'a pas bougé ses coordonnées
pendant plus de STATIONARY_THRESHOLD_SECONDS secondes.

Utilisation :
    python services/flink-jobs/jobs/stationary_detection.py
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
from pyflink.datastream.functions import (
    FlatMapFunction,
    KeyedProcessFunction,
    RuntimeContext,
)
from pyflink.datastream.state import ValueStateDescriptor

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
CONSUMER_GROUP = "flink-stationary-detection"

# Seuil : combien de secondes sans bouger → ALERTE
STATIONARY_THRESHOLD_SECONDS = int(
    os.getenv("STATIONARY_THRESHOLD_SECONDS", "300")  # 5 minutes par défaut
)

# Tolérance de mouvement : en dessous de ce nombre de pixels,
# on considère que l'objet n'a pas bougé (vibrations, bruit caméra)
MOVEMENT_TOLERANCE_PIXELS = float(
    os.getenv("MOVEMENT_TOLERANCE_PIXELS", "15.0")
)

# Classes d'objets à surveiller
MONITORED_CLASSES = ["box", "pallet"]  # On ignore les personnes (elles bougent)


# ─────────────────────────────────────────────
# CALCUL DE DISTANCE
# ─────────────────────────────────────────────

def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calcule la distance euclidienne entre deux points (en pixels).
    
    Formule : sqrt((x2-x1)² + (y2-y1)²)
    """
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def has_object_moved(
    old_x: float, old_y: float,
    new_x: float, new_y: float,
    tolerance: float = MOVEMENT_TOLERANCE_PIXELS,
) -> bool:
    """
    Retourne True si l'objet a bougé de plus de `tolerance` pixels.
    """
    distance = calculate_distance(old_x, old_y, new_x, new_y)
    return distance > tolerance


# ─────────────────────────────────────────────
# PARSER DE MESSAGES
# ─────────────────────────────────────────────

class TrackMessageParser(FlatMapFunction):
    """
    Parse les messages JSON du topic "tracks".
    Ignore les messages invalides ou pour des classes non surveillées.
    """
    
    def flat_map(self, raw_message: str) -> Iterator[tuple]:
        """
        Transforme un message JSON en tuple Python.
        
        Yields: (track_id, camera_id, x, y, class_name, timestamp_ms)
        """
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            return  # Message invalide, on ignore
        
        required = ["track_id", "camera_id", "x_center", "y_center", "class_name"]
        for field in required:
            if field not in msg:
                return  # Champ manquant, on ignore
        
        class_name = msg["class_name"]
        
        # On ne surveille que certaines classes
        if class_name not in MONITORED_CLASSES:
            return
        
        timestamp_ms = msg.get("timestamp_ms", int(time.time() * 1000))
        
        yield (
            msg["track_id"],          # [0] identifiant unique de l'objet
            msg["camera_id"],         # [1] caméra
            float(msg["x_center"]),   # [2] position X (centre)
            float(msg["y_center"]),   # [3] position Y (centre)
            class_name,               # [4] type d'objet
            timestamp_ms,             # [5] timestamp en millisecondes
        )


# ─────────────────────────────────────────────
# DÉTECTEUR STATIONNAIRE (avec état Flink)
# ─────────────────────────────────────────────

class StationaryObjectDetector(KeyedProcessFunction):
    """
    Détecte les objets qui ne bougent pas.
    
    Flink se souvient pour chaque track_id :
    - La dernière position connue
    - Le timestamp où il était à cette position pour la 1ère fois
    
    KeyedProcessFunction = la fonction est appelée séparément
    pour chaque track_id (partitionnement automatique par Flink).
    """
    
    # Ces attributs stockent l'état en mémoire Flink
    # (persistant entre les messages du même track_id)
    last_x_state: any = None
    last_y_state: any = None
    first_seen_at_position_state: any = None
    alert_already_sent_state: any = None
    
    def open(self, runtime_context: RuntimeContext):
        """
        Initialiser les "descripteurs d'état" Flink.
        
        Un ValueState = une valeur mémorisée par clé (ici par track_id).
        """
        # Mémoriser la dernière position X
        self.last_x_state = runtime_context.get_state(
            ValueStateDescriptor("last_x", Types.FLOAT())
        )
        
        # Mémoriser la dernière position Y
        self.last_y_state = runtime_context.get_state(
            ValueStateDescriptor("last_y", Types.FLOAT())
        )
        
        # Mémoriser depuis quand l'objet est à cette position (timestamp en ms)
        self.first_seen_at_position_state = runtime_context.get_state(
            ValueStateDescriptor("first_seen_at_position", Types.LONG())
        )
        
        # Pour ne pas envoyer 1000 alertes pour le même objet stationnaire
        self.alert_already_sent_state = runtime_context.get_state(
            ValueStateDescriptor("alert_sent", Types.BOOLEAN())
        )
        
        logger.info(
            f"🔍 StationaryObjectDetector initialisé\n"
            f"   Seuil: {STATIONARY_THRESHOLD_SECONDS}s sans mouvement\n"
            f"   Tolérance: {MOVEMENT_TOLERANCE_PIXELS}px\n"
            f"   Classes surveillées: {MONITORED_CLASSES}"
        )
    
    def process_element(
        self,
        value: tuple,
        ctx: KeyedProcessFunction.Context,
    ) -> Iterator[str]:
        """
        Appelé pour chaque message d'un track_id donné.
        
        Logique :
        1. Lire la dernière position mémorisée
        2. L'objet a-t-il bougé ?
            → OUI : reset le timer, mémoriser nouvelle position
            → NON : calculer combien de temps sans bouger
                → Dépasse le seuil ? → Envoyer alerte (une seule fois)
        """
        track_id, camera_id, new_x, new_y, class_name, timestamp_ms = value
        
        # ── Lire l'état actuel ──
        last_x = self.last_x_state.value()
        last_y = self.last_y_state.value()
        first_seen_at = self.first_seen_at_position_state.value()
        alert_sent = self.alert_already_sent_state.value()
        
        # ── Premier message pour cet objet ──
        if last_x is None:
            # Initialisation : mémoriser la position actuelle
            self.last_x_state.update(new_x)
            self.last_y_state.update(new_y)
            self.first_seen_at_position_state.update(timestamp_ms)
            self.alert_already_sent_state.update(False)
            logger.debug(f"Nouvel objet suivi: {track_id} à ({new_x:.0f}, {new_y:.0f})")
            return
        
        # ── L'objet a-t-il bougé ? ──
        moved = has_object_moved(last_x, last_y, new_x, new_y)
        
        if moved:
            # L'objet a bougé → reset tout
            logger.debug(
                f"Objet {track_id} en mouvement "
                f"({last_x:.0f},{last_y:.0f}) → ({new_x:.0f},{new_y:.0f})"
            )
            self.last_x_state.update(new_x)
            self.last_y_state.update(new_y)
            self.first_seen_at_position_state.update(timestamp_ms)
            self.alert_already_sent_state.update(False)
            return
        
        # ── L'objet n'a pas bougé ──
        # Calculer combien de temps il est immobile (en secondes)
        stationary_duration_ms = timestamp_ms - first_seen_at
        stationary_duration_sec = stationary_duration_ms / 1000
        
        logger.debug(
            f"Objet {track_id} immobile depuis "
            f"{stationary_duration_sec:.0f}s "
            f"(seuil: {STATIONARY_THRESHOLD_SECONDS}s)"
        )
        
        # ── Dépasse le seuil et alerte pas encore envoyée ? ──
        if (
            stationary_duration_sec >= STATIONARY_THRESHOLD_SECONDS
            and not alert_sent
        ):
            logger.warning(
                f"🚨 COLIS STATIONNAIRE ! "
                f"Objet {track_id} ({class_name}) "
                f"immobile depuis {stationary_duration_sec:.0f}s "
                f"à ({new_x:.0f}, {new_y:.0f}) "
                f"[caméra {camera_id}]"
            )
            
            # Marquer l'alerte comme envoyée (pour ne pas spam)
            self.alert_already_sent_state.update(True)
            
            # Créer l'événement d'alerte
            alert_event = {
                "event_id": f"stationary_{track_id}_{timestamp_ms}",
                "type": "stationary_object",
                "severity": "medium",
                "camera_id": camera_id,
                "payload": {
                    "track_id": track_id,
                    "class_name": class_name,
                    "position_x": new_x,
                    "position_y": new_y,
                    "stationary_since_ms": first_seen_at,
                    "stationary_duration_seconds": stationary_duration_sec,
                    "threshold_seconds": STATIONARY_THRESHOLD_SECONDS,
                    "message": (
                        f"L'objet {track_id} ({class_name}) "
                        f"n'a pas bougé depuis "
                        f"{stationary_duration_sec:.0f} secondes "
                        f"(position: {new_x:.0f}, {new_y:.0f})"
                    ),
                },
                "generated_at_ms": int(time.time() * 1000),
            }
            
            yield json.dumps(alert_event)


# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────

def main():
    logger.info("🚀 Démarrage du job Stationary Object Detector")
    logger.info(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"   Topic entrée: {INPUT_TOPIC}")
    logger.info(f"   Topic sortie: {OUTPUT_TOPIC}")
    logger.info(f"   Seuil stationnaire: {STATIONARY_THRESHOLD_SECONDS}s")
    logger.info(f"   Tolérance mouvement: {MOVEMENT_TOLERANCE_PIXELS}px")
    
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    
    # Activer le checkpointing (Flink sauvegarde l'état régulièrement)
    env.enable_checkpointing(60_000)  # Toutes les 60 secondes
    
    kafka_source = FlinkKafkaConsumer(
        topics=INPUT_TOPIC,
        deserialization_schema=SimpleStringSchema(),
        properties={
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "latest",
        },
    )
    
    kafka_sink = FlinkKafkaProducer(
        topic=OUTPUT_TOPIC,
        serialization_schema=SimpleStringSchema(),
        producer_config={"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS},
    )
    
    # Pipeline :
    # tracks Kafka → parser → grouper par track_id → détecter stationnaire → events Kafka
    (
        env
        .add_source(kafka_source)
        
        # Parser + filtrer les messages non pertinents
        .flat_map(
            TrackMessageParser(),
            output_type=Types.TUPLE([
                Types.STRING(),  # track_id
                Types.STRING(),  # camera_id
                Types.FLOAT(),   # x_center
                Types.FLOAT(),   # y_center
                Types.STRING(),  # class_name
                Types.LONG(),    # timestamp_ms
            ]),
        )
        
        # Grouper par track_id (chaque objet est traité indépendamment)
        .key_by(lambda x: x[0])
        
        # Détecter les objets stationnaires
        .process(
            StationaryObjectDetector(),
            output_type=Types.STRING(),
        )
        
        .add_sink(kafka_sink)
    )
    
    logger.info("  Exécution du pipeline...")
    env.execute("LOGIVISION Stationary Object Detector")


if __name__ == "__main__":
    main()