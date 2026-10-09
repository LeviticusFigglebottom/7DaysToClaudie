class_name IntroPlayer
extends Control
## The new-game intro (player report 4, item 2; ADR-0064): the Bloom, the Cordon, the Remand
## Program and how #4471 comes to be lying at the drop site, as a sequence of cards from
## data/intro/intro.json. Captions are typed on black, the Program's forms are typed on paper and
## stamped, the drop is a radio log, the wreck is a picture rendered offline and slowly zoomed
## (ADR-0065: nothing in the intro draws 3D), and the title closes it.
##
## It plays over the loading screen while the world loads. The load's main-thread half does heavy
## steps (up to ~0.5 s a frame headless, more with new models), so the intro tells GameWorld when
## a step may run: `is_calm()` is true only while a card is fully shown and holding, never during
## a fade or while text is being typed. A long step then lands where nothing moves. If the world is
## ready first, control waits for the intro; if the intro ends first, the loading screen returns.
##   Hold Esc, Space or Enter (or click Skip) to skip it.

signal finished()

const SCRIPT_PATH: String = "res://data/intro/intro.json"
const KINDS: PackedStringArray = ["caption", "document", "radio", "impact", "world", "title"]
const CARD_KEYS: PackedStringArray = ["kind", "stamp", "heading", "lines", "hold", "sound", "sounds", "caption", "poi", "at", "from", "to", "height"]
## The world card's picture, rendered offline (`make stills`, ADR-0065) and slowly zoomed in on over
## the card: the shot is never drawn live, so the load's work and a slow GPU can't stutter it, and
## it needs no world. SHOT_ZOOM is the zoom at the card's end (the old live shot's push in).
const SHOT_STILL: String = "res://assets/generated/stills/intro_wreck.png"
const SHOT_ZOOM: float = 1.12
## The hour the picture is taken at: just after first light (the wreck burned out before it; at
## 06:24 the hull was a dark shape under the card's words).
const SHOT_HOUR: float = 7.0
## The world card's camera (rendered): its field of view, metres out from its target, up, and
## degrees it turns over the card.
const SHOT_FOV: float = 52.0
const SHOT_RADIUS: float = 38.0
const SHOT_HEIGHT: float = 15.0
const SHOT_TURN: float = 14.0
## Where the camera starts round its target (degrees, 0 = +Z, 90 = +X: east, up the wreck's
## swath of snapped trees, which trails east of the nose; the swath is the clear line of sight).
const SHOT_START: float = 82.0
## A shot framed on its POI's plan (`from`/`to` cells): the camera starts `height` m over `from`,
## looks at `to`, and moves this share of the way toward it over the card (a slow push in).
const SHOT_PUSH: float = 0.22
## The impact card: seconds of shake and of the flash's fade.
const SHAKE_TIME: float = 1.6
const SHAKE_PX: float = 26.0
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
## Seconds into the current impact card (-1: none).
var _impact_t: float = -1.0
## The world card's picture while it shows, and seconds into it.
var _shot_still: TextureRect = null
var _shot_t: float = 0.0
var _shot_len: float = 1.0
var _bg: ColorRect


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = UiStyle.kit_theme()
	var bg := ColorRect.new()
	_bg = bg
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
	_skip_hint = UiStyle.label("Hold Esc (or B) to skip", &"DimLabel")
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
		if (c.get("lines", []) as Array).is_empty() and not str(c.get("kind", "")) in ["title", "impact"]:
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
	return {"day": day, "time": time, "hum_in": hum_in, "place": drop_place()}


## The region of the drop site in capitals ("LARCH HOLLOW"), else "THE TIMBER" before the world
## exists or where it has no name.
static func drop_place() -> String:
	var w: Node = Game.world if Game != null else null
	var tm: Object = w.get(&"terrain") if w != null else null
	var wd: WorldDef = tm.get(&"world") as WorldDef if tm != null else null
	if wd == null or not w.has_method(&"drop_site"):
		return "THE TIMBER"
	var at: Vector3 = w.call(&"drop_site")
	var name_: String = str((wd.regions.get(wd.region_at(at.x, at.z), {}) as Dictionary).get("name", ""))
	return name_.to_upper() if name_ != "" else "THE TIMBER"


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
	_request_shot_still()
	_index = -1
	if not _playing:
		finished.emit.call_deferred()
		return
	var music: String = str(_script.get("music", ""))
	if music != "" and Audio.stream(StringName(music)) != null:
		_music = AudioStreamPlayer.new()
		_music.stream = Audio.stream(StringName(music))
		_music.bus = &"Music"
		_music.volume_db = UiStyle.level("intro_music", -14.0)
		add_child(_music)
		_music.play()
	_next()


func is_playing() -> bool:
	return _playing


## True when nothing on screen is moving: the moment for the load to run a heavy step (never while
## the world card's picture zooms: a step would stall it).
func is_calm() -> bool:
	return not _playing or (_phase == &"hold" and _shot_still == null)


## Shown under the cards while the world loads ("Entering the Cordon… 40%").
func set_status(text: String) -> void:
	if _status != null:
		_status.text = text


func skip_intro() -> void:
	if not _playing:
		return
	_end()


func _end() -> void:
	_end_shot()
	position = Vector2.ZERO
	_impact_t = -1.0
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
	# Where the drop was, read from the world once it is up (a random world's region, not ours).
	_vars["place"] = drop_place()
	_card = _build_card(c)
	add_child(_card)
	move_child(_card, 2)
	_card.modulate.a = 0.0
	_phase = &"in"
	_t = 0.0
	_end_shot()
	if str(c.get("kind", "")) == "world":
		_begin_shot(c)
	var snd: String = str(c.get("sound", ""))
	if snd != "":
		Audio.play_2d(StringName(snd), UiStyle.level("intro_card", -6.0), &"SFX")
	for k: int in (c.get("sounds", []) as Array).size():
		Audio.play_2d(StringName(str(c["sounds"][k])), UiStyle.level("intro_impact", 0.0), &"SFX", 1.0 - 0.08 * k)
	if str(c.get("kind", "")) == "impact":
		# No fade in: the crash cuts in.
		_card.modulate.a = 1.0
		_phase = &"type"
		_impact_t = 0.0
		if _music != null:
			_music.volume_db = -40.0
			create_tween().tween_property(_music, "volume_db", UiStyle.level("intro_music", -14.0), 6.0)


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
	if _impact_t >= 0.0:
		_impact(dt)
	if _shot_still != null:
		_zoom_shot(dt)
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
		Audio.play_2d(&"sfx/item_place_mat", UiStyle.level("intro_stamp", -2.0), &"SFX", 0.7)
	return true


# --- The world card (an in-world shot: the Lift 3 wreck) ----------------------------------------

## Where a world card looks: its POI's built instance, else its `at` [x, z]; null when the world
## isn't up (the card then plays as a caption on black).
static func shot_target(c: Dictionary) -> Variant:
	var w: Node = Game.world
	if w == null or not bool(w.get(&"is_ready")):
		return null
	var poi_id := StringName(str(c.get("poi", "")))
	var pois: Node = w.get(&"pois")
	if poi_id != &"" and pois != null:
		for inst: Variant in (pois.get(&"instances") as Dictionary).values():
			var n: Node3D = inst as Node3D
			if n != null and is_instance_valid(n) and n.get(&"layout") != null and ((n.get(&"layout") as Object).get(&"def") as Object).get(&"id") == poi_id:
				return n.global_position
	var at: Array = c.get("at", [])
	if at.size() == 2 and w.has_method(&"height_at"):
		return Vector3(float(at[0]), float(w.call(&"height_at", float(at[0]), float(at[1]))), float(at[1]))
	return null


## A framed shot in world space: [camera start, camera end, look-at], from the card's `from`/`to`
## cells on its POI's plan (empty when the card has none, or the POI isn't built).
static func shot_frame(c: Dictionary) -> PackedVector3Array:
	var w: Node = Game.world
	var from: Array = c.get("from", [])
	var to: Array = c.get("to", [])
	if w == null or from.size() != 2 or to.size() != 2 or w.get(&"pois") == null:
		return PackedVector3Array()
	var poi_id := StringName(str(c.get("poi", "")))
	for inst: Variant in (w.get(&"pois").get(&"instances") as Dictionary).values():
		var n: Node3D = inst as Node3D
		if n == null or not is_instance_valid(n) or n.get(&"layout") == null:
			continue
		var layout: PoiLayout = n.get(&"layout") as PoiLayout
		if layout.def == null or layout.def.id != poi_id:
			continue
		var a: Vector3 = n.global_transform * layout.cell_center(0, Vector2i(int(from[0]), int(from[1])))
		var b: Vector3 = n.global_transform * layout.cell_center(0, Vector2i(int(to[0]), int(to[1])))
		var up := Vector3.UP * float(c.get("height", SHOT_HEIGHT))
		return PackedVector3Array([a + up, a.lerp(b, SHOT_PUSH) + up, b + Vector3.UP * 1.5])
	return PackedVector3Array()


## How long the world card's film runs (s): the card's hold, its fades and time for its words to
## type; the push in ends there and the last frame holds.
static func shot_length(c: Dictionary) -> float:
	return maxf(float(c.get("hold", 6.0)) + 2.0 * FADE + 4.0, 1.0)


## The world card's camera `t` seconds into its shot (filmed by FilmRunner): along the framed
## `path` (shot_frame) with an eased push in, else turning slowly round `at`, `w`'s ground under it.
static func shot_pose(path: PackedVector3Array, at: Vector3, t: float, length: float, w: Node) -> Transform3D:
	if path.size() == 3:
		var k: float = smoothstep(0.0, 1.0, clampf(t / length, 0.0, 1.0))
		return Transform3D(Basis.IDENTITY, path[0].lerp(path[1], k)).looking_at(path[2], Vector3.UP)
	var yaw: float = deg_to_rad(SHOT_START) + deg_to_rad(SHOT_TURN) / 14.0 * t
	var pos: Vector3 = at + Vector3(sin(yaw), 0.0, cos(yaw)) * SHOT_RADIUS
	var ground: float = float(w.call(&"height_at", pos.x, pos.z)) if w != null and w.has_method(&"height_at") else at.y
	pos.y = maxf(ground, at.y) + SHOT_HEIGHT
	return Transform3D(Basis.IDENTITY, pos).looking_at(at + Vector3.UP * 2.0, Vector3.UP)


## Whether the world card has its picture (generated assets; without it the card is a caption on
## black).
static func has_shot_still() -> bool:
	return ResourceLoader.exists(SHOT_STILL)


## Starts loading the world card's picture off the main thread (a 3200 px image would hitch the card
## it starts on).
func _request_shot_still() -> void:
	if has_shot_still():
		ResourceLoader.load_threaded_request(SHOT_STILL, "Texture2D")


func _begin_shot(c: Dictionary) -> void:
	if not has_shot_still() or ResourceLoader.load_threaded_get_status(SHOT_STILL) != ResourceLoader.THREAD_LOAD_LOADED:
		return
	var tex: Texture2D = ResourceLoader.load_threaded_get(SHOT_STILL) as Texture2D
	if tex == null:
		return
	_shot_still = TextureRect.new()
	_shot_still.texture = tex
	_shot_still.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_shot_still.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_shot_still.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_shot_still.modulate.a = 0.0
	add_child(_shot_still)
	_shot_still.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# Above the black, under the grain and the card's words.
	move_child(_shot_still, _bg.get_index() + 1)
	_shot_t = 0.0
	_shot_len = shot_length(c)
	_zoom_shot(0.0)
	create_tween().tween_property(_shot_still, "modulate:a", 1.0, FADE * 1.5)


## The picture's slow push in: eased to SHOT_ZOOM over the shot's length, about its centre (the
## camera looked at the wreck).
func _zoom_shot(dt: float) -> void:
	_shot_t += dt
	_shot_still.pivot_offset = _shot_still.size * 0.5
	var k: float = smoothstep(0.0, 1.0, clampf(_shot_t / _shot_len, 0.0, 1.0))
	_shot_still.scale = Vector2.ONE * lerpf(1.0, SHOT_ZOOM, k)


func _end_shot() -> void:
	if _shot_still == null:
		return
	_shot_still.queue_free()
	_shot_still = null


## Whether the world card is showing the world now (tests, QA).
func is_showing_world() -> bool:
	return _shot_still != null


## The crash: the frame shakes and a fire-white flash fades to black, decaying together.
func _impact(dt: float) -> void:
	_impact_t += dt
	var k: float = clampf(1.0 - _impact_t / SHAKE_TIME, 0.0, 1.0)
	var flash: ColorRect = _card.get_node_or_null("Flash") as ColorRect
	if flash != null:
		flash.color.a = k * k
	position = Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)) * SHAKE_PX * k * k
	if _impact_t >= SHAKE_TIME:
		position = Vector2.ZERO
		_impact_t = -1.0


func _update_skip(delta: float) -> void:
	var held: bool = Input.is_key_pressed(KEY_ESCAPE) or Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_ENTER)
	for j: int in Input.get_connected_joypads():
		held = held or Input.is_joy_button_pressed(j, JOY_BUTTON_B) or Input.is_joy_button_pressed(j, JOY_BUTTON_START)
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
	# Sound captions (Options): what the card's sound says, for players who can't hear it.
	if captions_on() and str(c.get("caption", "")) != "":
		var cap := UiStyle.label(str(c["caption"]), &"DimLabel")
		cap.add_theme_font_size_override(&"font_size", 22)
		cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cap.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
		cap.offset_top = -130
		cap.offset_bottom = -96
		cap.offset_left = -500
		cap.offset_right = 500
		root.add_child(cap)
	match str(c.get("kind", "caption")):
		"document":
			_document(root, c)
		"radio":
			_radio(root, c)
		"title":
			_title(root, c)
		"world":
			# A dark band under the words: the world behind them can be bright.
			var band := ColorRect.new()
			band.color = Color(0.0, 0.0, 0.0, 0.55)
			band.anchor_top = 0.5
			band.anchor_right = 1.0
			band.anchor_bottom = 0.86
			band.mouse_filter = Control.MOUSE_FILTER_IGNORE
			root.add_child(band)
			_caption(root, c)
		"impact":
			var flash := ColorRect.new()
			flash.name = "Flash"
			flash.color = Color(1.0, 0.82, 0.62, 1.0)
			flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
			flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
			root.add_child(flash)
			_caption(root, c)
		_:
			_caption(root, c)
	return root


## Whether sound captions are on (Options; off when the Settings autoload isn't there).
static func captions_on() -> bool:
	var st: Node = Engine.get_main_loop().root.get_node_or_null(^"/root/Settings") if Engine.get_main_loop() is SceneTree else null
	return st != null and bool(st.get(&"sound_captions"))


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
