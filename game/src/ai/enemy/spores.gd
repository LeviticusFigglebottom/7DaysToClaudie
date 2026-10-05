class_name Spores
extends RefCounted
## Bloom spore attacks: the Blister's arcing glob, the lingering puddle it leaves, and the
## cloud a Blister or a Bloomed Hollowed bursts into when it dies. Damage carries Bloom
## infection (DamageInfo type "spores"), so a spore fight is also a race against the infection
## meter.

const PLAYER_LAYER: int = 1 << 3
const WORLD_MASK: int = (1 << 0) | (1 << 1) | (1 << 2)
const COLOR := Color(0.78, 0.82, 0.46)


static func _material(alpha: float, glow: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(COLOR.r, COLOR.g, COLOR.b, alpha)
	m.emission_enabled = true
	m.emission = COLOR * glow
	m.roughness = 0.4
	m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	return m


static func _hurt_player(p: Player, amount: float, infection: float, source: StringName, from: Vector3) -> void:
	if p == null or not p.state.stats.alive:
		return
	var info := DamageInfo.make(amount, &"spores", &"spores", source)
	info.hit_pos = p.global_position + Vector3.UP * 1.2
	info.source_pos = from
	info.direction = (p.global_position - from).normalized()
	info.tool_power = {"infection": infection}
	p.take_damage(info)


## Lobs a glob from `from` toward `to` along a ballistic arc (horizontal speed `speed` m/s).
static func spit(parent: Node, from: Vector3, to: Vector3, params: Dictionary, source: StringName) -> void:
	var glob := Glob.new()
	glob.params = params
	glob.source = source
	parent.add_child(glob)
	glob.launch(from, to, float(params.get("speed", 13.0)))


## A one-off cloud: damage and infection falling off with distance, plus a puff of spores.
static func burst(parent: Node, pos: Vector3, params: Dictionary, source: StringName) -> void:
	var radius: float = float(params.get("radius", 3.0))
	var p: Player = Game.world.player if Game.world != null else null
	if p != null:
		var d: float = p.global_position.distance_to(pos)
		if d < radius:
			var k: float = 1.0 - d / radius
			_hurt_player(p, float(params.get("damage", 10.0)) * k, float(params.get("infection", 10.0)) * k, source, pos)
	var puff := Puff.new()
	puff.radius = radius
	parent.add_child(puff)
	puff.global_position = pos + Vector3.UP * 0.6
	Audio.play_3d(&"sfx/zombie_hit_flesh", pos + Vector3.UP, {"volume_db": 2.0, "pitch": 0.55})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(pos, 14.0, &"burst", source)


## The thrown glob: integrates its own arc and sweeps a ray each step against world + player.
class Glob:
	extends Node3D
	var params: Dictionary = {}
	var source: StringName = &""
	var velocity := Vector3.ZERO
	var _life: float = 0.0
	const G: float = 14.0

	func launch(from: Vector3, to: Vector3, speed: float) -> void:
		global_position = from
		var flat := Vector3(to.x - from.x, 0.0, to.z - from.z)
		var t: float = maxf(0.2, flat.length() / speed)
		velocity = flat / t
		velocity.y = (to.y - from.y) / t + 0.5 * G * t
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.12
		sm.height = 0.24
		sm.material = Spores._material(0.85, 0.6)
		mi.mesh = sm
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		Audio.play_3d(&"voice/zombie_attack", from, {"volume_db": 0.0, "pitch": 1.45})

	func _physics_process(delta: float) -> void:
		_life += delta
		var from: Vector3 = global_position
		velocity.y -= G * delta
		var to: Vector3 = from + velocity * delta
		var q := PhysicsRayQueryParameters3D.create(from, to, Spores.WORLD_MASK | Spores.PLAYER_LAYER)
		var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
		if not hit.is_empty() or _life > 4.0:
			var at: Vector3 = hit.get("position", to)
			var p: Player = hit.get("collider") as Player
			if p != null:
				Spores._hurt_player(p, float(params.get("damage", 6.0)), float(params.get("infection", 6.0)), source, from)
			_splash(at)
			queue_free()
			return
		global_position = to

	func _splash(at: Vector3) -> void:
		var ground: float = Game.world.height_at(at.x, at.z) if Game.world != null else at.y
		var puddle := Puddle.new()
		puddle.params = params
		puddle.source = source
		get_parent().add_child(puddle)
		puddle.global_position = Vector3(at.x, maxf(ground, at.y - 0.5) + 0.03, at.z)
		Audio.play_3d(&"sfx/zombie_hit_flesh", at, {"volume_db": -2.0, "pitch": 1.3})


## Lingering spore pool: hurts and infects whoever stands in it, then fades.
class Puddle:
	extends Area3D
	var params: Dictionary = {}
	var source: StringName = &""
	var _t: float = 0.0
	var _tick: float = 0.0
	var _disk: MeshInstance3D

	func _ready() -> void:
		collision_layer = 0
		collision_mask = Spores.PLAYER_LAYER
		var r: float = float(params.get("puddle_radius", 2.0))
		var cs := CollisionShape3D.new()
		var cyl := CylinderShape3D.new()
		cyl.radius = r
		cyl.height = 1.2
		cs.shape = cyl
		cs.position = Vector3.UP * 0.6
		add_child(cs)
		_disk = MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = r
		cm.bottom_radius = r
		cm.height = 0.03
		cm.material = Spores._material(0.55, 0.35)
		_disk.mesh = cm
		_disk.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(_disk)

	func _physics_process(delta: float) -> void:
		_t += delta
		_tick += delta
		var life: float = float(params.get("puddle_seconds", 8.0))
		if _t > life:
			queue_free()
			return
		_disk.scale = Vector3.ONE * (1.0 - 0.4 * _t / life)
		if _tick >= 0.5:
			_tick = 0.0
			for b: Node3D in get_overlapping_bodies():
				if b is Player:
					Spores._hurt_player(b as Player, float(params.get("puddle_dps", 4.0)) * 0.5, float(params.get("puddle_infection", 2.0)) * 0.5, source, global_position)


## Expanding, fading spore cloud (visual only).
class Puff:
	extends MeshInstance3D
	var radius: float = 3.0
	var _t: float = 0.0

	func _ready() -> void:
		var sm := SphereMesh.new()
		sm.radius = 0.5
		sm.height = 1.0
		mesh = sm
		material_override = Spores._material(0.5, 0.4)
		cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	func _process(delta: float) -> void:
		_t += delta
		var k: float = clampf(_t / 1.6, 0.0, 1.0)
		scale = Vector3.ONE * lerpf(0.6, radius * 1.6, ease(k, 0.4))
		(material_override as StandardMaterial3D).albedo_color.a = 0.5 * (1.0 - k)
		if k >= 1.0:
			queue_free()
