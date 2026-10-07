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
## A region's 1 m terrain came into or left memory (ADR-0038, region streaming).
signal region_attached(rid: String)
signal region_detached(rid: String)
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
	## The collision being built on a worker ({} = none): {task, out: [shape data], kind}.
	var col_job: Dictionary = {}


func _ready() -> void:
	_near_root = Node3D.new()
	_near_root.name = "Near"
	add_child(_near_root)
	_far_root = Node3D.new()
	_far_root.name = "Far"
	add_child(_far_root)


## Prepares data. `built` = region ids composed at 1 m (others get coarse far tiles only).
## With defer_materials the textures and the regions' materials are made in boot_steps() instead.
func setup(p_world: WorldDef, built: Dictionary, p_coarse: Dictionary) -> void:
	world = p_world
	regions = built
	coarse = p_coarse
	if not defer_materials:
		_make_materials()
		for rid: String in regions:
			_make_material_of(rid)
	# Near chunks in no region at all (off the map). Not the far material: that one discards the
	# whole near square.
	var ground := StandardMaterial3D.new()
	ground.albedo_color = Color(0.27, 0.24, 0.18)
	ground.roughness = 0.95
	_fallback_material = ground
	_build_grid()
	for rid: String in regions:
		_region_holes[rid] = _take_holes(regions[rid])
	_publish_holes()
	bloom = BloomWorld.new()
	bloom.name = "Bloom"
	add_child(bloom)
	# The world loader may have built the field on its thread already.
	var bcfg: Dictionary = ContentDB.instance.config(&"bloom") if ContentDB.instance != null else {}
	var tiles: BloomTiles = prebuilt_bloom if prebuilt_bloom != null else BloomTiles.build(world, regions, bcfg, false)
	prebuilt_bloom = null
	if tiles.lazy:
		# A tile not composed yet is read from its zones over the ground as it is now (1 m where
		# attached). Set before any worker reads the field; never replaced.
		tiles.mask_fn = ground_terrain_at
	# The window starts over the 1 m regions (a streamed world's first area); it follows the focus.
	var start := Rect2()
	for rid: String in regions:
		start = (regions[rid] as RegionTerrain).rect if start.size == Vector2.ZERO else start.merge((regions[rid] as RegionTerrain).rect)
	# A field composed whole (the main map, a world loaded without streaming) is shown whole, as
	# before tiles; a streamed world's through a window around the player.
	bloom.setup(tiles, self, start.get_center() if start.size != Vector2.ZERO else Vector2(NAN, NAN), bcfg, not tiles.lazy)
	_canopy = far_canopy(ContentDB.instance)
	if not defer_far_tiles:
		_build_far_tiles()
	volume = VolumeTerrain.new()
	volume.name = "Volume"
	add_child(volume)
	volume.setup(self)
	volume.column_activated.connect(_on_volume_column)


## Set before setup(): the layer textures' data, prepared on the world-load thread
## (WorldLoader.terrain_textures, TD-197); null makes them here.
var prepared_textures: TerrainTextures = null
## Set before setup() to make the layer textures and the regions' materials in boot_steps(), one
## step each (TD-197: they were ~140 ms of the boot's terrain frame on a first load).
var defer_materials: bool = false


## The shared layer textures and the far tiles' material.
func _make_materials() -> void:
	if textures != null:
		return
	textures = TerrainTextures.adopt(prepared_textures)
	prepared_textures = null
	_far_material = ShaderMaterial.new()
	_far_material.shader = load("res://assets/shaders/terrain_far.gdshader")
	_far_material.set_shader_parameter("macro_variation", textures.macro_variation)
	_far_material.set_shader_parameter("canopy_height", CANOPY_HEIGHT)


## A region's material, unless it has one already or is no longer attached (a deferred step).
func _make_material_of(rid: String) -> void:
	if regions.has(rid) and not _materials.has(rid):
		_materials[rid] = _make_region_material(regions[rid])


## A region's cellars: compiled on the thread that composed it when it carries them (the world
## loader, RegionStreamer's compose worker; meta "holes"), else here.
func _take_holes(rt: RegionTerrain) -> TerrainHoles:
	if rt.has_meta(&"holes"):
		var th: TerrainHoles = rt.get_meta(&"holes")
		rt.remove_meta(&"holes")
		return th
	return TerrainHoles.from_regions({rt.region_id: rt})


## The splat images of a region's material, pure data, safe on a worker thread: the composing
## thread stores them as meta "splat" (prepare_splat) so an attach only uploads them (TD-106).
static func prepare_splat(rt: RegionTerrain) -> void:
	rt.set_meta(&"splat", rt.splat_images())


func _make_region_material(rt: RegionTerrain) -> ShaderMaterial:
	if textures == null:
		_make_materials()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://assets/shaders/terrain.gdshader")
	textures.apply_to(mat)
	BloomWorld.apply_web(mat)
	var imgs: Array[Image] = []
	if rt.has_meta(&"splat"):
		imgs.assign(rt.get_meta(&"splat"))
		rt.remove_meta(&"splat")
	else:
		imgs = rt.splat_images()
	# The upload stays here: texture RIDs are made on the main thread (TD-103).
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


## The grid and `regions` are replaced whole when regions attach or detach (ADR-0038), and
## worker threads (chunk meshing, scatter, weather, the flow field) read them through height_at
## meanwhile. Replacing an Array or Dictionary member is not atomic in GDScript (the old one is
## released and the member left null for a moment before the new one is stored), so the swap and
## the workers' reads take _lock; main-thread code reads them freely (only it writes them).
var _lock := Mutex.new()


func _build_grid() -> void:
	var g: Array = []
	g.resize(world.cols * world.rows)
	for rid: String in world.regions:
		var c: Vector2i = WorldDef.cell_coords(str(world.regions[rid]["cell"]))
		g[c.x + c.y * world.cols] = regions.get(rid, coarse.get(rid))
	_lock.lock()
	_grid = g
	_lock.unlock()


func _terrain_for(x: float, z: float) -> RegionTerrain:
	var col: int = int(floor(x / world.region_size + world.cols * 0.5))
	var row: int = int(floor(z / world.region_size + world.rows * 0.5))
	if col < 0 or row < 0 or col >= world.cols or row >= world.rows:
		return null
	_lock.lock()
	var rt: RegionTerrain = _grid[col + row * world.cols]
	_lock.unlock()
	return rt


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
	return bloom.tiles.at(x, z) if bloom != null and bloom.tiles != null else 0.0


## The authored Bloom field only (deterministic per world; the vegetation scatter reads this).
func bloom_base_at(x: float, z: float) -> float:
	return bloom.tiles.base_at(x, z) if bloom != null and bloom.tiles != null else 0.0


## The terrain that answers height_at at (x, z): the region's 1 m terrain when attached, else its
## coarse one (null off the map). Thread-safe.
func ground_terrain_at(x: float, z: float) -> RegionTerrain:
	return _terrain_for(x, z)


## Terrain height at world (x, z). Thread-safe: the sample is taken under _lock, which edits of
## the heights also hold (see modify()).
func height_at(x: float, z: float) -> float:
	_lock.lock()
	var rt: RegionTerrain = _terrain_for(x, z)
	var h: float = rt.height.sample(x, z) if rt != null else (world.macro_height(x, z) if world != null else 0.0)
	_lock.unlock()
	return h


func normal_at(x: float, z: float) -> Vector3:
	var e: float = 0.75
	return Vector3(height_at(x - e, z) - height_at(x + e, z), 2.0 * e, height_at(x, z - e) - height_at(x, z + e)).normalized()


## Detailed (1 m) region terrain at a position, or null.
func region_terrain_at(x: float, z: float) -> RegionTerrain:
	var rt: RegionTerrain = _terrain_for(x, z)
	if rt == null:
		return null
	_lock.lock()
	var detailed: bool = regions.has(rt.region_id)
	_lock.unlock()
	return rt if detailed else null


## Dominant ground layer name (footsteps, particles); "" outside detailed regions.
func surface_at(x: float, z: float) -> String:
	var rt: RegionTerrain = region_terrain_at(x, z)
	return rt.surface_at(x, z) if rt != null else ""


static func chunk_of(x: float, z: float) -> Vector2i:
	return Vector2i(int(floor(x / CHUNK)), int(floor(z / CHUNK)))


# --- Regions in and out (ADR-0038) -----------------------------------------------------------

## Brings a region's 1 m terrain into play: its saved digs applied, published in a new `regions`
## and grid (under _lock), a material made, the near chunks over it re-meshed and their collision
## rebuilt. `pristine`: its unedited heights when the caller has them (the dig limit must never be
## taken from already-edited heights).
func attach_region(rt: RegionTerrain, pristine: HeightField = null) -> void:
	var rid: String = rt.region_id
	var t: int = Time.get_ticks_usec()
	attach_parts = {}
	if pristine != null:
		_base_cache[rid] = pristine
	_apply_deltas(rt)
	t = _part("deltas", t)
	var next: Dictionary = regions.duplicate()
	next[rid] = rt
	_lock.lock()
	regions = next
	_lock.unlock()
	_build_grid()
	t = _part("grid", t)
	# Its splat images were made on the compose worker when it streamed in (TD-106).
	_materials[rid] = _make_region_material(rt)
	t = _part("material", t)
	# Cellars of the region's buildings (a new object: workers hold the old one).
	# Compiled on the compose worker when it streamed in (RegionStreamer), else here.
	_region_holes[rid] = _take_holes(rt)
	_publish_holes()
	t = _part("holes", t)
	# The Bloom's tiles over the region, masked by its 1 m ground (TD-106): composed on the
	# streamer's worker, here otherwise (tests, tools). Before the chunks re-mesh, so the scatter
	# reads the field the region keeps from now on.
	if bloom != null and bloom.tiles != null and bloom.tiles.lazy:
		var made: Array = rt.get_meta(&"bloom_tiles") if rt.has_meta(&"bloom_tiles") else bloom.tiles.compose_region(rt)
		if rt.has_meta(&"bloom_tiles"):
			rt.remove_meta(&"bloom_tiles")
		bloom.install(made)
		t = _part("bloom", t)
	_refresh_chunks(rt.rect)
	_remesh_far_tile(rid)
	t = _part("chunks", t)
	region_attached.emit(rid)
	_part("listeners", t)


## What the last attach spent where (ms by part), for StreamMeter's slow-step log.
var attach_parts: Dictionary = {}


func _part(name: String, t0: int) -> int:
	var now: int = Time.get_ticks_usec()
	attach_parts[name] = snappedf(float(now - t0) / 1000.0, 0.1)
	return now


## Takes a region's 1 m terrain out of play: the coarse terrain (if any) answers height_at there
## again. Its digs stay in _deltas (saved as before) and come back on the next attach.
func detach_region(rid: String) -> void:
	if not regions.has(rid):
		return
	var rt: RegionTerrain = regions[rid]
	var rect: Rect2 = rt.rect
	var t: int = Time.get_ticks_usec()
	attach_parts = {}
	var next: Dictionary = regions.duplicate()
	next.erase(rid)
	_lock.lock()
	regions = next
	_lock.unlock()
	_build_grid()
	_materials.erase(rid)
	t = _part("grid", t)
	# _base_cache keeps a dug region's pristine heights (4 MB) across the detach: its digs live on
	# in _deltas and are re-applied over them on the next attach, whatever the object then holds.
	_region_holes.erase(rid)
	_publish_holes()
	t = _part("holes", t)
	_refresh_chunks(rect)
	_remesh_far_tile(rid)
	t = _part("chunks", t)
	region_detached.emit(rid)
	_part("listeners", t)


## Re-meshes the live near chunks over a rect (plus one chunk around it, whose skirts and normals
## read across the border) and rebuilds their collision.
func _refresh_chunks(rect: Rect2) -> void:
	var grown: Rect2 = rect.grow(CHUNK)
	for key: Vector2i in _chunks.keys():
		var ch: Chunk = _chunks[key]
		if not grown.intersects(Rect2(key.x * CHUNK, key.y * CHUNK, CHUNK, CHUNK)):
			continue
		if ch.lod >= 0 and not _pending.has(key):
			_request_mesh(key, ch.lod, false)
		if ch.has_collision:
			_rebuild_collision(ch, false)
	_start_queued()


# --- Streaming --------------------------------------------------------------------------------

## Joins in-flight mesh jobs so no worker touches freed data when the world goes away.
func _exit_tree() -> void:
	for ch: Chunk in _col_pending:
		if ch.col_job.has("task"):
			WorkerThreadPool.wait_for_task_completion(int(ch.col_job["task"]))
	_col_pending.clear()
	_task_queue.clear()
	if _far_task >= 0:
		WorkerThreadPool.wait_for_group_task_completion(_far_task)
		_far_task = -1
	for key: Variant in _pending.keys():
		var job: Dictionary = _pending[key]
		if job.has("task"):
			WorkerThreadPool.wait_for_task_completion(job["task"])
	_pending.clear()
	for job2: Dictionary in _far_jobs.values():
		WorkerThreadPool.wait_for_task_completion(int(job2["task"]))
	_far_jobs.clear()


func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_process_body(delta)
	StreamMeter.note("terrain", t0)


func _process_body(delta: float) -> void:
	if world == null or focus == null:
		return
	_collect_finished()
	_collect_collision()
	_start_queued()
	if not _far_jobs.is_empty():
		_collect_far_jobs()
	_update_accum += delta
	if _update_accum < 0.2:
		return
	_update_accum = 0.0
	update_streaming(focus.global_position)


## Ensures chunks around `pos` exist at the right LOD. Call directly for synchronous warm-up.
func update_streaming(pos: Vector3, synchronous: bool = false) -> void:
	_make_materials()
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
	# The graphics preset's terrain_lod_bias scales the LOD rings (low 0.6 .. ultra 1.3).
	var bias: float = float(Settings.gfx("terrain_lod_bias", 1.0))
	for dz: int in range(-NEAR_RADIUS, NEAR_RADIUS + 1):
		for dx: int in range(-NEAR_RADIUS, NEAR_RADIUS + 1):
			var key := Vector2i(c.x + dx, c.y + dz)
			var center := Vector2((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)
			var dist: float = center.distance_to(Vector2(pos.x, pos.z))
			var lod: int = 0 if dist < LOD_DIST[0] * bias else (1 if dist < LOD_DIST[1] * bias else 2)
			var ch: Chunk = _chunks.get(key)
			if ch == null:
				ch = Chunk.new()
				ch.key = key
				_chunks[key] = ch
			if ch.lod != lod and not _pending.has(key):
				_request_mesh(key, lod, synchronous)
			var want_col: bool = absi(dx) <= COLLISION_RADIUS and absi(dz) <= COLLISION_RADIUS
			if want_col != ch.has_collision:
				_set_collision(ch, want_col, synchronous)
	_start_queued()


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
		out[0] = TerrainMesher.build_chunk_job(origin, CHUNK, step, height_at, skirt, Callable(), hole, cut)
	if synchronous:
		fn.call()
		job["mesh"] = TerrainMesher.finish(out[0])
		_apply_mesh(job)
		return
	_pending[key] = job
	_queue_task(job, fn, "terrain chunk")


## Main-thread time a frame spends installing finished chunk meshes and collision bodies: the 169
## meshes and 25 bodies of a spawn otherwise all land in one frame (~0.5 s, ADR-0036); the rest
## wait for the next frames.
const COLLECT_BUDGET_MS: float = 6.0


func _collect_finished() -> void:
	var t0: int = Time.get_ticks_usec()
	for key: Vector2i in _pending.keys():
		var job: Dictionary = _pending[key]
		if job.has("task") and WorkerThreadPool.is_task_completed(job["task"]):
			WorkerThreadPool.wait_for_task_completion(job["task"])
			_pending.erase(key)
			job["mesh"] = TerrainMesher.finish(job["out"][0])
			_apply_mesh(job)
			if float(Time.get_ticks_usec() - t0) / 1000.0 >= COLLECT_BUDGET_MS:
				return


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
			# Made now if a chunk lands before its deferred boot step ran.
			_make_material_of(rid)
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


## Turns a chunk's collision on or off. On, unless `sync`: built on a worker (the heights or the
## cellar trimesh are ~25 ms of GDScript a chunk; the 25 around a spawn took 0.6 s of one frame,
## ADR-0036) and installed when it comes back (_collect_collision).
func _set_collision(ch: Chunk, on: bool, sync: bool = true) -> void:
	ch.has_collision = on
	if not on:
		ch.col_job = {}
		if ch.body != null:
			ch.body.queue_free()
			ch.body = null
		return
	_rebuild_collision(ch, sync)


## Builds a chunk's collision anew, keeping the old body until the new one replaces it (so the
## ground never disappears under someone). `sync`: now, on this thread (digging, which must
## collide with the new ground at once; chunks with volume columns, whose height reads volumes).
func _rebuild_collision(ch: Chunk, sync: bool) -> void:
	var origin := Vector2(ch.key.x * CHUNK, ch.key.y * CHUNK)
	var cut: Array[PackedVector2Array] = _cutters(ch.key)
	var has_volume: bool = _chunk_has_volume(ch.key)
	var out: Array = [null]
	var job: Dictionary = {"out": out, "kind": "faces" if not cut.is_empty() else "heights"}
	var hole: Callable = volume.is_volume_column if has_volume else Callable()
	var fn := func() -> void:
		if cut.is_empty():
			out[0] = TerrainMesher.collision_heights(origin, CHUNK, 1.0, height_at)
		else:
			out[0] = TerrainMesher.surface_faces(origin, CHUNK, 1.0, height_at, hole, cut)
	if sync or has_volume:
		if cut.is_empty() and has_volume:
			out[0] = TerrainMesher.collision_heights(origin, CHUNK, 1.0, _collision_height)
		else:
			fn.call()
		ch.col_job = {}
		_install_collision(ch, job)
		return
	ch.col_job = job
	# The key, not the chunk: chunk -> col_job -> chunk would be a reference cycle.
	job["col_key"] = ch.key
	_col_pending.append(ch)
	_queue_task(job, fn, "terrain collision")


## Collision jobs on workers or queued for one (chunks whose col_job is not empty).
var _col_pending: Array[Chunk] = []
## Chunk and collision jobs not started yet: [job, fn, task name] (see _start_queued).
var _task_queue: Array = []
## Chunk and collision tasks running at once: the pool's threads less two (TD-196/197). A spawn
## or a reload asks for the whole near square at once (169 meshes, 25 bodies: seconds of work),
## and Godot's pool runs high-priority tasks in order, so Jolt's physics jobs (high-priority pool
## tasks too) queued behind them all: with 70-100 chunk and 7-18 collision tasks queued, the
## physics step (between SceneTree.physics_frame and process_frame) took 0.45-2.1 s, after
## Jolt's "exceeded the maximum number of jobs" warning ("Finding your feet…" frames). With a
## short queue there is a thread for Jolt within one task's time; one more is left for the
## low-priority work (POI checks), which Godot already caps to a share of the pool.
var max_tasks: int = maxi(1, OS.get_processor_count() - 2)


## Queues a job; the caller (or the next frame) starts it with _start_queued().
func _queue_task(job: Dictionary, fn: Callable, task_name: String) -> void:
	_task_queue.append([job, fn, task_name])


## Starts queued chunk and collision jobs while fewer than max_tasks run: collision first (the
## ground under someone's feet), then by distance from the streaming centre. Jobs replaced or
## dropped while they waited are discarded.
func _start_queued() -> void:
	if _task_queue.is_empty():
		return
	# Task ids, not jobs: a chunk can be in _col_pending twice (rebuilt while its job ran).
	var running: Dictionary = {}
	for job: Dictionary in _pending.values():
		if job.has("task") and not WorkerThreadPool.is_task_completed(int(job["task"])):
			running[job["task"]] = true
	for ch: Chunk in _col_pending:
		if ch.col_job.has("task") and not WorkerThreadPool.is_task_completed(int(ch.col_job["task"])):
			running[ch.col_job["task"]] = true
	if running.size() >= max_tasks:
		return
	var live: Array = []
	for e: Array in _task_queue:
		var job: Dictionary = e[0]
		if job.has("col_key"):
			var ch: Chunk = _chunks.get(job["col_key"])
			if ch != null and is_same(ch.col_job, job):
				live.append(e)
		elif is_same(_pending.get(job["key"]), job):
			if _chunks.has(job["key"]):
				live.append(e)
			else:
				_pending.erase(job["key"])
	live.sort_custom(func(a: Array, b: Array) -> bool:
		var ca: bool = (a[0] as Dictionary).has("col_key")
		var cb: bool = (b[0] as Dictionary).has("col_key")
		if ca != cb:
			return ca
		return _queue_dist(a[0]) < _queue_dist(b[0]))
	var n: int = mini(max_tasks - running.size(), live.size())
	for i: int in n:
		var e: Array = live[i]
		(e[0] as Dictionary)["task"] = WorkerThreadPool.add_task(e[1], true, e[2])
	_task_queue = live.slice(n)


func _queue_dist(job: Dictionary) -> int:
	var key: Vector2i = job["col_key"] if job.has("col_key") else job["key"]
	return (key - _center).length_squared()


func _collect_collision() -> void:
	var t0: int = Time.get_ticks_usec()
	for i: int in range(_col_pending.size() - 1, -1, -1):
		if float(Time.get_ticks_usec() - t0) / 1000.0 >= COLLECT_BUDGET_MS:
			return
		var ch: Chunk = _col_pending[i]
		var job: Dictionary = ch.col_job
		if job.is_empty():
			_col_pending.remove_at(i)
			continue
		if not job.has("task") or not WorkerThreadPool.is_task_completed(int(job["task"])):
			continue
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
		_col_pending.remove_at(i)
		ch.col_job = {}
		if ch.has_collision and _chunks.get(ch.key) == ch:
			_install_collision(ch, job)


## A finished collision job in a body, replacing the chunk's old one.
func _install_collision(ch: Chunk, job: Dictionary) -> void:
	var origin := Vector2(ch.key.x * CHUNK, ch.key.y * CHUNK)
	var body := StaticBody3D.new()
	body.name = "Col_%d_%d" % [ch.key.x, ch.key.y]
	body.collision_layer = COLLISION_LAYER
	body.collision_mask = 0
	body.set_meta(&"terrain", true)
	body.set_meta(&"damage_receiver", self)
	var cs := CollisionShape3D.new()
	if str(job["kind"]) == "heights":
		var shape := HeightMapShape3D.new()
		var vc: int = int(CHUNK) + 1
		shape.map_width = vc
		shape.map_depth = vc
		shape.map_data = job["out"][0]
		cs.shape = shape
		# HeightMapShape3D is centred on its origin.
		cs.position = Vector3(CHUNK * 0.5, 0.0, CHUNK * 0.5)
	else:
		# A cellar cuts this chunk: exact trimesh (same triangles and cut as the render mesh at
		# 1 m); volume columns are left out instead of sunk.
		var tri := ConcavePolygonShape3D.new()
		tri.backface_collision = true
		tri.set_faces(job["out"][0])
		cs.shape = tri
	body.add_child(cs)
	body.position = Vector3(origin.x, 0.0, origin.y)
	_near_root.add_child(body)
	if ch.body != null:
		ch.body.queue_free()
	ch.body = body


## True once every chunk within `radius` chunks of pos has a mesh, and its collision when it wants
## one (and collision where needed).
func is_ready_around(pos: Vector3, radius: int = 1) -> bool:
	var c: Vector2i = chunk_of(pos.x, pos.z)
	for dz: int in range(-radius, radius + 1):
		for dx: int in range(-radius, radius + 1):
			var ch: Chunk = _chunks.get(Vector2i(c.x + dx, c.y + dz))
			if ch == null or ch.mesh_instance == null or (ch.has_collision and ch.body == null):
				return false
	return true


# --- Far tiles ----------------------------------------------------------------------------------

func _build_far_tiles() -> void:
	for rid: String in world.regions:
		_add_far_tile(rid, TerrainMesher.finish(_far_tile_mesh(rid)))


## The region streamer (ADR-0038) when this world streams; null otherwise.
var streamer: RegionStreamer = null


## Streams regions' 1 m terrain around the focus from now on (streamed random worlds).
func start_streaming(cfg: Dictionary) -> void:
	if streamer != null:
		return
	streamer = RegionStreamer.new()
	streamer.name = "Streamer"
	add_child(streamer)
	streamer.setup(self, cfg)


## Set before setup(): a Bloom field built off the main thread (WorldLoader.bloom_tiles).
var prebuilt_bloom: BloomTiles = null
## Set before setup() to build the far tiles on worker threads through boot_steps() (ADR-0036:
## about 1.5 s of meshing that used to run in the load's one long main-thread frame).
var defer_far_tiles: bool = false
var _far_task: int = -1
var _far_ids: Array = []
var _far_meshes: Array = []


## Boot steps for a deferred setup: the layer textures and each region's material (defer_materials),
## then every far tile meshed in parallel and added (defer_far_tiles).
func boot_steps() -> Array:
	var out: Array = []
	if defer_materials:
		out.append(["Laying the ground…", _make_materials, "terrain textures"])
		var ids: Array = regions.keys()
		ids.sort()
		for rid: String in ids:
			out.append(["Laying the ground…", _make_material_of.bind(rid), "terrain material %s" % rid])
	if defer_far_tiles:
		out.append_array([["Raising the far hills…", _start_far_tiles, "far tiles"], ["Raising the far hills…", _finish_far_tiles, "far tiles (add)"]])
	return out


func _start_far_tiles() -> void:
	_far_ids = world.regions.keys()
	_far_meshes.resize(_far_ids.size())
	# The workers read a snapshot: an attach on the main thread swaps `regions` meanwhile.
	var snap: Dictionary = regions
	_far_task = WorkerThreadPool.add_group_task(func(i: int) -> void: _far_meshes[i] = _far_tile_mesh(_far_ids[i], snap), _far_ids.size(), -1, false, "far tiles")


func _finish_far_tiles() -> bool:
	if _far_task >= 0:
		if not WorkerThreadPool.is_group_task_completed(_far_task):
			return false
		WorkerThreadPool.wait_for_group_task_completion(_far_task)
		_far_task = -1
	for i: int in _far_ids.size():
		_add_far_tile(_far_ids[i], TerrainMesher.finish(_far_meshes[i]))
	_far_meshes.clear()
	return true


## A far tile's mesh, as TerrainMesher.build_chunk_job gives it (pure data: reads the composed regions only, safe on a worker thread given
## `snap`, the `regions` dictionary taken on the main thread; attach and detach replace it).
func _far_tile_mesh(rid: String, snap: Dictionary = regions) -> Variant:
	var built: Array[Rect2] = []
	for b: String in snap:
		built.append(world.region_rect(b))
	var rect: Rect2 = world.region_rect(rid)
	var rt: RegionTerrain = snap.get(rid, coarse.get(rid))
	# Built regions draw their own trees (impostors out to 1.2 km); the others get a canopy,
	# raised into the mesh itself so its normals light the forest edges.
	var grid: PackedVector2Array = _far_canopy_grid(rt, rect, {} if snap.has(rid) else _canopy, built)
	var n: int = int(round(rect.size.x / FAR_STEP)) + 3
	var at := func(x: float, z: float) -> Vector2:
		return grid[clampi(int(round((z - rect.position.y) / FAR_STEP)) + 1, 0, n - 1) * n + clampi(int(round((x - rect.position.x) / FAR_STEP)) + 1, 0, n - 1)]
	var height_fn := func(x: float, z: float) -> float: return height_at(x, z) + (at.call(x, z) as Vector2).x * CANOPY_HEIGHT
	var color_fn := func(x: float, z: float) -> Color: return _far_color(rt, x, z, at.call(x, z))
	return TerrainMesher.build_chunk_job(rect.position, rect.size.x, FAR_STEP, height_fn, 12.0, color_fn)


## Region id -> {task, out}: far tiles being meshed again because the region attached (its trees
## are drawn by the vegetation from then on: no canopy) or detached (the canopy comes back).
var _far_jobs: Dictionary = {}
## Set by GameWorld. Off for bare managers (tests): a worker inside one of this node's methods
## makes free() refuse it, and a test frees with free() before _exit_tree can join the job.
var remesh_far_tiles: bool = false


func _remesh_far_tile(rid: String) -> void:
	if not remesh_far_tiles or _far_root == null or _far_task >= 0 or not is_inside_tree():
		return
	var old: Dictionary = _far_jobs.get(rid, {})
	if not old.is_empty():
		# Superseded: join it (it reads only snapshots) and start again with the current state.
		WorkerThreadPool.wait_for_task_completion(int(old["task"]))
	var snap: Dictionary = regions
	var out: Array = [null]
	_far_jobs[rid] = {"out": out, "task": WorkerThreadPool.add_task(func() -> void: out[0] = _far_tile_mesh(rid, snap), false, "far tile %s" % rid)}


func _collect_far_jobs() -> void:
	for rid: String in _far_jobs.keys():
		var job: Dictionary = _far_jobs[rid]
		if not WorkerThreadPool.is_task_completed(int(job["task"])):
			continue
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
		_far_jobs.erase(rid)
		var mi: MeshInstance3D = _far_root.get_node_or_null(NodePath("Far_" + rid)) as MeshInstance3D
		if mi != null:
			mi.mesh = TerrainMesher.finish((job["out"] as Array)[0])


func _add_far_tile(rid: String, mesh: ArrayMesh) -> void:
	_make_materials()
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

## Region id -> the cellars of every building placed in it (TerrainHoles.from_regions, made once
## per attach: compiling the layouts is the costly part).
var _region_holes: Dictionary = {}
## Set by a PoiManager that builds by distance (ADR-0038 §8): only the cellars of buildings in
## `_hole_gate` (instance id -> true) are cut, the others wait for their building.
var gate_holes: bool = false
var _hole_gate: Dictionary = {}


## Opens (a building now stands there) or closes (it was freed) one POI's cellar: the holes are
## published anew and the near chunks over it re-meshed and re-collided.
func set_poi_hole(id: StringName, open: bool) -> void:
	if open == _hole_gate.has(id):
		return
	if open:
		_hole_gate[id] = true
	else:
		_hole_gate.erase(id)
	if not gate_holes:
		return
	var where := Rect2()
	for th: TerrainHoles in _region_holes.values():
		var b: Rect2 = th.bounds_of(id)
		if b.size != Vector2.ZERO:
			where = b if where.size == Vector2.ZERO else where.merge(b)
	if where.size == Vector2.ZERO:
		return
	_publish_holes()
	_refresh_chunks(where)


## Starts gating cellars by built buildings (see gate_holes); the ones open so far stay open.
func start_gating_holes() -> void:
	if gate_holes:
		return
	gate_holes = true
	_publish_holes()
	for th: TerrainHoles in _region_holes.values():
		if not (th as TerrainHoles).is_empty():
			_refresh_chunks(th.bounds)


## Publishes `holes` from the regions' cellars, by region id order (from_regions' order), as a new
## object: workers and queued jobs keep the old one.
func _publish_holes() -> void:
	var ids: Array = _region_holes.keys()
	ids.sort()
	var parts: Array = []
	for rid: Variant in ids:
		parts.append(_region_holes[rid])
	holes = TerrainHoles.combined(parts, _hole_gate if gate_holes else null)

## Cellar footprints (world-XZ convex pieces) that cut a near chunk.
func _cutters(key: Vector2i) -> Array[PackedVector2Array]:
	if holes == null or holes.is_empty():
		return []
	return holes.pieces_in(Rect2(key.x * CHUNK, key.y * CHUNK, CHUNK, CHUNK))


## Whether (x, z) lies over a POI cellar, where the heightmap has been cut away.
func in_cellar(x: float, z: float) -> bool:
	return holes != null and holes.contains(x, z)


## The ground under a point: the cellar floor when the point is down in a cut-out POI cellar
## (anywhere under the ground floor's slab, fallen through the cellar floor included), the floor of
## a buried mine level or cave when it is down in one (ADR-0044), else the
## terrain height. height_at() keeps reporting the heightfield (ADR-0007); fell-through-the-world
## checks and settling things where they are want this.
func ground_below(pos: Vector3) -> float:
	var h: float = height_at(pos.x, pos.z)
	if holes == null:
		return h
	# Down on a buried mine level or in a cave under the ground (ADR-0044).
	if holes.has_buried():
		var bf: float = holes.buried_floor(pos.x, pos.z, pos.y)
		if not is_nan(bf) and pos.y < h - 1.0:
			return bf
	if holes.is_empty():
		return h
	var hole: TerrainHoles.Hole = holes.hole_at(pos.x, pos.z)
	return hole.floor_y if hole != null and pos.y < hole.ceiling_y else h


func _on_volume_column(col: Vector2i) -> void:
	var key: Vector2i = chunk_of(col.x * VolumeTerrain.SIZE + 1.0, col.y * VolumeTerrain.SIZE + 1.0)
	var ch: Chunk = _chunks.get(key)
	if ch != null:
		_request_mesh(key, maxi(ch.lod, 0), true)
		if ch.has_collision:
			_rebuild_collision(ch, true)


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
	# Written in place under _lock: worker threads read these heights all the time through
	# height_at (chunk meshing, scatter, weather, the Hum's flow field), which takes the lock too.
	# Neither alternative is safe without it: replacing the array releases the old one and leaves
	# the member null for a moment, and writing a packed array that a reader's temporary also
	# references copies it on write, swapping the buffer under that reader (TD-104).
	var original := PackedFloat32Array()
	if mode == "smooth":
		original = hf.heights.duplicate()
	_lock.lock()
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
			var h0: float = hf.heights[idx]
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
			hf.heights[idx] = nh
			moved += (h0 - nh) * hf.spacing * hf.spacing
			touched[chunk_of(x, z)] = true
			# Samples on chunk borders belong to neighbours too.
			touched[chunk_of(x - 0.01, z - 0.01)] = true
	_lock.unlock()
	for key: Vector2i in touched:
		_record_delta(rt, key)
		var ch: Chunk = _chunks.get(key)
		if ch != null:
			_request_mesh(key, ch.lod if ch.lod >= 0 else 0, true)
			if ch.has_collision:
				_rebuild_collision(ch, true)
	var aabb := AABB(center - Vector3(radius, MAX_DIG_DEPTH, radius), Vector3(radius, MAX_DIG_DEPTH, radius) * 2.0)
	terrain_changed.emit(aabb)
	Events.terrain_modified.emit(aabb)
	return moved


## Applies the saved digs that fall in a region onto its heights (in place, see modify()). The
## pristine heights come from _base_cache when the region was dug before (kept across a detach),
## so a re-attached object that still carries its digs gets them once, not twice.
func _apply_deltas(rt: RegionTerrain) -> void:
	var vc: int = int(CHUNK) + 1
	var hf: HeightField = rt.height
	var base: HeightField = null
	_lock.lock()
	for key_s: String in _deltas:
		var key: Vector2i = Ids.parse_chunk_key(key_s.substr(2))
		if not rt.rect.has_point(Vector2(key.x * CHUNK + 1.0, key.y * CHUNK + 1.0)):
			continue
		if base == null:
			base = _base_heights(rt)
		var delta: PackedFloat32Array = _deltas[key_s]
		for j: int in vc:
			for i: int in vc:
				var gx: int = int(round((key.x * CHUNK + i - hf.origin.x) / hf.spacing))
				var gz: int = int(round((key.y * CHUNK + j - hf.origin.y) / hf.spacing))
				if gx >= 0 and gz >= 0 and gx < hf.width and gz < hf.depth:
					hf.heights[gz * hf.width + gx] = base.heights[gz * hf.width + gx] + delta[j * vc + i]
	_lock.unlock()


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
	# Every saved dig is decoded (ADR-0038: a region that attaches later still gets its own), then
	# applied to the regions present now; attach_region applies the rest.
	for k: Variant in ws.chunk_blobs.keys():
		var key_s: String = str(k)
		if not key_s.begins_with("t:"):
			continue
		var raw: PackedByteArray = (ws.chunk_blobs[k] as PackedByteArray).decompress(vc * vc * 4, FileAccess.COMPRESSION_ZSTD)
		_deltas[key_s] = raw.to_float32_array()
	for rid: String in regions:
		_apply_deltas(regions[rid])
	if volume != null:
		volume.load_from(ws)
