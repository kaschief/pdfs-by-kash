#!/usr/bin/env bash
# Run Pdfs by Kash from source (the "dev app"), restarting it if it's already
# running. This never touches the installed /Applications copy.
#
#   scripts/dev.sh
#
# The dev app runs under Python's own preferences domain, so its icon, theme and
# remembered settings are separate from the installed app's.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.build-venv/bin/python"

# Stop a previous dev instance (only ours: matched by this repo's path).
if pgrep -f "$ROOT/native_app.py" >/dev/null; then
  pkill -f "$ROOT/native_app.py" || true
  for _ in {1..20}; do pgrep -f "$ROOT/native_app.py" >/dev/null || break; sleep 0.25; done
fi

nohup "$PY" "$ROOT/native_app.py" >"$ROOT/.dev.log" 2>&1 &
echo "Dev app started (pid $!) — log: .dev.log"
