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
var manual: FieldManual
var tether: Tether
var _final_death: bool = false
var _overlay: ColorRect
var _overlay_label: Label
var _death_button: Button
## Highest level reached since the last announcement (several can arrive in one award).
var _level_pending: int = 0
## Where recent hits came from (world positions + fade time), drawn as red wedges at the screen
## edge pointing at the attacker.
var _hits: Array[Dictionary] = []
var _wedges: Control
var _heart: AudioStreamPlayer


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
	_build_overlay()
	_build_pause()
	Events.player_status_message.connect(message)
	Events.player_damaged.connect(_on_player_damaged)
	# The Hum's warnings and its start are announced by HumDirector alone (with the forecast).
	Events.horde_night_ended.connect(_on_hum_ended)
	Events.game_saved.connect(func(_slot: String, ok: bool) -> void:
		# Autosaves announce themselves in their own line ("Rested. Progress saved.").
		if not ok or not Game.autosaving:
			message("Saved." if ok else "Save failed!", &"info" if ok else &"error"))
	Events.schematic_learned.connect(func(id: StringName) -> void: message("Learned: %s" % String(id).capitalize(), &"info"))
	Events.player_leveled.connect(_on_leveled)
	Events.supply_drop_incoming.connect(func(_id: StringName, _p: Vector3) -> void: message("A Program drone is overhead. Supplies are coming down.", &"level"))


## Dawn after a Hum: the run is saved (a night survived is the progress most worth keeping).
## Deferred: this handler connects before the Hum director's, which files the night's report and
## releases the survivors in its own handler of the same signal.
func _on_hum_ended(_day: int, _report: Dictionary) -> void:
	_autosave_after_hum.call_deferred()


func _autosave_after_hum() -> void:
	var lp: PlayerState = Game.local_player()
	if lp != null and lp.stats.alive and Game.autosave():
		message("Dawn. The Hollowed root into the soil. Progress saved.", &"info")
	else:
		message("Dawn. The Hollowed root into the soil.", &"info")


# --- Loading --------------------------------------------------------------------------------

func _build_loading() -> void:
	_loading = ColorRect.new()
	(_loading as ColorRect).color = Color(0.02, 0.022, 0.025)
	_loading.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_loading)
	var title := Label.new()
	title.text = "HOLLOWMERE"
	title.add_theme_font_size_override(&"font_size", 54)
	title.add_theme_color_override(&"font_color", Color(0.8, 0.78, 0.7))
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
	var tip := Label.new()
	tip.text = "Night is darker than you think. Carry a light — and remember they see it too."
	tip.add_theme_color_override(&"font_color", Color(0.45, 0.47, 0.44))
	tip.anchor_top = 1.0
	tip.anchor_bottom = 1.0
	tip.position = Vector2(84, -80)
	_loading.add_child(tip)


## `map`: the world's map (random worlds) and `marks` its region states (LoadingMap); a null map
## leaves the last one shown.
func show_loading(text: String, progress: float, map: Texture2D = null, marks: Dictionary = {}) -> void:
	_loading.visible = true
	_hud.visible = false
	_loading_label.text = text
	_loading_bar.value = progress * 100.0
	if map != null:
		_loading_map.set_map(map, marks)


## What the loading screen says now ("" once it is hidden).
func loading_text() -> String:
	return _loading_label.text if _loading != null and _loading.visible else ""


func hide_loading() -> void:
	_loading.visible = false
	_hud.visible = true


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
	_belt.add_theme_font_size_override(&"normal_font_size", 15)
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
	_hum_label = Label.new()
	_hum_label.anchor_left = 1.0
	_hum_label.anchor_right = 1.0
	_hum_label.position = Vector2(-360, 40)
	_hum_label.size = Vector2(320, 30)
	_hum_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_hum_label.add_theme_color_override(&"font_color", Color(0.75, 0.85, 0.75, 0.85))
	_hud.add_child(_hum_label)


static func _vignette_shader() -> Shader:
	var s := Shader.new()
	s.code = """
shader_type canvas_item;
uniform float damage = 0.0;
uniform float cold = 0.0;
uniform float low_health = 0.0;
void fragment() {
	vec2 d = UV - 0.5;
	float r = length(d * vec2(1.6, 1.0));
	float edge = smoothstep(0.35, 0.95, r);
	vec3 col = mix(vec3(0.0), vec3(0.45, 0.02, 0.02), clamp(damage + low_health * (0.6 + 0.4 * sin(TIME * 3.0)), 0.0, 1.0));
	col = mix(col, vec3(0.75, 0.85, 0.95), cold);
	float a = edge * clamp(damage * 0.9 + low_health * 0.6 + cold * 0.7, 0.0, 0.85);
	COLOR = vec4(col, a);
}
"""
	return s


func _process(delta: float) -> void:
	var w: Node = Game.world
	if w == null or w.get("player") == null or w.player == null:
		return
	var p: Player = w.player
	if p.interaction != null:
		_prompt.text = ("[E] " + p.interaction.prompt) if p.interaction.prompt != "" else ""
		var ht: float = p.interaction.hold_t / maxf(p.interaction.hold_needed, 0.001) if p.interaction.hold_needed > 0.0 else 0.0
		_hold.visible = ht > 0.0
		_hold.value = ht * 100.0
		var b: Node = w.get(&"building")
		var place_why: String = str(b.call(&"placement_hint")) if b != null else ""
		# Under the prompt: why a placement can't go, else the held tool's hint, else what holding
		# the cancel key on the target does (take a blueprint ghost down).
		_tool_hint.text = place_why if place_why != "" else (p.interaction.tool_hint if p.interaction.tool_hint != "" else p.interaction.alt_prompt)
	_update_belt(p.state, delta)
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
	elif hrs < 24.0:
		_hum_label.text = "Hum in %02d:%02d" % [int(hrs), int(fmod(hrs, 1.0) * 60.0)]
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
		if i == ps.equipped_slot and d != null:
			parts.append("[color=#f2e6c4][b]%d %s[/b][/color]" % [i + 1, name_])
		else:
			parts.append("[color=#9a9282]%d %s[/color]" % [i + 1, name_])
	var key: String = "   ".join(parts)
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
	l.add_theme_color_override(&"font_color", {&"info": Color(0.85, 0.85, 0.8), &"warning": Color(0.95, 0.8, 0.45), &"danger": Color(0.95, 0.35, 0.3), &"error": Color(1, 0.4, 0.4), &"level": Color(0.62, 0.95, 0.66)}.get(kind, Color.WHITE))
	l.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override(&"outline_size", 4)
	_messages.add_child(l)
	_fade_message(l)
	while _messages.get_child_count() > 6:
		_messages.get_child(0).queue_free()
		_messages.remove_child(_messages.get_child(0))


func _fade_message(l: Label) -> void:
	if l.has_meta(&"tween"):
		var prev: Tween = l.get_meta(&"tween") as Tween
		if prev != null and prev.is_valid():
			prev.kill()
	var tw: Tween = l.create_tween()
	tw.tween_interval(4.0)
	tw.tween_property(l, "modulate:a", 0.0, 1.2)
	tw.tween_callback(l.queue_free)
	l.set_meta(&"tween", tw)


func _on_leveled(player_id: StringName, level: int) -> void:
	if Game.session == null or player_id != Game.session.local_player_id:
		return
	if _level_pending == 0:
		_announce_level.call_deferred()
	_level_pending = maxi(_level_pending, level)


## One message and one chime however many levels a single award crossed.
func _announce_level() -> void:
	var p: PlayerState = Game.local_player()
	if p == null or _level_pending == 0:
		_level_pending = 0
		return
	var pts: int = p.progression.skill_points
	message("Level %d. %d point%s to spend — field manual (B), Record." % [_level_pending, pts, "" if pts == 1 else "s"], &"level")
	Audio.play_2d(&"ui/level_up", -4.0)
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
	add_child(_pause)
	var box := VBoxContainer.new()
	box.position = Vector2(100, 160)
	box.add_theme_constant_override(&"separation", 8)
	_pause.add_child(box)
	var title := Label.new()
	title.text = "PAUSED"
	title.add_theme_font_size_override(&"font_size", 40)
	box.add_child(title)
	for spec: Array in [["Resume", toggle_pause], ["Save", func() -> void: Game.save_game()],
			["Load last save", _confirm_load], ["Options", _open_options], ["Controls", _open_options.bind("Controls")],
			["Save and quit to menu", _save_and_quit], ["Quit without saving", _confirm_quit]]:
		var b := Button.new()
		b.text = spec[0]
		b.name = String(spec[0]).replace(" ", "_")
		b.custom_minimum_size = Vector2(320, 40)
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

func _unhandled_input(event: InputEvent) -> void:
	var w: Node = Game.world
	if w == null or not bool(w.get(&"is_ready")):
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
	manual.show_note(note_id)


func _build_overlay() -> void:
	_overlay = ColorRect.new()
	_overlay.color = Color(0, 0, 0, 0.0)
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	add_child(_overlay)
	_overlay_label = Label.new()
	_overlay_label.set_anchors_preset(Control.PRESET_CENTER)
	_overlay_label.position = Vector2(-300, -40)
	_overlay_label.size = Vector2(600, 80)
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.add_theme_font_size_override(&"font_size", 26)
	_overlay_label.add_theme_color_override(&"font_color", Color(0.85, 0.82, 0.75))
	_overlay.add_child(_overlay_label)
	_death_button = Button.new()
	_death_button.text = "Wake up"
	_death_button.set_anchors_preset(Control.PRESET_CENTER)
	_death_button.position = Vector2(-90, 60)
	_death_button.size = Vector2(180, 44)
	_death_button.visible = false
	_death_button.pressed.connect(_on_wake_after_death)
	_overlay.add_child(_death_button)


func show_sleep(on: bool) -> void:
	_overlay.visible = true
	_death_button.visible = false
	var tw: Tween = create_tween()
	if on:
		_overlay_label.text = "You sleep."
		tw.tween_property(_overlay, "color:a", 0.96, 0.8)
	else:
		_overlay_label.text = ""
		tw.tween_property(_overlay, "color:a", 0.0, 1.2)
		tw.tween_callback(func() -> void: _overlay.visible = false)


func show_death(cause: String, note: String = "Your pack lies where you fell.", final: bool = false) -> void:
	_overlay.visible = true
	_overlay.color = Color(0.08, 0.0, 0.0, 0.0)
	var tw: Tween = create_tween()
	tw.tween_property(_overlay, "color:a", 0.92, 2.0)
	var why: String = {"zombie": "The Hollowed got you.", "bleeding": "You bled out.", "cold": "The cold took you.",
		"starvation": "You starved.", "dehydration": "You died of thirst.", "fall": "You fell.", "tree": "The tree came down on you.",
		"turned": "The Bloom took you. You are one of them now.", "spores": "The spores filled your lungs."}.get(cause, "You died.")
	_overlay_label.text = why + "\n" + note
	_final_death = final
	_death_button.text = "Return to the menu" if final else _death_button.text
	_death_button.visible = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _on_wake_after_death() -> void:
	_death_button.visible = false
	if _final_death:
		Game.quit_to_menu()
		return
	var tw: Tween = create_tween()
	tw.tween_property(_overlay, "color:a", 0.0, 1.5)
	tw.tween_callback(func() -> void: _overlay.visible = false)
	if Game.world != null and Game.world.has_method(&"respawn"):
		Game.world.call(&"respawn")
