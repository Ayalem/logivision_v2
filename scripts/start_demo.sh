#!/usr/bin/env bash
# Bring up the full LOGIVISION pipeline in one shot. Idempotent: safe to
# re-run; will kill stale demo processes before starting fresh ones.
#
# Logs land in /tmp/logivision-demo-logs/, PIDs in /tmp/logivision-demo.pids.
# Stop with `make demo-stop`.
#
# Env overrides:
#   DEMO_VIDEO   (default: datasets/raw/videos/Camera3.mp4)
#   DEMO_CAMERA  (default: CAM03)
#   DEMO_FPS     (default: 2)
#   DEMO_ROLE    (default: admin — set to "operator" to hide the Système tab)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

DEMO_VIDEO="${DEMO_VIDEO:-datasets/raw/videos/Camera3.mp4}"
DEMO_CAMERA="${DEMO_CAMERA:-CAM03}"
DEMO_FPS="${DEMO_FPS:-2}"
DEMO_ROLE="${DEMO_ROLE:-admin}"

LOG_DIR=/tmp/logivision-demo-logs
PID_FILE=/tmp/logivision-demo.pids
mkdir -p "$LOG_DIR"

cyan()   { printf "\033[1;36m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
amber()  { printf "\033[1;33m%s\033[0m\n" "$*"; }
red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }

# ── 1. Pre-flight ──────────────────────────────────────────────────────
cyan "1/6  Pre-flight checks"
if ! docker info >/dev/null 2>&1; then
    red "    Docker daemon is not reachable. Restart Docker Desktop and try again."
    exit 1
fi

# Are the core LOGIVISION containers running?
required="logivision-mlops-mlflow logivision-mlops-postgres logivision-mlops-minio logivision-kafka"
missing=()
for c in $required; do
    state=$(docker inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
    if [[ "$state" != "running" ]]; then
        missing+=("$c")
    fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
    amber "    Some containers are not running: ${missing[*]}"
    cyan "    Running \`make bootstrap\` + \`make kafka-up\` for you..."
    make bootstrap 2>&1 | tail -3
    make kafka-up  2>&1 | tail -3
fi
green "    Docker + LOGIVISION stack ready"

# ── 2. Camera symlinks ────────────────────────────────────────────────
cyan "2/6  Camera videos"
make camera-videos 2>&1 | tail -3 || amber "    (camera-videos warning ignored)"

# ── 3. Kill stale demo processes ──────────────────────────────────────
cyan "3/6  Cleaning up any stale demo processes"
"$SCRIPT_DIR/stop_demo.sh" --quiet 2>/dev/null || true

# ── 4. Source .env (so MinIO/MLflow creds match Docker stack) ─────────
if [[ -f .env ]]; then
    set -a; . ./.env; set +a
fi

export DYLD_LIBRARY_PATH="/opt/homebrew/opt/zbar/lib:${DYLD_LIBRARY_PATH:-}"
export LOGIVISION_ROLE="$DEMO_ROLE"

# ── 5. Launch services (logs to $LOG_DIR, PIDs tracked in $PID_FILE) ──
cyan "4/6  Starting API on :8000"
nohup uv run uvicorn services.api.main:app --host 0.0.0.0 --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
api_pid=$!
echo "api=$api_pid" > "$PID_FILE"

# Wait for the API to bind
for i in $(seq 1 20); do
    sleep 0.5
    if curl -s -o /dev/null --max-time 1 http://localhost:8000/api/me; then
        green "    API ready (pid $api_pid)"
        break
    fi
    [[ $i -eq 20 ]] && { red "    API failed to bind. Check $LOG_DIR/api.log"; exit 1; }
done

cyan "5/6  Starting frame_grabber → inference_worker → cep"
if [[ ! -f "$DEMO_VIDEO" ]]; then
    red "    Video missing: $DEMO_VIDEO"
    red "    Run \`make camera-videos\` and ensure the source MP4 is on disk."
    exit 1
fi
nohup uv run python -m services.frame_grabber.grabber \
    --source "$DEMO_VIDEO" --camera-id "$DEMO_CAMERA" --fps "$DEMO_FPS" \
    > "$LOG_DIR/grabber.log" 2>&1 &
echo "grabber=$!" >> "$PID_FILE"

nohup uv run python -m services.inference_worker.worker \
    > "$LOG_DIR/worker.log" 2>&1 &
echo "worker=$!" >> "$PID_FILE"

nohup uv run python -m services.stream_processor.cep \
    --zones infra/zones.example.yaml \
    > "$LOG_DIR/cep.log" 2>&1 &
echo "cep=$!" >> "$PID_FILE"

sleep 2  # let things bind

# ── 6. Summary ────────────────────────────────────────────────────────
cyan "6/6  Demo is live"
echo ""
green "  Dashboard:    http://localhost:8000  (LOGIVISION_ROLE=$DEMO_ROLE)"
green "  MLflow:       http://localhost:5050"
green "  MinIO:        http://localhost:9001  (logivision / change-me-in-local-minimum-8-chars)"
green "  Kafka UI:     http://localhost:8086"
echo ""
echo "  Source video: $DEMO_VIDEO → Kafka topic raw-frames as $DEMO_CAMERA @ $DEMO_FPS fps"
echo "  Logs:         $LOG_DIR/{api,grabber,worker,cep}.log"
echo "  PIDs:         $(cat $PID_FILE | tr '\n' ' ')"
echo ""
echo "  Tail logs:    make demo-logs"
echo "  Stop demo:    make demo-stop"
