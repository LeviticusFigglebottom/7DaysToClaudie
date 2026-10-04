class_name LooseItems
extends Node3D
## Owns loose physics entities (ItemDrop, LogEntity): restores them from WorldState.loose on load,
## writes them back on save, freezes the ones outside terrain-collision range so they never fall
## through unstreamed ground, and rescues any that slipped under the terrain.

const ACTIVE_RADIUS: float = 96.0
const CHECK_INTERVAL: float = 0.75

var world: Node
var _accum: float = 0.0


func setup_world(w: Node) -> void:
	world = w
	var loose: Dictionary = Game.session.world.loose
	for id: Variant in loose.keys():
		var e: Dictionary = loose[id]
		var pos: Vector3 = _vec(e.get("pos", [0, 0, 0]))
		var rot: Quaternion = _quat(e.get("rot", [0, 0, 0, 1]))
		var body: RigidBody3D = null
		match str(e.get("kind", "item")):
			"log":
				body = spawn_log(pos, Basis(rot), StringName(str(e.get("species", ""))), StringName(str(id)))
			_:
				var st: ItemStack = ItemStack.from_dict(e.get("stack", {}))
				if st != null and st.def() != null:
					body = ItemDrop.spawn(self, st, pos, StringName(str(id)))
					body.global_basis = Basis(rot)
		if body != null:
			body.freeze = true


func spawn_log(pos: Vector3, basis: Basis, species_id: StringName = &"", id: StringName = &"") -> LogEntity:
	var l := LogEntity.new()
	l.entity_id = id if id != &"" else Game.session.ids.next("log")
	l.species_id = species_id
	add_child(l)
	l.global_transform = Transform3D(basis.orthonormalized(), pos)
	return l


func spawn_item(stack: ItemStack, pos: Vector3) -> ItemDrop:
	return ItemDrop.spawn(self, stack, pos)


func _physics_process(delta: float) -> void:
	_accum += delta
	if _accum < CHECK_INTERVAL or world == null or world.get(&"player") == null:
		return
	_accum = 0.0
	var center: Vector3 = (world.player as Node3D).global_position
	var terrain: TerrainManager = world.terrain
	for g: StringName in [&"logs", &"item_drops"]:
		for n: Node in get_tree().get_nodes_in_group(g):
			var b: RigidBody3D = n as RigidBody3D
			if b == null:
				continue
			var p: Vector3 = b.global_position
			var near: bool = Vector2(p.x - center.x, p.z - center.z).length() < ACTIVE_RADIUS
			var ground: float = terrain.height_at(p.x, p.z)
			if near and b.freeze and terrain.is_ready_around(p, 0):
				b.freeze = false
			elif not near and not b.freeze:
				b.freeze = true
			if p.y < ground - 1.5:
				b.global_position = Vector3(p.x, ground + 0.6, p.z)
				b.linear_velocity = Vector3.ZERO
				b.angular_velocity = Vector3.ZERO


func save_into(session: GameSession) -> void:
	var out: Dictionary = {}
	for g: StringName in [&"logs", &"item_drops"]:
		for n: Node in get_tree().get_nodes_in_group(g):
			if n.is_queued_for_deletion() or not n.has_method(&"to_dict"):
				continue
			var id: StringName = n.get(&"entity_id")
			if id == &"":
				continue
			out[String(id)] = n.call(&"to_dict")
	session.world.loose = out


static func _vec(a: Variant) -> Vector3:
	var arr: Array = a if a is Array else [0, 0, 0]
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))


static func _quat(a: Variant) -> Quaternion:
	var arr: Array = a if a is Array and (a as Array).size() == 4 else [0, 0, 0, 1]
	return Quaternion(float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])).normalized()
