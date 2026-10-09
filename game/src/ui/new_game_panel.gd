class_name NewGamePanel
extends PanelContainer
## New-game world settings (the 7 Days to Die "game options" screen), in two tabs:
## * Game: game mode, difficulty preset and every option of data/config/game_rules.json, grouped by
##   category. Changing the preset resets the options to it; edits are kept as overrides on top.
## * World (ADR-0031): the handcrafted Hollowmere Valley or a random world, with the random world's
##   preset, map seed and every option of data/config/world_gen.json, and "Generate preview", which
##   generates the world on a worker thread (cached, so starting it afterwards reuses it) and shows
##   its map: relief, water, roads, towns, places and the drop site.

signal closed

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
## The handcrafted map as it is today: the planned 7 x 7 km valley has one region built (D6,
## world.json `status`); the rest is coarse terrain. A test keeps it naming every built region.
const MAIN_MAP_LABEL: String = "Hollowmere Valley (handcrafted: Larch Hollow, 1 x 1 km)"

## Open on the World tab with a random world chosen (the main menu's Random World button).
var start_random: bool = false

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
var _tabs: TabContainer

# World tab.
var _map: OptionButton
var _wpreset: OptionButton
var _wpreset_info: Label
var _wseed: LineEdit
var _wpresets: PackedStringArray = []
var _wcontrols: Dictionary = {}
var _woverrides: Dictionary = {}
var _wbox: VBoxContainer
var _preview: TextureRect
var _preview_btn: Button
var _preview_status: Label
var _task: int = -1
var _task_result: Dictionary = {}
var _task_stage: String = ""
var _task_t: float = 0.0
var _task_key: String = ""
var _shown_key: String = ""
var _mutex := Mutex.new()


func _ready() -> void:
	custom_minimum_size = Vector2(1100, 760)
	# The kit theme (ADR-0063): an opaque dark canvas panel, like every other menu.
	theme = UiStyle.kit_theme()
	var root := VBoxContainer.new()
	root.add_theme_constant_override(&"separation", 10)
	add_child(root)
	root.add_child(UiStyle.label("NEW GAME — WORLD SETTINGS", &"HeadingLabel"))
	_tabs = TabContainer.new()
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(_tabs)
	_build_game_tab()
	_build_world_tab()
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_END
	root.add_child(buttons)
	var back := Button.new()
	back.text = "Back"
	back.pressed.connect(func() -> void: closed.emit())
	buttons.add_child(back)
	var start := Button.new()
	start.text = "Start"
	start.custom_minimum_size = Vector2(200, 44)
	start.theme_type_variation = &"PrimaryButton"
	start.pressed.connect(_start)
	buttons.add_child(start)
	_reset_to_preset()
	_reset_world_to_preset()
	if start_random:
		_map.select(1)
		_on_map_changed(1)
		_tabs.current_tab = 1


func _exit_tree() -> void:
	if _task >= 0:
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1


# --- Game tab --------------------------------------------------------------------------------------

func _build_game_tab() -> void:
	var tab := VBoxContainer.new()
	tab.name = "Game"
	tab.add_theme_constant_override(&"separation", 8)
	_tabs.add_child(tab)
	var top := GridContainer.new()
	top.columns = 2
	tab.add_child(top)
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
	# A fresh seed per new game (ADR-0030): buildings are dressed per run from it, so the default
	# run is a new one; type a seed to replay a run.
	_seed.text = str(100000 + randi() % 900000)
	_seed.tooltip_text = "Scatter, loot rolls, Hum plans and how every building is dressed (its rooms, wear and the houses on Larch Street) follow the run seed: a whole number or any text. A random world's land has its own map seed (World tab)."
	_add_pair(top, "Run seed", _seed)
	_preset_info = Label.new()
	_preset_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_preset_info.theme_type_variation = &"DimLabel"
	tab.add_child(_preset_info)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tab.add_child(scroll)
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_rows)
	_build_options()


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
		var grid: GridContainer = _section(_rows, str(c.get("label", c.get("id", ""))))
		for key: String in opts:
			var spec: Dictionary = opts[key]
			if str(spec.get("category", "")) != str(c.get("id", "")):
				continue
			var ctl: Control = _make_control(spec, _changed.bind(key))
			_controls[key] = ctl
			_add_pair(grid, str(spec.get("label", key)), ctl)


func _section(parent: Container, label: String) -> GridContainer:
	var header := Label.new()
	header.text = label.to_upper()
	header.theme_type_variation = &"SubheadingLabel"
	parent.add_child(header)
	var grid := GridContainer.new()
	grid.columns = 2
	parent.add_child(grid)
	return grid


## A control for one option spec (int/float spin box, enum option button, bool check box) that
## calls `on_change(value)` when the player edits it.
func _make_control(spec: Dictionary, on_change: Callable) -> Control:
	match str(spec.get("type", "float")):
		"bool":
			var cb := CheckBox.new()
			cb.toggled.connect(func(on: bool) -> void: on_change.call(on))
			return cb
		"enum":
			var ob := OptionButton.new()
			for v: Variant in spec.get("values", []):
				ob.add_item(str(v).capitalize().replace("_", " "))
			ob.item_selected.connect(func(i: int) -> void: on_change.call(str((spec.get("values", []) as Array)[i])))
			return ob
	var sb := SpinBox.new()
	sb.min_value = float(spec.get("min", 0))
	sb.max_value = float(spec.get("max", 100))
	sb.step = float(spec.get("step", 1 if str(spec.get("type")) == "int" else 0.05))
	sb.value_changed.connect(func(v: float) -> void: on_change.call(int(v) if str(spec.get("type")) == "int" else v))
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


func _changed(v: Variant, key: String) -> void:
	if _syncing:
		return
	if _resolved_base().values.get(key) == v:
		_overrides.erase(key)
	else:
		_overrides[key] = v


func overrides() -> Dictionary:
	return _overrides.duplicate()


# --- World tab -------------------------------------------------------------------------------------

func _build_world_tab() -> void:
	var tab := HBoxContainer.new()
	tab.name = "World"
	tab.add_theme_constant_override(&"separation", 16)
	_tabs.add_child(tab)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override(&"separation", 8)
	tab.add_child(left)
	var top := GridContainer.new()
	top.columns = 2
	left.add_child(top)
	_map = OptionButton.new()
	_map.add_item(MAIN_MAP_LABEL)
	_map.add_item("Random world")
	_map.item_selected.connect(_on_map_changed)
	_add_pair(top, "Map", _map)
	_wbox = VBoxContainer.new()
	_wbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_wbox.add_theme_constant_override(&"separation", 8)
	left.add_child(_wbox)
	var wtop := GridContainer.new()
	wtop.columns = 2
	_wbox.add_child(wtop)
	_wpreset = OptionButton.new()
	var ps: Dictionary = GenSettings.presets()
	for id: String in ps:
		_wpresets.append(id)
		_wpreset.add_item(str((ps[id] as Dictionary).get("label", id)))
	_wpreset.item_selected.connect(func(_i: int) -> void: _reset_world_to_preset())
	_add_pair(wtop, "World preset", _wpreset)
	var seed_row := HBoxContainer.new()
	_wseed = LineEdit.new()
	_wseed.text = _seed.text
	_wseed.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_wseed.tooltip_text = "The land, water, roads, towns and places follow the map seed: the same seed and settings always make the same world."
	_wseed.text_changed.connect(func(_t: String) -> void: _mark_stale())
	seed_row.add_child(_wseed)
	var dice := Button.new()
	dice.text = "New seed"
	dice.pressed.connect(func() -> void:
		_wseed.text = str(100000 + randi() % 900000)
		_mark_stale())
	seed_row.add_child(dice)
	_add_pair(wtop, "Map seed", seed_row)
	_wpreset_info = Label.new()
	_wpreset_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_wpreset_info.theme_type_variation = &"DimLabel"
	_wbox.add_child(_wpreset_info)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_wbox.add_child(scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(rows)
	var opts: Dictionary = GenSettings.options()
	for cat: Variant in GenSettings.schema().get("categories", []):
		var c: Dictionary = cat
		var grid: GridContainer = _section(rows, str(c.get("label", c.get("id", ""))))
		for key: String in opts:
			var spec: Dictionary = opts[key]
			if str(spec.get("category", "")) != str(c.get("id", "")):
				continue
			var ctl: Control = _make_control(spec, _world_changed.bind(key))
			_wcontrols[key] = ctl
			_add_pair(grid, str(spec.get("label", key)), ctl)
	# The map preview.
	var right := VBoxContainer.new()
	right.custom_minimum_size = Vector2(400, 0)
	right.add_theme_constant_override(&"separation", 8)
	tab.add_child(right)
	var frame := PanelContainer.new()
	frame.custom_minimum_size = Vector2(400, 400)
	right.add_child(frame)
	_preview = TextureRect.new()
	_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_preview.custom_minimum_size = Vector2(400, 400)
	frame.add_child(_preview)
	_preview_btn = Button.new()
	_preview_btn.text = "Generate preview"
	_preview_btn.pressed.connect(_generate_preview)
	right.add_child(_preview_btn)
	_preview_status = Label.new()
	_preview_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_preview_status.theme_type_variation = &"DimLabel"
	_preview_status.custom_minimum_size = Vector2(400, 0)
	right.add_child(_preview_status)
	_on_map_changed(0)


func _on_map_changed(i: int) -> void:
	var random: bool = i == 1
	_set_enabled(_wbox, random)
	_preview_btn.disabled = not random or _task >= 0
	if not random:
		_preview.texture = null
		_preview_status.text = "The handcrafted map: Larch Hollow, Pell's Crossing and the Tamsin valley. Its land is the same every run; the run seed dresses its buildings."
	else:
		_preview_status.text = "Generate a preview to see the land, rivers, roads, towns and places before you start. Larger worlds take longer to shape the first time they load (they are cached after)."


static func _set_enabled(node: Node, on: bool) -> void:
	for c: Node in node.get_children():
		if c is BaseButton:
			(c as BaseButton).disabled = not on
		elif c is LineEdit:
			(c as LineEdit).editable = on
		elif c is SpinBox:
			(c as SpinBox).editable = on
		_set_enabled(c, on)
	if node is CanvasItem:
		(node as CanvasItem).modulate.a = 1.0 if on else 0.45


func _reset_world_to_preset() -> void:
	_woverrides.clear()
	var id: String = _wpresets[maxi(0, _wpreset.selected)]
	_wpreset_info.text = str((GenSettings.presets().get(id, {}) as Dictionary).get("description", ""))
	var base: RefCounted = GenSettings.resolve(StringName(id), {}, 0)
	var vals: Dictionary = base.get(&"values")
	_syncing = true
	for key: String in _wcontrols:
		_set_control(_wcontrols[key], GenSettings.options()[key], vals.get(key))
	_syncing = false
	_mark_stale()


func _world_changed(v: Variant, key: String) -> void:
	if _syncing:
		return
	var base: Dictionary = GenSettings.resolve(StringName(_wpresets[maxi(0, _wpreset.selected)]), {}, 0).get(&"values")
	if base.get(key) == v:
		_woverrides.erase(key)
	else:
		_woverrides[key] = v
	_mark_stale()


## The run seed typed on the Game tab: a whole number is itself and any other text hashes as the
## map seed does (it used to become the session's default, 4471, silently); an empty field rolls
## a fresh run (ADR-0030).
static func run_seed_from_text(text: String) -> int:
	var t: String = text.strip_edges()
	if t == "":
		return fresh_seed()
	return int(t) if t.is_valid_int() else Ids.hash31(t)


## A fresh six-digit run seed, as the Game tab offers (ADR-0030: a new run per new game).
static func fresh_seed() -> int:
	return 100000 + randi() % 900000


## The random world these controls describe.
func world_settings() -> RefCounted:
	var seed_text: String = _wseed.text.strip_edges()
	var map_seed: int = int(seed_text) if seed_text.is_valid_int() else Ids.hash31(seed_text)
	return GenSettings.resolve(StringName(_wpresets[maxi(0, _wpreset.selected)]), _woverrides, map_seed)


func _mark_stale() -> void:
	if _preview == null or _map == null or _map.selected != 1:
		return
	if _shown_key != "" and _shown_key != str(world_settings().call(&"key")):
		_preview.modulate = Color(1, 1, 1, 0.35)
		_preview_status.text = "Settings changed: generate the preview again to see this world."


func _generate_preview() -> void:
	if _task >= 0:
		return
	var settings: RefCounted = world_settings()
	_task_key = str(settings.call(&"key"))
	_task_result = {}
	_preview_btn.disabled = true
	_preview_status.text = "Generating…"
	_task = WorkerThreadPool.add_task(func() -> void:
		var res: Dictionary = Worlds.ensure(settings, func(s: String, t: float) -> void:
			_mutex.lock()
			_task_stage = s
			_task_t = t
			_mutex.unlock(), false)
		_mutex.lock()
		_task_result = res
		_mutex.unlock(), true, "world preview")
	set_process(true)


func _process(_delta: float) -> void:
	if _task < 0:
		return
	if not WorkerThreadPool.is_task_completed(_task):
		_mutex.lock()
		_preview_status.text = "Generating… %s (%d%%)" % [_task_stage, int(_task_t * 100.0)]
		_mutex.unlock()
		return
	WorkerThreadPool.wait_for_task_completion(_task)
	_task = -1
	_preview_btn.disabled = _map.selected != 1
	var res: Dictionary = _task_result
	if not bool(res.get("ok", false)):
		_preview_status.text = "Could not generate the world: %s" % res.get("error", "?")
		return
	var img := Image.load_from_file(ProjectSettings.globalize_path(str(res["dir"]).path_join("map.png")))
	if img != null and not img.is_empty():
		_preview.texture = ImageTexture.create_from_image(img)
		_preview.modulate = Color(1, 1, 1, 1)
	_shown_key = _task_key
	_preview_status.text = _describe(str(res["dir"]), bool(res.get("generated", false)), int(res.get("ms", 0)))


## One paragraph about a generated world: its towns, places, water and roads.
func _describe(dir: String, generated: bool, ms: int) -> String:
	var j := JSON.new()
	if j.parse(FileAccess.get_file_as_string(dir.path_join("world.json"))) != OK or not j.data is Dictionary:
		return ""
	var w: Dictionary = j.data
	var gen: Dictionary = w.get("generator", {})
	var towns: PackedStringArray = []
	for t: Variant in gen.get("towns", []):
		towns.append("%s (%s, %d lots)" % [t["name"], t["kind"], int(t["lots"])])
	return "%s — %s in %.1f s.\nTowns: %s.\n%d places off the roads, %d rivers, %d lakes, %d roads. The yellow ring is where you are dropped." % [
		str(w.get("name", "")), "generated" if generated else "read from the cache", ms / 1000.0,
		", ".join(towns) if not towns.is_empty() else "none", (gen.get("places", []) as Array).size(), (w.get("rivers", []) as Array).size(),
		(w.get("lakes", []) as Array).size(), (w.get("roads", []) as Array).size()]


func _start() -> void:
	var opts: Dictionary = {"game_mode": _modes[_mode.selected], "preset": _presets[_preset.selected], "rules": overrides()}
	opts["seed"] = run_seed_from_text(_seed.text)
	if _map.selected == 1:
		opts["world_gen"] = world_settings().call(&"to_dict")
	Game.start_new_game(opts)
