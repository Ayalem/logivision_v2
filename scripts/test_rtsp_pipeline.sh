#!/usr/bin/env bash
# scripts/test_rtsp_pipeline.sh
#
# Test end-to-end : simule une caméra RTSP via FFmpeg → MediaMTX → Frame Grabber → Kafka
#
# Prérequis :
#   - make kafka-up (Kafka + MediaMTX démarrés)
#   - ffmpeg installé (brew install ffmpeg / apt install ffmpeg)
#   - uv sync --all-groups
#   - Un fichier vidéo dans datasets/raw/videos/ (ex: Camera1.mp4)
#
# Usage :
#   ./scripts/test_rtsp_pipeline.sh
#   ./scripts/test_rtsp_pipeline.sh --video datasets/raw/videos/Camera1.mp4 --frames 20

set -euo pipefail

VIDEO="${1:-datasets/raw/videos/Camera1.mp4}"
MAX_FRAMES="${2:-10}"
CAMERA_ID="CAM_TEST"
RTSP_PATH="test"
MEDIAMTX_HOST="localhost"
RTSP_PORT="8554"
KAFKA_BOOTSTRAP="${KAFKA_BOOTSTRAP:-localhost:9092}"
TOPIC="raw-frames"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

while [[ $# -gt 0 ]]; do
  case $1 in
    --video)   VIDEO="$2";      shift 2 ;;
    --frames)  MAX_FRAMES="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

log_info "=== Test end-to-end RTSP Pipeline LOGIVISION ==="

if [[ ! -f "$VIDEO" ]]; then
  log_error "Fichier vidéo introuvable : $VIDEO"
  log_error "Lance d'abord : make fetch-taltech-videos"
  exit 1
fi
log_ok "Vidéo source : $VIDEO"

if ! command -v ffmpeg &>/dev/null; then
  log_error "ffmpeg non installé."
  exit 1
fi
log_ok "ffmpeg disponible"

if ! curl -sf "http://${MEDIAMTX_HOST}:9997/v3/paths/list" &>/dev/null; then
  log_error "MediaMTX non joignable — lance : make kafka-up"
  exit 1
fi
log_ok "MediaMTX actif"

if ! docker exec logivision-kafka \
    /opt/kafka/bin/kafka-broker-api-versions.sh \
    --bootstrap-server localhost:9094 &>/dev/null; then
  log_error "Kafka non joignable — lance : make kafka-up"
  exit 1
fi
log_ok "Kafka actif"

RTSP_URL="rtsp://${MEDIAMTX_HOST}:${RTSP_PORT}/${RTSP_PATH}"
log_info "Publication RTSP : $VIDEO → $RTSP_URL"

ffmpeg -re -stream_loop -1 \
  -i "$VIDEO" \
  -c copy \
  -f rtsp \
  "$RTSP_URL" \
  -loglevel error &
FFMPEG_PID=$!
log_ok "FFmpeg PID=$FFMPEG_PID"

sleep 3

log_info "Lancement du Frame Grabber → topic ${TOPIC}..."
uv run python -m services.frame_grabber.grabber \
  --source "$RTSP_URL" \
  --camera-id "$CAMERA_ID" \
  --fps 2 \
  --max "$MAX_FRAMES" \
  --log-level INFO

GRABBER_EXIT=$?

kill "$FFMPEG_PID" 2>/dev/null || true
wait "$FFMPEG_PID" 2>/dev/null || true

MSG_COUNT=$(docker exec logivision-kafka \
  /opt/kafka/bin/kafka-run-class.sh kafka.tools.GetOffsetShell \
  --bootstrap-server localhost:9094 \
  --topic "$TOPIC" \
  --time -1 2>/dev/null \
  | awk -F: '{sum += $3} END {print sum+0}')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Résultats du test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ $GRABBER_EXIT -eq 0 ]]; then
  log_ok "Frame Grabber terminé sans erreur"
else
  log_error "Frame Grabber a terminé avec le code $GRABBER_EXIT"
fi

log_info "Messages dans ${TOPIC} : ${MSG_COUNT}"

if [[ "$MSG_COUNT" -ge "$MAX_FRAMES" ]]; then
  log_ok "✅ Pipeline RTSP → Kafka opérationnel !"
  exit 0
else
  log_warn "⚠️  Seulement ${MSG_COUNT} messages trouvés (attendu: ${MAX_FRAMES})"
  exit 1
fi
