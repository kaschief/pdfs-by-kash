#!/usr/bin/env bash
# Build, verify and install Pdfs by Kash into /Applications, then reopen it.
# Run only when the owner asks for a rebuild/install.
#
#   scripts/install_local_mac.sh
#
# 1. Runs the test suite (stops on failure).
# 2. Builds the signed app into release-test/ and verifies the signature.
# 3. Quits the installed app if it's open (politely; if a batch is still
#    compressing the app refuses to quit, and this script stops).
# 4. Replaces /Applications/Pdfs by Kash.app and reopens it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.build-venv/bin/python"
APP_NAME="Pdfs by Kash"
BUNDLE_ID="com.kaschief.pdfsbykash"
BUILT="$ROOT/release-test/$APP_NAME.app"
INSTALLED="/Applications/$APP_NAME.app"
GS_SOURCE="${MACOS_GHOSTSCRIPT_SOURCE_APP:-/Applications/FS PDF Compressor.app}"

cd "$ROOT"
echo "→ Tests"
"$PY" -m unittest discover -s tests >/dev/null 2>&1 || { echo "Tests failed — not installing."; "$PY" -m unittest discover -s tests 2>&1 | tail -20; exit 1; }

echo "→ Build"
if [[ -d "$GS_SOURCE" ]]; then export MACOS_GHOSTSCRIPT_SOURCE_APP="$GS_SOURCE"; fi
DIST_DIR=release-test "$PY" build_macos.py >"$ROOT/.build.log" 2>&1 || { echo "Build failed — see .build.log"; tail -20 "$ROOT/.build.log"; exit 1; }
codesign --verify --deep --strict "$BUILT"

running() { pgrep -f "$INSTALLED/Contents/MacOS/" >/dev/null; }
if running; then
  echo "→ Quitting the installed app"
  osascript -e "tell application id \"$BUNDLE_ID\" to quit" >/dev/null 2>&1 || true
  for _ in {1..40}; do running || break; sleep 0.25; done
  if running; then
    echo "The installed app is still open (a batch may be compressing). Finish or quit it, then run this again."
    exit 1
  fi
fi

echo "→ Install"
rm -rf "$INSTALLED"
ditto "$BUILT" "$INSTALLED"
codesign --verify --deep --strict "$INSTALLED"
open "$INSTALLED"
echo "Installed and reopened: $INSTALLED"
