#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
BIND_ADDRESS="${HOMEDASH_BIND:-0.0.0.0}"
PORT="${HOMEDASH_PORT:-8501}"
COLLECTOR_INTERVAL="${HOMEDASH_COLLECTOR_INTERVAL:-300}"
VIESSMANN_COLLECTOR_INTERVAL="${HOMEDASH_VIESSMANN_INTERVAL:-1800}"

cd "$PROJECT_ROOT"

cleanup() {
    if [ -n "${COLLECTOR_PID:-}" ]; then
        kill "$COLLECTOR_PID" 2>/dev/null || true
        wait "$COLLECTOR_PID" 2>/dev/null || true
    fi
    if [ -n "${VIESSMANN_COLLECTOR_PID:-}" ]; then
        kill "$VIESSMANN_COLLECTOR_PID" 2>/dev/null || true
        wait "$VIESSMANN_COLLECTOR_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

"$PYTHON_BIN" scripts/collect_snapshot.py --interval "$COLLECTOR_INTERVAL" &
COLLECTOR_PID=$!

"$PYTHON_BIN" scripts/collect_viessmann.py --interval "$VIESSMANN_COLLECTOR_INTERVAL" &
VIESSMANN_COLLECTOR_PID=$!

"$PYTHON_BIN" -m streamlit run app.py \
    --server.address "$BIND_ADDRESS" \
    --server.port "$PORT" \
    --server.headless true
