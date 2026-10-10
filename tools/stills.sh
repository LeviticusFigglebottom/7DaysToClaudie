#!/usr/bin/env bash
# Renders the pre-rendered backdrops (ADR-0065) into game/assets/generated/stills/:
#   menu_0.png .. menu_4.png   the main menu's valley: dusk, a misty dawn, a storm (MenuBackdrop pans across them)
#   intro_wreck.png            the intro's world card: the Lift 3 wreck at first light
# The game draws them (src/tools/cli/stills.gd; software Vulkan under Xvfb is fine, about a minute
# a picture) and this writes their import sidecars (lossy, mipmapped). A shot is skipped while its
# stamp (a hash of everything it is drawn from) matches; STILLS_FORCE=1 redraws.
#   tools/stills.sh [menu] [wreck]      (default: both)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-$ROOT/.tools/godot/godot}"
GAME="$ROOT/game"
OUT="$GAME/assets/generated/stills"
WORK="$ROOT/build/stills"
SHOTS=("$@")
[ ${#SHOTS[@]} -eq 0 ] && SHOTS=(menu wreck)
mkdir -p "$OUT" "$WORK" "$ROOT/build"

# The generated assets a shot is drawn with: trees, terrain and sky textures for the menu; every
# model and texture for the wreck (it loads the main map). Their manifest entries carry hashes.
manifest_part() {
  python3 - "$GAME/assets/generated/manifest.json" "$1" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    data = {}
tasks = data.get("tasks", data) if isinstance(data, dict) else {}
keys = sorted(tasks)
if sys.argv[2] == "menu":
    keys = [k for k in keys if any(w in k for w in ("tree", "fir", "larch", "birch", "terrain", "sky", "water", "ground"))]
print(json.dumps({k: (tasks[k] or {}).get("hash") for k in keys}, sort_keys=True))
PY
}

stamp() {
  local shot="$1"
  {
    echo "stills v1 $shot"
    cat "$GAME/src/tools/cli/stills_runner.gd" "$ROOT/tools/stills.sh"
    manifest_part "$shot"
    find "$GAME/assets/shaders" -type f -name '*.gdshader*' | sort | xargs cat
    if [ "$shot" = menu ]; then
      cat "$GAME/src/tools/stills/menu_flight.gd" "$GAME/world/main_map/world.json"
      find "$GAME/world/main_map/regions/d6_larch_hollow" -type f | sort | xargs cat
      git -C "$ROOT" ls-files -s -- game/src/worldgen game/src/world | sha256sum
    else
      cat "$GAME/src/ui/intro/intro_player.gd" "$GAME/data/intro/intro.json"
      git -C "$ROOT" ls-files -s -- game/src game/data game/world | grep -v -e 'game/src/ui/' -e 'game/src/tools/' | sha256sum
    fi
  } | sha256sum | cut -d' ' -f1
}

# Lossy (the pictures are photographs), mipmapped (they are shown smaller than drawn), no 3D use.
sidecar() {
  printf '[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\ncompress/mode=1\ncompress/lossy_quality=0.9\nmipmaps/generate=true\nprocess/size_limit=0\ndetect_3d/compress_to=0\n' > "$1.import"
}

for shot in "${SHOTS[@]}"; do
  case "$shot" in
    menu) first="menu_0.png" ;;
    wreck) first="intro_wreck.png" ;;
    *) echo "stills: unknown shot $shot" >&2; exit 2 ;;
  esac
  want="$(stamp "$shot")"
  if [ -z "${STILLS_FORCE:-}" ] && [ -f "$OUT/$first" ] && [ "$(cat "$OUT/$shot.stamp" 2>/dev/null)" = "$want" ]; then
    echo "stills: $shot is current"
    continue
  fi
  rm -rf "$WORK/$shot"
  mkdir -p "$WORK/$shot"
  echo "stills: drawing $shot"
  # The exit watchdog: after a loaded world, engine shutdown sometimes never returns (it held CI's
  # build for 1 h 40 min once the wreck was saved); the done line is what counts.
  flock "$ROOT/build/.godot.lock" timeout -k 30 3600 "$ROOT/tools/qa_watchdog.sh" "^STILLS $shot done" \
    xvfb-run -a -s "-screen 0 1920x1080x24" "$GODOT" --path "$GAME" \
    --rendering-driver vulkan --audio-driver Dummy -s res://src/tools/cli/stills.gd -- --shot "$shot" --out "$WORK/$shot" \
    > "$ROOT/build/stills_$shot.log" 2>&1 || { tail -40 "$ROOT/build/stills_$shot.log"; echo "stills: $shot failed" >&2; exit 1; }
  grep "^STILLS" "$ROOT/build/stills_$shot.log" || true
  [ -f "$WORK/$shot/$first" ] || { echo "stills: $shot drew nothing" >&2; exit 1; }
  for f in "$WORK/$shot"/*.png; do
    mv "$f" "$OUT/"
    sidecar "$OUT/$(basename "$f")"
  done
  echo "$want" > "$OUT/$shot.stamp"
done
