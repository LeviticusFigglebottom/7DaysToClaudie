#!/usr/bin/env bash
# Installs the pinned Godot editor binary into .tools/godot/ and verifies its checksum.
# Usage: tools/setup/install_godot.sh            (idempotent)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/tools/versions.env"
DEST="$ROOT/.tools/godot"
mkdir -p "$DEST"
if [[ -x "$DEST/$GODOT_BIN" ]] && "$DEST/$GODOT_BIN" --headless --version 2>/dev/null | grep -q "^$GODOT_VERSION.$GODOT_FLAVOR"; then
  echo "[godot] $GODOT_VERSION-$GODOT_FLAVOR already installed at $DEST"
  exit 0
fi
ZIP="$DEST/$GODOT_ZIP"
if [[ ! -f "$ZIP" ]]; then
  echo "[godot] downloading $GODOT_VERSION-$GODOT_FLAVOR ..."
  curl -fsSL --retry 4 --retry-delay 2 -o "$ZIP.part" "$GODOT_URL"
  mv "$ZIP.part" "$ZIP"
fi
echo "$GODOT_SHA512  $ZIP" | sha512sum -c - >/dev/null || { echo "[godot] CHECKSUM MISMATCH for $ZIP" >&2; rm -f "$ZIP"; exit 1; }
(cd "$DEST" && unzip -q -o "$GODOT_ZIP")
chmod +x "$DEST/$GODOT_BIN"
ln -sf "$GODOT_BIN" "$DEST/godot"
"$DEST/godot" --headless --version
echo "[godot] installed: $DEST/godot"
