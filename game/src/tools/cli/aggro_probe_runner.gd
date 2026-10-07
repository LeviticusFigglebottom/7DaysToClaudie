extends Node
## Aggro probe logic (see aggro_probe.gd; docs/AI_TUNING.md). Two modes:
##  * default (session 3): a real new game on the main map; for each enemy, day and night, the player
##    standing or walking, one awake wanderer facing the player at 5..60 m: does it chase within 4 s?
##  * `--flat`: a controlled matrix on a flat floor. Each trial builds a fresh floor, Stimuli,
##    AIDirector and Player, puts one enemy `dist` m away facing the player (F) or side-on (S, 90
##    degrees away), and paces the player sideways (+-3 m) in a stance: still, walk, crouch
##    (crouch-walk), sprint, torch (walking with a lit torch), cover (crouch-walking behind a 1.3 m
##    vegetation-layer log 1.5 m in front). It times when the enemy notices (leaves IDLE/WANDER;
##    `s` = saw the player, `i` = investigates a sound or scent) and when it gets within 2 m. A
##    group line puts a second Hollow 15 m behind the spotter, facing away, and times when it joins.
##    Run with --fixed-fps 60 so simulated time runs faster than the wall clock.

const DISTANCES: Array[float] = [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0]


func _ready() -> void:
	if args_has("--flat"):
		_flat_main()
		return
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var ids: PackedStringArray = ["hollow", "lurcher", "keener", "hollow_hound"]
	var i: int = args.find("--enemies")
	if i >= 0 and i + 1 < args.size():
		ids = args[i + 1].split(",")
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "aggro_probe"})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	var w: GameWorld = game.world
	var p: Player = w.player
	p.god_mode = true
	var ai: Node = w.ai
	var origin: Vector3 = p.global_position
	print("[aggro] enemy | time | player | noticed at (m) of %s" % [DISTANCES])
	for id: String in ids:
		for hour: float in [12.0, 23.0]:
			for walking: bool in [false, true]:
				var noticed: Array[String] = []
				for d: float in DISTANCES:
					noticed.append("Y" if await _trial(w, p, ai, StringName(id), hour, walking, d, origin) else ".")
				print("[aggro] %-12s | %s | %-8s | %s" % [id, "day  " if hour < 20.0 else "night", "walking" if walking else "standing", " ".join(noticed)])
	get_tree().quit(0)


func _trial(w: GameWorld, p: Player, ai: Node, id: StringName, hour: float, walking: bool, d: float, origin: Vector3) -> bool:
	Game.session.clock.set_time(Game.session.clock.day(), hour)
	for e: Node in get_tree().get_nodes_in_group(&"enemies"):
		ai.call(&"despawn", e)
	p.global_position = origin
	p.velocity = Vector3.ZERO
	await get_tree().physics_frame
	var at := Vector3(origin.x + d, 0.0, origin.z)
	at.y = w.height_at(at.x, at.z) + 0.1
	var e: Enemy = ai.call(&"spawn", id, at, {"authored": true}) as Enemy
	if e == null:
		return false
	e.look_at(Vector3(origin.x, at.y, origin.z), Vector3.UP)
	e.rotation.y += PI
	# Keep that facing: the body otherwise turns back to its random spawn yaw (Enemy._yaw_target).
	e.set(&"_yaw_target", e.rotation.y)
	if args_has("--diag"):
		await get_tree().physics_frame
		var st: Stimuli = Stimuli.current
		var light: float = st.light_at(p.global_position + Vector3.UP)
		var base: float = e.def.perc("sight_night" if e.is_night() else "sight_day", 15.0)
		var r: float = st.detection_range(base, light, false, 0.0, false, p.state.progression.modifier("visibility_mult"),
			e.def.perc("dark_sight", 0.15))
		print("[aggro] diag %s d=%.0f light=%.2f base=%.1f vis=%.2f range=%.1f los=%s state=%s" % [id, d, light, base, p.state.progression.modifier("visibility_mult"), r, e._line_of_sight(p), Enemy.State.keys()[e.state]])
	var chased: bool = false
	var t: int = 0
	while t < 240:
		if walking:
			# Strafe across its view at walking speed (the speed is what detection reads).
			p.velocity = Vector3(0, 0, 3.4)
			p.global_position.z = origin.z + sin(t * 0.05) * 3.0
		await get_tree().physics_frame
		t += 1
		if e.state in [Enemy.State.CHASE, Enemy.State.ATTACK, Enemy.State.CHARGE, Enemy.State.SCREAM]:
			chased = true
			break
	ai.call(&"despawn", e)
	return chased


func args_has(a: String) -> bool:
	return OS.get_cmdline_user_args().has(a)


# --- Flat-floor matrix (--flat) ----------------------------------------------------------------

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const NOTICE_LIMIT: float = 30.0
const TRIAL_LIMIT: float = 90.0
const REACH: float = 2.0
const PACE: float = 3.0
## Stimuli.ambient_light at night (EnvironmentController.ambient_light_level: 0 .. 0.15 by the moon).
const NIGHT_LIGHT: float = 0.05


class ProbeWorld:
	extends Node3D
	var player: Node3D = null
	var ai: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0

	func ground_below(_p: Vector3) -> float:
		return 0.0


var _enemies: PackedStringArray = ["hollow", "lurcher"]
var _dists: Array[float] = [10.0, 20.0, 30.0, 40.0, 60.0]
var _stances: PackedStringArray = ["still", "walk", "crouch", "sprint", "torch", "cover"]
var _periods: PackedStringArray = ["day", "night"]
var _world: ProbeWorld
var _player: Player


func _flat_main() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size() - 1:
		match args[i]:
			"--enemies":
				_enemies = args[i + 1].split(",")
			"--stances":
				_stances = args[i + 1].split(",")
			"--periods":
				_periods = args[i + 1].split(",")
			"--dists":
				_dists.clear()
				for s: String in args[i + 1].split(","):
					_dists.append(float(s))
	_flat_run.call_deferred()


func _flat_run() -> void:
	Game.session = GameSession.create_new({"seed": 4242, "game_mode": "survival"})
	var t0: int = Time.get_ticks_msec()
	var header: String = "| enemy | time | stance |"
	var rule: String = "|---|---|---|"
	for d: float in _dists:
		header += " %d m F | %d m S |" % [int(d), int(d)]
		rule += "---|---|"
	print("AGGRO cell = notice s/i (s: saw, i: heard/smelled) -> reached 2 m; '-' = not within %d s (notice) / %d s (reach)" % [int(NOTICE_LIMIT), int(TRIAL_LIMIT)])
	print("AGGRO " + header)
	print("AGGRO " + rule)
	for enemy: String in _enemies:
		for period: String in _periods:
			for stance: String in _stances:
				var line: String = "| %s | %s | %s |" % [enemy, period, stance]
				for d: float in _dists:
					for side: bool in [false, true]:
						var r: Dictionary = await _flat_trial(StringName(enemy), period == "night", stance, d, side)
						line += " %s |" % _cell(r)
				print("AGGRO " + line)
	for period: String in _periods:
		var g: Dictionary = await _group_trial(period == "night")
		print("AGGRO group (%s): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter %s, buddy %s" % [
			period, _cell(g["spotter"]), _cell(g["buddy"])])
	print("AGGRO done in %.1f s" % ((Time.get_ticks_msec() - t0) / 1000.0))
	get_tree().quit(0)


func _cell(r: Dictionary) -> String:
	if float(r["notice"]) < 0.0:
		return "-"
	var s: String = "%.1f%s" % [float(r["notice"]), r["how"]]
	s += " -> " + ("%.0f" % float(r["reach"]) if float(r["reach"]) >= 0.0 else "-")
	return s


func _setup(night: bool, stance: String) -> void:
	Game.session.clock.set_time(2, 23.0 if night else 12.0)
	_world = ProbeWorld.new()
	add_child(_world)
	_box(Vector3(0, -0.5, 0), Vector3(400, 1, 400), 1)
	var st := Stimuli.new()
	_world.add_child(st)
	st.recenter(Vector3.ZERO)
	# No GameWorld here to feed the sky's light: full day, or a moonless night.
	st.ambient_light = NIGHT_LIGHT if night else 1.0
	var ai := AIDirector.new()
	_world.add_child(ai)
	_world.ai = ai
	if stance == "cover":
		# A fallen log / thicket: vegetation layer (13), as tall as a crouched man's eyes and more.
		_box(Vector3(0, 0.65, 1.5), Vector3(10, 1.3, 0.6), 1 << 12)
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = true
	_world.add_child(_player)
	_player.bind_state(Game.session.local_player())
	_player.state.stats.alive = true
	_player.state.stats.health = 100.0
	_player.global_position = Vector3(0, 0.05, 0)
	_player.rotation.y = -PI * 0.5
	_world.player = _player
	Game.world = _world
	if stance == "torch":
		var eq: Node = _player.get_node(^"Equipment")
		var flame := OmniLight3D.new()
		eq.add_child(flame)
		eq.set(&"_light", flame)
		eq.set(&"_light_on", true)
		st.register_light(flame, 13.0 * 1.5, 2.4)


func _teardown() -> void:
	for a: StringName in [&"move_forward", &"sprint"]:
		Input.action_release(a)
	Game.world = null
	_world.queue_free()
	_world = null
	_player = null
	await get_tree().physics_frame
	await get_tree().physics_frame


func _box(at: Vector3, size: Vector3, layer: int) -> void:
	var b := StaticBody3D.new()
	b.collision_layer = layer
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	_world.add_child(b)
	b.global_position = at


func _drive(stance: String) -> void:
	_player.state.stats.stamina = 100.0
	_player.state.stats.health = 100.0
	if stance in ["crouch", "cover"]:
		_player.call(&"_set_crouch", true)
	if stance != "still":
		Input.action_press(&"move_forward")
	if stance == "sprint":
		Input.action_press(&"sprint")
	if _player.global_position.x > PACE:
		_player.rotation.y = PI * 0.5
	elif _player.global_position.x < -PACE:
		_player.rotation.y = -PI * 0.5


func _spawn(id: StringName, at: Vector3, yaw: float, tag: String) -> Enemy:
	return _world.ai.call(&"spawn", id, at, {"tier": "normal", "authored": true, "yaw": yaw, "id": "probe:" + tag}) as Enemy


static func _noticed(e: Enemy) -> bool:
	return e.state not in [Enemy.State.IDLE, Enemy.State.WANDER]


func _flat(e: Enemy) -> float:
	var d: Vector3 = e.global_position - _player.global_position
	return Vector2(d.x, d.z).length()


## A second in the stance first (the crouched eye height eases down; the gait gets going).
func _preroll(stance: String) -> void:
	for i: int in Engine.physics_ticks_per_second:
		_drive(stance)
		await get_tree().physics_frame


func _flat_trial(id: StringName, night: bool, stance: String, dist: float, side: bool) -> Dictionary:
	_setup(night, stance)
	await _preroll(stance)
	# Facing the player (toward -Z) or side-on (toward +X).
	var e: Enemy = _spawn(id, Vector3(0, 0.1, dist), PI * 0.5 if side else PI, "e")
	var out: Dictionary = {"notice": -1.0, "how": "", "reach": -1.0}
	var t: float = 0.0
	while t < TRIAL_LIMIT:
		_drive(stance)
		await get_tree().physics_frame
		t += 1.0 / float(Engine.physics_ticks_per_second)
		if not is_instance_valid(e):
			break
		if float(out["notice"]) < 0.0 and _noticed(e):
			out["notice"] = t
			out["how"] = "s" if e.last_seen_time > -50.0 else "i"
		if float(out["notice"]) < 0.0 and t > NOTICE_LIMIT:
			break
		if _flat(e) < REACH:
			out["reach"] = t
			break
	await _teardown()
	return out


func _group_trial(night: bool) -> Dictionary:
	_setup(night, "walk")
	await _preroll("walk")
	var spotter: Enemy = _spawn(&"hollow", Vector3(0, 0.1, 25.0), PI, "spotter")
	var buddy: Enemy = _spawn(&"hollow", Vector3(0, 0.1, 40.0), 0.0, "buddy")
	var res: Dictionary = {"spotter": {"notice": -1.0, "how": "", "reach": -1.0}, "buddy": {"notice": -1.0, "how": "", "reach": -1.0}}
	var t: float = 0.0
	while t < TRIAL_LIMIT:
		_drive("walk")
		await get_tree().physics_frame
		t += 1.0 / float(Engine.physics_ticks_per_second)
		for k: String in ["spotter", "buddy"]:
			var e: Enemy = spotter if k == "spotter" else buddy
			var r: Dictionary = res[k]
			if float(r["notice"]) < 0.0 and _noticed(e):
				r["notice"] = t
				r["how"] = "s" if e.last_seen_time > -50.0 else "i"
			if float(r["reach"]) < 0.0 and _flat(e) < REACH:
				r["reach"] = t
		if float((res["buddy"] as Dictionary)["reach"]) >= 0.0 or (t > NOTICE_LIMIT and float((res["buddy"] as Dictionary)["notice"]) < 0.0):
			break
	await _teardown()
	return res
