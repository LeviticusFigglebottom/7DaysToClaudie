class_name IntroPlayer
extends Control
## The new-game intro (player report 4, item 2; ADR-0064): the Bloom, the Cordon, the Remand
## Program and how #4471 comes to be lying at the drop site, as a sequence of cards from
## data/intro/intro.json. Captions are typed on black, the Program's forms are typed on paper and
## stamped, the drop is a radio log, and the title closes it.
##
## It plays over the loading screen while the world loads. The load's main-thread half does heavy
## steps (up to ~0.5 s a frame headless, more with new models), so the intro tells GameWorld when
## a step may run: `is_calm()` is true only while a card is fully shown and holding, never during
## a fade or while text is being typed. A long step then lands where nothing moves. If the world is
## ready first, control waits for the intro; if the intro ends first, the loading screen returns.
##   Hold Esc, Space or Enter (or click Skip) to skip it.

signal finished()

const SCRIPT_PATH: String = "res://data/intro/intro.json"
const KINDS: PackedStringArray = ["caption", "document", "radio", "title"]
const CARD_KEYS: PackedStringArray = ["kind", "stamp", "heading", "lines", "hold", "sound"]
const FADE: float = 1.1
## Seconds the skip keys are held to skip.
const SKIP_HOLD: float = 0.9
const RADIO_LINE_GAP: float = 0.55

var _script: Dictionary = {}
var _cards: Array = []
var _index: int = -1
var _phase: StringName = &"idle"
var _t: float = 0.0
var _playing: bool = false
var _card: Control = null
## Labels typed in order on the current card; the typing position in characters.
var _typed: Array[Label] = []
var _chars: float = 0.0
var _type_speed: float = 42.0
var _stamp: Control = null
var _skip_t: float = 0.0
var _skip_ring: ProgressBar
var _skip_hint: Label
var _music: AudioStreamPlayer
var _vars: Dictionary = {}
var _grain: ColorRect
## A line under the cards with the load's progress (set by GameUI while the world loads).
var _status: Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = UiStyle.kit_theme()
	var bg := ColorRect.new()
	bg.color = Color(0.012, 0.012, 0.011)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	_grain = ColorRect.new()
	_grain.set_anchors_preset(Control.PRESET_FULL_RECT)
	_grain.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sm := ShaderMaterial.new()
	sm.shader = _grain_shader()
	_grain.material = sm
	add_child(_grain)
	var foot := HBoxContainer.new()
	foot.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	foot.offset_top = -64
	foot.offset_bottom = -28
	foot.offset_left = 48
	foot.offset_right = -48
	foot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(foot)
	_status = UiStyle.label("", &"DimLabel")
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	foot.add_child(_status)
	_skip_hint = UiStyle.label("Hold Esc to skip", &"DimLabel")
	_skip_hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	foot.add_child(_skip_hint)
	_skip_ring = ProgressBar.new()
	_skip_ring.custom_minimum_size = Vector2(90, 6)
	_skip_ring.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_skip_ring.show_percentage = false
	_skip_ring.max_value = 1.0
	_skip_ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	foot.add_child(_skip_ring)
	var skip := Button.new()
	skip.text = "Skip"
	skip.focus_mode = Control.FOCUS_NONE
	skip.pressed.connect(skip_intro)
	foot.add_child(skip)


# --- Script -----------------------------------------------------------------------------------

## The intro's script from data/intro/intro.json ({} when missing or broken; problems go to
## `errors`).
static func load_script(path: String = SCRIPT_PATH, errors: PackedStringArray = []) -> Dictionary:
	if not FileAccess.file_exists(path):
		errors.append("%s: missing" % path)
		return {}
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK or not (json.data is Dictionary):
		errors.append("%s: %s" % [path, json.get_error_message()])
		return {}
	var d: Dictionary = json.data
	errors.append_array(validate(d))
	return d


## Problems with a script: unknown kinds or keys, cards without lines, holds out of range.
static func validate(d: Dictionary) -> PackedStringArray:
	var out: PackedStringArray = []
	for k: String in d:
		if not k.begins_with("_") and not k in ["music", "type_speed", "cards"]:
			out.append("intro: unknown key '%s'" % k)
	var cards: Array = d.get("cards", [])
	if cards.is_empty():
		out.append("intro: no cards")
	for i: int in cards.size():
		var c: Dictionary = cards[i] if cards[i] is Dictionary else {}
		if not KINDS.has(str(c.get("kind", ""))):
			out.append("intro card %d: kind '%s' is not one of %s" % [i, c.get("kind", ""), ", ".join(KINDS)])
		for k2: String in c:
			if not CARD_KEYS.has(k2):
				out.append("intro card %d: unknown key '%s'" % [i, k2])
		if (c.get("lines", []) as Array).is_empty() and str(c.get("kind", "")) != "title":
			out.append("intro card %d: no lines" % i)
		var hold: float = float(c.get("hold", 3.0))
		if hold < 1.0 or hold > 15.0:
			out.append("intro card %d: hold %.1f s out of 1..15" % [i, hold])
		if str(c.get("kind", "")) == "radio":
			for l: Variant in c.get("lines", []):
				if not str(l).contains("|"):
					out.append("intro card %d: radio line needs 'SPEAKER|text': %s" % [i, l])
	return out


## Fills {day}, {time}, {hum_in} in a line.
static func fill(text: String, vars: Dictionary) -> String:
	var s: String = text
	for k: String in vars:
		s = s.replace("{%s}" % k, str(vars[k]))
	return s


## The placeholders for a session: its day, the time, and how long until the first Hum in words.
static func vars_for(session: GameSession) -> Dictionary:
	var day: int = 1
	var time: String = "07:30"
	var hum_in: String = "Six days until the ground hums."
	if session != null and session.clock != null:
		var c: WorldClock = session.clock
		day = c.day()
		time = "%02d:%02d" % [c.hour(), c.minute()]
		hum_in = hum_line(c.hordes_enabled(), c.next_horde_day(day) - day)
	return {"day": day, "time": time, "hum_in": hum_in}


const NUMBER_WORDS: PackedStringArray = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
	"Eight", "Nine", "Ten", "Eleven", "Twelve"]


static func hum_line(enabled: bool, days: int) -> String:
	if not enabled:
		return "The tether's countdown reads nothing at all."
	if days <= 0:
		return "The ground hums tonight."
	var n: String = NUMBER_WORDS[days] if days < NUMBER_WORDS.size() else str(days)
	return "%s day%s until the ground hums." % [n, "" if days == 1 else "s"]


# --- Playback ---------------------------------------------------------------------------------

func play(script: Dictionary = {}, vars: Dictionary = {}) -> void:
	_script = script if not script.is_empty() else load_script()
	_cards = _script.get("cards", [])
	_type_speed = float(_script.get("type_speed", 42.0))
	_vars = vars
	_playing = not _cards.is_empty()
	_index = -1
	if not _playing:
		finished.emit.call_deferred()
		return
	var music: String = str(_script.get("music", ""))
	if music != "" and Audio.stream(StringName(music)) != null:
		_music = AudioStreamPlayer.new()
		_music.stream = Audio.stream(StringName(music))
		_music.bus = &"Music"
		_music.volume_db = -14.0
		add_child(_music)
		_music.play()
	_next()


func is_playing() -> bool:
	return _playing


## True when nothing on screen is moving: the moment for the load to run a heavy step.
func is_calm() -> bool:
	return not _playing or _phase == &"hold"


## Shown under the cards while the world loads ("Entering the Cordon… 40%").
func set_status(text: String) -> void:
	if _status != null:
		_status.text = text


func skip_intro() -> void:
	if not _playing:
		return
	_end()


func _end() -> void:
	_playing = false
	_phase = &"idle"
	if _music != null:
		var tw := create_tween()
		tw.tween_property(_music, "volume_db", -60.0, 1.2)
		tw.tween_callback(_music.stop)
	finished.emit()


func _next() -> void:
	_index += 1
	if _card != null:
		_card.queue_free()
		_card = null
	if _index >= _cards.size():
		_end()
		return
	var c: Dictionary = _cards[_index]
	_typed.clear()
	_stamp = null
	_chars = 0.0
	_card = _build_card(c)
	add_child(_card)
	move_child(_card, 2)
	_card.modulate.a = 0.0
	_phase = &"in"
	_t = 0.0
	var snd: String = str(c.get("sound", ""))
	if snd != "":
		Audio.play_2d(StringName(snd), -6.0)


## Shows card `i` fully typed and holding (visual QA, tests).
func show_card(i: int) -> void:
	if _cards.is_empty():
		play()
	_index = i - 1
	_next()
	_card.modulate.a = 1.0
	_chars = 1e6
	_type_step(0.0, str((_cards[_index] as Dictionary).get("kind", "")))
	_phase = &"hold"
	_t = 0.0


func _process(delta: float) -> void:
	if not _playing:
		return
	# Hitches (a load step) never skip a card: time in a phase advances at most a tenth of a second.
	var dt: float = minf(delta, 0.1)
	_update_skip(delta)
	_t += dt
	var c: Dictionary = _cards[_index]
	match _phase:
		&"in":
			_card.modulate.a = clampf(_t / FADE, 0.0, 1.0)
			if _t >= FADE * 0.6:
				_phase = &"type"
				_t = 0.0
		&"type":
			_card.modulate.a = 1.0
			if _type_step(dt, str(c.get("kind", ""))):
				_phase = &"hold"
				_t = 0.0
		&"hold":
			if _t >= float(c.get("hold", 3.0)):
				_phase = &"out"
				_t = 0.0
		&"out":
			_card.modulate.a = 1.0 - clampf(_t / FADE, 0.0, 1.0)
			if _t >= FADE:
				_next()


## Reveals the card's labels in order; true once everything (and the stamp) is shown.
func _type_step(dt: float, kind: String) -> bool:
	_chars += dt * _type_speed
	var budget: float = _chars
	for l: Label in _typed:
		var n: int = l.get_total_character_count()
		var gap: float = RADIO_LINE_GAP * _type_speed if kind == "radio" else 0.0
		if budget >= n + gap:
			l.visible_characters = -1
			budget -= n + gap
			continue
		l.visible_characters = maxi(0, int(budget))
		return false
	if _stamp != null and not _stamp.visible:
		_stamp.visible = true
		Audio.play_2d(&"sfx/item_place_mat", -2.0, &"UI", 0.7)
	return true


func _update_skip(delta: float) -> void:
	var held: bool = Input.is_key_pressed(KEY_ESCAPE) or Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_ENTER)
	_skip_t = _skip_t + delta if held else maxf(0.0, _skip_t - delta * 2.0)
	_skip_ring.value = clampf(_skip_t / SKIP_HOLD, 0.0, 1.0)
	if _skip_t >= SKIP_HOLD:
		_skip_t = 0.0
		skip_intro()


# --- Cards ------------------------------------------------------------------------------------

func _build_card(c: Dictionary) -> Control:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	match str(c.get("kind", "caption")):
		"document":
			_document(root, c)
		"radio":
			_radio(root, c)
		"title":
			_title(root, c)
		_:
			_caption(root, c)
	return root


func _typed_label(text: String, size: int, color: Color, f: Font = null) -> Label:
	var l := Label.new()
	l.text = fill(text, _vars)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", color)
	if f != null:
		l.add_theme_font_override(&"font", f)
	l.visible_characters = 0
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_typed.append(l)
	return l


func _centre_box(root: Control, width: float, top: float) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.anchor_left = 0.5
	v.anchor_right = 0.5
	v.anchor_top = top
	v.anchor_bottom = top
	v.offset_left = -width * 0.5
	v.offset_right = width * 0.5
	v.grow_vertical = Control.GROW_DIRECTION_BOTH
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(v)
	return v


func _caption(root: Control, c: Dictionary) -> void:
	var v: VBoxContainer = _centre_box(root, 1100.0, 0.62)
	v.add_theme_constant_override(&"separation", 14)
	if str(c.get("stamp", "")) != "":
		var st := UiStyle.label(fill(str(c["stamp"]), _vars), &"SubheadingLabel")
		st.add_theme_font_size_override(&"font_size", 20)
		v.add_child(st)
		var rule := ColorRect.new()
		rule.color = Color(UiStyle.RUST_BRIGHT, 0.6)
		rule.custom_minimum_size = Vector2(160, 2)
		rule.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		v.add_child(rule)
	for line: Variant in c.get("lines", []):
		v.add_child(_typed_label(str(line), 28, UiStyle.KIT_TEXT))


func _document(root: Control, c: Dictionary) -> void:
	var centre := CenterContainer.new()
	centre.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	centre.offset_bottom = -60
	centre.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(centre)
	var paper := PanelContainer.new()
	paper.theme = UiStyle.paper_theme()
	var sb: StyleBoxFlat = UiStyle.panel_box(true)
	sb.set_content_margin_all(44)
	sb.shadow_size = 24
	paper.add_theme_stylebox_override(&"panel", sb)
	paper.custom_minimum_size = Vector2(860, 0)
	paper.mouse_filter = Control.MOUSE_FILTER_IGNORE
	centre.add_child(paper)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 14)
	paper.add_child(v)
	v.add_child(UiStyle.label("FORM R-7  ·  REMAND SALVAGE PROGRAM  ·  CORDON AUTHORITY", &"DimLabel"))
	v.add_child(UiStyle.label(fill(str(c.get("heading", "")), _vars), &"HeadingLabel"))
	v.add_child(HSeparator.new())
	for line: Variant in c.get("lines", []):
		v.add_child(_typed_label(str(line), 22, UiStyle.INK, UiStyle.heading_font()))
	# The stamp has its own row at the foot of the form, struck at an angle once the text is in.
	var foot := HBoxContainer.new()
	foot.custom_minimum_size = Vector2(0, 76)
	foot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(foot)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	foot.add_child(spacer)
	if str(c.get("stamp", "")) != "":
		var stamp := PanelContainer.new()
		var ss := StyleBoxFlat.new()
		ss.bg_color = Color(0, 0, 0, 0)
		ss.border_color = Color(UiStyle.INK_MISSING, 0.85)
		ss.set_border_width_all(4)
		ss.set_corner_radius_all(6)
		ss.content_margin_left = 16
		ss.content_margin_right = 16
		ss.content_margin_top = 6
		ss.content_margin_bottom = 6
		stamp.add_theme_stylebox_override(&"panel", ss)
		stamp.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		stamp.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var sl := Label.new()
		sl.text = str(c["stamp"])
		sl.add_theme_font_override(&"font", UiStyle.heading_font())
		sl.add_theme_font_size_override(&"font_size", 34)
		sl.add_theme_color_override(&"font_color", Color(UiStyle.INK_MISSING, 0.85))
		stamp.add_child(sl)
		stamp.visible = false
		# Containers reset their children's rotation: the stamp hangs in a plain Control.
		var slot := Control.new()
		slot.custom_minimum_size = Vector2(340, 76)
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		foot.add_child(slot)
		slot.add_child(stamp)
		stamp.resized.connect(func() -> void:
			stamp.pivot_offset = stamp.size * 0.5
			stamp.position = Vector2(slot.custom_minimum_size.x - stamp.size.x, (76.0 - stamp.size.y) * 0.5))
		stamp.rotation = deg_to_rad(-8.0)
		_stamp = stamp
	# A touch of tilt, like a form on a desk: on the centring container, which no parent lays out.
	centre.resized.connect(func() -> void: centre.pivot_offset = centre.size * 0.5)
	centre.rotation = deg_to_rad(-1.0)


func _radio(root: Control, c: Dictionary) -> void:
	var v: VBoxContainer = _centre_box(root, 1000.0, 0.5)
	v.add_theme_constant_override(&"separation", 12)
	var head := UiStyle.label(fill(str(c.get("heading", "CORDON RADIO")), _vars), &"SubheadingLabel")
	head.add_theme_font_size_override(&"font_size", 20)
	v.add_child(head)
	var rule := ColorRect.new()
	rule.color = Color(UiStyle.RUST_BRIGHT, 0.6)
	rule.custom_minimum_size = Vector2(160, 2)
	rule.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	v.add_child(rule)
	for line: Variant in c.get("lines", []):
		var parts: PackedStringArray = str(line).split("|", true, 1)
		var h := HBoxContainer.new()
		h.add_theme_constant_override(&"separation", 18)
		h.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(h)
		var who := _typed_label(parts[0], 20, UiStyle.RUST_BRIGHT)
		who.custom_minimum_size = Vector2(130, 0)
		who.autowrap_mode = TextServer.AUTOWRAP_OFF
		h.add_child(who)
		var said := _typed_label(parts[1] if parts.size() > 1 else "", 24, UiStyle.KIT_TEXT)
		said.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(said)


func _title(root: Control, c: Dictionary) -> void:
	var v: VBoxContainer = _centre_box(root, 1200.0, 0.45)
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	var t := Label.new()
	t.text = "HOLLOWMERE"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.add_theme_font_override(&"font", UiStyle.heading_font())
	t.add_theme_font_size_override(&"font_size", 120)
	t.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	v.add_child(t)
	for line: Variant in c.get("lines", []):
		var l := _typed_label(str(line), 36, UiStyle.RUST_BRIGHT, UiStyle.hand_font())
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(l)


## Film grain and a vignette: the black between cards is never dead flat.
static func _grain_shader() -> Shader:
	var s := Shader.new()
	s.code = """shader_type canvas_item;
void fragment() {
	vec2 uv = UV;
	float n = fract(sin(dot(floor(uv * vec2(640.0, 360.0)) + floor(TIME * 24.0), vec2(12.9898, 78.233))) * 43758.5453);
	float vig = smoothstep(0.95, 0.25, distance(uv, vec2(0.5)));
	COLOR = vec4(vec3(n * 0.06), (1.0 - vig) * 0.65 + n * 0.035);
}
"""
	return s
