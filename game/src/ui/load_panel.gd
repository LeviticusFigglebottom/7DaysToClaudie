class_name LoadPanel
extends PanelContainer
## The Load screen: every run as a card, newest first, with the frame it was saved on (a small
## WebP the game writes beside the save), the day and the hour, where it was saved, the play time,
## the difficulty and the world, and Load and Delete (Delete asks twice). Kit theme, gamepad-ready:
## a card's buttons take focus.

signal closed()
signal load_requested(slot: String)

const THUMB_FILE: String = "thumb.webp"
const CARD_FILE: String = "card.json"
const THUMB_SIZE := Vector2i(384, 216)

var slots: Array[Dictionary] = []
var _list: VBoxContainer


func _ready() -> void:
	theme = UiStyle.kit_theme()
	custom_minimum_size = Vector2(1000, 720)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	add_child(v)
	v.add_child(UiStyle.label("LOAD A RUN", &"HeadingLabel"))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	v.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override(&"separation", 10)
	scroll.add_child(_list)
	var back := Button.new()
	back.text = "Back"
	back.custom_minimum_size = Vector2(0, 44)
	back.pressed.connect(func() -> void: closed.emit())
	v.add_child(back)
	_build()


func _build() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	if slots.is_empty():
		_list.add_child(UiStyle.label("No saved runs yet.", &"DimLabel"))
		return
	for s: Dictionary in slots:
		_list.add_child(_card(s))


## The words on a slot's card, from its meta.json and card.json: [title, details, saved]. Pure.
static func card_text(meta: Dictionary, card: Dictionary, now_unix: int) -> PackedStringArray:
	var slot: String = str(meta.get("slot", "?"))
	var hour: float = float(meta.get("hour", 7.5))
	var title: String = "%s  ·  Day %d, %02d:%02d" % [slot.capitalize(), int(meta.get("day", 1)), int(hour), int(fmod(hour, 1.0) * 60.0)]
	var where: String = str(card.get("place", card.get("region", "")))
	var bits: PackedStringArray = []
	if where != "":
		bits.append(where.left(1).to_upper() + where.substr(1))
	var preset: String = str(meta.get("preset", ""))
	if preset != "":
		bits.append(preset.capitalize())
	bits.append("Random world" if str(meta.get("world_mode", "")) == "random" else "Hollowmere Valley")
	if str(meta.get("game_mode", "")) == "slice":
		bits.append("Vertical slice")
	var secs: int = int(meta.get("play_seconds", 0))
	bits.append("played %dh %02dm" % [secs / 3600, (secs % 3600) / 60])
	return PackedStringArray([title, "  ·  ".join(bits), "saved " + ago(now_unix - int(meta.get("saved_unix", now_unix)))])


## "just now", "12 minutes ago", "3 hours ago", "2 days ago".
static func ago(seconds: int) -> String:
	if seconds < 90:
		return "just now"
	if seconds < 5400:
		return "%d minutes ago" % (seconds / 60)
	if seconds < 172800:
		return "%d hours ago" % (seconds / 3600)
	return "%d days ago" % (seconds / 86400)


## A frame cut to the card's 16:9 and shrunk to THUMB_SIZE (centre crop, so any window shape fits).
static func thumbnail(frame: Image) -> Image:
	var img: Image = frame.duplicate() as Image
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGB8)
	var aspect: float = float(THUMB_SIZE.x) / float(THUMB_SIZE.y)
	var w: int = img.get_width()
	var h: int = img.get_height()
	var cw: int = mini(w, roundi(h * aspect))
	var ch: int = mini(h, roundi(cw / aspect))
	img = img.get_region(Rect2i((w - cw) / 2, (h - ch) / 2, cw, ch))
	img.resize(THUMB_SIZE.x, THUMB_SIZE.y, Image.INTERPOLATE_LANCZOS)
	return img


static func read_card(slot: String) -> Dictionary:
	var path: String = SaveSystem.slot_dir(slot).path_join(CARD_FILE)
	if not FileAccess.file_exists(path):
		return {}
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK or not (json.data is Dictionary):
		return {}
	return json.data


static func read_thumb(slot: String) -> Texture2D:
	var path: String = SaveSystem.slot_dir(slot).path_join(THUMB_FILE)
	if not FileAccess.file_exists(path):
		return null
	var img := Image.load_from_file(ProjectSettings.globalize_path(path))
	return ImageTexture.create_from_image(img) if img != null and not img.is_empty() else null


func _card(meta: Dictionary) -> Control:
	var slot: String = str(meta.get("slot", ""))
	var panel := PanelContainer.new()
	var sb: StyleBoxFlat = UiStyle.panel_box(false)
	sb.set_content_margin_all(12)
	sb.shadow_size = 0
	sb.border_width_top = 1
	panel.add_theme_stylebox_override(&"panel", sb)
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 16)
	panel.add_child(h)
	var thumb := TextureRect.new()
	thumb.custom_minimum_size = Vector2(THUMB_SIZE) * 0.6
	thumb.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	thumb.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	thumb.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	thumb.texture = read_thumb(slot)
	if thumb.texture == null:
		# No frame (a save from before thumbnails, or a headless run): a plain dark plate.
		var plate := ColorRect.new()
		plate.color = Color(0.04, 0.045, 0.04)
		plate.custom_minimum_size = thumb.custom_minimum_size
		plate.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		h.add_child(plate)
	else:
		h.add_child(thumb)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override(&"separation", 6)
	h.add_child(v)
	var t: PackedStringArray = card_text(meta, read_card(slot), int(Time.get_unix_time_from_system()))
	var title := UiStyle.label(t[0], &"SubheadingLabel")
	title.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	v.add_child(title)
	var det := UiStyle.label(t[1])
	det.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(det)
	v.add_child(UiStyle.label(t[2], &"DimLabel"))
	var warn: String = SaveSystem.world_warning(meta)
	if warn != "":
		var wl := UiStyle.label(warn, &"DimLabel")
		wl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		wl.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
		v.add_child(wl)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override(&"separation", 8)
	v.add_child(buttons)
	var load := Button.new()
	load.text = "Load"
	load.theme_type_variation = &"PrimaryButton"
	load.custom_minimum_size = Vector2(160, 40)
	load.pressed.connect(func() -> void: load_requested.emit(slot))
	buttons.add_child(load)
	var del := Button.new()
	del.text = "Delete"
	del.custom_minimum_size = Vector2(120, 40)
	del.pressed.connect(func() -> void:
		# Twice: the first press asks, the second (within 3 s) deletes.
		if not del.has_meta(&"armed"):
			del.set_meta(&"armed", true)
			del.text = "Delete for good? Press again"
			get_tree().create_timer(3.0).timeout.connect(func() -> void:
				if is_instance_valid(del):
					del.remove_meta(&"armed")
					del.text = "Delete")
			return
		SaveSystem.delete_slot(slot)
		slots = slots.filter(func(m: Dictionary) -> bool: return str(m.get("slot", "")) != slot)
		_build())
	buttons.add_child(del)
	return panel


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"cancel") or event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		closed.emit()
