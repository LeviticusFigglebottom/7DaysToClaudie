extends Control
## Boot scene + main menu.
##
## Command line (after `--`):  --new-game [--mode slice|survival] [--seed N|text] [--skip-intro]
##                             (no --seed: the slice's demo seed, otherwise a fresh one)
##                             [--preset drifter|survivor|remanded|hollowed|rooted]
##                             [--rule key=value ...]   (any data/config/game_rules.json option)
##                             [--world random [--world-seed N] [--world-preset id]
##                              [--world-set key=value ...]]   (data/config/world_gen.json, ADR-0031)
##                             --load <slot>    --continue
## e.g. godot --path game -- --new-game --mode slice --skip-intro
##      godot --path game -- --new-game --world random --world-seed 77 --world-set size=3

## The menu's Vertical Slice button is the curated demo run, always on this run seed (the one the QA
## screenshots and the smoke test play, GameSession's default); every other new game rolls a
## fresh run seed (ADR-0030).
const SLICE_DEMO_SEED: int = 4471

@onready var _list: VBoxContainer = %Buttons
@onready var _status: Label = %Status


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if _handle_cli(args):
		return
	_style_menu()
	_build_menu()
	_show_notices()


func _handle_cli(args: PackedStringArray) -> bool:
	if args.has("--new-game"):
		var opts: Dictionary = {"game_mode": _arg_value(args, "--mode", "survival")}
		var seed_s: String = _arg_value(args, "--seed", "")
		if seed_s != "":
			opts["seed"] = NewGamePanel.run_seed_from_text(seed_s)
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
		if not opts.has("seed"):
			opts["seed"] = cli_default_seed(str(opts["game_mode"]), opts.has("world_gen"))
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


## The run seed of a `--new-game` without `--seed`: the slice on the handcrafted map is the curated
## demo run (the menu's button), anything else a fresh run (ADR-0030).
static func cli_default_seed(mode: String, random_world: bool) -> int:
	return SLICE_DEMO_SEED if mode == "slice" and not random_world else NewGamePanel.fresh_seed()


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


## The menu in the game's own style (ADR-0063): the kit theme, the title in the typewriter face,
## the line under it in the margin hand, entries down the left over a dark wash so they read on
## whatever the backdrop shows.
func _style_menu() -> void:
	theme = UiStyle.kit_theme()
	# The flight over Larch Hollow behind the menu (it builds on a worker and fades in).
	if Settings.menu_backdrop != "off":
		var backdrop := MenuBackdrop.new()
		backdrop.name = "Backdrop"
		backdrop.mode = Settings.menu_backdrop
		add_child(backdrop)
		move_child(backdrop, 1)
		backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var wash := TextureRect.new()
	wash.name = "Wash"
	var g := Gradient.new()
	g.set_color(0, Color(0.02, 0.022, 0.02, 0.92))
	g.set_color(1, Color(0.02, 0.022, 0.02, 0.0))
	g.add_point(0.55, Color(0.02, 0.022, 0.02, 0.6))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.width = 256
	gt.height = 4
	wash.texture = gt
	wash.stretch_mode = TextureRect.STRETCH_SCALE
	wash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(wash)
	move_child(wash, 2 if has_node("Backdrop") else 1)
	wash.anchor_right = 0.62
	wash.anchor_bottom = 1.0
	wash.offset_right = 0
	wash.offset_bottom = 0
	var title: Label = $Title
	title.add_theme_font_override(&"font", UiStyle.heading_font())
	title.add_theme_font_size_override(&"font_size", 104)
	title.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	title.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.6))
	title.add_theme_constant_override(&"shadow_offset_y", 3)
	title.offset_top = 64
	title.offset_bottom = 190
	var sub: Label = $Subtitle
	sub.add_theme_font_override(&"font", UiStyle.hand_font())
	sub.add_theme_font_size_override(&"font_size", 34)
	sub.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT)
	sub.offset_top = 182
	sub.offset_bottom = 230
	_list.offset_top = 290
	_list.offset_right = 640
	_list.add_theme_constant_override(&"separation", 2)
	_status.theme_type_variation = &"DimLabel"
	# The menu's own score (generated, music/menu), faded in.
	var tune: AudioStream = Audio.stream(&"music/menu")
	if tune != null:
		var music := AudioStreamPlayer.new()
		music.name = "Music"
		music.stream = tune
		music.bus = &"Music"
		music.volume_db = -40.0
		add_child(music)
		music.play()
		create_tween().tween_property(music, "volume_db", UiStyle.level("menu_music", -10.0), 4.0)


func _build_menu() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	var slots: Array[Dictionary] = SaveSystem.list_slots()
	if not slots.is_empty():
		_add_button("Continue (Day %d)" % int(slots[0].get("day", 1)), _load.bind(str(slots[0]["slot"])))
	_add_button("New Game…", _open_new_game)
	var demo: Button = _add_button("Vertical Slice demo",
		func() -> void: Game.start_new_game({"game_mode": "slice", "seed": SLICE_DEMO_SEED}))
	demo.tooltip_text = ("The curated demo run (seed %d, the Hum on night 3): the same run seed every time," % SLICE_DEMO_SEED) + " so the same buildings, loot and Hum as the QA screenshots. New Game… rolls a fresh run."
	_add_button("Random World…", _open_new_game.bind(true))
	for s: Dictionary in slots:
		var label: String = "Load %s — Day %d" % [str(s.get("slot", "?")).capitalize(), int(s.get("day", 1))]
		if str(s.get("preset", "")) != "":
			label += " · %s" % str(s["preset"]).capitalize()
		if str(s.get("world_mode", "")) == "random":
			label += " · Random world"
		var b: Button = _add_button(label, _load.bind(str(s["slot"])))
		# Save v7: a run whose world is neither on disk nor bundled in its slot gets a new world.
		var warn: String = SaveSystem.world_warning(s)
		if warn != "":
			b.text += " · world missing"
			b.tooltip_text = warn
	_add_button("Options…", _open_options)
	_add_button("The Intro", _play_intro)
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
	var sb: StyleBoxFlat = UiStyle.panel_box(false)
	sb.border_color = UiStyle.RUST_BRIGHT
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override(&"panel", sb)
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(520, 0)
	label.add_theme_color_override(&"font_color", Color(0.95, 0.86, 0.68))
	label.add_theme_font_size_override(&"font_size", UiStyle.BODY_SIZE - 2)
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


## Replays the new-game intro over the menu (ADR-0064).
func _play_intro() -> void:
	var intro := IntroPlayer.new()
	add_child(intro)
	_list.visible = false
	var music: AudioStreamPlayer = get_node_or_null("Music") as AudioStreamPlayer
	if music != null:
		music.stream_paused = true
	intro.finished.connect(func() -> void:
		var tw := intro.create_tween()
		tw.tween_property(intro, "modulate:a", 0.0, 0.8)
		tw.tween_callback(intro.queue_free)
		_list.visible = true
		if music != null:
			music.stream_paused = false)
	intro.play({}, IntroPlayer.vars_for(null))


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
	b.theme_type_variation = &"MenuEntry"
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(520, 50)
	b.pressed.connect(cb)
	_list.add_child(b)
	return b
