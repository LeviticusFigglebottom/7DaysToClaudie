class_name LoadMeter
extends RefCounted
## Measures the main thread while a world loads (ADR-0036): the longest frame (wall time between
## two _process calls, so rendering and stalls count) and what the loading screen said then, plus
## each boot step's own cost. The report goes to the log when the player spawns, and the meter
## keeps watching a few frames after that, because the first frames of the world draw new shaders.

## Frames still measured after the spawn.
const TRAILING_FRAMES: int = 30
## Frames longer than this are logged one by one, with the pipelines compiled in them.
const SLOW_FRAME_MS: float = 250.0
## RenderingServer pipeline compilation counters (Godot 4.4+): [info id, short name]. "draw" ones
## stall the frame that needs them; the others compile ahead or in the background.
const PIPELINES: Array = [[7, "mesh"], [8, "surface"], [9, "draw"], [10, "specialization"]]

var longest_ms: float = 0.0
var longest_at: String = ""
var frames: int = 0
var steps: Array[Dictionary] = []
var _last_us: int = -1
var _last_label: String = ""
var _trailing: int = -1
var _t0_us: int = Time.get_ticks_usec()
var _pipes: PackedInt64Array = []
## Pipelines compiled while the load was measured, by kind.
var pipelines: Dictionary = {}


## Call once per frame; `label` is what the loading screen shows.
func frame(label: String) -> void:
	var now: int = Time.get_ticks_usec()
	if _last_us >= 0:
		var ms: float = float(now - _last_us) / 1000.0
		frames += 1
		# The frame that just ended ran under the label shown when it began.
		if ms > longest_ms:
			longest_ms = ms
			longest_at = _last_label
		var compiled: String = _pipeline_delta()
		if ms > SLOW_FRAME_MS:
			# The steps it ran, so a frame whose label names the next step still says what it was.
			var ran: String = ", ".join(_frame_steps.map(func(s: Array) -> String: return "%s %.0f" % [s[0], s[1]])) if not _frame_steps.is_empty() else "no steps"
			Log.info("load", "slow frame %.0f ms (%s; ran: %s; process %.0f, physics %.0f)%s" % [ms, _last_label if _last_label != "" else "in the world", ran,
				Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, compiled])
	else:
		_pipeline_delta()
	_last_us = now
	_last_label = label
	_frame_steps.clear()
	if _trailing > 0:
		_trailing -= 1
		if _trailing == 0:
			Log.info("load", "first %d frames in the world: longest frame %.0f ms" % [TRAILING_FRAMES, longest_ms])


## Pipelines compiled since the last call, as " (draw 12, surface 40)"; "" when none or headless.
func _pipeline_delta() -> String:
	var parts: PackedStringArray = []
	var fresh: bool = _pipes.is_empty()
	if fresh:
		_pipes.resize(PIPELINES.size())
	for i: int in PIPELINES.size():
		var n: int = RenderingServer.get_rendering_info(int(PIPELINES[i][0]) as RenderingServer.RenderingInfo)
		var d: int = n - _pipes[i]
		_pipes[i] = n
		if not fresh and d > 0:
			parts.append("%s %d" % [PIPELINES[i][1], d])
			pipelines[PIPELINES[i][1]] = int(pipelines.get(PIPELINES[i][1], 0)) + d
	return "" if parts.is_empty() else " (pipelines: %s)" % ", ".join(parts)


func step(label: String, usec: int) -> void:
	steps.append({"label": label, "ms": float(usec) / 1000.0})
	_frame_steps.append([label, float(usec) / 1000.0])


## [label, ms] of the steps run since the last frame() (the slow-frame log names them).
var _frame_steps: Array = []


## True while the frames right after the spawn are still being measured.
func trailing() -> bool:
	return _trailing > 0


## Logs the load's report and starts the trailing window.
func spawned() -> void:
	var worst: Array[Dictionary] = steps.duplicate()
	worst.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["ms"]) > float(b["ms"]))
	var parts: PackedStringArray = []
	for s: Dictionary in worst.slice(0, 4):
		parts.append("%s %.0f ms" % [s["label"], s["ms"]])
	Log.info("load", "world ready in %.1f s over %d frames; longest frame %.0f ms (%s); slowest steps: %s; pipelines compiled: %s" % [
		float(Time.get_ticks_usec() - _t0_us) / 1e6, frames, longest_ms, longest_at, ", ".join(parts), pipelines])
	longest_ms = 0.0
	longest_at = "in the world"
	_trailing = TRAILING_FRAMES
