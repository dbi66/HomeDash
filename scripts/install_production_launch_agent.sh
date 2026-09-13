#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_ROOT="${HOMEDASH_PRODUCTION_ROOT:-$HOME/Library/Application Support/HomeDash/production}"
DATA_ROOT="${HOMEDASH_PRODUCTION_DATA:-$DEPLOY_ROOT/data}"
TEMPLATE="$PROJECT_ROOT/scripts/com.homedash.production.plist.template"
PLIST="$HOME/Library/LaunchAgents/com.homedash.production.plist"
COLLECTOR_TEMPLATE="$PROJECT_ROOT/scripts/com.homedash.production-collector.plist.template"
COLLECTOR_PLIST="$HOME/Library/LaunchAgents/com.homedash.production-collector.plist"
DOMAIN="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_ROOT/data/logs"
if [ ! -x "$DEPLOY_ROOT/.venv/bin/python" ]; then
	echo "Production deployment is missing: $DEPLOY_ROOT" >&2
	echo "Run scripts/deploy_production.sh first." >&2
	exit 1
fi
mkdir -p "$DATA_ROOT/logs" "$DATA_ROOT/backups"
sed -e "s#__PRODUCTION_ROOT__#$DEPLOY_ROOT#g" -e "s#__PRODUCTION_DATA__#$DATA_ROOT#g" "$TEMPLATE" > "$PLIST"
sed -e "s#__PRODUCTION_ROOT__#$DEPLOY_ROOT#g" -e "s#__PRODUCTION_DATA__#$DATA_ROOT#g" "$COLLECTOR_TEMPLATE" > "$COLLECTOR_PLIST"
plutil -lint "$PLIST" >/dev/null
plutil -lint "$COLLECTOR_PLIST" >/dev/null

launchctl bootout "$DOMAIN/com.homedash.production" 2>/dev/null || true
launchctl bootout "$DOMAIN/com.homedash.production-collector" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl bootstrap "$DOMAIN" "$COLLECTOR_PLIST"
launchctl enable "$DOMAIN/com.homedash.production"
launchctl enable "$DOMAIN/com.homedash.production-collector"
launchctl kickstart -k "$DOMAIN/com.homedash.production"
launchctl kickstart -k "$DOMAIN/com.homedash.production-collector"

echo "Production LaunchAgent installed and started."
echo "Dashboard: http://localhost:8501"
