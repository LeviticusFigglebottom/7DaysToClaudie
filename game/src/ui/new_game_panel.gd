class_name NewGamePanel
extends PanelContainer
## New-game world settings (the 7 Days to Die "game options" screen): game mode, difficulty
## preset and every option of data/config/game_rules.json, grouped by category. Changing the
## preset resets the options to it; edits are kept as overrides on top of the preset.

signal closed

var _mode: OptionButton
var _preset: OptionButton
var _preset_info: Label
var _seed: LineEdit
var _rows: VBoxContainer
var _controls: Dictionary = {}
var _overrides: Dictionary = {}
var _presets: PackedStringArray = []
var _modes: PackedStringArray = ["survival", "slice"]
var _syncing: bool = false


func _ready() -> void:
	custom_minimum_size = Vector2(760, 640)
	var root := VBoxContainer.new()
	root.add_theme_constant_override(&"separation", 10)
	add_child(root)
	var title := Label.new()
	title.text = "NEW GAME — WORLD SETTINGS"
	title.add_theme_font_size_override(&"font_size", 22)
	root.add_child(title)
	var top := GridContainer.new()
	top.columns = 2
	root.add_child(top)
	_mode = OptionButton.new()
	for m: String in _modes:
		_mode.add_item(str((Content.config(&"game_modes").get("modes", {}) as Dictionary).get(m, {}).get("name", m)))
	_mode.item_selected.connect(func(_i: int) -> void: _reset_to_preset())
	_add_pair(top, "Mode", _mode)
	_preset = OptionButton.new()
	var presets: Dictionary = GameRules.schema().get("presets", {})
	for id: String in presets:
		_presets.append(id)
		_preset.add_item(str((presets[id] as Dictionary).get("label", id)))
	_preset.select(maxi(0, _presets.find("survivor")))
	_preset.item_selected.connect(func(_i: int) -> void: _reset_to_preset())
	_add_pair(top, "Difficulty", _preset)
	_seed = LineEdit.new()
	_seed.text = "4471"
	_seed.tooltip_text = "Scatter, loot rolls and Hum plans follow the seed; the map itself is handcrafted."
	_add_pair(top, "World seed", _seed)
	_preset_info = Label.new()
	_preset_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_preset_info.modulate = Color(0.8, 0.8, 0.75)
	root.add_child(_preset_info)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	root.add_child(scroll)
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_rows)
	_build_options()
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_END
	root.add_child(buttons)
	var back := Button.new()
	back.text = "Back"
	back.pressed.connect(func() -> void: closed.emit())
	buttons.add_child(back)
	var start := Button.new()
	start.text = "Start"
	start.custom_minimum_size = Vector2(160, 40)
	start.pressed.connect(_start)
	buttons.add_child(start)
	_reset_to_preset()


func _add_pair(grid: GridContainer, label: String, control: Control) -> void:
	var l := Label.new()
	l.text = label
	l.custom_minimum_size = Vector2(240, 0)
	grid.add_child(l)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(control)


func _build_options() -> void:
	var opts: Dictionary = GameRules.options()
	for cat: Variant in GameRules.schema().get("categories", []):
		var c: Dictionary = cat
		var header := Label.new()
		header.text = str(c.get("label", c.get("id", ""))).to_upper()
		header.add_theme_font_size_override(&"font_size", 16)
		header.modulate = Color(0.95, 0.75, 0.45)
		_rows.add_child(header)
		var grid := GridContainer.new()
		grid.columns = 2
		_rows.add_child(grid)
		for key: String in opts:
			var spec: Dictionary = opts[key]
			if str(spec.get("category", "")) != str(c.get("id", "")):
				continue
			var ctl: Control = _make_control(key, spec)
			_controls[key] = ctl
			_add_pair(grid, str(spec.get("label", key)), ctl)


func _make_control(key: String, spec: Dictionary) -> Control:
	match str(spec.get("type", "float")):
		"bool":
			var cb := CheckBox.new()
			cb.toggled.connect(func(on: bool) -> void: _changed(key, on))
			return cb
		"enum":
			var ob := OptionButton.new()
			for v: Variant in spec.get("values", []):
				ob.add_item(str(v).capitalize().replace("_", " "))
			ob.item_selected.connect(func(i: int) -> void: _changed(key, str((spec.get("values", []) as Array)[i])))
			return ob
	var sb := SpinBox.new()
	sb.min_value = float(spec.get("min", 0))
	sb.max_value = float(spec.get("max", 100))
	sb.step = float(spec.get("step", 1 if str(spec.get("type")) == "int" else 0.05))
	sb.value_changed.connect(func(v: float) -> void: _changed(key, int(v) if str(spec.get("type")) == "int" else v))
	return sb


func _resolved_base() -> GameRules:
	var mode: Dictionary = (Content.config(&"game_modes").get("modes", {}) as Dictionary).get(_modes[_mode.selected], {})
	return GameRules.resolve(mode.get("rules", {}), StringName(_presets[_preset.selected]), {})


func _reset_to_preset() -> void:
	_overrides.clear()
	var base: GameRules = _resolved_base()
	var presets: Dictionary = GameRules.schema().get("presets", {})
	_preset_info.text = str((presets.get(_presets[_preset.selected], {}) as Dictionary).get("description", ""))
	_syncing = true
	for key: String in _controls:
		_set_control(_controls[key], GameRules.options()[key], base.values.get(key))
	_syncing = false


func _set_control(ctl: Control, spec: Dictionary, v: Variant) -> void:
	if ctl is CheckBox:
		(ctl as CheckBox).button_pressed = bool(v)
	elif ctl is OptionButton:
		(ctl as OptionButton).select(maxi(0, (spec.get("values", []) as Array).find(str(v))))
	elif ctl is SpinBox:
		(ctl as SpinBox).value = float(v)


func _changed(key: String, v: Variant) -> void:
	if _syncing:
		return
	if _resolved_base().values.get(key) == v:
		_overrides.erase(key)
	else:
		_overrides[key] = v


func overrides() -> Dictionary:
	return _overrides.duplicate()


func _start() -> void:
	var opts: Dictionary = {"game_mode": _modes[_mode.selected], "preset": _presets[_preset.selected], "rules": overrides()}
	if _seed.text.strip_edges().is_valid_int():
		opts["seed"] = int(_seed.text.strip_edges())
	Game.start_new_game(opts)
