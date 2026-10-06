class_name TerrainManager
extends Node3D
## Streams and renders terrain, answers height queries, owns terrain collision and digging.
##
## Layout (ADR-0007):
##  * near field: 64 m chunks in a (2*NEAR_RADIUS+1)^2 square around the focus, LOD by distance
##    (1 m / 2 m / 4 m vertex step), skirts hide LOD cracks; meshes built on worker threads.
##  * far field: one coarse tile per region (16 m step) for the whole map, discarding inside the
##    near square so they never overlap.
##  * collision: HeightMapShape3D for chunks within COLLISION_RADIUS of the focus (a trimesh
##    where a POI cellar cuts the chunk: a heightmap can only drop whole quads).
##  * cellars (TD-026): `holes` (TerrainHoles, derived from the POI placements at setup, never
##    saved) are cut exactly out of the near meshes, their skirts and the collision, so a POI's
##    below-ground rooms can be entered; the POI's cellar walls close the cut.
##  * digging: modifies the region height field; per-chunk deltas are saved as chunk blobs
##    ("t:<cx>_<cz>") so the composed world + deltas reproduce the edited terrain.

signal chunk_ready(key: Vector2i)
signal terrain_changed(aabb: AABB)

const CHUNK: float = 64.0
const NEAR_RADIUS: int = 6
const COLLISION_RADIUS: int = 2
const LOD_DIST: PackedFloat32Array = [150.0, 300.0]
const LOD_STEPS: PackedFloat32Array = [1.0, 2.0, 4.0]
const FAR_STEP: float = 16.0
const MAX_DIG_DEPTH: float = 3.0
const COLLISION_LAYER: int = 1
## Far tiles of unbuilt regions rise up to this far over the ground where the forest is closed and
## tall (the crown mass of grey firs).
const CANOPY_HEIGHT: float = 17.0
## Trees per 100 m² that close the canopy, and where a crown's mass sits as a share of tree height.
const CLOSED_CANOPY_DENSITY: float = 3.0
const CROWN_MASS_HEIGHT: float = 0.75

var world: WorldDef
## region id -> RegionTerrain (detailed, 1 m)
var regions: Dictionary = {}
## region id -> RegionTerrain (coarse, for far tiles of unbuilt regions)
var coarse: Dictionary = {}
var focus: Node3D
var textures: TerrainTextures

var _materials: Dictionary = {}
## Biome id -> Vector2(canopy, deciduous share) (far_canopy); set in setup.
var _canopy: Dictionary = {}
var _far_material: ShaderMaterial
var _fallback_material: Material
var _chunks: Dictionary = {}
var _pending: Dictionary = {}
var _far_root: Node3D
var _near_root: Node3D
var _center := Vector2i(999999, 999999)
var _deltas: Dictionary = {}
var _dirty_saves: Dictionary = {}
## Hybrid SDF volume (tunnels / mining) for columns dug past what the heightmap can express.
var volume: VolumeTerrain
## Cellar openings of the placed POIs (TD-026). Immutable after setup; read by mesh workers.
var holes := TerrainHoles.new()
## The Bloom's field over the built regions and its presence on screen (ADR-0025).
var bloom: BloomWorld
var _update_accum: float = 0.0


class Chunk:
	var key: Vector2i
	var lod: int = -1
	var mesh_instance: MeshInstance3D
	var body: StaticBody3D
	var has_collision: bool = false


func _ready() -> void:
	_near_root = Node3D.new()
	_near_root.name = "Near"
	add_child(_near_root)
	_far_root = Node3D.new()
	_far_root.name = "Far"
	add_child(_far_root)


## Prepares data. `built` = region ids composed at 1 m (others get coarse far tiles only).
func setup(p_world: WorldDef, built: Dictionary, p_coarse: Dictionary) -> void:
	world = p_world
	regions = built
	coarse = p_coarse
	textures = TerrainTextures.get_shared()
	for rid: String in regions:
		_materials[rid] = _make_region_material(regions[rid])
	_far_material = ShaderMaterial.new()
	_far_material.shader = load("res://assets/shaders/terrain_far.gdshader")
	_far_material.set_shader_parameter("macro_variation", textures.macro_variation)
	_far_material.set_shader_parameter("canopy_height", CANOPY_HEIGHT)
	# Near chunks in no region at all (off the map). Not the far material: that one discards the
	# whole near square.
	var ground := StandardMaterial3D.new()
	ground.albedo_color = Color(0.27, 0.24, 0.18)
	ground.roughness = 0.95
	_fallback_material = ground
	_build_grid()
	holes = TerrainHoles.from_regions(regions)
	bloom = BloomWorld.new()
	bloom.name = "Bloom"
	add_child(bloom)
	# The world loader may have built the field on its thread already.
	bloom.setup(prebuilt_bloom if prebuilt_bloom != null else BloomField.build(world, regions, ContentDB.instance.config(&"bloom") if ContentDB.instance != null else {}))
	prebuilt_bloom = null
	_canopy = far_canopy(ContentDB.instance)
	if not defer_far_tiles:
		_build_far_tiles()
	volume = VolumeTerrain.new()
	volume.name = "Volume"
	add_child(volume)
	volume.setup(self)
	volume.column_activated.connect(_on_volume_column)


func _make_region_material(rt: RegionTerrain) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://assets/shaders/terrain.gdshader")
	textures.apply_to(mat)
	BloomWorld.apply_web(mat)
	var imgs: Array[Image] = rt.splat_images()
	mat.set_shader_parameter("splat0", ImageTexture.create_from_image(imgs[0]))
	mat.set_shader_parameter("splat1", ImageTexture.create_from_image(imgs[1]))
	mat.set_shader_parameter("region_rect", Vector4(rt.rect.position.x, rt.rect.position.y, rt.rect.size.x, float(rt.height.width - 1)))
	var pal := PackedInt32Array()
	for name: String in rt.palette:
		pal.append(maxi(textures.layer_index(name), 0))
	while pal.size() < 8:
		pal.append(0)
	mat.set_shader_parameter("palette0", Vector4i(pal[0], pal[1], pal[2], pal[3]))
	mat.set_shader_parameter("palette1", Vector4i(pal[4], pal[5], pal[6], pal[7]))
	return mat


# --- Height queries ---------------------------------------------------------------------------

## Region grid lookup: index (col + row * cols) -> RegionTerrain (detailed preferred).
var _grid: Array = []


func _build_grid() -> void:
	_grid.clear()
	_grid.resize(world.cols * world.rows)
	for rid: String in world.regions:
		var c: Vector2i = WorldDef.cell_coords(str(world.regions[rid]["cell"]))
		_grid[c.x + c.y * world.cols] = regions.get(rid, coarse.get(rid))


func _terrain_for(x: float, z: float) -> RegionTerrain:
	var col: int = int(floor(x / world.region_size + world.cols * 0.5))
	var row: int = int(floor(z / world.region_size + world.rows * 0.5))
	if col < 0 or row < 0 or col >= world.cols or row >= world.rows:
		return null
	return _grid[col + row * world.cols]


## Forest canopy at world (x, z), 0..1 (see far_canopy): the biome's trees under the vegetation
## mask, so roads, water and clearings read open. Thread-safe for reads.
func canopy_at(x: float, z: float) -> float:
	var rt: RegionTerrain = _terrain_for(x, z)
	if rt == null:
		return 0.0
	return (_canopy.get(rt.biome_at(x, z), Vector2.ZERO) as Vector2).x * rt.veg_at(x, z)


## How far the Bloom has taken the ground at world (x, z), 0..1 (ADR-0025): the authored field plus
## the rooting mounds, as the shaders draw it. Thread-safe for reads.
func bloom_at(x: float, z: float) -> float:
	return bloom.field.at(x, z) if bloom != null and bloom.field != null else 0.0


## The authored Bloom field only (deterministic per world; the vegetation scatter reads this).
func bloom_base_at(x: float, z: float) -> float:
	return bloom.field.base_at(x, z) if bloom != null and bloom.field != null else 0.0


## Terrain height at world (x, z). Thread-safe for reads.
func height_at(x: float, z: float) -> float:
	var rt: RegionTerrain = _terrain_for(x, z)
	if rt != null:
		return rt.height.sample(x, z)
	return world.macro_height(x, z) if world != null else 0.0


func normal_at(x: float, z: float) -> Vector3:
	var e: float = 0.75
	return Vector3(height_at(x - e, z) - height_at(x + e, z), 2.0 * e, height_at(x, z - e) - height_at(x, z + e)).normalized()


## Detailed (1 m) region terrain at a position, or null.
func region_terrain_at(x: float, z: float) -> RegionTerrain:
	var rt: RegionTerrain = _terrain_for(x, z)
	return rt if rt != null and regions.has(rt.region_id) else null


## Dominant ground layer name (footsteps, particles); "" outside detailed regions.
func surface_at(x: float, z: float) -> String:
	var rt: RegionTerrain = region_terrain_at(x, z)
	return rt.surface_at(x, z) if rt != null else ""


static func chunk_of(x: float, z: float) -> Vector2i:
	return Vector2i(int(floor(x / CHUNK)), int(floor(z / CHUNK)))


# --- Streaming --------------------------------------------------------------------------------

## Joins in-flight mesh jobs so no worker touches freed data when the world goes away.
func _exit_tree() -> void:
	if _far_task >= 0:
		WorkerThreadPool.wait_for_group_task_completion(_far_task)
		_far_task = -1
	for key: Variant in _pending.keys():
		var job: Dictionary = _pending[key]
		if job.has("task"):
			WorkerThreadPool.wait_for_task_completion(job["task"])
	_pending.clear()


func _process(delta: float) -> void:
	if world == null or focus == null:
		return
	_collect_finished()
	_update_accum += delta
	if _update_accum < 0.2:
		return
	_update_accum = 0.0
	update_streaming(focus.global_position)


## Ensures chunks around `pos` exist at the right LOD. Call directly for synchronous warm-up.
func update_streaming(pos: Vector3, synchronous: bool = false) -> void:
	var c: Vector2i = chunk_of(pos.x, pos.z)
	if c != _center:
		_center = c
		var lo: Vector2 = Vector2(c.x - NEAR_RADIUS, c.y - NEAR_RADIUS) * CHUNK
		var hi: Vector2 = Vector2(c.x + NEAR_RADIUS + 1, c.y + NEAR_RADIUS + 1) * CHUNK
		var rect := Vector4(lo.x + 0.5, lo.y + 0.5, hi.x - 0.5, hi.y - 0.5)
		_far_material.set_shader_parameter("discard_rect", rect)
		# Drop chunks outside the square.
		for key: Vector2i in _chunks.keys():
			if absi(key.x - c.x) > NEAR_RADIUS or absi(key.y - c.y) > NEAR_RADIUS:
				_free_chunk(key)
	for dz: int in range(-NEAR_RADIUS, NEAR_RADIUS + 1):
		for dx: int in range(-NEAR_RADIUS, NEAR_RADIUS + 1):
			var key := Vector2i(c.x + dx, c.y + dz)
			var center := Vector2((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)
			var dist: float = center.distance_to(Vector2(pos.x, pos.z))
			var lod: int = 0 if dist < LOD_DIST[0] else (1 if dist < LOD_DIST[1] else 2)
			var ch: Chunk = _chunks.get(key)
			if ch == null:
				ch = Chunk.new()
				ch.key = key
				_chunks[key] = ch
			if ch.lod != lod and not _pending.has(key):
				_request_mesh(key, lod, synchronous)
			var want_col: bool = absi(dx) <= COLLISION_RADIUS and absi(dz) <= COLLISION_RADIUS
			if want_col != ch.has_collision:
				_set_collision(ch, want_col)


func _request_mesh(key: Vector2i, lod: int, synchronous: bool) -> void:
	var origin := Vector2(key.x * CHUNK, key.y * CHUNK)
	var step: float = LOD_STEPS[lod]
	var skirt: float = [1.0, 2.5, 6.0][lod]
	var job := {"key": key, "lod": lod, "origin": origin, "step": step, "skirt": skirt, "mesh": null}
	var hole: Callable = Callable()
	if volume != null and not volume.columns.is_empty() and _chunk_has_volume(key):
		hole = volume.is_volume_column
	var cut: Array[PackedVector2Array] = _cutters(key)
	# The worker fills its own slot: `job` gains "task" on this thread after the task has started,
	# and a dictionary written from two threads at once can corrupt itself.
	var out: Array = [null]
	job["out"] = out
	var fn := func() -> void:
		out[0] = TerrainMesher.build_chunk(origin, CHUNK, step, height_at, skirt, Callable(), hole, cut)
	if synchronous:
		fn.call()
		job["mesh"] = out[0]
		_apply_mesh(job)
		return
	job["task"] = WorkerThreadPool.add_task(fn, true, "terrain chunk")
	_pending[key] = job


func _collect_finished() -> void:
	for key: Vector2i in _pending.keys():
		var job: Dictionary = _pending[key]
		if WorkerThreadPool.is_task_completed(job["task"]):
			WorkerThreadPool.wait_for_task_completion(job["task"])
			_pending.erase(key)
			job["mesh"] = job["out"][0]
			_apply_mesh(job)


func _apply_mesh(job: Dictionary) -> void:
	var key: Vector2i = job["key"]
	var ch: Chunk = _chunks.get(key)
	if ch == null or job["mesh"] == null:
		return
	if ch.mesh_instance == null:
		ch.mesh_instance = MeshInstance3D.new()
		ch.mesh_instance.name = "C_%d_%d" % [key.x, key.y]
		ch.mesh_instance.position = Vector3(key.x * CHUNK, 0.0, key.y * CHUNK)
		_near_root.add_child(ch.mesh_instance)
	ch.mesh_instance.mesh = job["mesh"]
	ch.mesh_instance.material_override = _material_for(key)
	ch.lod = job["lod"]
	chunk_ready.emit(key)


func _material_for(key: Vector2i) -> Material:
	var center := Vector2((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)
	for rid: String in regions:
		var rt: RegionTerrain = regions[rid]
		if rt.rect.has_point(center):
			return _materials[rid]
	# Within 416 m of a built region's edge the near square reaches unbuilt ones: texture their
	# chunks from the coarse (16 m) splat, made on first use.
	for rid: String in coarse:
		var ct: RegionTerrain = coarse[rid]
		if ct.rect.has_point(center):
			if not _materials.has(rid):
				_materials[rid] = _make_region_material(ct)
			return _materials[rid]
	return _fallback_material


func _free_chunk(key: Vector2i) -> void:
	var ch: Chunk = _chunks.get(key)
	if ch == null:
		return
	if ch.mesh_instance != null:
		ch.mesh_instance.queue_free()
	if ch.body != null:
		ch.body.queue_free()
	_chunks.erase(key)


func _set_collision(ch: Chunk, on: bool) -> void:
	ch.has_collision = on
	if not on:
		if ch.body != null:
			ch.body.queue_free()
			ch.body = null
		return
	var origin := Vector2(ch.key.x * CHUNK, ch.key.y * CHUNK)
	var cut: Array[PackedVector2Array] = _cutters(ch.key)
	var body := StaticBody3D.new()
	body.name = "Col_%d_%d" % [ch.key.x, ch.key.y]
	body.collision_layer = COLLISION_LAYER
	body.collision_mask = 0
	body.set_meta(&"terrain", true)
	body.set_meta(&"damage_receiver", self)
	var cs := CollisionShape3D.new()
	if cut.is_empty():
		var shape := HeightMapShape3D.new()
		var vc: int = int(CHUNK) + 1
		shape.map_width = vc
		shape.map_depth = vc
		shape.map_data = TerrainMesher.collision_heights(origin, CHUNK, 1.0, _collision_height if _chunk_has_volume(ch.key) else height_at)
		cs.shape = shape
		# HeightMapShape3D is centred on its origin.
		cs.position = Vector3(CHUNK * 0.5, 0.0, CHUNK * 0.5)
	else:
		# A cellar cuts this chunk: exact trimesh (same triangles and cut as the render mesh at
		# 1 m); volume columns are left out instead of sunk.
		var tri := ConcavePolygonShape3D.new()
		tri.backface_collision = true
		var hole: Callable = volume.is_volume_column if _chunk_has_volume(ch.key) else Callable()
		tri.set_faces(TerrainMesher.surface_faces(origin, CHUNK, 1.0, height_at, hole, cut))
		cs.shape = tri
	body.add_child(cs)
	body.position = Vector3(origin.x, 0.0, origin.y)
	_near_root.add_child(body)
	ch.body = body


## True once every chunk within `radius` chunks of pos has a mesh (and collision where needed).
func is_ready_around(pos: Vector3, radius: int = 1) -> bool:
	var c: Vector2i = chunk_of(pos.x, pos.z)
	for dz: int in range(-radius, radius + 1):
		for dx: int in range(-radius, radius + 1):
			var ch: Chunk = _chunks.get(Vector2i(c.x + dx, c.y + dz))
			if ch == null or ch.mesh_instance == null:
				return false
	return true


# --- Far tiles ----------------------------------------------------------------------------------

func _build_far_tiles() -> void:
	for rid: String in world.regions:
		_add_far_tile(rid, _far_tile_mesh(rid))


## Set before setup(): a Bloom field built off the main thread (WorldLoader.bloom_field).
var prebuilt_bloom: BloomField = null
## Set before setup() to build the far tiles on worker threads through boot_steps() (ADR-0036:
## about 1.5 s of meshing that used to run in the load's one long main-thread frame).
var defer_far_tiles: bool = false
var _far_task: int = -1
var _far_ids: Array = []
var _far_meshes: Array = []


## Boot steps for a deferred setup: mesh every far tile in parallel, then add them.
func boot_steps() -> Array:
	if not defer_far_tiles:
		return []
	return [["Raising the far hills…", _start_far_tiles, "far tiles"], ["Raising the far hills…", _finish_far_tiles, "far tiles (add)"]]


func _start_far_tiles() -> void:
	_far_ids = world.regions.keys()
	_far_meshes.resize(_far_ids.size())
	_far_task = WorkerThreadPool.add_group_task(func(i: int) -> void: _far_meshes[i] = _far_tile_mesh(_far_ids[i]), _far_ids.size(), -1, false, "far tiles")


func _finish_far_tiles() -> bool:
	if _far_task >= 0:
		if not WorkerThreadPool.is_group_task_completed(_far_task):
			return false
		WorkerThreadPool.wait_for_group_task_completion(_far_task)
		_far_task = -1
	for i: int in _far_ids.size():
		_add_far_tile(_far_ids[i], _far_meshes[i])
	_far_meshes.clear()
	return true


## A far tile's mesh (pure data: reads the composed regions only, safe on a worker thread).
func _far_tile_mesh(rid: String) -> ArrayMesh:
	var built: Array[Rect2] = []
	for b: String in regions:
		built.append(world.region_rect(b))
	var rect: Rect2 = world.region_rect(rid)
	var rt: RegionTerrain = regions.get(rid, coarse.get(rid))
	# Built regions draw their own trees (impostors out to 1.2 km); the others get a canopy,
	# raised into the mesh itself so its normals light the forest edges.
	var grid: PackedVector2Array = _far_canopy_grid(rt, rect, {} if regions.has(rid) else _canopy, built)
	var n: int = int(round(rect.size.x / FAR_STEP)) + 3
	var at := func(x: float, z: float) -> Vector2:
		return grid[clampi(int(round((z - rect.position.y) / FAR_STEP)) + 1, 0, n - 1) * n + clampi(int(round((x - rect.position.x) / FAR_STEP)) + 1, 0, n - 1)]
	var height_fn := func(x: float, z: float) -> float: return height_at(x, z) + (at.call(x, z) as Vector2).x * CANOPY_HEIGHT
	var color_fn := func(x: float, z: float) -> Color: return _far_color(rt, x, z, at.call(x, z))
	return TerrainMesher.build_chunk(rect.position, rect.size.x, FAR_STEP, height_fn, 12.0, color_fn)


func _add_far_tile(rid: String, mesh: ArrayMesh) -> void:
	var rect: Rect2 = world.region_rect(rid)
	var mi := MeshInstance3D.new()
	mi.name = "Far_" + rid
	mi.mesh = mesh
	mi.material_override = _far_material
	mi.position = Vector3(rect.position.x, -0.35, rect.position.y)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_far_root.add_child(mi)


## {biome id: Vector2(canopy 0..1, deciduous share 0..1)} from the biomes' trees. Canopy is cover
## (tree density over a closed canopy's) times crown height over CANOPY_HEIGHT: the far tile rises
## canopy x CANOPY_HEIGHT, so birch groves stand lower than fir forest.
static func far_canopy(db: Node) -> Dictionary:
	var out: Dictionary = {}
	if db == null:
		return out
	for b: ContentDef in db.all(&"biome"):
		var veg: Dictionary = (b as BiomeDef).vegetation
		var trees: float = 0.0
		var leafy: float = 0.0
		var tall: float = 0.0
		for sid: Variant in veg:
			var sp := db.get_def(&"species", StringName(sid)) as SpeciesDef
			if sp == null or sp.veg_kind != "tree":
				continue
			var d: float = float(veg[sid])
			trees += d
			tall += d * (sp.height_range.x + sp.height_range.y) * 0.5
			if sp.deciduous:
				leafy += d
		if trees <= 0.0:
			out[str(b.id)] = Vector2.ZERO
			continue
		var crown: float = clampf(tall / trees * CROWN_MASS_HEIGHT / CANOPY_HEIGHT, 0.0, 1.0)
		out[str(b.id)] = Vector2(clampf(trees / CLOSED_CANOPY_DENSITY, 0.0, 1.0) * crown, leafy / trees)
	return out


## Canopy (cover, deciduous share) on a far tile's padded vertex grid, (size / FAR_STEP + 3)². Cover
## follows the biome's tree density and the vegetation mask (roads, water and clearings stay open),
## and fades out near built regions, whose own trees take over. Quantised as the shader decodes it.
func _far_canopy_grid(rt: RegionTerrain, rect: Rect2, canopy: Dictionary, built: Array[Rect2]) -> PackedVector2Array:
	var n: int = int(round(rect.size.x / FAR_STEP)) + 3
	var out := PackedVector2Array()
	out.resize(n * n)
	if canopy.is_empty() or rt == null:
		return out
	for j: int in n:
		var z: float = rect.position.y + (j - 1) * FAR_STEP
		for i: int in n:
			var x: float = rect.position.x + (i - 1) * FAR_STEP
			var c: Vector2 = canopy.get(rt.biome_at(x, z), Vector2.ZERO)
			var cover: float = c.x * rt.veg_at(x, z)
			for r: Rect2 in built:
				cover *= smoothstep(48.0, 192.0, _rect_distance(r, x, z))
			out[j * n + i] = Vector2(roundf(cover * 15.0) / 15.0, roundf(c.y * 15.0) / 15.0)
	return out


static func _rect_distance(r: Rect2, x: float, z: float) -> float:
	var dx: float = maxf(maxf(r.position.x - x, x - r.end.x), 0.0)
	var dz: float = maxf(maxf(r.position.y - z, z - r.end.y), 0.0)
	return sqrt(dx * dx + dz * dz)


## Far-tile vertex alpha: canopy cover in the high 4 bits, deciduous share in the low 4 (decoded per
## vertex by terrain_far.gdshader).
static func pack_canopy(cover: float, deciduous: float) -> float:
	return (roundf(clampf(cover, 0.0, 1.0) * 15.0) * 16.0 + roundf(clampf(deciduous, 0.0, 1.0) * 15.0)) / 255.0


func _far_color(rt: RegionTerrain, x: float, z: float, canopy: Vector2) -> Color:
	if rt == null:
		return Color(0.18, 0.2, 0.12, 0.0)
	var w: PackedFloat32Array = rt.splat_at(x, z)
	var col := Color(0, 0, 0)
	var total: float = 0.0
	for c: int in mini(8, rt.palette.size()):
		var fc: Color = TerrainTextures.FALLBACK_COLORS.get(rt.palette[c], Color(0.3, 0.3, 0.3))
		col += fc * w[c]
		total += w[c]
	col = col / maxf(total, 0.001)
	# Forested biomes read darker from afar (canopy shadowing).
	var b: String = rt.biome_at(x, z)
	if b == "conifer_forest":
		col = col.lerp(Color(0.08, 0.12, 0.07), 0.55)
	elif b == "birch_grove":
		col = col.lerp(Color(0.25, 0.27, 0.12), 0.3)
	col.a = pack_canopy(canopy.x, canopy.y)
	return col


# --- Volume hand-off -------------------------------------------------------------------------------

## Heightfield height (what the volume initialises from; ignores volume edits).
func base_height_at(x: float, z: float) -> float:
	return height_at(x, z)


func _chunk_has_volume(key: Vector2i) -> bool:
	if volume == null or volume.columns.is_empty():
		return false
	var per: int = int(CHUNK / VolumeTerrain.SIZE)
	for dz: int in per:
		for dx: int in per:
			if volume.columns.has(Vector2i(key.x * per + dx, key.y * per + dz)):
				return true
	return false


## Heightmap collision sinks out of the way where the volume owns the ground.
func _collision_height(x: float, z: float) -> float:
	var h: float = height_at(x, z)
	return h - 40.0 if volume.is_volume_column(x - 0.01, z - 0.01) and volume.is_volume_column(x + 0.01, z + 0.01) else h


# --- POI cellars (TD-026) -------------------------------------------------------------------------

## Cellar footprints (world-XZ convex pieces) that cut a near chunk.
func _cutters(key: Vector2i) -> Array[PackedVector2Array]:
	if holes == null or holes.is_empty():
		return []
	return holes.pieces_in(Rect2(key.x * CHUNK, key.y * CHUNK, CHUNK, CHUNK))


## Whether (x, z) lies over a POI cellar, where the heightmap has been cut away.
func in_cellar(x: float, z: float) -> bool:
	return holes != null and holes.contains(x, z)


## The ground under a point: the cellar floor when the point is down in a cut-out POI cellar
## (anywhere under the ground floor's slab, fallen through the cellar floor included), else the
## terrain height. height_at() keeps reporting the heightfield (ADR-0007); fell-through-the-world
## checks and settling things where they are want this.
func ground_below(pos: Vector3) -> float:
	var h: float = height_at(pos.x, pos.z)
	if holes == null or holes.is_empty():
		return h
	var hole: TerrainHoles.Hole = holes.hole_at(pos.x, pos.z)
	return hole.floor_y if hole != null and pos.y < hole.ceiling_y else h


func _on_volume_column(col: Vector2i) -> void:
	var key: Vector2i = chunk_of(col.x * VolumeTerrain.SIZE + 1.0, col.y * VolumeTerrain.SIZE + 1.0)
	var ch: Chunk = _chunks.get(key)
	if ch != null:
		_request_mesh(key, maxi(ch.lod, 0), true)
		if ch.has_collision:
			_set_collision(ch, false)
			_set_collision(ch, true)


## Tool hits on the ground: shovels dig the heightmap; past its depth limit, into steep faces or
## inside an existing tunnel the SDF volume takes over (pickaxes always cut the volume).
func take_damage(info: DamageInfo) -> void:
	var dig: float = float(info.tool_power.get("dig", 0.0))
	var mine: float = float(info.tool_power.get("mine", 0.0))
	if dig <= 0.0 and mine <= 0.0:
		return
	var p: Vector3 = info.hit_pos
	var n: Vector3 = normal_at(p.x, p.z)
	var collider: Node = info.collider as Node
	var in_volume: bool = collider != null and collider.has_meta(&"volume")
	var rt: RegionTerrain = region_terrain_at(p.x, p.z)
	var at_limit: bool = false
	if rt != null:
		var base: HeightField = _base_heights(rt)
		at_limit = height_at(p.x, p.z) <= base.sample(p.x, p.z) - MAX_DIG_DEPTH + 0.05
	var moved: float = 0.0
	if in_volume or mine > 0.0 or at_limit or n.y < 0.6:
		var center: Vector3 = p + info.direction.normalized() * 0.35
		moved = volume.edit_sphere(center, 0.9 if mine <= 0.0 else 0.75, 0.9 * maxf(dig, mine))
	else:
		moved = modify(p, 1.1, 0.3 * dig, "dig")
	if moved <= 0.01:
		return
	Audio.play_3d(&"sfx/dig_shovel", p, {"volume_db": -3.0})
	FxLibrary.burst(self, "dirt", p, n, 0.8)
	if Stimuli.current != null:
		Stimuli.current.emit_sound(p, 12.0, &"dig", info.source_id)
	if Game.session != null:
		Game.session.heat.add(p, float(Content.config(&"heat").get("sources", {}).get("dig" if mine <= 0.0 else "mine", 0.5)))
		var ps: PlayerState = Game.session.players.get(info.source_id)
		if ps != null:
			var rng: RandomNumberGenerator = Game.session.rng.stream("dig")
			if rng.randf() < 0.18 + (0.4 if mine > 0.0 else 0.0):
				Game.execute(&"world.pickup_item", {"player": String(ps.id), "item": "stone", "count": 1})
			ps.progression.award("dig")


# --- Digging ------------------------------------------------------------------------------------

## mode: "dig" lowers, "raise" raises, "flatten" moves toward target_y, "smooth" averages.
## Returns the volume of earth moved (m^3, positive = removed) for item yields.
func modify(center: Vector3, radius: float, amount: float, mode: String = "dig", target_y: float = 0.0) -> float:
	var rt: RegionTerrain = region_terrain_at(center.x, center.z)
	if rt == null:
		return 0.0
	var hf: HeightField = rt.height
	var base: HeightField = _base_heights(rt)
	var r_cells: int = int(ceil(radius / hf.spacing)) + 1
	var ci: int = int(round((center.x - hf.origin.x) / hf.spacing))
	var cj: int = int(round((center.z - hf.origin.y) / hf.spacing))
	var moved: float = 0.0
	var touched: Dictionary = {}
	# Edit a private copy and publish it whole (_publish_heights): worker threads read these heights
	# all the time (chunk meshing, scatter, weather, the Hum's flow field).
	var original: PackedFloat32Array = hf.heights
	var heights: PackedFloat32Array = hf.heights.duplicate()
	for j: int in range(cj - r_cells, cj + r_cells + 1):
		for i: int in range(ci - r_cells, ci + r_cells + 1):
			if i < 0 or j < 0 or i >= hf.width or j >= hf.depth:
				continue
			var x: float = hf.origin.x + i * hf.spacing
			var z: float = hf.origin.y + j * hf.spacing
			var d: float = Vector2(x, z).distance_to(Vector2(center.x, center.z)) / radius
			if d >= 1.0:
				continue
			var k: float = 0.5 + 0.5 * cos(d * PI)
			var idx: int = j * hf.width + i
			var h0: float = heights[idx]
			var nh: float = h0
			match mode:
				"dig":
					nh = maxf(h0 - amount * k, base.heights[idx] - MAX_DIG_DEPTH)
				"raise":
					nh = minf(h0 + amount * k, base.heights[idx] + MAX_DIG_DEPTH)
				"flatten":
					nh = move_toward(h0, target_y, amount * k)
				"smooth":
					var acc: float = 0.0
					for oj: int in range(-1, 2):
						for oi: int in range(-1, 2):
							acc += original[clampi(j + oj, 0, hf.depth - 1) * hf.width + clampi(i + oi, 0, hf.width - 1)]
					nh = lerpf(h0, acc / 9.0, amount * k)
			heights[idx] = nh
			moved += (h0 - nh) * hf.spacing * hf.spacing
			touched[chunk_of(x, z)] = true
			# Samples on chunk borders belong to neighbours too.
			touched[chunk_of(x - 0.01, z - 0.01)] = true
	_publish_heights(hf, heights)
	for key: Vector2i in touched:
		_record_delta(rt, key)
		var ch: Chunk = _chunks.get(key)
		if ch != null:
			_request_mesh(key, ch.lod if ch.lod >= 0 else 0, true)
			if ch.has_collision:
				_set_collision(ch, false)
				_set_collision(ch, true)
	var aabb := AABB(center - Vector3(radius, MAX_DIG_DEPTH, radius), Vector3(radius, MAX_DIG_DEPTH, radius) * 2.0)
	terrain_changed.emit(aabb)
	Events.terrain_modified.emit(aabb)
	return moved


## Height arrays replaced by an edit, kept alive for RETIRE_MSEC: a worker that fetched the old
## array just before the swap may still be reading it, and freeing it under that worker crashes
## (use after free; more likely the more threads a machine runs). [ticks_msec, array] oldest first.
var _retired: Array = []
const RETIRE_MSEC: int = 20000
const RETIRE_MIN: int = 4


## Swaps a region's heights for an edited copy. Readers on other threads see the old array or the
## new one, never a buffer freed under them, and never a half-written edit.
func _publish_heights(hf: HeightField, heights: PackedFloat32Array) -> void:
	var now: int = Time.get_ticks_msec()
	_retired.append([now, hf.heights])
	hf.heights = heights
	while _retired.size() > RETIRE_MIN and now - int(_retired[0][0]) > RETIRE_MSEC:
		_retired.pop_front()


## Composed (unedited) heights per region, kept to clamp digging depth and compute deltas.
var _base_cache: Dictionary = {}


func _base_heights(rt: RegionTerrain) -> HeightField:
	if not _base_cache.has(rt.region_id):
		var copy := HeightField.new()
		copy.origin = rt.height.origin
		copy.spacing = rt.height.spacing
		copy.width = rt.height.width
		copy.depth = rt.height.depth
		copy.heights = rt.height.heights.duplicate()
		_base_cache[rt.region_id] = copy
	return _base_cache[rt.region_id]


func _record_delta(rt: RegionTerrain, key: Vector2i) -> void:
	var hf: HeightField = rt.height
	var base: HeightField = _base_heights(rt)
	var vc: int = int(CHUNK) + 1
	var delta := PackedFloat32Array()
	delta.resize(vc * vc)
	var any: bool = false
	for j: int in vc:
		for i: int in vc:
			var gx: int = int(round((key.x * CHUNK + i - hf.origin.x) / hf.spacing))
			var gz: int = int(round((key.y * CHUNK + j - hf.origin.y) / hf.spacing))
			if gx < 0 or gz < 0 or gx >= hf.width or gz >= hf.depth:
				continue
			var d: float = hf.heights[gz * hf.width + gx] - base.heights[gz * hf.width + gx]
			delta[j * vc + i] = d
			any = any or absf(d) > 0.0001
	var k: String = "t:%d_%d" % [key.x, key.y]
	if any:
		_deltas[k] = delta
	else:
		_deltas.erase(k)
	_dirty_saves[k] = true


## Writes edited chunk deltas into the session (called on Events.game_saving).
func save_into(ws: WorldState) -> void:
	if volume != null:
		volume.save_into(ws)
	for k: String in _dirty_saves:
		if _deltas.has(k):
			ws.chunk_blobs[k] = (_deltas[k] as PackedFloat32Array).to_byte_array().compress(FileAccess.COMPRESSION_ZSTD)
		else:
			ws.chunk_blobs.erase(k)
	_dirty_saves.clear()


## Applies saved deltas to freshly composed heights (call after setup, before streaming).
func load_from(ws: WorldState) -> void:
	var vc: int = int(CHUNK) + 1
	for k: Variant in ws.chunk_blobs.keys():
		var key_s: String = str(k)
		if not key_s.begins_with("t:"):
			continue
		var raw: PackedByteArray = (ws.chunk_blobs[k] as PackedByteArray).decompress(vc * vc * 4, FileAccess.COMPRESSION_ZSTD)
		var delta: PackedFloat32Array = raw.to_float32_array()
		var key: Vector2i = Ids.parse_chunk_key(key_s.substr(2))
		var rt: RegionTerrain = region_terrain_at(key.x * CHUNK + 1.0, key.y * CHUNK + 1.0)
		if rt == null:
			continue
		_base_heights(rt)
		var hf: HeightField = rt.height
		var heights: PackedFloat32Array = hf.heights.duplicate()
		for j: int in vc:
			for i: int in vc:
				var gx: int = int(round((key.x * CHUNK + i - hf.origin.x) / hf.spacing))
				var gz: int = int(round((key.y * CHUNK + j - hf.origin.y) / hf.spacing))
				if gx >= 0 and gz >= 0 and gx < hf.width and gz < hf.depth:
					var base: HeightField = _base_cache[rt.region_id]
					heights[gz * hf.width + gx] = base.heights[gz * hf.width + gx] + delta[j * vc + i]
		_publish_heights(hf, heights)
		_deltas[key_s] = delta
	if volume != null:
		volume.load_from(ws)
