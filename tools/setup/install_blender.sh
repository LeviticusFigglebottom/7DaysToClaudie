#!/usr/bin/env bash
# Installs the pinned Blender into .tools/blender/ and verifies its checksum.
# Usage: tools/setup/install_blender.sh          (idempotent)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/tools/versions.env"
DEST="$ROOT/.tools/blender"
mkdir -p "$DEST"
if [[ -x "$DEST/$BLENDER_DIR/blender" ]]; then
  echo "[blender] $BLENDER_VERSION already installed at $DEST"
  exit 0
fi
TAR="$DEST/$BLENDER_TARBALL"
if [[ ! -f "$TAR" ]]; then
  echo "[blender] downloading $BLENDER_VERSION ..."
  curl -fsSL --retry 4 --retry-delay 2 -o "$TAR.part" "$BLENDER_URL"
  mv "$TAR.part" "$TAR"
fi
echo "$BLENDER_SHA256  $TAR" | sha256sum -c - >/dev/null || { echo "[blender] CHECKSUM MISMATCH for $TAR" >&2; rm -f "$TAR"; exit 1; }
tar -xf "$TAR" -C "$DEST"
rm -f "$TAR"
ln -sf "$BLENDER_DIR/blender" "$DEST/blender"
"$DEST/blender" --version | head -1
echo "[blender] installed: $DEST/blender"
