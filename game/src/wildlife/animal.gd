class_name Animal
extends CharacterBody3D
## A deer or a hare (ADR-0027): the generated quadruped body with its actions, a small brain fed
## by the same senses as the Hollowed (WildlifeBrain), and, once killed, a carcass to butcher.
##
## Animals glide on the terrain heightfield (no physics move: a herd costs a height lookup per
## body per frame) and wear the enemy layer so a swing or a shot finds them. A herd shares one
## mind for flight: when one bolts, its band bolts with it (WildlifeManager wires `herd`).
## States: GRAZE head down, IDLE head up chewing, WALK to a new patch, ALERT frozen staring at what
## it noticed (a deer stamps), FLEE flat out away from it, BED_DOWN / BED / GET_UP at night,
## DEAD. A carcass bleeds scent the Hollowed follow (Stimuli.deposit_scent) until it rots away.

enum State { GRAZE, IDLE, WALK, ALERT, FLEE, BED_DOWN, BED, GET_UP, DEAD }

const LAYER: int = 1 << 4
const CORPSE_LAYER: int = 1 << 7
const THINK_INTERVAL: float = 0.25
const LOOPS: Array[StringName] = [&"idle", &"graze", &"alert", &"bed", &"walk", &"trot", &"gallop"]

signal died(animal: Animal)

var entity_id: StringName = &""
var def: WildlifeDef
var manager: Node = null
var model_id: String = ""
var state: State = State.GRAZE
var health: float = 50.0
## The band it runs with (Array of Animal, itself included); the first is the leader.
var herd: Array = []
var butchered: bool = false
var killer: StringName = &""
## Where it was going and what it fled from.
var target := Vector3.ZERO
var threat_pos := Vector3.ZERO
var anim: AnimationPlayer = null
var visual: Node3D = null

var _rng := RandomNumberGenerator.new()
var _think_t: float = 0.0
var _state_t: float = 0.0
var _speed: float = 0.0
var _flee_t: float = 0.0
var _scent_t: float = 0.0
var _dead_t: float = 0.0
var _yaw_goal: float = 0.0
var _scale: float = 1.0
var _shape: CollisionShape3D
var _heard_seq: int = 0
var _calm_t: float = 0.0


func setup(id: StringName, p_def: WildlifeDef, p_manager: Node, opts: Dictionary = {}) -> void:
	entity_id = id
	def = p_def
	manager = p_manager
	_rng.seed = int(opts.get("seed", Ids.hash64(String(id))))
	model_id = str(opts.get("model", def.pick_model(_rng.randf())))
	_scale = float(opts.get("scale", lerpf(def.size.x, def.size.y, _rng.randf())))
	health = def.health * (_scale if model_id.ends_with("buck") else 1.0)
	collision_layer = LAYER
	collision_mask = 0
	state = State.BED if bool(opts.get("bedded", false)) else (State.GRAZE if _rng.randf() < 0.7 else State.IDLE)


func _ready() -> void:
	_build_visual()
	_shape = CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	var deer: bool = def.id != &"snowshoe_hare"
	cap.radius = (0.24 if deer else 0.085) * _scale
	cap.height = (1.55 if deer else 0.4) * _scale
	_shape.shape = cap
	_shape.rotation = Vector3(PI * 0.5, 0.0, 0.0)
	_shape.position = Vector3(0.0, (0.85 if deer else 0.16) * _scale, 0.0)
	add_child(_shape)
	_yaw_goal = rotation.y
	target = global_position
	_enter(state)


func _build_visual() -> void:
	var path: String = "res://assets/generated/models/%s.glb" % model_id
	var ps: PackedScene = load(path) as PackedScene if ResourceLoader.exists(path) else null
	if ps != null:
		visual = ps.instantiate() as Node3D
		anim = visual.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if anim != null:
			for a: StringName in anim.get_animation_list():
				if a in LOOPS:
					anim.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	else:
		# Stand-in until `make assets`: a brown body on four posts.
		visual = Node3D.new()
		var deer: bool = def.id != &"snowshoe_hare"
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.42, 0.31, 0.22)
		var body := MeshInstance3D.new()
		var cap := CapsuleMesh.new()
		cap.radius = 0.2 if deer else 0.08
		cap.height = 1.3 if deer else 0.36
		cap.material = m
		body.mesh = cap
		body.rotation = Vector3(PI * 0.5, 0, 0)
		body.position = Vector3(0, 0.85 if deer else 0.16, 0)
		visual.add_child(body)
	visual.scale = Vector3.ONE * _scale
	add_child(visual)


func is_alive() -> bool:
	return state != State.DEAD


# --- Behaviour ---------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	_state_t += delta
	if state == State.DEAD:
		_carcass_tick(delta)
		return
	_think_t -= delta
	if _think_t <= 0.0:
		_think_t = THINK_INTERVAL + _rng.randf() * 0.05
		_think()
	_move(delta)


func _think() -> void:
	var ctx: Dictionary = manager.call(&"senses_context", self) if manager != null else {}
	var worst: WildlifeBrain.Threat = WildlifeBrain.Threat.NONE
	var threats: Array[Vector3] = []
	var person: Dictionary = ctx.get("person", {})
	if not person.is_empty():
		var vis: float = WildlifeBrain.visibility(def, float(person["lit"]), float(person["light"]), bool(person["own_light"]))
		var t: WildlifeBrain.Threat = WildlifeBrain.person_threat(def, global_position, person["pos"], vis,
			bool(person["crouched"]), ctx.get("wind", Vector2.ZERO), float(ctx.get("wind_strength", 0.0)))
		if state in [State.BED, State.BED_DOWN] and t == WildlifeBrain.Threat.ALERT:
			t = WildlifeBrain.Threat.NONE   # bedded down, it lies tight until you are close
		if t != WildlifeBrain.Threat.NONE:
			threats.append(person["pos"])
		worst = maxi(worst, t) as WildlifeBrain.Threat
	for h: Vector3 in ctx.get("hollowed", []):
		var t2: WildlifeBrain.Threat = WildlifeBrain.hollowed_threat(def, global_position, h)
		if t2 != WildlifeBrain.Threat.NONE:
			threats.append(h)
		worst = maxi(worst, t2) as WildlifeBrain.Threat
	var loud: Dictionary = ctx.get("loud", {})
	if not loud.is_empty():
		var t3: WildlifeBrain.Threat = WildlifeBrain.sound_threat(def, float(loud["loudness"]), global_position.distance_to(loud["pos"]))
		if t3 != WildlifeBrain.Threat.NONE:
			threats.append(loud["pos"])
		worst = maxi(worst, t3) as WildlifeBrain.Threat
	# The player's footsteps (walk 6 m, sprint 14, crouch 2, x hearing): it looks up at a tread close
	# by in the dark, and a hare bolts from a sprint.
	var step: Dictionary = ctx.get("step", {})
	if not step.is_empty():
		var t4: WildlifeBrain.Threat = WildlifeBrain.sound_threat(def, float(step["loudness"]), global_position.distance_to(step["pos"]))
		if t4 != WildlifeBrain.Threat.NONE:
			threats.append(step["pos"])
		worst = maxi(worst, t4) as WildlifeBrain.Threat
	if bool(ctx.get("silence", false)):
		# a Hum night: the valley floor empties
		worst = WildlifeBrain.Threat.FLEE
		if threats.is_empty():
			threats.append(global_position + Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)))
	if worst == WildlifeBrain.Threat.FLEE:
		bolt(_nearest(threats))
		return
	if worst == WildlifeBrain.Threat.ALERT and state != State.FLEE:
		_calm_t = 0.0
		threat_pos = _nearest(threats)
		if state != State.ALERT and state not in [State.BED, State.BED_DOWN, State.GET_UP]:
			_enter(State.ALERT)
		return
	_calm_t += THINK_INTERVAL
	_routine(bool(ctx.get("night", false)))


func _nearest(points: Array[Vector3]) -> Vector3:
	var best := global_position + Vector3.FORWARD
	var bd: float = INF
	for p: Vector3 in points:
		var d: float = p.distance_squared_to(global_position)
		if d < bd:
			bd = d
			best = p
	return best


## Flight: the whole band goes, each a little apart, away from `from`.
func bolt(from: Vector3) -> void:
	for a: Variant in herd:
		if is_instance_valid(a) and a is Animal and a != self and (a as Animal).is_alive() and (a as Animal).state != State.FLEE:
			(a as Animal)._start_flee(from, false)
	if state != State.FLEE:
		_start_flee(from, true)
	else:
		threat_pos = from
		_flee_t = 0.0


func _start_flee(from: Vector3, first: bool) -> void:
	threat_pos = from
	_flee_t = 0.0
	if first:
		var snd: String = str(def.sounds.get("alarm", ""))
		if snd != "":
			Audio.play_3d(StringName(snd), global_position + Vector3.UP * 0.8 * _scale, {"volume_db": 0.0, "max_distance": 120.0})
		var run: String = str(def.sounds.get("flee", ""))
		if run != "":
			Audio.play_3d(StringName(run), global_position, {"volume_db": -3.0, "max_distance": 90.0})
		if def.alarm_loudness > 0.0 and Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, def.alarm_loudness, &"wildlife_alarm", entity_id)
	_enter(State.FLEE)


func _routine(night: bool) -> void:
	match state:
		State.ALERT:
			if _calm_t > 4.0:
				_enter(State.GRAZE if _rng.randf() < 0.6 else State.IDLE)
		State.FLEE:
			if _flee_t > 12.0 and _calm_t > 3.0:
				_enter(State.ALERT)
		State.GRAZE, State.IDLE:
			if night and def.beds_at_night and _rng.randf() < 0.08:
				_enter(State.BED_DOWN)
			elif _state_t > _rng.randf_range(6.0, 16.0):
				if _rng.randf() < 0.45:
					_pick_patch()
					_enter(State.WALK)
				else:
					_enter(State.IDLE if state == State.GRAZE else State.GRAZE)
		State.WALK:
			if Vector2(target.x - global_position.x, target.z - global_position.z).length() < 0.6 or _state_t > 20.0:
				_enter(State.GRAZE)
		State.BED_DOWN:
			if _state_t > _len(&"bed_down"):
				_enter(State.BED)
		State.BED:
			if not night and _state_t > 5.0:
				_enter(State.GET_UP)
		State.GET_UP:
			if _state_t > _len(&"get_up"):
				_enter(State.GRAZE)


## A nearby patch, staying with the band (followers keep near the leader).
func _pick_patch() -> void:
	var lead: Animal = herd[0] if not herd.is_empty() and is_instance_valid(herd[0]) else self
	var center: Vector3 = lead.global_position if lead != self else global_position
	var r: float = 6.0 if def.id != &"snowshoe_hare" else 3.0
	for i: int in 6:
		var p := center + Vector3(_rng.randf_range(-r, r), 0.0, _rng.randf_range(-r, r))
		if manager == null or bool(manager.call(&"walkable", p)):
			target = p
			return
	target = global_position


func _enter(s: State) -> void:
	state = s
	_state_t = 0.0
	match s:
		State.GRAZE:
			_play(&"graze", 1.0)
		State.IDLE:
			_play(&"idle", 1.0)
		State.ALERT:
			_play(&"alert", 1.0)
			_face(threat_pos)
		State.WALK:
			pass
		State.FLEE:
			pass
		State.BED_DOWN:
			_play(&"bed_down", 1.0, false)
		State.BED:
			_play(&"bed", 1.0)
		State.GET_UP:
			_play(&"get_up", 1.0, false)


func _face(p: Vector3) -> void:
	var to := p - global_position
	if Vector2(to.x, to.z).length() > 0.01:
		_yaw_goal = atan2(to.x, to.z)


func _move(delta: float) -> void:
	var want: float = 0.0
	var dir := Vector3.ZERO
	match state:
		State.WALK:
			var to := target - global_position
			to.y = 0.0
			if to.length() > 0.3:
				dir = to.normalized()
				want = float(def.speed.get("walk", 1.1))
		State.FLEE:
			_flee_t += delta
			var away: Vector3 = WildlifeBrain.flee_direction(global_position, [threat_pos] as Array[Vector3], sin(_flee_t * 0.7 + float(entity_id.hash() % 7)) * 0.35)
			dir = _steer(away)
			want = float(def.speed.get("flee", 10.0)) * (1.0 if _flee_t < 8.0 else 0.6)
	_speed = move_toward(_speed, want, delta * (14.0 if want > _speed else 6.0))
	if dir != Vector3.ZERO:
		_yaw_goal = atan2(dir.x, dir.z)
	rotation.y = lerp_angle(rotation.y, _yaw_goal, clampf(delta * (8.0 if state == State.FLEE else 3.0), 0.0, 1.0))
	if _speed > 0.02:
		var fwd := Vector3(sin(rotation.y), 0.0, cos(rotation.y))
		var next: Vector3 = global_position + fwd * _speed * delta
		if manager == null or bool(manager.call(&"walkable", next)):
			global_position = next
		else:
			_yaw_goal += PI * 0.5 * (1.0 if _rng.randf() < 0.5 else -1.0)
	if manager != null:
		var p := global_position
		p.y = float(manager.call(&"height_at", p.x, p.z))
		global_position = p
	_locomotion_anim()


## Turns a flight direction aside from what it cannot run through (water, buildings, cliffs).
func _steer(dir: Vector3) -> Vector3:
	if manager == null:
		return dir
	for k: int in 7:
		var a: float = (float((k + 1) / 2) * 0.45) * (1.0 if k % 2 == 1 else -1.0)
		var d: Vector3 = dir.rotated(Vector3.UP, a)
		if bool(manager.call(&"walkable", global_position + d * 4.0)):
			return d
	return dir


func _locomotion_anim() -> void:
	if state not in [State.WALK, State.FLEE]:
		return
	if _speed < 0.15:
		_play(&"alert" if state == State.FLEE else &"idle", 1.0)
		return
	var walk_s: float = float(def.anim_speed.get("walk", 1.0)) * _scale
	var trot_s: float = float(def.anim_speed.get("trot", 3.0)) * _scale
	var gallop_s: float = float(def.anim_speed.get("gallop", 9.0)) * _scale
	if _speed < (walk_s + trot_s) * 0.5 or anim == null or not anim.has_animation(&"trot") and _speed < gallop_s * 0.4:
		_play(&"walk", clampf(_speed / walk_s, 0.4, 2.2))
	elif _speed < (trot_s + gallop_s) * 0.5 and anim.has_animation(&"trot"):
		_play(&"trot", clampf(_speed / trot_s, 0.6, 1.8))
	else:
		_play(&"gallop", clampf(_speed / gallop_s, 0.6, 1.6))


func _play(n: StringName, speed: float = 1.0, loop: bool = true) -> void:
	if anim == null or not anim.has_animation(n):
		return
	if anim.current_animation == n and anim.is_playing():
		anim.speed_scale = speed
		return
	anim.play(n, 0.3 if loop else 0.2)
	anim.speed_scale = speed


func _len(n: StringName) -> float:
	return anim.get_animation(n).length if anim != null and anim.has_animation(n) else 1.0


# --- Hunting -----------------------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if state == State.DEAD:
		return
	var amount: float = info.amount
	if info.hit_pos != Vector3.ZERO and _is_head(info.hit_pos):
		amount *= def.head_mult
	health -= amount
	FxLibrary.burst(get_parent(), "blood", info.hit_pos if info.hit_pos != Vector3.ZERO else global_position + Vector3.UP * 0.8 * _scale,
		-info.direction, 0.6 * _scale)
	if health <= 0.0:
		_die(info)
		return
	var snd: String = str(def.sounds.get("hurt", ""))
	if snd != "":
		Audio.play_3d(StringName(snd), global_position + Vector3.UP * 0.8 * _scale, {"volume_db": -2.0})
	if anim != null and anim.has_animation(&"hit") and state != State.FLEE:
		anim.play(&"hit", 0.05)
	bolt(info.source_pos if info.source_pos != Vector3.ZERO else global_position - info.direction * 5.0)


func _is_head(p: Vector3) -> bool:
	var sk: Skeleton3D = visual.find_child("Skeleton3D", true, false) as Skeleton3D if visual != null else null
	if sk != null:
		var bi: int = sk.find_bone("head")
		if bi >= 0:
			var hp: Vector3 = sk.global_transform * sk.get_bone_global_pose(bi).origin
			return p.distance_to(hp) < 0.2 * _scale * (1.0 if def.id != &"snowshoe_hare" else 0.4)
	var local: Vector3 = global_transform.affine_inverse() * p
	return local.z > 0.55 * _scale and local.y > 1.1 * _scale


func _die(info: DamageInfo) -> void:
	state = State.DEAD
	_state_t = 0.0
	killer = info.source_id
	collision_layer = CORPSE_LAYER
	_shape.position.y = (0.25 if def.id != &"snowshoe_hare" else 0.06) * _scale
	var snd: String = str(def.sounds.get("death", ""))
	if snd != "":
		Audio.play_3d(StringName(snd), global_position + Vector3.UP * 0.6 * _scale, {"volume_db": 0.0})
	if anim != null and anim.has_animation(&"death"):
		anim.play(&"death", 0.1)
		anim.speed_scale = 1.0
	# blood on the ground is a scent the Hollowed pick up, and a kill is heat
	if Stimuli.current != null:
		Stimuli.current.deposit_scent(global_position, float(def.carcass.get("scent", 2.0)) * 4.0)
	if Game.session != null:
		var pl: PlayerState = Game.session.players.get(info.source_id)
		if pl != null:
			pl.progression.award("hunt_kill")
	for a: Variant in herd:
		if is_instance_valid(a) and a is Animal and a != self:
			(a as Animal).bolt(global_position)
	Events.wildlife_killed.emit(entity_id, def.id, global_position, String(info.source_id))
	died.emit(self)


func _carcass_tick(delta: float) -> void:
	_dead_t += delta
	_scent_t -= delta
	if _scent_t <= 0.0:
		_scent_t = 1.0
		if Stimuli.current != null:
			# a fresh kill bleeds; the trail fades as it stiffens, butchered remains still reek
			var s: float = float(def.carcass.get("scent", 2.0)) * clampf(1.0 - _dead_t / maxf(float(def.carcass.get("lifetime", 600.0)), 1.0), 0.25, 1.0)
			Stimuli.current.deposit_scent(global_position, s)


func carcass_age() -> float:
	return _dead_t


func interact_text(player: Player) -> String:
	if state != State.DEAD or butchered:
		return ""
	var tool := WildlifeManager.butcher_tool(player.state, def) if player != null and player.state != null else &""
	if tool == &"":
		return "Butcher %s (needs a knife or an axe)" % def.display_name.to_lower()
	return "Butcher %s" % def.display_name.to_lower()


func interact_hold_time(player: Player) -> float:
	if player == null or player.state == null or WildlifeManager.butcher_tool(player.state, def) == &"":
		return 0.0
	return float(def.carcass.get("time", 3.0))


func interact(player: Player) -> void:
	if state != State.DEAD or butchered or player == null:
		return
	var r: Dictionary = Game.execute(&"wildlife.butcher", {"player": player.state.id, "animal": entity_id})
	if not bool(r.get("ok", false)):
		Events.player_status_message.emit(str(r.get("error", "Can't butcher that")), &"warning")


## What is left once butchered: the body sinks into a pile of remains (the mesh flattens and
## darkens); it still smells.
func mark_butchered() -> void:
	butchered = true
	if visual != null:
		var tw := create_tween()
		tw.tween_property(visual, "scale", Vector3(_scale, _scale * 0.45, _scale), 1.2)
