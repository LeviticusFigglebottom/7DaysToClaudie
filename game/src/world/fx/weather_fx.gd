class_name WeatherFx
extends Node3D
## Rain, snow, splashes, eave drips and dust motes round the camera, and the weather map they and
## the surface shaders read (ADR-0033). Numbers in data/config/weather.json "precipitation",
## "dust" and "maps".
## * Precipitation is GPU particles with their own process shader (precipitation.gdshader): drops
##   and flakes spawn in a column box round the camera, fall with the wind and its gusts, and stop
##   where the weather map says rain lands, so none falls indoors, under a porch roof or a bridge.
##   A drop that lands turns into a splash on the spot for a fifth of a second (the flipbook
##   fx_splash): on roofs, on the road and on the water. Streaks are lit like anything else, so
##   they catch lamps, torches and lightning, and mirror the sky by day.
## * Eave drips fall from roof edges the map finds over open ground, faster as the roof runs wet,
##   and go on a while after the rain as it drains.
## * Dust motes hang in the air indoors by day; lit, they show only where a light shaft crosses
##   them.
## Nothing is built headless (tests, smoke): the map, the particles and the motes are presentation.

var env: EnvironmentController
var maps := WeatherMaps.new()
var rain: GPUParticles3D
var snow: GPUParticles3D
var drips: GPUParticles3D
var motes: GPUParticles3D

var _cfg: Dictionary = {}
var _pcfg: Dictionary = {}
var _headless: bool = false
var _w: Dictionary = {}
var _wind_now: float = 0.0
var _day: float = 1.0
var _eave_img: Image
var _eave_tex: ImageTexture
var _indoor_t: float = 0.0
var _indoors: bool = false
## How hard the roofs are dripping (follows wetness, lags the rain as the roofs drain), and the
## share of drip particles the eaves round the camera need.
var _drip_level: float = 0.0
var _drip_share: float = 0.0


func _ready() -> void:
	_headless = DisplayServer.get_name() == "headless"
	_cfg = Content.config(&"weather")
	_pcfg = _cfg.get("precipitation", {}) as Dictionary
	maps.configure(_cfg.get("maps", {}) as Dictionary)
	maps.min_drop = float((_pcfg.get("drips", {}) as Dictionary).get("min_drop_m", 1.8))
	if _headless:
		return
	var box: Array = _pcfg.get("box", [13.0, 12.0, 4.0])
	var preset: String = Settings.graphics_preset
	var rain_n: int = int((_pcfg.get("rain_drops", {}) as Dictionary).get(preset, 6000))
	var snow_n: int = int((_pcfg.get("snow_flakes", {}) as Dictionary).get(preset, 4000))
	var rs: float = float(_pcfg.get("rain_speed", 8.0))
	rain = _make_precip("Rain", 0, rain_n, (float(box[1]) + float(box[2])) / rs + 0.4)
	snow = _make_precip("Snow", 1, snow_n, (float(box[1]) + float(box[2])) / float(_pcfg.get("snow_speed", 1.1)))
	var dc: Dictionary = _pcfg.get("drips", {}) as Dictionary
	drips = _make_precip("Drips", 2, int(dc.get("count", 900)), 2.2)
	_eave_img = Image.create_empty(maxi(2, int(dc.get("max_points", 256)) * 2), 1, false, Image.FORMAT_RGBAF)
	_eave_tex = ImageTexture.create_from_image(_eave_img)
	(drips.process_material as ShaderMaterial).set_shader_parameter("eave_tex", _eave_tex)
	motes = _make_motes()


func _exit_tree() -> void:
	maps.shutdown()


## The weather now (EnvironmentController, every frame): what falls, the wind with its gust and the
## daylight.
func update_weather(w: Dictionary, wind_now: float, day: float, _flash: float) -> void:
	_w = w
	_wind_now = wind_now
	_day = day


## Stops (or restarts) the rain, snow and drips where they are. QA captures freeze them so the
## renderer's temporal antialiasing can settle on them: a software frame takes so long that a
## moving drop never covers the same pixels twice, and TAA averages it away.
func hold_still(on: bool) -> void:
	for p: GPUParticles3D in [rain, snow, drips]:
		if p != null:
			p.speed_scale = 0.0 if on else 1.0


## The low ground round the camera (the map's), for the far fog level.
func valley_level() -> float:
	return maps.valley if maps.is_ready() else 0.0


func _process(delta: float) -> void:
	if _headless or _w.is_empty():
		return
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam == null:
		return
	var world: Node = Game.world
	var terrain: Object = world.get(&"terrain") if world != null else null
	var water: Object = world.get(&"water") if world != null else null
	if maps.update(cam.global_position, terrain, water, get_world_3d().direct_space_state):
		_upload_eaves()
	var at: Vector3 = cam.global_position
	var rain_f: float = float(_w.get("rain", 0.0))
	var snow_f: float = float(_w.get("snow", 0.0))
	var wd: Vector2 = _w.get("wind_dir", Vector2(1, 0))
	var push: Vector2 = wd * _wind_now * float(_pcfg.get("wind_push", 5.0))
	_drive(rain, at, rain_f, push)
	# Flakes ride the wind far more than drops do.
	_drive(snow, at, snow_f, push * 1.6)
	var target: float = clampf(float(_w.get("wetness", 0.0)) * (0.35 + 0.65 * clampf(rain_f * 2.0, 0.0, 1.0)), 0.0, 1.0)
	_drip_level = move_toward(_drip_level, target, delta * 0.05)
	_drive(drips, at, _drip_level * _drip_share, push * 0.15)
	_indoor_t -= delta
	if _indoor_t <= 0.0:
		_indoor_t = 0.25
		var pois: Node = world.get(&"pois") as Node if world != null else null
		_indoors = pois != null and bool(pois.call(&"is_indoors", at))
	if motes != null:
		motes.global_position = at
		motes.emitting = _indoors and _day > 0.15


func _drive(p: GPUParticles3D, at: Vector3, amount: float, push: Vector2) -> void:
	if p == null:
		return
	# The emitter stays at the world origin and the column follows the camera through `focus`, so
	# the particles are in world space whichever way the engine places them; its culling box moves.
	var box: Array = _pcfg.get("box", [13.0, 12.0, 4.0])
	var hw: float = float(box[0]) + 2.0
	p.visibility_aabb = AABB(at + Vector3(-hw, -float(box[2]) - 30.0, -hw), Vector3(hw * 2.0, float(box[1]) + float(box[2]) + 34.0, hw * 2.0))
	(p.process_material as ShaderMaterial).set_shader_parameter("focus", at)
	var on: bool = amount > 0.01
	if p.emitting != on:
		if on:
			# From empty: restart() runs the preprocess, so the column is full at once.
			p.restart()
		else:
			p.emitting = false
	p.amount_ratio = clampf(amount, 0.0, 1.0)
	(p.process_material as ShaderMaterial).set_shader_parameter("wind", push)


func _make_precip(node_name: String, mode: int, count: int, life: float) -> GPUParticles3D:
	var box: Array = _pcfg.get("box", [13.0, 12.0, 4.0])
	var p := GPUParticles3D.new()
	p.name = node_name
	# At the world origin whatever its parents do (see _drive).
	p.top_level = true
	p.amount = maxi(1, count)
	p.lifetime = life
	p.local_coords = false
	p.preprocess = life if mode != 2 else 0.0
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.emitting = false
	var pm := ShaderMaterial.new()
	pm.shader = load("res://assets/shaders/precipitation.gdshader")
	pm.set_shader_parameter("mode", mode)
	pm.set_shader_parameter("box", Vector3(float(box[0]), float(box[1]), float(box[2])))
	pm.set_shader_parameter("fall_speed", float(_pcfg.get("snow_speed", 1.1)) if mode == 1 else float(_pcfg.get("rain_speed", 8.0)))
	pm.set_shader_parameter("splash_s", float(_pcfg.get("splash_s", 0.24)))
	pm.set_shader_parameter("eave_cell", maps.cell_m)
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2.ONE
	var dm := ShaderMaterial.new()
	dm.shader = load("res://assets/shaders/precipitation_draw.gdshader")
	dm.set_shader_parameter("mode", mode)
	dm.set_shader_parameter("streak_length", float(_pcfg.get("streak_length", 0.5)))
	dm.set_shader_parameter("streak_width", float(_pcfg.get("streak_width", 0.0085)))
	dm.set_shader_parameter("splash_size", float(_pcfg.get("splash_size", 0.15)))
	dm.set_shader_parameter("splash_s", float(_pcfg.get("splash_s", 0.24)))
	var fs: Array = _pcfg.get("flake_size", [0.035, 0.075])
	dm.set_shader_parameter("flake_size", Vector2(float(fs[0]), float(fs[1])))
	dm.set_shader_parameter("fade_far", float(box[0]))
	dm.set_shader_parameter("life", life)
	var base: String = "res://assets/generated/textures/"
	var splash: Texture2D = load(base + "fx_splash.png") as Texture2D if ResourceLoader.exists(base + "fx_splash.png") else null
	if splash != null:
		dm.set_shader_parameter("splash_tex", splash)
		dm.set_shader_parameter("has_textures", true)
	var flakes: Texture2D = load(base + "fx_snowflakes.png") as Texture2D if mode == 1 and ResourceLoader.exists(base + "fx_snowflakes.png") else null
	if flakes != null:
		dm.set_shader_parameter("flake_tex", flakes)
		dm.set_shader_parameter("has_flakes", true)
	q.material = dm
	p.draw_pass_1 = q
	add_child(p)
	return p


func _make_motes() -> GPUParticles3D:
	var dc: Dictionary = _cfg.get("dust", {}) as Dictionary
	var bx: Array = dc.get("box", [4.0, 1.6])
	var sz: Array = dc.get("size", [0.006, 0.014])
	var p := GPUParticles3D.new()
	p.name = "Motes"
	p.amount = int(dc.get("count", 260))
	p.lifetime = 9.0
	p.preprocess = 9.0
	p.local_coords = false
	p.emitting = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-8, -4, -8), Vector3(16, 8, 16))
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(float(bx[0]), float(bx[1]), float(bx[0]))
	m.direction = Vector3.UP
	m.spread = 180.0
	var drift: float = float(dc.get("drift", 0.035))
	m.initial_velocity_min = drift * 0.3
	m.initial_velocity_max = drift
	m.gravity = Vector3(0.0, -0.004, 0.0)
	m.turbulence_enabled = true
	m.turbulence_noise_strength = 0.4
	m.turbulence_noise_scale = 2.5
	m.turbulence_influence_min = 0.02
	m.turbulence_influence_max = 0.06
	m.scale_min = float(sz[0]) / 0.01
	m.scale_max = float(sz[1]) / 0.01
	m.anim_offset_min = 0.0
	m.anim_offset_max = 1.0
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 0))
	fade.set_color(1, Color(1, 1, 1, 0))
	fade.add_point(0.2, Color(1, 1, 1, 1))
	fade.add_point(0.8, Color(1, 1, 1, 1))
	var gt := GradientTexture1D.new()
	gt.gradient = fade
	m.color_ramp = gt
	p.process_material = m
	var q := QuadMesh.new()
	q.size = Vector2(0.01, 0.01)
	var mat := StandardMaterial3D.new()
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.billboard_keep_scale = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.vertex_color_use_as_albedo = true
	mat.albedo_color = Color(1.0, 0.96, 0.88, 0.85)
	mat.roughness = 1.0
	# Motes glow where a shaft of light crosses them and vanish in the shade: lit, and lit from
	# behind too (dust scatters forward).
	mat.backlight_enabled = true
	mat.backlight = Color(0.9, 0.85, 0.75)
	var tp: String = "res://assets/generated/textures/fx_dust_motes.png"
	if ResourceLoader.exists(tp):
		mat.albedo_texture = load(tp)
		mat.particles_anim_h_frames = 2
		mat.particles_anim_v_frames = 2
		mat.particles_anim_loop = false
	q.material = mat
	p.draw_pass_1 = q
	add_child(p)
	return p


## Eave drip points to the drip shader: two texels each, (x, y, z, drop height) and the edge's
## direction, nearest the camera first, within the configured radius.
func _upload_eaves() -> void:
	if drips == null:
		return
	var dc: Dictionary = _pcfg.get("drips", {}) as Dictionary
	var cam: Camera3D = get_viewport().get_camera_3d()
	var at: Vector3 = cam.global_position if cam != null else Vector3.ZERO
	var r2: float = pow(float(dc.get("radius_m", 22.0)), 2.0)
	var pts: Array = []
	for e: Array in maps.eaves:
		var d2: float = Vector2((e[0] as Vector3).x - at.x, (e[0] as Vector3).z - at.z).length_squared()
		if d2 <= r2:
			pts.append([d2, e])
	pts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var cap: int = _eave_img.get_width() / 2
	var n: int = mini(cap, pts.size())
	for i: int in n:
		var e2: Array = pts[i][1]
		var p: Vector3 = e2[0]
		var t: Vector3 = e2[1]
		_eave_img.set_pixel(i * 2, 0, Color(p.x, p.y, p.z, float(e2[2])))
		_eave_img.set_pixel(i * 2 + 1, 0, Color(t.x, t.y, t.z, 0.0))
	_eave_tex.update(_eave_img)
	var pm: ShaderMaterial = drips.process_material as ShaderMaterial
	pm.set_shader_parameter("eave_count", n)
	# Fewer roofs near you, fewer drips: the rate per edge stays the same.
	_drip_share = clampf(float(n) / float(maxi(1, cap)), 0.05, 1.0) if n > 0 else 0.0
