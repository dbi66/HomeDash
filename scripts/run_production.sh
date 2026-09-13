#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
BIND_ADDRESS="${HOMEDASH_BIND:-0.0.0.0}"
PORT="${HOMEDASH_PORT:-8501}"
DATABASE_PATH="${HOMEDASH_DATABASE:-$PROJECT_ROOT/data/heating_data.db}"

cd "$PROJECT_ROOT"
HOMEDASH_DATABASE="$DATABASE_PATH" exec "$PYTHON_BIN" -m streamlit run app.py \
    --server.address "$BIND_ADDRESS" \
    --server.port "$PORT" \
    --server.headless true
