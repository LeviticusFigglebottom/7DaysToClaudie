class_name GameUI
extends CanvasLayer
## Screen-space UI: loading screen, minimal HUD, pause menu, and the modal stack shared with the
## diegetic UIs (salvage roll, field manual, tether) so mouse capture is handled in one place.
## The HUD stays minimal by design: prompt + transient feedback; vitals live on the tether.

var _loading: Control
var _loading_label: Label
var _loading_bar: ProgressBar
var _hud: Control
var _crosshair: Control
var _prompt: Label
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
	Events.player_damaged.connect(func(_id: StringName, amount: float, _src: Dictionary) -> void: _flash_damage(amount))
	Events.horde_night_warning.connect(func(_d: int, h: float) -> void: message("The ground is humming. %d hour%s." % [int(h), "" if int(h) == 1 else "s"], &"warning"))
	Events.horde_night_started.connect(func(_d: int) -> void: message("THE HUM HAS BEGUN.", &"danger"))
	Events.horde_night_ended.connect(func(_d: int, _r: Dictionary) -> void: message("Dawn. The Hollowed root into the soil.", &"info"))
	Events.game_saved.connect(func(slot: String, ok: bool) -> void: message(("Saved (%s)." % slot) if ok else "Save failed!", &"info" if ok else &"error"))
	Events.schematic_learned.connect(func(id: StringName) -> void: message("Learned: %s" % String(id).capitalize(), &"info"))


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
	var tip := Label.new()
	tip.text = "Night is darker than you think. Carry a light — and remember they see it too."
	tip.add_theme_color_override(&"font_color", Color(0.45, 0.47, 0.44))
	tip.anchor_top = 1.0
	tip.anchor_bottom = 1.0
	tip.position = Vector2(84, -80)
	_loading.add_child(tip)


func show_loading(text: String, progress: float) -> void:
	_loading.visible = true
	_hud.visible = false
	_loading_label.text = text
	_loading_bar.value = progress * 100.0


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
	var s: SurvivalStats = p.state.stats
	(_bars["health"] as ProgressBar).value = s.health
	(_bars["stamina"] as ProgressBar).value = s.stamina / maxf(1.0, s.max_stamina) * 100.0
	(_bars["fullness"] as ProgressBar).value = s.fullness
	(_bars["hydration"] as ProgressBar).value = s.hydration
	# Vitals fade unless something is off (minimal HUD).
	var concern: bool = s.health < 70.0 or s.stamina < s.max_stamina * 0.6 or s.fullness < 30.0 or s.hydration < 30.0
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


func _flash_damage(amount: float) -> void:
	_damage_flash = clampf(_damage_flash + amount / 30.0, 0.0, 1.0)


func message(text: String, kind: StringName = &"info") -> void:
	var l := Label.new()
	l.text = text
	l.add_theme_color_override(&"font_color", {&"info": Color(0.85, 0.85, 0.8), &"warning": Color(0.95, 0.8, 0.45), &"danger": Color(0.95, 0.35, 0.3), &"error": Color(1, 0.4, 0.4)}.get(kind, Color.WHITE))
	l.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override(&"outline_size", 4)
	_messages.add_child(l)
	var tw: Tween = l.create_tween()
	tw.tween_interval(4.0)
	tw.tween_property(l, "modulate:a", 0.0, 1.2)
	tw.tween_callback(l.queue_free)
	while _messages.get_child_count() > 6:
		_messages.get_child(0).queue_free()
		_messages.remove_child(_messages.get_child(0))


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
			["Load last save", func() -> void: Game.load_game(Game.current_slot)],
			["Graphics preset", _cycle_gfx], ["Quit to menu", func() -> void: Game.quit_to_menu()]]:
		var b := Button.new()
		b.text = spec[0]
		b.custom_minimum_size = Vector2(320, 40)
		b.pressed.connect(spec[1])
		box.add_child(b)


func toggle_pause() -> void:
	var on: bool = not _pause.visible
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
		pop_modal(&"pause")


func _cycle_gfx() -> void:
	var order: PackedStringArray = Settings.PRESET_ORDER
	Settings.set_graphics_preset(order[(order.find(Settings.graphics_preset) + 1) % order.size()])
	message("Graphics: %s" % Settings.graphics_preset, &"info")


# --- Diegetic UIs --------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	var w: Node = Game.world
	if w == null or not bool(w.get(&"is_ready")) or _pause.visible or _overlay.visible:
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
		"turned": "The Bloom took you. You are one of them now."}.get(cause, "You died.")
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
