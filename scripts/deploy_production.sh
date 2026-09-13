#!/bin/sh
set -eu

SOURCE_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_ROOT="${HOMEDASH_PRODUCTION_ROOT:-$HOME/Library/Application Support/HomeDash/production}"
DATA_ROOT="${HOMEDASH_PRODUCTION_DATA:-$DEPLOY_ROOT/data}"
REF="${1:-HEAD}"
SOURCE_PYTHON="${PYTHON_BIN:-$SOURCE_ROOT/.venv/bin/python}"

if [ ! -x "$SOURCE_PYTHON" ]; then
    echo "Missing source virtual environment: $SOURCE_PYTHON" >&2
    exit 1
fi

mkdir -p "$(dirname -- "$DEPLOY_ROOT")"
if [ ! -e "$DEPLOY_ROOT/.git" ]; then
    git -C "$SOURCE_ROOT" worktree add --detach "$DEPLOY_ROOT" "$REF"
else
    git -C "$DEPLOY_ROOT" checkout --detach "$REF"
fi

if [ ! -x "$DEPLOY_ROOT/.venv/bin/python" ]; then
    "$SOURCE_PYTHON" -m venv "$DEPLOY_ROOT/.venv"
fi
"$DEPLOY_ROOT/.venv/bin/python" -m pip install -q -r "$DEPLOY_ROOT/requirements.txt"

mkdir -p "$DATA_ROOT" "$DATA_ROOT/logs" "$DATA_ROOT/backups"
if [ ! -f "$DATA_ROOT/heating_data.db" ] && [ -f "$SOURCE_ROOT/data/heating_data.db" ]; then
    HOMEDASH_DATABASE="$SOURCE_ROOT/data/heating_data.db" \
        "$SOURCE_PYTHON" "$SOURCE_ROOT/scripts/backup_database.py" \
        --output "$DATA_ROOT/heating_data.db"
fi
if [ -f "$SOURCE_ROOT/config.ini" ]; then
    cp "$SOURCE_ROOT/config.ini" "$DEPLOY_ROOT/config.ini"
fi

HOMEDASH_PRODUCTION_ROOT="$DEPLOY_ROOT" \
HOMEDASH_PRODUCTION_DATA="$DATA_ROOT" \
    sh "$SOURCE_ROOT/scripts/install_production_launch_agent.sh"

echo "Production deployed from $REF at $DEPLOY_ROOT"
