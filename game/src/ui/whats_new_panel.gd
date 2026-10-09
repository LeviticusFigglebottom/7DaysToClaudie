class_name WhatsNewPanel
extends PanelContainer
## The main menu's What's new (data/config/whats_new.json): the newest entry's short lines, in the
## kit theme. It opens by itself once per entry (Settings.whats_new_seen holds the last one closed)
## and from the menu's What's New any time. Gamepad-ready: Close takes focus, B closes.

signal closed()

var entry: Dictionary = {}


## The entries, newest first ([] when the file has none).
static func entries() -> Array:
	var cfg: Dictionary = Content.config(&"whats_new") if Content != null else {}
	return cfg.get("entries", []) as Array


## The newest entry ({} when there is none).
static func newest() -> Dictionary:
	var all: Array = entries()
	return all[0] as Dictionary if not all.is_empty() and all[0] is Dictionary else {}


## Whether the menu should open it by itself: a newest entry the player hasn't closed yet. Pure.
static func should_show(newest_id: String, seen_id: String) -> bool:
	return newest_id != "" and newest_id != seen_id


func _ready() -> void:
	theme = UiStyle.kit_theme()
	custom_minimum_size = Vector2(760, 600)
	if entry.is_empty():
		entry = newest()
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 10)
	add_child(v)
	v.add_child(UiStyle.label(str(entry.get("title", "What's new")).to_upper(), &"HeadingLabel"))
	if str(entry.get("date", "")) != "":
		v.add_child(UiStyle.label(str(entry["date"]), &"DimLabel"))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	v.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override(&"separation", 8)
	scroll.add_child(list)
	for it: Variant in entry.get("items", []):
		if not (it is Dictionary):
			continue
		var row := VBoxContainer.new()
		row.add_theme_constant_override(&"separation", 1)
		var head := UiStyle.label(str((it as Dictionary).get("head", "")), &"SubheadingLabel")
		head.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
		row.add_child(head)
		var body := UiStyle.label(str((it as Dictionary).get("text", "")))
		body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.add_child(body)
		list.add_child(row)
	var close := Button.new()
	close.text = "Close"
	close.theme_type_variation = &"PrimaryButton"
	close.custom_minimum_size = Vector2(0, 44)
	close.pressed.connect(_close)
	v.add_child(close)
	close.grab_focus.call_deferred()


func _close() -> void:
	var id: String = str(entry.get("id", ""))
	if id != "" and Settings.whats_new_seen != id:
		Settings.whats_new_seen = id
		Settings.save()
	closed.emit()


func _unhandled_input(event: InputEvent) -> void:
	var jb := event as InputEventJoypadButton
	if event.is_action_pressed(&"ui_cancel") or event.is_action_pressed(&"cancel") or (jb != null and jb.pressed and jb.button_index == JOY_BUTTON_B):
		get_viewport().set_input_as_handled()
		_close()
