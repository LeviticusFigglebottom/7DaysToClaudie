class_name StreamMeter
extends RefCounted
## Measures streaming in play (ADR-0038 §8, RWG_V2_PLAN Phase 3): what the RegionStreamer's
## StepRunner spends, by step kind, and what the player feels.
##
## * Steps are grouped by kind, the step name without its id ("poi plan merrow_house" -> "poi
##   plan", "attach 3_4_pines" -> "attach"): count, total and max ms, and the name of the worst.
## * Frames: the longest wall time between two frames (rendering and stalls count) and the step
##   kinds that ran in it, so a long frame is pinned on the work that caused it.
## * Late seconds: play time spent with a focus point (a player) on ground that wasn't attached
##   yet, the player outrunning the stream.
##
## Every WINDOW_S seconds of play it logs one line (Log "stream") and starts a new window; a
## whole-session tally is kept beside it for tools (stream_walk). Main thread only: the streamer
## feeds it from _process and from StepRunner.step_ran.

## Seconds of play per logged window.
const WINDOW_S: float = 60.0
## A frame adds at most this much to late seconds: a stall doesn't move the player further (the
## physics step count is capped) and must not read as minutes of outrunning.
const MAX_LATE_STEP: float = 0.1
## The per-step budget in play (RWG_V2_PLAN §7.2): over_budget's default.
const STEP_BUDGET_MS: float = 8.0

var window_s: float = WINDOW_S
## Whether a closed window is logged (tests turn it off).
var log_windows: bool = true
## The last closed window's report (empty before the first).
var last_window: Dictionary = {}

var _win: Dictionary = _new_tally()
var _all: Dictionary = _new_tally()
var _last_us: int = -1
## Step kinds run since the last frame() (the frame being measured) -> ms.
var _frame_kinds: Dictionary = {}


## The kind of a step name: the name without its last word (the id), or the name itself when it
## is one word.
static func kind_of(step_name: String) -> String:
	var i: int = step_name.rfind(" ")
	return step_name.substr(0, i) if i > 0 else step_name


## One step ran (StepRunner.step_ran): `usec` of main-thread time. A step that waits on a worker
## (finished false) still costs its call, and counts.
func step(step_name: String, usec: int, finished: bool = true) -> void:
	var ms: float = float(usec) / 1000.0
	var kind: String = kind_of(step_name)
	for t: Dictionary in [_win, _all]:
		var kinds: Dictionary = t["kinds"]
		var k: Dictionary = kinds.get(kind, {})
		if k.is_empty():
			k = {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "max_name": "", "waits": 0}
			kinds[kind] = k
		k["count"] = int(k["count"]) + 1
		k["total_ms"] = float(k["total_ms"]) + ms
		if not finished:
			k["waits"] = int(k["waits"]) + 1
		if ms > float(k["max_ms"]):
			k["max_ms"] = ms
			k["max_name"] = step_name
		t["steps"] = int(t["steps"]) + 1
		t["step_ms"] = float(t["step_ms"]) + ms
	_frame_kinds[kind] = float(_frame_kinds.get(kind, 0.0)) + ms


## Call once a frame, before the frame's steps run: closes the frame before it (whose steps were
## reported since the last call). `delta` is the frame's play time, `late` whether a focus point
## stands on ground not attached yet. `wall_ms` overrides the measured wall time (tests). Returns
## true when this call closed (and logged) a window.
func frame(delta: float, late: bool = false, wall_ms: float = -1.0) -> bool:
	var now: int = Time.get_ticks_usec()
	var ms: float = wall_ms
	if ms < 0.0:
		ms = float(now - _last_us) / 1000.0 if _last_us >= 0 else 0.0
	_last_us = now
	var at: String = _describe_frame()
	_frame_kinds.clear()
	for t: Dictionary in [_win, _all]:
		t["frames"] = int(t["frames"]) + 1
		t["seconds"] = float(t["seconds"]) + delta
		if late:
			t["late_s"] = float(t["late_s"]) + minf(delta, MAX_LATE_STEP)
		if ms > float(t["longest_ms"]):
			t["longest_ms"] = ms
			t["longest_at"] = at
	if float(_win["seconds"]) >= window_s:
		last_window = report()
		if log_windows:
			Log.info("stream", summary())
		_win = _new_tally()
		return true
	return false


## The current window ({} parts below), or the whole session with `all`:
## {seconds, frames, longest_ms, longest_at, late_s, steps, step_ms,
##  kinds: {kind: {count, total_ms, max_ms, max_name, waits}}}
func report(all: bool = false) -> Dictionary:
	return (_all if all else _win).duplicate(true)


## Kinds whose slowest step took more than `step_ms`, worst first.
func over_budget(step_ms: float = STEP_BUDGET_MS, all: bool = false) -> PackedStringArray:
	var kinds: Dictionary = (_all if all else _win)["kinds"]
	var out: Array = []
	for kind: String in kinds:
		if float(kinds[kind]["max_ms"]) > step_ms:
			out.append(kind)
	out.sort_custom(func(a: String, b: String) -> bool: return float(kinds[a]["max_ms"]) > float(kinds[b]["max_ms"]))
	return PackedStringArray(out)


## The kind with the slowest single step: [kind, max_ms], or ["", 0.0] when no step ran.
func worst_kind(all: bool = false) -> Array:
	var kinds: Dictionary = (_all if all else _win)["kinds"]
	var best: String = ""
	for kind: String in kinds:
		if best == "" or float(kinds[kind]["max_ms"]) > float(kinds[best]["max_ms"]):
			best = kind
	return [best, float(kinds[best]["max_ms"]) if best != "" else 0.0]


## One compact line: the window's (or the session's) frames, late seconds and the costliest
## kinds, e.g. "60 s, 3412 frames, longest 212 ms (poi), late 0.0 s; 85 steps 610 ms;
## poi 12x max 48/total 210 ms, attach 2x 41/80 ms; over 8 ms: poi, attach".
func summary(all: bool = false) -> String:
	var t: Dictionary = _all if all else _win
	var kinds: Dictionary = t["kinds"]
	var names: Array = kinds.keys()
	names.sort_custom(func(a: String, b: String) -> bool: return float(kinds[a]["total_ms"]) > float(kinds[b]["total_ms"]))
	var parts: PackedStringArray = []
	for kind: String in names:
		var k: Dictionary = kinds[kind]
		parts.append("%s %dx max %.1f/total %.0f ms" % [kind, int(k["count"]), float(k["max_ms"]), float(k["total_ms"])])
	var over: PackedStringArray = over_budget(STEP_BUDGET_MS, all)
	return "%.0f s, %d frames, longest %.0f ms (%s), late %.1f s; %d steps %.0f ms%s%s" % [
		float(t["seconds"]), int(t["frames"]), float(t["longest_ms"]), t["longest_at"] if str(t["longest_at"]) != "" else "no steps",
		float(t["late_s"]), int(t["steps"]), float(t["step_ms"]),
		("; " + ", ".join(parts)) if not parts.is_empty() else "",
		("; over %.0f ms: %s" % [STEP_BUDGET_MS, ", ".join(over)]) if not over.is_empty() else ""]


## The kinds run in the frame being closed, costliest first ("poi 31 ms + attach 4 ms").
func _describe_frame() -> String:
	if _frame_kinds.is_empty():
		return ""
	var names: Array = _frame_kinds.keys()
	names.sort_custom(func(a: String, b: String) -> bool: return float(_frame_kinds[a]) > float(_frame_kinds[b]))
	var parts: PackedStringArray = []
	for kind: String in names.slice(0, 3):
		parts.append("%s %.0f ms" % [kind, float(_frame_kinds[kind])])
	return " + ".join(parts)


## The meter of the running streamed world (null otherwise), for note().
static var current: StreamMeter = null


## A system's per-frame work outside the steps (vegetation, terrain installs, AI...), noted by name
## so a long frame says what filled it: "~veg 210 ms". Costs nothing without a streamed world.
static func note(name: String, t0_usec: int) -> void:
	if current == null:
		return
	var ms: float = float(Time.get_ticks_usec() - t0_usec) / 1000.0
	if ms >= 2.0:
		current._frame_kinds["~" + name] = float(current._frame_kinds.get("~" + name, 0.0)) + ms


static func _new_tally() -> Dictionary:
	return {"seconds": 0.0, "frames": 0, "longest_ms": 0.0, "longest_at": "", "late_s": 0.0, "steps": 0, "step_ms": 0.0, "kinds": {}}
