class_name MenuFlight
extends Node3D
## The flight up the Tamsin through Larch Hollow at dusk behind the main menu (player report 4,
## item 3; ADR-0063, ADR-0065), built from the real main map. It is never drawn in the game: the
## stills runner (`make stills`) photographs it at STILLS points along the river, supersampled, and
## the menu pans slowly across those pictures (MenuBackdrop). Building and drawing it live behind
## the menu froze the packaged build's menu on the owner's machine (Build #94).
##
## `build()` makes it all at once (seconds: D6 composed at 2 m, its mesh, the water and a tree
## scatter from the region's biome and vegetation masks); `place_still(i)` puts the camera on still i,
## grows the game's own ground cover and undergrowth (VegetationScatter's medium and ground layers)
## in front of it, and sets the still's light (STILL_MOODS: three at dusk, one at a misty dawn).

const MAIN_WORLD_DIR: String = "res://world/main_map"
const REGION: String = "d6_larch_hollow"
const RIVER: String = "tamsin"
## The terrain's step: 2 m, so the river's banks meet its water cleanly (offline, the cost is free).
const SPACING: float = 2.0
## Metres per second along the river (the old live flight's pace; tests keep the path long enough).
const SPEED: float = 2.4
## Where the stills are taken, as shares of the river path's usable length.
const STILLS: PackedFloat32Array = [0.14, 0.38, 0.62, 0.86]
## The light of each still: MenuBackdrop dissolves from one to the next, so a dawn among the dusks
## reads as the valley's day turning over (TD-378).
const STILL_MOODS: PackedStringArray = ["dusk", "dusk", "dawn_mist", "dusk"]
## Per mood: the sun (direction towards it, colour, energy), the sky shader's colours and amounts,
## and the fog. mist > 0 lays height fog that far over the river below the camera.
const MOODS: Dictionary = {
	# The sun low in the west behind thin cloud, the first stars over the ridge.
	"dusk": {"sun_dir": Vector3(-0.78, 0.09, -0.62), "sun_color": Color(1.0, 0.66, 0.42), "sun_energy": 1.2,
		"sky_sun": Vector3(1.0, 0.62, 0.36), "sky_sun_energy": 1.4, "zenith": Color(0.12, 0.17, 0.3),
		"horizon": Color(0.62, 0.5, 0.45), "sunset": Color(1.0, 0.45, 0.2), "sunset_amount": 0.85,
		"night": 0.12, "cloud": 0.42, "stars": 0.25, "ambient": 0.7,
		"fog_color": Color(0.5, 0.44, 0.45), "fog_density": 0.0022, "mist": 0.0},
	# First light from the east over the far ridge, cold air and mist lying on the river.
	"dawn_mist": {"sun_dir": Vector3(0.82, 0.06, -0.57), "sun_color": Color(1.0, 0.76, 0.56), "sun_energy": 0.95,
		"sky_sun": Vector3(1.0, 0.74, 0.52), "sky_sun_energy": 1.1, "zenith": Color(0.24, 0.32, 0.46),
		"horizon": Color(0.74, 0.68, 0.68), "sunset": Color(1.0, 0.62, 0.45), "sunset_amount": 0.55,
		"night": 0.04, "cloud": 0.3, "stars": 0.04, "ambient": 0.85,
		"fog_color": Color(0.7, 0.7, 0.74), "fog_density": 0.0042, "mist": 16.0},
}
## The real scatter (VegetationScatter, the game's seed for the main map's look) is grown per still
## over chunks within these metres of the camera and in front of it: undergrowth (bushes, rocks,
## deadfall) out to MEDIUM_REACH, ground cover (grass, ferns, flowers, moss, litter) out to
## GROUND_REACH, shrinking away plant by plant over its last fifth as the game's does. Offline, so
## further than the game draws them (GROUND_END 52 m).
const MEDIUM_REACH: float = 320.0
const GROUND_REACH: float = 150.0
const SCATTER_SEED: int = 4471
## Tree scatter: one candidate per CELL metres, kept by the region's vegetation mask and biome.
const CELL: float = 7.0
const TILE: float = 128.0
const LOD1_END: float = 260.0
const LOD2_END: float = 1000.0
## Per biome: species ids and their shares, and the share of cells that get a tree.
const BIOME_TREES: Dictionary = {
	"conifer_forest": {"density": 0.62, "species": {"grey_fir": 0.6, "hollow_larch": 0.4}},
	"birch_grove": {"density": 0.5, "species": {"paper_birch": 0.7, "hollow_larch": 0.3}},
	"riverbank": {"density": 0.16, "species": {"paper_birch": 0.5, "hollow_larch": 0.5}},
	"rocky_slope": {"density": 0.18, "species": {"grey_fir": 1.0}},
	"meadow": {"density": 0.04, "species": {"hollow_larch": 1.0}},
}

var _data: Dictionary = {}
var _textures: TerrainTextures = null
var _root: Node3D
var _cam: Camera3D
var _path: PackedVector3Array = []
var _path_len: float = 0.0
var _rt: RegionTerrain = null
var _env: Environment
var _sky_mat: ShaderMaterial
var _sun: DirectionalLight3D
## The current still's undergrowth and ground cover (freed when the camera moves on).
var _near: Node3D = null
## Rivers and lakes as a 64 m grid of segments, so the scatter keeps plants out of the water.
var _water_grid: Dictionary = {}


## Builds the whole flight under this node (blocking). False without the region or its river.
func build() -> bool:
	var species: Dictionary = {}
	for id: String in ["grey_fir", "hollow_larch", "paper_birch"]:
		var sp: SpeciesDef = Content.get_def(&"species", StringName(id)) as SpeciesDef
		if sp != null and not sp.models.is_empty():
			species[id] = {"models": sp.models.duplicate(), "height": sp.height_range}
	_data = build_data(species)
	if _data.is_empty():
		return false
	_root = self
	_path = _data["path"]
	_path_len = maxf(0.0, (_path.size() - 1) * 6.0) if not _path.is_empty() else 0.0
	_build_environment()
	_build_terrain(_data["rt"])
	_build_water()
	_build_trees((_data["trees"] as Dictionary).keys())
	_rt = _data["rt"]
	_water_grid = water_grid(_rt.water)
	_data.clear()
	return not _path.is_empty()


## Puts the camera on still `i` (of STILLS), with its light and the plants in front of it.
func place_still(i: int) -> void:
	_place_camera(still_distance(STILLS[i], _path_len))
	apply_mood(STILL_MOODS[i] if i < STILL_MOODS.size() else "dusk")
	grow_near()


## The still's light (a key of MOODS).
func apply_mood(mood: String) -> void:
	var m: Dictionary = MOODS.get(mood, MOODS["dusk"])
	var sun_dir: Vector3 = (m["sun_dir"] as Vector3).normalized()
	_sky_mat.set_shader_parameter("sun_dir", sun_dir)
	_sky_mat.set_shader_parameter("sun_color", m["sky_sun"])
	_sky_mat.set_shader_parameter("sun_energy", m["sky_sun_energy"])
	_sky_mat.set_shader_parameter("zenith_color", m["zenith"])
	_sky_mat.set_shader_parameter("horizon_color", m["horizon"])
	_sky_mat.set_shader_parameter("sunset_color", m["sunset"])
	_sky_mat.set_shader_parameter("sunset_amount", m["sunset_amount"])
	_sky_mat.set_shader_parameter("night_amount", m["night"])
	_sky_mat.set_shader_parameter("cloud_cover", m["cloud"])
	_sky_mat.set_shader_parameter("star_visibility", m["stars"])
	_env.ambient_light_energy = m["ambient"]
	_env.fog_light_color = m["fog_color"]
	_env.fog_density = m["fog_density"]
	var mist: float = float(m["mist"])
	# Height fog: thick below the river's level plus `mist`, thinning above (Godot's height fog).
	_env.fog_height = _water_below(_cam.global_position) + mist if mist > 0.0 else 0.0
	_env.fog_height_density = 0.12 if mist > 0.0 else 0.0
	_sun.light_color = m["sun_color"]
	_sun.light_energy = m["sun_energy"]
	_sun.look_at_from_position(Vector3.ZERO, -sun_dir, Vector3.UP)
	# The water reflects the sky gradient EnvironmentController publishes in game; publish this
	# light's (the game's environment overwrites them when a world loads).
	var hz: Color = (m["horizon"] as Color) * 0.55
	var zn: Color = (m["zenith"] as Color) * 0.55
	RenderingServer.global_shader_parameter_set(&"hm_sky_zenith", Vector4(zn.r, zn.g, zn.b, 1.0))
	RenderingServer.global_shader_parameter_set(&"hm_sky_horizon", Vector4(hz.r, hz.g, hz.b, 1.0))


## Grows the game's undergrowth and ground cover over the chunks the camera looks at.
func grow_near() -> void:
	if _near != null:
		_near.queue_free()
	_near = Node3D.new()
	_near.name = "Near"
	_root.add_child(_near)
	if _rt == null:
		return
	var at := Vector2(_cam.global_position.x, _cam.global_position.z)
	var fwd3: Vector3 = -_cam.global_transform.basis.z
	var fwd := Vector2(fwd3.x, fwd3.z).normalized()
	var height_fn: Callable = _rt.height.sample
	var water_fn: Callable = func(x: float, z: float) -> float: return water_level(_water_grid, x, z)
	var groups: Dictionary = {}
	for key: Vector2i in chunks_in_view(at, fwd, MEDIUM_REACH, _rt.rect):
		var layers: Dictionary = VegetationScatter.scatter_chunk(key, _rt, SCATTER_SEED, height_fn, water_fn, 3)
		var centre := Vector2((key.x + 0.5) * VegetationScatter.CHUNK, (key.y + 0.5) * VegetationScatter.CHUNK)
		var with_ground: bool = centre.distance_to(at) < GROUND_REACH + VegetationScatter.CHUNK * 0.71
		for layer: String in (["medium", "ground"] if with_ground else ["medium"]):
			for inst: VegetationScatter.Instance in layers.get(layer, []):
				var gk: String = "%s|%s|%d" % [layer, inst.species, inst.variant]
				if not groups.has(gk):
					groups[gk] = []
				(groups[gk] as Array).append(inst)
	for gk: String in groups:
		var parts: PackedStringArray = gk.split("|")
		var sp: SpeciesDef = Content.get_def(&"species", StringName(parts[1])) as SpeciesDef
		var ground: bool = parts[0] == "ground"
		var model: String = sp.models[int(parts[2]) % sp.models.size()]
		var mesh: Mesh = ModelLibrary.mesh(model, "rock" if sp.veg_kind == "rock" else "plant")
		_near.add_child(_plants(mesh, groups[gk], GROUND_REACH if ground else 0.0, not ground))


## Chunks (VegetationScatter's 64 m) of `rect` within `reach` of `at` and in front of the camera
## (within 70° of `fwd`, or under 90 m away: the banks below the lens).
static func chunks_in_view(at: Vector2, fwd: Vector2, reach: float, rect: Rect2) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var c: float = VegetationScatter.CHUNK
	var lo := Vector2i(floori(maxf(at.x - reach, rect.position.x) / c), floori(maxf(at.y - reach, rect.position.y) / c))
	var hi := Vector2i(floori(minf(at.x + reach, rect.end.x - 0.01) / c), floori(minf(at.y + reach, rect.end.y - 0.01) / c))
	for z: int in range(lo.y, hi.y + 1):
		for x: int in range(lo.x, hi.x + 1):
			var centre := Vector2((x + 0.5) * c, (z + 0.5) * c)
			var d: float = centre.distance_to(at)
			if d > reach + c * 0.71:
				continue
			if d > 90.0 and fwd.dot((centre - at) / d) < cos(deg_to_rad(70.0)):
				continue
			out.append(Vector2i(x, z))
	return out


## A MultiMesh of plants; shrink > 0 shrinks each away over the last fifth of that distance
## (foliage.gdshader reads it from a negative INSTANCE_CUSTOM.a, as VegetationManager sets it).
func _plants(mesh: Mesh, insts: Array, shrink: float, shadows: bool) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = shrink > 0.0
	mm.mesh = mesh
	mm.instance_count = insts.size()
	for i: int in insts.size():
		var inst: VegetationScatter.Instance = insts[i]
		var b := Basis.from_euler(Vector3(inst.tilt.x, inst.yaw, inst.tilt.y)).scaled(Vector3.ONE * inst.scale)
		mm.set_instance_transform(i, Transform3D(b, inst.pos))
		if shrink > 0.0:
			mm.set_instance_custom_data(i, Color(0.0, 0.0, 0.0, -shrink))
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mmi


## Rivers (segments with their levels and half widths) and lakes (polygons) on a 64 m grid:
## {Vector2i: [[a, b, level_a, level_b, half_a, half_b] or [polygon, level]]}.
static func water_grid(water: Array) -> Dictionary:
	var grid: Dictionary = {}
	for w: Variant in water:
		var d: Dictionary = w
		if str(d.get("kind", "")) == "river":
			var pts: Array = d.get("points", [])
			var levels: Array = d.get("levels", [])
			var widths: Array = d.get("widths", [])
			for i: int in range(1, pts.size()):
				var a := Vector2(float(pts[i - 1][0]), float(pts[i - 1][1]))
				var b := Vector2(float(pts[i][0]), float(pts[i][1]))
				var ha: float = float(widths[i - 1] if i - 1 < widths.size() else 12.0) * 0.5
				var hb: float = float(widths[i] if i < widths.size() else 12.0) * 0.5
				var seg: Array = [a, b, float(levels[i - 1] if i - 1 < levels.size() else 0.0), float(levels[i] if i < levels.size() else 0.0), ha, hb]
				var box: Rect2 = Rect2(a, Vector2.ZERO).expand(b).grow(maxf(ha, hb))
				_grid_add(grid, box, seg)
		elif d.has("polygon"):
			var poly := PackedVector2Array()
			for p: Variant in d.get("polygon", []):
				poly.append(Vector2(float(p[0]), float(p[1])))
			if poly.size() >= 3:
				var box2 := Rect2(poly[0], Vector2.ZERO)
				for q: Vector2 in poly:
					box2 = box2.expand(q)
				_grid_add(grid, box2, [poly, float(d.get("level", 0.0))])
	return grid


static func _grid_add(grid: Dictionary, box: Rect2, entry: Array) -> void:
	for z: int in range(floori(box.position.y / 64.0), floori(box.end.y / 64.0) + 1):
		for x: int in range(floori(box.position.x / 64.0), floori(box.end.x / 64.0) + 1):
			var k := Vector2i(x, z)
			if not grid.has(k):
				grid[k] = []
			(grid[k] as Array).append(entry)


## The water's level at (x, z), or -INF where there is no water.
static func water_level(grid: Dictionary, x: float, z: float) -> float:
	var p := Vector2(x, z)
	var best: float = -INF
	for e: Array in grid.get(Vector2i(floori(x / 64.0), floori(z / 64.0)), []):
		if e.size() == 2:
			if Geometry2D.is_point_in_polygon(p, e[0]):
				best = maxf(best, float(e[1]))
			continue
		var a: Vector2 = e[0]
		var b: Vector2 = e[1]
		var ab: Vector2 = b - a
		var t: float = clampf((p - a).dot(ab) / maxf(ab.length_squared(), 0.0001), 0.0, 1.0)
		if p.distance_to(a + ab * t) <= lerpf(float(e[4]), float(e[5]), t):
			best = maxf(best, lerpf(float(e[2]), float(e[3]), t))
	return best


## The river's level nearest below `at` (the path flies over it), for the mist's height.
func _water_below(at: Vector3) -> float:
	var lvl: float = water_level(_water_grid, at.x, at.z)
	return lvl if lvl > -INF else (_rt.height.sample(at.x, at.z) if _rt != null else at.y - 24.0)


## Metres along a path of `path_len` m for a still at `share` of its usable length (the last
## 120 m are kept back: the camera looks 110 m ahead).
static func still_distance(share: float, path_len: float) -> float:
	return clampf(share, 0.0, 1.0) * maxf(path_len - 120.0, 0.0)


# --- Data -------------------------------------------------------------------------------------

## Everything the flight needs, as plain data: {"rt", "terrain" (mesh job),
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


# --- Scene ------------------------------------------------------------------------------------

func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ShaderMaterial.new()
	_sky_mat = sky_mat
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
	_env = env
	var we := WorldEnvironment.new()
	we.environment = env
	_root.add_child(we)
	var sun := DirectionalLight3D.new()
	_sun = sun
	sun.light_color = Color(1.0, 0.66, 0.42)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 420.0
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


