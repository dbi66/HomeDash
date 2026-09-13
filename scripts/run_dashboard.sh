#!/bin/sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
BIND_ADDRESS="${HOMEDASH_BIND:-127.0.0.1}"
PORT="${HOMEDASH_PORT:-8501}"

exec "$PYTHON_BIN" -m streamlit run app.py \
    --server.address "$BIND_ADDRESS" \
    --server.port "$PORT" \
    --server.headless true
