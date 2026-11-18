#!/bin/bash
# Convierte a PNG los diagramas SVG de una carpeta, con Microsoft Edge sin ventana.
# Uso: bash tools/er-diagram/to-png.sh docs/database/img
set -e
cd "${1:-.}"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
AQUI="$(pwd -W)"
for f in chen-*.svg; do
  n="${f%.svg}"
  w=$(grep -o '<svg width="[0-9]*pt"' "$f" | grep -o '[0-9]*' | head -1)
  h=$(grep -o 'height="[0-9]*pt"' "$f" | grep -o '[0-9]*' | head -1)
  printf '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#fff}img{display:block}</style></head><body><img src="%s.svg" width="%s" height="%s"></body></html>' "$n" "$(( w * 4 / 3 ))" "$(( h * 4 / 3 ))" > "$n.tmp.html"
  "$EDGE" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=8000 --window-size=$(( w * 4 / 3 + 8 )),$(( h * 4 / 3 + 8 )) --screenshot="$AQUI/$n.png" "file:///$AQUI/$n.tmp.html" >/dev/null 2>&1
  rm -f "$n.tmp.html"
  echo "$n.png"
done
