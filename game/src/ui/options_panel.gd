class_name OptionsPanel
extends PanelContainer
## Player options (autoload Settings): mouse, field of view, head bob, volumes per bus, graphics
## preset, fullscreen and vsync. Every change applies at once and is saved; used from the main
## menu and the pause menu.

signal closed()

const BUSES: PackedStringArray = ["Master", "SFX", "Ambience", "Music", "UI"]

var _grid: GridContainer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	custom_minimum_size = Vector2(620, 0)
	var box := VBoxContainer.new()
	box.add_theme_constant_override(&"separation", 10)
	add_child(box)
	var title := Label.new()
	title.text = "Options"
	title.add_theme_font_size_override(&"font_size", 28)
	box.add_child(title)
	_grid = GridContainer.new()
	_grid.columns = 2
	_grid.add_theme_constant_override(&"h_separation", 18)
	_grid.add_theme_constant_override(&"v_separation", 8)
	box.add_child(_grid)
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
	var gfx := OptionButton.new()
	for i: int in Settings.PRESET_ORDER.size():
		gfx.add_item(Settings.PRESET_ORDER[i].capitalize(), i)
	gfx.selected = maxi(0, Settings.PRESET_ORDER.find(Settings.graphics_preset))
	gfx.item_selected.connect(func(i: int) -> void: Settings.set_graphics_preset(Settings.PRESET_ORDER[i]))
	_row("Graphics", gfx)
	_check("Fullscreen", Settings.fullscreen, func(on: bool) -> void: Settings.set_display(on, Settings.vsync))
	_check("Vertical sync", Settings.vsync, func(on: bool) -> void: Settings.set_display(Settings.fullscreen, on))
	var back := Button.new()
	back.text = "Back"
	back.custom_minimum_size = Vector2(160, 40)
	back.pressed.connect(close)
	box.add_child(back)


func close() -> void:
	closed.emit()
	queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"pause") or event.is_action_pressed(&"cancel"):
		get_viewport().set_input_as_handled()
		close()


func _row(label: String, control: Control) -> void:
	var l := Label.new()
	l.text = label
	_grid.add_child(l)
	control.custom_minimum_size = Vector2(300, 0)
	_grid.add_child(control)


func _slider(label: String, lo: float, hi: float, step: float, value: float, on_change: Callable) -> void:
	var hb := HBoxContainer.new()
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = value
	s.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	s.custom_minimum_size = Vector2(230, 20)
	var v := Label.new()
	v.custom_minimum_size = Vector2(60, 0)
	v.text = _fmt(value, step)
	s.value_changed.connect(func(x: float) -> void:
		v.text = _fmt(x, step)
		on_change.call(x))
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
