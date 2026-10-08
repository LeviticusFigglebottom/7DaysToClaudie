class_name EnvironmentController
extends Node3D
## Sky, sun/moon, ambient, fog, volumetric fog, GI and post-processing driven by the world clock,
## weather and the graphics preset. Also publishes the hm_* global shader parameters.
## Night is meant to be genuinely dark, and no two nights alike: the moon (MoonModel, ADR-0023)
## orbits with phases, and the night's ambient light, sky and stars run from a near-black new moon
## to a readable full moon over the range in data/config/world_clock.json "moon".
## Weather (ADR-0033, numbers in data/config/weather.json): lightning flashes the sky and throws a
## brief hard shadow from the strike, its thunder following at the speed of sound; ground fog pools
## in hollows and over water at dawn and dusk; rain hangs a grey haze; gusts drive the foliage and the
## rain. The precipitation, the weather map and the motes are WeatherFx's.
## The biome round the camera tints the fog (its `fog_tint` against the conifer forest's, so the
## forest looks as it always did), and a fen pools deeper, thicker ground fog (ADR-0047). Both are
## sampled twice a second at five points and eased over a few seconds, so they cost nothing.

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
## data/config/weather.json.
var _wcfg: Dictionary = {}
## The lightning's light: a hard-shadowed directional light from the cloud base over the strike,
## shown only while a flash lasts.
var flash_light: DirectionalLight3D
## How bright the lightning is now (0 .. ~1 at a near strike's first stroke), and the strike
## lighting the sky.
var flash: float = 0.0
var flash_strike: Dictionary = {}
## Strikes still flashing: {"strike": Dictionary, "t0": real seconds when it began}.
var _strikes: Array[Dictionary] = []
## > 0 holds the last strike's flash at this brightness (QA renders, whose frames take seconds).
var flash_hold: float = 0.0
var _last_minutes: float = -1.0
var _real_t: float = 0.0
## Ground fog now (0 none .. ~2 thick dawn mist), and the level it fills to far from the camera.
var ground_fog: float = 0.0
var fog_volume: FogVolume
var _fog_mat: ShaderMaterial
## The fog's colour multiplier from the biomes round the camera (white: as the reference biome), and
## how much of that ground is fen (0..1), both eased toward the last sample (ADR-0047).
var biome_tint: Color = Color.WHITE
var fen_weight: float = 0.0
var _tint_target: Color = Color.WHITE
var _fen_target: float = 0.0
var _biome_check: float = 0.0
## Biome id -> [fog tint multiplier, is fen], filled on first use.
var _biome_fog: Dictionary = {}
## Seconds between biome samples; the ease's time constant.
const BIOME_CHECK: float = 0.5
## How much the eye is inside a building's room (0 outdoors .. 1 inside one), eased: it opens the
## exposure indoors (data/config/interior_light.json).
var indoors: float = 0.0
var _interior_cfg: Dictionary = {}
const BIOME_EASE: float = 3.0
## Rain, snow, splashes, eave drips and motes round the camera, and the weather map.
var fx: WeatherFx


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
	_wcfg = Content.config(&"weather")
	_interior_cfg = Content.config(&"interior_light")
	flash_light = DirectionalLight3D.new()
	flash_light.name = "Lightning"
	flash_light.light_color = Color(0.82, 0.86, 1.0)
	flash_light.shadow_enabled = true
	# A point-like bolt: a hard shadow edge, and one split is plenty for a tenth of a second.
	flash_light.light_angular_distance = 0.0
	flash_light.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	flash_light.directional_shadow_max_distance = 80.0
	flash_light.shadow_bias = 0.04
	flash_light.light_volumetric_fog_energy = 2.0
	flash_light.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	flash_light.visible = false
	add_child(flash_light)
	_load_sky_textures()
	_publish_surface_tables()
	if DisplayServer.get_name() != "headless":
		_make_fog_volume()
	fx = WeatherFx.new()
	fx.name = "WeatherFx"
	fx.env = self
	add_child(fx)
	Settings.graphics_changed.connect(apply_graphics)
	apply_graphics()


func _load_sky_textures() -> void:
	var base: String = "res://assets/generated/textures/"
	var cloud: Texture2D = load(base + "sky_cloud_noise.png") if ResourceLoader.exists(base + "sky_cloud_noise.png") else _fallback_clouds()
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


## The stand-in cloud noise (no generated assets), kept for the process so a reload reuses it.
static var _clouds: ImageTexture = null
## The worker task making its image, until _exit_tree joins it.
static var _cloud_task: int = -1


## A flat grey now, the noise once a worker has made it (TD-197): the 512² seamless noise with
## mipmaps is ~120 ms, which was nearly all of the boot's `environment` step. set_image runs on
## the main thread (call_deferred from the worker), as WaterSystem's stand-in normal maps do.
static func _fallback_clouds() -> Texture2D:
	if _clouds != null:
		return _clouds
	var flat := Image.create_empty(1, 1, false, Image.FORMAT_RGBA8)
	flat.fill(Color(0.5, 0.5, 0.5))
	var tex := ImageTexture.create_from_image(flat)
	_clouds = tex
	_cloud_task = WorkerThreadPool.add_task(func() -> void:
		tex.set_image.call_deferred(_cloud_image()), false, "sky clouds")
	return tex


static func _cloud_image() -> Image:
	var nz := FastNoiseLite.new()
	nz.frequency = 0.006
	nz.fractal_octaves = 6
	var img: Image = nz.get_seamless_image(512, 512)
	img.convert(Image.FORMAT_RGBA8)
	img.generate_mipmaps()
	return img


func _exit_tree() -> void:
	if _cloud_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_cloud_task)
		_cloud_task = -1


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
	_real_t += delta
	_biome_check -= delta
	if _biome_check <= 0.0:
		_biome_check = BIOME_CHECK
		_sample_biomes()
	var eased: float = 1.0 - exp(-delta / BIOME_EASE)
	biome_tint = biome_tint.lerp(_tint_target, eased)
	fen_weight = lerpf(fen_weight, _fen_target, eased)
	_update_lightning()
	var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	var inside: float = 1.0 if cam != null and in_interior(cam.global_position) else 0.0
	indoors = move_toward(indoors, inside, delta / maxf(0.05, float(_interior_cfg.get("adapt_seconds", 1.2))))
	update_now()


func update_now() -> void:
	var w: Dictionary = weather.params() if weather != null else {"fog_density": 0.001, "volumetric_density": 0.008, "rain": 0.0, "snow": 0.0, "wind": 0.3,
		"cloud_cover": 0.3, "wind_dir": Vector2(1, 0), "wetness": 0.0, "gust": 0.25, "ground_fog": 1.0, "haze": 0.0}
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
	if weather != null:
		# Drying runs on the sun (WeatherState.daylight).
		weather.daylight = day * (1.0 - 0.8 * cover)
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
	# Lightning: the cloud deck lights up, most of all over the strike, and a near enough strike
	# draws its bolt.
	var lf: Dictionary = _wcfg.get("lightning", {}) as Dictionary
	var fdir: Vector3 = LightningModel.light_direction(flash_strike) if not flash_strike.is_empty() else Vector3.UP
	var fdist: float = float(flash_strike.get("distance", 1e9))
	# Like the moon's disc, the flash is not dimmed with the night sky's background energy.
	sky_mat.set_shader_parameter("lightning", flash * float(lf.get("sky_flash", 3.0)) / bg_energy)
	sky_mat.set_shader_parameter("lightning_dir", fdir)
	sky_mat.set_shader_parameter("bolt", (flash if fdist < float(lf.get("bolt_within_m", 6000.0)) else 0.0) / bg_energy)
	sky_mat.set_shader_parameter("bolt_seed", float(int(flash_strike.get("shape", 0)) % 997))
	sky_mat.set_shader_parameter("bolt_distance", fdist)
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
	# The whole sky lights up in a flash: a cold fill, strongest at night against the dark.
	_update_flash_light(fdir, fdist, lf)
	if flash > 0.001:
		var fill: float = flash * float(lf.get("light_energy", 2.2)) * 0.35 * _flash_reach(fdist, lf)
		env.ambient_light_color = env.ambient_light_color.lerp(Color(0.72, 0.78, 1.0), clampf(fill * 2.0, 0.0, 1.0))
		env.ambient_light_energy += fill
	# Building interiors: their probes' flat fill (PoiBuilder), daylight by day and a share of the
	# night's ambient at night.
	var room_fill: Color = interior_fill(_interior_cfg, day, overcast, night_fill + hum_fill, night_col)
	if flash > 0.001:
		# A flash through the windows lights the room too, a little.
		var ff: float = flash * float(lf.get("light_energy", 2.2)) * float(_interior_cfg.get("flash_share", 0.12)) * _flash_reach(fdist, lf)
		var fc: Color = Color(room_fill.r, room_fill.g, room_fill.b).lerp(Color(0.72, 0.78, 1.0), clampf(ff / (ff + room_fill.a), 0.0, 1.0))
		room_fill = Color(fc.r, fc.g, fc.b, room_fill.a + ff)
	var floor_e: float = float(_interior_cfg.get("night_floor", 0.012))
	for probe: Node in get_tree().get_nodes_in_group(&"interior_probe"):
		var share: float = daylight_share(_interior_cfg, float(probe.get_meta(&"daylight")) if probe.has_meta(&"daylight") else -1.0,
			float(probe.get_meta(&"min_share")) if probe.has_meta(&"min_share") else -1.0)
		(probe as ReflectionProbe).ambient_color = Color(room_fill.r, room_fill.g, room_fill.b)
		(probe as ReflectionProbe).ambient_color_energy = maxf(floor_e, room_fill.a * share)
	env.background_energy_multiplier = bg_energy
	# Fog: weather + early-morning valley mist.
	# A thin haze at dawn that burns off by mid-morning (weather fog adds on top); the mist itself
	# lies in the low ground (ground fog, below).
	var morning_mist: float = smoothstep(4.0, 6.0, hour) * (1.0 - smoothstep(7.0, 9.5, hour)) * 0.0006
	# Rain and snow hang a grey haze in the air (the weather's haze, by how hard it falls now).
	var fall: float = clampf(float(w["rain"]) + float(w["snow"]), 0.0, 1.0)
	var haze: float = float(w.get("haze", 0.0))
	var fog_d: float = float(w["fog_density"]) * 0.6 + morning_mist + haze
	# A light floor of haze keeps sun shafts in the canopy; on a clear noon it veils a pond's far
	# shore by under a fifth.
	var vol_d: float = float(w["volumetric_density"]) * 0.5 + morning_mist * 2.0 + 0.001
	if not env.volumetric_fog_enabled:
		# Low preset has no froxel fog: carry mist weather and dawn haze in the depth fog instead
		# (they vanished entirely).
		fog_d += (vol_d - 0.001) * 0.12
	env.fog_density = fog_d
	var fog_col: Color = horizon.lerp(sun_col * 0.7, golden * 0.35)
	# Haze in rain is grey water in the air, not blue distance.
	fog_col = fog_col.lerp(Color(0.6, 0.62, 0.64).lerp(horizon, 0.5), fall * 0.6)
	# The biome round the camera: a burn's dusty warmth, a fen's grey-green (ADR-0047).
	fog_col *= biome_tint
	env.fog_light_color = fog_col
	env.fog_light_energy = lerpf(0.06 + 0.12 * moon_sky, 1.0, day) + flash * 0.6 * _flash_reach(fdist, lf)
	env.fog_sun_scatter = 0.25 * day
	_update_ground_fog(w, hour, day, fog_col, sun_col, golden)
	env.volumetric_fog_density = vol_d
	env.volumetric_fog_albedo = Color(0.88, 0.9, 0.92) * biome_tint
	env.volumetric_fog_emission = Color(0.02, 0.06, 0.04) * hum_intensity
	env.volumetric_fog_emission_energy = hum_intensity * 0.4
	env.volumetric_fog_ambient_inject = lerpf(0.05, 0.4, day)
	env.tonemap_exposure = lerpf(1.25, 1.1, day) * Settings.brightness * indoor_exposure(_interior_cfg, day, indoors)
	# Globals for every shader.
	# Gusts in seconds over the state's slow swell: the foliage bends and the rain slants with them.
	var gust_mul: float = WeatherState.gust_at(clock.total_minutes / maxf(0.001, clock.minutes_per_real_second()), float(w.get("gust", 0.25)))
	var wind_now: float = clampf(float(w["wind"]) * gust_mul, 0.0, 1.0)
	RenderingServer.global_shader_parameter_set(&"hm_wind", Vector4(wd.x, wd.y, wind_now, 0.3 + 0.5 * float(w["wind"])))
	RenderingServer.global_shader_parameter_set(&"hm_wetness", float(w.get("wetness", 0.0)))
	# Rainfall now, standing water, the lightning and snowfall now (weather.gdshaderinc).
	RenderingServer.global_shader_parameter_set(&"hm_rain", Vector4(float(w["rain"]), float(w.get("puddles", 0.0)), flash, float(w["snow"])))
	if fx != null:
		fx.update_weather(w, wind_now, day, flash)
	# Snow on surfaces is the accumulated cover, not the snowfall (it stays after the snow stops).
	RenderingServer.global_shader_parameter_set(&"hm_snow", float(w.get("snow_cover", w.get("snow", 0.0))))
	RenderingServer.global_shader_parameter_set(&"hm_bloom", hum_intensity)
	RenderingServer.global_shader_parameter_set(&"hm_season", _season_weights())
	# The sky gradient as linear radiance, for surfaces that fake their own reflections (water).
	var sky_e: float = env.background_energy_multiplier
	var zl: Color = zenith.srgb_to_linear() * sky_e
	var hl: Color = horizon.lerp(sun_col, golden * 0.3).srgb_to_linear() * sky_e
	# Water and wet ground mirror the flash.
	var fl: float = flash * float(lf.get("sky_flash", 3.0)) * 0.12 * _flash_reach(fdist, lf)
	zl += Color(0.7, 0.75, 0.95) * fl
	hl += Color(0.7, 0.75, 0.95) * fl * 1.4
	RenderingServer.global_shader_parameter_set(&"hm_sky_zenith", Vector4(zl.r, zl.g, zl.b, 1.0))
	RenderingServer.global_shader_parameter_set(&"hm_sky_horizon", Vector4(hl.r, hl.g, hl.b, 1.0))
	_last_snapshot = {"elev": elev, "day": day, "night": night, "cover": cover, "moon_sky": moon_sky}


## The interior probes' fill: colour in rgb, energy in a. By day `day_fill` of `day_color`, dimmed
## by overcast; at night `night_share` of the outdoor night's ambient energy (`night_energy`, in its
## colour); never below `night_floor`.
static func interior_fill(cfg: Dictionary, day: float, overcast: float, night_energy: float, night_col: Color) -> Color:
	var day_col: Color = Color.html(str(cfg.get("day_color", "#dbd4c7")))
	var day_e: float = float(cfg.get("day_fill", 0.6)) * (1.0 - float(cfg.get("overcast_dim", 0.3)) * overcast)
	var night_e: float = maxf(float(cfg.get("night_floor", 0.012)), float(cfg.get("night_share", 0.6)) * night_energy)
	var col: Color = night_col.lerp(day_col, day)
	return Color(col.r, col.g, col.b, lerpf(night_e, day_e, day))


## How much of the interior fill a room gets by its daylight ratio (PoiBuilder.daylight_ratio:
## outside openings per floor area): `daylight_min_share` with none, all of it from
## `daylight_full_ratio` up. A probe with no ratio (-1) gets all of it. `min_share` (a probe's meta,
## >= 0) stands in for `daylight_min_share`: a cave's (CaveLighting) is darker than a cellar's.
static func daylight_share(cfg: Dictionary, ratio: float, min_share: float = -1.0) -> float:
	if ratio < 0.0:
		return 1.0
	var lo: float = min_share if min_share >= 0.0 else float(cfg.get("daylight_min_share", 0.2))
	return lerpf(lo, 1.0, clampf(ratio / maxf(0.001, float(cfg.get("daylight_full_ratio", 0.1))), 0.0, 1.0))


## The exposure multiplier for an eye `indoors` (0..1) inside a room: exposure_day by day,
## exposure_night at night.
static func indoor_exposure(cfg: Dictionary, day: float, inside: float) -> float:
	var open: float = lerpf(float(cfg.get("exposure_night", 1.1)), float(cfg.get("exposure_day", 1.3)), day)
	return lerpf(1.0, open, clampf(inside, 0.0, 1.0))


## Whether `eye` is inside a live interior probe's box: in one of the buildings' rooms.
func in_interior(eye: Vector3) -> bool:
	for n: Node in get_tree().get_nodes_in_group(&"interior_probe"):
		var p := n as ReflectionProbe
		if p == null or not p.visible:
			continue
		var local: Vector3 = p.global_transform.affine_inverse() * eye
		var h: Vector3 = p.size * 0.5
		if absf(local.x) <= h.x and absf(local.y) <= h.y and absf(local.z) <= h.z:
			return true
	return false


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


# --- Lightning (ADR-0033) -------------------------------------------------------------------------

## Starts the strikes the clock passed since the last frame (LightningModel: a pure function of the
## seed and the game clock) and works out how bright the sky is now. A big step of the clock
## (sleep, a loaded save) flashes nothing: a night's storm would go off at once.
func _update_lightning() -> void:
	var now: float = clock.total_minutes
	var lf: Dictionary = _wcfg.get("lightning", {}) as Dictionary
	if weather != null and _last_minutes >= 0.0 and now > _last_minutes and now - _last_minutes < 2.0:
		var rate: float = float(weather.params().get("lightning", 0.0))
		var sd: int = Game.session.world_seed if Game.session != null else 0
		for s: Dictionary in LightningModel.strikes_between(sd, _last_minutes, now, rate, lf):
			_begin_strike(s)
	_last_minutes = now
	flash = 0.0
	var keep: Array[Dictionary] = []
	for e: Dictionary in _strikes:
		var st: Dictionary = e["strike"]
		var since: float = _real_t - float(e["t0"])
		if since > LightningModel.duration(st, lf):
			continue
		keep.append(e)
		# Far strikes light only their own corner of the cloud deck.
		var f: float = LightningModel.flash(st, since, lf) * lerpf(0.35, 1.0, _flash_reach(float(st["distance"]), lf))
		if f > flash:
			flash = f
			flash_strike = st
	_strikes = keep
	if flash_hold > 0.0 and not flash_strike.is_empty():
		flash = flash_hold


## A strike now, `bearing` radians round from +X and `distance` metres off (QA shots, debug and
## scripted moments); it flashes and thunders like any other.
func strike_now(bearing: float, distance: float, strokes: int = 3) -> void:
	var offsets: PackedFloat32Array = [0.0]
	for k: int in range(1, maxi(1, strokes)):
		offsets.append(0.09 * float(k))
	var s: Dictionary = {"slot": -1, "at_min": clock.total_minutes if clock != null else 0.0, "bearing": bearing, "distance": distance,
		"strokes": offsets, "shape": 4471}
	_begin_strike(s)
	# A held flash (flash_hold) shows this strike even if a slow frame outlasts it.
	flash_strike = s


func _begin_strike(s: Dictionary) -> void:
	_strikes.append({"strike": s, "t0": _real_t})
	var delay: float = LightningModel.thunder_delay(float(s["distance"]), _wcfg.get("lightning", {}) as Dictionary)
	if is_inside_tree():
		get_tree().create_timer(delay, false).timeout.connect(_thunder.bind(float(s["distance"])))


## 1 for a strike close by, fading to 0 at light_far_m.
static func _flash_reach(distance: float, lf: Dictionary) -> float:
	return 1.0 - smoothstep(600.0, float(lf.get("light_far_m", 6000.0)), distance)


## The flash's light: from the cloud base over the strike, hard-shadowed, only while it flashes.
func _update_flash_light(dir: Vector3, distance: float, lf: Dictionary) -> void:
	var e: float = flash * float(lf.get("light_energy", 2.2)) * _flash_reach(distance, lf)
	flash_light.visible = e > 0.01
	if flash_light.visible:
		_orient(flash_light, dir)
		flash_light.light_energy = e


## Thunder for a strike `distance` metres off, arriving now: a crack and rumble close by, a low roll
## from far off, quieter with distance and muffled indoors.
func _thunder(distance: float) -> void:
	var lf: Dictionary = _wcfg.get("lightning", {}) as Dictionary
	var near_m: float = float(lf.get("thunder_near_m", 1600.0))
	var dbs: Array = lf.get("thunder_db", [0.0, -22.0])
	var dr: Array = lf.get("distance_m", [350.0, 9000.0])
	var t: float = clampf(log(maxf(distance, 1.0) / float(dr[0])) / log(maxf(float(dr[1]) / float(dr[0]), 1.001)), 0.0, 1.0)
	var db: float = lerpf(float(dbs[0]), float(dbs[1]), t)
	var w: Node = Game.world
	var pl: Node3D = w.get(&"player") as Node3D if w != null else null
	var pois: Node = w.get(&"pois") as Node if w != null else null
	if pl != null and pois != null and bool(pois.call(&"is_indoors", pl.global_position)):
		db -= 8.0
	Audio.play_2d(&"amb/thunder_near" if distance < near_m else &"amb/thunder_far", db, &"Ambience", randf_range(0.92, 1.05))


# --- Fog (ADR-0033) ------------------------------------------------------------------------------

## How much ground fog the hour brings, 0..1 (x the weather's ground_fog and the calm): it gathers
## at dusk, deepens through the night, peaks at sunrise and burns off through the morning.
static func ground_fog_at(hour: float, sunrise: float, sunset: float, fcfg: Dictionary) -> float:
	var dawn: Array = fcfg.get("dawn", [-1.5, 3.2])
	var dusk_s: float = float(fcfg.get("dusk_strength", 0.55))
	if hour >= sunset:
		return dusk_s * smoothstep(sunset, sunset + float(fcfg.get("dusk_hours", 2.5)), hour)
	if hour <= sunrise:
		# The small hours: from the dusk level to full at sunrise, building through the last hours.
		return lerpf(dusk_s, 1.0, smoothstep(sunrise + float(dawn[0]) - 2.0, sunrise, hour))
	return 1.0 - smoothstep(sunrise, sunrise + float(dawn[1]), hour)


func _make_fog_volume() -> void:
	fog_volume = FogVolume.new()
	fog_volume.name = "GroundFog"
	fog_volume.shape = RenderingServer.FOG_VOLUME_SHAPE_BOX
	var vs: Array = (_wcfg.get("fog", {}) as Dictionary).get("volume_size", [200.0, 60.0])
	fog_volume.size = Vector3(float(vs[0]), float(vs[1]), float(vs[0]))
	_fog_mat = ShaderMaterial.new()
	_fog_mat.shader = load("res://assets/shaders/ground_fog.gdshader")
	fog_volume.material = _fog_mat
	fog_volume.visible = false
	add_child(fog_volume)


## Ground fog for the hour, the weather and the wind: a volume round the camera (High and up) that
## fills the low ground to the local fog level, and the depth fog's height falloff under the same
## level for everything beyond it (and on Low). God rays come from the sun through this fog.
func _update_ground_fog(w: Dictionary, hour: float, day: float, fog_col: Color, sun_col: Color, golden: float) -> void:
	var fc: Dictionary = _wcfg.get("fog", {}) as Dictionary
	var calm: float = 1.0 - smoothstep(float(fc.get("calm_wind", 0.55)) * 0.4, float(fc.get("calm_wind", 0.55)), float(w["wind"]))
	# A misty state (ground_fog over 1) keeps a bank in the low ground all day, thinner at noon.
	var gf: float = float(w.get("ground_fog", 1.0))
	ground_fog = (ground_fog_at(hour, clock.sunrise_hour, clock.sunset_hour, fc) * gf + maxf(0.0, gf - 1.0) * 0.5) * calm
	# A fen pools more of it, deeper, when it gathers (dawn and dusk; ADR-0047).
	var pool: Vector2 = fen_pool(fen_weight, fc)
	ground_fog *= pool.x
	var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	var depth: float = float(fc.get("depth_m", 6.0)) + pool.y
	var level: float = (fx.valley_level() if fx != null else 0.0) + depth
	if cam != null:
		# Standing in the fog, the depth fog's falloff would veil your own feet: keep it below you
		# and let the volume carry the fog you stand in.
		env.fog_height = minf(level, cam.global_position.y - 3.0)
	else:
		env.fog_height = level
	env.fog_height_density = float(fc.get("height_density", 0.06)) * ground_fog
	# Sun shafts through the mist and the canopy.
	sun.light_volumetric_fog_energy = 1.4 + float(fc.get("god_rays", 2.4)) * clampf(ground_fog, 0.0, 1.0) * golden
	if fog_volume == null:
		return
	fog_volume.visible = ground_fog > 0.02 and env.volumetric_fog_enabled
	if not fog_volume.visible:
		return
	if cam != null:
		fog_volume.global_position = Vector3(cam.global_position.x, level - 4.0, cam.global_position.z)
	var albedo: Color = Color(0.9, 0.92, 0.95).lerp(sun_col, golden * 0.25) * biome_tint
	_fog_mat.set_shader_parameter("density", float(fc.get("volume_density", 0.05)) * ground_fog)
	_fog_mat.set_shader_parameter("albedo", Vector3(albedo.r, albedo.g, albedo.b))
	_fog_mat.set_shader_parameter("depth_m", depth)
	_fog_mat.set_shader_parameter("water_depth_m", float(fc.get("water_depth_m", 4.0)))
	_fog_mat.set_shader_parameter("noise_scale", float(fc.get("noise_scale", 0.05)))
	_fog_mat.set_shader_parameter("fallback_level", level)
	var wd: Vector2 = w["wind_dir"]
	_fog_mat.set_shader_parameter("drift", wd * (0.15 + 1.5 * float(w["wind"])))


## The fog of the biomes round the camera (ADR-0047): the camera's ground and four points
## `biome_sample_m` round it, weighted 0.4 and 0.15 each, set the tint and fen targets.
func _sample_biomes() -> void:
	var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	var world: Node = Game.world
	var terrain: TerrainManager = world.get(&"terrain") as TerrainManager if world != null else null
	if cam == null or terrain == null:
		return
	var fc: Dictionary = _wcfg.get("fog", {}) as Dictionary
	var r: float = float(fc.get("biome_sample_m", 40.0))
	var p: Vector3 = cam.global_position
	var ids := PackedStringArray()
	for o: Vector2 in [Vector2.ZERO, Vector2(r, 0.0), Vector2(-r, 0.0), Vector2(0.0, r), Vector2(0.0, -r)]:
		var rt: RegionTerrain = terrain.region_terrain_at(p.x + o.x, p.z + o.y)
		ids.append(rt.biome_at(p.x + o.x, p.z + o.y) if rt != null else "")
	var t: Array = biome_fog_target(ids, _biome_fog_of, fc)
	_tint_target = t[0]
	_fen_target = t[1]


## [tint multiplier, is fen (0/1)] of a biome, cached.
func _biome_fog_of(id: String) -> Array:
	if not _biome_fog.has(id):
		var fc: Dictionary = _wcfg.get("fog", {}) as Dictionary
		var bd: BiomeDef = Content.get_def(&"biome", StringName(id)) as BiomeDef if id != "" else null
		var ref := Color(str(fc.get("biome_tint_reference", "#9aa59c")))
		_biome_fog[id] = [fog_tint_mul(bd.fog_tint, ref) if bd != null else Color.WHITE, 1.0 if id == "fen" else 0.0]
	return _biome_fog[id]


## The fog colour multiplier of a biome's `fog_tint` against the reference tint: their ratio per
## channel with its luminance taken out (fog brightness is the sky's and the sun's), so the
## reference biome is white and the others shift hue only.
static func fog_tint_mul(tint: Color, reference: Color) -> Color:
	var m := Color(tint.r / maxf(reference.r, 0.01), tint.g / maxf(reference.g, 0.01), tint.b / maxf(reference.b, 0.01))
	var lum: float = maxf(m.r * 0.2126 + m.g * 0.7152 + m.b * 0.0722, 0.01)
	return Color(m.r / lum, m.g / lum, m.b / lum)


## [tint multiplier, fen weight] for five biome samples (the camera's first, weighted 0.4, then four
## round it at 0.15 each), the tint pulled `biome_tint` of the way from white. `of(id)` gives a
## biome's [multiplier, is fen].
static func biome_fog_target(ids: PackedStringArray, of: Callable, fc: Dictionary) -> Array:
	var tint := Color(0.0, 0.0, 0.0)
	var fen: float = 0.0
	for i: int in ids.size():
		var wgt: float = 0.4 if i == 0 else 0.6 / maxf(1.0, ids.size() - 1.0)
		var bf: Array = of.call(ids[i])
		var m: Color = bf[0]
		tint += Color(m.r * wgt, m.g * wgt, m.b * wgt, 0.0)
		fen += float(bf[1]) * wgt
	tint.a = 1.0
	return [Color.WHITE.lerp(tint, float(fc.get("biome_tint", 0.6))), fen]


## How a fen changes the ground fog: Vector2(density multiplier, extra depth in m). The multiplier
## scales the hour's fog (ground_fog_at), so the pooling shows at dawn and dusk and is gone by noon.
static func fen_pool(fen: float, fc: Dictionary) -> Vector2:
	var fp: Dictionary = fc.get("fen_pool", {}) as Dictionary
	return Vector2(1.0 + fen * float(fp.get("density", 0.9)), fen * float(fp.get("depth_m", 2.5)))


## Per terrain layer: how readily puddles collect and how much darker it turns soaked (config
## "surfaces"), as two mat4 globals indexed by the layer's slice (column = slice / 4).
func _publish_surface_tables() -> void:
	var sf: Dictionary = _wcfg.get("surfaces", {}) as Dictionary
	var layers: PackedStringArray = TerrainTextures.DEFAULT_LAYERS
	if FileAccess.file_exists(TerrainTextures.LAYERS_JSON):
		var j := JSON.new()
		if j.parse(FileAccess.get_file_as_string(TerrainTextures.LAYERS_JSON)) == OK and j.data is Dictionary:
			layers = PackedStringArray((j.data as Dictionary).get("layers", layers))
	RenderingServer.global_shader_parameter_set(&"hm_terrain_puddle", _layer_table(layers, sf.get("puddle", {}) as Dictionary, 0.5))
	RenderingServer.global_shader_parameter_set(&"hm_terrain_porosity", _layer_table(layers, sf.get("porosity", {}) as Dictionary, 0.7))


static func _layer_table(layers: PackedStringArray, values: Dictionary, fallback: float) -> Projection:
	var v: PackedFloat32Array = []
	v.resize(16)
	v.fill(fallback)
	for i: int in mini(16, layers.size()):
		v[i] = float(values.get(layers[i], fallback))
	return Projection(Vector4(v[0], v[1], v[2], v[3]), Vector4(v[4], v[5], v[6], v[7]), Vector4(v[8], v[9], v[10], v[11]), Vector4(v[12], v[13], v[14], v[15]))


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
