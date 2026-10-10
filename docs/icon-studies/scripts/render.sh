#!/usr/bin/env bash
# Render every concept SVG to PNG at the macOS icon sizes, and build out/sheet.png.
# Needs rsvg-convert (brew install librsvg) and Python 3 with Pillow for the contact sheet.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$here/png"
for svg in "$here"/concepts/*.svg; do
  name="$(basename "$svg" .svg)"
  for size in 1024 256 128 64 32 16; do
    rsvg-convert -w "$size" -h "$size" "$svg" -o "$here/png/$name-$size.png"
  done
  echo "rendered $name"
done
python3 "$here/scripts/sheet.py"
