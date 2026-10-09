class_name GameUI
extends CanvasLayer
## Screen-space UI: loading screen, minimal HUD, pause menu, and the modal stack shared with the
## diegetic UIs (salvage roll, field manual, tether) so mouse capture is handled in one place.
## The HUD stays minimal by design: prompt + transient feedback; vitals live on the tether.

var _loading: Control
var _loading_label: Label
var _loading_map: LoadingMap
var _loading_bar: ProgressBar
var _hud: Control
var _crosshair: Control
var _prompt: Label
var _tool_hint: Label
## Toolbelt strip: shown for a moment whenever the held item or the belt changes.
var _belt: RichTextLabel
var _belt_key: String = ""
var _belt_t: float = 0.0
var _hold: ProgressBar
var _messages: VBoxContainer
var _vitals: HBoxContainer
var _bars: Dictionary = {}
var _hum_label: Label
var _vignette: ColorRect
var _pause: Control
var _modals: Array[StringName] = []
var _wire_t: float = 0.0
var _damage_flash: float = 0.0
var roll: SalvageRoll
var world_map: WorldMap
var reader: NoteReader
var manual: FieldManual
var tether: Tether
var _final_death: bool = false
var _overlay: ColorRect
var _overlay_label: Label
var _overlay_head: Label
var _overlay_note: Label
var _death_button: Button
## Highest level reached since the last announcement (several can arrive in one award).
var _level_pending: int = 0
## Where recent hits came from (world positions + fade time), drawn as red wedges at the screen
## edge pointing at the attacker.
var _hits: Array[Dictionary] = []
var _wedges: Control
var _heart: AudioStreamPlayer
## The new-game intro (ADR-0064) while it plays, over the loading screen and then the world.
var intro: IntroPlayer = null
## Whether the intro paused the world (it outlasted the load) and holds the "intro" modal.
var _intro_holds_world: bool = false
## The last clean frame of play (no menu over it), kept for the save's thumbnail on the Load
## screen: taken as the pause menu opens and every THUMB_EVERY seconds of free play.
var _last_frame: Image = null
var _relief_done: bool = false
var _pickups: VBoxContainer
## Whether this run's first journal card has been announced (once, as the player first stands).
var _first_card_said: bool = false
## StatusFeed priorities of the lines GameUI queues (the Hum's report is StatusFeed.PRIORITY_REPORT,
## 10): at dawn the report, then the autosave line, the level-up, the drone.
const PRIO_DAWN: int = 5
const PRIO_LEVEL: int = 3
const PRIO_DROP: int = 0
var _ov_tween: Tween = null
## Caption text -> when it was last shown (the repeat limit).
var _captions_said: Dictionary = {}
const CAPTION_REPEAT: float = 8.0
## Seconds left before the waiting level-up is said (see _on_leveled).
var _level_wait: float = 0.0
const LEVEL_SETTLE: float = 2.5
var _tip_box: Control
var _tip_title: Label
var _tip_text: Label
var _tips: Array[Array] = []
var _tip_i: int = 0
var _tip_left: float = 0.0
var _frame_t: float = 0.0
const THUMB_EVERY: float = 90.0


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_loading()
	_build_hud()
	roll = SalvageRoll.new()
	roll.name = "SalvageRoll"
	add_child(roll)
	manual = FieldManual.new()
	manual.name = "FieldManual"
	add_child(manual)
	world_map = WorldMap.new()
	world_map.name = "WorldMap"
	add_child(world_map)
	reader = NoteReader.new()
	reader.name = "NoteReader"
	add_child(reader)
	# Notes (the lore trail): where each was found, and the reader straight from picking one up.
	if not Game.has_command(&"notes.mark_found"):
		Game.register_command(&"notes.mark_found", _cmd_mark_found)
	Events.note_found.connect(_on_note_found)
	Events.item_picked_up.connect(_on_item_picked_up)
	_build_overlay()
	_build_pause()
	_maybe_start_intro()
	Events.player_status_message.connect(message)
	Events.player_damaged.connect(_on_player_damaged)
	# Standing again after a death: nothing of the death screen may stay over the world.
	Events.player_spawned.connect(func(_id: StringName) -> void:
		if _overlay.visible and not _death_button.visible and not (Game.world != null and bool(Game.world.get(&"sleeping"))):
			_overlay_tween().kill()
			_overlay.visible = false)
	# The Hum's warnings and its start are announced by HumDirector alone (with the forecast).
	Events.horde_night_ended.connect(_on_hum_ended)
	Events.game_saved.connect(_write_thumb)
	Events.game_saved.connect(func(_slot: String, ok: bool) -> void:
		# Autosaves announce themselves in their own line ("Rested. Progress saved.").
		if not ok or not Game.autosaving:
			message("Saved." if ok else "Save failed!", &"info" if ok else &"error"))
	Events.schematic_learned.connect(func(id: StringName) -> void: message("Learned: %s" % String(id).capitalize(), &"info"))
	Events.player_leveled.connect(_on_leveled)
	# The first days' tutorial (hub contract): a nudge when a step is done, a call when the
	# distress signal comes in. Connected only once the backend's signals exist.
	if Events.has_signal(&"tutorial_changed"):
		Events.connect(&"tutorial_changed", _on_tutorial_changed)
	if Events.has_signal(&"tutorial_distress"):
		Events.connect(&"tutorial_distress", _on_tutorial_distress)
	Events.supply_drop_landed.connect(func(_id: StringName, at: Vector3) -> void:
		message(drop_landed_line(FieldManual.distress_bearing(at)), &"level"))
	# Sound captions (Options): the Hum's rise is music, which nothing else puts into words.
	Events.sound_caption.connect(_on_sound_caption)
	Events.horde_night_started.connect(func(_d: int) -> void:
		if Settings.sound_captions:
			message("[a deep hum rises through the ground]", &"danger"))
	Events.supply_drop_incoming.connect(func(_id: StringName, _p: Vector3) -> void:
		Events.status_message_queued.emit("A Program drone is overhead. Supplies are coming down.", &"level", PRIO_DROP))


## Dawn after a Hum: the run is saved (a night survived is the progress most worth keeping).
## Deferred: this handler connects before the Hum director's, which files the night's report and
## releases the survivors in its own handler of the same signal.
func _on_hum_ended(_day: int, _report: Dictionary) -> void:
	_autosave_after_hum.call_deferred()


func _autosave_after_hum() -> void:
	var lp: PlayerState = Game.local_player()
	# Through the paced feed (first-week W15): the night's report goes first, then this.
	if lp != null and lp.stats.alive and Game.autosave():
		Events.status_message_queued.emit("Dawn. The Hollowed root into the soil. Progress saved.", &"info", PRIO_DAWN)
	else:
		Events.status_message_queued.emit("Dawn. The Hollowed root into the soil.", &"info", PRIO_DAWN)


# --- Loading --------------------------------------------------------------------------------

func _build_loading() -> void:
	_loading = ColorRect.new()
	(_loading as ColorRect).color = Color(0.02, 0.022, 0.025)
	_loading.set_anchors_preset(Control.PRESET_FULL_RECT)
	_loading.theme = UiStyle.kit_theme()
	add_child(_loading)
	var title := Label.new()
	title.text = "HOLLOWMERE"
	title.add_theme_font_override(&"font", UiStyle.heading_font())
	title.add_theme_font_size_override(&"font_size", 72)
	title.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	title.position = Vector2(80, 80)
	_loading.add_child(title)
	_loading_label = Label.new()
	_loading_label.position = Vector2(84, 170)
	_loading_label.add_theme_color_override(&"font_color", Color(0.6, 0.62, 0.58))
	_loading.add_child(_loading_label)
	_loading_bar = ProgressBar.new()
	_loading_bar.position = Vector2(84, 205)
	_loading_bar.size = Vector2(520, 10)
	_loading_bar.show_percentage = false
	_loading.add_child(_loading_bar)
	_loading_map = LoadingMap.new()
	_loading_map.position = Vector2(680, 80)
	_loading_map.size = Vector2(520, 520)
	_loading_map.visible = false
	_loading.add_child(_loading_map)
	# A Survival page from the Field Manual at a time, turned at reading pace (never one that
	# gives away a find: FieldManual.TIPS_NOT_WHILE_LOADING).
	var tip_box := VBoxContainer.new()
	tip_box.add_theme_constant_override(&"separation", 6)
	tip_box.anchor_top = 1.0
	tip_box.anchor_bottom = 1.0
	tip_box.grow_vertical = Control.GROW_DIRECTION_BEGIN
	tip_box.offset_left = 84
	tip_box.offset_right = 84 + 1000
	tip_box.offset_bottom = -64
	_loading.add_child(tip_box)
	_tip_title = Label.new()
	_tip_title.add_theme_font_override(&"font", UiStyle.hand_font())
	_tip_title.add_theme_font_size_override(&"font_size", 32)
	_tip_title.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
	tip_box.add_child(_tip_title)
	_tip_text = Label.new()
	_tip_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_tip_text.custom_minimum_size = Vector2(1000, 0)
	_tip_text.add_theme_font_size_override(&"font_size", 19)
	_tip_text.add_theme_color_override(&"font_color", Color(0.72, 0.73, 0.68))
	tip_box.add_child(_tip_text)
	_tip_box = tip_box
	_tips = FieldManual.loading_tips()
	_tip_i = randi() % maxi(_tips.size(), 1)
	_show_tip()


## How long a tip stays up: reading time at a calm pace, at least 8 s.
static func tip_seconds(text: String) -> float:
	return maxf(8.0, text.split(" ", false).size() / 3.2 + 2.0)


func _show_tip() -> void:
	if _tips.is_empty():
		return
	var t: Array = _tips[_tip_i % _tips.size()]
	_tip_title.text = str(t[0])
	_tip_text.text = str(t[1])
	_tip_left = tip_seconds(str(t[1]))
	_tip_box.modulate.a = 0.0
	var tw := _tip_box.create_tween()
	tw.tween_property(_tip_box, "modulate:a", 1.0, 0.6)


func _turn_tip(delta: float) -> void:
	if _loading == null or not _loading.visible or _tips.is_empty():
		return
	_tip_left -= delta
	if _tip_left <= 0.0:
		_tip_i = (_tip_i + 1) % _tips.size()
		_tip_left = 1.0e9
		var tw := _tip_box.create_tween()
		tw.tween_property(_tip_box, "modulate:a", 0.0, 0.6)
		tw.tween_callback(_show_tip)


## The tip on the loading screen now ([title, text]).
func loading_tip() -> Array:
	return [_tip_title.text, _tip_text.text] if _tip_title != null else []


## `map`: the world's map (random worlds) and `marks` its region states (LoadingMap); a null map
## leaves the last one shown.
func show_loading(text: String, progress: float, map: Texture2D = null, marks: Dictionary = {}) -> void:
	if intro != null:
		intro.set_status("%s  %d%%" % [text, roundi(progress * 100.0)])
	_loading.visible = true
	_hud.visible = false
	_loading_label.text = text
	_loading_bar.value = progress * 100.0
	if map != null:
		_loading_map.set_map(map, marks)
		_relief_done = true
	elif not _relief_done:
		_show_relief()


## The main map's loading screen (a random world brings its own map.png): the survey sheet the
## world map shades, kept per world on disk (WorldMap.cache_file), under the save's fog, so only
## what the player has walked shows. A world's first load shows the blank sheet. The drop site is
## marked, and on a Continue the place the run was saved.
func _show_relief() -> void:
	var w: Node = Game.world
	var tm: Object = w.get(&"terrain") if w != null else null
	var wd: WorldDef = tm.get(&"world") as WorldDef if tm != null else null
	var lp: PlayerState = Game.local_player()
	if Game.session == null or Game.session.world_mode != &"main_map":
		_relief_done = true
		return
	if wd == null or lp == null or not w.has_method(&"drop_site"):
		return
	_relief_done = true
	var sheet: Image = null
	var file: String = WorldMap.cache_file(wd)
	if FileAccess.file_exists(file):
		sheet = Image.load_from_file(ProjectSettings.globalize_path(file))
	var drop: Vector3 = w.call(&"drop_site")
	var here: Variant = lp.position if not lp.explored.is_empty() else null
	var r: Rect2 = wd.world_rect()
	var img: Image = relief_image(sheet, WorldMap.fog_image(lp.explored, r), r, here)
	var side: float = maxf(r.size.x, r.size.y)
	var origin: Vector2 = r.get_center() - Vector2(side, side) * 0.5
	_loading_map.set_map(ImageTexture.create_from_image(img), {"point": (Vector2(drop.x, drop.z) - origin) / side})


## The loading screen's sheet: `sheet` (or blank paper) under `fog`, centred on a square of the
## loading screen's dark, with a ring where the run was saved (`here`, a Vector3 or null). Pure.
static func relief_image(sheet: Image, fog: Image, r: Rect2, here: Variant) -> Image:
	var w: int = maxi(int(r.size.x * WorldMap.PX_PER_M), 1)
	var h: int = maxi(int(r.size.y * WorldMap.PX_PER_M), 1)
	var paper := Image.create(w, h, false, Image.FORMAT_RGBA8)
	if sheet != null and not sheet.is_empty():
		paper = sheet.duplicate() as Image
		paper.convert(Image.FORMAT_RGBA8)
		if paper.get_width() != w or paper.get_height() != h:
			paper.resize(w, h, Image.INTERPOLATE_BILINEAR)
	else:
		paper.fill(WorldMap.PAPER)
	var f: Image = fog.duplicate() as Image
	f.resize(w, h, Image.INTERPOLATE_NEAREST)
	paper.blend_rect(f, Rect2i(0, 0, w, h), Vector2i.ZERO)
	if here is Vector3:
		var p: Vector2 = (Vector2((here as Vector3).x, (here as Vector3).z) - r.position) * WorldMap.PX_PER_M
		for dy: int in range(-9, 10):
			for dx: int in range(-9, 10):
				var d: float = Vector2(dx, dy).length()
				var x: int = int(p.x) + dx
				var y: int = int(p.y) + dy
				if x >= 0 and y >= 0 and x < w and y < h and d <= 9.0:
					paper.set_pixel(x, y, Color(0.1, 0.05, 0.02) if d > 6.0 or d < 2.5 else WorldMap.PAPER)
	var side: int = maxi(w, h)
	var out := Image.create(side, side, false, Image.FORMAT_RGBA8)
	out.fill(Color(0.02, 0.022, 0.025))
	out.blit_rect(paper, Rect2i(0, 0, w, h), Vector2i((side - w) / 2, (side - h) / 2))
	return out


## What the loading screen says now ("" once it is hidden).
func loading_text() -> String:
	return _loading_label.text if _loading != null and _loading.visible else ""


func hide_loading() -> void:
	_loading.visible = false
	_say_first_card.call_deferred()
	# Shade this world's sheet now (on a worker), so the next loading screen shows it.
	world_map.prepare.call_deferred()
	_hud.visible = true
	_hold_world_for_intro.call_deferred()


# --- The first days' journal (tutorial) ----------------------------------------------------------

## Step ids already done, to tell which ones a change just finished (null until first seen).
var _tutorial_done: Variant = null


func _on_tutorial_changed() -> void:
	# A frame later: when the tutorial hears a deed before the directives do, the step's folded
	# reward is set only after this signal (call_deferred runs too soon).
	await get_tree().process_frame
	var t: Object = FieldManual.tutorial()
	if t == null or not is_inside_tree():
		return
	var steps: Array = t.call(&"steps")
	var done: Dictionary = {}
	var rewards: Dictionary = {}
	var next_title: String = ""
	for st: Dictionary in steps:
		if bool(st.get("done", false)):
			done[str(st.get("id", ""))] = str(st.get("title", ""))
			rewards[str(st.get("id", ""))] = str(st.get("reward", ""))
		elif next_title == "" and bool(st.get("current", false)):
			next_title = str(st.get("title", ""))
	if _tutorial_done is Dictionary and bool(t.call(&"is_enabled")):
		for id: String in done:
			if not (_tutorial_done as Dictionary).has(id):
				message(journal_line(done[id], rewards[id], next_title, PlayerInteraction.key_label(&"guidebook")), &"level")
	_tutorial_done = done


## "Journal: Make a stone axe ✓  +40 XP   Next: Fell a tree  [B]": the step, what the deed paid
## (the Program directive it also finished, folded in), and the next card. Pure.
static func journal_line(title: String, reward: String, next_title: String, key: String) -> String:
	var line: String = "Journal: %s ✓" % title
	if reward != "":
		line += "  " + reward
	if next_title != "":
		line += "   Next: %s  [%s]" % [next_title, key]
	return line


## A new run's first card, said once the player can act (the load and the intro both over):
## nothing else tells a new player the journal exists or what to do first.
func _say_first_card() -> void:
	if _first_card_said or is_intro_playing() or (_loading != null and _loading.visible):
		return
	_first_card_said = true
	var line: String = first_card_line()
	if line != "":
		message(line, &"level")


## "Journal: <first step>  [B]" for a run with the tutorial on and no step done yet, else "".
static func first_card_line() -> String:
	var t: Object = FieldManual.tutorial()
	if t == null or not bool(t.call(&"is_enabled")):
		return ""
	var first: String = ""
	for st: Dictionary in t.call(&"steps"):
		if bool(st.get("done", false)):
			return ""
		if first == "":
			first = str(st.get("title", ""))
	return "" if first == "" else "Journal: %s  [%s]" % [first, PlayerInteraction.key_label(&"guidebook")]


func _on_tutorial_distress(_companion_id: StringName, position: Vector3) -> void:
	var d: Dictionary = FieldManual.live_distress()
	# A skipped call (Ezra already with you, or gone) has no text and no crackle.
	if d.is_empty():
		return
	var text: String = str(d.get("text", ""))
	Audio.play_2d(&"ui/tether_alarm", UiStyle.level("tether_alarm", -4.0))
	var cap: String = "[radio crackle] " if Settings.sound_captions else ""
	message("%sTether: a distress call crackles in, %s. %s" % [cap, FieldManual.distress_bearing(position), text], &"level")


# --- The intro (ADR-0064) -------------------------------------------------------------------------

## A new game plays the intro over the load (not a loaded one, not with skip_intro).
func _maybe_start_intro() -> void:
	var opts: Dictionary = Game.pending_options
	if not bool(opts.get("is_new_game", false)) or bool(opts.get("skip_intro", false)):
		return
	# Headless runs skip it, unless a probe asks (intro_load_probe measures its frames).
	if DisplayServer.get_name() == "headless" and not bool(opts.get("force_intro", false)):
		return
	intro = IntroPlayer.new()
	intro.name = "Intro"
	add_child(intro)
	intro.finished.connect(_on_intro_finished)
	intro.play({}, IntroPlayer.vars_for(Game.session))


## Whether the load may run a heavy main-thread step now (GameWorld asks each frame of its
## boot): only while no intro is moving on screen, so a long step never lands mid-fade.
func load_may_step() -> bool:
	return intro == null or intro.is_calm()


func is_intro_playing() -> bool:
	return intro != null and intro.is_playing()


## The world is ready but the intro is still on: pause the world under it and keep the player's
## hands off until it ends (the pause menu's pause, so nothing ticks unseen).
func _hold_world_for_intro() -> void:
	if not is_intro_playing() or _intro_holds_world:
		return
	_intro_holds_world = true
	push_modal(&"intro")
	get_tree().paused = true
	# The intro's world shot shows the world: not the HUD over it.
	_hud.visible = false


func _on_intro_finished() -> void:
	var i: IntroPlayer = intro
	intro = null
	if i != null:
		var tw := i.create_tween()
		tw.tween_property(i, "modulate:a", 0.0, 0.8)
		tw.tween_callback(i.queue_free)
	if _intro_holds_world:
		_intro_holds_world = false
		get_tree().paused = false
		_hud.visible = true
		pop_modal(&"intro")
	_say_first_card.call_deferred()


# --- HUD -----------------------------------------------------------------------------------

func _build_hud() -> void:
	_hud = Control.new()
	_hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.visible = false
	add_child(_hud)
	_vignette = ColorRect.new()
	_vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	_vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var vm := ShaderMaterial.new()
	vm.shader = _vignette_shader()
	_vignette.material = vm
	_hud.add_child(_vignette)
	_wedges = Control.new()
	_wedges.set_anchors_preset(Control.PRESET_FULL_RECT)
	_wedges.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wedges.draw.connect(_draw_wedges)
	_hud.add_child(_wedges)
	_heart = AudioStreamPlayer.new()
	_heart.bus = &"SFX"
	_heart.volume_db = -8.0
	# Replays while the condition lasts (the generated beats are one-shots).
	_heart.finished.connect(func() -> void:
		if _heart.get_meta(&"id", &"") != &"":
			_heart.play())
	_hud.add_child(_heart)
	_crosshair = ColorRect.new()
	(_crosshair as ColorRect).color = Color(0.9, 0.9, 0.85, 0.55)
	_crosshair.size = Vector2(3, 3)
	_crosshair.anchor_left = 0.5
	_crosshair.anchor_top = 0.5
	_crosshair.anchor_right = 0.5
	_crosshair.anchor_bottom = 0.5
	_crosshair.position = Vector2(-1.5, -1.5)
	_crosshair.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_crosshair)
	_prompt = Label.new()
	_prompt.anchor_left = 0.5
	_prompt.anchor_right = 0.5
	_prompt.anchor_top = 0.5
	_prompt.anchor_bottom = 0.5
	_prompt.position = Vector2(-300, 28)
	_prompt.size = Vector2(600, 30)
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.add_theme_color_override(&"font_color", Color(0.92, 0.9, 0.82))
	_prompt.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.8))
	_prompt.add_theme_constant_override(&"outline_size", 4)
	_prompt.add_theme_stylebox_override(&"normal", prompt_box(0.55))
	# Hidden until _hug gives it words: an empty label would still draw its plate.
	_prompt.visible = false
	_hud.add_child(_prompt)
	_tool_hint = Label.new()
	_tool_hint.anchor_left = 0.5
	_tool_hint.anchor_right = 0.5
	_tool_hint.anchor_top = 0.5
	_tool_hint.anchor_bottom = 0.5
	_tool_hint.position = Vector2(-400, 72)
	_tool_hint.size = Vector2(800, 24)
	_tool_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_tool_hint.add_theme_font_size_override(&"font_size", 15)
	_tool_hint.add_theme_color_override(&"font_color", Color(0.8, 0.78, 0.7, 0.9))
	_tool_hint.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.8))
	_tool_hint.add_theme_constant_override(&"outline_size", 4)
	_tool_hint.add_theme_stylebox_override(&"normal", prompt_box(0.45))
	_tool_hint.visible = false
	_hud.add_child(_tool_hint)
	_belt = RichTextLabel.new()
	_belt.bbcode_enabled = true
	_belt.fit_content = true
	_belt.scroll_active = false
	_belt.autowrap_mode = TextServer.AUTOWRAP_OFF
	_belt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_belt.anchor_left = 0.5
	_belt.anchor_right = 0.5
	_belt.anchor_top = 1.0
	_belt.anchor_bottom = 1.0
	# Above the vitals bars (bottom left at -46) so long belts never run into them.
	_belt.position = Vector2(-450, -96)
	_belt.size = Vector2(900, 30)
	_belt.add_theme_font_size_override(&"normal_font_size", 17)
	_belt.add_theme_font_size_override(&"bold_font_size", 17)
	_belt.add_theme_font_override(&"bold_font", UiStyle.bold_font())
	_belt.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
	_belt.add_theme_constant_override(&"outline_size", 4)
	_belt.modulate.a = 0.0
	_hud.add_child(_belt)
	_hold = ProgressBar.new()
	_hold.anchor_left = 0.5
	_hold.anchor_right = 0.5
	_hold.anchor_top = 0.5
	_hold.anchor_bottom = 0.5
	_hold.position = Vector2(-80, 60)
	_hold.size = Vector2(160, 6)
	_hold.show_percentage = false
	_hold.visible = false
	_hud.add_child(_hold)
	_messages = VBoxContainer.new()
	_messages.position = Vector2(40, 40)
	_messages.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_messages)
	_vitals = HBoxContainer.new()
	_vitals.anchor_top = 1.0
	_vitals.anchor_bottom = 1.0
	_vitals.position = Vector2(40, -46)
	_vitals.add_theme_constant_override(&"separation", 10)
	_hud.add_child(_vitals)
	for k: String in ["health", "stamina", "fullness", "hydration"]:
		var b := ProgressBar.new()
		b.custom_minimum_size = Vector2(90, 5)
		b.show_percentage = false
		b.modulate = {"health": Color(0.8, 0.25, 0.2), "stamina": Color(0.85, 0.85, 0.8), "fullness": Color(0.8, 0.6, 0.3), "hydration": Color(0.35, 0.6, 0.85)}[k]
		_vitals.add_child(b)
		_bars[k] = b
	_pickups = VBoxContainer.new()
	_pickups.anchor_left = 1.0
	_pickups.anchor_right = 1.0
	_pickups.anchor_top = 1.0
	_pickups.anchor_bottom = 1.0
	_pickups.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_pickups.grow_vertical = Control.GROW_DIRECTION_BEGIN
	# A zero-height rect at its bottom edge that grows upward with each line.
	_pickups.offset_left = -360
	_pickups.offset_right = -40
	_pickups.offset_top = -110
	_pickups.offset_bottom = -110
	_pickups.alignment = BoxContainer.ALIGNMENT_END
	_pickups.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(_pickups)
	_hum_label = Label.new()
	_hum_label.anchor_left = 1.0
	_hum_label.anchor_right = 1.0
	_hum_label.position = Vector2(-360, 40)
	_hum_label.size = Vector2(320, 30)
	_hum_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	# The Hum in the typewriter face and the rust accent (ADR-0063), outlined for daylight.
	_hum_label.add_theme_font_override(&"font", UiStyle.heading_font())
	_hum_label.add_theme_font_size_override(&"font_size", 26)
	_hum_label.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
	_hum_label.add_theme_color_override(&"font_outline_color", Color(0.03, 0.03, 0.02, 0.9))
	_hum_label.add_theme_constant_override(&"outline_size", 6)
	_hud.add_child(_hum_label)


## "The canister is down, north-west, 140 m. Its smoke marks the spot.", or without the bearing
## when the player's position isn't known.
static func drop_landed_line(bearing: String) -> String:
	return "The canister is down%s. Its smoke marks the spot." % ((", " + bearing) if bearing != "" else "")


## A big unseen sound put into words (Events.sound_caption), when captions are on: "[wolves
## howling, north-east]". The same sound again within CAPTION_REPEAT seconds is the same caption:
## a pack howling round you is one line, not ten.
func _on_sound_caption(text: String, at: Vector3) -> void:
	if not Settings.sound_captions or text == "":
		return
	var now: float = Time.get_ticks_msec() / 1000.0
	if now - float(_captions_said.get(text, -INF)) < CAPTION_REPEAT:
		return
	_captions_said[text] = now
	var w: Node = Game.world
	var bearing: String = ""
	if w != null and w.get(&"player") != null and at != Vector3.INF:
		bearing = FieldManual.bearing_words((w.player as Node3D).global_position, at)
	message(caption_line(text, bearing), &"info")


## "[wolves howling, north-east]" from a caption and FieldManual.bearing_words ("north-east,
## 140 m": the distance is left out, a sound only says where); "here" or no bearing: no direction.
static func caption_line(text: String, bearing: String) -> String:
	var dir: String = bearing.get_slice(",", 0).strip_edges()
	return "[%s]" % text if dir == "" or dir == "here" else "[%s, %s]" % [text, dir]


## The keys while laying out a blueprint ("[Left mouse] place  ·  [R] turn  ·  [Esc] cancel") or
## carrying logs; "" otherwise.
static func build_controls(placing: bool, carrying_logs: bool) -> String:
	var k: Callable = func(a: StringName) -> String: return "[%s]" % PlayerInteraction.key_label(a)
	if placing:
		return "%s place  ·  %s turn  ·  %s cancel" % [k.call(&"attack"), k.call(&"rotate_piece"), k.call(&"cancel")]
	if carrying_logs:
		return "%s set the log  ·  %s turn  ·  %s stand / pitch  ·  %s drop" % [k.call(&"attack"), k.call(&"rotate_piece"), k.call(&"build_mode_toggle"), k.call(&"drop")]
	return ""


## A quiet dark plate behind a prompt line, so it reads over a lit fire, snow or a pale ghost.
static func prompt_box(alpha: float) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.02, 0.02, 0.02, alpha)
	sb.set_corner_radius_all(3)
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	sb.content_margin_top = 2
	sb.content_margin_bottom = 3
	return sb


## Shrinks a centred prompt line to its text (its plate hugs the words) and keeps it centred
## under the crosshair, `below` px down; hidden when empty, plate and all.
func _hug(l: Label, below: float) -> void:
	l.visible = l.text != ""
	if not l.visible:
		return
	# Offsets, not position: the line hangs off the screen's centre anchor.
	var m: Vector2 = l.get_combined_minimum_size()
	l.offset_left = -m.x * 0.5
	l.offset_right = m.x * 0.5
	l.offset_top = below
	l.offset_bottom = below + m.y


static func _vignette_shader() -> Shader:
	var s := Shader.new()
	s.code = """
shader_type canvas_item;
uniform float damage = 0.0;
uniform float cold = 0.0;
uniform float low_health = 0.0;
// Value noise: the edges are ragged (blood seeping in, frost creeping in), never a clean ring.
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
void fragment() {
	vec2 d = UV - 0.5;
	float r = length(d * vec2(1.6, 1.0));
	// Square noise cells whatever the screen's shape.
	vec2 q = UV * vec2(SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x, 1.0);
	float n = vnoise(q * 9.0) * 0.6 + vnoise(q * 31.0) * 0.4;
	// Hurt: dark red seeping from the edge, the pulse quickening as health falls.
	float hurt = clamp(damage + low_health * (0.6 + 0.4 * sin(TIME * (3.0 + 3.0 * low_health))), 0.0, 1.0);
	float hurt_edge = smoothstep(0.42 - 0.12 * n, 0.98, r);
	// Cold: frost crystals creeping in, pale blue-white, sharper grain.
	float frost_n = vnoise(q * 70.0 + vec2(3.1, 7.7)) * 0.5 + vnoise(q * 160.0) * 0.5;
	// At its worst it keeps to the outer ring (from 0.38 out, at most 60%): a freezing player must
	// still see the night (first-week frames: the frost hid the Hum).
	float frost_edge = smoothstep(0.55 - 0.17 * cold - 0.08 * n, 0.95, r) * (0.65 + 0.35 * frost_n);
	vec3 col = vec3(0.4, 0.02, 0.02) * (0.8 + 0.2 * n);
	float a = hurt_edge * clamp(damage * 0.9 + low_health * 0.6, 0.0, 0.85);
	float fa = frost_edge * cold * 0.6;
	col = mix(col, vec3(0.82, 0.9, 0.97), fa / max(a + fa, 0.001));
	COLOR = vec4(col, clamp(a + fa, 0.0, 0.88));
}
"""
	return s


func _process(delta: float) -> void:
	_turn_tip(delta)
	if _level_wait > 0.0:
		_level_wait -= delta
		if _level_wait <= 0.0:
			_announce_level()
	_fade_pickups(delta)
	var w: Node = Game.world
	if w == null or w.get("player") == null or w.player == null:
		return
	var p: Player = w.player
	if p.interaction != null:
		# Nothing to act on through the death or sleep screen.
		_prompt.text = ("[%s] %s" % [PlayerInteraction.key_label(&"interact"), p.interaction.prompt]) if p.interaction.prompt != "" and not _overlay.visible else ""
		var ht: float = p.interaction.hold_t / maxf(p.interaction.hold_needed, 0.001) if p.interaction.hold_needed > 0.0 else 0.0
		_hold.visible = ht > 0.0
		_hold.value = ht * 100.0
		var b: Node = w.get(&"building")
		var place_why: String = str(b.call(&"placement_hint")) if b != null else ""
		# Under the prompt: why a placement can't go, else the held tool's hint, else what holding
		# the cancel key on the target does (take a blueprint ghost down).
		_tool_hint.text = place_why if place_why != "" else (p.interaction.tool_hint if p.interaction.tool_hint != "" else p.interaction.alt_prompt)
		# Laying out a blueprint or carrying logs: the keys, which nothing else on screen names.
		if place_why == "" and b != null and b.has_method(&"is_placing"):
			var ctl: String = build_controls(bool(b.call(&"is_placing")), p.state.inventory.count_of(&"log") > 0)
			if ctl != "" and _prompt.text == "":
				_tool_hint.text = ctl
		if _overlay.visible:
			_tool_hint.text = ""
		_hug(_prompt, 28.0)
		_hug(_tool_hint, 72.0)
	_update_belt(p.state, delta)
	_frame_t += delta
	if _frame_t >= THUMB_EVERY and not has_modal() and not _overlay.visible and not is_intro_playing():
		_grab_frame()
	if not _hits.is_empty():
		for h: Dictionary in _hits:
			h["t"] = float(h["t"]) - delta
		_hits = _hits.filter(func(h: Dictionary) -> bool: return float(h["t"]) > 0.0)
		_wedges.queue_redraw()
	var s: SurvivalStats = p.state.stats
	_update_heartbeat(s)
	# Grit raises max health past 100: the bar shows the share of it.
	(_bars["health"] as ProgressBar).value = s.health / maxf(1.0, s.max_health) * 100.0
	(_bars["stamina"] as ProgressBar).value = s.stamina / maxf(1.0, s.max_stamina) * 100.0
	(_bars["fullness"] as ProgressBar).value = s.fullness
	(_bars["hydration"] as ProgressBar).value = s.hydration
	# Vitals fade unless something is off (minimal HUD).
	var concern: bool = s.health < s.max_health * 0.7 or s.stamina < s.max_stamina * 0.6 or s.fullness < 30.0 or s.hydration < 30.0
	_vitals.modulate.a = lerpf(_vitals.modulate.a, 1.0 if concern else 0.15, minf(1.0, 3.0 * delta))
	var vm: ShaderMaterial = _vignette.material
	_damage_flash = maxf(0.0, _damage_flash - delta * 1.5)
	vm.set_shader_parameter("damage", _damage_flash)
	vm.set_shader_parameter("low_health", clampf((35.0 - s.health) / 35.0, 0.0, 1.0))
	vm.set_shader_parameter("cold", clampf((36.2 - s.body_temp) / 1.5, 0.0, 1.0))
	# Hum countdown (only within the last day or during).
	var clock: WorldClock = Game.session.clock
	var hrs: float = clock.hours_until_horde()
	if clock.is_horde_active():
		_hum_label.text = "THE HUM"
		_hum_label.modulate.a = 0.7 + 0.3 * sin(Time.get_ticks_msec() * 0.004)
	elif hrs < 24.0:
		_hum_label.text = "THE HUM IN %02d:%02d" % [int(hrs), int(fmod(hrs, 1.0) * 60.0)]
		_hum_label.modulate.a = 1.0
	else:
		_hum_label.text = ""
	_crosshair.visible = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED


func _update_belt(ps: PlayerState, delta: float) -> void:
	var parts: PackedStringArray = []
	for i: int in ps.toolbelt.size():
		var id: StringName = ps.toolbelt[i]
		var d: ItemDef = Content.item(id) if id != &"" and ps.inventory.has(id) else null
		var name_: String = d.display_name if d != null else "—"
		if d != null and ps.inventory.count_of(id) > 1:
			name_ += " ×%d" % ps.inventory.count_of(id)
		# In hand: the kit's rust accent and bold; the rest the kit's light type, never so dim it
		# reads as empty against bright ground (the outline carries it).
		if i == ps.equipped_slot and d != null:
			parts.append("[color=%s][b]%d %s[/b][/color]" % [UiStyle.hex(UiStyle.RUST_BRIGHT), i + 1, name_])
		elif d != null:
			parts.append("[color=%s]%d %s[/color]" % [UiStyle.hex(UiStyle.KIT_TEXT), i + 1, name_])
		else:
			parts.append("[color=%s]%d —[/color]" % [UiStyle.hex(UiStyle.KIT_TEXT_DIM), i + 1])
	var key: String = "    ·    ".join(parts)
	if key != _belt_key:
		_belt_key = key
		_belt.text = "[center]%s[/center]" % key
		_belt_t = 2.5
	_belt_t = maxf(0.0, _belt_t - delta)
	_belt.modulate.a = clampf(_belt_t / 0.6, 0.0, 1.0)


func _on_player_damaged(_id: StringName, amount: float, src: Dictionary) -> void:
	_flash_damage(amount)
	var from: Array = src.get("from", [])
	if from.size() == 3:
		_hits.append({"pos": Vector3(float(from[0]), float(from[1]), float(from[2])), "t": 1.4})
		if _hits.size() > 6:
			_hits.pop_front()


## Red wedges at the screen edge toward recent attackers, by the camera's yaw.
func _draw_wedges() -> void:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null or w.player == null:
		return
	var cam: Camera3D = (w.player as Player).camera
	var c: Vector2 = _wedges.size * 0.5
	var r: float = minf(c.x, c.y) * 0.62
	for h: Dictionary in _hits:
		var to: Vector3 = (h["pos"] as Vector3) - cam.global_position
		var local: Vector3 = cam.global_transform.basis.inverse() * to
		# Screen angle: straight ahead is up, behind is down.
		var ang: float = atan2(local.x, -local.z)
		var a: float = clampf(float(h["t"]) / 1.4, 0.0, 1.0)
		var pts := PackedVector2Array()
		for k: int in 9:
			var t: float = ang - 0.32 + 0.64 * float(k) / 8.0
			pts.append(c + Vector2(sin(t), -cos(t)) * r)
		for k: int in range(8, -1, -1):
			var t2: float = ang - 0.22 + 0.44 * float(k) / 8.0
			pts.append(c + Vector2(sin(t2), -cos(t2)) * (r - 26.0))
		_wedges.draw_colored_polygon(pts, Color(0.75, 0.05, 0.03, 0.55 * a))


## A heartbeat under 30% health, faster under 15%.
func _update_heartbeat(s: SurvivalStats) -> void:
	var share: float = s.health / maxf(1.0, s.max_health)
	var want: StringName = &"" if not s.alive or share >= 0.3 else (&"sfx/heartbeat_fast" if share < 0.15 else &"sfx/heartbeat_slow")
	if want == &"":
		if _heart.playing:
			_heart.stop()
		_heart.set_meta(&"id", &"")
		return
	if _heart.playing and _heart.get_meta(&"id", &"") == want:
		return
	_heart.stream = Audio.stream(want)
	_heart.set_meta(&"id", want)
	if _heart.stream != null:
		_heart.play()


func _flash_damage(amount: float) -> void:
	_damage_flash = clampf(_damage_flash + amount / 30.0, 0.0, 1.0)


func message(text: String, kind: StringName = &"info") -> void:
	# The same line again (a full pack, a locked door) refreshes the one on screen with a count
	# instead of stacking copies.
	for c: Node in _messages.get_children():
		var old: Label = c as Label
		if old != null and not old.is_queued_for_deletion() and str(old.get_meta(&"text", "")) == text:
			var n: int = int(old.get_meta(&"count", 1)) + 1
			old.set_meta(&"count", n)
			old.text = "%s  ×%d" % [text, n]
			old.modulate.a = 1.0
			_fade_message(old)
			return
	var l := Label.new()
	l.text = text
	l.set_meta(&"text", text)
	# The kit's palette (ADR-0063): light type, amber warnings, red danger, rust for progress (a
	# level, a journal step); a heavy outline so a line reads over snow or a bright sky.
	l.add_theme_color_override(&"font_color", {&"info": UiStyle.KIT_TEXT, &"warning": Color(0.95, 0.8, 0.45), &"danger": Color(0.95, 0.35, 0.3), &"error": Color(1, 0.4, 0.4), &"level": UiStyle.RUST_BRIGHT}.get(kind, UiStyle.KIT_TEXT))
	l.add_theme_color_override(&"font_outline_color", Color(0.03, 0.03, 0.02, 0.9))
	l.add_theme_constant_override(&"outline_size", 6)
	l.add_theme_font_size_override(&"font_size", UiStyle.BODY_SIZE + 1)
	_messages.add_child(l)
	# A long line (the distress call) wraps at 820 px instead of running off the screen; a short
	# one never wraps (a guessed width once put "[B]" on its own line).
	if text.length() > 80:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(820, 0)
	_fade_message(l)
	while _messages.get_child_count() > 6:
		_messages.get_child(0).queue_free()
		_messages.remove_child(_messages.get_child(0))


## How long a message stays before it fades: 4 s, or its reading time when longer (a distress
## call is fifty words).
static func message_seconds(text: String) -> float:
	return maxf(4.0, text.split(" ", false).size() / 3.0 + 1.5)


func _fade_message(l: Label) -> void:
	if l.has_meta(&"tween"):
		var prev: Tween = l.get_meta(&"tween") as Tween
		if prev != null and prev.is_valid():
			prev.kill()
	var tw: Tween = l.create_tween()
	tw.tween_interval(message_seconds(str(l.get_meta(&"text", l.text))))
	tw.tween_property(l, "modulate:a", 0.0, 1.2)
	tw.tween_callback(l.queue_free)
	l.set_meta(&"tween", tw)


func _on_leveled(player_id: StringName, level: int) -> void:
	if Game.session == null or player_id != Game.session.local_player_id:
		return
	# A burst (a dungeon cleared pays for several levels over a few seconds) is said once, at its
	# highest, when no new level has come for LEVEL_SETTLE seconds (mid-game audit M8).
	_level_pending = maxi(_level_pending, level)
	_level_wait = LEVEL_SETTLE


## One message and one chime however many levels a single award crossed.
func _announce_level() -> void:
	var p: PlayerState = Game.local_player()
	if p == null or _level_pending == 0:
		_level_pending = 0
		return
	var pts: int = p.progression.skill_points
	Events.status_message_queued.emit("Level %d. %d point%s to spend — field manual [%s], Record." % [_level_pending, pts, "" if pts == 1 else "s", PlayerInteraction.key_label(&"guidebook")], &"level", PRIO_LEVEL)
	Audio.play_2d(&"ui/level_up", UiStyle.level("level_up", -4.0))
	_level_pending = 0


# --- Modal stack / pause ---------------------------------------------------------------------

## Diegetic UIs call these so mouse capture and player input stay consistent.
func push_modal(id: StringName) -> void:
	if not _modals.has(id):
		_modals.append(id)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var w: Node = Game.world
	if w != null and w.get("player") != null and w.player != null:
		w.player.look_enabled = false
		w.player.input_enabled = false
	Events.ui_modal_opened.emit(id)


func pop_modal(id: StringName) -> void:
	_modals.erase(id)
	if _modals.is_empty():
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		var w: Node = Game.world
		if w != null and w.get("player") != null and w.player != null:
			w.player.look_enabled = true
			w.player.input_enabled = w.player.state.stats.alive
	Events.ui_modal_closed.emit(id)


func has_modal() -> bool:
	return not _modals.is_empty()


func _build_pause() -> void:
	_pause = ColorRect.new()
	(_pause as ColorRect).color = Color(0, 0, 0, 0.6)
	_pause.set_anchors_preset(Control.PRESET_FULL_RECT)
	_pause.visible = false
	_pause.theme = UiStyle.kit_theme()
	add_child(_pause)
	var box := VBoxContainer.new()
	box.position = Vector2(80, 120)
	box.add_theme_constant_override(&"separation", 2)
	_pause.add_child(box)
	var title := UiStyle.label("PAUSED", &"HeadingLabel")
	title.add_theme_font_size_override(&"font_size", 64)
	box.add_child(title)
	var sub := UiStyle.label("The valley waits. It is good at that.", &"HandLabel")
	sub.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
	box.add_child(sub)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 24)
	box.add_child(gap)
	for spec: Array in [["Resume", toggle_pause], ["Save", func() -> void: Game.save_game()],
			["Load last save", _confirm_load], ["Options", _open_options], ["Controls", _open_options.bind("Controls")],
			["Save and quit to menu", _save_and_quit], ["Quit without saving", _confirm_quit]]:
		var b := Button.new()
		b.text = spec[0]
		b.name = String(spec[0]).replace(" ", "_")
		b.theme_type_variation = &"MenuEntry"
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size = Vector2(520, 48)
		b.pressed.connect(spec[1])
		box.add_child(b)


## Actions that throw away unsaved progress ask twice: the first press re-labels the button.
func _confirmed(button_name: String, question: String) -> bool:
	var b: Button = _pause.find_child(button_name, true, false) as Button
	if b == null:
		return true
	if b.has_meta(&"armed"):
		return true
	var text: String = b.text
	b.text = question
	b.set_meta(&"armed", true)
	get_tree().create_timer(3.0, true, false, true).timeout.connect(func() -> void:
		if is_instance_valid(b):
			b.text = text
			b.remove_meta(&"armed"))
	return false


func _confirm_load() -> void:
	if _confirmed("Load_last_save", "Lose progress since the last save? Press again"):
		Game.load_game(Game.current_slot)


func _confirm_quit() -> void:
	if _confirmed("Quit_without_saving", "Lose progress since the last save? Press again"):
		Game.quit_to_menu()


func _save_and_quit() -> void:
	var lp: PlayerState = Game.local_player()
	if lp != null and lp.stats.alive and not Game.save_game():
		message("Save failed: still in the game.", &"error")
		return
	Game.quit_to_menu()


func _open_options(tab: String = "General") -> void:
	var panel := OptionsPanel.new()
	panel.open_tab = tab
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.position = (get_viewport().get_visible_rect().size - Vector2(680, 660)) * 0.5
	_pause.visible = false
	panel.closed.connect(func() -> void: _pause.visible = true)


func toggle_pause() -> void:
	# Not while asleep or on the death screen: resuming would hand control back mid-sleep.
	if _overlay.visible:
		return
	var on: bool = not _pause.visible and not _modals.has(&"pause")
	if on and has_modal() and not _modals.has(&"pause"):
		# Escape closes the top diegetic UI first.
		var top: StringName = _modals.back()
		Events.ui_modal_closed.emit(top)
		pop_modal(top)
		return
	if on:
		# The frame just drawn, before the menu covers it: what a save from the menu shows.
		_grab_frame()
	_pause.visible = on
	get_tree().paused = on
	if on:
		push_modal(&"pause")
	else:
		for c: Node in get_children():
			if c is OptionsPanel:
				c.queue_free()
		pop_modal(&"pause")


# --- Diegetic UIs --------------------------------------------------------------------------

## A gamepad press with nothing focused focuses the first control of the screen on top (the
## reader, the map, the roll's recipe sheet, the manual, the trader, pause, the death screen).
func _input(event: InputEvent) -> void:
	# The pad's B puts away whatever is on top (the screens' own keys are keyboard keys).
	var jb := event as InputEventJoypadButton
	if jb != null and jb.pressed and jb.button_index == JOY_BUTTON_B and close_top_screen():
		get_viewport().set_input_as_handled()
		return
	if not UiStyle.is_pad_event(event) or get_viewport().gui_get_focus_owner() != null:
		return
	for i: int in range(get_child_count() - 1, -1, -1):
		var c: Control = get_child(i) as Control
		if c == null or not c.visible or c == _hud or c == _loading:
			continue
		# The roll steers its cloth with the pad itself; its recipe sheet takes focus on RB.
		if c == roll:
			return
		if UiStyle.focus_first(c):
			get_viewport().set_input_as_handled()
			return


## Closes the screen on top, if one is open (gamepad B). True when something closed.
func close_top_screen() -> bool:
	if reader.is_open():
		reader.close_reader()
	elif world_map.is_open():
		world_map.close()
	elif manual.is_open():
		manual.close()
	elif roll.is_open():
		roll.close()
	elif _pause.visible:
		toggle_pause()
	else:
		for c: Node in get_children():
			if c is TraderScreen and (c as TraderScreen).is_open():
				(c as TraderScreen).close_screen()
				return true
			# Ezra's order card (CompanionScreen): B on a pad closes it like Esc.
			if c is CompanionScreen and (c as CompanionScreen).is_open():
				(c as CompanionScreen).close_screen()
				return true
		return false
	return true


func _unhandled_input(event: InputEvent) -> void:
	var w: Node = Game.world
	if w == null or not bool(w.get(&"is_ready")) or is_intro_playing():
		return
	# Handled here, not in GameWorld: this layer keeps processing while the tree is paused, so
	# Escape also closes the pause menu.
	if event.is_action_pressed(&"pause"):
		get_viewport().set_input_as_handled()
		toggle_pause()
		return
	if _pause.visible or _overlay.visible:
		return
	if event.is_action_pressed(&"inventory") and not roll.is_open() and not manual.is_open():
		roll.open()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"guidebook") and not manual.is_open() and not roll.is_open():
		manual.open()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"map") and not roll.is_open() and not manual.is_open():
		world_map.toggle()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed(&"tracker"):
		_ensure_tether()
		if tether != null:
			tether.toggle()
			_raise_wrist(tether.raised)
		get_viewport().set_input_as_handled()


## The first-person arms lift the left wrist to read the tether (held until it is lowered).
func _raise_wrist(up: bool) -> void:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null:
		return
	var vm: ViewModel = (w.player as Player).equipment.viewmodel
	if vm != null:
		vm.play_action(&"fp_raise_wrist" if up else &"fp_lower_wrist", 0.0, up)


func _ensure_tether() -> void:
	if tether != null and is_instance_valid(tether):
		return
	var w: Node = Game.world
	if w == null or w.get(&"player") == null or w.player == null:
		return
	tether = Tether.new()
	tether.name = "Tether"
	(w.player as Player).camera.add_child(tether)


## Station crafting (campfire, workbench...) on the salvage roll's flap.
func open_crafting(station_id: StringName, node: Node) -> void:
	roll.open(&"station", station_id, node)


## Containers (crates, cabinets, remains, storage) on the roll's flap.
func open_container(node: Object) -> void:
	roll.open(&"container", &"", node)


func show_note(note_id: StringName) -> void:
	if roll.is_open():
		roll.close()
	var p: PlayerState = Game.local_player()
	reader.show_note(Content.get_def(&"note", note_id) as NoteDef, p.notes_found.get(note_id, {}) if p != null else {})


func _exit_tree() -> void:
	if Game.has_command(&"notes.mark_found"):
		Game.unregister_command(&"notes.mark_found")


## notes.mark_found {note, where, day}: records where and when the local player found a note,
## once (the first find stands).
func _cmd_mark_found(args: Dictionary) -> Dictionary:
	var p: PlayerState = Game.local_player()
	var id := StringName(str(args.get("note", "")))
	if p == null or id == &"":
		return {"ok": false, "error": "no player or note"}
	if not p.notes_found.has(id):
		p.notes_found[id] = {"where": str(args.get("where", "")), "day": int(args.get("day", 1)), "order": p.notes_found.size()}
	return {"ok": true}


func _on_note_found(note_id: StringName) -> void:
	var day: int = Game.session.clock.day() if Game.session != null and Game.session.clock != null else 1
	Game.execute(&"notes.mark_found", {"note": String(note_id), "where": place_name(), "day": day})


func _grab_frame() -> void:
	_frame_t = 0.0
	# The headless (dummy) renderer has no frame to read: its saves get the plain plate.
	if DisplayServer.get_name() == "headless":
		return
	var tex: ViewportTexture = get_viewport().get_texture()
	var img: Image = tex.get_image() if tex != null else null
	if img != null and not img.is_empty():
		_last_frame = img


## After a save: the slot's thumbnail and where it was made, beside the save (LoadPanel reads them).
## Additive files the loader ignores; a save without them shows a plain plate.
func _write_thumb(slot: String, ok: bool) -> void:
	if not ok:
		return
	var dir: String = SaveSystem.slot_dir(slot)
	if not DirAccess.dir_exists_absolute(dir):
		return
	var f := FileAccess.open(dir.path_join(LoadPanel.CARD_FILE), FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"place": place_name(), "region": region_name()}))
		f.close()
	if _last_frame == null:
		_grab_frame()
	if _last_frame != null:
		LoadPanel.thumbnail(_last_frame).save_webp(dir.path_join(LoadPanel.THUMB_FILE), true, 0.8)


## The region the player stands in ("" before the world exists).
static func region_name() -> String:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null:
		return ""
	var at: Vector3 = (w.player as Node3D).global_position
	var tm: Object = w.get(&"terrain")
	var wd: WorldDef = tm.get(&"world") as WorldDef if tm != null else null
	if wd == null:
		return ""
	return str((wd.regions.get(wd.region_at(at.x, at.z), {}) as Dictionary).get("name", ""))


## Where the player stands, as a note's finding place: the building they're in, else the region.
static func place_name() -> String:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null:
		return ""
	var at: Vector3 = (w.player as Node3D).global_position
	var pois: Node = w.get(&"pois")
	if pois != null and pois.has_method(&"poi_at"):
		var inst: Object = pois.call(&"poi_at", at)
		if inst != null and inst.get(&"layout") != null and (inst.get(&"layout") as Object).get(&"def") != null:
			return str(((inst.get(&"layout") as Object).get(&"def") as Object).get(&"display_name"))
	var tm: Object = w.get(&"terrain")
	var wd: WorldDef = tm.get(&"world") as WorldDef if tm != null else null
	if wd != null:
		var rid: String = wd.region_at(at.x, at.z)
		var name_: String = str((wd.regions.get(rid, {}) as Dictionary).get("name", ""))
		if name_ != "":
			return "the woods of %s" % name_
	return "the woods"


## A note just picked up opens in the reader (it counts as read: inventory.read).
func _on_item_picked_up(owner_id: StringName, item_id: StringName, count: int) -> void:
	var p: PlayerState = Game.local_player()
	var d: ItemDef = Content.item(item_id)
	if p == null or owner_id != p.id or d == null:
		return
	if d.category != "note":
		feed_pickup(d.display_name, count)
	if d.category != "note" or d.note == &"":
		return
	var res: Dictionary = Game.execute(&"inventory.read", {"item": String(item_id)})
	if bool(res.get("ok", false)):
		show_note.call_deferred(d.note)


## The quiet line for what just went into the pack ("+2 Plant Fibre", bottom right), so a
## harvest or a pickup is never silent on screen. Repeats within a moment add up on one line.
func feed_pickup(item_name: String, count: int) -> void:
	if _pickups == null or count <= 0:
		return
	for c: Node in _pickups.get_children():
		var l: Label = c as Label
		if l != null and l.get_meta(&"item", "") == item_name and float(l.get_meta(&"t", 0.0)) > Time.get_ticks_msec() / 1000.0 - 2.0:
			l.set_meta(&"n", int(l.get_meta(&"n", 0)) + count)
			l.set_meta(&"t", Time.get_ticks_msec() / 1000.0)
			l.text = "+%d %s" % [int(l.get_meta(&"n")), item_name]
			l.modulate.a = 1.0
			return
	var line := Label.new()
	line.text = "+%d %s" % [count, item_name]
	line.set_meta(&"item", item_name)
	line.set_meta(&"n", count)
	line.set_meta(&"t", Time.get_ticks_msec() / 1000.0)
	line.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	line.add_theme_font_size_override(&"font_size", 17)
	line.add_theme_color_override(&"font_color", Color(0.9, 0.88, 0.8))
	line.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
	line.add_theme_constant_override(&"outline_size", 4)
	_pickups.add_child(line)
	while _pickups.get_child_count() > 5:
		_pickups.get_child(0).free()


func _fade_pickups(delta: float) -> void:
	if _pickups == null:
		return
	var now: float = Time.get_ticks_msec() / 1000.0
	for c: Node in _pickups.get_children():
		var l: Label = c as Label
		var age: float = now - float(l.get_meta(&"t", now))
		if age > 2.5:
			l.modulate.a -= delta * 1.5
			if l.modulate.a <= 0.0:
				l.queue_free()


## What the pickup feed shows now (tests).
func pickup_lines() -> PackedStringArray:
	var out: PackedStringArray = []
	for c: Node in _pickups.get_children() if _pickups != null else []:
		if not c.is_queued_for_deletion():
			out.append((c as Label).text)
	return out


func _build_overlay() -> void:
	_overlay = ColorRect.new()
	_overlay.color = Color(0, 0, 0, 0.0)
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	_overlay.theme = UiStyle.kit_theme()
	add_child(_overlay)
	var centre := CenterContainer.new()
	centre.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(centre)
	var v := VBoxContainer.new()
	v.custom_minimum_size = Vector2(760, 0)
	v.add_theme_constant_override(&"separation", 14)
	centre.add_child(v)
	_overlay_head = UiStyle.label("", &"HeadingLabel")
	_overlay_head.add_theme_font_size_override(&"font_size", 54)
	_overlay_head.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_overlay_head)
	_overlay_label = Label.new()
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.add_theme_font_size_override(&"font_size", 24)
	_overlay_label.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	v.add_child(_overlay_label)
	_overlay_note = UiStyle.label("", &"DimLabel")
	_overlay_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_note.add_theme_font_size_override(&"font_size", 19)
	v.add_child(_overlay_note)
	var row := CenterContainer.new()
	v.add_child(row)
	_death_button = Button.new()
	_death_button.text = "Wake up"
	_death_button.theme_type_variation = &"PrimaryButton"
	_death_button.custom_minimum_size = Vector2(280, 48)
	_death_button.visible = false
	_death_button.pressed.connect(_on_wake_after_death)
	row.add_child(_death_button)


## One tween drives the overlay at a time: a death's fade-in still running when Wake up is
## pressed must not fight the fade-out (the first-hour run saw the death screen linger).
func _overlay_tween() -> Tween:
	if _ov_tween != null and _ov_tween.is_valid():
		_ov_tween.kill()
	_ov_tween = create_tween()
	return _ov_tween


func show_sleep(on: bool) -> void:
	_overlay.visible = true
	_death_button.visible = false
	_overlay_head.text = ""
	_overlay_note.text = ""
	var tw: Tween = _overlay_tween()
	if on:
		_overlay_label.text = "You sleep."
		tw.tween_property(_overlay, "color:a", 0.96, 0.8)
	else:
		_overlay_label.text = ""
		tw.tween_property(_overlay, "color:a", 0.0, 1.2)
		tw.tween_callback(func() -> void: _overlay.visible = false)


## What the death screen says, as the tether's incident log would: [heading, the cause, the
## consequence and where you wake]. Pure, for tests.
static func death_text(cause: String, note: String, final: bool, day: int, deaths: int, has_bed: bool) -> Array[String]:
	var why: String = {"zombie": "The Hollowed got you.", "ashen": "The Ashen killed you.", "bleeding": "You bled out.", "cold": "The cold took you.",
		"starvation": "You starved.", "dehydration": "You died of thirst.", "fall": "You fell.", "tree": "The tree came down on you.",
		"turned": "The Bloom took you. You are one of them now.", "spores": "The spores filled your lungs."}.get(cause, "You died.")
	var log: String = "TETHER 4471  ·  DAY %d  ·  VITALS FLAT" % day
	var wake: String = "" if final else ("The Program will wake you at your bed." if has_bed else "The Program will wake you at the drop site.")
	var count: String = "" if deaths <= 1 else ("  Deaths logged: %d." % deaths)
	return [log, why, note + ((" " + wake) if wake != "" else "") + count]


func show_death(cause: String, note: String = "Your pack lies where you fell.", final: bool = false) -> void:
	_overlay.visible = true
	_overlay.color = Color(0.08, 0.0, 0.0, 0.0)
	var tw: Tween = _overlay_tween()
	tw.tween_property(_overlay, "color:a", 0.92, 2.0)
	var p: PlayerState = Game.local_player()
	var day: int = Game.session.clock.day() if Game.session != null and Game.session.clock != null else 1
	var t: Array[String] = death_text(cause, note, final, day, p.deaths if p != null else 1, p != null and p.has_spawn_point)
	_overlay_head.text = "SIGNAL LOST" if not final else "SIGNAL LOST  ·  FILE CLOSED"
	_overlay_head.tooltip_text = ""
	_overlay_label.text = t[1]
	_overlay_note.text = t[0] + "\n" + t[2]
	_final_death = final
	_death_button.text = "Return to the menu" if final else "Wake up"
	_death_button.visible = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _on_wake_after_death() -> void:
	_death_button.visible = false
	if _final_death:
		Game.quit_to_menu()
		return
	# The words go at once; the red fades behind them.
	_overlay_head.text = ""
	_overlay_label.text = ""
	_overlay_note.text = ""
	var tw: Tween = _overlay_tween()
	tw.tween_property(_overlay, "color:a", 0.0, 1.5)
	tw.tween_callback(func() -> void: _overlay.visible = false)
	if Game.world != null and Game.world.has_method(&"respawn"):
		Game.world.call(&"respawn")
