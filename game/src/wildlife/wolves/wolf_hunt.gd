class_name WolfHunt
extends RefCounted
## One wolf's part in its pack (ADR-0055), kept out of enemy.gd, which calls it from two hooks
## (as EnemyFoes): step() runs the wolf whenever the pack is not after the player, and
## ignores_player() keeps the hound brain's senses off the player meanwhile. What it does follows
## its WolfPack's mode: ROAM drifts round the range (and keeps off a player, watching), HUNT stalks
## then runs down the prey and bites it (an Enemy's blow on an Animal: Animal.take_damage, with the
## wolf's id as the source, so the kill is nobody's), FEED eats at the carcass, REST lies by it. When
## the pack has the player, the hound brain hunts them, except at night inside the ring of a lit
## fire or station: the wolves circle outside it and never close (WolfPack.fires).

var e: Enemy
var pack: WolfPack
## Its place round the prey or the kill (radians), and where it is drifting to.
var _angle: float = 0.0
var _goal := Vector3.INF
var _goal_t: float = 0.0
var _bite_cd: float = 0.0
## A one-shot (a howl, a bite) is playing: no locomotion clip over it.
var _hold_t: float = 0.0
var _lying: bool = false


func _init(p_enemy: Enemy, p_pack: WolfPack) -> void:
	e = p_enemy
	pack = p_pack
	_angle = TAU * float(p_enemy.pack_slot) / float(maxi(1, p_pack.members.size())) + 0.4


## The hound brain leaves the player alone (the pack has no reason to take them on).
func ignores_player() -> bool:
	return not pack.engaged


## A stalking wolf: its prey has not seen it yet (WildlifeManager leaves it out of the animals' senses).
func unseen_by_prey() -> bool:
	return not pack.engaged and pack.mode == WolfPack.Mode.HUNT and not pack.rushing


func hold(seconds: float) -> void:
	_hold_t = maxf(_hold_t, seconds)


## This frame of the wolf. True: it moved itself (the Enemy's state machine sits it out); false:
## the hound brain runs (the pack has the player, or the wolf is reeling from a blow).
func step(delta: float, p: Player, dist: float) -> bool:
	if e.state in [Enemy.State.STAGGER, Enemy.State.DEAD]:
		return false
	_bite_cd = maxf(0.0, _bite_cd - delta)
	_hold_t = maxf(0.0, _hold_t - delta)
	var want := Vector3.ZERO
	if pack.engaged:
		var ring: Dictionary = _fire_ring(p)
		if ring.is_empty():
			_stand_up()
			return false
		want = _circle_fire(ring, p)
	else:
		if e.state not in [Enemy.State.IDLE, Enemy.State.WANDER]:
			e._set_state(Enemy.State.IDLE)
		match pack.mode:
			WolfPack.Mode.HUNT:
				want = _hunt()
			WolfPack.Mode.FEED:
				want = _feed()
			WolfPack.Mode.REST:
				want = _rest()
			_:
				want = _roam(p, dist, delta)
		var ring2: Dictionary = _fire_ring(null)
		if not ring2.is_empty():
			want = _out_of(ring2, want)
	e._move(want, delta, dist)
	if _lying:
		e.visual.play(&"idle_sleep_lie", 1.0, 0.5, [&"idle"] as Array[StringName])
	elif pack.mode == WolfPack.Mode.FEED and want == Vector3.ZERO and not pack.engaged and pack.valid_kill() \
			and e._flat_dist((pack.kill as Node3D).global_position) < 2.4:
		e.visual.play(&"eat", 1.0, 0.3, [&"track", &"idle"] as Array[StringName])
	elif _hold_t <= 0.0:
		e._update_anim(want)
	return true


# --- The pack's business -------------------------------------------------------------------------

func _roam(p: Player, dist: float, delta: float) -> Vector3:
	_stand_up()
	var day: Dictionary = WolfPack.section("day")
	var avoid: float = float(day.get("avoid", 40.0))
	if p != null and p.state != null and p.state.stats.alive and dist < avoid * 1.3:
		var away := Vector3(e.global_position.x - p.global_position.x, 0.0, e.global_position.z - p.global_position.z)
		if dist < avoid and away.length() > 0.01:
			# too close: off it goes, glancing back (it never runs from a hunt or a kill)
			_goal = Vector3.INF
			return e._steer_open(away.normalized()) * float(day.get("avoid_speed", 4.5))
		e._face(p.global_position)  # far enough: it stands and watches
		return Vector3.ZERO
	_goal_t -= delta
	if _goal == Vector3.INF or _goal_t <= 0.0 or e._flat_dist(_goal) < 1.5:
		_goal_t = e._fx_rng.randf_range(8.0, 20.0)
		var a: float = e._fx_rng.randf() * TAU
		_goal = pack.den + Vector3(sin(a), 0.0, cos(a)) * e._fx_rng.randf_range(6.0, 26.0)
	if e._flat_dist(_goal) < 1.5:
		return Vector3.ZERO
	return e._move_dir(_goal) * e._speed(false)


func _hunt() -> Vector3:
	_stand_up()
	if not pack.valid_prey():
		return Vector3.ZERO
	var c: Dictionary = WolfPack.section("hunt")
	var prey_pos: Vector3 = (pack.prey as Node3D).global_position
	var d: float = e._flat_dist(prey_pos)
	if pack.rushing:
		if d <= float(c.get("bite", 2.2)):
			if _bite_cd <= 0.0:
				_bite(c)
			return Vector3.ZERO
		return e._steer_open(_flat_dir(prey_pos)) * float(c.get("rush_speed", 13.5))
	# stalking: each to its own bearing round the prey, just outside the rush, nose down
	var spot: Vector3 = prey_pos + Vector3(sin(_angle), 0.0, cos(_angle)) * float(c.get("rush_range", 28.0)) * 0.8
	if e._flat_dist(spot) < 2.0:
		e._face(prey_pos)
		return Vector3.ZERO
	return e._move_dir(spot) * float(c.get("stalk_speed", 2.4))


## A bite on the prey: the hound's attack clip and the wolf's jaws (the Animal bolts, bleeds and dies
## as a shot deer does; its herd runs).
func _bite(c: Dictionary) -> void:
	_bite_cd = float(c.get("bite_every", 0.7))
	var a: Node3D = pack.prey as Node3D
	e._face(a.global_position)
	hold(e.visual.play_once(&"attack_a", 1.2, [&"idle"] as Array[StringName]) * 0.8)
	var info := DamageInfo.make(float(c.get("bite_damage", 45.0)), &"slash", &"wolf", e.entity_id)
	info.hit_pos = a.global_position + Vector3.UP * 0.8
	info.source_pos = e.global_position
	info.direction = _flat_dir(a.global_position)
	a.call(&"take_damage", info)
	Audio.play_3d(&"voice/hound_snarl", e._mouth(), {"volume_db": -2.0})


func _feed() -> Vector3:
	_stand_up()
	if not pack.valid_kill():
		return Vector3.ZERO
	var at: Vector3 = (pack.kill as Node3D).global_position
	var spot: Vector3 = at + Vector3(sin(_angle), 0.0, cos(_angle)) * 1.3
	if e._flat_dist(spot) < 0.8 or e._flat_dist(at) < 1.6:
		e._face(at)
		return Vector3.ZERO
	return e._move_dir(spot) * (e._speed(true) * 0.45 if e._flat_dist(spot) > 6.0 else e._speed(false))


func _rest() -> Vector3:
	var at: Vector3 = pack.guard_point()
	var spot: Vector3 = at + Vector3(sin(_angle * 1.7), 0.0, cos(_angle * 1.7)) * (3.0 + float(e.pack_slot % 3))
	if _lying or e._flat_dist(spot) < 1.0:
		if not _lying:
			_lying = true
			e._face(at)
		return Vector3.ZERO
	return e._move_dir(spot) * e._speed(false)


func _stand_up() -> void:
	if _lying:
		_lying = false
		hold(e.visual.play_once(&"wake_lie", 1.0, [&"idle"] as Array[StringName]))


# --- Fire ------------------------------------------------------------------------------------------

## The fire ring that matters to this wolf now (night only): the one the player stands in when the
## pack has them, or one the wolf itself is inside. {} when none.
func _fire_ring(p: Player) -> Dictionary:
	if pack.fires.is_empty() or not e.is_night():
		return {}
	for f: Dictionary in pack.fires:
		var at: Vector3 = f["pos"]
		var r: float = float(f["r"])
		if p != null and Vector2(p.global_position.x - at.x, p.global_position.z - at.z).length() < r:
			return f
		if e._flat_dist(at) < r:
			return f
	return {}


## Circling the fire the player keeps to: round its ring, facing them, never in.
func _circle_fire(ring: Dictionary, p: Player) -> Vector3:
	var at: Vector3 = ring["pos"]
	var r: float = float(ring["r"]) + 1.5
	var out := Vector3(e.global_position.x - at.x, 0.0, e.global_position.z - at.z)
	var d: float = out.length()
	var radial: Vector3 = out / d if d > 0.01 else Vector3.FORWARD
	var side: Vector3 = radial.cross(Vector3.UP) * (1.0 if e.pack_slot % 2 == 0 else -1.0)
	if e.state in [Enemy.State.ATTACK, Enemy.State.SCREAM]:
		e._set_state(Enemy.State.CHASE)
	var want: Vector3 = (side * 0.8 + radial * clampf((r - d) * 0.8, -1.0, 1.0)).normalized() * e._speed(false) * 1.6
	if p != null:
		e._face(p.global_position)
	return want


## A move bent so it does not carry the wolf further into a fire's ring.
func _out_of(ring: Dictionary, want: Vector3) -> Vector3:
	var at: Vector3 = ring["pos"]
	var out := Vector3(e.global_position.x - at.x, 0.0, e.global_position.z - at.z)
	if out.length() < 0.01:
		return want
	var push: Vector3 = out.normalized() * maxf(want.length(), e._speed(false))
	return push if want.dot(out) <= 0.0 else want


func _flat_dir(to: Vector3) -> Vector3:
	var d := Vector3(to.x - e.global_position.x, 0.0, to.z - e.global_position.z)
	return d.normalized() if d.length() > 0.01 else Vector3.ZERO
