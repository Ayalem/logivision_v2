#!/usr/bin/env bash
# Boot the local MLOps stack (PostgreSQL + MinIO + MLflow).
# Idempotent: re-run safely. Target time on a standard laptop: < 90 s cold,
# < 20 s warm (volumes + images cached).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT/infra/docker-compose/docker-compose.mlops.yml"
ENV_FILE="$ROOT/.env"
ENV_EXAMPLE="$ROOT/.env.example"

log() { printf "\033[1;36m[bootstrap]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[bootstrap]\033[0m %s\n" "$*" >&2; }

# 1. Ensure .env exists.
if [[ ! -f "$ENV_FILE" ]]; then
    log ".env not found — creating from .env.example."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    log "  ⚠️  edit $ENV_FILE before any production-like use."
fi

# 2. Pre-flight: docker daemon reachable.
if ! docker info >/dev/null 2>&1; then
    err "Docker daemon is not reachable. Start Docker Desktop / dockerd and retry."
    exit 1
fi

# 3. Bring the stack up.
log "Building images and starting services…"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

# 4. Wait for healthchecks.
wait_for_health() {
    local container="$1"
    local timeout="${2:-120}"
    local elapsed=0
    local interval=2
    local last_status=""
    log "Waiting for $container to be healthy (max ${timeout}s)…"
    while [[ $elapsed -lt $timeout ]]; do
        local status
        status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
                 "$container" 2>/dev/null || echo "missing")
        case "$status" in
            healthy|running)
                log "  $container: $status"
                return 0
                ;;
            exited)
                err "  $container exited — docker logs $container"
                return 1
                ;;
        esac
        if [[ "$status" != "$last_status" ]]; then
            log "  $container: $status"
            last_status="$status"
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    err "  $container: timeout after ${timeout}s — docker logs $container"
    return 1
}

# Postgres + MinIO have explicit healthchecks. MLflow doesn't (image is custom);
# we wait until its HTTP /health responds.
wait_for_health logivision-mlops-postgres 60
wait_for_health logivision-mlops-minio 60

MLFLOW_PORT="$(grep -E '^MLFLOW_PORT=' "$ENV_FILE" | cut -d= -f2)"
MLFLOW_PORT="${MLFLOW_PORT:-5050}"
log "Waiting for MLflow /health on :${MLFLOW_PORT}…"
mlflow_ok=0
for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null "http://localhost:${MLFLOW_PORT}/health"; then
        mlflow_ok=1
        break
    fi
    sleep 2
done
if [[ $mlflow_ok -eq 0 ]]; then
    err "MLflow /health never responded — docker logs logivision-mlops-mlflow"
    exit 1
fi
log "  logivision-mlops-mlflow: healthy"

# 5. Print URLs.
cat <<EOF

✅ MLOps stack is up.

  MLflow UI:     http://localhost:${MLFLOW_PORT}
  MinIO Console: http://localhost:9001   (user: $(grep '^MINIO_ROOT_USER=' "$ENV_FILE" | cut -d= -f2))
  PostgreSQL:    localhost:5432          (user: $(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2))

Buckets: mlflow, datasets, models, frames

Stop with:        make down
Wipe volumes:     make clean
Smoke tests:      uv run pytest tests/integration -m integration
EOF
