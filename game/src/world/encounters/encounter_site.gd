class_name EncounterSite
extends Node3D
## One built "scene" encounter (ADR-0054): its props on the ground (a container prop is a
## LootProp keyed "enc:<cell>:<prop key>"), its loose items and note as pickups, and the plan of
## its sleepers, which Encounters spawns when the player comes near. Everything it shows is drawn
## from the site's seed in a fixed order, so every visit and every machine builds the same scene;
## what the player changed lives in WorldState (`encounters[id]`, `containers`).
##
## Acts as the `poi` of its LootProps and Pickups (they report searches and pickups to it).

## The planner's site: {id, kind, def, pos, yaw, region, seed, trunk}.
var site: Dictionary = {}
var def: EncounterDef
var site_id: StringName = &""
## [{sid, enemy, pos: Vector3, yaw, pose}] (spawned by Encounters when the player is near).
var sleeper_plan: Array[Dictionary] = []
## sid -> Enemy while spawned.
var sleepers: Dictionary = {}
var sleepers_spawned: bool = false
## Container ids of its loot props (debug overlay, tests).
var container_ids: Array[StringName] = []
## Pickup ids still lying here.
var pickup_ids: Array[String] = []
## (x, z) -> ground height (TerrainManager.height_at); tests may inject one.
var height_fn: Callable


## Builds the scene under this node (the node is placed at the site by the caller first).
func build(p_site: Dictionary, p_def: EncounterDef, p_height: Callable) -> void:
	site = p_site
	def = p_def
	site_id = site["id"]
	height_fn = p_height
	name = String(site_id).replace(":", "_")
	var pos: Vector3 = site["pos"]
	transform = Transform3D(Basis(Vector3.UP, float(site["yaw"])), pos)
	var st: Dictionary = Encounters.state_of(site_id)
	var taken: Array = st.get("taken", [])
	var rng := RandomNumberGenerator.new()
	rng.seed = int(site["seed"])
	# Anchored on a tree: prop positions are measured from the trunk's surface (+Z, away from it).
	var trunk: float = float(site.get("trunk", 0.0))
	for i: int in def.props.size():
		var p: Dictionary = def.props[i]
		var roll: float = rng.randf()
		var pick: float = rng.randf()
		if roll >= float(p.get("chance", 1.0)):
			continue
		var ids: PackedStringArray = EncounterDef.entry_props(p)
		var pid: String = ids[mini(int(pick * ids.size()), ids.size() - 1)]
		var pd: PropDef = Content.get_def(&"prop", StringName(pid)) as PropDef
		if pd == null:
			continue
		var key: String = str(p.get("id", str(i)))
		_add_prop(pd, p, key, trunk)
	for j: int in def.loose.size():
		var l: Dictionary = def.loose[j]
		var roll2: float = rng.randf()
		var r_count: float = rng.randf()
		var lid: String = str(l.get("id", "l%d" % j))
		if roll2 >= float(l.get("chance", 1.0)) or taken.has(lid):
			continue
		var cnt: Vector2 = _range(l.get("count", 1))
		_add_pickup(lid, StringName(str(l["item"])), int(round(lerpf(cnt.x, cnt.y, r_count))), l, trunk)
	var n_roll: float = rng.randf()
	var n_pick: float = rng.randf()
	var items: Array = def.notes.get("items", [])
	if not items.is_empty() and n_roll < float(def.notes.get("chance", 1.0)) and not taken.has("note"):
		_add_pickup("note", StringName(str(items[mini(int(n_pick * items.size()), items.size() - 1)])), 1, def.notes, trunk)
	_plan_sleepers(rng, st.get("dead", []))


static func _range(v: Variant) -> Vector2:
	if v is Array and (v as Array).size() == 2:
		return Vector2(float(v[0]), float(v[1]))
	return Vector2(float(v), float(v))


## Site-local (x, z) of an entry, on the ground: a Transform3D in this node's frame.
func _local_xf(e: Dictionary, trunk: float, rot_deg: float) -> Transform3D:
	var at: Array = e.get("pos", [0, 0])
	var local := Vector3(float(at[0]), 0.0, float(at[1]) + (trunk if trunk > 0.0 else 0.0))
	var world: Vector3 = transform * local
	var ground: float = float(height_fn.call(world.x, world.z)) if height_fn.is_valid() else transform.origin.y
	local.y = ground - transform.origin.y + float(e.get("y", 0.0))
	return Transform3D(Basis(Vector3.UP, deg_to_rad(rot_deg)), local)


func _add_prop(pd: PropDef, p: Dictionary, key: String, trunk: float) -> void:
	var xf: Transform3D = _local_xf(p, trunk, float(p.get("rot", 0.0)))
	var model: String = pd.model_for(str(p.get("variant", "worn")))
	var cont: StringName = StringName(str(p.get("container", pd.container)))
	var cdef: ContainerDef = Content.get_def(&"container", cont) as ContainerDef if cont != &"" else null
	var mi := MeshInstance3D.new()
	mi.mesh = _mesh_for(model, pd)
	if cdef != null:
		var lp := PoiPieces.LootProp.new()
		lp.poi = self
		lp.prop = pd
		lp.cdef = cdef
		lp.container_id = StringName("%s:%s" % [site_id, key])
		lp.prop_key = key
		lp.tier = def.tier
		lp.transform = xf
		lp.add_child(mi)
		_box(lp, pd)
		add_child(lp)
		container_ids.append(lp.container_id)
		return
	mi.transform = xf
	add_child(mi)
	if pd.collision != "none":
		var body := StaticBody3D.new()
		body.collision_layer = 1
		body.collision_mask = 0
		body.transform = xf
		body.set_meta(&"prop", str(pd.id))
		_box(body, pd)
		add_child(body)


## The generated model, else a box the prop's size standing on its base (the stand-in).
static func _mesh_for(model: String, pd: PropDef) -> Mesh:
	var m: Mesh = ModelLibrary.generated_mesh(model)
	if m != null:
		return m
	var box := BoxMesh.new()
	box.size = pd.size.max(Vector3(0.05, 0.05, 0.05))
	var arr := ArrayMesh.new()
	var a: Array = box.get_mesh_arrays()
	var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var c: Vector3 = pd.box_centre()
	for i: int in verts.size():
		verts[i] += c
	a[Mesh.ARRAY_VERTEX] = verts
	arr.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, a)
	return arr


static func _box(body: CollisionObject3D, pd: PropDef) -> void:
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = pd.size.max(Vector3(0.2, 0.2, 0.2))
	cs.shape = b
	cs.position = pd.box_centre()
	body.add_child(cs)


func _add_pickup(pid: String, item: StringName, count: int, e: Dictionary, trunk: float) -> void:
	if Content.item(item) == null or count <= 0:
		return
	var pk := PoiPieces.Pickup.new()
	pk.poi = self
	pk.pickup_id = pid
	pk.item = item
	pk.count = count
	pk.transform = _local_xf(e, trunk, 0.0)
	pk.name = "Pickup_%s" % pid
	add_child(pk)
	pickup_ids.append(pid)


## Who sleeps here (drawn whether or not they are dead, so the draws never shift).
func _plan_sleepers(rng: RandomNumberGenerator, dead: Array) -> void:
	var sl: Dictionary = def.sleepers
	var chance: float = rng.randf()
	var r_count: float = rng.randf()
	if sl.is_empty() or chance >= float(sl.get("chance", 1.0)):
		return
	var cnt: Vector2 = _range(sl.get("count", 1))
	var n: int = int(round(lerpf(cnt.x, cnt.y, r_count)))
	var enemies: Dictionary = sl.get("enemies", {})
	var keys: Array = enemies.keys()
	keys.sort()
	var total: float = 0.0
	for k: Variant in keys:
		total += float(enemies[k])
	var poses: Array = sl.get("poses", ["lie"])
	var ring: Vector2 = _range(sl.get("ring", [1.5, 5.0]))
	for i: int in n:
		var r_enemy: float = rng.randf() * total
		var r_pose: float = rng.randf()
		var r_ang: float = rng.randf()
		var r_dist: float = rng.randf()
		var r_yaw: float = rng.randf()
		var sid: String = "s%d" % i
		if dead.has(sid):
			continue
		var enemy: String = str(keys.back())
		var acc: float = 0.0
		for k2: Variant in keys:
			acc += float(enemies[k2])
			if r_enemy <= acc:
				enemy = str(k2)
				break
		var a: float = r_ang * TAU
		var d: float = lerpf(ring.x, ring.y, r_dist)
		var world: Vector3 = transform * Vector3(cos(a) * d, 0.0, sin(a) * d)
		world.y = float(height_fn.call(world.x, world.z)) if height_fn.is_valid() else world.y
		sleeper_plan.append({"sid": sid, "enemy": StringName(enemy), "pos": world + Vector3.UP * 0.05, "yaw": r_yaw * TAU,
			"pose": str(poses[mini(int(r_pose * poses.size()), poses.size() - 1)])})


# --- The poi interface of LootProp and Pickup -------------------------------------------------

func on_container_searched(_prop_key: String, _pos: Vector3) -> void:
	Encounters.state_of(site_id, true)["visited"] = true


func set_piece_state(piece_id: String, state: String) -> void:
	if state != "broken":
		return
	var st: Dictionary = Encounters.state_of(site_id, true)
	var taken: Array = st.get("taken", [])
	if not taken.has(piece_id):
		taken.append(piece_id)
	st["taken"] = taken
	pickup_ids.erase(piece_id)


func on_pickup_taken(_piece_id: String, _pos: Vector3) -> void:
	pass
