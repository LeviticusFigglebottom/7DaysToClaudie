class_name EnvironmentController
extends Node3D
## Sky, sun/moon, ambient, fog, volumetric fog, GI and post-processing driven by the world clock,
## weather and the graphics preset. Also publishes the hm_* global shader parameters.
## Night is meant to be genuinely dark: moonlight is faint, ambient nearly black.

var clock: WorldClock
var weather: WeatherState
var hum_intensity: float = 0.0

var env: Environment
var world_env: WorldEnvironment
var sun: DirectionalLight3D
var moon: DirectionalLight3D
var sky_mat: ShaderMaterial
var _last_snapshot: Dictionary = {}


func _ready() -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky_mat = ShaderMaterial.new()
	sky_mat.shader = load("res://assets/shaders/sky.gdshader")
	sky.sky_material = sky_mat
	sky.radiance_size = Sky.RADIANCE_SIZE_128
	sky.process_mode = Sky.PROCESS_MODE_REALTIME
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	env.fog_sky_affect = 0.6
	env.fog_aerial_perspective = 0.35
	env.glow_enabled = true
	env.glow_intensity = 0.35
	env.glow_bloom = 0.04
	env.adjustment_enabled = true
	env.adjustment_saturation = 0.92
	env.adjustment_contrast = 1.04
	env.volumetric_fog_anisotropy = 0.62
	env.volumetric_fog_length = 96.0
	env.volumetric_fog_detail_spread = 2.0
	env.volumetric_fog_gi_inject = 0.6
	world_env = WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)
	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_blend_splits = true
	sun.shadow_bias = 0.03
	sun.shadow_normal_bias = 1.2
	sun.light_volumetric_fog_energy = 1.4
	sun.light_angular_distance = 0.6
	add_child(sun)
	moon = DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = Color(0.55, 0.65, 0.95)
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 60.0
	moon.light_volumetric_fog_energy = 0.4
	moon.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_AND_SKY
	add_child(moon)
	_load_sky_textures()
	Settings.graphics_changed.connect(apply_graphics)
	apply_graphics()


func _load_sky_textures() -> void:
	var base: String = "res://assets/generated/textures/"
	var cloud: Texture2D = load(base + "sky_cloud_noise.png") if ResourceLoader.exists(base + "sky_cloud_noise.png") else null
	if cloud == null:
		var nz := FastNoiseLite.new()
		nz.frequency = 0.006
		nz.fractal_octaves = 6
		var img: Image = nz.get_seamless_image(512, 512)
		img.convert(Image.FORMAT_RGBA8)
		img.generate_mipmaps()
		cloud = ImageTexture.create_from_image(img)
	sky_mat.set_shader_parameter("cloud_tex", cloud)
	var stars: Texture2D = load(base + "sky_stars.png") if ResourceLoader.exists(base + "sky_stars.png") else _fallback_stars()
	sky_mat.set_shader_parameter("star_tex", stars)
	if ResourceLoader.exists(base + "moon_disc.png"):
		sky_mat.set_shader_parameter("moon_tex", load(base + "moon_disc.png"))
	else:
		var m := Image.create(64, 64, false, Image.FORMAT_RGBA8)
		for y: int in 64:
			for x: int in 64:
				var d: float = Vector2(x - 31.5, y - 31.5).length() / 31.5
				m.set_pixel(x, y, Color(0.9, 0.9, 0.85, clampf((1.0 - d) * 8.0, 0.0, 1.0)))
		sky_mat.set_shader_parameter("moon_tex", ImageTexture.create_from_image(m))


static func _fallback_stars() -> Texture2D:
	var img := Image.create(1024, 512, false, Image.FORMAT_RGB8)
	var rng := RandomNumberGenerator.new()
	rng.seed = 4471
	for i: int in 2200:
		var b: float = pow(rng.randf(), 6.0)
		img.set_pixel(rng.randi_range(0, 1023), rng.randi_range(0, 511), Color(b, b, b * 1.1))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func apply_graphics() -> void:
	env.sdfgi_enabled = bool(Settings.gfx("sdfgi", true))
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 4
	env.sdfgi_min_cell_size = 0.25
	env.sdfgi_energy = 0.9
	env.ssao_enabled = bool(Settings.gfx("ssao", true))
	env.ssao_radius = 1.4
	env.ssao_intensity = 2.2
	env.ssil_enabled = bool(Settings.gfx("ssil", false))
	env.ssr_enabled = bool(Settings.gfx("ssr", false))
	env.volumetric_fog_enabled = bool(Settings.gfx("volumetric_fog", true))
	env.glow_enabled = bool(Settings.gfx("glow", true))
	sun.directional_shadow_max_distance = float(Settings.gfx("shadow_distance", 130.0))


func _process(_delta: float) -> void:
	if clock == null:
		return
	update_now()


func update_now() -> void:
	var w: Dictionary = weather.params() if weather != null else {"fog_density": 0.001, "volumetric_density": 0.008, "rain": 0.0, "snow": 0.0, "wind": 0.3, "cloud_cover": 0.3, "wind_dir": Vector2(1, 0), "wetness": 0.0}
	var hour: float = clock.hour_f()
	var elev: float = clock.sun_elevation_deg()
	var a: float = (hour - 12.0) / 12.0 * PI
	var dir_h := Vector3(-sin(a), 0.0, cos(a))
	var el: float = deg_to_rad(elev)
	var sun_dir := Vector3(dir_h.x * cos(el), sin(el), dir_h.z * cos(el)).normalized()
	_orient(sun, sun_dir)
	var moon_dir := Vector3(-sun_dir.x * 0.9 + 0.2, maxf(-sun_dir.y, -0.2) * 0.9 + 0.12, -sun_dir.z * 0.9).normalized()
	_orient(moon, moon_dir)
	var cover: float = float(w["cloud_cover"])
	var day: float = smoothstep(-5.0, 12.0, elev)
	var golden: float = (1.0 - smoothstep(4.0, 22.0, elev)) * smoothstep(-6.0, 1.0, elev)
	var night: float = 1.0 - smoothstep(-12.0, 0.0, elev)
	# Sun light.
	var sun_col: Color = Color(1.0, 0.56, 0.3).lerp(Color(1.0, 0.95, 0.88), smoothstep(2.0, 35.0, elev))
	sun.light_color = sun_col
	sun.light_energy = smoothstep(-3.0, 18.0, elev) * 1.35 * (1.0 - 0.72 * cover)
	sun.visible = elev > -4.0
	sun.shadow_enabled = elev > 0.5
	# Moonlight: faint, cool; clouds kill it.
	var moon_up: float = smoothstep(-2.0, 10.0, rad_to_deg(asin(moon_dir.y)))
	moon.light_energy = 0.065 * moon_up * night * (1.0 - 0.85 * cover)
	moon.visible = moon.light_energy > 0.001
	# Sky.
	var overcast: float = smoothstep(0.55, 1.0, cover)
	var zenith: Color = Color(0.2, 0.34, 0.56).lerp(Color(0.42, 0.45, 0.48), overcast)
	var horizon: Color = Color(0.64, 0.69, 0.74).lerp(Color(0.56, 0.58, 0.6), overcast)
	zenith = zenith.lerp(Color(0.006, 0.009, 0.02), night)
	horizon = horizon.lerp(Color(0.012, 0.016, 0.028), night)
	sky_mat.set_shader_parameter("zenith_color", zenith)
	sky_mat.set_shader_parameter("horizon_color", horizon)
	sky_mat.set_shader_parameter("ground_color", horizon.darkened(0.6))
	sky_mat.set_shader_parameter("sunset_amount", golden * (1.0 - overcast * 0.7))
	sky_mat.set_shader_parameter("night_amount", night)
	sky_mat.set_shader_parameter("cloud_cover", cover)
	sky_mat.set_shader_parameter("cloud_darkness", clampf(float(w["rain"]) + overcast * 0.4, 0.0, 1.0))
	var wd: Vector2 = w["wind_dir"]
	sky_mat.set_shader_parameter("cloud_wind", wd * (0.002 + 0.006 * float(w["wind"])))
	sky_mat.set_shader_parameter("aurora", hum_intensity)
	# Ambient: bright by day, near-black at night (light sources must matter).
	env.ambient_light_energy = lerpf(0.035, 0.85, day) * (1.0 - 0.25 * overcast)
	env.ambient_light_sky_contribution = 0.85
	env.background_energy_multiplier = lerpf(0.25, 1.0, day)
	# Fog: weather + early-morning valley mist.
	var morning_mist: float = smoothstep(4.0, 6.0, hour) * (1.0 - smoothstep(7.5, 10.0, hour)) * 0.004
	var fog_d: float = float(w["fog_density"]) + morning_mist
	env.fog_density = fog_d
	var fog_col: Color = horizon.lerp(sun_col * 0.7, golden * 0.35)
	env.fog_light_color = fog_col
	env.fog_light_energy = lerpf(0.06, 1.0, day)
	env.fog_sun_scatter = 0.25 * day
	env.volumetric_fog_density = float(w["volumetric_density"]) + morning_mist * 3.0 + 0.004
	env.volumetric_fog_albedo = Color(0.88, 0.9, 0.92)
	env.volumetric_fog_emission = Color(0.02, 0.06, 0.04) * hum_intensity
	env.volumetric_fog_emission_energy = hum_intensity * 0.4
	env.volumetric_fog_ambient_inject = lerpf(0.05, 0.4, day)
	env.tonemap_exposure = lerpf(1.25, 1.0, day)
	# Globals for every shader.
	RenderingServer.global_shader_parameter_set(&"hm_wind", Vector4(wd.x, wd.y, float(w["wind"]), 0.3 + 0.5 * float(w["wind"])))
	RenderingServer.global_shader_parameter_set(&"hm_wetness", float(w.get("wetness", 0.0)))
	RenderingServer.global_shader_parameter_set(&"hm_snow", float(w.get("snow", 0.0)))
	RenderingServer.global_shader_parameter_set(&"hm_bloom", hum_intensity)
	RenderingServer.global_shader_parameter_set(&"hm_season", _season_weights())
	_last_snapshot = {"elev": elev, "day": day, "night": night, "cover": cover}


func _season_weights() -> Vector4:
	var idx: int = clock.season_index()
	var p: float = clock.season_progress()
	var w := [0.0, 0.0, 0.0, 0.0]
	# Blend into the next season over the last 25% of each season.
	var blend: float = smoothstep(0.75, 1.0, p)
	w[idx] = 1.0 - blend
	w[(idx + 1) % 4] += blend
	return Vector4(w[0], w[1], w[2], w[3])


## Light level of the sky at the moment (0 dark night .. 1 bright day), used by stealth/visibility.
func ambient_light_level() -> float:
	return float(_last_snapshot.get("day", 1.0)) * (1.0 - 0.3 * float(_last_snapshot.get("cover", 0.0)))


static func _orient(light: DirectionalLight3D, toward_light: Vector3) -> void:
	var up: Vector3 = Vector3.UP if absf(toward_light.y) < 0.98 else Vector3.FORWARD
	light.basis = Basis.looking_at(-toward_light, up)
