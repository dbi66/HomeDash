#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TEMPLATE="$PROJECT_ROOT/scripts/com.homedash.production.plist.template"
PLIST="$HOME/Library/LaunchAgents/com.homedash.production.plist"
DOMAIN="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_ROOT/data/logs"
sed "s#__PROJECT_ROOT__#$PROJECT_ROOT#g" "$TEMPLATE" > "$PLIST"
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/com.homedash.production" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/com.homedash.production"
launchctl kickstart -k "$DOMAIN/com.homedash.production"

echo "Production LaunchAgent installed and started."
echo "Dashboard: http://localhost:8501"
