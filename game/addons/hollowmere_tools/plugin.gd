@tool
extends EditorPlugin
## Editor integration for project tools. Heavy lifting lives in res://src/tools so the same code
## runs headless from the CLI (make validate) and in the editor dock.

var _dock: Control


func _enter_tree() -> void:
	var dock_script: Script = load("res://addons/hollowmere_tools/validator_dock.gd")
	if dock_script != null:
		_dock = dock_script.new()
		_dock.name = "Hollowmere"
		add_control_to_dock(DOCK_SLOT_RIGHT_UL, _dock)


func _exit_tree() -> void:
	if _dock != null:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
