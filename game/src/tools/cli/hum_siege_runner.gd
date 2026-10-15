extends Node
## hum_siege.gd's work: see there.

const STREET := Vector3(-45, 1.7, 2068)
const STUCK_WINDOW: float = 10.0
const STUCK_MOVE: float = 1.0
const NEAR_WALL: float = 8.0

var _mode: String = "house"
var _secs: float = 240.0
var _out: String = "user://hum_siege"
var w: Node
var p: Node3D
var _ai: Node
var _inst: PoiInstance = null
var _hut: Vector3 = Vector3.INF


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < args.size():
		match args[i]:
			"--mode":
				i += 1
				_mode = args[i]
			"--secs":
				i += 1
				_secs = float(args[i])
			"--out":
				i += 1
				_out = args[i]
		i += 1
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "qa_humsiege",
		"rules": {"hum_max_alive": 40, "hum_size": 1.5}})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	w = game.world
	p = w.player
	p.set(&"god_mode", true)
	p.set(&"input_enabled", false)
	p.global_position = Vector3(STREET.x, w.height_at(STREET.x, STREET.z) + 0.1, STREET.z)
	w.terrain.update_streaming(p.global_position, true)
	for k: int in 240:
		await get_tree().process_frame
	var where: String = _place_house() if _mode == "house" else _place_shelter()
	if where == "":
		print("[siege] no place to hole up")
		get_tree().quit(1)
		return
	print("[siege] %s" % where)
	# Let the nav tiles round it bake.
	for k: int in 600:
		await get_tree().physics_frame
	_ai = w.get(&"ai")
	var day: int = game.session.clock.next_horde_day(1)
	game.session.clock.set_time(day, 21.98)
	var t0: int = Time.get_ticks_msec() + 900000
	while not bool(_ai.hum.active) and Time.get_ticks_msec() < t0:
		await get_tree().process_frame
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	game.session.horde.horde_index = 3
	var plan: Dictionary = game.session.horde.plan(40, rng)
	_ai.hum.set(&"_wave_i", 0)
	for wv: Dictionary in plan.get("waves", []):
		wv["start_min"] = 0.0
	_ai.hum.plan = plan
	print("[siege] hum active %s, plan %d" % [_ai.hum.active, int(plan.get("total", 0))])
	await _watch()
	get_tree().quit(0)


## A loaded town house with an outside door and windows on the ground floor; the player in the
## room cell farthest from its openings.
func _place_house() -> String:
	var best: PoiInstance = null
	var best_score: float = -1.0
	for inst: PoiInstance in (w.pois.get(&"instances") as Dictionary).values():
		if inst.layout == null or inst.global_position.distance_to(p.global_position) > 120.0:
			continue
		var doors: int = 0
		var windows: int = 0
		var boarded: int = 0
		for op: Dictionary in inst.layout.openings:
			if int(op["level"]) != 0:
				continue
			if PoiLayout.is_window(str(op["type"])):
				windows += 1
				boarded += 1 if str(op["state"]) == "boarded" else 0
			elif str(op["type"]).begins_with("door"):
				doors += 1
		if doors == 0 or windows < 2:
			continue
		var score: float = float(windows) + 2.0 * float(mini(boarded, 1)) - inst.global_position.distance_to(p.global_position) / 100.0
		if score > best_score:
			best_score = score
			best = inst
	if best == null:
		return ""
	_inst = best
	var lay: PoiLayout = best.layout
	var lv: Dictionary = lay.levels.get(0, {})
	var far_c := Vector2i(-1, -1)
	var far_d: float = -1.0
	for y: int in int(lv.get("d", 0)):
		for x: int in (lv["plan"] as PackedStringArray)[y].length():
			var c := Vector2i(x, y)
			if not lay.is_room(lay.room_at(0, c)):
				continue
			var near: float = INF
			for op: Dictionary in lay.openings:
				if int(op["level"]) == 0:
					near = minf(near, Vector2(c).distance_to(Vector2(op["edge"])))
			if near > far_d:
				far_d = near
				far_c = c
	var at: Vector3 = best.to_global(Vector3(lay.origin.x + far_c.x + 0.5, lay.level_y(0) + 0.1, lay.origin.y + far_c.y + 0.5))
	p.global_position = at
	var states: PackedStringArray = []
	for op: Dictionary in lay.openings:
		if int(op["level"]) == 0:
			states.append("%s %s %s" % [op["id"], op["type"], best.piece_state(str(op["id"]), str(op["state"]))])
	return "house %s, player at cell %s (%.1f cells from an opening); ground-floor openings: %s" % [best.instance_id, far_c, far_d, ", ".join(states)]


## A sealed 4 x 4 m hut of logs six courses high (2 m), 20 m off the street on the flattest ground.
func _place_shelter() -> String:
	var bm: Node = w.get(&"building")
	var def: StructureDef = Content.structure(&"log_piece")
	var c: Vector3 = Vector3(STREET.x + 20.0, 0.0, STREET.z)
	c.y = w.height_at(c.x, c.z)
	var n: int = 0
	for k: int in 6:
		var y: float = c.y + 0.17 + 0.34 * float(k)
		for side: Array in [[Vector3(0, 0, 2.0), 0.0], [Vector3(0, 0, -2.0), 0.0], [Vector3(2.0, 0, 0), PI * 0.5], [Vector3(-2.0, 0, 0), PI * 0.5]]:
			var at: Vector3 = Vector3(c.x, y, c.z) + (side[0] as Vector3)
			bm.call(&"_spawn_piece", StringName("s:siege_%d" % n), def, Transform3D(Basis(Vector3.UP, float(side[1])), at), def.hp)
			n += 1
	_hut = c
	p.global_position = c + Vector3.UP * 0.1
	return "shelter: %d logs (%d hp each) round (%.1f, %.1f), ground %.2f" % [n, int(def.hp), c.x, c.z, c.y]


func _inside(pos: Vector3) -> bool:
	if _inst != null:
		return _inst.is_indoors(pos)
	return absf(pos.x - _hut.x) < 1.8 and absf(pos.z - _hut.z) < 1.8


func _dist_to_target(pos: Vector3) -> float:
	if _inst != null:
		var b: AABB = _inst.world_bounds()
		var q := Vector3(clampf(pos.x, b.position.x, b.end.x), pos.y, clampf(pos.z, b.position.z, b.end.z))
		return Vector2(pos.x - q.x, pos.z - q.z).length()
	return maxf(0.0, Vector2(pos.x - _hut.x, pos.z - _hut.z).length() - 2.0)


func _watch() -> void:
	var t: float = 0.0
	var hist: Dictionary = {}        # body -> [[t, pos], ...]
	var how: Dictionary = {}         # body -> last "window"/"break:<id>"/... before inside
	var entered: Dictionary = {}     # body -> [t, how]
	var stuck_eps: Dictionary = {}   # body -> true once counted
	var stuck_now: int = 0
	var stuck_max: int = 0
	var stuck_bodies: Dictionary = {}
	var ang_sum: float = 0.0
	var ang_n: int = 0
	var ang_far: int = 0
	var frame_ms: PackedFloat32Array = []
	var states: Dictionary = {}
	var first_in: float = -1.0
	var reached: Dictionary = {}     # body -> t when within 2.5 m of the player
	var near_max: int = 0
	Enemy.prof = {}
	Enemy.prof_on = true
	# Hits that land (through a wall or not): god mode drops damage, so it is off and the health
	# is topped up each frame; a drop is a hit.
	p.set(&"god_mode", false)
	var stats: Object = (p.get(&"state") as Object).get(&"stats")
	var hits: int = 0
	var first_hit: float = -1.0
	var frames: int = 0
	var next_log: float = 0.0
	while t < _secs:
		await get_tree().physics_frame
		frames += 1
		var dt: float = get_physics_process_delta_time()
		t += dt
		if float(stats.get(&"health")) < float(stats.get(&"max_health")) - 0.01:
			hits += 1
			if first_hit < 0.0:
				first_hit = t
		stats.set(&"health", stats.get(&"max_health"))
		stats.set(&"alive", true)
		frame_ms.append(float(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) + Performance.get_monitor(Performance.TIME_PROCESS)) * 1000.0)
		stuck_now = 0
		var near: int = 0
		for m: Dictionary in (_ai.hum.members as Dictionary).values():
			var e: Enemy = m.get("node") as Enemy if is_instance_valid(m.get("node")) else null
			if e == null or not e.is_alive():
				continue
			var pos: Vector3 = e.global_position
			var dist: float = _dist_to_target(pos)
			if dist < 30.0:
				near += 1
			var st: String = Enemy.State.keys()[e.state]
			states[st] = int(states.get(st, 0)) + 1
			if e.state == Enemy.State.VAULT:
				how[e] = "window vault"
			elif e.state == Enemy.State.BREAK and e.break_target != null and is_instance_valid(e.break_target):
				var pid: Variant = e.break_target.get(&"piece_id")
				how[e] = "break %s" % (str(pid) if pid != null else String(e.break_target.name))
			if not reached.has(e) and Vector2(pos.x - p.global_position.x, pos.z - p.global_position.z).length() < 2.5 \
					and absf(pos.y - p.global_position.y) < 1.5:
				reached[e] = t
			if _inside(pos):
				if not entered.has(e):
					entered[e] = [t, how.get(e, "walked in")]
					if first_in < 0.0:
						first_in = t
				continue
			# Stuck: near the walls, not tearing / vaulting / striking, under STUCK_MOVE m in STUCK_WINDOW s.
			var hlist: Array = hist.get(e, [])
			hlist.append([t, pos])
			while hlist.size() > 1 and t - float(hlist[0][0]) > STUCK_WINDOW:
				hlist.pop_front()
			hist[e] = hlist
			if dist < NEAR_WALL and e.state not in [Enemy.State.BREAK, Enemy.State.VAULT, Enemy.State.ATTACK, Enemy.State.STAGGER] \
					and t - float(hlist[0][0]) >= STUCK_WINDOW * 0.98 and (hlist[0][1] as Vector3).distance_to(pos) < STUCK_MOVE:
				stuck_now += 1
				stuck_bodies[e] = true
				if not stuck_eps.has(e):
					stuck_eps[e] = [t, st, pos]
			# Flow field vs this body's own nav path (horde bodies near the target).
			if e.state == Enemy.State.HORDE and dist < 40.0 and e.agent != null and not e.agent.is_navigation_finished():
				var flow: Vector3 = _ai.call(&"horde_direction", pos)
				var nv: Vector3 = e.agent.get_next_path_position() - pos
				nv.y = 0.0
				if flow.length() > 0.1 and nv.length() > 0.3:
					var a: float = rad_to_deg(Vector2(flow.x, flow.z).angle_to(Vector2(nv.x, nv.z)))
					ang_sum += absf(a)
					ang_n += 1
					ang_far += 1 if absf(a) > 90.0 else 0
		stuck_max = maxi(stuck_max, stuck_now)
		near_max = maxi(near_max, near)
		if t > next_log:
			next_log = t + 20.0
			print("[siege] t %.0f s: alive %d, within 30 m %d, inside %d, stuck now %d" % [t, _ai.hum.call(&"_alive_count"), near, entered.size(), stuck_now])
	Enemy.prof_on = false
	var sorted: PackedFloat32Array = frame_ms.duplicate()
	sorted.sort()
	var ways: Dictionary = {}
	for e: Variant in entered:
		var hw: String = str(entered[e][1])
		ways[hw] = int(ways.get(hw, 0)) + 1
	var eps: Array = []
	for e: Variant in stuck_eps:
		var ep: Array = stuck_eps[e]
		eps.append("%s at (%.0f, %.0f) t %.0f" % [ep[1], (ep[2] as Vector3).x, (ep[2] as Vector3).z, ep[0]])
	var sections: Dictionary = {}
	for k: Variant in Enemy.prof:
		sections[str(k)] = snappedf(float(Enemy.prof[k]) / 1000.0 / float(maxi(frames, 1)), 0.01)
	var first_reach: float = -1.0
	for e: Variant in reached:
		first_reach = float(reached[e]) if first_reach < 0.0 else minf(first_reach, float(reached[e]))
	var report: Dictionary = {
		"hits_on_player": hits, "first_hit_s": snappedf(first_hit, 0.1), "reached_player": reached.size(), "first_reach_s": snappedf(first_reach, 0.1),
		"mode": _mode, "secs": _secs, "first_in_s": snappedf(first_in, 0.1), "inside": entered.size(), "ways_in": ways,
		"stuck_10s_bodies": stuck_eps.size(), "stuck_max_at_once": stuck_max, "stuck_first": eps.slice(0, 8),
		"flow_vs_nav_mean_deg": snappedf(ang_sum / maxf(1.0, float(ang_n)), 0.1), "flow_vs_nav_over_90_share": snappedf(float(ang_far) / maxf(1.0, float(ang_n)), 0.001),
		"flow_vs_nav_samples": ang_n, "near_max": near_max,
		"frame_ms_p50": snappedf(sorted[sorted.size() / 2], 0.01), "frame_ms_p95": snappedf(sorted[int(sorted.size() * 0.95)], 0.01),
		"frame_ms_worst": snappedf(sorted[sorted.size() - 1], 0.01), "enemy_sections_ms_per_frame": sections,
		"state_frames": states}
	print("[siege] ", JSON.stringify(report))
	var f := FileAccess.open(_out.path_join("report_%s.json" % _mode), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
