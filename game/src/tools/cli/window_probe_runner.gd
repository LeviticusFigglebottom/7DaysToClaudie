extends Node
## Window probe logic (see window_probe.gd). A new game on the main map; for each of the nearest
## built houses with window links (up to --trials windows, one per house), the player stands 2.5 m
## inside a ground-floor window and a Hollow 8 m outside it is set hunting them (it knows where
## they are). Over 40 s it reports what it did: tore at the window (VAULT), at something else
## (BREAK: a door, a wall), climbed in, and whether it reached the player indoors.

const LIMIT: float = 40.0


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var trials: int = 6
	var i: int = args.find("--trials")
	if i >= 0 and i + 1 < args.size():
		trials = int(args[i + 1])
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "qa_window_probe"})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	var w: GameWorld = game.world
	var p: Player = w.player
	p.god_mode = true
	Game.session.clock.set_time(Game.session.clock.day(), 12.0)
	var done: int = 0
	var tried: Dictionary = {}
	var start: Vector3 = p.global_position
	while done < trials:
		var inst: PoiInstance = _nearest_with_links(w, start, tried)
		if inst == null:
			print("[window] no more houses with window links near %s" % start)
			break
		tried[inst.instance_id] = true
		var r: String = await _trial(w, p, inst)
		print("[window] %-32s %s" % [inst.instance_id, r])
		done += 1
	get_tree().quit(0)


func _nearest_with_links(w: GameWorld, at: Vector3, tried: Dictionary) -> PoiInstance:
	var best: PoiInstance = null
	var bd: float = INF
	for inst: PoiInstance in (w.pois.get(&"instances") as Dictionary).values():
		if tried.has(inst.instance_id) or (inst.get(&"_window_links") as Array).is_empty():
			continue
		var d: float = inst.global_position.distance_to(at)
		if d < bd:
			bd = d
			best = inst
	return best


func _trial(w: GameWorld, p: Player, inst: PoiInstance) -> String:
	var rid: RID = (inst.get(&"_window_links") as Array)[0]
	var info: Dictionary = WindowLinks.info(rid)
	var outside: Vector3 = NavigationServer3D.link_get_start_position(rid)
	var inside: Vector3 = NavigationServer3D.link_get_end_position(rid)
	var inward: Vector3 = Vector3(inside.x - outside.x, 0, inside.z - outside.z).normalized()
	p.global_position = inside + inward * 2.5 + Vector3.UP * 0.1
	p.velocity = Vector3.ZERO
	# The nav tiles round the house bake on workers once the player is here: wait (up to 60 s) until
	# the mesh is under the window on both sides.
	var map: RID = w.get_world_3d().navigation_map
	for f: int in 3600:
		await get_tree().physics_frame
		p.global_position = inside + inward * 2.5 + Vector3.UP * 0.1
		if f > 60 and NavigationServer3D.map_get_closest_point(map, outside).distance_to(outside) < 1.0 \
				and NavigationServer3D.map_get_closest_point(map, inside).distance_to(inside) < 1.0:
			break
	var at: Vector3 = outside - inward * 8.0
	at.y = w.height_at(at.x, at.z) + 0.1
	var target: Vector3 = p.global_position
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, at, target, true)
	var via: bool = false
	for q: Vector3 in path:
		via = via or q.distance_to(outside) < 1.0 or q.distance_to(inside) < 1.0
	print("[window]   diag: outside off mesh %.2f, inside off mesh %.2f, player off mesh %.2f, path %d points (ends %.1f m from player), via link %s" % [
		NavigationServer3D.map_get_closest_point(map, outside).distance_to(outside),
		NavigationServer3D.map_get_closest_point(map, inside).distance_to(inside),
		NavigationServer3D.map_get_closest_point(map, target).distance_to(target),
		path.size(), path[path.size() - 1].distance_to(target) if not path.is_empty() else -1.0, via])
	var e: Enemy = w.ai.call(&"spawn", &"hollow", at, {"authored": true}) as Enemy
	if e == null:
		return "no spawn"
	await get_tree().physics_frame
	var states: Dictionary = {}
	var reached: float = -1.0
	var t: float = 0.0
	var dt: float = 1.0 / float(Engine.physics_ticks_per_second)
	while t < LIMIT:
		e.last_seen_time = e._now() + 5.0
		e.target_pos = p.global_position
		if e.state in [Enemy.State.IDLE, Enemy.State.WANDER, Enemy.State.INVESTIGATE]:
			e._set_state(Enemy.State.CHASE)
		await get_tree().physics_frame
		t += dt
		states[Enemy.State.keys()[e.state]] = true
		if e.state == Enemy.State.BREAK and e.break_target != null:
			states["BREAK:" + str(e.break_target.get(&"piece_id") if e.break_target.get(&"piece_id") != null else e.break_target.name)] = true
		var d: Vector3 = e.global_position - p.global_position
		if inst.is_indoors(e.global_position) and Vector2(d.x, d.z).length() < 2.2:
			reached = t
			break
	var broke: Array[String] = []
	for b: Variant in info["pieces"]:
		if b != null and is_instance_valid(b) and (b as PoiPieces.Breakable).is_broken():
			broke.append((b as PoiPieces.Breakable).kind)
	var r: String = "window %s sill %.2f: %s, broke %s, %s" % [info["opening"], float(info["sill"]) - inside.y,
		",".join(states.keys()), broke, ("reached indoors in %.1f s" % reached) if reached >= 0.0 else "NOT in (at %s)" % e.global_position]
	w.ai.call(&"despawn", e)
	return r
