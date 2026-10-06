class_name LoadMeter
extends RefCounted
## Measures the main thread while a world loads (ADR-0036): the longest frame (wall time between
## two _process calls, so rendering and stalls count) and what the loading screen said then, plus
## each boot step's own cost. The report goes to the log when the player spawns, and the meter
## keeps watching a few frames after that, because the first frames of the world draw new shaders.

## Frames still measured after the spawn.
const TRAILING_FRAMES: int = 30

var longest_ms: float = 0.0
var longest_at: String = ""
var frames: int = 0
var steps: Array[Dictionary] = []
var _last_us: int = -1
var _last_label: String = ""
var _trailing: int = -1
var _t0_us: int = Time.get_ticks_usec()


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
	_last_us = now
	_last_label = label
	if _trailing > 0:
		_trailing -= 1
		if _trailing == 0:
			Log.info("load", "first %d frames in the world: longest frame %.0f ms" % [TRAILING_FRAMES, longest_ms])


func step(label: String, usec: int) -> void:
	steps.append({"label": label, "ms": float(usec) / 1000.0})


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
	Log.info("load", "world ready in %.1f s over %d frames; longest frame %.0f ms (%s); slowest steps: %s" % [
		float(Time.get_ticks_usec() - _t0_us) / 1e6, frames, longest_ms, longest_at, ", ".join(parts)])
	longest_ms = 0.0
	longest_at = "in the world"
	_trailing = TRAILING_FRAMES
