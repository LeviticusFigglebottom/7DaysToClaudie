class_name Enemy
extends CharacterBody3D
## A Hollowed: body, senses and brain in one data-driven node (EnemyDef archetypes walker /
## feral / screamer / crawler). The brain is a small state machine fed by the shared stimulus
## fields (Stimuli: sound events, scent grid, light) — it never reads the player's position
## unless it can actually see, hear or smell them (ADR-0012).
##
## SLEEP sleepers lie/sit/stand dormant in POIs; noise, light and a close careless player build
## `awareness` until they wake. WANDER/IDLE drift; INVESTIGATE walks to a sound or follows scent;
## CHASE runs at what it saw; ATTACK/BREAK hit the player or whatever wall is in the way; HORDE
## follows the Hum flow field toward the base; SCREAM (Keener) summons the neighbourhood.

enum State { SLEEP, WAKING, IDLE, WANDER, INVESTIGATE, CHASE, ATTACK, BREAK, SCREAM, STAGGER, HORDE, DEAD }

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
var _heard_since: float = 0.0
var _stuck_t: float = 0.0
var _resume_state: State = State.IDLE
var _yaw_target: float = 0.0
var _shape: CollisionShape3D
var _corpse_t: float = 0.0
var _looted: bool = false


func setup(p_id: StringName, p_def: EnemyDef, p_director: Node, opts: Dictionary = {}) -> void:
	entity_id = p_id
	def = p_def
	director = p_director
	_rng.seed = Ids.hash64("enemy:" + String(p_id))
	health = def.health
	limb_hp = def.limbs.duplicate()
	poi_id = StringName(str(opts.get("poi", "")))
	sleeper_id = StringName(str(opts.get("sleeper", "")))
	sleep_pose = str(opts.get("pose", "stand"))
	horde_sector = int(opts.get("horde_sector", -1))
	horde = horde_sector >= 0
	crawling = def.archetype == "crawler"
	if bool(opts.get("sleeper", "") != ""):
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
	_shape = CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 0.7 if crawling else 1.75
	_shape.shape = cap
	_shape.position = Vector3(0, cap.height * 0.5, 0)
	add_child(_shape)
	visual = EnemyVisual.new()
	visual.name = "Visual"
	add_child(visual)
	var body: String = def.bodies[_rng.randi() % def.bodies.size()] if not def.bodies.is_empty() else ""
	visual.build(body, _rng.randf_range(def.scale_range.x, def.scale_range.y))
	agent = NavigationAgent3D.new()
	agent.path_desired_distance = 0.8
	agent.target_desired_distance = 1.0
	agent.path_max_distance = 3.0
	agent.radius = 0.35
	agent.height = 1.7
	add_child(agent)
	home = global_position
	target_pos = global_position
	_yaw_target = rotation.y
	_perc_t = _rng.randf() * PERCEPTION_INTERVAL
	_heard_since = _now()
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
			if def.archetype == "screamer" and dist < float(def.beh("keeps_distance", 0.0)):
				want = (global_position - tgt).normalized() * _speed(true) * Vector3(1, 0, 1)
			else:
				want = _move_dir(tgt) * _speed(true)
			if p != null and dist <= def.atk("range", 1.5) + 0.2 and _now() - last_seen_time < 1.0:
				_set_state(State.ATTACK)
			elif _now() - last_seen_time > MEMORY_SECONDS:
				_set_state(State.HORDE if horde else State.INVESTIGATE)
		State.ATTACK:
			_face(p.global_position if p != null else target_pos)
			if _hit_at >= 0.0 and _state_t >= _hit_at:
				_hit_at = -1.0
				_deliver_hit(p)
			if _hit_at < 0.0 and _attack_cd <= 0.0:
				if p == null or dist > def.atk("range", 1.5) + 0.5:
					_set_state(State.CHASE)
				else:
					_start_attack()
		State.BREAK:
			if break_target == null or not is_instance_valid(break_target) or break_target.is_queued_for_deletion():
				break_target = null
				_set_state(_resume_state)
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
	if global_position.y < (Game.world.height_at(global_position.x, global_position.z) if Game.world != null else -INF) - 3.0:
		global_position.y = Game.world.height_at(global_position.x, global_position.z) + 0.5
		velocity = Vector3.ZERO


func _blocking_structure() -> Node3D:
	for i: int in get_slide_collision_count():
		var c: Object = get_slide_collision(i).get_collider()
		if c is StructurePiece:
			return c
		if c is Node and (c as Node).has_meta(&"breakable"):
			return c
	return null


func _move_dir(to: Vector3) -> Vector3:
	var d: Vector3
	agent.target_position = to
	var path: PackedVector3Array = agent.get_current_navigation_path()
	if not path.is_empty() and not agent.is_navigation_finished():
		d = agent.get_next_path_position() - global_position
	else:
		d = to - global_position
	d.y = 0.0
	return d.normalized() if d.length() > 0.05 else Vector3.ZERO


func _flat_dist(p: Vector3) -> float:
	return Vector2(p.x - global_position.x, p.z - global_position.z).length()


func _face(p: Vector3) -> void:
	var d: Vector3 = p - global_position
	if Vector2(d.x, d.z).length() > 0.05:
		_yaw_target = atan2(d.x, d.z)


func _speed(running: bool) -> float:
	var s: float = def.speed_for(is_night(), running)
	if severed.has("leg_l") or severed.has("leg_r"):
		s *= 0.6
	return s


# --- Senses ----------------------------------------------------------------------------------

func _perceive(p: Player, dist: float) -> void:
	if p == null or Stimuli.current == null or not p.state.stats.alive:
		return
	var st: Stimuli = Stimuli.current
	var night: bool = is_night()
	var base_sight: float = def.perc("sight_night" if night else "sight_day", 15.0)
	var light: float = st.light_at(p.global_position + Vector3.UP)
	var own_light: bool = p.get_node(^"Equipment").call(&"has_light_on") if p.has_node(^"Equipment") else false
	var vis_mult: float = p.state.progression.modifier("visibility_mult")
	var range_m: float = st.detection_range(base_sight, light, p.crouching, p.horizontal_speed(), own_light, vis_mult)
	if state == State.SLEEP:
		range_m *= 0.35
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
		if def.archetype == "screamer" and _scream_cd <= 0.0 and bool(def.beh("scream", false)) and state != State.SCREAM:
			_scream()
			return
		if state in [State.IDLE, State.WANDER, State.INVESTIGATE, State.HORDE]:
			_set_state(State.CHASE)
			if first:
				Audio.play_3d(&"voice/zombie_alert", global_position + Vector3.UP * 1.6, {"volume_db": 0.0})
				Events.enemy_alerted.emit(entity_id, global_position)
		return
	# Hearing.
	var e: Stimuli.SoundEvent = st.loudest_heard(global_position, def.perc("hearing", 1.0) * (0.7 if state == State.SLEEP else 1.0), _heard_since, entity_id)
	_heard_since = st.now()
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
	# Smell: a strong trail pulls idle Hollowed along it.
	if state in [State.IDLE, State.WANDER] and st.scent_at(global_position) * def.perc("smell", 1.0) > 2.0:
		var g: Vector3 = st.scent_gradient(global_position)
		if g != Vector3.ZERO:
			target_pos = global_position + g * 8.0
			_set_state(State.INVESTIGATE)
	if state == State.SLEEP:
		awareness = maxf(0.0, awareness - 0.05)


func _line_of_sight(p: Player) -> bool:
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(global_position + Vector3.UP * (0.4 if crawling else 1.6), p.eye_position(), SIGHT_MASK)
	q.exclude = [get_rid()]
	return space.intersect_ray(q).is_empty()


func _wake(toward: Vector3, saw: bool) -> void:
	awareness = 1.0
	target_pos = toward
	if saw:
		last_seen_time = _now()
	_set_state(State.WAKING)
	Audio.play_3d(&"voice/zombie_wake", global_position + Vector3.UP, {"volume_db": -2.0})


func notice(pos: Vector3, alert: bool = true) -> void:
	if state == State.DEAD:
		return
	if state == State.SLEEP:
		_wake(pos, false)
		return
	target_pos = pos
	if alert and state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
		_set_state(State.INVESTIGATE)


# --- Actions ---------------------------------------------------------------------------------

func _start_attack() -> void:
	_attack_cd = def.atk("cooldown", 1.5)
	var dur: float = visual.play_once(&"crawl_attack" if crawling else (&"attack_a" if _rng.randf() < 0.5 else &"attack_b"), 1.0, [&"attack_a"] as Array[StringName])
	_hit_at = _state_t + dur * 0.45
	Audio.play_3d(&"voice/zombie_attack", global_position + Vector3.UP * 1.5, {"volume_db": -2.0})


func _deliver_hit(p: Player) -> void:
	if p == null or not p.state.stats.alive:
		return
	if global_position.distance_to(p.global_position) > def.atk("range", 1.5) + 0.45:
		return
	var dmg: float = def.atk("damage", 10.0) * (0.5 if severed.has("arm_l") and severed.has("arm_r") else 1.0)
	var info := DamageInfo.make(dmg, &"zombie", &"zombie", entity_id)
	info.hit_pos = p.global_position + Vector3.UP * 1.3
	info.source_pos = global_position
	info.direction = (p.global_position - global_position).normalized()
	info.tool_power = {"bleed": def.atk("bleed", 0.15), "infection": def.atk("infection", 3.0)}
	p.take_damage(info)
	Audio.play_3d(&"sfx/zombie_hit_flesh", info.hit_pos, {"volume_db": -2.0})


func _strike_structure() -> void:
	visual.play(&"attack_structure", 1.0, 0.2, [&"attack_a"] as Array[StringName])
	var info := DamageInfo.make(def.atk("structure_damage", 10.0), &"zombie", &"zombie", entity_id)
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


# --- Damage ----------------------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if state == State.DEAD:
		return
	var limb: String = visual.limb_at(info.hit_pos, self) if info.hit_pos != Vector3.ZERO else "torso"
	var mult: float = 2.2 if limb == "head" else (0.7 if limb != "torso" else 1.0)
	if info.cause == &"tree":
		mult = 1.0
	var amount: float = info.amount * mult
	health -= amount
	last_hit_cause = info.cause
	if limb_hp.has(limb):
		limb_hp[limb] = float(limb_hp[limb]) - amount
		if float(limb_hp[limb]) <= 0.0 and limb != "torso" and not severed.has(limb):
			var chance: float = info.dismember + clampf(-float(limb_hp[limb]) / 40.0, 0.0, 0.4)
			if _rng.randf() < chance:
				_sever(limb, info)
	FxLibrary.burst(get_parent(), "blood", info.hit_pos, -info.direction if info.direction != Vector3.ZERO else Vector3.UP, 0.8)
	Audio.play_3d(&"sfx/hit_flesh", info.hit_pos, {"volume_db": -3.0})
	if health <= 0.0 or (severed.has("head")):
		_die(info)
		return
	if Game.session != null and Game.session.players.has(info.source_id):
		last_seen_time = _now()
		target_pos = info.source_pos
	if state == State.SLEEP:
		_wake(info.source_pos, true)
	elif amount >= float(def.beh("stagger_threshold", 18.0)) and state != State.STAGGER:
		_resume_state = State.CHASE if state in [State.ATTACK, State.CHASE, State.BREAK] else state
		if _resume_state == State.SLEEP:
			_resume_state = State.CHASE
		_stagger_t = visual.play_once(&"stagger" if amount > 30.0 else (&"hit_front" if info.direction.dot(-global_transform.basis.z) < 0.0 else &"hit_back"), 1.0, [&"hit_front"] as Array[StringName])
		_set_state(State.STAGGER)
	elif state in [State.IDLE, State.WANDER, State.INVESTIGATE]:
		_set_state(State.CHASE)


func _sever(limb: String, info: DamageInfo) -> void:
	severed[limb] = true
	visual.sever(limb, info.direction * 3.0 + Vector3.UP * 2.0)
	FxLibrary.burst(get_parent(), "gore", info.hit_pos, info.direction, 1.2)
	Audio.play_3d(&"sfx/dismember", info.hit_pos, {"volume_db": 0.0})
	Events.limb_severed.emit(entity_id, StringName(limb), info.hit_pos)
	if limb.begins_with("leg") and bool(def.beh("crawl_on_leg_loss", true)) and not crawling:
		crawling = true
		var cap: CapsuleShape3D = _shape.shape
		cap.height = 0.7
		_shape.position = Vector3(0, 0.35, 0)


func _die(info: DamageInfo) -> void:
	_set_state(State.DEAD)
	killer = {"source": String(info.source_id), "cause": String(info.cause)}
	velocity = Vector3.ZERO
	collision_layer = CORPSE_LAYER
	collision_mask = 1
	var box := BoxShape3D.new()
	box.size = Vector3(0.6, 0.3, 1.7)
	_shape.shape = box
	_shape.position = Vector3(0, 0.15, -0.6)
	var back: bool = info.direction.dot(global_transform.basis.z) > 0.0
	visual.play_once(&"death_back" if back else &"death_front", 1.0, [&"death_front"] as Array[StringName])
	visual.animate_placeholder(0.0, 0.0, true)
	Audio.play_3d(&"voice/zombie_death", global_position + Vector3.UP, {"volume_db": -2.0})
	if Game.session != null:
		Game.session.stats["zombies_killed"] = int(Game.session.stats.get("zombies_killed", 0)) + 1
		var pl: PlayerState = Game.session.players.get(info.source_id)
		if pl != null:
			pl.progression.add_xp(def.xp)
			pl.kills[String(def.id)] = int(pl.kills.get(String(def.id), 0)) + 1
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
			ctx.tier = 1
			ctx.gamestage = player.state.progression.gamestage(Game.session.clock.day())
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
	state = s
	_state_t = 0.0
	_enter_anim()


func _enter_anim() -> void:
	match state:
		State.SLEEP:
			visual.play(StringName("idle_sleep_" + sleep_pose), 1.0, 0.0, [&"idle_sleep_stand", &"idle"] as Array[StringName])
			visual.animate_placeholder(0.0, 0.0, sleep_pose == "lie")
		State.WAKING:
			visual.play_once(&"wake_lie" if sleep_pose == "lie" else &"wake_sit", 1.0, [&"idle"] as Array[StringName])
			visual.animate_placeholder(0.0, 0.0, false)


func _update_anim(want: Vector3) -> void:
	if state in [State.SLEEP, State.WAKING, State.ATTACK, State.SCREAM, State.STAGGER, State.DEAD, State.BREAK]:
		return
	var sp: float = Vector2(velocity.x, velocity.z).length()
	if crawling:
		visual.play(&"crawl", clampf(sp / 0.6, 0.4, 2.0), 0.25, [&"walk"] as Array[StringName])
	elif sp > 2.4:
		visual.play(&"run", clampf(sp / 4.5, 0.6, 1.4), 0.25, [&"walk"] as Array[StringName])
	elif sp > 0.15:
		visual.play(&"walk" if (_rng.seed & 1) == 0 else &"walk_b", clampf(sp / 0.9, 0.5, 2.0), 0.3, [&"walk"] as Array[StringName])
	else:
		visual.play(&"idle", 1.0, 0.4)
	visual.animate_placeholder(get_physics_process_delta_time(), want.length(), false)
