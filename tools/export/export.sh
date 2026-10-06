#!/usr/bin/env bash
# Packages playable builds (ADR-0036): exports the Godot presets in game/export_presets.cfg with the
# pinned templates, then zips each with the player readme and third-party notices into
# build/export/hollowmere-<platform>-<version>.zip.
# Usage: tools/export/export.sh [windows] [linux]      (default: both)
# Env:   GODOT (binary), LOCK (command prefix that serialises Godot runs), EXPORT_STANDIN=1 to allow
#        a build without generated assets (it would ship the procedural stand-ins).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GODOT="${GODOT:-$ROOT/.tools/godot/godot}"
LOCK="${LOCK:-}"
OUT="$ROOT/build/export"
targets=("$@")
[[ ${#targets[@]} -gt 0 ]] || targets=(windows linux)

if [[ ! -d "$ROOT/game/assets/generated/models" && "${EXPORT_STANDIN:-0}" != "1" ]]; then
  echo "[export] game/assets/generated is missing: run 'make assets' first (EXPORT_STANDIN=1 exports the stand-ins)" >&2
  exit 1
fi
"$ROOT/tools/setup/install_export_templates.sh"
version="$(sed -n 's/^config\/version="\(.*\)"/\1/p' "$ROOT/game/project.godot")"
rev="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo local)"
for t in "${targets[@]}"; do
  case "$t" in
    windows) preset="Windows Desktop"; bin="Hollowmere.exe" ;;
    linux) preset="Linux"; bin="Hollowmere.x86_64" ;;
    *) echo "[export] unknown target $t (windows, linux)" >&2; exit 1 ;;
  esac
  dir="$OUT/$t"
  rm -rf "$dir" && mkdir -p "$dir"
  echo "[export] $preset -> $dir/$bin"
  # Templates come from .tools/xdg, never from the user's own Godot data dir.
  XDG_DATA_HOME="$ROOT/.tools/xdg" $LOCK "$GODOT" --headless --path "$ROOT/game" --export-release "$preset" "$dir/$bin" \
    > "$OUT/export_$t.log" 2>&1 || { tail -40 "$OUT/export_$t.log"; echo "[export] $preset failed (log: $OUT/export_$t.log)" >&2; exit 1; }
  [[ -f "$dir/Hollowmere.pck" ]] || { tail -40 "$OUT/export_$t.log"; echo "[export] no .pck written" >&2; exit 1; }
  sed -e "s/@VERSION@/$version ($rev)/" "$ROOT/tools/export/README.txt" > "$dir/README.txt"
  cp "$ROOT/THIRD_PARTY.md" "$dir/"
  zip_name="hollowmere-$t-$version-$rev.zip"
  rm -f "$OUT/$zip_name"
  (cd "$dir" && zip -q -r -9 "$OUT/$zip_name" .)
  echo "[export] $OUT/$zip_name ($(du -h "$OUT/$zip_name" | cut -f1))"
done
