"""
Job Flink : Agrégation des métriques de détection.

Ce job écoute le topic Kafka "detections" et calcule :
- Le nombre de colis traités par minute (fenêtre tumbling de 60 secondes)

Il publie les résultats dans le topic "events".

Utilisation :
    python services/flink-jobs/jobs/kpi_aggregator.py
"""

import json
import logging
import os
from datetime import datetime

from pyflink.common import Time, Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.watermark_strategy import (
    TimestampAssigner,
    WatermarkStrategy,
)
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    FlinkKafkaConsumer,
    FlinkKafkaProducer,
)
from pyflink.datastream.functions import ProcessWindowFunction
from pyflink.datastream.window import TumblingEventTimeWindows

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURATION — modifie ces valeurs si besoin
# ─────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "detections"   # Topic qu'on écoute
OUTPUT_TOPIC = "events"      # Topic où on publie les alertes
CONSUMER_GROUP = "flink-kpi-aggregator"
WINDOW_SIZE_SECONDS = 60     # Fenêtre de 1 minute


# ─────────────────────────────────────────────
# ÉTAPE 1 : Parser les messages JSON entrants
# ─────────────────────────────────────────────

def parse_detection_message(raw_message: str) -> dict | None:
    """
    Transforme un message JSON brut en dictionnaire Python.
    
    Retourne None si le message est invalide (on l'ignore).
    """
    try:
        data = json.loads(raw_message)
        
        # Vérification minimale : on a besoin de ces champs
        required_fields = ["frame_id", "camera_id", "timestamp_ms", "detections"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Message ignoré : champ manquant '{field}'")
                return None
        
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Impossible de parser le message JSON : {e}")
        return None


# ─────────────────────────────────────────────
# ÉTAPE 2 : Extraire le nombre de détections
# ─────────────────────────────────────────────

def extract_detection_count(message: dict) -> tuple[str, int, int]:
    """
    Extrait les informations utiles d'un message de détection.
    
    Retourne : (camera_id, nombre_de_detections, timestamp_ms)
    """
    camera_id = message["camera_id"]
    # len(detections) = nombre d'objets détectés dans cette frame
    num_detections = len(message.get("detections", []))
    timestamp_ms = message["timestamp_ms"]
    
    return (camera_id, num_detections, timestamp_ms)


# ─────────────────────────────────────────────
# ÉTAPE 3 : Agréger par fenêtre de 1 minute
# ─────────────────────────────────────────────

class CountPerMinuteFunction(ProcessWindowFunction):
    """
    Fonction appelée à la fin de chaque fenêtre de 1 minute.
    
    Elle reçoit toutes les détections de la dernière minute
    et calcule le total.
    """
    
    def process(
        self,
        key: str,            # camera_id
        context,             # infos sur la fenêtre (début, fin)
        elements,            # toutes les détections de la fenêtre
    ):
        """
        Calcule le total de colis pour une caméra sur 1 minute.
        """
        total_packages = 0
        for camera_id, count, ts in elements:
            total_packages += count
        
        # Récupérer les timestamps de début et fin de la fenêtre
        window_start = context.window().start  # timestamp en ms
        window_end = context.window().end
        
        # Convertir en format lisible
        start_dt = datetime.fromtimestamp(window_start / 1000).strftime("%H:%M:%S")
        end_dt = datetime.fromtimestamp(window_end / 1000).strftime("%H:%M:%S")
        
        logger.info(
            f"📦 Caméra {key} | Fenêtre {start_dt}→{end_dt} | "
            f"{total_packages} colis traités"
        )
        
        # Créer l'événement de sortie
        event = {
            "event_id": f"kpi_{key}_{window_end}",
            "type": "packages_per_minute",
            "severity": "info",
            "camera_id": key,
            "payload": {
                "total_packages_in_window": total_packages,
                "window_start_ms": window_start,
                "window_end_ms": window_end,
                "window_start_human": start_dt,
                "window_end_human": end_dt,
            },
            "generated_at_ms": window_end,
        }
        
        yield json.dumps(event)


# ─────────────────────────────────────────────
# ÉTAPE 4 : Assigner les timestamps aux events
# ─────────────────────────────────────────────

class DetectionTimestampAssigner(TimestampAssigner):
    """
    Indique à Flink quel champ utiliser comme timestamp.
    
    C'est important pour que les fenêtres temporelles
    fonctionnent correctement même si les messages
    arrivent dans le désordre.
    """
    
    def extract_timestamp(self, value, record_timestamp: int) -> int:
        # value est un tuple (camera_id, count, timestamp_ms)
        camera_id, count, timestamp_ms = value
        return timestamp_ms


# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────

def main():
    """
    Point d'entrée du job Flink.
    
    Crée le pipeline et le lance.
    """
    logger.info("🚀 Démarrage du job KPI Aggregator")
    logger.info(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"   Topic entrée: {INPUT_TOPIC}")
    logger.info(f"   Topic sortie: {OUTPUT_TOPIC}")
    logger.info(f"   Fenêtre: {WINDOW_SIZE_SECONDS} secondes")
    
    # ── 1. Créer l'environnement d'exécution Flink ──
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)  # 1 pour commencer, à augmenter en prod
    
    # ── 2. Configurer le consumer Kafka (source) ──
    kafka_consumer_props = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "latest",  # Commencer depuis les nouveaux messages
    }
    
    kafka_source = FlinkKafkaConsumer(
        topics=INPUT_TOPIC,
        deserialization_schema=SimpleStringSchema(),
        properties=kafka_consumer_props,
    )
    
    # ── 3. Configurer le producer Kafka (sink) ──
    kafka_sink = FlinkKafkaProducer(
        topic=OUTPUT_TOPIC,
        serialization_schema=SimpleStringSchema(),
        producer_config={
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        },
    )
    
    # ── 4. Définir la stratégie de watermark ──
    # Le watermark indique à Flink de tolérer X ms de retard
    # dans l'arrivée des messages (réseau, etc.)
    watermark_strategy = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Time.seconds(5))  # 5s de tolérance
        .with_timestamp_assigner(DetectionTimestampAssigner())
    )
    
    # ── 5. Construire le pipeline ──
    # 
    # Voici comment lire le pipeline (de haut en bas) :
    # 1. Lire depuis Kafka
    # 2. Parser le JSON
    # 3. Filtrer les messages invalides
    # 4. Extraire (camera_id, nb_detections, timestamp)
    # 5. Assigner les timestamps pour les fenêtres
    # 6. Grouper par camera_id (key_by)
    # 7. Fenêtre de 60 secondes
    # 8. Compter le total par fenêtre
    # 9. Écrire dans Kafka
    
    (
        env
        # Étape 1 : Lire les messages Kafka
        .add_source(kafka_source)
        
        # Étape 2 : Parser JSON → dict Python
        .map(parse_detection_message, output_type=Types.PICKLED_BYTE_ARRAY())
        
        # Étape 3 : Ignorer les messages invalides (None)
        .filter(lambda msg: msg is not None)
        
        # Étape 4 : Extraire les champs utiles
        # Résultat : (camera_id, nb_detections, timestamp_ms)
        .map(
            extract_detection_count,
            output_type=Types.TUPLE([Types.STRING(), Types.INT(), Types.LONG()]),
        )
        
        # Étape 5 : Assigner les timestamps pour Flink
        .assign_timestamps_and_watermarks(watermark_strategy)
        
        # Étape 6 : Grouper par camera_id (le premier élément du tuple)
        .key_by(lambda x: x[0])
        
        # Étape 7 : Fenêtre tumbling de 60 secondes
        # "Tumbling" = non-chevauchante : 0-60s, 60-120s, 120-180s...
        .window(TumblingEventTimeWindows.of(Time.seconds(WINDOW_SIZE_SECONDS)))
        
        # Étape 8 : Calculer le total dans la fenêtre
        .process(
            CountPerMinuteFunction(),
            output_type=Types.STRING(),
        )
        
        # Étape 9 : Publier dans Kafka
        .add_sink(kafka_sink)
    )
    
    # ── 6. Lancer le job ──
    logger.info("▶️  Exécution du pipeline Flink...")
    env.execute("LOGIVISION KPI Aggregator — Packages per Minute")


if __name__ == "__main__":
    main()