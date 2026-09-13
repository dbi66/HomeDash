#!/bin/sh
set -eu

PLIST="$HOME/Library/LaunchAgents/com.homedash.production.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/com.homedash.production" 2>/dev/null || true
rm -f "$PLIST"
echo "Production LaunchAgent removed. Existing databases were not changed."
