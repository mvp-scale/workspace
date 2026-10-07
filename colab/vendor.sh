#!/bin/bash
# Refresh colab/vendor from the main repo. vendor/ is a copy of the layout the install and serve scripts expect, so the same
# code runs here and on Colab. Run from anywhere after changing an adapter, server wrapper or setup script.
set -euo pipefail
SRC=${1:-/workspace}; DST="$(cd "$(dirname "$0")" && pwd)/vendor"
rm -rf "$DST"; mkdir -p "$DST/demo" "$DST/jevbench"
cp "$SRC/dev-bench-setup.sh" "$DST/"
cp "$SRC/demo/serve_inproc.py" "$SRC/demo/serve_kev.py" "$DST/demo/"
(cd "$SRC/jevbench" && find jevbench -name '*.py' -not -path '*/__pycache__/*' | tar -cf - -T - ) | tar -xf - -C "$DST/jevbench"
echo "vendored $(find "$DST" -type f | wc -l) files, $(du -sh "$DST" | cut -f1) -> $DST (from $SRC, $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo no-git))"
