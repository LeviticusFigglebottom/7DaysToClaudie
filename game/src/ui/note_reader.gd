class_name NoteReader
extends Control
## The note reader (the lore trail, docs/LORE_TRAIL.md): a found note on its own sheet, in the
## hand or machine that wrote it.
##   handwritten  Caveat in blue-black on cream
##   scrawl       Caveat in pencil on torn grey card, tilted
##   typed        Special Elite on office white
##   printed      EB Garamond on newsprint
## Long notes turn pages (A/D, the arrows, the wheel or the buttons). Esc, E or Close puts it away.
## It opens straight from picking a note up (GameUI) and from the Field Manual's notes.

signal closed()

## Per style: the face, its size, the ink, the paper, the tilt (degrees), characters per page.
const STYLES: Dictionary = {
	"handwritten": {"font": "hand", "size": 32, "ink": Color(0.13, 0.17, 0.33), "paper": Color(0.93, 0.89, 0.78), "tilt": -1.2, "page": 620},
	"scrawl": {"font": "hand", "size": 36, "ink": Color(0.27, 0.27, 0.28), "paper": Color(0.78, 0.76, 0.72), "tilt": 2.0, "page": 380},
	"typed": {"font": "typed", "size": 22, "ink": Color(0.12, 0.11, 0.1), "paper": Color(0.95, 0.94, 0.9), "tilt": -0.6, "page": 900},
	"printed": {"font": "serif", "size": 24, "ink": Color(0.1, 0.1, 0.1), "paper": Color(0.86, 0.84, 0.78), "tilt": 0.4, "page": 1000},
}
const SERIF_FONT: String = "res://assets/fonts/EBGaramond-Variable.ttf"

var _sheet: PanelContainer
var _holder: Control
var _title: Label
var _byline: Label
var _body: Label
var _foot: Label
var _prev: Button
var _next: Button
var _pages: PackedStringArray = []
var _page: int = 0
var _open: bool = false


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	theme = UiStyle.kit_theme()
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.02, 0.02, 0.78)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	var centre := CenterContainer.new()
	centre.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	centre.offset_bottom = -70
	centre.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(centre)
	_holder = centre
	_sheet = PanelContainer.new()
	_sheet.custom_minimum_size = Vector2(760, 640)
	_sheet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	centre.add_child(_sheet)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	_sheet.add_child(v)
	_title = Label.new()
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_title)
	_byline = Label.new()
	_byline.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_byline)
	_body = Label.new()
	_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_body.custom_minimum_size = Vector2(680, 0)
	v.add_child(_body)
	_foot = Label.new()
	_foot.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	v.add_child(_foot)
	# The buttons sit under the sheet, in the kit's style, so the paper stays paper.
	var bar := HBoxContainer.new()
	bar.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	bar.offset_top = -64
	bar.offset_bottom = -20
	bar.offset_left = -300
	bar.offset_right = 300
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	bar.add_theme_constant_override(&"separation", 12)
	add_child(bar)
	_prev = Button.new()
	_prev.text = "< Page"
	_prev.pressed.connect(func() -> void: turn(-1))
	bar.add_child(_prev)
	var close := Button.new()
	close.text = "Put it away"
	close.theme_type_variation = &"PrimaryButton"
	close.custom_minimum_size = Vector2(220, 44)
	close.pressed.connect(close_reader)
	bar.add_child(close)
	_next = Button.new()
	_next.text = "Page >"
	_next.pressed.connect(func() -> void: turn(1))
	bar.add_child(_next)


## Splits a note's body into pages of at most `per_page` characters, at paragraph breaks, else at
## sentence ends, else at spaces. Pure, for tests.
static func paginate(body: String, per_page: int) -> PackedStringArray:
	var pages: PackedStringArray = []
	var cur: String = ""
	for para: String in body.split("\n"):
		var chunks: PackedStringArray = [para]
		if para.length() > per_page:
			chunks = _split_long(para, per_page)
		for chunk: String in chunks:
			var add: String = chunk if cur == "" else cur + "\n" + chunk
			if add.length() > per_page and cur != "":
				pages.append(cur.strip_edges())
				cur = chunk
			else:
				cur = add
	if cur.strip_edges() != "" or pages.is_empty():
		pages.append(cur.strip_edges())
	return pages


static func _split_long(text: String, per_page: int) -> PackedStringArray:
	var out: PackedStringArray = []
	var rest: String = text
	while rest.length() > per_page:
		var cut: int = -1
		for mark: String in [". ", "? ", "! ", "; ", ", ", " "]:
			cut = rest.rfind(mark, per_page)
			if cut > per_page / 3:
				cut += mark.length()
				break
		if cut <= 0:
			cut = per_page
		out.append(rest.substr(0, cut).strip_edges())
		rest = rest.substr(cut)
	if rest.strip_edges() != "":
		out.append(rest.strip_edges())
	return out


static func style_of(n: NoteDef) -> Dictionary:
	return STYLES.get(n.style, STYLES["handwritten"])


static func _face(kind: String) -> Font:
	match kind:
		"hand":
			return UiStyle.hand_font()
		"typed":
			return UiStyle.heading_font()
		"serif":
			return UiStyle.font(SERIF_FONT)
	return UiStyle.body_font()


## Shows a note. `found` is where and when it was found ({"where", "day"}; {} when unknown).
func show_note(n: NoteDef, found: Dictionary = {}) -> void:
	if n == null:
		return
	var st: Dictionary = style_of(n)
	var ink: Color = st["ink"]
	var f: Font = _face(str(st["font"]))
	var sb := StyleBoxFlat.new()
	sb.bg_color = st["paper"]
	sb.set_content_margin_all(48)
	sb.shadow_color = Color(0, 0, 0, 0.55)
	sb.shadow_size = 22
	sb.shadow_offset = Vector2(0, 6)
	if n.style == "scrawl":
		# Torn card: an uneven, darker edge.
		sb.border_color = Color(0.55, 0.53, 0.5)
		sb.set_border_width_all(2)
		sb.border_width_bottom = 5
	_sheet.add_theme_stylebox_override(&"panel", sb)
	for l: Label in [_title, _byline, _body, _foot]:
		l.add_theme_color_override(&"font_color", ink)
		l.add_theme_font_override(&"font", f)
	_title.add_theme_font_size_override(&"font_size", int(st["size"]) + 8)
	_body.add_theme_font_size_override(&"font_size", int(st["size"]))
	_byline.add_theme_font_size_override(&"font_size", int(st["size"]) - 4)
	_byline.add_theme_color_override(&"font_color", Color(ink, 0.75))
	_foot.add_theme_font_override(&"font", UiStyle.body_font())
	_foot.add_theme_font_size_override(&"font_size", 15)
	_foot.add_theme_color_override(&"font_color", Color(ink, 0.6))
	_title.text = n.title
	_byline.text = n.author
	_byline.visible = n.author != ""
	_pages = paginate(n.body, int(st["page"]))
	_page = 0
	var where: String = str(found.get("where", ""))
	_foot.set_meta(&"where", ("Found: %s, day %d" % [where, int(found.get("day", 1))]) if where != "" else "")
	_holder.pivot_offset = _holder.size * 0.5
	_holder.rotation = deg_to_rad(float(st["tilt"]))
	_show_page()
	_open = true
	visible = true
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"note_reader")
	Audio.play_2d(&"ui/page_turn", UiStyle.level("page_turn", -6.0))


func _show_page() -> void:
	_body.text = _pages[_page] if _page < _pages.size() else ""
	var where: String = str(_foot.get_meta(&"where", ""))
	var pages: String = ("page %d of %d" % [_page + 1, _pages.size()]) if _pages.size() > 1 else ""
	var bits: PackedStringArray = []
	for b: String in [where, pages]:
		if b != "":
			bits.append(b)
	_foot.text = "   ·   ".join(bits)
	_prev.disabled = _page <= 0
	_next.disabled = _page >= _pages.size() - 1
	_prev.visible = _pages.size() > 1
	_next.visible = _pages.size() > 1


func turn(step: int) -> void:
	var to: int = clampi(_page + step, 0, maxi(0, _pages.size() - 1))
	if to != _page:
		_page = to
		_show_page()
		Audio.play_2d(&"ui/page_turn", UiStyle.level("page_turn", -6.0) - 4.0)


func is_open() -> bool:
	return _open


func page_count() -> int:
	return _pages.size()


func close_reader() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"note_reader")
	closed.emit()


func _gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if _open and mb != null and mb.pressed:
		if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			turn(1)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			turn(-1)
		accept_event()


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed(&"cancel") or event.is_action_pressed(&"pause") or event.is_action_pressed(&"interact") or event.is_action_pressed(&"ui_cancel"):
		close_reader()
	elif event.is_action_pressed(&"move_right") or event.is_action_pressed(&"ui_right"):
		turn(1)
	elif event.is_action_pressed(&"move_left") or event.is_action_pressed(&"ui_left"):
		turn(-1)
	else:
		return
	get_viewport().set_input_as_handled()
