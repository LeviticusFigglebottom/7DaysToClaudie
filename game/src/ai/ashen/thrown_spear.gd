class_name ThrownSpear
extends Node3D
## An Ashen spear in flight (ADR-0048): a ballistic arc like the Blister's glob, sweeping a ray each
## step against the world, the player and Enemies. A hit is a piercing wound that bleeds (no
## infection: the Ashen are not the Bloom); a miss sticks in the ground a while. Cover stops it, and
## it can be side-stepped at range. It wounds a body of a faction hostile to the thrower's (a Hollow,
## TD-186) and flies on past the thrower and its own kind.

const PLAYER_LAYER: int = 1 << 3
## Enemy.LAYER (the Hollowed and the Ashen).
const ENEMY_LAYER: int = 1 << 4
const WORLD_MASK: int = (1 << 0) | (1 << 1) | (1 << 2)
const G: float = 12.0
const STUCK_SECONDS: float = 20.0

var velocity := Vector3.ZERO
var damage: float = 15.0
var bleed: float = 0.4
var source: StringName = &""
## The thrower's faction (EnemyDef.faction) and what the spear flies past (the thrower, its friends).
var faction: String = "ashen"
var _exclude: Array[RID] = []
var _life: float = 0.0
var _stuck: bool = false


static func launch(parent: Node, from: Vector3, to: Vector3, speed: float, p_damage: float, p_bleed: float,
		p_source: StringName, thrower: Enemy = null) -> ThrownSpear:
	var s := ThrownSpear.new()
	s.damage = p_damage
	s.bleed = p_bleed
	s.source = p_source
	if thrower != null:
		s.faction = thrower.def.faction
		s._exclude.append(thrower.get_rid())
	parent.add_child(s)
	s.global_position = from
	var flat := Vector3(to.x - from.x, 0.0, to.z - from.z)
	var t: float = maxf(0.15, flat.length() / maxf(speed, 1.0))
	s.velocity = flat / t
	s.velocity.y = (to.y - from.y) / t + 0.5 * G * t
	s._build()
	Audio.play_3d(&"sfx/spear_throw", from, {"volume_db": -2.0})
	return s


## A shaft with a stone head, pointing along +Z (turned to face its flight each step).
func _build() -> void:
	var shaft := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.018
	cm.bottom_radius = 0.022
	cm.height = 1.9
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.42, 0.33, 0.24)
	wood.roughness = 0.9
	cm.material = wood
	shaft.mesh = cm
	shaft.rotation = Vector3(PI * 0.5, 0.0, 0.0)
	add_child(shaft)
	var head := MeshInstance3D.new()
	var pm := PrismMesh.new()
	pm.size = Vector3(0.07, 0.16, 0.02)
	var stone := StandardMaterial3D.new()
	stone.albedo_color = Color(0.25, 0.25, 0.27)
	pm.material = stone
	head.mesh = pm
	head.position = Vector3(0, 0, 1.0)
	head.rotation = Vector3(PI * 0.5, 0.0, 0.0)
	add_child(head)
	_face()


func _face() -> void:
	if velocity.length() > 0.1:
		look_at(global_position + velocity, Vector3.UP if absf(velocity.normalized().y) < 0.99 else Vector3.RIGHT)
		rotate_object_local(Vector3.UP, PI)


func _physics_process(delta: float) -> void:
	_life += delta
	if _stuck:
		if _life > STUCK_SECONDS:
			queue_free()
		return
	var from: Vector3 = global_position
	velocity.y -= G * delta
	var to: Vector3 = from + velocity * delta
	var q := PhysicsRayQueryParameters3D.create(from, to + velocity.normalized() * 0.9, WORLD_MASK | PLAYER_LAYER | ENEMY_LAYER)
	q.exclude = _exclude
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	var e: Enemy = hit.get("collider") as Enemy
	if e != null:
		if e.is_alive() and FactionDef.hostile(faction, e.def.faction):
			_hurt_enemy(e, from, hit.get("position", to))
			queue_free()
			return
		# One of its own: the spear flies on past.
		_exclude.append(e.get_rid())
		global_position = to
		_face()
		return
	if not hit.is_empty() or _life > 5.0:
		var p: Player = hit.get("collider") as Player
		if p != null:
			_hurt(p, from)
			queue_free()
			return
		# In the ground or a wall: it stays there, quivering, for a while.
		global_position = (hit.get("position", to) as Vector3) - velocity.normalized() * 0.7
		_stuck = true
		_life = 0.0
		Audio.play_3d(&"sfx/spear_thunk", global_position, {"volume_db": -4.0})
		return
	global_position = to
	_face()


func _hurt(p: Player, from: Vector3) -> void:
	if not p.state.stats.alive:
		return
	# Type "zombie" is the wound path (bleeding, ADR-0029's guard); the cause names who did it.
	var info := DamageInfo.make(damage, &"zombie", &"ashen", source)
	info.hit_pos = p.global_position + Vector3.UP * 1.2
	info.source_pos = from
	info.direction = velocity.normalized()
	info.tool_power = {"bleed": bleed, "infection": 0.0}
	p.take_damage(info)
	Audio.play_3d(&"sfx/blade_hit_flesh", info.hit_pos, {"volume_db": 0.0})


## A spear in a foe of the thrower's faction (TD-186): the cause names the Ashen, the source the
## thrower's entity id, so a kill is never the player's.
func _hurt_enemy(e: Enemy, from: Vector3, at: Vector3) -> void:
	var info := DamageInfo.make(damage, &"pierce", &"ashen", source)
	info.hit_pos = at
	info.source_pos = from
	info.direction = velocity.normalized()
	e.take_damage(info)
