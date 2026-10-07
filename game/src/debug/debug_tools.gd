extends Node
## Debug tools hub (autoload `DebugTools`). Owns toggles shared by overlays and tools.
## The actual overlay/tool nodes live in src/debug/ and are added by GameWorld in debug builds:
##   F1 debug menu (spawn, time, weather, teleport, seed viewer), F2 free cam, F3 AI overlay,
##   F4 performance overlay, F6 POI route visualizer, F7 structural view, F8 forest encounters. See docs/DEBUG_TOOLS.md.

signal toggled(flag: StringName, on: bool)

var flags: Dictionary = {
	&"ai_overlay": false, &"perf_overlay": false, &"poi_routes": false, &"structure_view": false,
	&"encounters": false, &"free_cam": false, &"god_mode": false, &"invisible": false, &"no_hunger": false,
}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func enabled() -> bool:
	return OS.is_debug_build() or OS.has_feature("debug_tools")


func is_on(flag: StringName) -> bool:
	return bool(flags.get(flag, false))


func set_flag(flag: StringName, on: bool) -> void:
	flags[flag] = on
	toggled.emit(flag, on)


func toggle(flag: StringName) -> bool:
	set_flag(flag, not is_on(flag))
	return is_on(flag)
