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
	get_viewport().size_changed.connect(_fit_menu)
	_show_notices()
	# Once per new entry (a new build's notes), over the menu.
	if WhatsNewPanel.should_show(str(WhatsNewPanel.newest().get("id", "")), Settings.whats_new_seen):
		_open_whats_new.call_deferred()


## A gamepad press with nothing focused focuses the first entry of what is open (the menu, New
## Game, Options), so the menu can be driven by the pad alone.
func _input(event: InputEvent) -> void:
	if UiStyle.is_pad_event(event) and UiStyle.focus_first(self):
		get_viewport().set_input_as_handled()


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
	_list.offset_top = MENU_TOP
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


## Save slots the QA runners write (smoke, tour, screenshots, probes); "qa_" marks any new one.
## Players never see them on the menu; a developer does (the editor, or `--dev`).
const QA_SLOTS: PackedStringArray = ["smoke", "tour", "screens", "perf", "intro_probe", "continue_check",
	"rwg_shots", "exterior_qa", "aggro_probe", "stream_walk", "humwatch"]


## Whether this run shows developer entries (QA saves, the slice demo): the editor's binary or
## `-- --dev`. A packaged build shows a player's menu only.
static func dev_menu(args: PackedStringArray) -> bool:
	# `--player` shows a player's menu from the editor's binary (the menu guard checks that it fits).
	return (OS.has_feature("editor") and not args.has("--player")) or args.has("--dev")


## The slots the menu lists: everything for a developer, the player's own runs otherwise.
static func menu_slots(slots: Array[Dictionary], dev: bool) -> Array[Dictionary]:
	if dev:
		return slots
	var out: Array[Dictionary] = []
	for s: Dictionary in slots:
		var name: String = str(s.get("slot", ""))
		if not QA_SLOTS.has(name) and not name.begins_with("qa_"):
			out.append(s)
	return out


## The list's top and an entry's height on a tall window; a short one (1280x720 with Continue:
## 8 entries) moves the list up and then thins the entries so Quit stays above the version line.
const MENU_TOP: float = 290.0
const ENTRY_HEIGHT: float = 50.0
const MENU_TOP_MIN: float = 236.0
const ENTRY_HEIGHT_MIN: float = 40.0
const ENTRY_GAP: float = 2.0
## Room kept under the list for the version line (Status, 50 px up from the bottom).
const BOTTOM_ROOM: float = 58.0


## {top, entry} for `n` entries in a window `view_h` tall: the list ends at least BOTTOM_ROOM
## above the bottom, moving up first (not past the subtitle), then with thinner entries. Pure.
static func menu_fit(view_h: float, n: int) -> Dictionary:
	var room: float = view_h - BOTTOM_ROOM
	var gaps: float = ENTRY_GAP * maxf(0.0, n - 1)
	var top: float = MENU_TOP
	var entry: float = ENTRY_HEIGHT
	if top + n * entry + gaps > room:
		top = maxf(MENU_TOP_MIN, room - n * entry - gaps)
	if top + n * entry + gaps > room and n > 0:
		entry = maxf(ENTRY_HEIGHT_MIN, floorf((room - top - gaps) / n))
	return {"top": top, "entry": entry}


func _fit_menu() -> void:
	var entries: Array[Node] = _list.get_children().filter(func(c: Node) -> bool: return c is Button and not c.is_queued_for_deletion())
	var fit: Dictionary = menu_fit(get_viewport_rect().size.y, entries.size())
	_list.offset_top = float(fit["top"])
	for b: Node in entries:
		(b as Button).custom_minimum_size.y = float(fit["entry"])


func _build_menu() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	var dev: bool = dev_menu(OS.get_cmdline_user_args())
	var slots: Array[Dictionary] = menu_slots(SaveSystem.list_slots(), dev)
	if not slots.is_empty():
		_add_button("Continue (Day %d)" % int(slots[0].get("day", 1)), _load.bind(str(slots[0]["slot"])))
	_add_button("New Game…", _open_new_game)
	var demo: Button = null
	if dev:
		demo = _add_button("Vertical Slice demo (dev)",
			func() -> void: Game.start_new_game({"game_mode": "slice", "seed": SLICE_DEMO_SEED}))
		demo.tooltip_text = ("The curated demo run (seed %d, the Hum on night 3): the same run seed every time," % SLICE_DEMO_SEED) + " so the same buildings, loot and Hum as the QA screenshots. New Game… rolls a fresh run."
	_add_button("Random World…", _open_new_game.bind(true))
	if not slots.is_empty():
		_add_button("Load…", _open_load.bind(slots))
	_add_button("Options…", _open_options)
	_add_button("The Intro", _play_intro)
	if not WhatsNewPanel.newest().is_empty():
		_add_button("What's New", _open_whats_new)
	_add_button("Quit", quit_cleanly)
	_fit_menu.call_deferred()
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
	_centre(panel)
	_list.visible = false
	_set_title_visible(false)
	panel.closed.connect(func() -> void:
		panel.queue_free()
		_list.visible = true
		_set_title_visible(true))


## The newest build's notes (WhatsNewPanel); closing marks them seen.
func _open_whats_new() -> void:
	var panel := WhatsNewPanel.new()
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	_centre(panel)
	_list.visible = false
	_set_title_visible(false)
	panel.closed.connect(func() -> void:
		panel.queue_free()
		_list.visible = true
		_set_title_visible(true))


## Every run as a card (thumbnail, day, place, play time, world; delete with confirm).
func _open_load(slots: Array[Dictionary]) -> void:
	var panel := LoadPanel.new()
	panel.slots = slots
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	_centre(panel)
	_list.visible = false
	_set_title_visible(false)
	panel.load_requested.connect(_load)
	panel.closed.connect(func() -> void:
		panel.queue_free()
		_list.visible = true
		_set_title_visible(true)
		# A run deleted there leaves Continue and Load… pointing at it.
		_build_menu())


## Quits once the menu's music has let go of its stream: quitting while it plays left the
## AudioServer holding the playback, and the engine reported the stream "still in use at exit".
func quit_cleanly() -> void:
	var music: AudioStreamPlayer = get_node_or_null("Music") as AudioStreamPlayer
	if music != null:
		music.stop()
		music.stream = null
	for i: int in 3:
		await get_tree().process_frame
	get_tree().quit()


## Centres a panel over the menu by its laid-out size, once it has one: centred by its minimum
## size, Options (laid out 1050 wide, not the 680 assumed) ran off a 1280 window's right edge.
func _centre(panel: Control) -> void:
	panel.position = centred(get_viewport_rect().size, panel.get_combined_minimum_size())
	await get_tree().process_frame
	if is_instance_valid(panel):
		panel.position = centred(get_viewport_rect().size, panel.size)


## Where a panel `s` big goes in a `view`-sized window: centred, never above or left of its edge.
static func centred(view: Vector2, s: Vector2) -> Vector2:
	return ((view - s) * 0.5).max(Vector2.ZERO)


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
	_centre(panel)
	_list.visible = false
	panel.closed.connect(func() -> void: _list.visible = true)


func _add_button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.theme_type_variation = &"MenuEntry"
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(520, ENTRY_HEIGHT)
	b.pressed.connect(cb)
	_list.add_child(b)
	return b
