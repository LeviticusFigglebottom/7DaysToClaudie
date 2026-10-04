class_name VegetationManager
extends Node3D
## Renders and simulates vegetation from VegetationScatter (deterministic per chunk).
##  * near chunks (±NEAR_CHUNKS): MultiMesh per species/variant/LOD with visibility-range fades
##  * ground cover (±GROUND_CHUNKS): ferns, grass, flowers, pebbles with short fade distance
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
const GROUND_END: float = 52.0
const FADE: float = 8.0

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
var _far_task: int = -1
var _far_result: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	terrain = w.terrain
	_removed = Game.session.world.trees
	_far_root = Node3D.new()
	_far_root.name = "FarTrees"
	add_child(_far_root)
	_build_far_layer()


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
	return VegetationScatter.scatter_chunk(key, rt, Game.session.world_seed, terrain.height_at, _water_fn())


## Joins in-flight scatter jobs (they read content and terrain) before the world is freed.
func _exit_tree() -> void:
	for key: Vector2i in _pending.keys():
		WorkerThreadPool.wait_for_task_completion(_pending[key]["task"])
	_pending.clear()
	if _far_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_far_task)
		_far_task = -1


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
	for dz: int in range(-NEAR_CHUNKS, NEAR_CHUNKS + 1):
		for dx: int in range(-NEAR_CHUNKS, NEAR_CHUNKS + 1):
			var key := Vector2i(c.x + dx, c.y + dz)
			var want_ground: bool = absi(dx) <= GROUND_CHUNKS and absi(dz) <= GROUND_CHUNKS
			if not _data.has(key):
				if not _pending.has(key) and _rt_for_chunk(key) != null:
					var job: Dictionary = {"key": key, "res": {}}
					job["task"] = WorkerThreadPool.add_task(func() -> void: job["res"] = _scatter(key), false, "veg scatter")
					_pending[key] = job
				continue
			var n: Dictionary = _nodes.get(key, {})
			if n.is_empty():
				_build_chunk(key, want_ground)
			elif bool(n.get("ground", false)) != want_ground:
				_set_ground(key, want_ground)


func _collect() -> void:
	for key: Vector2i in _pending.keys():
		var job: Dictionary = _pending[key]
		if WorkerThreadPool.is_task_completed(job["task"]):
			WorkerThreadPool.wait_for_task_completion(job["task"])
			_pending.erase(key)
			_data[key] = job["res"]


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
			var lod_count: int = 3 if sp.veg_kind == "tree" else 1
			for lod: int in lod_count:
				var mesh: Mesh = _lod_mesh(sp, variant, lod)
				var begin: float = 0.0 if lod == 0 else LOD_END[lod - 1]
				var end: float = LOD_END[lod] if sp.veg_kind == "tree" else minf(float(sp.lod_distances[1]) * 2.0, 220.0)
				holder.add_child(_mmi(mesh, insts, begin, end, sp.veg_kind != "rock" or lod > 0))
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
	var groups: Dictionary = _group(key, (_data[key] as Dictionary).get("ground", []))
	var density: float = float(Settings.gfx("grass_density", 0.8))
	for gk: String in groups:
		var parts: PackedStringArray = gk.split("|")
		var sp: SpeciesDef = Content.get_def(&"species", StringName(parts[0])) as SpeciesDef
		var insts: Array = groups[gk]
		if sp.veg_kind == "grass" and density < 1.0:
			insts = insts.slice(0, int(insts.size() * density))
		var mmi: MultiMeshInstance3D = _mmi(_lod_mesh(sp, int(parts[1]), 0), insts, 0.0, minf(GROUND_END, float(Settings.gfx("grass_distance", 60.0))), false)
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


func _mmi(mesh: Mesh, insts: Array, begin: float, end: float, shadows: bool) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = insts.size()
	for i: int in insts.size():
		mm.set_instance_transform(i, _xform(insts[i]))
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.visibility_range_begin = begin
	mmi.visibility_range_begin_margin = FADE if begin > 0.0 else 0.0
	mmi.visibility_range_end = end
	mmi.visibility_range_end_margin = FADE
	mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mmi


static func _xform(inst: VegetationScatter.Instance) -> Transform3D:
	var b := Basis.from_euler(Vector3(inst.tilt.x, inst.yaw, inst.tilt.y)).scaled(Vector3.ONE * inst.scale)
	return Transform3D(b, inst.pos)


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
	var regions: Dictionary = terrain.regions.duplicate()
	var seed_v: int = Game.session.world_seed
	var height_fn: Callable = terrain.height_at
	var removed: Dictionary = _removed.duplicate(true)
	_far_task = WorkerThreadPool.add_task(func() -> void: _far_result = _scatter_far(regions, seed_v, height_fn, removed), false, "far trees")


static func _scatter_far(regions: Dictionary, seed_v: int, height_fn: Callable, removed: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for rid: String in regions:
		var rt: RegionTerrain = regions[rid]
		var per_species: Dictionary = {}
		var cx0: int = int(floor(rt.rect.position.x / CHUNK))
		var cz0: int = int(floor(rt.rect.position.y / CHUNK))
		var count: int = int(rt.rect.size.x / CHUNK)
		for cz: int in range(cz0, cz0 + count):
			for cx: int in range(cx0, cx0 + count):
				var key := Vector2i(cx, cz)
				var gone: Dictionary = removed.get(Ids.chunk_key(cx, cz), {})
				var layers: Dictionary = VegetationScatter.scatter_chunk(key, rt, seed_v, height_fn, Callable(), 1)
				for inst: VegetationScatter.Instance in layers.get("tree", []):
					if gone.has(str(inst.index)):
						continue
					if not per_species.has(inst.species):
						per_species[inst.species] = []
					(per_species[inst.species] as Array).append(inst)
		out[rid] = per_species
	return out


func _collect_far() -> void:
	if _far_task < 0 or not WorkerThreadPool.is_task_completed(_far_task):
		return
	WorkerThreadPool.wait_for_task_completion(_far_task)
	_far_task = -1
	for rid: String in _far_result:
		var per_species: Dictionary = _far_result[rid]
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
			_far_mats.append(mat)
			var quad := QuadMesh.new()
			quad.size = Vector2(1.0, 1.0)
			quad.center_offset = Vector3(0, 0.5, 0)
			quad.material = mat
			var insts: Array = per_species[sp_id]
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = quad
			mm.instance_count = insts.size()
			var dims: Vector2 = ImpostorLibrary.size_for(sp)
			for i: int in insts.size():
				var inst: VegetationScatter.Instance = insts[i]
				var b := Basis(Vector3.UP, inst.yaw).scaled(Vector3(dims.x, dims.y, dims.x) * inst.scale)
				mm.set_instance_transform(i, Transform3D(b, inst.pos))
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "Far_%s_%s" % [rid, sp_id]
			mmi.multimesh = mm
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.visibility_range_end = float(Settings.gfx("view_distance", 1400.0))
			_far_root.add_child(mmi)
	_far_result = {}


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
	for layer: String in ["tree", "medium", "ground"]:
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
		p.progression.add_xp(int(Content.config(&"progression").get("xp", {}).get("fell_tree", 10)))
	Events.tree_felled.emit(id, inst.pos)


## Nearest loaded instance of a vegetation kind ("tree", "rock", ...): [chunk, Instance] or [].
func nearest_instance(pos: Vector3, veg_kind: String, max_dist: float = 80.0) -> Array:
	var best: Array = []
	var best_d: float = max_dist
	for key: Vector2i in _data:
		for layer: String in ["tree", "medium", "ground"]:
			for inst: VegetationScatter.Instance in (_data[key] as Dictionary).get(layer, []):
				var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
				if sp.veg_kind != veg_kind or _is_removed(key, inst.index):
					continue
				var d: float = inst.pos.distance_to(pos)
				if d < best_d:
					best_d = d
					best = [key, inst]
	return best


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
			var layers: Dictionary = _data.get(k, {})
			for layer: String in ["medium", "ground"]:
				for inst: VegetationScatter.Instance in layers.get(layer, []):
					var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
					if sp.yields.is_empty() or sp.veg_kind == "tree" or sp.hp > 40.0:
						continue
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
			Game.execute(&"world.pickup_item", {"player": player.state.id, "item": item, "count": n})
	_mark_removed(key, inst, "harvested", sp.regrow_days)
	_rebuild(key)
	Audio.play_3d(&"sfx/foliage_rustle" if sp.veg_kind != "rock" else &"sfx/stone_pickup", inst.pos, {"volume_db": -6.0})


func save_into(session: GameSession) -> void:
	session.world.trees = _removed
