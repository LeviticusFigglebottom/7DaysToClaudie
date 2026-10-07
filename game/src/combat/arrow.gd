class_name Arrow
extends Node3D
## An arrow loosed from a bow (ADR-0057): a ballistic arc (the bow's gravity and the draw's speed),
## sweeping a ray from its tip each physics step like the Ashen spear, always facing along its
## flight. What it strikes it sticks in: the ground, a wall or a tree where it struck, a body in the
## bone nearest the wound (it rides that bone as the body moves and falls). A living Hollow or
## animal takes a piercing wound; anything else only takes the arrow. Each impact is a quiet sound
## in the stimulus field. A stuck arrow can be pulled out and kept (interact) unless it broke (the
## bow's per-arrow break chance); one in a body only once the body is dead. One in a body that goes
## away (rots, despawns) or a wall that comes down drops where it was as a loose item, and one in the
## ground is saved as a loose item (it comes back lying there).
##
## Node frame: the tip at the origin, the shaft back along +Z (so -Z, the node's forward, is the
## flight direction). The model is models/projectiles/<item>.glb in that frame, or a procedural
## shaft, head and fletching before `make assets`.

## World (terrain, structures, props), Enemy.LAYER (Hollowed, Ashen, animals), corpses, structure
## pieces and vegetation: what PlayerEquipment.HIT_MASK strikes, plus remains lying on the ground.
const MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 7) | (1 << 9) | (1 << 12)
## The pickup layer (ItemDrop's): the interaction ray finds a stuck arrow's nock there.
const PICK_LAYER: int = 1 << 6
const MODEL_PATH: String = "res://assets/generated/models/projectiles/%s.glb"
const LENGTH: float = 0.74
## Seconds in flight before an arrow that never struck anything (off the edge of the world) goes.
const MAX_FLIGHT: float = 12.0
## How deep the tip goes in: a body, wood, anything else (m).
const DEPTH_FLESH: float = 0.16
const DEPTH_WOOD: float = 0.07
const DEPTH_HARD: float = 0.04

signal struck(arrow: Arrow, target: Object)

var item_id: StringName = &"arrow_stone"
var velocity := Vector3.ZERO
var gravity: float = 9.8
var damage: float = 30.0
var dismember: float = 0.0
## Chance (0..1) that it breaks on impact and can't be recovered.
var break_chance: float = 0.0
var impact_noise: float = 6.0
## Seconds a stuck arrow stays before it's gone (0 = until picked up).
var stuck_seconds: float = 900.0
## Who loosed it (player id): the wound's source, so a kill is theirs.
var shooter: StringName = &""
var origin := Vector3.ZERO
var entity_id: StringName = &""
var stuck: bool = false
var broken: bool = false
## The body (or wall, tree) it is in; null in the ground. What it rides: a bone of the host's
## skeleton (_bone >= 0), else the host itself.
var host: Node3D = null
var exclude: Array[RID] = []
## Seeded per arrow so a shot's break roll is reproducible in tests.
var rng := RandomNumberGenerator.new()

var _life: float = 0.0
var _skel: Skeleton3D = null
var _bone: int = -1
var _local := Transform3D()
var _pick: Area3D = null


## Looses an arrow of `p_item` from `from` with `vel` (m/s). opts: damage, dismember, break,
## gravity, noise, stuck_seconds, shooter, origin, exclude (Array[RID]), seed.
static func launch(parent: Node, p_item: StringName, from: Vector3, vel: Vector3, opts: Dictionary = {}) -> Arrow:
	var a := Arrow.new()
	a.item_id = p_item
	a.velocity = vel
	a.damage = float(opts.get("damage", 30.0))
	a.dismember = float(opts.get("dismember", 0.0))
	a.break_chance = float(opts.get("break", 0.0))
	a.gravity = float(opts.get("gravity", 9.8))
	a.impact_noise = float(opts.get("noise", 6.0))
	a.stuck_seconds = float(opts.get("stuck_seconds", 900.0))
	a.shooter = StringName(str(opts.get("shooter", "")))
	a.origin = opts.get("origin", from)
	var ex: Array = opts.get("exclude", [])
	for r: Variant in ex:
		if r is RID:
			a.exclude.append(r)
	a.rng.seed = int(opts.get("seed", Time.get_ticks_usec()))
	a.add_child(make_visual(p_item))
	parent.add_child(a)
	a.global_position = from
	a._face()
	return a


## Where an arrow loosed from `from` at `vel` is after `t` seconds in the air (no drag).
static func position_at(from: Vector3, vel: Vector3, g: float, t: float) -> Vector3:
	return from + vel * t + Vector3.DOWN * (0.5 * g * t * t)


## The arrow's model: tip at the origin, shaft along +Z.
static func make_visual(p_item: StringName) -> Node3D:
	var path: String = MODEL_PATH % p_item
	if ResourceLoader.exists(path):
		var ps: PackedScene = load(path) as PackedScene
		if ps != null:
			return ps.instantiate() as Node3D
	return _procedural(p_item)


static func _procedural(p_item: StringName) -> Node3D:
	var root := Node3D.new()
	root.name = "ArrowModel"
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.55, 0.43, 0.3)
	wood.roughness = 0.85
	var shaft := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.0045
	cm.bottom_radius = 0.0045
	cm.height = LENGTH - 0.04
	cm.radial_segments = 6
	cm.rings = 1
	cm.material = wood
	shaft.mesh = cm
	shaft.rotation = Vector3(PI * 0.5, 0.0, 0.0)
	shaft.position = Vector3(0, 0, 0.04 + cm.height * 0.5)
	root.add_child(shaft)
	var head := MeshInstance3D.new()
	var hm := CylinderMesh.new()
	hm.top_radius = 0.0
	hm.bottom_radius = 0.011
	hm.height = 0.045
	hm.radial_segments = 4
	hm.rings = 1
	var hmat := StandardMaterial3D.new()
	hmat.albedo_color = Color(0.86, 0.82, 0.7) if p_item == &"arrow_bone" else Color(0.27, 0.27, 0.29)
	hmat.roughness = 0.6
	hm.material = hmat
	head.mesh = hm
	# The cone's apex is +Y: turn it to -Z, the tip at the origin.
	head.rotation = Vector3(-PI * 0.5, 0.0, 0.0)
	head.position = Vector3(0, 0, hm.height * 0.5)
	head.scale = Vector3(1.0, 1.0, 0.35)
	root.add_child(head)
	var fl := StandardMaterial3D.new()
	fl.albedo_color = Color(0.62, 0.58, 0.48)
	fl.roughness = 0.95
	fl.cull_mode = BaseMaterial3D.CULL_DISABLED
	for k: int in 3:
		var vane := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.0006, 0.013, 0.1)
		bm.material = fl
		vane.mesh = bm
		var ang: float = TAU * k / 3.0
		vane.rotation = Vector3(0, 0, ang)
		vane.position = Vector3(-sin(ang), cos(ang), 0.0) * 0.009 + Vector3(0, 0, LENGTH - 0.07)
		root.add_child(vane)
	return root


func _face() -> void:
	if velocity.length() > 0.1:
		var f: Vector3 = velocity.normalized()
		look_at(global_position + f, Vector3.UP if absf(f.y) < 0.99 else Vector3.RIGHT)


func _physics_process(delta: float) -> void:
	_life += delta
	if stuck:
		_ride()
		if stuck_seconds > 0.0 and _life > stuck_seconds:
			queue_free()
		return
	step(delta)


## One physics step of flight: gravity, then a ray from the tip to where it will be.
func step(delta: float) -> void:
	if stuck or not is_inside_tree():
		return
	var from: Vector3 = global_position
	velocity.y -= gravity * delta
	var to: Vector3 = from + velocity * delta
	var q := PhysicsRayQueryParameters3D.create(from, to, MASK)
	q.exclude = exclude
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	if not hit.is_empty():
		_impact(hit)
		return
	if _life > MAX_FLIGHT:
		queue_free()
		return
	global_position = to
	_face()


func _impact(hit: Dictionary) -> void:
	var collider: Object = hit.get("collider")
	var at: Vector3 = hit["position"]
	var dir: Vector3 = velocity.normalized()
	var receiver: Object = PlayerEquipment._damage_receiver(collider)
	var flesh: bool = receiver is Enemy or receiver is Animal
	if flesh and alive(receiver):
		var info := DamageInfo.make(damage, &"pierce", &"arrow", shooter)
		info.hit_pos = at
		info.source_pos = origin
		info.direction = dir
		info.dismember = dismember
		info.stagger = 0.35
		info.collider = collider
		receiver.call(&"take_damage", info)
	var surf: StringName = ViewModelHolds.surface_kind(collider, receiver)
	var depth: float = DEPTH_FLESH if flesh else (DEPTH_WOOD if surf in [&"wood", &"bark"] else DEPTH_HARD)
	Audio.play_3d(&"sfx/blade_hit_flesh" if flesh else &"sfx/spear_thunk", at, {"volume_db": -8.0 if flesh else -10.0, "pitch": 1.5})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(at, impact_noise, &"impact", shooter)
	struck.emit(self, receiver if receiver != null else collider)
	global_position = at + dir * depth
	_face()
	velocity = Vector3.ZERO
	stuck = true
	_life = 0.0
	broken = rng.randf() < break_chance
	if broken:
		# The shaft snaps: a splinter burst, and nothing to pull out.
		if get_parent() != null:
			FxLibrary.burst(get_parent(), "wood", at - dir * 0.05, -dir, 0.3)
		queue_free()
		return
	var host_node: Node3D = (receiver as Node3D) if receiver is Node3D else (collider as Node3D)
	_stick_in(host_node, at)
	_make_pickup()


## Rides the bone nearest the wound (or the host itself) from now on. Terrain chunks are hosts too
## (they stream out); a host that goes away drops the arrow as a loose item.
func _stick_in(h: Node3D, at: Vector3) -> void:
	host = h
	if host == null:
		_save_as_loose()
		return
	_skel = null
	_bone = -1
	var skels: Array[Node] = host.find_children("*", "Skeleton3D", true, false)
	if not skels.is_empty() and (host is Enemy or host is Animal):
		_skel = skels[0] as Skeleton3D
		var best: float = INF
		for b: int in _skel.get_bone_count():
			var p: Vector3 = _skel.global_transform * _skel.get_bone_global_pose(b).origin
			var d: float = p.distance_squared_to(at)
			if d < best:
				best = d
				_bone = b
	_local = _anchor().affine_inverse() * global_transform
	if not (host is Enemy or host is Animal):
		_save_as_loose()


func _anchor() -> Transform3D:
	if _skel != null and _bone >= 0 and is_instance_valid(_skel):
		return _skel.global_transform * _skel.get_bone_global_pose(_bone)
	return host.global_transform


func _ride() -> void:
	if host == null:
		return
	if not is_instance_valid(host) or not host.is_inside_tree() or host.is_queued_for_deletion():
		_fall_loose()
		return
	if host is Enemy or host is Animal:
		global_transform = _anchor() * _local


## Its host is gone: it falls where it was as an ordinary loose item.
func _fall_loose() -> void:
	host = null
	var parent: Node = get_parent()
	if parent != null and not broken and Game.session != null:
		ItemDrop.spawn(parent, ItemStack.make(item_id, 1), global_position + Vector3.UP * 0.05)
	queue_free()


## In the ground, a wall or a tree it is saved with the loose items (and comes back lying there).
func _save_as_loose() -> void:
	if entity_id == &"":
		entity_id = Game.session.ids.next("i") if Game.session != null else StringName("i:arrow:%d" % get_instance_id())
	add_to_group(&"item_drops")


func _make_pickup() -> void:
	_pick = Area3D.new()
	_pick.name = "Pickup"
	_pick.collision_layer = PICK_LAYER
	_pick.collision_mask = 0
	_pick.monitoring = false
	var cs := CollisionShape3D.new()
	var sh := SphereShape3D.new()
	sh.radius = 0.1
	cs.shape = sh
	_pick.add_child(cs)
	# Round the shaft's exposed end (the nock), where a hand would take it.
	_pick.position = Vector3(0, 0, LENGTH * 0.75)
	add_child(_pick)


## Whether a body (Enemy or Animal) is still alive.
static func alive(body: Object) -> bool:
	if body is Enemy:
		return (body as Enemy).is_alive()
	if body is Animal:
		return (body as Animal).state != Animal.State.DEAD
	return false


## Stuck, whole, and not in something still alive.
func recoverable() -> bool:
	return stuck and not broken and not is_queued_for_deletion() and not (is_instance_valid(host) and alive(host))


func interact_text(_player: Player) -> String:
	if not recoverable():
		return ""
	var def: ItemDef = Content.item(item_id)
	var name_s: String = def.display_name if def != null else "arrow"
	return ("Pull out %s" if host is Enemy or host is Animal else "Pick up %s") % name_s


func interact(player: Player) -> void:
	if not recoverable() or player == null or player.state == null:
		return
	var res: Dictionary = Game.execute(&"world.pickup_stack", {"player": player.state.id, "stack": ItemStack.make(item_id, 1)})
	if bool(res.get("ok", false)):
		queue_free()


func to_dict() -> Dictionary:
	var q: Quaternion = global_transform.basis.get_rotation_quaternion()
	var p: Vector3 = global_position
	return {"kind": "item", "stack": ItemStack.make(item_id, 1).to_dict(), "pos": [p.x, p.y, p.z], "rot": [q.x, q.y, q.z, q.w]}
