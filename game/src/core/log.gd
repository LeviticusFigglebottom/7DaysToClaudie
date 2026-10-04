@tool
extends Node
## Categorized logging (autoload `Log`).
##
## Usage: `Log.info(&"terrain", "chunk %s built" % key)`.
## Keeps a ring buffer for the in-game console/debug overlay and mirrors to stdout.
## Errors also go through push_error so they show up in the editor debugger and fail tests.

enum Level { DEBUG, INFO, WARN, ERROR }

const LEVEL_NAMES: PackedStringArray = ["DEBUG", "INFO", "WARN", "ERROR"]
const RING_SIZE: int = 512

signal line_logged(level: int, category: StringName, message: String)

var min_level: int = Level.INFO
## Per-category overrides, e.g. {&"ai": Level.DEBUG}.
var category_levels: Dictionary = {}
var _ring: Array[String] = []


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if OS.is_debug_build():
		min_level = Level.INFO
	var env_level: String = OS.get_environment("HOLLOWMERE_LOG_LEVEL").to_upper()
	var idx: int = LEVEL_NAMES.find(env_level)
	if idx >= 0:
		min_level = idx


func debug(category: StringName, message: String) -> void:
	_log(Level.DEBUG, category, message)


func info(category: StringName, message: String) -> void:
	_log(Level.INFO, category, message)


func warn(category: StringName, message: String) -> void:
	_log(Level.WARN, category, message)


func error(category: StringName, message: String) -> void:
	_log(Level.ERROR, category, message)


func recent_lines() -> Array[String]:
	return _ring.duplicate()


func _log(level: int, category: StringName, message: String) -> void:
	var threshold: int = category_levels.get(category, min_level)
	if level < threshold:
		return
	var line: String = "[%s][%s] %s" % [LEVEL_NAMES[level], category, message]
	_ring.append(line)
	if _ring.size() > RING_SIZE:
		_ring.pop_front()
	match level:
		Level.ERROR:
			push_error(line)
			printerr(line)
		Level.WARN:
			push_warning(line)
			print(line)
		_:
			print(line)
	line_logged.emit(level, category, message)
