class_name EnemyFoes
extends RefCounted
## The Ashen and the Hollowed fight each other (TD-186, ADR-0048 phase 2). Kept out of enemy.gd,
## which calls it from three one-line hooks. Every SCAN_INTERVAL s a body within SCAN_RANGE of the
## player looks for the nearest living Enemy of a hostile faction (FactionDef.hostile) it can see
## within its sight range; a blow from one does the same. The player stays the priority: the foe is
## only fought once the player hasn't been seen for a second. Blows go to the foe's take_damage
## with the attacker's entity id as source, so its death is nobody's kill (no XP, directive or
## hostility). The foe itself and its timers live on the Enemy (`foe`, `_foe_seen`, `_foe_scan_t`).

const SCAN_INTERVAL: float = 1.0
const SCAN_RANGE: float = 40.0


## Scans for a foe now and then and, while one is engaged, runs the chase and the blows at it
## (movement and animation included). False: the ordinary state machine runs this frame.
static func step(e: Enemy, delta: float, pdist: float) -> bool:
	e._foe_scan_t -= delta
	if e._foe_scan_t <= 0.0:
		e._foe_scan_t = SCAN_INTERVAL
		scan(e, pdist)
	if not fighting(e):
		return false
	var want: Vector3 = _fight(e)
	e._move(want, delta, pdist)
	e._update_anim(want)
	return true


## Whether the foe has the body's attention now: alive and remembered, the body on the hunt, and
## the player not seen this last second.
static func fighting(e: Enemy) -> bool:
	var f: Enemy = e.foe
	if f != null and (not is_instance_valid(f) or not f.is_alive() or e._now() - e._foe_seen > Enemy.MEMORY_SECONDS):
		e.foe = null
	return e.foe != null and e.state in [Enemy.State.CHASE, Enemy.State.ATTACK, Enemy.State.SPIT] \
		and e._now() - e.last_seen_time >= 1.0


## Keeps the foe in view, or picks the nearest hostile body in sight (none past SCAN_RANGE of the
## player, nor while asleep, in the Hum, watching or running: the cost stays small).
static func scan(e: Enemy, pdist: float) -> void:
	if _scout(e):
		return  # a scout watches and reports (ADR-0048): it picks no fights
	var f: Enemy = e.foe
	if f != null and is_instance_valid(f) and f.is_alive() and sees(e, f):
		e._foe_seen = e._now()
		return
	if pdist > SCAN_RANGE or e.director == null \
			or e.state not in [Enemy.State.IDLE, Enemy.State.WANDER, Enemy.State.INVESTIGATE, Enemy.State.CHASE, Enemy.State.ATTACK]:
		return
	var sight: float = e.def.perc("sight_night" if e.is_night() else "sight_day", 15.0)
	var best: Enemy = null
	var best_d: float = INF
	for o: Enemy in e.director.call(&"enemies_in_radius", e.global_position, sight):
		if o == e or not o.is_alive() or not FactionDef.hostile(e.def.faction, o.def.faction):
			continue
		if o.ally != null and not o.ally.open_to(e):
			continue  # TD-312: downed, Ezra is kept only by those already on him
		var d: float = e.global_position.distance_to(o.global_position)
		if d < best_d and sees(e, o):
			best = o
			best_d = d
	if best != null:
		_take(e, best)


static func _take(e: Enemy, o: Enemy) -> void:
	var first: bool = e.foe == null
	e.foe = o
	e._foe_seen = e._now()
	e.target_pos = o.global_position
	if e.state in [Enemy.State.IDLE, Enemy.State.WANDER, Enemy.State.INVESTIGATE]:
		e.break_target = null
		e._set_state(Enemy.State.CHASE)
	if first:
		Audio.play_3d(e._vid(&"voice/zombie_alert", &"voice/hound_bark"), e._mouth(), {"volume_db": -2.0})


## A blow from a body of a hostile faction: that body is the foe now.
static func hurt_by(e: Enemy, info: DamageInfo) -> void:
	var enemies: Variant = e.director.get(&"enemies") if e.director != null else null
	if not (enemies is Dictionary):
		return
	var o: Enemy = (enemies as Dictionary).get(info.source_id) as Enemy
	if o != null and o != e and is_instance_valid(o) and o.is_alive() and FactionDef.hostile(e.def.faction, o.def.faction):
		if _scout(e):
			# Engaged, a scout breaks off and runs rather than trading blows (mid-game audit M11: a
			# scout downed Ezra within seconds); only cornered, with nowhere to run, does it fight.
			if not _cornered(e, o):
				e.tribe.flee_from(o.global_position)
				return
		e.foe = o
		e._foe_seen = e._now()
		e.target_pos = o.global_position


## The foe's chase: in close, a blow (ATTACK); an Ashen throws its spear from its band of range.
static func _fight(e: Enemy) -> Vector3:
	var to: Vector3 = e.foe.global_position
	var d: float = e.global_position.distance_to(to)
	var reach: float = e.def.atk("range", 1.5)
	e.target_pos = to
	match e.state:
		Enemy.State.SPIT:
			e._face(to)
			if not e._spit_done and e._state_t >= 0.55:
				e._spit_done = true
				if e.tribe != null:
					e.tribe.throw_at_body(e.foe)
			elif e._state_t > 1.3:
				e._set_state(Enemy.State.CHASE)
			return Vector3.ZERO
		Enemy.State.ATTACK:
			e._face(to)
			if e._hit_at >= 0.0 and e._state_t >= e._hit_at:
				e._hit_at = -1.0
				hit(e)
			if e._hit_at < 0.0 and e._attack_cd <= 0.0:
				if d > reach + 0.5:
					e._set_state(Enemy.State.CHASE)
				else:
					e._start_attack()
			return Vector3.ZERO
	if e.tribe != null and e.tribe.can_throw(d, e._spit_cd):
		e._start_spit()
		return Vector3.ZERO
	if d <= reach + 0.2:
		e._set_state(Enemy.State.ATTACK)
		return Vector3.ZERO
	return e._move_dir(to) * e._speed(true)


## A blow landing on the foe (in reach, in front, nothing in between): its own attack damage. A
## Hollowed's bite carries no infection that matters to another Enemy.
static func hit(e: Enemy) -> void:
	var f: Enemy = e.foe
	if f == null or not is_instance_valid(f) or not f.is_alive():
		return
	var to: Vector3 = f.global_position - e.global_position
	if to.length() > e.def.atk("range", 1.5) + 0.45:
		return
	var fwd := Vector3(sin(e.rotation.y), 0.0, cos(e.rotation.y))
	if fwd.dot(Vector3(to.x, 0.0, to.z).normalized()) < 0.3 or not sees(e, f):
		return
	var dmg: float = e.def.atk("damage", 10.0) * e.damage_mult * (0.5 if e.severed.has("arm_l") and e.severed.has("arm_r") else 1.0)
	var info := DamageInfo.make(dmg, &"zombie" if e.tribe == null else &"slash", &"zombie" if e.tribe == null else &"ashen", e.entity_id)
	info.hit_pos = f.global_position + Vector3.UP * (1.2 if f.quad.is_empty() else 0.4)
	info.source_pos = e.global_position
	info.direction = to.normalized()
	f.take_damage(info)
	Audio.play_3d(&"sfx/zombie_hit_flesh", info.hit_pos, {"volume_db": -2.0})


## A clear sight line from its eye to another body's chest (Enemies don't block sight).
static func sees(e: Enemy, b: Node3D) -> bool:
	if not e.is_inside_tree() or not b.is_inside_tree():
		return false
	var q := PhysicsRayQueryParameters3D.create(e._eye(), b.global_position + Vector3.UP * 1.2, Enemy.SIGHT_MASK)
	q.exclude = [e.get_rid()]
	return e.get_world_3d().direct_space_state.intersect_ray(q).is_empty()


## An Ashen scout (ADR-0048: scouts observe and report, they don't fight).
static func _scout(e: Enemy) -> bool:
	return e.tribe != null and e.tribe.job == AshenMind.Job.SCOUT


## No way out: its attacker is on it and the way straight away from it is blocked within a few
## metres (a wall, a cliff edge), so running would only turn its back to the blows.
static func _cornered(e: Enemy, o: Enemy) -> bool:
	if e.global_position.distance_to(o.global_position) > 2.5:
		return false
	var away := Vector3(e.global_position.x - o.global_position.x, 0.0, e.global_position.z - o.global_position.z)
	if away.length() < 0.05:
		return false
	var from: Vector3 = e.global_position + Vector3.UP * 0.9
	var q := PhysicsRayQueryParameters3D.create(from, from + away.normalized() * 4.0, Enemy.DETOUR_MASK, [e.get_rid()])
	return not e.get_world_3d().direct_space_state.intersect_ray(q).is_empty()
