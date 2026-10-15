#!/usr/bin/env bash
# Renders trailer shots (data/trailer, TrailerShotDef) with Movie Maker at 1920x1080, 30 fps:
#   tools/trailer_shot.sh <id>...      -> build/trailer/shots/<id>/frame########.png + frame.wav
#   tools/trailer_shot.sh --list       the shot ids
#   TRAILER_PREVIEW=1 tools/trailer_shot.sh <id>   first/middle/last frame only -> build/trailer/preview
# Movie Maker records from launch: the runner (src/tools/cli/trailer_runner.gd) shows a magenta
# MARKER frame just before the shot, and this cuts everything up to it from the frames and the WAV.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-$ROOT/.tools/godot/godot}"
GAME="$ROOT/game"
PY="$ROOT/.tools/venv/bin/python"
[ -x "$PY" ] || PY=python3
mkdir -p "$ROOT/build/trailer"

if [ "${1:-}" = "--list" ]; then
  flock "$ROOT/build/.godot.lock" "$GODOT" --headless --path "$GAME" -s res://src/tools/cli/trailer.gd -- --list 2>&1 | grep "^TRAILER shot" | sed 's/^TRAILER shot //'
  exit 0
fi
[ $# -gt 0 ] || { echo "usage: tools/trailer_shot.sh <shot id>... (--list)" >&2; exit 2; }

for shot in "$@"; do
  log="$ROOT/build/trailer/$shot.log"
  if [ -n "${TRAILER_PREVIEW:-}" ]; then
    out="$ROOT/build/trailer/preview"
    mkdir -p "$out"
    flock "$ROOT/build/.godot.lock" timeout -k 30 3600 "$ROOT/tools/qa_watchdog.sh" "^TRAILER $shot (done|FAILED)" \
      xvfb-run -a -s "-screen 0 1920x1080x24" "$GODOT" --path "$GAME" --rendering-driver vulkan --audio-driver Dummy \
      --resolution 1920x1080 --fixed-fps 30 -s res://src/tools/cli/trailer.gd -- --shot "$shot" --preview --out "$out" ${TRAILER_ARGS:-} \
      > "$log" 2>&1 || true
    grep "^TRAILER" "$log" || tail -30 "$log"
    grep -q "^TRAILER $shot done" "$log" || { echo "trailer: $shot failed (see $log)" >&2; exit 1; }
    continue
  fi
  raw="$ROOT/build/trailer/raw/$shot"
  dest="$ROOT/build/trailer/shots/$shot"
  rm -rf "$raw"
  mkdir -p "$raw"
  echo "trailer: rendering $shot (Movie Maker, software Vulkan: slow)"
  # The watchdog ends a run whose engine shutdown hangs after the done line (it would hold the lock);
  # Movie Maker has written every frame by then, and the WAV's sizes are read from the data.
  flock "$ROOT/build/.godot.lock" timeout -k 30 36000 "$ROOT/tools/qa_watchdog.sh" "^TRAILER $shot (done|FAILED)" \
    xvfb-run -a -s "-screen 0 1920x1080x24" "$GODOT" --path "$GAME" --rendering-driver vulkan \
    --resolution 1920x1080 --write-movie "$raw/frame.png" --fixed-fps 30 \
    -s res://src/tools/cli/trailer.gd -- --shot "$shot" > "$log" 2>&1 || true
  grep "^TRAILER" "$log" || tail -30 "$log"
  grep -q "^TRAILER $shot done" "$log" || { echo "trailer: $shot failed (see $log)" >&2; exit 1; }
  frames=$(sed -n "s/^TRAILER recording \([0-9]*\) frames.*/\1/p" "$log" | tail -1)
  "$PY" "$ROOT/tools/trailer_cut.py" "$raw" "$dest" "$frames"
  rm -rf "$raw"
done
