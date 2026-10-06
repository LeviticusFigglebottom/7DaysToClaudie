extends Control
## Boot scene + main menu.
##
## Command line (after `--`):  --new-game [--mode slice|survival] [--seed N] [--skip-intro]
##                             [--preset drifter|survivor|remanded|hollowed|rooted]
##                             [--rule key=value ...]   (any data/config/game_rules.json option)
##                             [--world random [--world-seed N] [--world-preset id]
##                              [--world-set key=value ...]]   (data/config/world_gen.json, ADR-0031)
##                             --load <slot>    --continue
## e.g. godot --path game -- --new-game --mode slice --skip-intro
##      godot --path game -- --new-game --world random --world-seed 77 --world-set size=3

@onready var _list: VBoxContainer = %Buttons
@onready var _status: Label = %Status


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if _handle_cli(args):
		return
	_build_menu()
	_show_notices()


func _handle_cli(args: PackedStringArray) -> bool:
	if args.has("--new-game"):
		var opts: Dictionary = {"game_mode": _arg_value(args, "--mode", "survival")}
		var seed_s: String = _arg_value(args, "--seed", "")
		if seed_s != "":
			opts["seed"] = int(seed_s)
		opts["skip_intro"] = args.has("--skip-intro")
		opts["preset"] = _arg_value(args, "--preset", "survivor")
		var rules: Dictionary = {}
		for i: int in args.size() - 1:
			if args[i] == "--rule" and args[i + 1].contains("="):
				var kv: PackedStringArray = args[i + 1].split("=", true, 1)
				rules[kv[0]] = kv[1]
		opts["rules"] = rules
		if _arg_value(args, "--world", "main") == "random":
			opts["world_gen"] = world_gen_from_args(args, int(opts.get("seed", randi() % 1000000)))
		Game.start_new_game.call_deferred(opts)
		return true
	# A load that fails leaves the menu up with the reason, not a blank screen.
	if args.has("--load"):
		_build_menu()
		_load.call_deferred(_arg_value(args, "--load", "run1"))
		return true
	if args.has("--continue"):
		var slots: Array[Dictionary] = SaveSystem.list_slots()
		if not slots.is_empty():
			_build_menu()
			_load.call_deferred(str(slots[0]["slot"]))
			return true
	return false


## A random world's settings from the command line: --world-seed, --world-preset, --world-set k=v.
static func world_gen_from_args(args: PackedStringArray, default_seed: int) -> Dictionary:
	var overrides: Dictionary = {}
	for i: int in args.size() - 1:
		if args[i] == "--world-set" and args[i + 1].contains("="):
			var kv: PackedStringArray = args[i + 1].split("=", true, 1)
			overrides[kv[0]] = kv[1]
	var map_seed: int = int(_arg_value(args, "--world-seed", str(default_seed)))
	var settings: RefCounted = (load("res://src/worldgen/rwg/world_gen_settings.gd") as GDScript).call(&"resolve",
		StringName(_arg_value(args, "--world-preset", "standard")), overrides, map_seed)
	return settings.call(&"to_dict")


static func _arg_value(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default


func _build_menu() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	var slots: Array[Dictionary] = SaveSystem.list_slots()
	if not slots.is_empty():
		_add_button("Continue (Day %d)" % int(slots[0].get("day", 1)), _load.bind(str(slots[0]["slot"])))
	_add_button("New Game…", _open_new_game)
	_add_button("New Game — Vertical Slice (Hum on night 3)", func() -> void: Game.start_new_game({"game_mode": "slice"}))
	_add_button("Random World…", _open_new_game.bind(true))
	for s: Dictionary in slots:
		var label: String = "Load %s — Day %d" % [str(s.get("slot", "?")).capitalize(), int(s.get("day", 1))]
		if str(s.get("preset", "")) != "":
			label += " · %s" % str(s["preset"]).capitalize()
		if str(s.get("world_mode", "")) == "random":
			label += " · Random world"
		_add_button(label, _load.bind(str(s["slot"])))
	_add_button("Options…", _open_options)
	_add_button("Quit", func() -> void: get_tree().quit())
	_status.text = "Hollowmere %s  ·  Godot %s" % [ProjectSettings.get_setting("application/config/version"), Engine.get_version_info()["string"]]


## The Godot version the project is pinned to (tools/versions.env GODOT_VERSION; a test keeps the
## two in step). Exports always carry it; an editor of another version may import and run the
## project differently (the first playtest ran 4.7.1).
const PINNED_GODOT: String = "4.7.2"


## Problems a player should know about before they play, shown on the menu (ADR-0036):
## * no generated assets (built by `make assets` on Linux and shipped in the packaged builds,
##   never committed): the world is procedural stand-ins, which is not what the game looks like;
## * the project opened in a Godot editor of another version than the pinned one.
static func startup_notices(share: float, engine_version: String) -> PackedStringArray:
	var out: PackedStringArray = []
	if share <= 0.0:
		out.append("Placeholder world: the generated models, textures and sounds are missing, so "
			+ "everything is drawn as simple stand-in shapes (no grass, no textures). To play the real "
			+ "game, download a packaged build (they include the assets), or on Linux run "
			+ "\"make setup assets\" and reopen the project. See docs/BUILDS.md.")
	elif share < 1.0:
		out.append(("Incomplete assets: only %d%% of the generated models were found, so some of the "
			+ "world is drawn as stand-in shapes. Re-run \"make assets\" (see docs/BUILDS.md).") % roundi(share * 100.0))
	if engine_version != PINNED_GODOT:
		out.append(("Godot %s: this project is made for Godot %s. Open it with Godot %s (or play a "
			+ "packaged build): other versions can import, render or crash differently.") % [engine_version, PINNED_GODOT, PINNED_GODOT])
	return out


## "major.minor.patch" of the running engine.
static func engine_version() -> String:
	var v: Dictionary = Engine.get_version_info()
	return "%d.%d.%d" % [int(v["major"]), int(v["minor"]), int(v["patch"])]


func _show_notices() -> void:
	var notices: PackedStringArray = startup_notices(ModelLibrary.generated_share(Content), engine_version())
	if notices.is_empty():
		return
	var panel := PanelContainer.new()
	panel.name = "Notices"
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.16, 0.1, 0.06, 0.92)
	sb.border_color = Color(0.85, 0.6, 0.25)
	sb.set_border_width_all(2)
	sb.set_content_margin_all(16)
	panel.add_theme_stylebox_override(&"panel", sb)
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(520, 0)
	label.add_theme_color_override(&"font_color", Color(0.95, 0.85, 0.65))
	label.text = "\n\n".join(notices)
	panel.add_child(label)
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	panel.position = Vector2(get_viewport_rect().size.x - 520 - 32 - 40, 240)
	for n: String in notices:
		Log.warn("startup", n)


## World settings screen (difficulty preset + every game rule) before a new game; `random` opens it
## on its World tab with a random world chosen (ADR-0031).
func _open_new_game(random: bool = false) -> void:
	var panel := NewGamePanel.new()
	panel.start_random = random
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	add_child(panel)
	panel.position = (get_viewport_rect().size - panel.custom_minimum_size) * 0.5
	_list.visible = false
	_set_title_visible(false)
	panel.closed.connect(func() -> void:
		panel.queue_free()
		_list.visible = true
		_set_title_visible(true))


## The big title would show beside (and under) the wide New Game panel.
func _set_title_visible(on: bool) -> void:
	for n: String in ["Title", "Subtitle", "Notices"]:
		var c: CanvasItem = get_node_or_null(n) as CanvasItem
		if c != null:
			c.visible = on


## Loads a slot; a damaged or newer save says why here instead of failing silently.
func _load(slot: String) -> void:
	if not Game.load_game(slot):
		_status.text = "Could not load %s: %s." % [slot, SaveSystem.last_error]


func _open_options() -> void:
	var panel := OptionsPanel.new()
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.position = (get_viewport_rect().size - Vector2(680, 660)) * 0.5
	_list.visible = false
	panel.closed.connect(func() -> void: _list.visible = true)


func _add_button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(420, 44)
	b.pressed.connect(cb)
	_list.add_child(b)
	return b
