#!/usr/bin/env bash
# Wraps an exported Hollowmere.pck in Godot's macOS app template and packs it as a .dmg, on Linux.
#
#   tools/export/macos_dmg.sh <dir with Hollowmere.pck, README.txt, THIRD_PARTY.md> <macos.zip> <out.dmg> [label]
#
# The pck is platform-independent (the Linux/Windows export's pack, S3TC/BPTC textures, which Apple
# Silicon and Intel Macs both sample natively), so a Mac build needs no export of its own: the
# universal release template becomes Hollowmere.app with the pck in Contents/Resources (where Godot
# looks for <executable>.pck), the game's icon and a filled-in Info.plist. The bundle is signed
# ad hoc with rcodesign (arm64 refuses unsigned code; a broken seal reads as "damaged"), so macOS
# shows the ordinary unidentified-developer prompt. The image is ISO 9660 + Rock Ridge + Joliet,
# which macOS mounts as a disk image with the exec bits intact (hdiutil isn't available on Linux).
# Needs: genisoimage, unzip, python3 with Pillow (.tools/venv), the pinned Godot (SVG -> PNG),
# rcodesign on PATH or $RCODESIGN.
set -euo pipefail

SRC=$1
TEMPLATE_ZIP=$2
OUT=$3
LABEL=${4:-}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
GODOT=${GODOT:-$ROOT/.tools/godot/godot}
PYTHON=${PYTHON:-$ROOT/.tools/venv/bin/python}
RCODESIGN=${RCODESIGN:-rcodesign}
VERSION=$(sed -n 's/^config\/version="\(.*\)"/\1/p' "$ROOT/game/project.godot")

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
unzip -q "$TEMPLATE_ZIP" -d "$work"
tpl=$work/macos_template.app
root=$work/dmg
app=$root/Hollowmere.app
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"

cp "$tpl/Contents/MacOS/godot_macos_release.universal" "$app/Contents/MacOS/Hollowmere"
chmod 755 "$app/Contents/MacOS/Hollowmere"
cp "$tpl/Contents/PkgInfo" "$app/Contents/"
cp "$tpl/Contents/Resources/PrivacyInfo.xcprivacy" "$app/Contents/Resources/"
cp "$SRC/Hollowmere.pck" "$app/Contents/Resources/Hollowmere.pck"

# The game's icon: Godot renders the SVG (ImageMagick needs a delegate runners lack), Pillow writes the .icns.
cat > "$work/svg2png.gd" <<EOF
extends SceneTree
func _initialize() -> void:
	var img := Image.new()
	if img.load_svg_from_string(FileAccess.get_file_as_string("$ROOT/game/icon.svg"), 8.0) == OK:
		img.save_png("$work/icon.png")
	quit()
EOF
"$GODOT" --headless -s "$work/svg2png.gd" >/dev/null 2>&1 || true
if ! { [ -f "$work/icon.png" ] && "$PYTHON" -c "
from PIL import Image
Image.open('$work/icon.png').convert('RGBA').save('$app/Contents/Resources/icon.icns',
    sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])"; }; then
	echo "[macos] icon render failed, keeping Godot's icon" >&2
	cp "$tpl/Contents/Resources/icon.icns" "$app/Contents/Resources/icon.icns"
fi

VERSION=$VERSION LABEL=$LABEL python3 - "$tpl/Contents/Info.plist" "$app/Contents/Info.plist" <<'EOF'
import os, plistlib, sys
s = open(sys.argv[1]).read()
version = os.environ["VERSION"]
sub = {"$binary": "Hollowmere", "$name": "Hollowmere", "$bundle_identifier": "io.github.leviticusfigglebottom.hollowmere",
       "$short_version": version.split("-")[0], "$version": version, "$signature": "????",
       "$copyright": f"Hollowmere playtest build {os.environ['LABEL']}".strip(), "$app_category": "games",
       "$min_version_arm64": "11.00", "$min_version_x86_64": "10.15", "$highres": "\t<true/>"}
for k in ("$platfbuild", "$sdkver", "$sdkbuild", "$sdkname", "$xcodever", "$xcodebuild",
          "$liquid_glass_icon", "$usage_descriptions", "$additional_plist_content"):
    sub[k] = ""
for k in sorted(sub, key=len, reverse=True):
    s = s.replace(k, sub[k])
if "$" in s:
    raise SystemExit(f"unfilled Info.plist keys: {[l for l in s.splitlines() if '$' in l]}")
plistlib.loads(s.encode())
open(sys.argv[2], "w").write(s)
EOF

"$RCODESIGN" sign "$app" >/dev/null

cat > "$root/READ ME FIRST.txt" <<EOF
HOLLOWMERE $VERSION $LABEL - macOS playtest build

1. Drag Hollowmere.app into Applications (or anywhere).
2. Double-click it. macOS will say it can't verify the developer, because the build isn't
   signed with an Apple Developer ID. Click Done (not Move to Trash).
3. Open System Settings > Privacy & Security, scroll down to "Hollowmere was blocked..." and
   click Open Anyway, then confirm. You only need to do this once.
   (macOS 14 and older: you can instead right-click the app, choose Open, then Open.)

If macOS says the app "is damaged", open Terminal and run:
    xattr -dr com.apple.quarantine /Applications/Hollowmere.app
then open it again.

Needs macOS 11 or newer, Apple Silicon (M1 and later) or Intel. It runs best on M-series Macs;
Intel Macs with integrated graphics will struggle.

Saves, settings and logs: ~/Library/Application Support/hollowmere/
If it crashes, please send logs/godot.log from that folder.

EOF
# The controls, as the Windows/Linux README lists them.
if [ -f "$SRC/README.txt" ]; then
	sed -n '/^Controls/,/^Saves/p' "$SRC/README.txt" | sed '$d' >> "$root/READ ME FIRST.txt"
fi
[ -f "$SRC/THIRD_PARTY.md" ] && cp "$SRC/THIRD_PARTY.md" "$root/"
ln -s /Applications "$root/Applications"

mkdir -p "$(dirname "$OUT")"
genisoimage -quiet -V Hollowmere -R -J -joliet-long -no-pad -o "$OUT" "$root"
echo "[macos] $OUT ($(du -h "$OUT" | cut -f1))"
