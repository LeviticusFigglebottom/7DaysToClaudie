class_name Enemy
extends CharacterBody3D
## A Hollowed: body, senses and brain in one data-driven node (EnemyDef archetypes walker /
## feral / screamer / crawler). The brain is a small state machine fed by the shared stimulus
## fields (Stimuli: sound events, scent grid, light) — it never reads the player's position
## unless it can actually see, hear or smell them (ADR-0012).
##
## SLEEP sleepers lie/sit/stand dormant in POIs; noise, light and a close careless player build
## `awareness` until they wake. A *held* sleeper (a POI ambush group or guardian, ADR-0018)
## ignores all of that: only gunfire, explosions or an alarm close by, a blow, or its group's
## trigger (`ambush()`) wakes it. WANDER/IDLE drift; INVESTIGATE walks to a sound or follows scent;
## CHASE runs at what it saw; ATTACK/BREAK hit the player or whatever wall is in the way; HORDE
## follows the Hum flow field toward the base; SCREAM (Keener) summons the neighbourhood.
## Specials (EnemyDef.behavior): SPIT (Blister) lobs spore globs from range, CHARGE (Rammer)
## barrels at you or through a wall, `armor` (Husk) shrugs off everything but headshots, and
## `death_burst` leaves a spore cloud. Infected tiers (Seeded, Bloomed) scale stats, regenerate
## and glow (InfectedTiers, ADR-0014). Hollowed hounds (archetype `hound`, ADR-0034) run on four
## legs in a low body: a pack rallies to the first one that sees you (it howls), spreads round you
## before it closes, bites and breaks off, tracks you by scent when it loses sight of you, and
## keeps clear of a flame held up to it.

enum State { SLEEP, WAKING, IDLE, WANDER, INVESTIGATE, CHASE, ATTACK, BREAK, SCREAM, STAGGER, HORDE, DEAD, SPIT, CHARGE }

const LAYER: int = 1 << 4
const CORPSE_LAYER: int = 1 << 7
const MOVE_MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 12)
const SIGHT_MASK: int = (1 << 0) | (1 << 1) | (1 << 14)
const GRAVITY: float = 18.0
const PERCEPTION_INTERVAL: float = 0.25
const KINEMATIC_BEYOND: float = 110.0
const MEMORY_SECONDS: float = 9.0

signal died(enemy: Enemy)

var entity_id: StringName = &""
var def: EnemyDef
var director: Node = null
var visual: EnemyVisual
var agent: NavigationAgent3D
var state: State = State.IDLE
var health: float = 100.0
var limb_hp: Dictionary = {}
var severed: Dictionary = {}
var crawling: bool = false
var awareness: float = 0.0
var home := Vector3.ZERO
var target_pos := Vector3.ZERO
var last_seen_time: float = -100.0
var poi_id: StringName = &""
var sleeper_id: StringName = &""
var sleep_pose: String = "stand"
## POI ambush group this sleeper belongs to ("" = none) and whether it is still held dormant
## until a trigger of that group fires (ADR-0018). Guardians spawn one infected tier up.
var group: StringName = &""
var held: bool = false
var guardian: bool = false
## A sleeper on a seat or bed (ADR-0022, SleeperAnchors), world space: {kind ("seat" / "bed"),
## lean ("back" / "forward" / "low"), point (seat or mattress top under the pelvis), floor (y under the
## seat), yaw (its facing), exit (floor spot it stands on once up), exit_yaw}. While set, the body
## keeps out of physics: it sits or lies posed on the furniture and, once woken, rises off it along
## a scripted path to the exit (rise_seconds) before it hunts. Empty on the floor and once up.
var perch: Dictionary = {}
var horde_sector: int = -1
var horde: bool = false
var break_target: Node3D = null
var last_hit_cause: StringName = &""
var killer: Dictionary = {}
var inventory: Inventory = null

var _rng := RandomNumberGenerator.new()
var _perc_t: float = 0.0
var _state_t: float = 0.0
var _attack_cd: float = 0.0
var _scream_cd: float = 0.0
var _stagger_t: float = 0.0
var _hit_at: float = -1.0
var _heard_seq: int = 0
var _stuck_t: float = 0.0
## Navigation: the goal the agent's current path leads to, and time until a forced re-path.
var _nav_goal := Vector3.INF
var _nav_t: float = 0.0
## Beyond collision range the body glides on the heightfield; no path queries out there.
var _far: bool = false
## No new stagger until this runs out (a fast weapon could otherwise stun-lock).
var _stagger_lock: float = 0.0
## After the Hum: seconds until this survivor roots into the soil (despawns) when unobserved.
var _root_t: float = -1.0
var _resume_state: State = State.IDLE
var _yaw_target: float = 0.0
var _shape: CollisionShape3D
var _corpse_t: float = 0.0
var _looted: bool = false
var _voice_t: float = 0.0
var _step_t: float = 0.0
## World-setting and tier multipliers, fixed at spawn (GameRules + infected tier).
var max_health: float = 100.0
var damage_mult: float = 1.0
var structure_mult: float = 1.0
var _speed_scales: Dictionary = {"day": 1.0, "night": 1.0, "hum": 1.0}
var _wake_factor: float = 1.0
## Infected tier (normal / seeded / bloomed) and what it adds.
var tier: StringName = &"normal"
var xp_mult: float = 1.0
var _regen: float = 0.0
var _glow: float = 0.0
var _tier_burst: Dictionary = {}
var _spit_cd: float = 0.0
var _spit_done: bool = false
var _charge_cd: float = 0.0
var _charge_dir := Vector3.ZERO
var _charge_hit: bool = false
## Where a perched sleeper sleeps (its transform when woken) and where the rise ends.
var _perch_from := Transform3D.IDENTITY
## The standing capsule (sleep poses and crawling reshape it; waking restores it).
var _cap_radius: float = 0.3
var _cap_height: float = 1.75
## A POI sleeper spawned already awake (its building was roused while nobody was near, ADR-0022):
## where it heads first. INF = none.
var _wake_at := Vector3.INF
## Hollowed hounds (ADR-0034): the low four-legged body (EnemyDef behavior.quadruped; empty for
## everything that walks upright), the pack it hunts with (Array of Enemy, itself included, wired
## by AIDirector.spawn_pack) and its place in the pack's spread round the quarry.
var quad: Dictionary = {}
var pack: Array = []
var pack_slot: int = 0
var _retreat_t: float = 0.0
var _howl_cd: float = 0.0
## Reached its flanking spot this approach: now it goes straight in.
var _flanked: bool = false


func setup(p_id: StringName, p_def: EnemyDef, p_director: Node, opts: Dictionary = {}) -> void:
	entity_id = p_id
	def = p_def
	director = p_director
	quad = def.beh("quadruped", {})
	_rng.seed = Ids.hash64("enemy:" + String(p_id))
	var rules: GameRules = GameRules.current()
	max_health = def.health * rules.num("enemy_health")
	health = max_health
	damage_mult = rules.num("enemy_damage")
	structure_mult = rules.num("structure_damage")
	for period: String in _speed_scales:
		_speed_scales[period] = rules.speed_scale(period)
	_wake_factor = rules.sleeper_wake_factor()
	tier = StringName(str(opts.get("tier", "normal")))
	var t: Dictionary = InfectedTiers.tier(tier)
	max_health *= float(t.get("hp", 1.0))
	health = max_health
	damage_mult *= float(t.get("damage", 1.0))
	structure_mult *= float(t.get("structure", 1.0))
	for period: String in _speed_scales:
		_speed_scales[period] = float(_speed_scales[period]) * float(t.get("speed", 1.0))
	xp_mult = float(t.get("xp", 1.0))
	_regen = float(t.get("regen", 0.0))
	_glow = float(t.get("glow", 0.0))
	_tier_burst = t.get("death_burst", {})
	_spit_cd = _rng.randf_range(1.0, 3.0)
	_charge_cd = _rng.randf_range(2.0, 4.0)
	# Limbs scale with the body (difficulty, infected tier): a Bloomed head is not a Hollow's.
	var hp_scale: float = max_health / maxf(1.0, def.health)
	limb_hp = {}
	for k: Variant in def.limbs.keys():
		limb_hp[k] = float(def.limbs[k]) * hp_scale
	poi_id = StringName(str(opts.get("poi", "")))
	sleeper_id = StringName(str(opts.get("sleeper", "")))
	sleep_pose = str(opts.get("pose", "stand"))
	group = StringName(str(opts.get("group", "")))
	held = bool(opts.get("held", false))
	guardian = bool(opts.get("guardian", false))
	horde_sector = int(opts.get("horde_sector", -1))
	horde = horde_sector >= 0
	crawling = def.archetype == "crawler"
	perch = opts.get("perch", {})
	if opts.get("awake_at", null) is Vector3:
		# A roused POI sleeper: up and about by its post, making for where the building was woken.
		_wake_at = opts["awake_at"]
		perch = {}
		held = false
		state = State.IDLE
	elif bool(opts.get("sleeper", "") != ""):
		state = State.SLEEP
	elif horde:
		state = State.HORDE
	else:
		state = State.IDLE


func _ready() -> void:
	collision_layer = LAYER
	collision_mask = MOVE_MASK
	floor_max_angle = deg_to_rad(50.0)
	floor_snap_length = 0.4
	add_to_group(&"enemies")
	visual = EnemyVisual.new()
	visual.name = "Visual"
	add_child(visual)
	var body: String = def.bodies[_rng.randi() % def.bodies.size()] if not def.bodies.is_empty() else ""
	var bs: Array = def.beh("body_scale", [1.0, 1.0, 1.0])
	var size: float = _rng.randf_range(def.scale_range.x, def.scale_range.y)
	visual.build(body, size, Vector3(float(bs[0]), float(bs[1]), float(bs[2])))
	# The capsule is also what weapons hit: as tall as this body really is (a tall Hollow's head
	# stuck out of a fixed 1.75 m capsule), lying down for crawlers.
	_shape = CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = float(def.beh("radius", 0.3))
	cap.height = maxf(1.75, float(def.beh("height", 1.75))) * size * float(bs[1])
	if not quad.is_empty():
		# A hound: a capsule lying along its body on the ground, nose to tail.
		cap.radius = float(quad.get("radius", 0.3)) * size
		cap.height = maxf(float(quad.get("length", 1.2)) * size, cap.radius * 2.0 + 0.01)
	_cap_radius = cap.radius
	_cap_height = cap.height
	_shape.shape = cap
	add_child(_shape)
	_fit_shape()
	if _glow > 0.0:
		visual.set_bloom(_glow)
	agent = NavigationAgent3D.new()
	agent.path_desired_distance = 0.8
	agent.target_desired_distance = 1.0
	agent.path_max_distance = 3.0
	agent.radius = maxf(0.35, cap.radius)
	agent.height = 1.7 if quad.is_empty() else 0.8
	add_child(agent)
	if not perch.is_empty():
		# On its seat or bed, posed for this body's size (the animation offsets scale with it).
		var place: Dictionary = SleeperAnchors.body_origin(perch, visual.scale)
		global_position = place["origin"]
		rotation.y = float(place["yaw"])
		_perch_from = global_transform
		velocity = Vector3.ZERO
	home = global_position if perch.is_empty() else (perch["exit"] as Vector3)
	target_pos = global_position
	_yaw_target = rotation.y
	_perc_t = _rng.randf() * PERCEPTION_INTERVAL
	_heard_seq = Stimuli.current.last_seq() if Stimuli.current != null else 0
	if state == State.SLEEP:
		_fit_sleep_shape()
	if _wake_at != Vector3.INF:
		target_pos = _wake_at
		_set_state(State.INVESTIGATE)
	_enter_anim()


func _now() -> float:
	return Stimuli.current.now() if Stimuli.current != null else Time.get_ticks_msec() / 1000.0


func _player() -> Player:
	return Game.world.player if Game.world != null else null


func is_alive() -> bool:
	return state != State.DEAD


func is_night() -> bool:
	return Game.session != null and Game.session.clock.is_night()


# --- Main loop -------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if state == State.DEAD:
		_corpse_t += delta
		return
	var p: Player = _player()
	var dist: float = global_position.distance_to(p.global_position) if p != null else 9999.0
	_attack_cd = maxf(0.0, _attack_cd - delta)
	_scream_cd = maxf(0.0, _scream_cd - delta)
	_spit_cd = maxf(0.0, _spit_cd - delta)
	_charge_cd = maxf(0.0, _charge_cd - delta)
	_howl_cd = maxf(0.0, _howl_cd - delta)
	_retreat_t = maxf(0.0, _retreat_t - delta)
	_stagger_lock = maxf(0.0, _stagger_lock - delta)
	_far = dist > KINEMATIC_BEYOND
	if _root_t > 0.0:
		_root_t -= delta
		if _root_t <= 0.0:
			if dist > 25.0 and state not in [State.CHASE, State.ATTACK, State.CHARGE, State.SPIT] and director != null:
				Events.hollowed_rooted.emit(entity_id, def.id, global_position)
				director.call(&"despawn", self)
				return
			_root_t = 20.0
	if _regen > 0.0 and health < max_health:
		health = minf(max_health, health + _regen * delta)
	if dist < 45.0:
		_vocalize(delta, dist)
	_state_t += delta
	_perc_t -= delta
	if _perc_t <= 0.0:
		_perc_t = PERCEPTION_INTERVAL * (1.0 if dist < 60.0 else 3.0)
		_perceive(p, dist)
	var want := Vector3.ZERO
	match state:
		State.SLEEP, State.WAKING, State.SCREAM, State.STAGGER:
			want = Vector3.ZERO
			if state == State.WAKING and _state_t > 1.3:
				_set_state(State.CHASE if _now() - last_seen_time < MEMORY_SECONDS else State.INVESTIGATE)
			elif state == State.SCREAM and _state_t > 1.6:
				_set_state(State.CHASE)
			elif state == State.STAGGER and _state_t > _stagger_t:
				_set_state(_resume_state)
		State.SPIT:
			_face(p.global_position if p != null else target_pos)
			if not _spit_done and _state_t >= 0.55:
				_spit_done = true
				_fire_spit(p)
			elif _state_t > 1.3:
				_set_state(State.CHASE)
		State.CHARGE:
			want = _charge_dir * float((def.beh("charge", {}) as Dictionary).get("speed", 8.0)) * _speed_scales["hum" if horde else ("night" if is_night() else "day")]
			_yaw_target = atan2(_charge_dir.x, _charge_dir.z)
			if p != null and not _charge_hit and dist < 1.9 and (p.global_position - global_position).normalized().dot(_charge_dir) > 0.3:
				_charge_hit = true
				_charge_impact_player(p)
			if _charge_hit or _state_t > float((def.beh("charge", {}) as Dictionary).get("max_time", 2.4)):
				_set_state(State.CHASE)
		State.IDLE:
			if _state_t > _rng.randf_range(4.0, 9.0):
				target_pos = home + Vector3(_rng.randf_range(-12, 12), 0, _rng.randf_range(-12, 12))
				_set_state(State.WANDER)
		State.WANDER:
			want = _move_dir(target_pos) * _speed(false)
			if _flat_dist(target_pos) < 1.2 or _state_t > 30.0:
				_set_state(State.IDLE)
		State.INVESTIGATE:
			want = _move_dir(target_pos) * _speed(is_night())
			if _flat_dist(target_pos) < 1.5:
				var grad: Vector3 = Stimuli.current.scent_gradient(global_position) if Stimuli.current != null else Vector3.ZERO
				if grad != Vector3.ZERO and float(def.perc("smell", 1.0)) > 0.0 and Stimuli.current.scent_at(global_position) > 0.5:
					target_pos = global_position + grad * 6.0
					_state_t = 0.0
				else:
					home = global_position
					_set_state(State.IDLE)
			elif _state_t > 40.0:
				_set_state(State.IDLE)
		State.CHASE:
			var tgt: Vector3 = target_pos
			if p != null and _now() - last_seen_time < 1.0:
				tgt = p.global_position
				target_pos = tgt
			var seen: bool = p != null and _now() - last_seen_time < 1.0
			if seen and _can_spit(dist):
				_start_spit()
			elif seen and _can_charge(dist):
				_start_charge(p)
			elif dist < float(def.beh("keeps_distance", 0.0)):
				want = (global_position - tgt).normalized() * _speed(true) * Vector3(1, 0, 1)
			elif not quad.is_empty() and p != null:
				want = _hound_move(p, tgt, dist, seen)
			else:
				want = _move_dir(tgt) * _speed(true)
			if p != null and dist <= def.atk("range", 1.5) + 0.2 and _now() - last_seen_time < 1.0 and _may_close(p):
				_set_state(State.ATTACK)
			elif _now() - last_seen_time > MEMORY_SECONDS:
				_set_state(State.HORDE if horde else State.INVESTIGATE)
		State.ATTACK:
			if p == null or not p.state.stats.alive:
				_set_state(State.IDLE)
				return
			_face(p.global_position)
			if _hit_at >= 0.0 and _state_t >= _hit_at:
				_hit_at = -1.0
				_deliver_hit(p)
				if not quad.is_empty():
					# A hound bites and breaks off, then comes again (from wherever the pack puts it).
					var rr: Array = Content.config(&"hounds").get("retreat", [0.9, 1.8])
					_retreat_t = _rng.randf_range(float(rr[0]), float(rr[1]))
					_flanked = false
					_set_state(State.CHASE)
					return
			if not _may_close(p):
				_set_state(State.CHASE)
				return
			if _hit_at < 0.0 and _attack_cd <= 0.0:
				if p == null or dist > def.atk("range", 1.5) + 0.5:
					_set_state(State.CHASE)
				else:
					_start_attack()
		State.BREAK:
			var close: bool = p != null and _now() - last_seen_time < 1.0 and dist <= def.atk("range", 1.5) + 1.0
			if break_target == null or not is_instance_valid(break_target) or break_target.is_queued_for_deletion() \
					or _target_broken(break_target) or _state_t > 20.0 or close:
				# Broken through (or given up, or the player is right here): back to the hunt.
				break_target = null
				_set_state(State.ATTACK if close else _resume_state)
			else:
				_face(break_target.global_position)
				if _attack_cd <= 0.0:
					_attack_cd = def.atk("cooldown", 1.5) * 1.1
					_strike_structure()
		State.HORDE:
			var flow: Vector3 = director.call(&"horde_direction", global_position) if director != null else Vector3.ZERO
			if flow == Vector3.ZERO and p != null:
				flow = _move_dir(p.global_position)
			want = flow * _speed(true) * 0.9
	if not perch.is_empty():
		# Posed on a seat or bed: no gravity, no sliding; once awake, the scripted rise.
		_perch_step()
		return
	_move(want, delta, dist)
	_update_anim(want)


func _move(want: Vector3, delta: float, dist: float) -> void:
	if crawling:
		want *= 0.35 if def.archetype != "crawler" else 1.0
	if dist > KINEMATIC_BEYOND:
		# No terrain collision this far out: glide along the heightfield.
		var p: Vector3 = global_position + want * delta
		p.y = Game.world.height_at(p.x, p.z) if Game.world != null else p.y
		global_position = p
		if want.length() > 0.05:
			_yaw_target = atan2(want.x, want.z)
		rotation.y = lerp_angle(rotation.y, _yaw_target, minf(1.0, delta * 5.0))
		return
	var v: Vector3 = velocity
	v.x = want.x
	v.z = want.z
	if not is_on_floor():
		v.y -= GRAVITY * delta
	else:
		v.y = maxf(v.y, -1.0)
	velocity = v
	move_and_slide()
	if state == State.CHARGE:
		var wall: Node3D = _blocking_structure()
		if wall != null:
			_charge_impact_structure(wall)
	if want.length() > 0.05:
		_yaw_target = atan2(want.x, want.z)
		# Walls in the way of something that wants in get torn down.
		if state in [State.CHASE, State.HORDE, State.INVESTIGATE]:
			var blocked: Node3D = _blocking_structure()
			if blocked != null:
				break_target = blocked
				_resume_state = state
				_set_state(State.BREAK)
			elif Vector2(velocity.x, velocity.z).length() < want.length() * 0.25:
				_stuck_t += delta
				if _stuck_t > 2.5:
					_stuck_t = 0.0
					target_pos = global_position + Vector3(_rng.randf_range(-3, 3), 0, _rng.randf_range(-3, 3))
			else:
				_stuck_t = 0.0
	rotation.y = lerp_angle(rotation.y, _yaw_target, minf(1.0, delta * 6.0))
	# Fell through the world: back onto the ground. ground_below() is the cellar floor for a body
	# down in a POI cellar, which lies under height_at()'s surface (TD-026).
	var ground: float = Game.world.ground_below(global_position) if Game.world != null else -INF
	if global_position.y < ground - 3.0:
		global_position.y = ground + 0.5
		velocity = Vector3.ZERO


func _blocking_structure() -> Node3D:
	for i: int in get_slide_collision_count():
		var c: Object = get_slide_collision(i).get_collider()
		if c is StructurePiece:
			return c
		if c is Node and (c as Node).has_meta(&"breakable"):
			return c
	return null


## Direction toward `to` along the navmesh (around houses, through doorways). The path is only
## re-requested when the goal moves a metre or every half second (a query per enemy per frame
## would be wasteful). Off the baked tiles, far away or once the path is done: straight line.
func _move_dir(to: Vector3) -> Vector3:
	var d: Vector3 = to - global_position
	if not _far and agent != null and agent.is_inside_tree():
		_nav_t -= get_physics_process_delta_time()
		if _nav_goal == Vector3.INF or _nav_goal.distance_to(to) > 1.0 or _nav_t <= 0.0:
			_nav_goal = to
			_nav_t = 0.5
			agent.target_position = to
		if not agent.is_navigation_finished():
			var step: Vector3 = agent.get_next_path_position() - global_position
			if Vector2(step.x, step.z).length() > 0.05:
				d = step
	d.y = 0.0
	return d.normalized() if d.length() > 0.05 else Vector3.ZERO


## Whether a door/window/board/wall being torn at has already given way.
static func _target_broken(n: Node) -> bool:
	if n.has_method(&"is_broken"):
		return bool(n.call(&"is_broken"))
	var hp: Variant = n.get(&"hp")
	return hp != null and float(hp) <= 0.0


func _flat_dist(p: Vector3) -> float:
	return Vector2(p.x - global_position.x, p.z - global_position.z).length()


func _face(p: Vector3) -> void:
	var d: Vector3 = p - global_position
	if Vector2(d.x, d.z).length() > 0.05:
		_yaw_target = atan2(d.x, d.z)


func _speed(running: bool) -> float:
	var s: float = def.speed_for(is_night(), running) * _speed_scales["hum" if horde else ("night" if is_night() else "day")]
	if severed.has("leg_l") or severed.has("leg_r"):
		s *= 0.6
	return s


## Idle groans, sleeping breaths, lurcher panting, shuffling feet and the dragger's scrape.
func _vocalize(delta: float, dist: float) -> void:
	_voice_t -= delta
	if _voice_t <= 0.0:
		_voice_t = _rng.randf_range(5.0, 12.0)
		var id: StringName = &""
		match state:
			State.SLEEP:
				id = &"voice/hollow_sleep_breath" if dist < 14.0 else &""
			State.IDLE, State.WANDER, State.INVESTIGATE, State.HORDE:
				id = &"voice/lurcher_pant" if def.archetype == "feral" else &"voice/hollow_groan_idle"
			State.CHASE:
				id = &"voice/lurcher_pant" if def.archetype == "feral" else &"voice/hollow_attack"
				_voice_t *= 0.5
		if not quad.is_empty() and id != &"":
			id = &"" if state == State.SLEEP else (&"voice/hound_pant" if state == State.CHASE else &"voice/hound_growl")
		if id != &"":
			Audio.play_3d(id, global_position + Vector3.UP * (0.4 if crawling or not quad.is_empty() else 1.6), {"volume_db": -4.0, "max_distance": 45.0})
	var sp: float = Vector2(velocity.x, velocity.z).length()
	# a hound's pads make no shuffle (its panting gives it away)
	if sp > 0.2 and is_on_floor() and quad.is_empty():
		_step_t -= delta * sp
		if _step_t <= 0.0:
			_step_t = 0.9 if not crawling else 1.3
			Audio.play_3d(&"voice/dragger_drag" if crawling else &"sfx/zombie_footstep_shuffle", global_position, {"volume_db": -10.0, "max_distance": 30.0})


# --- Senses ----------------------------------------------------------------------------------

func _perceive(p: Player, dist: float) -> void:
	if p == null or Stimuli.current == null or not p.state.stats.alive or DebugTools.is_on(&"invisible"):
		return
	var st: Stimuli = Stimuli.current
	if state == State.SLEEP and held:
		_perceive_held(st)
		return
	var night: bool = is_night()
	var base_sight: float = def.perc("sight_night" if night else "sight_day", 15.0)
	var light: float = st.light_at(p.global_position + Vector3.UP)
	var own_light: bool = p.get_node(^"Equipment").call(&"has_light_on") if p.has_node(^"Equipment") else false
	var vis_mult: float = p.state.progression.modifier("visibility_mult")
	var range_m: float = st.detection_range(base_sight, light, p.crouching, p.horizontal_speed(), own_light, vis_mult)
	if state == State.SLEEP:
		range_m *= 0.35 * _wake_factor
	var sees: bool = false
	if dist < range_m:
		var to_p: Vector3 = (p.global_position - global_position)
		var fwd := Vector3(sin(rotation.y), 0, cos(rotation.y))
		var ang: float = rad_to_deg(fwd.angle_to(Vector3(to_p.x, 0, to_p.z)))
		var fov: float = def.perc("fov", 120.0) * (0.6 if state == State.SLEEP else 1.0)
		if (ang < fov * 0.5 or dist < 2.2) and _line_of_sight(p):
			sees = true
	if sees:
		if state == State.SLEEP:
			awareness += 0.25 + (1.0 - dist / maxf(range_m, 0.1)) * 0.6
			if awareness >= 1.0:
				_wake(p.global_position, true)
			return
		var first: bool = _now() - last_seen_time > MEMORY_SECONDS
		last_seen_time = _now()
		target_pos = p.global_position
		if not quad.is_empty():
			_rally_pack(p.global_position)
			if first and _howl_cd <= 0.0 and _pack_alive() > 1 and state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
				_howl()
				return
		if def.archetype == "screamer" and _scream_cd <= 0.0 and bool(def.beh("scream", false)) and state != State.SCREAM:
			_scream()
			return
		if state in [State.IDLE, State.WANDER, State.INVESTIGATE, State.HORDE, State.BREAK]:
			break_target = null
			_set_state(State.CHASE)
			if first:
				Audio.play_3d(_vid(&"voice/lurcher_screech" if def.archetype == "feral" else &"voice/zombie_alert", &"voice/hound_bark"),
					_mouth(), {"volume_db": 0.0})
				Events.enemy_alerted.emit(entity_id, global_position)
		return
	# Hearing.
	var e: Stimuli.SoundEvent = st.loudest_heard(global_position, def.perc("hearing", 1.0) * (0.7 * _wake_factor if state == State.SLEEP else 1.0), _heard_seq, entity_id)
	_heard_seq = st.last_seq()
	if e != null:
		if state == State.SLEEP:
			awareness += 0.5 if e.loudness < 25.0 else 1.0
			if awareness >= 1.0:
				_wake(e.pos, false)
			return
		if state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
			target_pos = e.pos + Vector3(_rng.randf_range(-2, 2), 0, _rng.randf_range(-2, 2))
			_set_state(State.INVESTIGATE)
		return
	# A tracker (a hound) works a trail it is on: it keeps its nose to the freshest scent ahead.
	if state == State.INVESTIGATE and bool(def.beh("tracker", false)) and st.scent_at(global_position) * def.perc("smell", 1.0) > 0.6:
		var tg: Vector3 = st.scent_gradient(global_position)
		if tg != Vector3.ZERO:
			target_pos = global_position + tg * 6.0
			_state_t = 0.0
	# Smell: a strong trail pulls idle Hollowed along it.
	if state in [State.IDLE, State.WANDER] and st.scent_at(global_position) * def.perc("smell", 1.0) > 2.0:
		var g: Vector3 = st.scent_gradient(global_position)
		if g != Vector3.ZERO:
			target_pos = global_position + g * 8.0
			_set_state(State.INVESTIGATE)
	if state == State.SLEEP:
		awareness = maxf(0.0, awareness - 0.05)


## A held (ambush) sleeper sees and hears nothing ordinary: only gunfire, explosions or an alarm
## within the ambush wake radius (data/config/traps.json "ambush") rouses it early.
func _perceive_held(st: Stimuli) -> void:
	var cfg: Dictionary = Content.config(&"traps").get("ambush", {})
	var kinds: Array = cfg.get("wake_kinds", ["gunshot", "explosion", "alarm"])
	var radius: float = float(cfg.get("wake_radius", 14.0))
	var heard: Stimuli.SoundEvent = null
	for e: Stimuli.SoundEvent in st.sounds:
		if e.seq <= _heard_seq or e.source_id == entity_id or not kinds.has(String(e.kind)):
			continue
		if e.pos.distance_to(global_position) <= radius:
			heard = e
	_heard_seq = st.last_seq()
	if heard != null:
		_wake(heard.pos, false)


## Where it looks from: the head of the pose it is in (a sleeper lying on a bed sees from the
## pillow, not from 1.6 m above its knees).
func _eye() -> Vector3:
	if not quad.is_empty():
		return global_position + Vector3.UP * float(quad.get("eye", 0.62)) * (visual.scale.y if visual != null else 1.0)
	if crawling:
		return global_position + Vector3.UP * 0.4
	if state == State.SLEEP:
		var s: Vector3 = visual.scale if visual != null else Vector3.ONE
		var local: Vector3 = POSE_EYES.get(_pose_key(), Vector3(0, 1.6, 0))
		return global_transform * Vector3(local.x * s.x, local.y * s.y, local.z * s.z)
	return global_position + Vector3.UP * 1.6


func _line_of_sight(p: Player) -> bool:
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(_eye(), p.eye_position(), SIGHT_MASK)
	q.exclude = [get_rid()]
	return space.intersect_ray(q).is_empty()


func _wake(toward: Vector3, saw: bool) -> void:
	awareness = 1.0
	held = false
	target_pos = toward
	if saw:
		last_seen_time = _now()
	if perch.is_empty():
		_fit_shape()
	else:
		_perch_from = global_transform
	_set_state(State.WAKING)
	Audio.play_3d(_vid(&"voice/zombie_wake", &"voice/hound_growl"), global_position + Vector3.UP, {"volume_db": -2.0})


func notice(pos: Vector3, alert: bool = true) -> void:
	if state == State.DEAD:
		return
	if state == State.SLEEP:
		# An ambush keeps still through other sleepers waking, screams and chimes.
		if held:
			return
		_wake(pos, false)
		return
	target_pos = pos
	if alert and state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
		_set_state(State.INVESTIGATE)


## A POI ambush springs (ADR-0018): the sleeper is released and wakes already knowing where the
## intruder is (it heads straight into the chase once on its feet). Awake ones just turn on them.
func ambush(target: Vector3) -> void:
	if state == State.DEAD:
		return
	held = false
	if state != State.SLEEP:
		target_pos = target
		last_seen_time = _now()
		if state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
			_set_state(State.CHASE)
		return
	_wake(target, true)
	Audio.play_3d(_vid(&"voice/lurcher_screech" if def.archetype == "feral" else &"voice/zombie_alert", &"voice/hound_bark"), _mouth(),
		{"volume_db": 2.0})
	Events.enemy_alerted.emit(entity_id, global_position)


## Lets a held sleeper wake to ordinary noise and light again (its ambush was spent elsewhere).
func release_hold() -> void:
	held = false


## The Hum is over. Survivors drift away from the base to where it last drew them, and root into
## the soil (DESIGN §6) once nobody is near to see it; one already on the player keeps going.
func release_from_horde() -> void:
	horde = false
	horde_sector = -1
	_root_t = _rng.randf_range(60.0, 150.0)
	if _resume_state == State.HORDE:
		_resume_state = State.INVESTIGATE
	if state in [State.HORDE, State.BREAK]:
		break_target = null
		target_pos = global_position + Vector3(_rng.randf_range(-25.0, 25.0), 0.0, _rng.randf_range(-25.0, 25.0))
		home = target_pos
		_set_state(State.INVESTIGATE)


# --- Actions ---------------------------------------------------------------------------------

func _start_attack() -> void:
	_attack_cd = def.atk("cooldown", 1.5)
	var dur: float = visual.play_once(&"crawl_attack" if crawling else (&"attack_a" if _rng.randf() < 0.5 else &"attack_b"), 1.0, [&"attack_a"] as Array[StringName])
	_hit_at = _state_t + dur * 0.45
	Audio.play_3d(_vid(&"voice/zombie_attack", &"voice/hound_snarl"), _mouth(), {"volume_db": -2.0})


func _deliver_hit(p: Player) -> void:
	if p == null or not p.state.stats.alive:
		return
	if global_position.distance_to(p.global_position) > def.atk("range", 1.5) + 0.45:
		return
	# A swing only lands on what is in front of it and not behind a door that just shut.
	var to_p: Vector3 = p.global_position - global_position
	var fwd := Vector3(sin(rotation.y), 0.0, cos(rotation.y))
	if fwd.dot(Vector3(to_p.x, 0.0, to_p.z).normalized()) < 0.3 or not _line_of_sight(p):
		return
	var dmg: float = def.atk("damage", 10.0) * damage_mult * (0.5 if severed.has("arm_l") and severed.has("arm_r") else 1.0)
	var info := DamageInfo.make(dmg, &"zombie", &"zombie", entity_id)
	info.hit_pos = p.global_position + Vector3.UP * (1.3 if quad.is_empty() else 0.6)
	info.source_pos = global_position
	info.direction = (p.global_position - global_position).normalized()
	info.tool_power = {"bleed": def.atk("bleed", 0.15), "infection": def.atk("infection", 3.0)}
	p.take_damage(info)
	Audio.play_3d(&"sfx/zombie_hit_flesh", info.hit_pos, {"volume_db": -2.0})


func _strike_structure() -> void:
	visual.play(&"attack_structure", 1.0, 0.2, [&"attack_a"] as Array[StringName])
	var info := DamageInfo.make(def.atk("structure_damage", 10.0) * structure_mult, &"zombie", &"zombie", entity_id)
	info.hit_pos = break_target.global_position + Vector3.UP * 0.8
	info.source_pos = global_position
	info.direction = (break_target.global_position - global_position).normalized()
	if break_target.has_method(&"take_damage"):
		break_target.call(&"take_damage", info)
	if Stimuli.current != null:
		Stimuli.current.emit_sound(info.hit_pos, 18.0, &"pound", entity_id)


func _scream() -> void:
	_scream_cd = float(def.beh("scream_cooldown", 25.0))
	_set_state(State.SCREAM)
	visual.play_once(&"scream", 1.0, [&"attack_a"] as Array[StringName])
	Audio.play_3d(&"voice/keener_scream", global_position + Vector3.UP * 1.7, {"volume_db": 6.0, "max_distance": 300.0})
	var radius: float = float(def.beh("scream_radius", 120.0))
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, radius, &"scream", entity_id)
	if Game.session != null:
		Game.session.heat.add(global_position, float(Content.config(&"heat").get("sources", {}).get("scream", 30.0)))
	if director != null and director.has_method(&"on_scream"):
		director.call(&"on_scream", self, int(def.beh("scream_summons", 3)))


# --- Hollowed hounds (ADR-0034) ------------------------------------------------------------------

## A voice for this body: the Hollowed's own, or a hound's.
func _vid(hollowed: StringName, hound: StringName) -> StringName:
	return hollowed if quad.is_empty() else hound


## Where its voice comes from: a Hollowed's head, a hound's muzzle.
func _mouth() -> Vector3:
	if quad.is_empty():
		return global_position + Vector3.UP * 1.6
	return global_position + Vector3.UP * float(quad.get("eye", 0.62)) * 0.9 + global_transform.basis.z * 0.5


## Pack mates still alive (itself included).
func _pack_alive() -> int:
	var n: int = 0
	for m: Variant in pack:
		if m is Enemy and is_instance_valid(m) and (m as Enemy).is_alive():
			n += 1
	return n


func _pack_centre() -> Vector3:
	var c := Vector3.ZERO
	var n: int = 0
	for m: Variant in pack:
		if m is Enemy and is_instance_valid(m) and (m as Enemy).is_alive():
			c += (m as Enemy).global_position
			n += 1
	return c / float(n) if n > 0 else global_position


## What one hound sees, the pack knows: every mate within call that is not already on the quarry
## takes up the chase (a dozing one wakes to it).
func _rally_pack(at: Vector3) -> void:
	var r: float = float((Content.config(&"hounds").get("howl", {}) as Dictionary).get("pack_radius", 90.0))
	for m: Variant in pack:
		if not (m is Enemy) or not is_instance_valid(m) or m == self:
			continue
		var e: Enemy = m
		if e.is_alive() and e.state in [State.SLEEP, State.IDLE, State.WANDER, State.INVESTIGATE] \
				and e.global_position.distance_to(global_position) <= r:
			e.ambush(at)


## First sight: it stops and howls, and the pack answers. The howl carries a long way; the Hollowed
## hear it like any other sound and come to see what the dogs have found.
func _howl() -> void:
	var c: Dictionary = Content.config(&"hounds").get("howl", {})
	_howl_cd = float(c.get("cooldown", 40.0))
	for m: Variant in pack:
		if m is Enemy and is_instance_valid(m):
			(m as Enemy)._howl_cd = _howl_cd
	_set_state(State.SCREAM)
	visual.play_once(&"scream", 1.0, [&"idle"] as Array[StringName])
	Audio.play_3d(&"voice/hound_howl", _mouth(), {"volume_db": 4.0, "max_distance": 260.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, float(c.get("loudness", 70.0)), &"howl", entity_id)
	Events.enemy_alerted.emit(entity_id, global_position)


## Whether it will go in for the bite now: not while it is breaking off after one, nor in front of
## a held flame.
func _may_close(p: Player) -> bool:
	if quad.is_empty():
		return true
	return _retreat_t <= 0.0 and not _flame_shy(p)


## In front of a player holding a flame up (a torch, a lantern): it keeps off. A hound behind them
## still goes for the legs.
func _flame_shy(p: Player) -> bool:
	if p == null or not p.has_node(^"Equipment") or not bool(p.get_node(^"Equipment").call(&"has_flame_on")):
		return false
	var c: Dictionary = Content.config(&"hounds").get("torch", {})
	var fwd: Vector3 = -p.camera.global_transform.basis.z if p.camera != null else Vector3.FORWARD
	fwd.y = 0.0
	var to_me := Vector3(global_position.x - p.global_position.x, 0.0, global_position.z - p.global_position.z)
	if fwd.length() < 0.01 or to_me.length() < 0.01:
		return true
	return rad_to_deg(fwd.angle_to(to_me)) < float(c.get("behind_angle", 110.0))


## How a hound runs a chase: breaking off wide after a bite, circling out of a flame's reach, and
## with its pack, spreading round the quarry (each to its own bearing) before it closes.
func _hound_move(p: Player, tgt: Vector3, dist: float, seen: bool) -> Vector3:
	var cfg: Dictionary = Content.config(&"hounds")
	var spd: float = _speed(true)
	var away := Vector3(global_position.x - p.global_position.x, 0.0, global_position.z - p.global_position.z)
	var away_n: Vector3 = away.normalized() if away.length() > 0.05 else Vector3.FORWARD
	var side: Vector3 = away_n.cross(Vector3.UP) * (1.0 if pack_slot % 2 == 0 else -1.0)
	if _retreat_t > 0.0:
		return _steer_open((away_n + side * 0.7).normalized()) * spd * 0.85
	if seen and _flame_shy(p):
		var keep: float = float((cfg.get("torch", {}) as Dictionary).get("keep_off", 3.8))
		var radial: float = clampf((keep - dist) * 0.8, -1.0, 1.0)
		return _steer_open((side + away_n * radial).normalized()) * spd * 0.5
	var flank: Dictionary = cfg.get("flank", {})
	var mates: int = _pack_alive()
	var radius: float = float(flank.get("radius", 6.5))
	if seen and mates > 1 and not _flanked and dist > radius * 0.6 and _state_t < 6.0:
		var base: Vector3 = _pack_centre() - p.global_position
		var bearing: float = atan2(base.x, base.z) + deg_to_rad(float(flank.get("spread", 55.0))) * (float(pack_slot) - float(pack.size() - 1) * 0.5)
		var spot: Vector3 = p.global_position + Vector3(sin(bearing), 0.0, cos(bearing)) * radius
		if _flat_dist(spot) > float(flank.get("close_within", 2.0)):
			return _move_dir(spot) * spd
		_flanked = true
	return _move_dir(tgt) * spd


## A direction turned aside from walls it would run into (a quick probe, no path query: breaking
## off and circling are short moves round the quarry).
func _steer_open(dir: Vector3) -> Vector3:
	if not is_inside_tree():
		return dir
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var from: Vector3 = global_position + Vector3.UP * 0.4
	for k: int in 5:
		var a: float = float((k + 1) / 2) * 0.6 * (1.0 if k % 2 == 1 else -1.0)
		var d: Vector3 = dir.rotated(Vector3.UP, a)
		var q := PhysicsRayQueryParameters3D.create(from, from + d * 2.0, MOVE_MASK & ~LAYER)
		q.exclude = [get_rid()]
		if space.intersect_ray(q).is_empty():
			return d
	return dir


func _can_spit(dist: float) -> bool:
	var spit: Dictionary = def.beh("spit", {})
	return not spit.is_empty() and _spit_cd <= 0.0 and not crawling \
		and dist >= float(spit.get("min_range", 4.0)) and dist <= float(spit.get("range", 15.0))


func _start_spit() -> void:
	_spit_cd = float((def.beh("spit", {}) as Dictionary).get("cooldown", 6.0)) * _rng.randf_range(0.85, 1.2)
	_spit_done = false
	_set_state(State.SPIT)
	visual.play_once(&"scream", 1.2, [&"attack_a"] as Array[StringName])
	Audio.play_3d(&"voice/zombie_alert", global_position + Vector3.UP * 1.5, {"volume_db": -1.0, "pitch": 1.35})


func _fire_spit(p: Player) -> void:
	if p == null or get_parent() == null:
		return
	var mouth: Vector3 = global_position + Vector3.UP * 1.55 + global_transform.basis.z * 0.25
	# Lead the target a little: where they will be when the glob lands.
	var lead: Vector3 = p.velocity * clampf(mouth.distance_to(p.global_position) / 13.0, 0.0, 1.2) * 0.6
	Spores.spit(get_parent(), mouth, p.global_position + Vector3(lead.x, 0.3, lead.z), _scaled_spores(def.beh("spit", {})), entity_id)


## Spore attack parameters with this body's damage multiplier (difficulty, infected tier).
func _scaled_spores(params: Dictionary) -> Dictionary:
	var out: Dictionary = params.duplicate()
	for k: String in ["damage", "puddle_dps"]:
		if out.has(k):
			out[k] = float(out[k]) * damage_mult
	return out


func _can_charge(dist: float) -> bool:
	var ch: Dictionary = def.beh("charge", {})
	return not ch.is_empty() and _charge_cd <= 0.0 and not crawling \
		and dist >= float(ch.get("min_range", 5.0)) and dist <= float(ch.get("range", 15.0))


func _start_charge(p: Player) -> void:
	var ch: Dictionary = def.beh("charge", {})
	_charge_cd = float(ch.get("cooldown", 9.0)) * _rng.randf_range(0.85, 1.2)
	_charge_dir = Vector3(p.global_position.x - global_position.x, 0.0, p.global_position.z - global_position.z).normalized()
	_charge_hit = false
	_set_state(State.CHARGE)
	Audio.play_3d(&"voice/zombie_alert", global_position + Vector3.UP * 2.0, {"volume_db": 4.0, "pitch": 0.6, "max_distance": 90.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, 30.0, &"roar", entity_id)


func _charge_impact_player(p: Player) -> void:
	var ch: Dictionary = def.beh("charge", {})
	var info := DamageInfo.make(float(ch.get("damage", 30.0)) * damage_mult, &"zombie", &"zombie", entity_id)
	info.hit_pos = p.global_position + Vector3.UP * 1.2
	info.source_pos = global_position
	info.direction = _charge_dir
	info.tool_power = {"bleed": def.atk("bleed", 0.2), "infection": def.atk("infection", 3.0)}
	p.take_damage(info)
	p.velocity += _charge_dir * float(ch.get("knockback", 7.0)) + Vector3.UP * 3.0
	Audio.play_3d(&"sfx/land_hard", p.global_position, {"volume_db": 2.0})


## A charge into a wall hits it with everything; the Rammer reels for a moment.
func _charge_impact_structure(wall: Node3D) -> void:
	var ch: Dictionary = def.beh("charge", {})
	var info := DamageInfo.make(float(ch.get("structure_damage", 400.0)) * structure_mult, &"zombie", &"zombie", entity_id)
	info.hit_pos = wall.global_position + Vector3.UP * 0.8
	info.source_pos = global_position
	info.direction = _charge_dir
	if wall.has_method(&"take_damage"):
		wall.call(&"take_damage", info)
	if Stimuli.current != null:
		Stimuli.current.emit_sound(info.hit_pos, 40.0, &"pound", entity_id)
	Audio.play_3d(&"sfx/land_hard", info.hit_pos, {"volume_db": 6.0, "pitch": 0.7, "max_distance": 120.0})
	_resume_state = State.CHASE
	_stagger_t = visual.play_once(&"stagger", 1.0, [&"hit_front"] as Array[StringName])
	_set_state(State.STAGGER)


# --- Damage ----------------------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if state == State.DEAD:
		return
	var limb: String = visual.limb_at(info.hit_pos, self) if info.hit_pos != Vector3.ZERO else "torso"
	var mult: float = 2.2 if limb == "head" else (0.7 if limb != "torso" else 1.0)
	if info.cause == &"tree":
		mult = 1.0
	var amount: float = info.amount * mult
	var armor: Dictionary = def.beh("armor", {})
	var armored: bool = not armor.is_empty() and not (armor.get("weak", ["head"]) as Array).has(limb)
	if armored:
		# Fungal plates: everything but the soft spots glances off (some types bite through).
		var pierce: float = float((armor.get("pierce", {}) as Dictionary).get(String(info.type), 0.0))
		amount *= 1.0 - float(armor.get("reduction", 0.6)) * (1.0 - pierce)
	health -= amount
	last_hit_cause = info.cause
	if limb_hp.has(limb):
		limb_hp[limb] = float(limb_hp[limb]) - amount
		if float(limb_hp[limb]) <= 0.0 and limb != "torso" and not severed.has(limb) and not bool(def.beh("no_dismember", false)):
			var chance: float = info.dismember + clampf(-float(limb_hp[limb]) / 40.0, 0.0, 0.4)
			if _rng.randf() < chance:
				_sever(limb, info)
	if armored:
		Audio.play_3d(&"sfx/axe_chop_wood", info.hit_pos, {"volume_db": -4.0, "pitch": 0.8})
	else:
		FxLibrary.burst(get_parent(), "blood", info.hit_pos, -info.direction if info.direction != Vector3.ZERO else Vector3.UP, 0.8)
		Audio.play_3d(&"sfx/blade_hit_flesh" if info.type in [&"slash", &"pierce"] else &"sfx/hit_flesh", info.hit_pos, {"volume_db": -3.0})
	if health > 0.0 and _rng.randf() < 0.6:
		Audio.play_3d(_vid(&"voice/zombie_pain", &"voice/hound_yelp"), _mouth(), {"volume_db": -3.0})
	if health <= 0.0 or (severed.has("head")):
		_die(info)
		return
	if Game.session != null and Game.session.players.has(info.source_id):
		last_seen_time = _now()
		target_pos = info.source_pos
	if state == State.SLEEP:
		_wake(info.source_pos, true)
	elif amount >= _stagger_threshold(info) and state != State.STAGGER and _stagger_lock <= 0.0:
		_resume_state = State.CHASE if state in [State.ATTACK, State.CHASE, State.BREAK] else state
		if _resume_state == State.SLEEP:
			_resume_state = State.CHASE
		# Bodies face +Z: a blow from the front travels against it (recoil backwards = hit_front).
		var from_front: bool = info.direction.dot(global_transform.basis.z) < 0.0
		_stagger_t = visual.play_once(&"stagger" if amount > 30.0 else (&"hit_front" if from_front else &"hit_back"), 1.0, [&"hit_front"] as Array[StringName])
		_stagger_lock = _stagger_t + 0.6
		_set_state(State.STAGGER)
	elif state in [State.IDLE, State.WANDER, State.INVESTIGATE, State.BREAK]:
		break_target = null
		_set_state(State.CHASE)


## Damage needed to stagger. Heavier weapons (DamageInfo.stagger) stagger with less: the
## default 0.3 (also assumed when a source sets none) leaves the enemy's threshold as is, a
## sledge (0.6) needs 70% of it, Heavy Hands lowers it further.
func _stagger_threshold(info: DamageInfo) -> float:
	var s: float = info.stagger if info.stagger > 0.0 else 0.3
	return float(def.beh("stagger_threshold", 18.0)) * clampf(1.3 - s, 0.3, 1.0)


func _sever(limb: String, info: DamageInfo) -> void:
	severed[limb] = true
	visual.sever(limb, info.direction * 3.0 + Vector3.UP * 2.0)
	FxLibrary.burst(get_parent(), "gore", info.hit_pos, info.direction, 1.2)
	Audio.play_3d(&"sfx/dismember", info.hit_pos, {"volume_db": 0.0})
	Events.limb_severed.emit(entity_id, StringName(limb), info.hit_pos)
	if limb.begins_with("leg") and bool(def.beh("crawl_on_leg_loss", true)) and not crawling:
		crawling = true
		_fit_shape()


## Upright capsule for a standing body; for a crawler a short one lying along its length, low to
## the ground where its head and arms actually are.
func _fit_shape() -> void:
	var cap: CapsuleShape3D = _shape.shape
	if not quad.is_empty():
		# A hound: lying along its body, resting on the ground (also what weapons hit).
		cap.radius = _cap_radius
		cap.height = _cap_height
		_shape.rotation = Vector3(PI * 0.5, 0.0, 0.0)
		_shape.position = Vector3(0, cap.radius, 0.0)
		return
	if crawling:
		cap.radius = minf(_cap_radius, 0.3)
		cap.height = 1.3
		_shape.rotation = Vector3(PI * 0.5, 0.0, 0.0)
		_shape.position = Vector3(0, cap.radius, 0.15)
	else:
		cap.radius = _cap_radius
		cap.height = _cap_height
		_shape.rotation = Vector3.ZERO
		_shape.position = Vector3(0, cap.height * 0.5, 0)


## Dormant poses (ADR-0022): which one this body holds. "seat" / "hunch" on a seat anchor (leaning
## back / hunched on a backless one), "sit" slumped on the floor or sat legs out on a low seat (a
## tub, a mattress), "lie" on the floor or a bed, else the authored pose (stand, kneel, crouch).
func _pose_key() -> String:
	if not perch.is_empty() and str(perch.get("kind", "")) == "seat":
		match str(perch.get("lean", "back")):
			"forward":
				return "hunch"
			"low":
				# Sat in a tub or on a mattress, legs out: the floor sit, raised onto it.
				return "sit"
		return "seat"
	return sleep_pose


## Capsule (what weapons hit and the player bumps) around each dormant pose, unscaled, in the body's
## frame: [centre, height, radius, lying along Z]. The poses' bodies lie behind their origin
## (char_anim LIE_Y, SIT_Y, SEAT_Y), and a capsule standing at the knees of a lying body missed every
## blow to its head.
const POSE_SHAPES: Dictionary = {
	"lie": [Vector3(0, 0.22, -0.42), 1.75, 0.22, true],
	"sit": [Vector3(0, 0.5, -0.24), 1.0, 0.28, false],
	"seat": [Vector3(0, 0.92, -0.36), 0.8, 0.25, false],
	"hunch": [Vector3(0, 0.86, -0.28), 0.78, 0.27, false],
	"crouch": [Vector3(0, 0.45, -0.04), 0.9, 0.3, false],
	"kneel": [Vector3(0, 0.55, 0.0), 1.1, 0.28, false],
}
## Corpse box ([centre, size], body frame, unscaled) of a sleeper killed where it lay or sat: what
## "Search remains" finds.
const CORPSE_BOXES: Dictionary = {
	"lie": [Vector3(0, 0.15, -0.42), Vector3(0.6, 0.3, 1.75)],
	"sit": [Vector3(0, 0.33, -0.18), Vector3(0.6, 0.66, 0.85)],
	"seat": [Vector3(0, 0.8, -0.28), Vector3(0.5, 0.8, 0.7)],
	"hunch": [Vector3(0, 0.75, -0.18), Vector3(0.55, 0.7, 0.75)],
}
## Eye of each dormant pose (body frame, unscaled): sight lines start at the head.
const POSE_EYES: Dictionary = {
	"lie": Vector3(0, 0.25, -1.12), "sit": Vector3(0, 0.62, -0.18), "seat": Vector3(0, 1.12, -0.24),
	"hunch": Vector3(0, 0.98, -0.05), "crouch": Vector3(0, 0.62, 0.15), "kneel": Vector3(0, 0.85, 0.08),
	"stand": Vector3(0, 1.5, 0.05),
}


func _fit_sleep_shape() -> void:
	var spec: Array = POSE_SHAPES.get(_pose_key(), [])
	if spec.is_empty() or crawling or not quad.is_empty():
		_fit_shape()
		return
	var s: Vector3 = visual.scale if visual != null else Vector3.ONE
	var cap: CapsuleShape3D = _shape.shape
	var lying: bool = bool(spec[3])
	cap.radius = float(spec[2]) * maxf(s.x, s.z)
	cap.height = maxf(float(spec[1]) * (s.z if lying else s.y), cap.radius * 2.0 + 0.01)
	var c: Vector3 = spec[0]
	_shape.position = Vector3(c.x * s.x, c.y * s.y, c.z * s.z)
	_shape.rotation = Vector3(PI * 0.5, 0.0, 0.0) if lying else Vector3.ZERO


## A perched sleeper (ADR-0022): holds its pose on the seat or bed while it sleeps; once woken it
## gets up along a scripted path while its wake animation plays (wake_seat / wake_hunch keep the
## feet planted; wake_lie sits up, and the body swings round and drops off the side of the bed to
## its exit), then it is an ordinary body on the floor.
func _perch_step() -> void:
	if state == State.SLEEP or state == State.DEAD:
		return
	if state != State.WAKING:
		_release_perch()
		return
	var c: Dictionary = SleeperAnchors.cfg()
	var t: float = _state_t / maxf(float(c.get("rise_seconds", 1.25)), 0.05)
	if t >= 1.0:
		_release_perch()
		return
	var bed: bool = str(perch.get("kind", "")) == "bed"
	var mv: Array = c.get("bed_move" if bed else "seat_move", [0.4, 0.8])
	var k: float = smoothstep(float(mv[0]), float(mv[1]), t)
	var turn: Array = c.get("bed_turn", [0.12, 0.45]) if bed else mv
	var yaw0: float = _perch_from.basis.get_euler().y
	var yaw: float = lerp_angle(yaw0, float(perch["exit_yaw"]), smoothstep(float(turn[0]), float(turn[1]), t))
	var exit: Vector3 = perch["exit"]
	if not bed:
		global_position = _perch_from.origin.lerp(exit, k)
	else:
		# The body turns about its pelvis (wake_lie keeps the pelvis lie_back behind the origin while
		# it sits up, and brings it over the feet as it stands), which travels from the mattress to
		# above the exit with a little hop over the edge.
		var lb: float = float(c.get("lie_back", 0.45)) * (visual.scale.z if visual != null else 1.0)
		var pel0: Vector3 = _perch_from.origin - Vector3(sin(yaw0), 0.0, cos(yaw0)) * lb
		var pel: Vector3 = pel0.lerp(exit, k) + Vector3.UP * sin(k * PI) * 0.12
		global_position = pel + Vector3(sin(yaw), 0.0, cos(yaw)) * lb * _lie_rise_offset(t)
	rotation.y = yaw
	_yaw_target = yaw


## How far behind its feet wake_lie holds the pelvis (fraction of LIE_Y) at time t of the rise:
## lying and sitting up (frames 0-17), crouched over the feet (26), rising (34), standing (40).
static func _lie_rise_offset(t: float) -> float:
	var keys: Array = [[0.0, 1.0], [0.425, 1.0], [0.65, 0.36], [0.85, 0.11], [1.0, 0.0]]
	for i: int in range(1, keys.size()):
		if t <= float(keys[i][0]):
			var a: Array = keys[i - 1]
			var b: Array = keys[i]
			return lerpf(float(a[1]), float(b[1]), (t - float(a[0])) / maxf(float(b[0]) - float(a[0]), 1e-4))
	return 0.0


## Off the seat or bed for good: standing on its exit spot, an ordinary body under physics.
func _release_perch() -> void:
	if perch.is_empty():
		return
	global_position = perch["exit"]
	rotation.y = float(perch["exit_yaw"])
	_yaw_target = rotation.y
	velocity = Vector3.ZERO
	home = global_position
	perch = {}
	_fit_shape()


func _die(info: DamageInfo) -> void:
	# Killed in its sleep lying, slumped or seated: it stays as it was (a body dead on its bed or
	# its pew, ADR-0022). Standing, kneeling and crouching sleepers, and anything awake, fall.
	var pose: String = _pose_key()
	var in_pose: bool = state == State.SLEEP and pose in ["lie", "sit", "seat", "hunch"]
	if not in_pose:
		_release_perch()
	_set_state(State.DEAD)
	killer = {"source": String(info.source_id), "cause": String(info.cause), "tier": String(tier)}
	velocity = Vector3.ZERO
	collision_layer = CORPSE_LAYER
	collision_mask = 1
	var box := BoxShape3D.new()
	box.size = Vector3(0.6, 0.3, 1.7)
	_shape.shape = box
	_shape.rotation = Vector3.ZERO
	_shape.position = Vector3(0, 0.15, -0.6)
	if not quad.is_empty():
		# a dog on its side
		box.size = Vector3(0.7, 0.3, float(quad.get("length", 1.2))) * (visual.scale if visual != null else Vector3.ONE)
		_shape.position = Vector3(0, 0.15, 0.0)
	if in_pose:
		var s: Vector3 = visual.scale
		var corpse: Array = CORPSE_BOXES.get(pose, CORPSE_BOXES["lie"])
		box.size = (corpse[1] as Vector3) * s
		_shape.position = (corpse[0] as Vector3) * s
		visual.freeze()
	else:
		# Struck from the front, fall on the back; from behind, pitch forward onto the face.
		var back: bool = info.direction.dot(global_transform.basis.z) < 0.0
		visual.play_once(&"death_back" if back else &"death_front", 1.0, [&"death_front"] as Array[StringName])
		visual.animate_placeholder(0.0, 0.0, true)
	Audio.play_3d(_vid(&"voice/zombie_death", &"voice/hound_death"), global_position + Vector3.UP * (1.0 if quad.is_empty() else 0.5), {"volume_db": -2.0})
	if Game.session != null:
		Game.session.stats["zombies_killed"] = int(Game.session.stats.get("zombies_killed", 0)) + 1
		var pl: PlayerState = Game.session.players.get(info.source_id)
		if pl != null:
			pl.progression.add_xp(int(round(def.xp * xp_mult)))
			pl.kills[String(def.id)] = int(pl.kills.get(String(def.id), 0)) + 1
	var burst: Dictionary = def.beh("death_burst", {})
	if burst.is_empty():
		burst = _tier_burst
	if not burst.is_empty() and get_parent() != null:
		Spores.burst(get_parent(), global_position, _scaled_spores(burst), entity_id)
	Events.enemy_killed.emit(entity_id, def.id, global_position, killer)
	died.emit(self)


# --- Corpse loot -------------------------------------------------------------------------------

func interact_text(_player: Player) -> String:
	if state != State.DEAD:
		return ""
	return "Search remains" if not _looted else ("Remains" if inventory == null or inventory.stacks.is_empty() else "Search remains")


func interact_hold_time(_player: Player) -> float:
	return 1.2 if not _looted else 0.0


func interact(player: Player) -> void:
	if state != State.DEAD:
		return
	if not _looted:
		_looted = true
		inventory = Inventory.new()
		inventory.owner_id = entity_id
		inventory.max_slots = 6
		if def.loot_table != &"":
			var ctx := LootRoller.Context.new()
			# Seeded and Bloomed remains carry better finds (the reward for fighting them).
			ctx.tier = int(InfectedTiers.tier(tier).get("loot_tier", 1))
			ctx.gamestage = Game.session.gamestage(player.state)
			ctx.quality_bonus = player.state.progression.modifier("loot_quality_bonus")
			ctx.rng = _rng
			for s: ItemStack in LootRoller.roll(def.loot_table, ctx):
				inventory.add(s)
	var ui: Node = Game.world.get(&"ui") if Game.world != null else null
	if ui != null and ui.has_method(&"open_container"):
		ui.call(&"open_container", self)
	else:
		Game.execute(&"container.take_all", {"player": player.state.id, "container": self})


var container_id: StringName:
	get:
		return entity_id


# --- Animation ---------------------------------------------------------------------------------

func _set_state(s: State) -> void:
	if state == s:
		return
	if not perch.is_empty() and s not in [State.SLEEP, State.WAKING, State.DEAD]:
		# Staggered or turned on mid-rise: off the furniture at once.
		_release_perch()
	if state == State.ATTACK:
		# A swing interrupted (stagger, chase) must not land later without its animation.
		_hit_at = -1.0
	state = s
	_state_t = 0.0
	_enter_anim()


func _enter_anim() -> void:
	match state:
		State.SLEEP:
			var key: String = _pose_key()
			var alts: Array[StringName] = [&"idle_sleep_stand", &"idle"]
			if key in ["seat", "hunch"]:
				alts = [&"idle_sleep_seat", &"idle_sleep_sit", &"idle"]
			visual.play(StringName("idle_sleep_" + key), 1.0, 0.0, alts)
			visual.animate_placeholder(0.0, 0.0, key == "lie")
		State.WAKING:
			# Standing, kneeling and crouching sleepers just straighten up (no sit-down first);
			# seated ones push up off their seat, feet planted (ADR-0022).
			match _pose_key():
				"lie":
					visual.play_once(&"wake_lie", 1.0, [&"idle"] as Array[StringName])
				"sit":
					visual.play_once(&"wake_sit", 1.0, [&"idle"] as Array[StringName])
				"seat":
					visual.play_once(&"wake_seat", 1.0, [&"wake_sit", &"idle"] as Array[StringName])
				"hunch":
					visual.play_once(&"wake_hunch", 1.0, [&"wake_seat", &"wake_sit", &"idle"] as Array[StringName])
				_:
					visual.play(&"idle", 1.0, 0.5)
			visual.animate_placeholder(0.0, 0.0, false)


func _update_anim(want: Vector3) -> void:
	if state in [State.SLEEP, State.WAKING, State.ATTACK, State.SCREAM, State.STAGGER, State.DEAD, State.BREAK, State.SPIT]:
		return
	if state == State.CHARGE:
		visual.play(&"run", 1.5, 0.15, [&"walk"] as Array[StringName])
		return
	var sp: float = Vector2(velocity.x, velocity.z).length()
	if not quad.is_empty() and state == State.INVESTIGATE and sp > 0.15 and sp <= 2.4 and bool(def.beh("tracker", false)):
		# nose down on the trail
		visual.play(&"track", clampf(sp / 1.4, 0.5, 1.8), 0.3, [&"walk"] as Array[StringName])
		visual.animate_placeholder(get_physics_process_delta_time(), want.length(), false)
		return
	if crawling:
		visual.play(&"crawl", clampf(sp / 0.6, 0.4, 2.0), 0.25, [&"walk"] as Array[StringName])
	elif sp > 2.4:
		visual.play(&"run", clampf(sp / 4.5, 0.6, 1.4), 0.25, [&"walk"] as Array[StringName])
	elif sp > 0.15:
		visual.play(&"walk" if (_rng.seed & 1) == 0 else &"walk_b", clampf(sp / 0.9, 0.5, 2.0), 0.3, [&"walk"] as Array[StringName])
	else:
		visual.play(&"idle", 1.0, 0.4)
	visual.animate_placeholder(get_physics_process_delta_time(), want.length(), false)
