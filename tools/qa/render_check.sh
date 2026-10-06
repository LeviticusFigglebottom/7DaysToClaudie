#!/usr/bin/env bash
# render_check.sh [shots]   (ADR-0036)
# Renders a few screenshot-suite views (software Vulkan under Xvfb is enough: renderer limits are
# the same on every GPU) and fails on engine errors that only a rendered run shows. The first
# playtest crashed on a reflection probe atlas overflow (more than 64 probes in view on Pell's
# Crossing's street): headless runs never render, so nothing caught it.
# Env: GODOT, LOCK (as in the Makefile), RENDER_CHECK_SETTLE (seconds a view settles, default 4).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GODOT="${GODOT:-$ROOT/.tools/godot/godot}"
LOCK="${LOCK:-}"
shots="${1:-pell_crossing_street,larch_street}"
out="$ROOT/build/render_check"
log="$out/render_check.log"
mkdir -p "$out"
# Engine lines that mean a broken frame or a crash. "Condition ... is true" from the renderer
# follows the probe overflow, so the named messages are enough.
bad='Reflection probe atlas index invalid|FATAL|CrashHandlerException|Program crashed with signal|Maximum amount of reflection probes'
$LOCK "$ROOT/tools/qa_watchdog.sh" "SHOT done" xvfb-run -a -s "-screen 0 1920x1080x24" \
	"$GODOT" --path "$ROOT/game" --rendering-driver vulkan --audio-driver Dummy --resolution 1280x720 \
	-s res://src/tools/cli/screenshots.gd -- --out "$out" --only "$shots" --settle "${RENDER_CHECK_SETTLE:-4}" > "$log" 2>&1
rc=$?
if grep -nE "$bad" "$log"; then
	echo "[render_check] FAIL: renderer errors above (log: $log)" >&2
	exit 1
fi
if ! grep -q "SHOT done" "$log"; then
	tail -30 "$log"
	echo "[render_check] FAIL: the run ended before its shots were done (exit $rc, log: $log)" >&2
	exit 1
fi
echo "[render_check] ok: $shots rendered with no renderer errors"
