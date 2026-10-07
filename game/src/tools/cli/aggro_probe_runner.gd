extends Node
## Aggro probe logic (see aggro_probe.gd).

const DISTANCES: Array[float] = [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0]


func _ready() -> void:
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
	if args_has("--diag"):
		await get_tree().physics_frame
		var st: Stimuli = Stimuli.current
		var light: float = st.light_at(p.global_position + Vector3.UP)
		var base: float = e.def.perc("sight_night" if e.is_night() else "sight_day", 15.0)
		var r: float = st.detection_range(base, light, false, 0.0, false, p.state.progression.modifier("visibility_mult"))
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
