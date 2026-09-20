#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
BIND_ADDRESS="${HOMEDASH_BIND:-0.0.0.0}"
PORT="${HOMEDASH_PORT:-8501}"
COLLECTOR_INTERVAL="${HOMEDASH_COLLECTOR_INTERVAL:-900}"
VIESSMANN_COLLECTOR_INTERVAL="${HOMEDASH_VIESSMANN_INTERVAL:-1800}"

cd "$PROJECT_ROOT"

if [ "$PORT" != "8501" ]; then
    echo "Migration production requires port 8501." >&2
    exit 1
fi

exec 9>"$PROJECT_ROOT/data/.homedash-collectors.lock"
if ! flock -n 9; then
    echo "Another HomeDash collector set is already active." >&2
    exit 1
fi

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

exec "$PYTHON_BIN" -m uvicorn migration.api:app --host "$BIND_ADDRESS" --port "$PORT"