class_name MenuBackdrop
extends SubViewportContainer
## The main menu's backdrop (player report 4, item 3; ADR-0063): a slow flight up the Tamsin
## through Larch Hollow at dusk, built from the real main map, not a picture of it.
##
## Everything heavy runs on one worker task: the region's terrain (composed at 4 m, cached on disk
## after the first menu), its mesh, the water, a tree scatter from the region's biome and
## vegetation masks, and the camera's path along the river. The main thread then adds the result a
## few nodes a frame and fades it in, so the menu never stalls while it builds.
##
## Cost guard: once the flight is up, the frame times of the next seconds are measured. If the
## menu runs below MIN_FPS the camera stops and the view is rendered once more and then frozen (a
## still backdrop that costs nothing per frame). The "Menu backdrop" option picks moving, still or
## off. Headless runs skip it entirely.

const MAIN_WORLD_DIR: String = "res://world/main_map"
const REGION: String = "d6_larch_hollow"
const RIVER: String = "tamsin"
## The terrain's step for the backdrop: 4 m reads well from 25 m up and composes in ~3 s once.
const SPACING: float = 4.0
## Metres per second along the river.
const SPEED: float = 2.4
## Under this the backdrop freezes (measured over MEASURE_TIME seconds after it fades in).
const MIN_FPS: float = 40.0
const MEASURE_TIME: float = 4.0
const FADE_IN: float = 3.0
const LOOP_FADE: float = 2.5
## Tree scatter: one candidate per CELL metres, kept by the region's vegetation mask and biome.
const CELL: float = 7.0
const TILE: float = 128.0
const LOD1_END: float = 230.0
const LOD2_END: float = 900.0
## Per biome: species ids and their shares, and the share of cells that get a tree.
const BIOME_TREES: Dictionary = {
	"conifer_forest": {"density": 0.62, "species": {"grey_fir": 0.6, "hollow_larch": 0.4}},
	"birch_grove": {"density": 0.5, "species": {"paper_birch": 0.7, "hollow_larch": 0.3}},
	"riverbank": {"density": 0.16, "species": {"paper_birch": 0.5, "hollow_larch": 0.5}},
	"rocky_slope": {"density": 0.18, "species": {"grey_fir": 1.0}},
	"meadow": {"density": 0.04, "species": {"hollow_larch": 1.0}},
}

## "moving" | "still" | "off" (Settings.menu_backdrop).
var mode: String = "moving"
## Measured mean frame time (ms) after the fade-in, 0 until measured; the verdict is in `frozen`.
var measured_ms: float = 0.0
var frozen: bool = false

var _vp: SubViewport
var _root: Node3D
var _cam: Camera3D
var _task: int = -1
var _data: Dictionary = {}
var _species: Dictionary = {}
var _textures: TerrainTextures = null
var _steps: Array[Callable] = []
var _path: PackedVector3Array = []
var _path_len: float = 0.0
var _s: float = 0.0
var _loops: int = 0
var _fade: float = 0.0
var _live: bool = false
var _times: PackedFloat32Array = []
var _measure_t: float = 0.0
var _black: ColorRect


func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	modulate.a = 0.0
	_vp = SubViewport.new()
	_vp.own_world_3d = true
	_vp.msaa_3d = Viewport.MSAA_2X
	_vp.positional_shadow_atlas_size = 0
	add_child(_vp)
	_root = Node3D.new()
	_vp.add_child(_root)
	_black = ColorRect.new()
	_black.color = Color(0, 0, 0, 0)
	_black.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_black.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_black)
	if mode == "off" or DisplayServer.get_name() == "headless":
		set_process(false)
		return
	# Content reads stay on the main thread; the worker gets plain data.
	for id: String in ["grey_fir", "hollow_larch", "paper_birch"]:
		var sp: SpeciesDef = Content.get_def(&"species", StringName(id)) as SpeciesDef
		if sp != null and not sp.models.is_empty():
			_species[id] = {"models": sp.models.duplicate(), "height": sp.height_range}
	var species: Dictionary = _species.duplicate(true)
	_task = WorkerThreadPool.add_task(func() -> void: _data = build_data(species), false, "menu backdrop")


func _exit_tree() -> void:
	if _task >= 0:
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1


func _process(delta: float) -> void:
	if _task >= 0:
		if not WorkerThreadPool.is_task_completed(_task):
			return
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1
		if _data.is_empty():
			Log.warn("menu", "backdrop: no terrain for %s; the menu stays plain" % REGION)
			set_process(false)
			return
		_queue_build()
	if not _steps.is_empty():
		# One step a frame: the terrain, the water, then trees a batch at a time.
		var step: Callable = _steps.pop_front()
		step.call()
		return
	if not _live:
		return
	_fade = minf(_fade + delta / FADE_IN, 1.0)
	modulate.a = _fade
	if not frozen and mode == "moving":
		_fly(delta)
	if _fade >= 1.0 and measured_ms == 0.0:
		_measure(delta)


# --- Worker -----------------------------------------------------------------------------------

## Everything the backdrop needs, as plain data (worker thread): {"rt", "terrain" (mesh job),
## "water": [arrays], "trees": {model_key: PackedFloat32Array of transforms}, "path"}.
static func build_data(species: Dictionary) -> Dictionary:
	var world: WorldDef = WorldDef.load_from(MAIN_WORLD_DIR)
	if world == null:
		return {}
	var rt: RegionTerrain = TerrainComposer.get_or_compose(world, REGION, SPACING)
	if rt == null:
		return {}
	var out: Dictionary = {"rt": rt}
	out["textures"] = TerrainTextures.prepare()
	TerrainManager.prepare_splat(rt)
	var origin: Vector2 = rt.rect.position
	out["terrain"] = TerrainMesher.build_chunk_job(origin, rt.rect.size.x, SPACING, rt.height.sample, 6.0)
	var water: Array = []
	var river: Dictionary = {}
	for w: Variant in rt.water:
		var d: Dictionary = w
		if str(d.get("kind", "")) == "river":
			water.append(river_arrays(d))
			if str(d.get("id", "")) == RIVER:
				river = d
		elif d.has("polygon"):
			var lake: Array = lake_arrays(d)
			if not lake.is_empty():
				water.append(lake)
	out["water"] = water
	out["trees"] = scatter_trees(rt, species)
	out["path"] = river_path(river, rt)
	return out


## A river's surface: a ribbon along its points at their water levels, its width wide.
static func river_arrays(d: Dictionary) -> Array:
	var pts: Array = d.get("points", [])
	var levels: Array = d.get("levels", [])
	var widths: Array = d.get("widths", [])
	var verts := PackedVector3Array()
	var idx := PackedInt32Array()
	for i: int in pts.size():
		var p := Vector2(float(pts[i][0]), float(pts[i][1]))
		var a: Vector2 = Vector2(float(pts[maxi(i - 1, 0)][0]), float(pts[maxi(i - 1, 0)][1]))
		var b: Vector2 = Vector2(float(pts[mini(i + 1, pts.size() - 1)][0]), float(pts[mini(i + 1, pts.size() - 1)][1]))
		var n: Vector2 = (b - a).normalized().orthogonal()
		var half: float = float(widths[i] if i < widths.size() else 12.0) * 0.5 + 1.5
		var y: float = float(levels[i] if i < levels.size() else 0.0)
		verts.append(Vector3(p.x + n.x * half, y, p.y + n.y * half))
		verts.append(Vector3(p.x - n.x * half, y, p.y - n.y * half))
		if i > 0:
			var k: int = i * 2
			idx.append_array([k - 2, k - 1, k, k - 1, k + 1, k])
	return _surface(verts, idx)


## A lake's surface: its polygon, triangulated, at its level.
static func lake_arrays(d: Dictionary) -> Array:
	var poly := PackedVector2Array()
	for p: Variant in d.get("polygon", []):
		poly.append(Vector2(float(p[0]), float(p[1])))
	var tris: PackedInt32Array = Geometry2D.triangulate_polygon(poly)
	if tris.is_empty():
		return []
	var y: float = float(d.get("level", 0.0))
	var verts := PackedVector3Array()
	for p2: Vector2 in poly:
		verts.append(Vector3(p2.x, y, p2.y))
	return _surface(verts, tris)


## A flat surface's arrays, every triangle wound to face up (Godot's front faces are clockwise
## seen from the front, so (b - a) x (c - a) must point down).
static func _surface(verts: PackedVector3Array, tris: PackedInt32Array) -> Array:
	var idx := PackedInt32Array()
	for t: int in range(0, tris.size() - 2, 3):
		var a: Vector3 = verts[tris[t]]
		var up: bool = (verts[tris[t + 1]] - a).cross(verts[tris[t + 2]] - a).y > 0.0
		idx.append_array([tris[t], tris[t + 2], tris[t + 1]] if up else [tris[t], tris[t + 1], tris[t + 2]])
	var normals := PackedVector3Array()
	normals.resize(verts.size())
	normals.fill(Vector3.UP)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = idx
	return arrays


## Trees over the region from its biome and vegetation masks, deterministic: {"<model>|<tile>":
## PackedFloat32Array (MultiMesh 3D transform buffer, 12 floats each)}.
static func scatter_trees(rt: RegionTerrain, species: Dictionary) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = 4471
	var out: Dictionary = {}
	var r: Rect2 = rt.rect
	for z: float in range(int(r.position.y + CELL * 0.5), int(r.end.y), int(CELL)):
		for x: float in range(int(r.position.x + CELL * 0.5), int(r.end.x), int(CELL)):
			var roll: float = rng.randf()
			var jx: float = x + rng.randf_range(-0.45, 0.45) * CELL
			var jz: float = z + rng.randf_range(-0.45, 0.45) * CELL
			var pick: float = rng.randf()
			var size_roll: float = rng.randf()
			var yaw: float = rng.randf() * TAU
			var cfg: Dictionary = BIOME_TREES.get(rt.biome_at(jx, jz), {})
			if cfg.is_empty():
				continue
			if roll > float(cfg["density"]) * clampf(rt.veg_at(jx, jz) * 1.2, 0.0, 1.0):
				continue
			if rt.height.normal_at(jx, jz).y < 0.8:
				continue
			var id: String = _pick(cfg["species"], pick)
			if not species.has(id):
				continue
			var sp: Dictionary = species[id]
			var models: Array = sp["models"]
			var model: String = models[int(size_roll * 997.0) % models.size()]
			var hr: Vector2 = sp["height"] if sp["height"] is Vector2 else Vector2(18, 26)
			var s: float = lerpf(hr.x, hr.y, size_roll) / 20.0
			var y: float = rt.height.sample(jx, jz) - 0.15
			var key: String = "%s|%d,%d" % [model, int(floor(jx / TILE)), int(floor(jz / TILE))]
			if not out.has(key):
				out[key] = []
			var basis := Basis(Vector3.UP, yaw).scaled(Vector3.ONE * s)
			# An Array per key (a reference); packed copies are made once at the end.
			(out[key] as Array).append_array([basis.x.x, basis.y.x, basis.z.x, jx,
				basis.x.y, basis.y.y, basis.z.y, y, basis.x.z, basis.y.z, basis.z.z, jz])
	for k: String in out:
		out[k] = PackedFloat32Array(out[k])
	return out


static func _pick(shares: Dictionary, roll: float) -> String:
	var acc: float = 0.0
	var last: String = ""
	for id: String in shares:
		acc += float(shares[id])
		last = id
		if roll <= acc:
			return id
	return last


## The camera's path: up the river from where it enters the region to where it leaves, smoothed,
## high enough over the banks within 50 m. Empty without the river.
static func river_path(d: Dictionary, rt: RegionTerrain) -> PackedVector3Array:
	var out := PackedVector3Array()
	var pts: Array = d.get("points", [])
	var levels: Array = d.get("levels", [])
	var inner: Rect2 = rt.rect.grow(-90.0)
	var raw: Array[Vector3] = []
	for i: int in pts.size():
		var p := Vector2(float(pts[i][0]), float(pts[i][1]))
		if not inner.has_point(p):
			continue
		var clear: float = float(levels[i] if i < levels.size() else rt.height.sample(p.x, p.y)) + 24.0
		for k: int in 8:
			var o: Vector2 = Vector2.from_angle(TAU * k / 8.0) * 50.0
			clear = maxf(clear, rt.height.sample(p.x + o.x, p.y + o.y) + 14.0)
		raw.append(Vector3(p.x, clear, p.y))
	# The river runs north to south; the camera goes upstream into the valley's evening light.
	raw.reverse()
	var n: int = raw.size()
	for i2: int in n:
		var acc := Vector3.ZERO
		var w: float = 0.0
		for j: int in range(maxi(0, i2 - 10), mini(n, i2 + 11)):
			acc += raw[j]
			w += 1.0
		out.append(acc / w)
	return out


## Whether frame times (seconds) say the moving backdrop costs too much: their mean is under
## MIN_FPS. Pure, for tests and for the options note.
static func too_slow(times: PackedFloat32Array) -> bool:
	if times.is_empty():
		return false
	var sum: float = 0.0
	for t: float in times:
		sum += t
	return sum / times.size() > 1.0 / MIN_FPS


# --- Main thread ------------------------------------------------------------------------------

func _queue_build() -> void:
	var rt: RegionTerrain = _data["rt"]
	_path = _data["path"]
	_path_len = maxf(0.0, (_path.size() - 1) * 6.0) if not _path.is_empty() else 0.0
	_steps.append(_build_environment)
	_steps.append(func() -> void: _build_terrain(rt))
	_steps.append(_build_water)
	var keys: Array = (_data["trees"] as Dictionary).keys()
	for i: int in range(0, keys.size(), 12):
		var batch: Array = keys.slice(i, i + 12)
		_steps.append(func() -> void: _build_trees(batch))
	_steps.append(_start)


func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ShaderMaterial.new()
	sky_mat.shader = load("res://assets/shaders/sky.gdshader")
	var base: String = "res://assets/generated/textures/"
	if ResourceLoader.exists(base + "sky_cloud_noise.png"):
		sky_mat.set_shader_parameter("cloud_tex", load(base + "sky_cloud_noise.png"))
	# Dusk: the sun low in the west behind thin cloud, the first stars over the ridge.
	var sun_dir: Vector3 = Vector3(-0.78, 0.09, -0.62).normalized()
	sky_mat.set_shader_parameter("sun_dir", sun_dir)
	sky_mat.set_shader_parameter("sun_color", Vector3(1.0, 0.62, 0.36))
	sky_mat.set_shader_parameter("sun_energy", 1.4)
	sky_mat.set_shader_parameter("zenith_color", Color(0.12, 0.17, 0.3))
	sky_mat.set_shader_parameter("horizon_color", Color(0.62, 0.5, 0.45))
	sky_mat.set_shader_parameter("sunset_color", Color(1.0, 0.45, 0.2))
	sky_mat.set_shader_parameter("sunset_amount", 0.85)
	sky_mat.set_shader_parameter("night_amount", 0.12)
	sky_mat.set_shader_parameter("cloud_cover", 0.42)
	sky_mat.set_shader_parameter("star_visibility", 0.25)
	sky.sky_material = sky_mat
	sky.radiance_size = Sky.RADIANCE_SIZE_64
	sky.process_mode = Sky.PROCESS_MODE_QUALITY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.7
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	env.fog_density = 0.0022
	env.fog_light_color = Color(0.5, 0.44, 0.45)
	env.fog_sun_scatter = 0.35
	env.fog_sky_affect = 0.5
	env.fog_aerial_perspective = 0.4
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.adjustment_enabled = true
	env.adjustment_saturation = 0.88
	env.adjustment_contrast = 1.06
	var we := WorldEnvironment.new()
	we.environment = env
	_root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.light_color = Color(1.0, 0.66, 0.42)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	sun.directional_shadow_max_distance = 260.0
	_root.add_child(sun)
	sun.look_at_from_position(Vector3.ZERO, -sun_dir, Vector3.UP)
	_cam = Camera3D.new()
	_cam.fov = 58.0
	_cam.far = 2400.0
	_root.add_child(_cam)
	_cam.make_current()
	if not _path.is_empty():
		_place_camera(0.0)


func _build_terrain(rt: RegionTerrain) -> void:
	_textures = TerrainTextures.adopt(_data["textures"])
	var mat := ShaderMaterial.new()
	mat.shader = load("res://assets/shaders/terrain.gdshader")
	_textures.apply_to(mat)
	var imgs: Array[Image] = []
	imgs.assign(rt.get_meta(&"splat") if rt.has_meta(&"splat") else rt.splat_images())
	mat.set_shader_parameter("splat0", ImageTexture.create_from_image(imgs[0]))
	mat.set_shader_parameter("splat1", ImageTexture.create_from_image(imgs[1]))
	mat.set_shader_parameter("region_rect", Vector4(rt.rect.position.x, rt.rect.position.y, rt.rect.size.x, float(rt.height.width - 1)))
	var pal := PackedInt32Array()
	for name: String in rt.palette:
		pal.append(maxi(_textures.layer_index(name), 0))
	while pal.size() < 8:
		pal.append(0)
	mat.set_shader_parameter("palette0", Vector4i(pal[0], pal[1], pal[2], pal[3]))
	mat.set_shader_parameter("palette1", Vector4i(pal[4], pal[5], pal[6], pal[7]))
	var mi := MeshInstance3D.new()
	mi.mesh = TerrainMesher.finish(_data["terrain"])
	mi.material_override = mat
	mi.position = Vector3(rt.rect.position.x, 0.0, rt.rect.position.y)
	_root.add_child(mi)


func _build_water() -> void:
	var m := ShaderMaterial.new()
	m.shader = load("res://assets/shaders/water.gdshader")
	var base: String = "res://assets/generated/textures/"
	if ResourceLoader.exists(base + "water_normal_a.png"):
		m.set_shader_parameter("normal_a", load(base + "water_normal_a.png"))
		m.set_shader_parameter("normal_b", load(base + "water_normal_b.png") if ResourceLoader.exists(base + "water_normal_b.png") else load(base + "water_normal_a.png"))
	m.set_shader_parameter("flow_speed", 0.4)
	# The water reflects the sky gradient EnvironmentController publishes in game; publish the
	# dusk's here (the game's environment overwrites them when a world loads).
	var hz: Color = Color(0.62, 0.5, 0.45) * 0.55
	var zn: Color = Color(0.12, 0.17, 0.3) * 0.55
	RenderingServer.global_shader_parameter_set(&"hm_sky_zenith", Vector4(zn.r, zn.g, zn.b, 1.0))
	RenderingServer.global_shader_parameter_set(&"hm_sky_horizon", Vector4(hz.r, hz.g, hz.b, 1.0))
	for arrays: Array in _data["water"]:
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		mi.material_override = m
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_root.add_child(mi)


## Trees in 128 m tiles: LOD1 near, LOD2 out to the fog (visibility ranges, fading between).
func _build_trees(keys: Array) -> void:
	var trees: Dictionary = _data["trees"]
	for key: String in keys:
		var model: String = key.get_slice("|", 0)
		var buf: PackedFloat32Array = trees[key]
		var ph: String = "deciduous" if model.contains("birch") else "conifer"
		for lod: int in [1, 2]:
			var id: String = "%s_lod%d" % [model, lod]
			var mesh: Mesh = ModelLibrary.mesh(id if ModelLibrary.has_model(id) else model, ph)
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = mesh
			mm.instance_count = buf.size() / 12
			mm.buffer = buf
			var mmi := MultiMeshInstance3D.new()
			mmi.multimesh = mm
			mmi.visibility_range_begin = 0.0 if lod == 1 else LOD1_END - 20.0
			mmi.visibility_range_end = LOD1_END if lod == 1 else LOD2_END
			mmi.visibility_range_begin_margin = 20.0 if lod == 2 else 0.0
			mmi.visibility_range_end_margin = 20.0
			mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if lod == 1 else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			_root.add_child(mmi)


func _start() -> void:
	_data.clear()
	_live = true
	if mode == "still" or _path.is_empty():
		_freeze()


## Where the camera is at `s` metres along the path: on it, looking 110 m ahead and down a little,
## with a slow sway so the flight never reads as a rail.
func _place_camera(s: float) -> void:
	var at: Vector3 = _path_at(s)
	var ahead: Vector3 = _path_at(s + 110.0)
	ahead.y -= 22.0
	var sway: float = sin(s * 0.011) * 0.12
	_cam.look_at_from_position(at, ahead, Vector3.UP)
	_cam.rotate_object_local(Vector3.UP, sway)


func _path_at(s: float) -> Vector3:
	var f: float = clampf(s / 6.0, 0.0, float(_path.size() - 1))
	var i: int = mini(int(f), _path.size() - 2)
	return _path[i].lerp(_path[i + 1], f - i) if _path.size() > 1 else _path[0]


func _fly(delta: float) -> void:
	_s += SPEED * delta
	var end: float = _path_len - 120.0
	# The last metres fade to black and the flight starts over.
	_black.color.a = loop_black(_s, end, _loops > 0)
	if _s >= end:
		_s = 0.0
		_loops += 1
	_place_camera(_s)


## The black over the flight at `s` of `end` metres: fading out over the last LOOP_FADE seconds,
## and in over the first ones of every loop after the first (the menu's own fade covers that one).
static func loop_black(s: float, end: float, again: bool) -> float:
	var span: float = SPEED * LOOP_FADE
	var out: float = clampf(1.0 - (end - s) / span, 0.0, 1.0)
	var into: float = clampf(1.0 - s / span, 0.0, 1.0) if again else 0.0
	return maxf(out, into)


func _measure(delta: float) -> void:
	_times.append(delta)
	_measure_t += delta
	if _measure_t < MEASURE_TIME:
		return
	var sum: float = 0.0
	for t: float in _times:
		sum += t
	measured_ms = 1000.0 * sum / maxf(1.0, _times.size())
	var slow: bool = too_slow(_times)
	Log.info("menu", "backdrop: %.1f ms a frame over %.0f s (%s)" % [measured_ms, MEASURE_TIME, "frozen: too slow" if slow else "moving"])
	if slow and mode == "moving":
		_freeze()


## A still backdrop: one more frame, then the viewport stops rendering.
func _freeze() -> void:
	frozen = true
	_black.color.a = 0.0
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
