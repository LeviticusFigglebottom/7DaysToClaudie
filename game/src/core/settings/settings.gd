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
## The What's new entry the player last closed (WhatsNewPanel; "" before the first).
var whats_new_seen: String = ""
## Bracketed captions for sounds that carry meaning (the intro's cues, the tether's radio).
var sound_captions: bool = false
## Frames a second the game may draw (0 = no cap): saves power and heat on a fast GPU.
var max_fps: int = 0
const FPS_CAPS: PackedInt32Array = [0, 30, 60, 90, 120, 144, 165, 240]

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


## Whether the player last used a gamepad (prompts then name pad buttons, not keys).
var using_pad: bool = false


func _input(event: InputEvent) -> void:
	if event is InputEventJoypadButton or (event is InputEventJoypadMotion and absf((event as InputEventJoypadMotion).axis_value) > 0.5):
		using_pad = true
	elif event is InputEventKey or event is InputEventMouseButton:
		using_pad = false


## How a prompt names an action's input now: its pad button while the pad is in use (when it has
## one), else its key or mouse button (TD-119; rebinds show up here).
func input_label(action: String) -> String:
	var first_key: Variant = null
	var first_pad: Variant = null
	for spec: Variant in bindings(action):
		if spec is Dictionary:
			var d: Dictionary = spec
			if first_key == null and (d.has("key") or d.has("mouse")):
				first_key = d
			if first_pad == null and d.has("joy_button"):
				first_pad = d
	if using_pad and first_pad != null:
		return describe(first_pad).trim_prefix("Pad ")
	return describe(first_key) if first_key != null else "?"


## Binds a gamepad button as the action's main pad binding, keeping its keys and mouse buttons.
func bind_pad(action: String, ev: InputEvent) -> bool:
	var spec: Dictionary = spec_from_event(ev)
	if not spec.has("joy_button"):
		return false
	var out: Array = []
	var replaced: bool = false
	for old: Variant in bindings(action):
		var d: Dictionary = old if old is Dictionary else {}
		if not replaced and d.has("joy_button"):
			replaced = true
			out.append(spec)
			continue
		if d != spec:
			out.append(d)
	if not replaced:
		out.append(spec)
	rebind(action, out)
	return true


## Actions that may share an input on purpose (the same key does different things in different
## places): Esc both cancels and pauses, the toolbelt keys pick slots in the roll too.
const SHARED_OK: Array = [["cancel", "pause"], ["attack", "ui_accept"]]


## Other actions bound to the same input as `spec` (a conflict the controls screen warns about).
func conflicts(action: String, spec: Dictionary, actions: PackedStringArray) -> PackedStringArray:
	var out: PackedStringArray = []
	for other: String in actions:
		if other == action:
			continue
		var ok_pair: bool = false
		for pair: Array in SHARED_OK:
			if pair.has(action) and pair.has(other):
				ok_pair = true
		# Inputs the shipped defaults share are shared by design (block and aim on the right
		# mouse, reload and rotate on R: each works in its own context); only new clashes warn.
		if ok_pair or (_default_bindings.get(action, []) as Array).has(spec) and (_default_bindings.get(other, []) as Array).has(spec):
			continue
		for sp: Variant in bindings(other):
			if sp is Dictionary and (sp as Dictionary) == spec:
				out.append(other)
	return out


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
	if ev is InputEventJoypadButton:
		return {"joy_button": int((ev as InputEventJoypadButton).button_index)}
	return {}


## Gamepad buttons by Godot's SDL index, as the controls screen and prompts name them.
const PAD_NAMES: Dictionary = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "Back", 5: "Guide", 6: "Start",
	7: "Left stick", 8: "Right stick", 9: "LB", 10: "RB", 11: "D-pad up", 12: "D-pad down",
	13: "D-pad left", 14: "D-pad right"}


## "E", "Mouse 1", "Pad 2"... for the controls screen.
static func describe(spec: Variant) -> String:
	var d: Dictionary = spec if spec is Dictionary else {}
	if d.has("key"):
		return str(d["key"])
	if d.has("mouse"):
		return {1: "Left mouse", 2: "Right mouse", 3: "Middle mouse", 4: "Wheel up", 5: "Wheel down"}.get(int(d["mouse"]), "Mouse %d" % int(d["mouse"]))
	if d.has("joy_button"):
		return "Pad " + str(PAD_NAMES.get(int(d["joy_button"]), str(int(d["joy_button"]))))
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
static func preset_for_adapter(adapter_type: RenderingDevice.DeviceType, adapter_name: String = "") -> String:
	match adapter_type:
		RenderingDevice.DEVICE_TYPE_DISCRETE_GPU:
			return discrete_tier(adapter_name)
		RenderingDevice.DEVICE_TYPE_INTEGRATED_GPU, RenderingDevice.DEVICE_TYPE_CPU:
			return "low"
	return "medium"


## A discrete GPU's preset from its name (ADR-0037): recent high-end cards get Ultra, cards from
## before about 2018 get Medium, everything else High. Only a first-run default; the player can
## change it, and a name we don't know is High.
const ULTRA_GPUS: PackedStringArray = ["RX 9070", "RX 7900", "RX 7800", "RX 6950", "RX 6900", "RX 6800",
	"RTX 5090", "RTX 5080", "RTX 5070", "RTX 4090", "RTX 4080", "RTX 4070", "RTX 3090", "RTX 3080"]
const MEDIUM_GPUS: PackedStringArray = ["GTX 9", "GTX 10", "GTX 16", "GTX 7", "RX 4", "RX 5", "R9 ", "R7 ", "MX1", "MX2", "MX3", "MX4",
	"QUADRO K", "QUADRO M", "RADEON PRO WX"]


static func discrete_tier(adapter_name: String) -> String:
	var n: String = adapter_name.to_upper()
	for u: String in ULTRA_GPUS:
		if n.contains(u):
			return "ultra"
	for m: String in MEDIUM_GPUS:
		if n.contains(m):
			return "medium"
	return "high"


## The preset this machine would get on a first run (the Graphics page offers it back).
static func recommended_preset() -> String:
	if DisplayServer.get_name() == "headless":
		return "high"
	return preset_for_adapter(RenderingServer.get_video_adapter_type(), RenderingServer.get_video_adapter_name())


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


func set_max_fps(v: int) -> void:
	max_fps = maxi(0, v)
	Engine.max_fps = max_fps
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
	_cfg.set_value("display", "whats_new_seen", whats_new_seen)
	_cfg.set_value("audio", "sound_captions", sound_captions)
	_cfg.set_value("display", "max_fps", max_fps)
	_cfg.save(SETTINGS_PATH)
	settings_changed.emit()


func _load_user_settings() -> void:
	if _cfg.load(SETTINGS_PATH) != OK:
		_cfg = ConfigFile.new()
	graphics_preset = _cfg.get_value("graphics", "preset", "")
	if graphics_preset == "":
		# First run: start from what the GPU can carry, and remember it (ADR-0037).
		graphics_preset = recommended_preset()
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
	whats_new_seen = str(_cfg.get_value("display", "whats_new_seen", whats_new_seen))
	sound_captions = bool(_cfg.get_value("audio", "sound_captions", sound_captions))
	max_fps = int(_cfg.get_value("display", "max_fps", max_fps))
	Engine.max_fps = max_fps
	var v: Variant = _cfg.get_value("audio", "volumes", volumes)
	if v is Dictionary:
		volumes.merge(v, true)
	_apply_volumes.call_deferred()
	# Only touch the window when the player has chosen something (keeps --resolution runs as asked).
	if _cfg.has_section("display"):
		_apply_display.call_deferred()
