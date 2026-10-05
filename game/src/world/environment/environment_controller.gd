class_name EnvironmentController
extends Node3D
## Sky, sun/moon, ambient, fog, volumetric fog, GI and post-processing driven by the world clock,
## weather and the graphics preset. Also publishes the hm_* global shader parameters.
## Night is meant to be genuinely dark, and no two nights alike: the moon (MoonModel, ADR-0023)
## orbits with phases, and the night's ambient light, sky and stars run from a near-black new moon
## to a readable full moon over the range in data/config/world_clock.json "moon".

var clock: WorldClock
var weather: WeatherState
var hum_intensity: float = 0.0

var env: Environment
var world_env: WorldEnvironment
var sun: DirectionalLight3D
var moon: DirectionalLight3D
var sky_mat: ShaderMaterial
var moon_model := MoonModel.new()
## The moon now: phase (0 new .. 0.5 full), lit fraction, light relative to full, altitude in
## degrees, how much moonlight is in the sky (0..1) and the phase's name.
var moon_state: Dictionary = {}
var _moon_cfg: Dictionary = {}
var _last_snapshot: Dictionary = {}


func _ready() -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky_mat = ShaderMaterial.new()
	sky_mat.shader = load("res://assets/shaders/sky.gdshader")
	sky.sky_material = sky_mat
	# Realtime skies always render a 256 radiance map (a smaller size is overridden, with a warning).
	sky.radiance_size = Sky.RADIANCE_SIZE_256
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
	# The sky shader draws the moon from uniforms; as a sky light it would take the hidden sun's
	# LIGHT0 slot at night.
	moon.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	moon.light_angular_distance = 0.5
	add_child(moon)
	_moon_cfg = (Content.config(&"world_clock").get("moon", {}) as Dictionary)
	moon_model.configure(_moon_cfg)
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


func _process(delta: float) -> void:
	if clock == null:
		return
	# The Hum's glow (aurora, green fog, Bloom veins) builds through the last three hours before
	# it and peaks while it runs; it was never driven at all.
	var hum_target: float = 1.0 if clock.is_horde_active() else 0.35 * (1.0 - smoothstep(0.0, 3.0, clock.hours_until_horde()))
	hum_intensity = move_toward(hum_intensity, hum_target, delta * 0.05)
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
	var cover: float = float(w["cloud_cover"])
	var day: float = smoothstep(-5.0, 12.0, elev)
	# Ambient follows twilight down to -10 degrees: it used to hit its night floor at -5 while the
	# sky still glowed, so the world went black under a bright dusk sky.
	var dusk: float = smoothstep(-10.0, 12.0, elev)
	var golden: float = (1.0 - smoothstep(4.0, 22.0, elev)) * smoothstep(-6.0, 1.0, elev)
	var night: float = 1.0 - smoothstep(-12.0, 0.0, elev)
	# Sun light.
	var sun_col: Color = Color(1.0, 0.56, 0.3).lerp(Color(1.0, 0.95, 0.88), smoothstep(2.0, 35.0, elev))
	sun.light_color = sun_col
	sun.light_energy = smoothstep(-3.0, 18.0, elev) * 1.35 * (1.0 - 0.72 * cover)
	sun.visible = elev > -4.0
	sun.shadow_enabled = elev > 0.5
	# The sky is drawn dimmer at night (background energy); the moon's disc is not.
	var bg_energy: float = lerpf(0.25, 1.0, day)
	var moon_sky: float = _update_moon(sun_dir, night, day, cover, bg_energy)
	# Sky. Night colours run from the new-moon black to a moonlit deep blue.
	var overcast: float = smoothstep(0.55, 1.0, cover)
	var zenith: Color = Color(0.2, 0.34, 0.56).lerp(Color(0.42, 0.45, 0.48), overcast)
	var horizon: Color = Color(0.64, 0.69, 0.74).lerp(Color(0.56, 0.58, 0.6), overcast)
	var night_zenith: Color = _moon_color("night_zenith_new", "#020307").lerp(_moon_color("night_zenith_full", "#0b1630"), moon_sky)
	var night_horizon: Color = _moon_color("night_horizon_new", "#05070d").lerp(_moon_color("night_horizon_full", "#1a2741"), moon_sky)
	zenith = zenith.lerp(night_zenith, night)
	horizon = horizon.lerp(night_horizon, night)
	sky_mat.set_shader_parameter("zenith_color", zenith)
	sky_mat.set_shader_parameter("horizon_color", horizon)
	sky_mat.set_shader_parameter("ground_color", horizon.darkened(0.6))
	sky_mat.set_shader_parameter("sunset_amount", golden * (1.0 - overcast * 0.7))
	sky_mat.set_shader_parameter("night_amount", night)
	sky_mat.set_shader_parameter("cloud_cover", cover)
	sky_mat.set_shader_parameter("cloud_darkness", clampf(float(w["rain"]) + overcast * 0.4, 0.0, 1.0))
	sky_mat.set_shader_parameter("sun_dir", sun_dir)
	sky_mat.set_shader_parameter("sun_color", Vector3(sun_col.r, sun_col.g, sun_col.b))
	sky_mat.set_shader_parameter("sun_energy", sun.light_energy)
	var wd: Vector2 = w["wind_dir"]
	sky_mat.set_shader_parameter("cloud_wind", wd * (0.002 + 0.006 * float(w["wind"])))
	sky_mat.set_shader_parameter("aurora", hum_intensity)
	# Ambient: bright by day; at night the moonlit (or moonless) fill from data, plus the Bloom
	# aurora's green during the Hum. At night the fill comes from the ambient colour rather than
	# the near-black sky, so the darkness range in data is what the player gets.
	var night_fill: float = lerpf(float(_moon_cfg.get("night_ambient_new", 0.03)), float(_moon_cfg.get("night_ambient_full", 0.11)), moon_sky)
	var hum_fill: float = float(_moon_cfg.get("hum_ambient", 0.05)) * hum_intensity
	var night_col: Color = _moon_color("night_ambient_color", "#5c6f99")
	if hum_fill > 0.0:
		night_col = night_col.lerp(_moon_color("hum_ambient_color", "#5fae86"), hum_fill / (night_fill + hum_fill))
	env.ambient_light_color = Color.BLACK.lerp(night_col, night)
	env.ambient_light_sky_contribution = lerpf(0.85, 0.25, night)
	env.ambient_light_energy = lerpf((night_fill + hum_fill) / 0.75, 1.05, dusk) * (1.0 - 0.25 * overcast)
	# Building interiors: a dim daylight fill from their interior probes (PoiBuilder), none at night.
	var interior_fill: float = lerpf(0.0, 0.55, day) * (1.0 - 0.3 * overcast)
	for probe: Node in get_tree().get_nodes_in_group(&"interior_probe"):
		(probe as ReflectionProbe).ambient_color_energy = interior_fill
	env.background_energy_multiplier = bg_energy
	# Fog: weather + early-morning valley mist.
	# A thin valley mist at dawn that burns off by mid-morning (weather fog adds on top).
	var morning_mist: float = smoothstep(4.0, 6.0, hour) * (1.0 - smoothstep(7.0, 9.5, hour)) * 0.0012
	var fog_d: float = float(w["fog_density"]) * 0.6 + morning_mist
	# A light floor of haze keeps sun shafts in the canopy; on a clear noon it veils a pond's far
	# shore by under a fifth.
	var vol_d: float = float(w["volumetric_density"]) * 0.5 + morning_mist * 2.0 + 0.001
	if not env.volumetric_fog_enabled:
		# Low preset has no froxel fog: carry mist weather and dawn haze in the depth fog instead
		# (they vanished entirely).
		fog_d += (vol_d - 0.001) * 0.12
	env.fog_density = fog_d
	var fog_col: Color = horizon.lerp(sun_col * 0.7, golden * 0.35)
	env.fog_light_color = fog_col
	env.fog_light_energy = lerpf(0.06 + 0.12 * moon_sky, 1.0, day)
	env.fog_sun_scatter = 0.25 * day
	env.volumetric_fog_density = vol_d
	env.volumetric_fog_albedo = Color(0.88, 0.9, 0.92)
	env.volumetric_fog_emission = Color(0.02, 0.06, 0.04) * hum_intensity
	env.volumetric_fog_emission_energy = hum_intensity * 0.4
	env.volumetric_fog_ambient_inject = lerpf(0.05, 0.4, day)
	env.tonemap_exposure = lerpf(1.25, 1.1, day) * Settings.brightness
	# Globals for every shader.
	RenderingServer.global_shader_parameter_set(&"hm_wind", Vector4(wd.x, wd.y, float(w["wind"]), 0.3 + 0.5 * float(w["wind"])))
	RenderingServer.global_shader_parameter_set(&"hm_wetness", float(w.get("wetness", 0.0)))
	# Snow on surfaces is the accumulated cover, not the snowfall (it stays after the snow stops).
	RenderingServer.global_shader_parameter_set(&"hm_snow", float(w.get("snow_cover", w.get("snow", 0.0))))
	RenderingServer.global_shader_parameter_set(&"hm_bloom", hum_intensity)
	RenderingServer.global_shader_parameter_set(&"hm_season", _season_weights())
	# The sky gradient as linear radiance, for surfaces that fake their own reflections (water).
	var sky_e: float = env.background_energy_multiplier
	var zl: Color = zenith.srgb_to_linear() * sky_e
	var hl: Color = horizon.lerp(sun_col, golden * 0.3).srgb_to_linear() * sky_e
	RenderingServer.global_shader_parameter_set(&"hm_sky_zenith", Vector4(zl.r, zl.g, zl.b, 1.0))
	RenderingServer.global_shader_parameter_set(&"hm_sky_horizon", Vector4(hl.r, hl.g, hl.b, 1.0))
	_last_snapshot = {"elev": elev, "day": day, "night": night, "cover": cover, "moon_sky": moon_sky}


## Places the moon, sets its light by phase and altitude and feeds the sky shader (ADR-0023).
## Returns how much moonlight is in the night sky (0 new moon or set .. 1 high full moon).
func _update_moon(sun_dir: Vector3, night: float, day: float, cover: float, bg_energy: float) -> float:
	var moon_dir: Vector3 = moon_model.direction(clock)
	_orient(moon, moon_dir)
	var phase: float = moon_model.phase_at(clock.total_minutes)
	var illum: float = MoonModel.illuminated(phase)
	var bright: float = moon_model.brightness(phase)
	var alt: float = rad_to_deg(asin(clampf(moon_dir.y, -1.0, 1.0)))
	var up: float = smoothstep(-1.0, 8.0, alt)
	# A low moon shines through more air: dimmer and warmer.
	var high: float = smoothstep(4.0, 30.0, alt)
	var col: Color = _moon_color("color_crescent", "#93a7d6").lerp(_moon_color("color_full", "#b9c7e6"), illum)
	col = _moon_color("color_low", "#d9b98f").lerp(col, high)
	moon.light_color = col
	moon.light_energy = float(_moon_cfg.get("energy_full", 0.2)) * bright * up * lerpf(0.55, 1.0, high) * night * (1.0 - 0.85 * cover)
	moon.visible = moon.light_energy > 0.0015
	moon.shadow_enabled = moon.light_energy > 0.02
	var moon_sky: float = bright * smoothstep(-6.0, 12.0, alt) * (1.0 - 0.6 * cover)
	sky_mat.set_shader_parameter("moon_dir", moon_dir)
	sky_mat.set_shader_parameter("moon_sun_dir", MoonModel.sunlight_at_moon(moon_dir, sun_dir, phase))
	sky_mat.set_shader_parameter("moon_radius", deg_to_rad(float(_moon_cfg.get("disc_degrees", 3.2)) * 0.5))
	sky_mat.set_shader_parameter("moon_illum", illum)
	sky_mat.set_shader_parameter("moon_color", Vector3(col.r, col.g, col.b))
	sky_mat.set_shader_parameter("moon_disc_energy", lerpf(float(_moon_cfg.get("disc_energy", 2.2)), float(_moon_cfg.get("disc_energy_day", 0.45)), day) / bg_energy)
	sky_mat.set_shader_parameter("earthshine", float(_moon_cfg.get("earthshine", 0.05)))
	sky_mat.set_shader_parameter("moon_glow", float(_moon_cfg.get("glow", 0.35)) * bright * up * night / bg_energy)
	sky_mat.set_shader_parameter("moon_sky", moon_sky * night)
	sky_mat.set_shader_parameter("star_visibility", 1.0 - float(_moon_cfg.get("star_fade_full", 0.72)) * moon_sky)
	sky_mat.set_shader_parameter("star_rotation", star_basis(clock, moon_model.latitude_deg))
	moon_state = {"phase": phase, "illuminated": illum, "brightness": bright, "altitude": alt, "sky": moon_sky,
		"name": MoonModel.phase_name(phase)}
	return moon_sky


## The star sphere's turn: about the celestial pole (north, `latitude` up) once a sidereal day,
## which is a day less a year's worth (one turn more per year than the sun makes). Maps a view
## direction to its place on the star texture.
static func star_basis(c: WorldClock, latitude: float) -> Basis:
	var year_days: float = float(c.season_length_days * maxi(1, c.season_order.size()))
	var sidereal: float = WorldClock.MIN_PER_DAY * year_days / (year_days + 1.0)
	var lat: float = deg_to_rad(latitude)
	var pole := Vector3(0.0, sin(lat), -cos(lat))
	return Basis(pole, TAU * fposmod(c.total_minutes / sidereal, 1.0))


func _moon_color(key: String, fallback: String) -> Color:
	return Color.html(str(_moon_cfg.get(key, fallback)))


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
## A full moon lifts the night a little.
func ambient_light_level() -> float:
	var sky: float = float(_last_snapshot.get("day", 1.0)) * (1.0 - 0.3 * float(_last_snapshot.get("cover", 0.0)))
	return maxf(sky, 0.15 * float(_last_snapshot.get("moon_sky", 0.0)) * float(_last_snapshot.get("night", 0.0)))


static func _orient(light: DirectionalLight3D, toward_light: Vector3) -> void:
	var up: Vector3 = Vector3.UP if absf(toward_light.y) < 0.98 else Vector3.FORWARD
	light.basis = Basis.looking_at(-toward_light, up)
