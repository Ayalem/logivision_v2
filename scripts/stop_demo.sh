#!/usr/bin/env bash
# Stop the LOGIVISION demo started by start_demo.sh.
#
# Pass --quiet to suppress messages when used internally.
set -euo pipefail

PID_FILE=/tmp/logivision-demo.pids
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

log() { [[ $QUIET -eq 0 ]] && printf "\033[1;36m%s\033[0m\n" "$*" || true; }

# Stop by PID file (clean path)
if [[ -f "$PID_FILE" ]]; then
    log "stopping tracked demo processes:"
    while IFS= read -r entry; do
        name="${entry%%=*}"
        pid="${entry##*=}"
        if kill "$pid" 2>/dev/null; then
            log "  $name (pid $pid) → SIGTERM"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Catch any orphans (in case the user started services manually)
for pattern in \
    'uvicorn services.api.main' \
    'services.inference_worker.worker' \
    'services.frame_grabber.grabber' \
    'services.stream_processor.cep' \
    'services.qr_decoder.decoder'; do
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        log "  killing orphan: $pattern"
        pkill -f "$pattern" 2>/dev/null || true
    fi
done

[[ $QUIET -eq 0 ]] && printf "\033[1;32m%s\033[0m\n" "demo stopped" || true
