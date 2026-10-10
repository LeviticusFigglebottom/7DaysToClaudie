extends GutTest
## Graphics and controls options (ADR-0037): per-feature overrides on top of a preset, a preset
## that drops them, the first-run preset from the GPU kind, key rebinding that keeps gamepad and
## second bindings, and the options panel building all three tabs. Restores the user's settings.

var _preset: String
var _overrides: Dictionary = {}
var _crouch: Array


func before_each() -> void:
	_preset = Settings.graphics_preset
	_overrides.clear()
	for k: String in Settings.graphics_overrides():
		_overrides[k] = Settings.graphics[k]
	_crouch = Settings.bindings("crouch").duplicate(true)


func after_each() -> void:
	Settings.set_graphics_preset(_preset)
	for k: String in _overrides:
		Settings.set_graphics_override(k, _overrides[k])
	var defaults: Array = Content.config(&"input_bindings").get("actions", {}).get("crouch", [])
	if _crouch == defaults:
		Settings.reset_bindings()
	else:
		Settings.rebind("crouch", _crouch)


func test_an_override_sits_on_the_preset_until_a_preset_is_picked() -> void:
	Settings.set_graphics_preset("high")
	assert_true(bool(Settings.gfx("sdfgi", false)), "high has GI")
	Settings.set_graphics_override("sdfgi", false)
	assert_false(bool(Settings.gfx("sdfgi", true)), "turned off on top of high")
	assert_true(Settings.graphics_overrides().has("sdfgi"))
	assert_eq(float(Settings.gfx("shadow_distance", 0.0)), 130.0, "the rest of the preset stands")
	Settings.set_graphics_preset("low")
	assert_eq(Settings.graphics_overrides().size(), 0, "a preset drops the changes")
	assert_eq(int(Settings.gfx("shadow_filter", -1)), 1)


func test_first_run_preset_follows_the_gpu_kind() -> void:
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU), "high")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_INTEGRATED_GPU), "low")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_CPU), "low")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_OTHER), "medium")


func test_every_preset_sets_every_option_the_screen_shows() -> void:
	var presets: Dictionary = Content.config(&"graphics_presets").get("presets", {})
	for name: String in Settings.PRESET_ORDER:
		var p: Dictionary = presets.get(name, {})
		for k: String in ["render_scale", "upscaler", "taa", "sdfgi", "volumetric_fog", "ssao", "ssil", "ssr",
				"directional_shadow_size", "shadow_filter", "shadow_distance", "view_distance", "tree_lod_scale", "object_distance",
				"grass_density", "grass_distance"]:
			assert_true(p.has(k), "%s sets %s" % [name, k])


func test_rebinding_replaces_the_main_key_and_keeps_the_rest() -> void:
	Settings.reset_bindings()
	var ev := InputEventKey.new()
	ev.physical_keycode = KEY_Z
	assert_true(Settings.bind_primary("crouch", ev))
	var specs: Array = Settings.bindings("crouch")
	assert_eq(specs[0], {"key": "Z"})
	assert_true(specs.has({"key": "Ctrl"}), "the second key stays")
	assert_true(specs.any(func(s: Dictionary) -> bool: return s.has("joy_button")), "the gamepad button stays")
	var z := InputEventKey.new()
	z.physical_keycode = KEY_Z
	z.pressed = true
	assert_true(InputMap.event_is_action(z, &"crouch"), "the input map follows")
	Settings.reset_bindings()
	assert_eq(Settings.bindings("crouch")[0], {"key": "C"})


func test_binding_specs_round_trip_and_read_well() -> void:
	var mb := InputEventMouseButton.new()
	mb.button_index = MOUSE_BUTTON_RIGHT
	assert_eq(Settings.spec_from_event(mb), {"mouse": 2})
	assert_eq(Settings.describe({"mouse": 2}), "Right mouse")
	assert_eq(Settings.describe({"key": "Shift"}), "Shift")
	assert_eq(Settings.spec_from_event(InputEventJoypadMotion.new()), {}, "only keys and mouse buttons are bound here")


func test_the_panel_builds_every_tab() -> void:
	for tab: String in OptionsPanel.TABS:
		var panel := OptionsPanel.new()
		panel.open_tab = tab
		add_child_autofree(panel)
		await get_tree().process_frame
		assert_eq(panel._tabs.get_tab_count(), 3)
		assert_eq(panel._tabs.current_tab, OptionsPanel.TABS.find(tab))
		assert_gt((panel._graphics_page.get_child(0) as GridContainer).get_child_count(), 20, "graphics rows")
		assert_gt((panel._controls_page.get_child(0) as GridContainer).get_child_count(), 40, "a row per action")


func test_discrete_gpus_by_name() -> void:
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "AMD Radeon RX 9070 XT"), "ultra", "the owner's card")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "NVIDIA GeForce RTX 4070 SUPER"), "ultra")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "NVIDIA GeForce RTX 3060"), "high")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "NVIDIA GeForce GTX 1060 6GB"), "medium")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "Radeon RX 580 Series"), "medium")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_DISCRETE_GPU, "Something New 9000"), "high", "unknown names default to High")
	assert_eq(Settings.preset_for_adapter(RenderingDevice.DEVICE_TYPE_INTEGRATED_GPU, "AMD Radeon RX 9070 XT"), "low")


func test_numeric_choices_match_json_floats() -> void:
	assert_true(OptionsPanel.same_choice(4096, 4096.0), "a preset's 4096.0 is the 4096 choice")
	assert_true(OptionsPanel.same_choice(3, 3.0))
	assert_false(OptionsPanel.same_choice(2048, 4096.0))
	assert_true(OptionsPanel.same_choice("fsr2", "fsr2"))
	assert_false(OptionsPanel.same_choice("fsr", "fsr2"))


func test_pad_names_and_device_aware_labels() -> void:
	assert_eq(Settings.describe({"joy_button": 0}), "Pad A")
	assert_eq(Settings.describe({"joy_button": 10}), "Pad RB")
	var was: bool = Settings.using_pad
	Settings.using_pad = false
	assert_eq(Settings.input_label("jump"), "Space")
	Settings.using_pad = true
	assert_eq(Settings.input_label("jump"), "A", "a pad player sees the pad button")
	assert_eq(Settings.input_label("light"), Settings.input_label("light"), "an action with no pad button keeps its key")
	Settings.using_pad = was


func test_conflicts_name_other_actions_on_the_same_input() -> void:
	var actions: PackedStringArray = ["jump", "sprint", "cancel", "pause"]
	assert_true(Settings.conflicts("jump", {"key": "Shift"}, actions).has("sprint"))
	assert_eq(Settings.conflicts("jump", {"key": "F13"}, actions).size(), 0)
	var esc: Dictionary = {}
	for sp: Variant in Settings.bindings("pause"):
		if sp is Dictionary and (sp as Dictionary).has("key"):
			esc = sp
	if not esc.is_empty():
		assert_false(Settings.conflicts("cancel", esc, actions).has("pause"), "cancel and pause may share Esc")


func test_bind_pad_keeps_keys() -> void:
	var before: Array = Settings.bindings("interact").duplicate(true)
	var ev := InputEventJoypadButton.new()
	ev.button_index = JOY_BUTTON_Y
	assert_true(Settings.bind_pad("interact", ev))
	var after: Array = Settings.bindings("interact")
	assert_true(after.has({"joy_button": 3}))
	var keys: int = 0
	for sp: Variant in after:
		if sp is Dictionary and (sp as Dictionary).has("key"):
			keys += 1
	assert_gt(keys, 0, "the key binding stays")
	Settings.rebind("interact", before)


func test_a_pad_alone_reaches_every_screen_and_the_fight() -> void:
	# A pad-only pass: by default the pad could move, jump and interact, but not look, attack, open
	# the roll, the field manual, the tether or pause.
	var cfg: Dictionary = Content.config(&"input_bindings").get("actions", {})
	for action: String in ["attack", "block", "inventory", "guidebook", "tracker", "pause", "map", "interact", "jump", "cancel", "toolbelt_next", "toolbelt_prev", "drop", "light"]:
		var pad: bool = false
		for spec: Variant in cfg.get(action, []):
			if spec is Dictionary and ((spec as Dictionary).has("joy_button") or (spec as Dictionary).has("joy_axis")):
				pad = true
		assert_true(pad, "%s has a pad default" % action)
	# No two actions share a pad input, except block and aim on LT (each in its own context).
	var seen: Dictionary = {}
	for action2: String in cfg:
		for spec2: Variant in cfg[action2]:
			if spec2 is Dictionary and (spec2 as Dictionary).has("joy_button"):
				var key: String = str((spec2 as Dictionary)["joy_button"])
				assert_false(seen.has(key), "pad button %s on %s and %s" % [key, seen.get(key, ""), action2])
				seen[key] = action2
	assert_eq(Settings.describe({"joy_axis": JOY_AXIS_TRIGGER_RIGHT, "dir": 1}), "Pad RT")
	assert_eq(Settings.describe({"joy_axis": JOY_AXIS_TRIGGER_LEFT, "dir": 1}), "Pad LT")


func test_the_right_stick_looks() -> void:
	const PlayerScript := preload("res://src/player/player.gd")
	assert_eq(PlayerScript.pad_look(Vector2(0.1, 0.05), 0.016), Vector2.ZERO, "the dead zone")
	var full: Vector2 = PlayerScript.pad_look(Vector2(1, 0), 1.0)
	assert_almost_eq(full.x, PlayerScript.PAD_LOOK_SPEED.x, 0.001, "full tilt turns at the look speed")
	var half: Vector2 = PlayerScript.pad_look(Vector2(0.575, 0), 1.0)
	assert_lt(half.x, full.x * 0.5, "eased: fine aim near the centre")
