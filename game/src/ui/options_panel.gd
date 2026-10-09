class_name OptionsPanel
extends PanelContainer
## Player options (autoload Settings), in three tabs; used from the main menu and the pause menu.
## * General: mouse, field of view, head bob, volumes per bus, brightness, fullscreen, vsync.
## * Graphics (ADR-0037): a preset, then any feature on top of it (render scale and upscaler,
##   anti-aliasing, GI, fog, AO, reflections, shadows, view distance, tree detail, grass). Picking a
##   preset drops the changes made on top of the old one.
## * Controls (ADR-0037): every player action and its key; click one, press the new key or mouse
##   button (Escape cancels). Gamepad bindings are kept.
## Every change applies at once and is saved.

signal closed()

const BUSES: PackedStringArray = ["Master", "SFX", "Ambience", "Music", "UI"]
## Player actions on the controls tab, in reading order, with their names. Debug keys stay out.
const ACTIONS: Array = [
	["move_forward", "Move forward"], ["move_back", "Move back"], ["move_left", "Move left"], ["move_right", "Move right"],
	["sprint", "Sprint"], ["crouch", "Crouch"], ["jump", "Jump / vault"], ["interact", "Interact (hold to search)"],
	["attack", "Use / attack / place"], ["block", "Block / consume"], ["aim", "Aim (guns)"], ["reload", "Reload"], ["light", "Light"], ["inspect", "Inspect held item"], ["drop", "Drop"],
	["companion_order", "Companion: follow / stay"],
	["inventory", "Salvage roll (inventory)"], ["guidebook", "Field manual"], ["tracker", "Tether"], ["map", "Map"],
	["rotate_piece", "Rotate piece"], ["build_mode_toggle", "Log pose"], ["cancel", "Cancel"],
	["toolbelt_1", "Toolbelt 1"], ["toolbelt_2", "Toolbelt 2"], ["toolbelt_3", "Toolbelt 3"],
	["toolbelt_4", "Toolbelt 4"], ["toolbelt_5", "Toolbelt 5"], ["toolbelt_6", "Toolbelt 6"],
	["toolbelt_next", "Next tool"], ["toolbelt_prev", "Previous tool"],
	["quicksave", "Quicksave"], ["quickload", "Quickload"], ["screenshot", "Screenshot"], ["pause", "Pause"],
]
const TABS: PackedStringArray = ["General", "Graphics", "Controls"]

## Tab shown first ("General", "Graphics" or "Controls"); set before adding the panel.
var open_tab: String = "General"
var _tabs: TabContainer
var _grid: GridContainer
var _graphics_page: ScrollContainer
var _controls_page: ScrollContainer
## The action waiting for a key on the controls tab ("" = none), and its button.
var _listening: String = ""


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = UiStyle.kit_theme()
	custom_minimum_size = Vector2(760, 0)
	var box := VBoxContainer.new()
	box.add_theme_constant_override(&"separation", 10)
	add_child(box)
	box.add_child(UiStyle.label("OPTIONS", &"HeadingLabel"))
	_tabs = TabContainer.new()
	_tabs.custom_minimum_size = Vector2(720, 600)
	box.add_child(_tabs)
	_tabs.add_child(_page("General"))
	_general()
	_graphics_page = _page("Graphics")
	_tabs.add_child(_graphics_page)
	_build_graphics()
	_controls_page = _page("Controls")
	_tabs.add_child(_controls_page)
	_build_controls()
	_tabs.current_tab = maxi(0, TABS.find(open_tab))
	var back := Button.new()
	back.text = "Back"
	back.custom_minimum_size = Vector2(160, 40)
	back.pressed.connect(close)
	box.add_child(back)


func close() -> void:
	closed.emit()
	queue_free()


func _input(event: InputEvent) -> void:
	if _listening == "" or not event.is_pressed() or event.is_echo():
		return
	if not (event is InputEventKey or event is InputEventMouseButton):
		return
	get_viewport().set_input_as_handled()
	if event is InputEventKey and (event as InputEventKey).physical_keycode == KEY_ESCAPE:
		_listening = ""
		_build_controls()
		return
	Settings.bind_primary(_listening, event)
	_listening = ""
	_build_controls.call_deferred()


func _unhandled_input(event: InputEvent) -> void:
	if _listening != "":
		return
	if event.is_action_pressed(&"pause") or event.is_action_pressed(&"cancel"):
		get_viewport().set_input_as_handled()
		close()


# --- Pages ---------------------------------------------------------------------------------

func _page(page_name: String) -> ScrollContainer:
	var sc := ScrollContainer.new()
	sc.name = page_name
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var g := GridContainer.new()
	g.columns = 2
	g.add_theme_constant_override(&"h_separation", 18)
	g.add_theme_constant_override(&"v_separation", 8)
	g.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sc.add_child(g)
	return sc


func _use(page: ScrollContainer) -> void:
	_grid = page.get_child(0) as GridContainer
	for c: Node in _grid.get_children():
		c.queue_free()


func _general() -> void:
	_grid = (_tabs.get_child(0) as ScrollContainer).get_child(0) as GridContainer
	_slider("Mouse sensitivity", 0.0005, 0.006, 0.0001, Settings.mouse_sensitivity, func(v: float) -> void:
		Settings.mouse_sensitivity = v
		Settings.save())
	_check("Invert mouse Y", Settings.invert_y, func(on: bool) -> void:
		Settings.invert_y = on
		Settings.save())
	_slider("Field of view", 60.0, 100.0, 1.0, Settings.fov, func(v: float) -> void:
		Settings.fov = v
		Settings.save())
	_slider("Head bob", 0.0, 1.0, 0.05, Settings.head_bob, func(v: float) -> void:
		Settings.head_bob = v
		Settings.save())
	for bus: String in BUSES:
		_slider("%s volume" % bus, 0.0, 1.0, 0.05, float(Settings.volumes.get(bus, 1.0)), func(v: float) -> void: Settings.set_volume(bus, v))
	_slider("Brightness", 0.7, 1.5, 0.05, Settings.brightness, func(v: float) -> void:
		Settings.brightness = v
		Settings.save())
	var ui := OptionButton.new()
	ui.add_item("Auto (follows the window)", 0)
	for i: int in UiStyle.SCALES.size():
		ui.add_item("%d%%" % roundi(UiStyle.SCALES[i] * 100.0), i + 1)
	ui.selected = 0 if Settings.ui_scale <= 0.0 else maxi(0, UiStyle.SCALES.find(Settings.ui_scale) + 1)
	ui.item_selected.connect(func(i: int) -> void: Settings.set_ui_scale(0.0 if i == 0 else UiStyle.SCALES[i - 1]))
	_row("Interface size", ui)
	var bd := OptionButton.new()
	var bd_modes: PackedStringArray = ["moving", "still", "off"]
	for m: String in ["Moving (stops if the menu runs slow)", "Still", "Off"]:
		bd.add_item(m)
	bd.selected = maxi(0, bd_modes.find(Settings.menu_backdrop))
	bd.item_selected.connect(func(i: int) -> void:
		Settings.menu_backdrop = bd_modes[i]
		Settings.save())
	_row("Menu backdrop", bd)
	_check("Sound captions ([radio crackle], [a low hum])", Settings.sound_captions, func(on: bool) -> void:
		Settings.sound_captions = on
		Settings.save())
	_check("Fullscreen", Settings.fullscreen, func(on: bool) -> void: Settings.set_display(on, Settings.vsync))
	_check("Vertical sync", Settings.vsync, func(on: bool) -> void: Settings.set_display(Settings.fullscreen, on))


func _build_graphics() -> void:
	_use(_graphics_page)
	var preset := OptionButton.new()
	for i: int in Settings.PRESET_ORDER.size():
		preset.add_item(Settings.PRESET_ORDER[i].capitalize(), i)
	preset.selected = maxi(0, Settings.PRESET_ORDER.find(Settings.graphics_preset))
	preset.item_selected.connect(func(i: int) -> void:
		Settings.set_graphics_preset(Settings.PRESET_ORDER[i])
		_build_graphics.call_deferred())
	var custom: int = Settings.graphics_overrides().size()
	_row("Preset" + (" (%d changed)" % custom if custom > 0 else ""), preset)
	_gfx_slider("Render scale", "render_scale", 0.5, 1.0, 0.05)
	_gfx_choice("Upscaler", "upscaler", [["bilinear", "Bilinear"], ["fsr", "FSR 1"], ["fsr2", "FSR 2 (sharper, own AA)"]])
	_gfx_check("Temporal anti-aliasing", "taa")
	_gfx_check("Global illumination (SDFGI)", "sdfgi")
	_gfx_check("Volumetric fog", "volumetric_fog")
	_gfx_check("Ambient occlusion", "ssao")
	_gfx_check("Indirect light (SSIL)", "ssil")
	_gfx_check("Screen-space reflections", "ssr")
	_gfx_choice("Shadow resolution", "directional_shadow_size", [[2048, "Low"], [4096, "High"], [8192, "Ultra"]],
		func(v: Variant) -> void: Settings.set_graphics_override("positional_shadow_atlas", v))
	_gfx_choice("Shadow softness", "shadow_filter", [[0, "Hard"], [1, "Very low"], [2, "Low"], [3, "Medium"], [4, "High"], [5, "Ultra"]])
	_gfx_slider("Shadow distance", "shadow_distance", 40.0, 200.0, 10.0)
	_gfx_slider("View distance", "view_distance", 500.0, 2500.0, 100.0)
	_gfx_slider("Tree detail distance (under 50%: no full-detail trees)", "tree_lod_scale", 0.3, 1.5, 0.05)
	_gfx_slider("Object draw distance", "object_distance", 50.0, 300.0, 10.0)
	_gfx_slider("Grass density", "grass_density", 0.0, 1.0, 0.05)
	_gfx_slider("Grass distance", "grass_distance", 20.0, 90.0, 5.0)
	var note := Label.new()
	note.text = "Grass and tree changes show as the forest around you rebuilds."
	note.theme_type_variation = &"DimLabel"
	_grid.add_child(note)
	_grid.add_child(Control.new())


func _build_controls() -> void:
	_use(_controls_page)
	for a: Array in ACTIONS:
		var action: String = a[0]
		if not InputMap.has_action(action):
			continue
		var b := Button.new()
		var specs: Array = Settings.bindings(action)
		var names: PackedStringArray = []
		for sp: Variant in specs:
			var d: Dictionary = sp if sp is Dictionary else {}
			if d.has("key") or d.has("mouse"):
				names.append(Settings.describe(d))
		b.text = "Press a key…" if _listening == action else (" / ".join(names) if not names.is_empty() else "—")
		b.pressed.connect(func() -> void:
			_listening = action
			b.text = "Press a key…")
		_row(str(a[1]), b)
	var reset := Button.new()
	reset.text = "Reset all to defaults"
	reset.pressed.connect(func() -> void:
		Settings.reset_bindings()
		_build_controls.call_deferred())
	_row("", reset)


# --- Rows ----------------------------------------------------------------------------------

func _gfx_slider(label: String, key: String, lo: float, hi: float, step: float) -> void:
	_slider(label, lo, hi, step, float(Settings.gfx(key, lo)), func(v: float) -> void: Settings.set_graphics_override(key, v))


func _gfx_check(label: String, key: String) -> void:
	_check(label, bool(Settings.gfx(key, false)), func(on: bool) -> void: Settings.set_graphics_override(key, on))


## choices: [[value, label]...]; also_set runs with the chosen value too (a paired setting).
func _gfx_choice(label: String, key: String, choices: Array, also_set: Callable = Callable()) -> void:
	var ob := OptionButton.new()
	var cur: Variant = Settings.gfx(key, choices[0][0])
	for i: int in choices.size():
		ob.add_item(str(choices[i][1]), i)
		if str(choices[i][0]) == str(cur):
			ob.selected = i
	ob.item_selected.connect(func(i: int) -> void:
		Settings.set_graphics_override(key, choices[i][0])
		if also_set.is_valid():
			also_set.call(choices[i][0]))
	_row(label, ob)


func _row(label: String, control: Control) -> void:
	var l := Label.new()
	l.text = label
	_grid.add_child(l)
	control.custom_minimum_size = Vector2(320, 0)
	_grid.add_child(control)


func _slider(label: String, lo: float, hi: float, step: float, value: float, on_change: Callable) -> void:
	var hb := HBoxContainer.new()
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = value
	s.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	s.custom_minimum_size = Vector2(240, 20)
	var v := Label.new()
	v.custom_minimum_size = Vector2(60, 0)
	v.text = _fmt(value, step)
	# Sliders apply when let go (or on a click/key step), not on every pixel of a drag: a graphics
	# change rebuilds viewport and environment state.
	s.value_changed.connect(func(x: float) -> void: v.text = _fmt(x, step))
	s.drag_ended.connect(func(changed: bool) -> void:
		if changed:
			on_change.call(s.value))
	s.gui_input.connect(func(e: InputEvent) -> void:
		if (e is InputEventKey or (e is InputEventMouseButton and (e as InputEventMouseButton).button_index > 3)) and e.is_pressed():
			on_change.call.call_deferred(s.value))
	hb.add_child(s)
	hb.add_child(v)
	_row(label, hb)


func _check(label: String, on: bool, on_toggle: Callable) -> void:
	var c := CheckBox.new()
	c.button_pressed = on
	c.toggled.connect(func(x: bool) -> void: on_toggle.call(x))
	_row(label, c)


static func _fmt(x: float, step: float) -> String:
	if step >= 1.0:
		return "%d" % int(round(x))
	if step < 0.001:
		return "%.4f" % x
	return "%d%%" % int(round(x * 100.0))
