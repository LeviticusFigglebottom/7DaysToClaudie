class_name VegetationManager
extends Node3D
## Renders and simulates vegetation from VegetationScatter (deterministic per chunk).
##  * near chunks (±NEAR_CHUNKS): MultiMesh per species/variant/LOD with visibility-range fades
##  * ground cover (±GROUND_CHUNKS): ferns, grass, flowers, moss, litter in 32 m blocks; each plant
##    shrinks away near the grass distance in the shader. The Bloom's fruiting bodies (the scatter's
##    bloom layer, ADR-0025) are drawn the same way.
##  * far layer: per-region camera-facing impostor MultiMeshes discarding inside the near square
##  * collision: pooled bodies for trees/boulders within COLLISION_RADIUS of the player
##  * chopping (take_damage with tool_power.chop) -> FallingTree -> logs + stump
##  * harvesting (pebbles, deadfall, plants) via HarvestTarget proxies for the interaction ray
## Changes are stored in WorldState.trees[chunk][index] = {state, day} (felled/harvested).

const CHUNK: float = 64.0
const NEAR_CHUNKS: int = 3
const GROUND_CHUNKS: int = 1
const COLLISION_RADIUS: float = 45.0
const LOD_END: PackedFloat32Array = [55.0, 140.0, 330.0]
## Boulders with a "_lod1" model switch to it for chunks whose centre is farther than this (the
## nearest decimated boulder is then >= ~45 m away).
const ROCK_LOD_SPLIT: float = 90.0
const GROUND_END: float = 52.0
## Ground cover is batched in 32 m blocks (4 per chunk) so a block's visibility range follows the
## camera closely; each plant then shrinks away on its own in the shader (custom data).
const GROUND_BLOCK: float = 32.0
## Ground kinds thinned by the grass density setting (ferns and moss carry the look and stay).
const THINNED_KINDS: PackedStringArray = ["grass", "litter", "flower", "herb"]
## Ground blocks whose centre is farther than this draw a species' cheaper "_lod1" model when it
## has one (ferns): the nearest such plant is then >= ~17 m away.
const GROUND_LOD_SPLIT: float = 40.0
## Twig litter is invisible beyond a few tens of metres: it shrinks away sooner.
const LITTER_END: float = 30.0
## The Bloom's pale caps read further than litter against the dark floor, but are small.
const FUNGUS_END: float = 36.0
const FADE: float = 8.0
const MAX_JOBS: int = 3

static var _ring: Array[Vector2i] = []


## Chunk offsets within NEAR_CHUNKS sorted by distance from the centre chunk.
static func _ring_order() -> Array[Vector2i]:
	if _ring.is_empty():
		for dz: int in range(-NEAR_CHUNKS, NEAR_CHUNKS + 1):
			for dx: int in range(-NEAR_CHUNKS, NEAR_CHUNKS + 1):
				_ring.append(Vector2i(dx, dz))
		_ring.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.length_squared() < b.length_squared())
	return _ring

var world: Node
var terrain: TerrainManager
var _data: Dictionary = {}
var _pending: Dictionary = {}
var _nodes: Dictionary = {}
var _center := Vector2i(999999, 999999)
var _bodies: Dictionary = {}
var _tree_hp: Dictionary = {}
var _removed: Dictionary = {}
var _far_root: Node3D
var _far_mats: Array[ShaderMaterial] = []
var _accum: float = 0.0
var _col_accum: float = 0.0
var _last_harvest: HarvestTarget = null
## Chunk key -> its harvestable small plants and stones (the only instances the interaction ray
## can pick), filtered once when the chunk's scatter arrives, binned by PICK_CELL m cell
## ({Vector2i cell: Array}): the ray, under 3 m long, asked every one of the nine chunks' thousands
## each physics tick (8-38 ms a frame after the spawn, TD-324).
var _pickable: Dictionary = {}
const PICK_CELL: float = 4.0
## Far layer: one group task over every 64 m chunk of every detailed region (one element each).
## The far impostor layer per region (ADR-0038: regions attach and detach in a streamed world):
## rid -> {task (-1 once built), jobs: [[rid, chunk key]], chunks: [result per job], holder: Node3D,
## mats: [ShaderMaterial], dropped: bool}.
var _far: Dictionary = {}
## The buildings on town lots (organic towns, ADR-0040, and frameworks), as yards see them: chunk key -> [[world to
## building-local Transform2D, local box Rect2, front edge y (the street side)], ...]. Built once in
## setup_world from the PoiRegistry and never replaced (the far layer's workers read it). A yard
## grows grass, brush and a few trees (the `yard` biome) right up to its house: what stands in a
## building's box, or a tree or bush on the walk in front of it, is hidden by index like a clearing,
## so the scatter and the saved trees keep their indices (player report 4).
var _footprints: Dictionary = {}
## How far round a building's box each layer keeps off (m), and how much further on its street side
## (the front yard and the verge out to the street, as wide as the house: the walk to its door stays
## clear of trees, brush and boulders).
const FOOTPRINT_MARGIN: Dictionary = {"tree": 1.6, "medium": 0.8, "ground": 0.25, "bloom": 0.25}
const FOOTPRINT_FRONT: Dictionary = {"tree": 12.0, "medium": 12.0, "ground": 0.0, "bloom": 0.0}
## How far past a cave's air box (caves_changed) its mouth apron can reach (m): the chunks to re-mask.
const CAVE_APRON_REACH: float = 16.0
## Coarse far forest (TD-006, HLOD): the regions held only at 16 m (never built on the main map,
## beyond the attach rings in a streamed world) get cluster impostors, one quad standing for a few
## trees, so the forest runs on to the view distance. rid -> {task (-1 once built), rect, blocks:
## [per-block {species: [count, buffer]}], holder, redo}. Built near the player, freed far off.
var _coarse: Dictionary = {}
var _coarse_mats: Dictionary = {}
var _coarse_accum: float = 0.0
## Off hides every coarse cluster (perf_capture's with/without measure of the ridge view).
var coarse_enabled: bool = true:
	set(v):
		coarse_enabled = v
		for rid: String in _coarse.keys():
			_coarse_show(rid)
		if world != null and world.player != null:
			var pp: Vector3 = world.player.global_position
			_coarse_ring(Vector2(pp.x, pp.z), float(Settings.gfx("view_distance", 1400.0)))
## Trees per cluster quad (the quads are COARSE_SPREAD wider and COARSE_LIFT taller, so the crowns
## still meet at a distance), the block a MultiMesh covers (visibility range culls by block), how
## many region scatters run at once, and how far past the view distance a built one is kept.
const COARSE_TREES: float = 4.0
const COARSE_SPREAD: float = 1.55
const COARSE_LIFT: float = 1.12
const COARSE_BLOCK: float = 512.0
const COARSE_JOBS: int = 2
const COARSE_FREE_PAST: float = 1200.0
const COARSE_MAX_SLOPE: float = 34.0
const COARSE_MINOR: float = 0.15
const COARSE_PER_CELL: int = 4
## Clusters grow in from this far round the player (an unbuilt region has no near trees, so it
## keeps no near square; closer than this a billboard cluster reads as one).
const COARSE_INNER: float = 90.0
## Clearing ids `set_clearings` opened, by source (Bloom nests' mats, ADR-0055): a thin layer over
## the runtime clearings below, so nests and forest encounters share one mask.
var _source_clearings: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	terrain = w.terrain
	_removed = Game.session.world.trees
	_build_footprints(w.get(&"poi_registry") as PoiRegistry)
	_far_root = Node3D.new()
	_far_root.name = "FarTrees"
	add_child(_far_root)
	_build_far_layer()
	terrain.region_attached.connect(_far_attach)
	terrain.region_detached.connect(_far_detach)
	# Cave mouths keep their apron clear (ADR-0056 WS-E): a cave placed or removed re-masks the
	# chunks around it, near and far.
	if terrain.has_signal(&"caves_changed"):
		terrain.caves_changed.connect(_on_caves_changed)
	# The fungal mounds Hum survivors leave where they root at dawn (ADR-0025).
	var mounds := BloomMounds.new()
	mounds.name = "BloomMounds"
	add_child(mounds)
	mounds.setup_world(w)


# --- Queries ----------------------------------------------------------------------------------

func _rt_for_chunk(key: Vector2i) -> RegionTerrain:
	return terrain.region_terrain_at((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)


func _is_removed(key: Vector2i, index: int) -> bool:
	if _cleared.has(key) and (_cleared[key] as Dictionary).has(index):
		return true
	var ck: String = Ids.chunk_key(key.x, key.y)
	var st: Dictionary = (_removed.get(ck, {}) as Dictionary).get(str(index), {})
	if st.is_empty():
		return false
	var sp_regrow: float = float(st.get("regrow", 0.0))
	if sp_regrow > 0.0 and Game.session.clock.day() - int(st.get("day", 0)) >= sp_regrow:
		(_removed[ck] as Dictionary).erase(str(index))
		return false
	return true


# --- Runtime clearings (ADR-0054) -------------------------------------------------------------

## Clearings other systems open in the forest at runtime (a forest encounter's campsite): id ->
## [centre: Vector2, tree radius, undergrowth radius]. Their instances count as removed (hidden,
## no collision, not harvestable) without touching the scatter's indices or the saved trees.
var _clearings: Dictionary = {}
## Chunk -> clearing ids over it; chunk -> {instance index: true} hidden by them.
var _clearings_by_chunk: Dictionary = {}
var _cleared: Dictionary = {}


## Opens (or moves) clearing `id`: trees within `r_trees` m of `at` and everything smaller within
## `r_brush` m. Chunks already built are rebuilt.
func add_clearing(id: StringName, at: Vector2, r_trees: float, r_brush: float) -> void:
	remove_clearing(id)
	var r: float = maxf(r_trees, r_brush)
	if r <= 0.0:
		return
	_clearings[id] = [at, r_trees, r_brush]
	for key: Vector2i in _chunks_over(at, r):
		if not _clearings_by_chunk.has(key):
			_clearings_by_chunk[key] = []
		(_clearings_by_chunk[key] as Array).append(id)
		_recompute_cleared(key)


func remove_clearing(id: StringName) -> void:
	if not _clearings.has(id):
		return
	var c: Array = _clearings[id]
	_clearings.erase(id)
	for key: Vector2i in _chunks_over(c[0], maxf(float(c[1]), float(c[2]))):
		var ids: Array = _clearings_by_chunk.get(key, [])
		ids.erase(id)
		if ids.is_empty():
			_clearings_by_chunk.erase(key)
		_recompute_cleared(key)


func clearing_count() -> int:
	return _clearings.size()


static func _chunks_over(at: Vector2, r: float) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for cz: int in range(floori((at.y - r) / CHUNK), floori((at.y + r) / CHUNK) + 1):
		for cx: int in range(floori((at.x - r) / CHUNK), floori((at.x + r) / CHUNK) + 1):
			out.append(Vector2i(cx, cz))
	return out


## The instances of chunk `key` its clearings hide (once its scatter is in), and a rebuild of the
## chunk when that changed what it shows.
func _recompute_cleared(key: Vector2i) -> void:
	var had: Dictionary = _cleared.get(key, {})
	var now: Dictionary = {}
	var layers: Dictionary = _data.get(key, {})
	for layer0: String in layers:
		for inst0: VegetationScatter.Instance in layers[layer0]:
			if _in_footprint(_footprints.get(key, []), layer0, inst0.pos.x, inst0.pos.z):
				now[inst0.index] = true
	# Cave mouths' aprons (CaveSet.keep_out): every layer, by index like a clearing.
	var caves: Object = _caves_over(key)
	if caves != null:
		for layer1: String in layers:
			for inst1: VegetationScatter.Instance in layers[layer1]:
				if bool(caves.call(&"keep_out", inst1.pos.x, inst1.pos.z)):
					now[inst1.index] = true
	for cid: StringName in _clearings_by_chunk.get(key, []):
		var c: Array = _clearings[cid]
		var at: Vector2 = c[0]
		for layer: String in layers:
			var r: float = float(c[1]) if layer == "tree" else float(c[2])
			if r <= 0.0:
				continue
			for inst: VegetationScatter.Instance in layers[layer]:
				if Vector2(inst.pos.x - at.x, inst.pos.z - at.y).length_squared() <= r * r:
					now[inst.index] = true
	if now.is_empty():
		_cleared.erase(key)
	else:
		_cleared[key] = now
	if now.hash() != had.hash() and _nodes.has(key):
		_rebuild(key)


## The terrain's cave set when a cave's footprint reaches chunk `key`, else null. The set is
## immutable once published (TerrainManager replaces it whole), so workers may hold it too.
func _caves_over(key: Vector2i) -> Object:
	var caves: Object = terrain.get(&"caves") if terrain != null else null
	if caves == null or not caves.has_method(&"any_in_rect") or bool(caves.call(&"is_empty")):
		return null
	return caves if bool(caves.call(&"any_in_rect", Rect2(key.x * CHUNK, key.y * CHUNK, CHUNK, CHUNK))) else null


## A cave was placed or removed over `box` (its air): the chunks around it (grown to take in the
## mouth's apron) re-mask, and the far trees of the regions it touches scatter again.
func _on_caves_changed(box: AABB) -> void:
	var r := Rect2(box.position.x, box.position.z, box.size.x, box.size.z).grow(CAVE_APRON_REACH)
	for key: Vector2i in _data.keys():
		if r.intersects(Rect2(key.x * CHUNK, key.y * CHUNK, CHUNK, CHUNK)):
			_recompute_cleared(key)
	for rid: String in _far.keys():
		var rt: RegionTerrain = terrain.regions.get(rid)
		if rt != null and rt.rect.intersects(r):
			_far_redo(rid)
	for rid: String in _coarse.keys():
		var e: Dictionary = _coarse[rid]
		if (e["rect"] as Rect2).intersects(r):
			if int(e["task"]) >= 0:
				e["redo"] = true
			else:
				_coarse_free(rid)


func _water_fn() -> Callable:
	var wsys: Node = world.water
	if wsys == null:
		return Callable()
	return func(x: float, z: float) -> float: return wsys.water_level_at(x, z)


func _scatter(key: Vector2i) -> Dictionary:
	var rt: RegionTerrain = _rt_for_chunk(key)
	if rt == null:
		return {}
	return VegetationScatter.scatter_chunk(key, rt, Game.session.world_seed, terrain.height_at, _water_fn(),
		VegetationScatter.ORDER.size(), terrain.bloom_base_at)


## Joins in-flight scatter jobs (they read content and terrain) before the world is freed.
func _exit_tree() -> void:
	for key: Vector2i in _pending.keys():
		WorkerThreadPool.wait_for_task_completion(_pending[key]["task"])
	_pending.clear()
	for e: Dictionary in _far.values():
		if int(e["task"]) >= 0:
			WorkerThreadPool.wait_for_group_task_completion(int(e["task"]))
			e["task"] = -1
	for e: Dictionary in _coarse.values():
		if int(e["task"]) >= 0:
			WorkerThreadPool.wait_for_group_task_completion(int(e["task"]))
			e["task"] = -1


# --- Streaming --------------------------------------------------------------------------------

func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_process_body(delta)
	StreamMeter.note("veg", t0)


func _process_body(delta: float) -> void:
	_collect_far()
	_collect_coarse()
	if world == null or world.player == null:
		return
	_collect()
	_accum += delta
	_col_accum += delta
	_coarse_accum += delta
	var pos: Vector3 = world.player.global_position
	if _coarse_accum > 1.0:
		_coarse_accum = 0.0
		_coarse_update(pos)
	if _accum > 0.25:
		_accum = 0.0
		_update(pos)
	if _col_accum > 0.5:
		_col_accum = 0.0
		_update_collision(pos)


func _update(pos: Vector3) -> void:
	var c: Vector2i = TerrainManager.chunk_of(pos.x, pos.z)
	if c != _center:
		_center = c
		for m: ShaderMaterial in _far_mats:
			m.set_shader_parameter("discard_rect", _near_rect())
		for key: Vector2i in _nodes.keys():
			if absi(key.x - c.x) > NEAR_CHUNKS or absi(key.y - c.y) > NEAR_CHUNKS:
				_free_nodes(key)
	# Nearest chunks first; a few scatter jobs at a time so the ground under you fills in first.
	# One build a call (a chunk's trees and rocks, or its ground cover: 10-25 ms each), and the next
	# frame calls again while any is left (TD-324: after the spawn every chunk whose scatter had
	# arrived was built in one frame, with its ground).
	var built: bool = false
	for off: Vector2i in _ring_order():
		var key := Vector2i(c.x + off.x, c.y + off.y)
		var want_ground: bool = absi(off.x) <= GROUND_CHUNKS and absi(off.y) <= GROUND_CHUNKS
		if not _data.has(key):
			if not _pending.has(key) and _pending.size() < MAX_JOBS and _rt_for_chunk(key) != null:
				# The worker fills its own slot: `job` gains "task" on this thread after the task has
				# started, and a dictionary written from two threads at once can corrupt itself.
				var out: Array = [{}]
				var job: Dictionary = {"key": key, "out": out}
				job["task"] = WorkerThreadPool.add_task(func() -> void: out[0] = _scatter(key), false, "veg scatter")
				_pending[key] = job
			continue
		var n: Dictionary = _nodes.get(key, {})
		if built:
			if n.is_empty() or bool(n.get("ground", false)) != want_ground:
				_accum = 1.0
			continue
		if n.is_empty():
			_build_chunk(key, false)
			built = true
			if want_ground:
				_accum = 1.0
		elif bool(n.get("ground", false)) != want_ground:
			_set_ground(key, want_ground)
			built = true


## True once every chunk within NEAR_CHUNKS of the player has its instances built and no scatter
## job is in flight (visual QA and tests wait on this instead of a fixed delay).
## `radius` (chunks) narrows the check to the inner rings; the far impostor layer covers the rest.
func is_settled(radius: int = NEAR_CHUNKS) -> bool:
	return settle_report(radius) == ""


## Why streaming is not settled yet ("" when it is): for QA logs.
func settle_report(radius: int = NEAR_CHUNKS) -> String:
	if world == null or world.player == null:
		return "no player"
	for e: Dictionary in _far.values():
		if int(e["task"]) != -1:
			return "far layer scattering"
	if not _pending.is_empty():
		return "%d scatter jobs pending" % _pending.size()
	var p: Vector3 = world.player.global_position
	if TerrainManager.chunk_of(p.x, p.z) != _center:
		return "recentring"
	var missing: Array[Vector2i] = []
	for off: Vector2i in _ring_order():
		if absi(off.x) > radius or absi(off.y) > radius:
			continue
		var key := Vector2i(_center.x + off.x, _center.y + off.y)
		if not _nodes.has(key) and _rt_for_chunk(key) != null:
			missing.append(key)
	return "" if missing.is_empty() else "chunks not built: %s (data: %s)" % [missing, missing.map(func(k: Vector2i) -> bool: return _data.has(k))]


func _collect() -> void:
	for key: Vector2i in _pending.keys():
		var job: Dictionary = _pending[key]
		if WorkerThreadPool.is_task_completed(job["task"]):
			WorkerThreadPool.wait_for_task_completion(job["task"])
			_pending.erase(key)
			_data[key] = job["out"][0]
			_pickable[key] = _bin_pickables(_harvestables(job["out"][0]))
			if _clearings_by_chunk.has(key) or _footprints.has(key) or _caves_over(key) != null:
				_recompute_cleared(key)


## Sets one source's clearings ([{pos: Vector2, r}]), replacing the ones it set before; each is a
## runtime clearing (trees and undergrowth within r) like a forest encounter's.
func set_clearings(source: StringName, list: Array) -> void:
	for id: StringName in _source_clearings.get(source, []):
		remove_clearing(id)
	var ids: Array[StringName] = []
	for i: int in list.size():
		var c: Dictionary = list[i]
		var id := StringName("%s:%d" % [source, i])
		add_clearing(id, c["pos"], float(c["r"]), float(c["r"]))
		ids.append(id)
	if ids.is_empty():
		_source_clearings.erase(source)
	else:
		_source_clearings[source] = ids


## `list` (instances) by PICK_CELL m cell of their position.
static func _bin_pickables(list: Array) -> Dictionary:
	var out: Dictionary = {}
	for inst: VegetationScatter.Instance in list:
		var c := Vector2i(floori(inst.pos.x / PICK_CELL), floori(inst.pos.z / PICK_CELL))
		if not out.has(c):
			out[c] = []
		(out[c] as Array).append(inst)
	return out


## Small plants and stones with yields, filtered once per chunk instead of on every physics
## frame (the ground layer holds thousands of grass tufts the ray can never pick).
func _harvestables(layers: Dictionary) -> Array:
	var out: Array = []
	var ok: Dictionary = {}
	for layer: String in ["medium", "ground"]:
		for inst: VegetationScatter.Instance in layers.get(layer, []):
			if not ok.has(inst.species):
				var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
				ok[inst.species] = sp != null and not sp.yields.is_empty() and sp.veg_kind != "tree" and sp.hp <= 40.0
			if ok[inst.species]:
				out.append(inst)
	return out


func _build_chunk(key: Vector2i, ground: bool) -> void:
	var holder := Node3D.new()
	holder.name = "V_%d_%d" % [key.x, key.y]
	add_child(holder)
	var entry: Dictionary = {"holder": holder, "ground": false, "ground_nodes": []}
	_nodes[key] = entry
	var layers: Dictionary = _data[key]
	for layer: String in ["tree", "medium"]:
		var groups: Dictionary = _group(key, layers.get(layer, []))
		for gk: String in groups:
			var parts: PackedStringArray = gk.split("|")
			var sp: SpeciesDef = Content.get_def(&"species", StringName(parts[0])) as SpeciesDef
			var variant: int = int(parts[1])
			var insts: Array = groups[gk]
			if sp.veg_kind == "tree":
				for lod: int in 3:
					if _lod_end(lod) <= 0.0:
						continue
					holder.add_child(_mmi(_lod_mesh(sp, variant, lod), insts, 0.0 if lod == 0 else _lod_end(lod - 1), _lod_end(lod), true))
				continue
			var end: float = minf(float(sp.lod_distances[1]) * 2.0, 220.0)
			# Boulders cast shadows (they sit in the light like the trees); loose pebbles don't.
			var shadows: bool = sp.veg_kind != "rock" or sp.collides
			if sp.veg_kind == "rock" and end > ROCK_LOD_SPLIT and ModelLibrary.has_model(sp.models[variant % sp.models.size()] + "_lod1"):
				holder.add_child(_mmi(_lod_mesh(sp, variant, 0), insts, 0.0, ROCK_LOD_SPLIT, shadows))
				holder.add_child(_mmi(_lod_mesh(sp, variant, 1), insts, ROCK_LOD_SPLIT, end, shadows))
			else:
				holder.add_child(_mmi(_lod_mesh(sp, variant, 0), insts, 0.0, end, shadows))
	if ground:
		_set_ground(key, true)


func _set_ground(key: Vector2i, on: bool) -> void:
	var entry: Dictionary = _nodes[key]
	for n: Node in entry["ground_nodes"]:
		n.queue_free()
	entry["ground_nodes"] = []
	entry["ground"] = on
	if not on:
		return
	var holder: Node3D = entry["holder"]
	var density: float = float(Settings.gfx("grass_density", 0.8))
	var fade_end: float = minf(GROUND_END, float(Settings.gfx("grass_distance", 60.0)))
	var origin := Vector2(key.x * CHUNK, key.y * CHUNK)
	var groups: Dictionary = {}
	var layers: Dictionary = _data[key]
	for inst: VegetationScatter.Instance in (layers.get("ground", []) as Array) + (layers.get("bloom", []) as Array):
		if _is_removed(key, inst.index):
			continue
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		# Thin by a hash of the index, not by list order (that kept only the chunk's first rows).
		if density < 1.0 and THINNED_KINDS.has(sp.veg_kind) and float(((inst.index * 2654435761) >> 16) & 0xFFFF) / 65536.0 >= density:
			continue
		var bx: int = clampi(int((inst.pos.x - origin.x) / GROUND_BLOCK), 0, 1)
		var bz: int = clampi(int((inst.pos.z - origin.y) / GROUND_BLOCK), 0, 1)
		var gk: String = "%s|%d|%d" % [inst.species, inst.variant, bx + bz * 2]
		if not groups.has(gk):
			groups[gk] = []
		(groups[gk] as Array).append(inst)
	for gk: String in groups:
		var parts: PackedStringArray = gk.split("|")
		var sp: SpeciesDef = Content.get_def(&"species", StringName(parts[0])) as SpeciesDef
		var variant: int = int(parts[1])
		var shrink: float = fade_end
		if sp.veg_kind == "litter":
			shrink = minf(fade_end, LITTER_END)
		elif sp.veg_kind == "fungus":
			shrink = minf(fade_end, FUNGUS_END)
		# Drawn while any plant of the block can be inside the fade distance (half a block diagonal).
		var end: float = shrink + GROUND_BLOCK * 0.71
		var mmis: Array[MultiMeshInstance3D] = []
		if end > GROUND_LOD_SPLIT and ModelLibrary.has_model(sp.models[variant % sp.models.size()] + "_lod1"):
			var near: MultiMeshInstance3D = _mmi(_lod_mesh(sp, variant, 0), groups[gk], 0.0, GROUND_LOD_SPLIT, false, shrink)
			var far: MultiMeshInstance3D = _mmi(_lod_mesh(sp, variant, 1), groups[gk], GROUND_LOD_SPLIT, end, false, shrink)
			# A dithered cross-fade between the two block LODs; the far end is the per-plant shrink.
			near.visibility_range_end_margin = 6.0
			near.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			far.visibility_range_begin_margin = 6.0
			far.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			mmis = [near, far]
		else:
			mmis = [_mmi(_lod_mesh(sp, variant, 0), groups[gk], 0.0, end, false, shrink)]
		for mmi: MultiMeshInstance3D in mmis:
			holder.add_child(mmi)
			(entry["ground_nodes"] as Array).append(mmi)


func _group(key: Vector2i, insts: Array) -> Dictionary:
	var groups: Dictionary = {}
	for inst: VegetationScatter.Instance in insts:
		if _is_removed(key, inst.index):
			continue
		var gk: String = "%s|%d" % [inst.species, inst.variant]
		if not groups.has(gk):
			groups[gk] = []
		(groups[gk] as Array).append(inst)
	return groups


## shrink_at > 0: ground cover; every instance shrinks away between 80 % and 100 % of that
## distance in the shader (negative custom alpha), and the whole MultiMesh is cut at `end`
## without a dither fade.
func _mmi(mesh: Mesh, insts: Array, begin: float, end: float, shadows: bool, shrink_at: float = 0.0) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = shrink_at > 0.0
	mm.mesh = mesh
	mm.instance_count = insts.size()
	for i: int in insts.size():
		mm.set_instance_transform(i, _xform(insts[i]))
		if shrink_at > 0.0:
			mm.set_instance_custom_data(i, Color(0.0, 0.0, 0.0, -shrink_at))
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.visibility_range_begin = begin
	mmi.visibility_range_begin_margin = FADE if begin > 0.0 else 0.0
	mmi.visibility_range_end = end
	mmi.visibility_range_end_margin = FADE if shrink_at <= 0.0 else 0.0
	mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF if shrink_at <= 0.0 else GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mmi


static func _xform(inst: VegetationScatter.Instance) -> Transform3D:
	var b := Basis.from_euler(Vector3(inst.tilt.x, inst.yaw, inst.tilt.y)).scaled(Vector3.ONE * inst.scale)
	return Transform3D(b, inst.pos)


## Where tree LOD `lod` ends. The graphics setting tree_lod_scale (ADR-0037) moves the full-detail
## and middle LODs nearer or further; the last LOD keeps its end, since the far impostors start at
## the near ring's edge. LODs switch per 64 m chunk (TD-035), so the chunk around the player is
## full detail whenever LOD0 reaches its centre: ~340 firs of ~10k triangles. Below 0.5 there is
## no full detail at all (LOD1 from 0 m): the low preset's saving (TD-003).
func _lod_end(lod: int) -> float:
	if lod >= LOD_END.size() - 1:
		return LOD_END[LOD_END.size() - 1]
	var scale: float = clampf(float(Settings.gfx("tree_lod_scale", 1.0)), 0.3, 2.0)
	if lod == 0 and scale < 0.5:
		return 0.0
	return minf(LOD_END[lod] * scale, LOD_END[LOD_END.size() - 1] - 20.0 * float(LOD_END.size() - 1 - lod))


func _lod_mesh(sp: SpeciesDef, variant: int, lod: int) -> Mesh:
	var base: String = sp.models[variant % sp.models.size()]
	var id: String = base if lod == 0 else "%s_lod%d" % [base, lod]
	if lod > 0 and not ModelLibrary.has_model(id):
		id = base
	var ph: String = "plant"
	match sp.veg_kind:
		"tree":
			ph = "deciduous" if String(sp.id).contains("birch") else "conifer"
		"rock":
			ph = "rock"
	return ModelLibrary.mesh(id, ph)


func _free_nodes(key: Vector2i) -> void:
	var entry: Dictionary = _nodes.get(key, {})
	if not entry.is_empty():
		(entry["holder"] as Node).queue_free()
	_nodes.erase(key)
	_data.erase(key)
	_pickable.erase(key)
	_cleared.erase(key)


func _rebuild(key: Vector2i) -> void:
	if not _nodes.has(key):
		return
	var ground: bool = bool(_nodes[key]["ground"])
	(_nodes[key]["holder"] as Node).queue_free()
	_nodes.erase(key)
	_build_chunk(key, ground)


# --- Far impostors ----------------------------------------------------------------------------

## Scatters the tree layer of every detailed region on a worker thread; the impostor
## MultiMeshes are built on the main thread once it finishes (_process -> _collect_far).
func _build_far_layer() -> void:
	VegetationScatter.warm()
	for rid: String in terrain.regions:
		_far_attach(rid)


## Scatters a region's far trees on workers (low priority); _collect_far adds them when done.
func _far_attach(rid: String) -> void:
	if _far.has(rid):
		# Still scattering after a detach: keep that work (its task must stay joinable).
		_far[rid]["dropped"] = false
		return
	var rt: RegionTerrain = terrain.regions.get(rid)
	if rt == null:
		return
	var seed_v: int = Game.session.world_seed
	var height_fn: Callable = terrain.height_at
	var removed: Dictionary = _removed.duplicate(true)
	var fps: Dictionary = _footprints
	# The cave set as published now: immutable, so the workers may read it (a new one replaces it).
	var caves: Object = terrain.get(&"caves")
	if caves != null and (not caves.has_method(&"keep_out") or bool(caves.call(&"is_empty"))):
		caves = null
	var jobs: Array = []
	var cx0: int = int(floor(rt.rect.position.x / CHUNK))
	var cz0: int = int(floor(rt.rect.position.y / CHUNK))
	var count: int = int(rt.rect.size.x / CHUNK)
	for cz: int in range(cz0, cz0 + count):
		for cx: int in range(cx0, cx0 + count):
			jobs.append([rid, Vector2i(cx, cz)])
	var results: Array = []
	results.resize(jobs.size())
	# Impostor sizes per species, read here: ImpostorLibrary caches them in a static (not for
	# worker threads).
	var dims: Dictionary = {}
	for d: ContentDef in Content.all(&"species"):
		if (d as SpeciesDef).veg_kind == "tree":
			dims[d.id] = ImpostorLibrary.size_for(d as SpeciesDef)
	# Each element writes only its own slot of the pre-sized results array. Low priority: Godot
	# caps low-priority work to a share of the pool, so the near chunks around the player (high
	# priority scatter jobs, terrain meshing) never queue behind the far layer.
	var task: int = WorkerThreadPool.add_group_task(func(i: int) -> void:
		results[i] = _far_buffers(_scatter_far_chunk(rt, jobs[i][1], seed_v, height_fn, removed, fps.get(jobs[i][1], []), caves), dims),
		jobs.size(), -1, false, "far trees")
	_far[rid] = {"task": task, "jobs": jobs, "chunks": results, "holder": null, "mats": [], "dropped": false}


## Scatters a region's far trees again (a cave placed or removed there). The old impostors stay
## up until the new ones are built (_far_build frees them), so the region's skyline never blinks;
## a scatter still running finishes first and starts over (its task must stay joinable).
func _far_redo(rid: String) -> void:
	if not _far.has(rid):
		return
	var e: Dictionary = _far[rid]
	if int(e["task"]) >= 0:
		e["redo"] = true
		return
	if bool(e["dropped"]):
		return
	_far.erase(rid)
	_far_attach(rid)
	if _far.has(rid):
		_far[rid]["old"] = [e["holder"], e["mats"]]
		var older: Array = e.get("old", [])
		if not older.is_empty():
			_far_free_old(older)
	else:
		_far_free_old([e["holder"], e["mats"]])


func _far_free_old(old: Array) -> void:
	if old[0] != null and is_instance_valid(old[0]):
		(old[0] as Node).queue_free()
	for m: ShaderMaterial in old[1]:
		_far_mats.erase(m)


## A region detached: its far trees go (once their scatter, if still running, comes back).
func _far_detach(rid: String) -> void:
	if not _far.has(rid):
		return
	var e: Dictionary = _far[rid]
	if int(e["task"]) >= 0:
		e["dropped"] = true
		return
	_far_free(rid)


func _far_free(rid: String) -> void:
	var e: Dictionary = _far[rid]
	if e.has("old"):
		_far_free_old(e["old"])
	if e["holder"] != null and is_instance_valid(e["holder"]):
		(e["holder"] as Node).queue_free()
	for m: ShaderMaterial in e["mats"]:
		_far_mats.erase(m)
	_far.erase(rid)
	_coarse_show(rid)


## A chunk's far trees as MultiMesh transform buffers per species ({species: [count,
## PackedFloat32Array of 12 floats each]}), built on the worker (ADR-0038): the main thread only
## joins them, where setting ~50k transforms one by one took ~0.5 s of one frame.
static func _far_buffers(insts: Array, dims: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for inst: VegetationScatter.Instance in insts:
		var dim: Vector2 = dims.get(inst.species, Vector2(6.4, 21.0))
		var b := Basis(Vector3.UP, inst.yaw).scaled(Vector3(dim.x, dim.y, dim.x) * inst.scale)
		if not out.has(inst.species):
			out[inst.species] = [0, PackedFloat32Array()]
		var e: Array = out[inst.species]
		var buf: PackedFloat32Array = e[1]
		buf.append_array([b.x.x, b.y.x, b.z.x, inst.pos.x, b.x.y, b.y.y, b.z.y, inst.pos.y, b.x.z, b.y.z, b.z.z, inst.pos.z])
		e[1] = buf
		e[0] = int(e[0]) + 1
	return out


## Trees of one chunk for the far layer (felled ones and those on a town building removed).
static func _scatter_far_chunk(rt: RegionTerrain, key: Vector2i, seed_v: int, height_fn: Callable, removed: Dictionary, fps: Array = [], caves: Object = null) -> Array:
	var gone: Dictionary = removed.get(Ids.chunk_key(key.x, key.y), {})
	var keep: Array = []
	var layers: Dictionary = VegetationScatter.scatter_chunk(key, rt, seed_v, height_fn, Callable(), 1)
	for inst: VegetationScatter.Instance in layers.get("tree", []):
		if not gone.has(str(inst.index)) and not _in_footprint(fps, "tree", inst.pos.x, inst.pos.z) \
				and (caves == null or not bool(caves.call(&"keep_out", inst.pos.x, inst.pos.z))):
			keep.append(inst)
	return keep


## Whether a `layer` instance at (x, z) stands on one of `fps` (a chunk's _footprints entry) or its
## margin, or on the walk in front of it.
static func _in_footprint(fps: Array, layer: String, x: float, z: float) -> bool:
	if fps.is_empty():
		return false
	var m: float = float(FOOTPRINT_MARGIN.get(layer, 0.5))
	var front: float = float(FOOTPRINT_FRONT.get(layer, 0.0))
	for f: Array in fps:
		var lp: Vector2 = (f[0] as Transform2D) * Vector2(x, z)
		var box: Rect2 = f[1]
		if lp.x > box.position.x - m and lp.x < box.end.x + m and lp.y > box.position.y - m and lp.y < box.end.y + m + front:
			return true
	return false


## _footprints from the registry's town lots (an organic town's frame lots and a framework's rect
## lots, Pell's Crossing's on the main map). An authored building
## fills its footprint; a generated one stands where BuildingGenerator.plan_box lays it out.
func _build_footprints(reg: PoiRegistry) -> void:
	if reg == null:
		return
	var db: Node = ContentDB.instance
	var max_m: float = 0.0
	for k: String in FOOTPRINT_MARGIN:
		max_m = maxf(max_m, float(FOOTPRINT_MARGIN[k]) + float(FOOTPRINT_FRONT.get(k, 0.0)))
	for e: Dictionary in reg.entries.values():
		if str(e["kind"]) != "lot":
			continue
		var res: Dictionary = e["res"]
		var l: Dictionary = res.get("lot", {})
		if not l.has("frame") and not l.has("rect"):
			continue
		var fp := Vector2i.ZERO
		var box := Rect2i()
		match str(res.get("kind", "")):
			"authored":
				var pd: PoiDef = db.call(&"get_def", &"poi", StringName(str(res["def_id"]))) as PoiDef if db != null else null
				if pd == null:
					continue
				fp = pd.footprint
				box = Rect2i(Vector2i.ZERO, fp)
			"generated":
				var t: BuildingTemplateDef = db.call(&"get_def", &"building_template", StringName(str(res["template"]))) as BuildingTemplateDef if db != null else null
				if t == null:
					continue
				fp = res["size"]
				box = BuildingGenerator.plan_box(t, int(res["seed"]), fp)
				if box.size == Vector2i.ZERO:
					continue
			_:
				continue
		var local: Transform3D = LotPicker.lot_local_xf(l, fp) if l.has("frame") else PoiRegistry.rect_lot_xf(l, fp)
		var xf: Transform3D = (e["fxf"] as Transform3D) * local
		var x2 := Transform2D(Vector2(xf.basis.x.x, xf.basis.x.z), Vector2(xf.basis.z.x, xf.basis.z.z), Vector2(xf.origin.x, xf.origin.z))
		var entry: Array = [x2.affine_inverse(), Rect2(box), 0.0]
		# The chunks the box (grown by the widest margin) reaches.
		var lo := Vector2(INF, INF)
		var hi := Vector2(-INF, -INF)
		var gb: Rect2 = Rect2(box).grow(max_m)
		for c: Vector2 in [gb.position, Vector2(gb.end.x, gb.position.y), gb.end, Vector2(gb.position.x, gb.end.y)]:
			var wp: Vector2 = x2 * c
			lo = lo.min(wp)
			hi = hi.max(wp)
		for cz: int in range(floori(lo.y / CHUNK), floori(hi.y / CHUNK) + 1):
			for cx: int in range(floori(lo.x / CHUNK), floori(hi.x / CHUNK) + 1):
				var key := Vector2i(cx, cz)
				if not _footprints.has(key):
					_footprints[key] = []
				(_footprints[key] as Array).append(entry)


func _collect_far() -> void:
	for rid0: String in _far.keys():
		var e: Dictionary = _far[rid0]
		if int(e["task"]) < 0 or not WorkerThreadPool.is_group_task_completed(int(e["task"])):
			continue
		WorkerThreadPool.wait_for_group_task_completion(int(e["task"]))
		e["task"] = -1
		if bool(e["dropped"]):
			_far_free(rid0)
			continue
		if bool(e.get("redo", false)):
			# The caves changed while it scattered: its results are dropped and it starts over (a
			# scatter is never built yet while it runs; the impostors it replaces stay up).
			_far.erase(rid0)
			_far_attach(rid0)
			if e.has("old") and _far.has(rid0):
				_far[rid0]["old"] = e["old"]
			elif e.has("old"):
				_far_free_old(e["old"])
			continue
		_far_build(rid0, e)
		# One region a frame.
		return


## Joins a region's chunk buffers per species (packed appends, no per-tree work here) and adds
## its MultiMeshes.
func _far_build(rid0: String, e: Dictionary) -> void:
	var holder := Node3D.new()
	holder.name = "Far_%s" % rid0
	_far_root.add_child(holder)
	e["holder"] = holder
	var joined: Dictionary = {}
	var jobs: Array = e["jobs"]
	var chunks: Array = e["chunks"]
	for i: int in jobs.size():
		var rid: String = jobs[i][0]
		if not joined.has(rid):
			joined[rid] = {}
		var per_species: Dictionary = joined[rid]
		var chunk: Dictionary = chunks[i] if chunks[i] != null else {}
		for sp_id: Variant in chunk:
			var ce: Array = chunk[sp_id]
			if not per_species.has(sp_id):
				per_species[sp_id] = [0, PackedFloat32Array()]
			var acc: Array = per_species[sp_id]
			acc[0] = int(acc[0]) + int(ce[0])
			var buf: PackedFloat32Array = acc[1]
			buf.append_array(ce[1])
			acc[1] = buf
	e["jobs"] = []
	e["chunks"] = []
	if e.has("old"):
		_far_free_old(e["old"])
		e.erase("old")
	for rid: String in joined:
		var per_species: Dictionary = joined[rid]
		for sp_id: StringName in per_species:
			var sp: SpeciesDef = Content.get_def(&"species", sp_id) as SpeciesDef
			var mat: ShaderMaterial = _impostor_mat(sp)
			_far_mats.append(mat)
			(e["mats"] as Array).append(mat)
			holder.add_child(_impostor_mmi("Far_%s_%s" % [rid, sp_id], mat, per_species[sp_id]))
	# Its coarse clusters (TD-006) give way now that the region's own far trees are up.
	_coarse_show(rid0)


## The far impostor material of a species (its atlas, normals and season tints).
func _impostor_mat(sp: SpeciesDef) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://assets/shaders/impostor.gdshader")
	mat.set_shader_parameter("atlas", ImpostorLibrary.atlas_for(sp))
	var nrm: Texture2D = ImpostorLibrary.normal_atlas_for(sp)
	mat.set_shader_parameter("has_normals", nrm != null)
	if nrm != null:
		mat.set_shader_parameter("normal_atlas", nrm)
	mat.set_shader_parameter("frames", ImpostorLibrary.FRAMES)
	mat.set_shader_parameter("discard_rect", _near_rect())
	if ImpostorLibrary.is_baked(sp):
		var tints: Dictionary = ImpostorLibrary.season_tints(sp)
		for k: String in tints:
			mat.set_shader_parameter(k, tints[k])
	return mat


## A MultiMesh of impostor quads from a [count, transform buffer] pair, drawn to the view distance.
func _impostor_mmi(node_name: String, mat: ShaderMaterial, e2: Array) -> MultiMeshInstance3D:
	var quad := QuadMesh.new()
	quad.size = Vector2(1.0, 1.0)
	quad.center_offset = Vector3(0, 0.5, 0)
	quad.material = mat
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = quad
	mm.instance_count = int(e2[0])
	if int(e2[0]) > 0:
		mm.buffer = e2[1]
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi.visibility_range_end = float(Settings.gfx("view_distance", 1400.0))
	return mmi


# --- Coarse far forest (TD-006) ---------------------------------------------------------------

## Starts the cluster scatter of coarse regions coming into view (nearest first, COARSE_JOBS at a
## time) and frees those well past it.
func _coarse_update(pos: Vector3) -> void:
	var p := Vector2(pos.x, pos.z)
	var view: float = float(Settings.gfx("view_distance", 1400.0))
	var running: int = 0
	for e: Dictionary in _coarse.values():
		if int(e["task"]) >= 0:
			running += 1
	var want: Array = []
	for rid: String in terrain.coarse:
		var rt: RegionTerrain = terrain.coarse[rid]
		var d: float = RegionRings.rect_distance(rt.rect, p)
		if _coarse.has(rid):
			if d > view + COARSE_FREE_PAST and int(_coarse[rid]["task"]) < 0:
				_coarse_free(rid)
		elif d < view:
			want.append([d, rid])
	_coarse_ring(p, view)
	want.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	for w: Array in want:
		if running >= COARSE_JOBS:
			break
		_coarse_attach(str(w[1]))
		running += 1


## Scatters a coarse region's clusters on workers, a block per element (low priority).
func _coarse_attach(rid: String) -> void:
	var rt: RegionTerrain = terrain.coarse.get(rid)
	if rt == null:
		return
	VegetationScatter.warm()
	var seed_v: int = Game.session.world_seed
	var fps: Dictionary = _footprints
	var caves: Object = terrain.get(&"caves")
	if caves != null and (not caves.has_method(&"keep_out") or bool(caves.call(&"is_empty"))):
		caves = null
	var dims: Dictionary = {}
	var heights: Dictionary = {}
	for d: ContentDef in Content.all(&"species"):
		var sp := d as SpeciesDef
		if sp.veg_kind == "tree":
			dims[sp.id] = ImpostorLibrary.size_for(sp)
			heights[sp.id] = sp.height_range
	var n: int = maxi(1, int(ceil(rt.rect.size.x / COARSE_BLOCK)))
	var results: Array = []
	results.resize(n * n)
	var task: int = WorkerThreadPool.add_group_task(func(i: int) -> void:
		var o: Vector2 = rt.rect.position + Vector2(i % n, floori(float(i) / n)) * COARSE_BLOCK
		var block := Rect2(o, Vector2(COARSE_BLOCK, COARSE_BLOCK)).intersection(rt.rect)
		results[i] = _coarse_block(rt, block, seed_v, fps, caves, dims, heights),
		n * n, -1, false, "coarse trees")
	_coarse[rid] = {"task": task, "rect": rt.rect, "blocks": results, "holder": null}


## One block's cluster quads as {species: [count, transform buffer]}, on a worker. A 16 m cell
## (the coarse spacing) expects the trees the near scatter would put there (its biome's tree
## density under the vegetation mask); every COARSE_TREES of them make a cluster quad, the
## remainder by chance. Steep ground, town buildings and cave mouths stay bare as they do near.
static func _coarse_block(rt: RegionTerrain, block: Rect2, seed_v: int, fps: Dictionary, caves: Object, dims: Dictionary, heights: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	var tables: Dictionary = VegetationScatter._biome_tables()
	var cell: float = maxf(rt.spacing, 8.0)
	var tree_cell: float = float(VegetationScatter.LAYERS["tree"]["cell"])
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.derive_seed(seed_v, "veg_coarse:%d_%d" % [int(block.position.x), int(block.position.y)])
	var steps_x: int = int(block.size.x / cell)
	var steps_z: int = int(block.size.y / cell)
	for gz: int in steps_z:
		for gx: int in steps_x:
			# The same draws every cell, so a cell's clusters don't hang on its neighbours'.
			var r_count: float = rng.randf()
			var draws: PackedFloat32Array = []
			for k: int in COARSE_PER_CELL * 4:
				draws.append(rng.randf())
			var cx: float = block.position.x + (gx + 0.5) * cell
			var cz: float = block.position.y + (gz + 0.5) * cell
			var veg: float = rt.veg_at(cx, cz)
			if veg <= 0.05:
				continue
			var table: Dictionary = (tables.get(rt.biome_at(cx, cz), {}) as Dictionary).get("tree", {})
			if table.is_empty():
				continue
			var p_place: float = minf(1.0, float(table["_total"]) * tree_cell * tree_cell / 100.0) * veg
			var trees: float = p_place * (cell / tree_cell) * (cell / tree_cell)
			var q: float = trees / COARSE_TREES
			var count: int = mini(COARSE_PER_CELL, int(q) + (1 if r_count < q - floorf(q) else 0))
			for k: int in count:
				var x: float = cx + (draws[k * 4] - 0.5) * cell
				var z: float = cz + (draws[k * 4 + 1] - 0.5) * cell
				if not rt.rect.has_point(Vector2(x, z)) or rt.height.slope_deg(x, z) > COARSE_MAX_SLOPE:
					continue
				var key := Vector2i(floori(x / CHUNK), floori(z / CHUNK))
				if _in_footprint(fps.get(key, []), "tree", x, z):
					continue
				if caves != null and bool(caves.call(&"keep_out", x, z)):
					continue
				var sp_id: StringName = VegetationScatter._pick_species(table, draws[k * 4 + 2])
				if not dims.has(sp_id):
					continue
				var dim: Vector2 = dims[sp_id]
				var hr: Vector2 = heights[sp_id]
				var sc: float = lerpf(hr.x, hr.y, draws[k * 4 + 3]) / 20.0
				var yaw: float = draws[k * 4 + 3] * 977.0
				var b := Basis(Vector3.UP, yaw).scaled(Vector3(dim.x * COARSE_SPREAD, dim.y * COARSE_LIFT, dim.x * COARSE_SPREAD) * sc)
				# Sunk a little more than a near tree: the 16 m ground is smoother than the real one.
				var y: float = rt.height.sample(x, z) - 0.6
				if not out.has(sp_id):
					out[sp_id] = [0, PackedFloat32Array()]
				var e: Array = out[sp_id]
				var buf: PackedFloat32Array = e[1]
				buf.append_array([b.x.x, b.y.x, b.z.x, x, b.x.y, b.y.y, b.z.y, y, b.x.z, b.y.z, b.z.z, z])
				e[1] = buf
				e[0] = int(e[0]) + 1
	return _coarse_fold(out)


## Folds a block's minor species (under COARSE_MINOR of its quads) into its main one: at range a
## few snags or birches among the firs don't show, and each species is a draw call a block.
static func _coarse_fold(out: Dictionary) -> Dictionary:
	var total: int = 0
	var main: Variant = null
	for k: Variant in out:
		total += int(out[k][0])
		if main == null or int(out[k][0]) > int(out[main][0]):
			main = k
	if main == null:
		return out
	for k: Variant in out.keys():
		if k != main and float(out[k][0]) < float(total) * COARSE_MINOR:
			var into: Array = out[main]
			var buf: PackedFloat32Array = into[1]
			buf.append_array(out[k][1])
			into[1] = buf
			into[0] = int(into[0]) + int(out[k][0])
			out.erase(k)
	return out


## Builds the coarse regions whose scatter came back (one a frame).
func _collect_coarse() -> void:
	for rid: String in _coarse.keys():
		var e: Dictionary = _coarse[rid]
		if int(e["task"]) < 0 or not WorkerThreadPool.is_group_task_completed(int(e["task"])):
			continue
		WorkerThreadPool.wait_for_group_task_completion(int(e["task"]))
		e["task"] = -1
		if bool(e.get("redo", false)):
			_coarse.erase(rid)
			continue
		var holder := Node3D.new()
		holder.name = "Coarse_%s" % rid
		_far_root.add_child(holder)
		e["holder"] = holder
		var blocks: Array = e["blocks"]
		for i: int in blocks.size():
			var per_species: Dictionary = blocks[i] if blocks[i] != null else {}
			for sp_id: StringName in per_species:
				var mmi: MultiMeshInstance3D = _impostor_mmi("Coarse_%s_%d_%s" % [rid, i, sp_id], _coarse_mat(sp_id), per_species[sp_id])
				# The range is measured to the block's centre: half its diagonal more keeps the
				# block's near corner drawn out to the view distance (fade_ring shrinks the rest).
				mmi.visibility_range_end += COARSE_BLOCK * 0.71
				holder.add_child(mmi)
		e["blocks"] = []
		_coarse_show(rid)
		return


## Where the clusters stand on the ground and shrink away (impostor fade_ring), the far terrain
## takes its canopy raise down (terrain_far canopy_flat), so they hand over to it at the view
## distance instead of popping or being buried in it.
func _coarse_ring(p: Vector2, view: float) -> void:
	var ring := Vector3(p.x, p.y, view if coarse_enabled else 0.0)
	for m: ShaderMaterial in _coarse_mats.values():
		m.set_shader_parameter("fade_ring", ring)
	if terrain.has_method(&"set_canopy_flat"):
		terrain.set_canopy_flat(ring)


## The coarse layer's material for a species: one per species, shared by every coarse region.
func _coarse_mat(sp_id: StringName) -> ShaderMaterial:
	if not _coarse_mats.has(sp_id):
		var mat: ShaderMaterial = _impostor_mat(Content.get_def(&"species", sp_id) as SpeciesDef)
		# No near square: a coarse region has no near trees to take over (fade_inner instead).
		mat.set_shader_parameter("discard_rect", Vector4.ZERO)
		mat.set_shader_parameter("fade_inner", COARSE_INNER)
		if world != null and world.player != null:
			var pp: Vector3 = world.player.global_position
			mat.set_shader_parameter("fade_ring", Vector3(pp.x, pp.z, float(Settings.gfx("view_distance", 1400.0)) if coarse_enabled else 0.0))
		_coarse_mats[sp_id] = mat
	return _coarse_mats[sp_id]


## Hides a region's clusters while its own far trees are up (it attached at 1 m), shows them again
## once those go.
func _coarse_show(rid: String) -> void:
	if not _coarse.has(rid):
		return
	var holder: Variant = _coarse[rid]["holder"]
	if holder == null or not is_instance_valid(holder):
		return
	var far_up: bool = _far.has(rid) and _far[rid]["holder"] != null and is_instance_valid(_far[rid]["holder"])
	(holder as Node3D).visible = coarse_enabled and not far_up


func _coarse_free(rid: String) -> void:
	var e: Dictionary = _coarse[rid]
	if int(e["task"]) >= 0:
		e["redo"] = true
		return
	if e["holder"] != null and is_instance_valid(e["holder"]):
		(e["holder"] as Node).queue_free()
	_coarse.erase(rid)


## Coarse regions still scattering or waiting to be built.
func coarse_pending() -> int:
	var n: int = 0
	for e: Dictionary in _coarse.values():
		if e["holder"] == null:
			n += 1
	return n


## Coarse cluster quads standing (for perf views and tests).
func coarse_count() -> int:
	var n: int = 0
	for e: Dictionary in _coarse.values():
		var holder: Variant = e["holder"]
		if holder == null or not is_instance_valid(holder) or not (holder as Node3D).visible:
			continue
		for c: Node in (holder as Node).get_children():
			n += (c as MultiMeshInstance3D).multimesh.instance_count
	return n


func _near_rect() -> Vector4:
	var lo := Vector2(_center.x - NEAR_CHUNKS, _center.y - NEAR_CHUNKS) * CHUNK
	var hi := Vector2(_center.x + NEAR_CHUNKS + 1, _center.y + NEAR_CHUNKS + 1) * CHUNK
	return Vector4(lo.x, lo.y, hi.x, hi.y)


# --- Collision ---------------------------------------------------------------------------------

func _update_collision(pos: Vector3) -> void:
	var want: Dictionary = {}
	var c: Vector2i = TerrainManager.chunk_of(pos.x, pos.z)
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var key := Vector2i(c.x + dx, c.y + dz)
			var layers: Dictionary = _data.get(key, {})
			for layer: String in ["tree", "medium"]:
				for inst: VegetationScatter.Instance in layers.get(layer, []):
					if inst.pos.distance_squared_to(pos) > COLLISION_RADIUS * COLLISION_RADIUS:
						continue
					if _is_removed(key, inst.index):
						continue
					var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
					if not sp.collides:
						continue
					want[VegetationScatter.instance_id(key, inst.index)] = [key, inst, sp]
	for id: StringName in _bodies.keys():
		if not want.has(id):
			(_bodies[id] as Node).queue_free()
			_bodies.erase(id)
	for id: StringName in want:
		if _bodies.has(id):
			continue
		var w: Array = want[id]
		_bodies[id] = _make_body(id, w[0], w[1], w[2])


func _make_body(id: StringName, key: Vector2i, inst: VegetationScatter.Instance, sp: SpeciesDef) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.collision_layer = 1 << 12
	body.collision_mask = 0
	body.set_meta(&"veg_id", id)
	body.set_meta(&"damage_receiver", self)
	body.set_meta(&"surface", "wood_floor")
	var model: String = sp.models[inst.variant % sp.models.size()]
	var shapes: Array = ModelLibrary.shapes(model) if sp.veg_kind != "tree" else []
	if shapes.is_empty():
		var cs := CollisionShape3D.new()
		if sp.veg_kind == "tree" or sp.veg_kind == "deadfall":
			var cyl := CylinderShape3D.new()
			cyl.radius = maxf(0.08, sp.trunk_radius * inst.scale * (1.0 if sp.veg_kind == "tree" else 1.0))
			cyl.height = 8.0 if sp.veg_kind == "tree" else 1.0
			cs.shape = cyl
			cs.position = Vector3(0, cyl.height * 0.5, 0)
		else:
			var sph := SphereShape3D.new()
			sph.radius = maxf(0.3, sp.trunk_radius * inst.scale)
			cs.shape = sph
			cs.position = Vector3(0, sph.radius * 0.6, 0)
		body.add_child(cs)
		body.position = inst.pos
	else:
		for s: Dictionary in shapes:
			var cs2 := CollisionShape3D.new()
			cs2.shape = s["shape"]
			cs2.transform = s["transform"]
			body.add_child(cs2)
		body.transform = _xform(inst)
	add_child(body)
	return body


# --- Chopping ----------------------------------------------------------------------------------

## Called for hits on vegetation bodies (damage_receiver meta).
func take_damage(info: DamageInfo) -> void:
	var col: Node = info.collider as Node
	if col == null or not col.has_meta(&"veg_id"):
		return
	var id: StringName = col.get_meta(&"veg_id")
	var found: Array = _find_instance(id)
	if found.is_empty():
		return
	var key: Vector2i = found[0]
	var inst: VegetationScatter.Instance = found[1]
	var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
	var chop: float = float(info.tool_power.get("chop", 0.0))
	Audio.play_3d(&"sfx/axe_chop_wood" if chop > 0.0 else &"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -2.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(info.hit_pos, 22.0 if chop > 0.0 else 10.0, &"chop", info.source_id)
	if Game.session != null:
		Game.session.heat.add(info.hit_pos, float(Content.config(&"heat").get("sources", {}).get("chop", 0.6)))
	FxLibrary.spawn_chips(self, info.hit_pos, -info.direction)
	if sp.veg_kind != "tree" or chop <= 0.0:
		return
	var hp: float = float(_tree_hp.get(id, sp.hp * clampf(inst.scale, 0.6, 1.6)))
	hp -= chop
	_tree_hp[id] = hp
	if hp <= 0.0:
		_fell(key, inst, sp, info)


func _find_instance(id: StringName) -> Array:
	var parts: PackedStringArray = String(id).split(":")
	if parts.size() != 3:
		return []
	var key: Vector2i = Ids.parse_chunk_key(parts[1])
	var idx: int = int(parts[2])
	for layer: String in VegetationScatter.ORDER:
		for inst: VegetationScatter.Instance in (_data.get(key, {}) as Dictionary).get(layer, []):
			if inst.index == idx:
				return [key, inst]
	return []


func _mark_removed(key: Vector2i, inst: VegetationScatter.Instance, state: String, regrow: float) -> void:
	var ck: String = Ids.chunk_key(key.x, key.y)
	if not _removed.has(ck):
		_removed[ck] = {}
	_removed[ck][str(inst.index)] = {"state": state, "day": Game.session.clock.day(), "regrow": regrow}
	Game.session.world.trees = _removed


func _fell(key: Vector2i, inst: VegetationScatter.Instance, sp: SpeciesDef, info: DamageInfo) -> void:
	var id: StringName = VegetationScatter.instance_id(key, inst.index)
	_mark_removed(key, inst, "stump", 0.0)
	_tree_hp.erase(id)
	if _bodies.has(id):
		(_bodies[id] as Node).queue_free()
		_bodies.erase(id)
	_rebuild(key)
	var mesh: Mesh = _lod_mesh(sp, inst.variant, 0)
	var ft := FallingTree.new()
	ft.mesh = mesh
	ft.species = sp
	ft.instance_scale = inst.scale
	ft.fall_dir = (info.direction * Vector3(1, 0, 1)).normalized() if info.direction.length() > 0.1 else Vector3.FORWARD
	ft.tree_id = id
	add_child(ft)
	ft.global_transform = _xform(inst)
	if sp.stump_model != "":
		var stump := MeshInstance3D.new()
		stump.mesh = ModelLibrary.mesh(sp.stump_model, "box")
		stump.transform = Transform3D(Basis(Vector3.UP, inst.yaw).scaled(Vector3.ONE * clampf(inst.scale, 0.7, 1.4)), inst.pos)
		stump.name = "Stump_" + String(id)
		add_child(stump)
	Audio.play_3d(&"sfx/tree_crack", inst.pos + Vector3.UP * 2.0, {"volume_db": 0.0, "max_distance": 150.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(inst.pos, 45.0, &"tree_fall", info.source_id)
	Game.session.stats["trees_felled"] = int(Game.session.stats.get("trees_felled", 0)) + 1
	var p: PlayerState = Game.local_player()
	if p != null:
		# The companion's trees pay the player a share (ADR-0058: he is the player's crew).
		p.progression.award("fell_tree", CompanionDef.share_for(info.source_id))
	Events.tree_felled.emit(id, inst.pos, info.source_id)


## Nearest loaded instance of a vegetation kind ("tree", "rock", ...): [chunk, Instance] or [].
func nearest_instance(pos: Vector3, veg_kind: String, max_dist: float = 80.0) -> Array:
	var best: Array = []
	var best_d: float = max_dist
	for key: Vector2i in _data:
		for layer: String in VegetationScatter.ORDER:
			for inst: VegetationScatter.Instance in (_data[key] as Dictionary).get(layer, []):
				var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
				if sp.veg_kind != veg_kind or _is_removed(key, inst.index):
					continue
				var d: float = inst.pos.distance_to(pos)
				if d < best_d:
					best_d = d
					best = [key, inst]
	return best


## Loaded instances within `max_dist` (horizontally) of `pos`, nearest first, as [chunk, Instance]
## pairs; only one species when `species` is given. Visual QA frames a tree or a cluster of caps
## with it, and keeps the lens clear of everything else.
func instances_near(pos: Vector3, max_dist: float, species: StringName = &"") -> Array:
	var found: Array = []
	var p := Vector2(pos.x, pos.z)
	for key: Vector2i in _data:
		var lo := Vector2(key.x, key.y) * CHUNK
		if p.x < lo.x - max_dist or p.x > lo.x + CHUNK + max_dist or p.y < lo.y - max_dist or p.y > lo.y + CHUNK + max_dist:
			continue
		for layer: String in VegetationScatter.ORDER:
			for inst: VegetationScatter.Instance in (_data[key] as Dictionary).get(layer, []):
				if species != &"" and inst.species != species:
					continue
				var d: float = Vector2(inst.pos.x, inst.pos.z).distance_to(p)
				if d <= max_dist and not _is_removed(key, inst.index):
					found.append([d, key, inst])
	found.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	return found.map(func(e: Array) -> Array: return [e[1], e[2]])


## Collision body of a tree/boulder instance if it is currently pooled near the player.
func body_for(key: Vector2i, inst: VegetationScatter.Instance) -> Node:
	return _bodies.get(VegetationScatter.instance_id(key, inst.index))


## Collidable trees and boulders inside a rect (navigation obstructions).
func obstacles_in_rect(r: Rect2) -> Array:
	var out: Array = []
	var c0 := Vector2i(int(floor(r.position.x / CHUNK)), int(floor(r.position.y / CHUNK)))
	var c1 := Vector2i(int(floor(r.end.x / CHUNK)), int(floor(r.end.y / CHUNK)))
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			var key := Vector2i(cx, cz)
			var layers: Dictionary = _data.get(key, {})
			for layer: String in ["tree", "medium"]:
				for inst: VegetationScatter.Instance in layers.get(layer, []):
					if not r.has_point(Vector2(inst.pos.x, inst.pos.z)) or _is_removed(key, inst.index):
						continue
					var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
					if not sp.collides:
						continue
					var rad: float = maxf(0.15, sp.trunk_radius * inst.scale) if sp.veg_kind == "tree" else maxf(0.3, sp.trunk_radius * inst.scale * 0.8)
					out.append({"pos": inst.pos, "radius": rad})
	return out


# --- Harvesting ---------------------------------------------------------------------------------

## Nearest harvestable plant/stone/deadfall within reach of a ray (for the interaction system).
func pick_harvestable(from: Vector3, dir: Vector3, reach: float) -> Object:
	var best: VegetationScatter.Instance = null
	var best_key := Vector2i.ZERO
	var best_d: float = 0.9
	# Only the cells the ray's box (grown past best_d) touches; a 4 m cell lies in one 64 m chunk.
	var end: Vector3 = from + dir * reach
	var lo := Vector2i(floori((minf(from.x, end.x) - 1.0) / PICK_CELL), floori((minf(from.z, end.z) - 1.0) / PICK_CELL))
	var hi := Vector2i(floori((maxf(from.x, end.x) + 1.0) / PICK_CELL), floori((maxf(from.z, end.z) + 1.0) / PICK_CELL))
	for cz: int in range(lo.y, hi.y + 1):
		for cx: int in range(lo.x, hi.x + 1):
			var k: Vector2i = TerrainManager.chunk_of((cx + 0.5) * PICK_CELL, (cz + 0.5) * PICK_CELL)
			var bins: Dictionary = _pickable.get(k, {})
			for inst: VegetationScatter.Instance in bins.get(Vector2i(cx, cz), []):
				var to: Vector3 = inst.pos + Vector3.UP * 0.25 - from
				var t: float = to.dot(dir)
				if t < 0.0 or t > reach:
					continue
				var d: float = (to - dir * t).length()
				if d < best_d and not _is_removed(k, inst.index):
					best_d = d
					best = inst
					best_key = k
	if best == null:
		return null
	if _last_harvest != null and _last_harvest.same_as(best_key, best):
		return _last_harvest
	var h := HarvestTarget.new()
	h.manager = self
	h.key = best_key
	h.inst = best
	_last_harvest = h
	return h


func harvest(key: Vector2i, inst: VegetationScatter.Instance, player: Player) -> void:
	harvest_into(key, inst, {"player": player.state.id})


## Harvests an instance into whoever `who` names for world.pickup_item: {player} or {owner: the
## companion's id} (ADR-0058 phase 2: he gathers into his own pack).
func harvest_into(key: Vector2i, inst: VegetationScatter.Instance, who: Dictionary) -> void:
	var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
	var rng: RandomNumberGenerator = Game.session.rng.stream("harvest")
	for item: Variant in sp.yields.keys():
		var r: Array = sp.yields[item]
		var n: int = rng.randi_range(int(r[0]), int(r[1]))
		if n > 0:
			var res: Dictionary = Game.execute(&"world.pickup_item", who.merged({"item": item, "count": n}))
			# A full pack leaves the rest on the ground instead of destroying it.
			var left: int = int(res.get("left", 0))
			if left > 0:
				ItemDrop.spawn(get_parent(), ItemStack.make(StringName(str(item)), left), inst.pos + Vector3.UP * 0.5)
	_mark_removed(key, inst, "harvested", sp.regrow_days)
	_rebuild(key)
	Audio.play_3d(&"sfx/foliage_rustle" if sp.veg_kind != "rock" else &"sfx/stone_pickup", inst.pos, {"volume_db": -6.0})


func save_into(session: GameSession) -> void:
	session.world.trees = _removed
