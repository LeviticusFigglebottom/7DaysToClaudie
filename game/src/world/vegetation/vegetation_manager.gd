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
## can pick), filtered once when the chunk's scatter arrives.
var _pickable: Dictionary = {}
## Far layer: one group task over every 64 m chunk of every detailed region (one element each).
## The far impostor layer per region (ADR-0038: regions attach and detach in a streamed world):
## rid -> {task (-1 once built), jobs: [[rid, chunk key]], chunks: [result per job], holder: Node3D,
## mats: [ShaderMaterial], dropped: bool}.
var _far: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	terrain = w.terrain
	_removed = Game.session.world.trees
	_far_root = Node3D.new()
	_far_root.name = "FarTrees"
	add_child(_far_root)
	_build_far_layer()
	terrain.region_attached.connect(_far_attach)
	terrain.region_detached.connect(_far_detach)
	# The fungal mounds Hum survivors leave where they root at dawn (ADR-0025).
	var mounds := BloomMounds.new()
	mounds.name = "BloomMounds"
	add_child(mounds)
	mounds.setup_world(w)


# --- Queries ----------------------------------------------------------------------------------

func _rt_for_chunk(key: Vector2i) -> RegionTerrain:
	return terrain.region_terrain_at((key.x + 0.5) * CHUNK, (key.y + 0.5) * CHUNK)


func _is_removed(key: Vector2i, index: int) -> bool:
	var ck: String = Ids.chunk_key(key.x, key.y)
	var st: Dictionary = (_removed.get(ck, {}) as Dictionary).get(str(index), {})
	if st.is_empty():
		return false
	var sp_regrow: float = float(st.get("regrow", 0.0))
	if sp_regrow > 0.0 and Game.session.clock.day() - int(st.get("day", 0)) >= sp_regrow:
		(_removed[ck] as Dictionary).erase(str(index))
		return false
	return true


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


# --- Streaming --------------------------------------------------------------------------------

func _process(delta: float) -> void:
	_collect_far()
	if world == null or world.player == null:
		return
	_collect()
	_accum += delta
	_col_accum += delta
	var pos: Vector3 = world.player.global_position
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
	for off: Vector2i in _ring_order():
		var key := Vector2i(c.x + off.x, c.y + off.y)
		var want_ground: bool = absi(off.x) <= GROUND_CHUNKS and absi(off.y) <= GROUND_CHUNKS
		if not _data.has(key):
			if not _pending.has(key) and _pending.size() < MAX_JOBS and _rt_for_chunk(key) != null:
				# The worker fills its own slot: `job` gains "task" on this thread after the task has
				# started, and a dictionary written from two threads at once can corrupt itself.
				var out: Array = [{}]
				var job: Dictionary = {"key": key, "out": out}
				job["task"] = WorkerThreadPool.add_task(func() -> void: out[0] = _scatter(key), true, "veg scatter")
				_pending[key] = job
			continue
		var n: Dictionary = _nodes.get(key, {})
		if n.is_empty():
			_build_chunk(key, want_ground)
		elif bool(n.get("ground", false)) != want_ground:
			_set_ground(key, want_ground)


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
			_pickable[key] = _harvestables(job["out"][0])


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
		results[i] = _far_buffers(_scatter_far_chunk(rt, jobs[i][1], seed_v, height_fn, removed), dims),
		jobs.size(), -1, false, "far trees")
	_far[rid] = {"task": task, "jobs": jobs, "chunks": results, "holder": null, "mats": [], "dropped": false}


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
	if e["holder"] != null and is_instance_valid(e["holder"]):
		(e["holder"] as Node).queue_free()
	for m: ShaderMaterial in e["mats"]:
		_far_mats.erase(m)
	_far.erase(rid)


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


## Trees of one chunk for the far layer (felled ones removed).
static func _scatter_far_chunk(rt: RegionTerrain, key: Vector2i, seed_v: int, height_fn: Callable, removed: Dictionary) -> Array:
	var gone: Dictionary = removed.get(Ids.chunk_key(key.x, key.y), {})
	var keep: Array = []
	var layers: Dictionary = VegetationScatter.scatter_chunk(key, rt, seed_v, height_fn, Callable(), 1)
	for inst: VegetationScatter.Instance in layers.get("tree", []):
		if not gone.has(str(inst.index)):
			keep.append(inst)
	return keep


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
	for rid: String in joined:
		var per_species: Dictionary = joined[rid]
		for sp_id: StringName in per_species:
			var sp: SpeciesDef = Content.get_def(&"species", sp_id) as SpeciesDef
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
			_far_mats.append(mat)
			(e["mats"] as Array).append(mat)
			var quad := QuadMesh.new()
			quad.size = Vector2(1.0, 1.0)
			quad.center_offset = Vector3(0, 0.5, 0)
			quad.material = mat
			var e2: Array = per_species[sp_id]
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = quad
			mm.instance_count = int(e2[0])
			if int(e2[0]) > 0:
				mm.buffer = e2[1]
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "Far_%s_%s" % [rid, sp_id]
			mmi.multimesh = mm
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.visibility_range_end = float(Settings.gfx("view_distance", 1400.0))
			holder.add_child(mmi)


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
		p.progression.award("fell_tree")
	Events.tree_felled.emit(id, inst.pos)


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
	var key: Vector2i = TerrainManager.chunk_of(from.x, from.z)
	var best: VegetationScatter.Instance = null
	var best_key := Vector2i.ZERO
	var best_d: float = 0.9
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var k := Vector2i(key.x + dx, key.y + dz)
			for inst: VegetationScatter.Instance in _pickable.get(k, []):
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
	var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
	var rng: RandomNumberGenerator = Game.session.rng.stream("harvest")
	for item: Variant in sp.yields.keys():
		var r: Array = sp.yields[item]
		var n: int = rng.randi_range(int(r[0]), int(r[1]))
		if n > 0:
			var res: Dictionary = Game.execute(&"world.pickup_item", {"player": player.state.id, "item": item, "count": n})
			# A full pack leaves the rest on the ground instead of destroying it.
			var left: int = int(res.get("left", 0))
			if left > 0:
				ItemDrop.spawn(get_parent(), ItemStack.make(StringName(str(item)), left), inst.pos + Vector3.UP * 0.5)
	_mark_removed(key, inst, "harvested", sp.regrow_days)
	_rebuild(key)
	Audio.play_3d(&"sfx/foliage_rustle" if sp.veg_kind != "rock" else &"sfx/stone_pickup", inst.pos, {"volume_db": -6.0})


func save_into(session: GameSession) -> void:
	session.world.trees = _removed
