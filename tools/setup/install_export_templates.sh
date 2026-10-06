#!/usr/bin/env bash
# Installs the pinned Godot export templates (only the Windows and Linux x86_64 ones `make export`
# uses) into .tools/xdg/godot/export_templates/<version>.<flavor>/ and verifies the archive.
# Godot finds them there when run with XDG_DATA_HOME=.tools/xdg (the Makefile's export target).
# Usage: tools/setup/install_export_templates.sh            (idempotent)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/tools/versions.env"
DL="$ROOT/.tools/downloads"
DEST="$ROOT/.tools/xdg/godot/export_templates/$GODOT_VERSION.$GODOT_FLAVOR"
WANT=(windows_release_x86_64.exe windows_release_x86_64_console.exe windows_debug_x86_64.exe
  windows_debug_x86_64_console.exe linux_release.x86_64 linux_debug.x86_64)
have_all() { for f in "${WANT[@]}"; do [[ -f "$DEST/$f" ]] || return 1; done; }
if have_all && [[ "$(cat "$DEST/version.txt" 2>/dev/null)" == "$GODOT_VERSION.$GODOT_FLAVOR" ]]; then
  echo "[templates] $GODOT_VERSION-$GODOT_FLAVOR already installed at $DEST"
  exit 0
fi
mkdir -p "$DL" "$DEST"
TPZ="$DL/$GODOT_TEMPLATES_TPZ"
if [[ ! -f "$TPZ" ]]; then
  echo "[templates] downloading $GODOT_VERSION-$GODOT_FLAVOR (~1.3 GB) ..."
  curl -fsSL --retry 4 --retry-delay 2 -o "$TPZ.part" "$GODOT_TEMPLATES_URL"
  mv "$TPZ.part" "$TPZ"
fi
echo "$GODOT_TEMPLATES_SHA512  $TPZ" | sha512sum -c - >/dev/null || { echo "[templates] CHECKSUM MISMATCH for $TPZ" >&2; rm -f "$TPZ"; exit 1; }
# The archive holds templates/<file>; take only what the presets need (the full set is ~1.3 GB).
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
unzip -q -o "$TPZ" "templates/version.txt" $(printf 'templates/%s ' "${WANT[@]}") -d "$TMP"
cp "$TMP"/templates/* "$DEST/"
chmod +x "$DEST"/linux_* || true
# The archive is only needed again for a version bump.
rm -f "$TPZ"
echo "[templates] installed: $DEST ($(cat "$DEST/version.txt"))"
