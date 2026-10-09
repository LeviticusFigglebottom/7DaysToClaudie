extends Node
## User settings (autoload `Settings`): input bindings, graphics presets, audio, gameplay prefs.
##
## Input actions are defined in res://data/config/input_bindings.json and registered here at
## startup (rebinds are persisted to user://settings.cfg). Graphics presets come from
## res://data/config/graphics_presets.json; systems read `Settings.graphics` and listen to
## `graphics_changed` (the world environment controller applies GI/fog/shadows).

signal graphics_changed()
signal settings_changed()

const SETTINGS_PATH: String = "user://settings.cfg"
const PRESET_ORDER: PackedStringArray = ["low", "medium", "high", "ultra"]

var graphics_preset: String = "high"
## Resolved preset values (dictionary from graphics_presets.json, plus user overrides).
var graphics: Dictionary = {}
var mouse_sensitivity: float = 0.0022
var invert_y: bool = false
var fov: float = 75.0
var head_bob: float = 1.0
var volumes: Dictionary = {"Master": 1.0, "SFX": 1.0, "Ambience": 0.9, "Music": 0.6, "UI": 0.8}
var fullscreen: bool = false
var vsync: bool = true
## Exposure multiplier for the picture (options screen); nights stay dark, just less so.
var brightness: float = 1.0
## Size of the 2D interface: 0 follows the window (1 up to 1080p, 2 at 4K), else a fixed factor
## (UiStyle.SCALES; ADR-0063).
var ui_scale: float = 0.0
## The main menu's backdrop: "moving" (the flight, frozen if it runs slow), "still" or "off".
var menu_backdrop: String = "moving"
## Bracketed captions for sounds that carry meaning (the intro's cues, the tether's radio).
var sound_captions: bool = false

var _cfg := ConfigFile.new()
var _default_bindings: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_load_user_settings()
	register_input_actions()
	_resolve_graphics()
	get_tree().root.size_changed.connect(apply_ui_scale)
	apply_ui_scale.call_deferred()


## Scales the 2D interface to the window (or the player's fixed choice).
func apply_ui_scale() -> void:
	UiStyle.apply_scale(get_tree().root, ui_scale)


func set_ui_scale(v: float) -> void:
	ui_scale = v
	apply_ui_scale()
	save()


# --- Input ---------------------------------------------------------------------------------

## (Re)registers every action from input_bindings.json (+ user rebinds).
func register_input_actions() -> void:
	_default_bindings = Content.config(&"input_bindings").get("actions", {})
	for action: String in _default_bindings:
		var events: Array = _cfg.get_value("input", action, _default_bindings[action])
		if InputMap.has_action(action):
			InputMap.action_erase_events(action)
		else:
			InputMap.add_action(action, 0.2)
		for spec: Variant in events:
			var ev: InputEvent = _event_from_spec(spec)
			if ev != null:
				InputMap.action_add_event(action, ev)


func rebind(action: String, specs: Array) -> void:
	_cfg.set_value("input", action, specs)
	register_input_actions()
	save()


## The binding specs of an action as used now (user rebinds over input_bindings.json).
func bindings(action: String) -> Array:
	return _cfg.get_value("input", action, _default_bindings.get(action, []))


## Binds a keyboard key or mouse button as the action's main (first keyboard/mouse) binding,
## keeping its gamepad bindings (ADR-0037). Returns false for an event that can't be bound.
func bind_primary(action: String, ev: InputEvent) -> bool:
	var spec: Dictionary = spec_from_event(ev)
	if spec.is_empty():
		return false
	# The first keyboard/mouse binding is replaced; other bindings (Ctrl as well as C for crouch,
	# the gamepad's) stay, unless one is the new input itself.
	var out: Array = [spec]
	var replaced: bool = false
	for old: Variant in bindings(action):
		var d: Dictionary = old if old is Dictionary else {}
		if not replaced and (d.has("key") or d.has("mouse")):
			replaced = true
			continue
		if d != spec:
			out.append(d)
	rebind(action, out)
	return true


## Every action back to input_bindings.json.
func reset_bindings() -> void:
	if _cfg.has_section("input"):
		_cfg.erase_section("input")
	register_input_actions()
	save()


static func spec_from_event(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var k: InputEventKey = ev
		var code: Key = k.physical_keycode if k.physical_keycode != KEY_NONE else k.keycode
		return {} if code == KEY_NONE else {"key": OS.get_keycode_string(code)}
	if ev is InputEventMouseButton:
		return {"mouse": int((ev as InputEventMouseButton).button_index)}
	return {}


## "E", "Mouse 1", "Pad 2"... for the controls screen.
static func describe(spec: Variant) -> String:
	var d: Dictionary = spec if spec is Dictionary else {}
	if d.has("key"):
		return str(d["key"])
	if d.has("mouse"):
		return {1: "Left mouse", 2: "Right mouse", 3: "Middle mouse", 4: "Wheel up", 5: "Wheel down"}.get(int(d["mouse"]), "Mouse %d" % int(d["mouse"]))
	if d.has("joy_button"):
		return "Pad %d" % int(d["joy_button"])
	if d.has("joy_axis"):
		return "Stick %d%s" % [int(d["joy_axis"]), "+" if float(d.get("dir", 1.0)) > 0.0 else "-"]
	return "?"


static func _event_from_spec(spec: Variant) -> InputEvent:
	if not spec is Dictionary:
		return null
	var d: Dictionary = spec
	if d.has("key"):
		var ev := InputEventKey.new()
		var code: Key = OS.find_keycode_from_string(str(d["key"]))
		if code == KEY_NONE:
			push_warning("Settings: unknown key '%s'" % d["key"])
			return null
		ev.physical_keycode = code
		return ev
	if d.has("mouse"):
		var mb := InputEventMouseButton.new()
		mb.button_index = int(d["mouse"]) as MouseButton
		return mb
	if d.has("joy_button"):
		var jb := InputEventJoypadButton.new()
		jb.button_index = int(d["joy_button"]) as JoyButton
		return jb
	if d.has("joy_axis"):
		var ja := InputEventJoypadMotion.new()
		ja.axis = int(d["joy_axis"]) as JoyAxis
		ja.axis_value = float(d.get("dir", 1.0))
		return ja
	return null


# --- Graphics ------------------------------------------------------------------------------

func set_graphics_preset(preset: String) -> void:
	if not PRESET_ORDER.has(preset):
		push_warning("Settings: unknown preset '%s'" % preset)
		return
	graphics_preset = preset
	_cfg.set_value("graphics", "preset", preset)
	# A preset is a starting point: picking one drops the per-feature changes made on top of it.
	if _cfg.has_section("graphics_overrides"):
		_cfg.erase_section("graphics_overrides")
	_resolve_graphics()
	save()


## Changes one graphics feature on top of the preset (ADR-0037); saved, applied at once.
func set_graphics_override(key: String, value: Variant) -> void:
	_cfg.set_value("graphics_overrides", key, value)
	_resolve_graphics()
	save()


## Keys changed on top of the active preset.
func graphics_overrides() -> PackedStringArray:
	return _cfg.get_section_keys("graphics_overrides") if _cfg.has_section("graphics_overrides") else PackedStringArray()


## Value from the active graphics preset.
func gfx(key: String, default: Variant) -> Variant:
	return graphics.get(key, default)


## The preset a first run starts on, from the GPU kind (ADR-0037): integrated or software
## rendering gets low, an unknown kind medium, a discrete GPU high.
static func preset_for_adapter(adapter_type: RenderingDevice.DeviceType) -> String:
	match adapter_type:
		RenderingDevice.DEVICE_TYPE_DISCRETE_GPU:
			return "high"
		RenderingDevice.DEVICE_TYPE_INTEGRATED_GPU, RenderingDevice.DEVICE_TYPE_CPU:
			return "low"
	return "medium"


func _resolve_graphics() -> void:
	var presets: Dictionary = Content.config(&"graphics_presets").get("presets", {})
	var env_preset: String = OS.get_environment("HOLLOWMERE_GFX")
	if PRESET_ORDER.has(env_preset):
		graphics_preset = env_preset
	graphics = (presets.get(graphics_preset, {}) as Dictionary).duplicate()
	for key: String in _cfg.get_section_keys("graphics_overrides") if _cfg.has_section("graphics_overrides") else PackedStringArray():
		graphics[key] = _cfg.get_value("graphics_overrides", key)
	_apply_viewport_graphics()
	graphics_changed.emit()


func _apply_viewport_graphics() -> void:
	var vp: Viewport = get_viewport()
	if vp == null:
		return
	vp.scaling_3d_scale = float(graphics.get("render_scale", 1.0))
	match str(graphics.get("upscaler", "bilinear")):
		"fsr2":
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
		"fsr":
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR
		_:
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
	vp.use_taa = bool(graphics.get("taa", true)) and vp.scaling_3d_mode != Viewport.SCALING_3D_MODE_FSR2
	vp.mesh_lod_threshold = float(graphics.get("mesh_lod_threshold", 1.5))
	vp.positional_shadow_atlas_size = int(graphics.get("positional_shadow_atlas", 4096))
	RenderingServer.directional_shadow_atlas_set_size(int(graphics.get("directional_shadow_size", 4096)), true)
	# Soft shadow filtering (0 hard .. 5 ultra) costs taps per pixel on every shadowed surface.
	var filt: int = clampi(int(graphics.get("shadow_filter", 3)), 0, 5)
	RenderingServer.directional_soft_shadow_filter_set_quality(filt as RenderingServer.ShadowQuality)
	RenderingServer.positional_soft_shadow_filter_set_quality(filt as RenderingServer.ShadowQuality)


# --- Audio ---------------------------------------------------------------------------------

func set_volume(bus: String, linear: float) -> void:
	volumes[bus] = clampf(linear, 0.0, 1.0)
	_apply_volumes()
	save()


func _apply_volumes() -> void:
	for bus: String in volumes:
		var idx: int = AudioServer.get_bus_index(bus)
		if idx >= 0:
			AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(0.0001, float(volumes[bus]))))


# --- Display -------------------------------------------------------------------------------

func set_display(p_fullscreen: bool, p_vsync: bool) -> void:
	fullscreen = p_fullscreen
	vsync = p_vsync
	_apply_display()
	save()


func _apply_display() -> void:
	# Headless runs (tests, CI, the smoke) have no window to change.
	if DisplayServer.get_name() == "headless":
		return
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if vsync else DisplayServer.VSYNC_DISABLED)


# --- Persistence ---------------------------------------------------------------------------

func save() -> void:
	_cfg.set_value("gameplay", "mouse_sensitivity", mouse_sensitivity)
	_cfg.set_value("gameplay", "invert_y", invert_y)
	_cfg.set_value("gameplay", "fov", fov)
	_cfg.set_value("gameplay", "head_bob", head_bob)
	_cfg.set_value("graphics", "brightness", brightness)
	_cfg.set_value("audio", "volumes", volumes)
	_cfg.set_value("display", "fullscreen", fullscreen)
	_cfg.set_value("display", "vsync", vsync)
	_cfg.set_value("display", "ui_scale", ui_scale)
	_cfg.set_value("display", "menu_backdrop", menu_backdrop)
	_cfg.set_value("audio", "sound_captions", sound_captions)
	_cfg.save(SETTINGS_PATH)
	settings_changed.emit()


func _load_user_settings() -> void:
	if _cfg.load(SETTINGS_PATH) != OK:
		_cfg = ConfigFile.new()
	graphics_preset = _cfg.get_value("graphics", "preset", "")
	if graphics_preset == "":
		# First run: start from what the GPU can carry, and remember it (ADR-0037).
		graphics_preset = "high" if DisplayServer.get_name() == "headless" else preset_for_adapter(RenderingServer.get_video_adapter_type())
		if DisplayServer.get_name() != "headless":
			_cfg.set_value("graphics", "preset", graphics_preset)
	mouse_sensitivity = _cfg.get_value("gameplay", "mouse_sensitivity", mouse_sensitivity)
	invert_y = _cfg.get_value("gameplay", "invert_y", invert_y)
	fov = _cfg.get_value("gameplay", "fov", fov)
	head_bob = _cfg.get_value("gameplay", "head_bob", head_bob)
	brightness = _cfg.get_value("graphics", "brightness", brightness)
	fullscreen = _cfg.get_value("display", "fullscreen", fullscreen)
	vsync = _cfg.get_value("display", "vsync", vsync)
	ui_scale = float(_cfg.get_value("display", "ui_scale", ui_scale))
	menu_backdrop = str(_cfg.get_value("display", "menu_backdrop", menu_backdrop))
	sound_captions = bool(_cfg.get_value("audio", "sound_captions", sound_captions))
	var v: Variant = _cfg.get_value("audio", "volumes", volumes)
	if v is Dictionary:
		volumes.merge(v, true)
	_apply_volumes.call_deferred()
	# Only touch the window when the player has chosen something (keeps --resolution runs as asked).
	if _cfg.has_section("display"):
		_apply_display.call_deferred()
