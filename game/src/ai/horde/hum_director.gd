class_name HumDirector
extends Node
## The Hum (horde nights, novel system #2 with HordeMemory). At 22:00 on a Hum day it reads the
## horde memory's plan — waves, sectors, roles, mix — spawns the waves around the base over the
## night, keeps one shared FlowField toward the player (rebuilt on a worker thread as walls
## change), tallies per-sector deaths and breaches, and at the end files the night's report so the
## next Hum adapts (flanks killing fields, sieges the wall that held, escalates fast clears).
## The same plan, generated ahead with the day's RNG stream, is the tether's Hum forecast.

var ai: Node = null
var active: bool = false
var day: int = 0
var plan: Dictionary = {}
var base := Vector3.ZERO
var report: Dictionary = {}
var members: Dictionary = {}
var flow: FlowField = null

var _cfg: Dictionary = {}
var _started_min: float = 0.0
var _wave_i: int = 0
var _queue: Array[Dictionary] = []
var _flow_task: int = -1
var _flow_next: FlowField = null
var _flow_t: float = 0.0
var _spawned_total: int = 0
## player id -> deaths when the night began (a death during it forfeits the survival award).
var _deaths_at_start: Dictionary = {}


func _ready() -> void:
	_cfg = Content.config(&"horde")
	Events.horde_night_started.connect(_on_start)
	Events.horde_night_ended.connect(_on_end)
	Events.horde_night_warning.connect(_on_warning)
	Events.enemy_killed.connect(_on_enemy_killed)
	Events.structure_destroyed.connect(_on_structure_destroyed)
	Events.session_started.connect(_resume_if_inside)


## A game loaded (or started) inside the Hum window would otherwise never see the start event:
## pick the night back up, with the clock counted from 22:00 so overdue waves queue at once.
func _resume_if_inside(_new_game: bool) -> void:
	var c: WorldClock = Game.session.clock if Game.session != null else null
	if c == null or active or not c.is_horde_active():
		return
	var d: int = c.day() if c.hour_f() >= c.horde_start_hour else c.day() - 1
	_on_start(d)
	_started_min = float(d - 1) * WorldClock.MIN_PER_DAY + c.horde_start_hour * 60.0


func _rng_for(d: int) -> RandomNumberGenerator:
	return Game.session.rng.keyed("hum:%d" % d)


func _gamestage() -> int:
	var p: PlayerState = Game.local_player()
	return Game.session.gamestage(p)


func _exit_tree() -> void:
	if _flow_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_flow_task)
		_flow_task = -1


## The plan the next Hum will follow (deterministic), for warnings and the tether.
func forecast() -> Dictionary:
	var c: WorldClock = Game.session.clock
	var d: int = c.next_horde_day(c.day() if not c.is_horde_active() else c.day() + 1)
	var p: Dictionary = Game.session.horde.plan(_gamestage(), _rng_for(d))
	p["day"] = d
	p["hours_until"] = c.hours_until_horde()
	return p


func _on_warning(d: int, hours_left: float) -> void:
	var f: Dictionary = forecast()
	var line: String = (f.get("tactics", []) as Array).front() if not (f.get("tactics", []) as Array).is_empty() else ""
	if hours_left <= 1.5:
		Events.player_status_message.emit("The ground has started to hum. Within the hour, they come.", &"danger")
	elif hours_left <= 7.0:
		Events.player_status_message.emit("The Hum tonight. %s" % line, &"warning")
	else:
		Events.player_status_message.emit("Tether: Hum forecast for day %d — %s" % [d, line], &"info")


func _on_start(d: int) -> void:
	if active:
		return
	day = d
	active = true
	base = _find_base()
	plan = Game.session.horde.plan(_gamestage(), _rng_for(d))
	report = {"day": d, "spawned": _zeros(), "killed": _zeros(), "breaches": _zeros(), "causes": {}, "total": int(plan.get("total", 0))}
	members.clear()
	_queue.clear()
	_wave_i = 0
	_spawned_total = 0
	_deaths_at_start.clear()
	for pid: StringName in Game.session.players:
		_deaths_at_start[pid] = (Game.session.players[pid] as PlayerState).deaths
	_started_min = Game.session.clock.total_minutes
	flow = null
	_rebuild_flow()
	Audio.play_2d(&"music/hum_start", -2.0, &"Music")
	Events.player_status_message.emit("THE HUM HAS BEGUN.", &"danger")


func _on_end(_d: int, _r: Dictionary) -> void:
	if not active:
		return
	active = false
	var alive: int = 0
	for id: StringName in members:
		var e: Enemy = members[id]["node"] if members[id].has("node") else null
		if e != null and is_instance_valid(e) and e.is_alive():
			alive += 1
			e.release_from_horde()
	var total: int = maxi(1, _spawned_total)
	report["clear_time"] = clampf(float(alive) / float(total) + 0.2 * float(_queue.size()) / float(total), 0.0, 1.0)
	Game.session.horde.record_night(report)
	var survived: int = int(Game.session.stats.get("hums_survived", 0)) + 1
	Game.session.stats["hums_survived"] = survived
	# Everyone still standing at dawn earns it; each later Hum pays half again more.
	for pid: StringName in Game.session.players:
		var ps: PlayerState = Game.session.players[pid]
		# Not one who died during the night and stood up again at their bed (first-week audit W7).
		if ps.stats.alive and ps.deaths <= int(_deaths_at_start.get(pid, ps.deaths)):
			ps.progression.award("survive_hum", 1.0 + 0.5 * float(survived - 1))
	# First of the dawn's lines (the drop, the autosave, a level-up follow it): StatusFeed paces them.
	Events.status_message_queued.emit("The Hum fades. %d of them came; %d lie still." % [_spawned_total, _sum(report["killed"])], &"info", StatusFeed.PRIORITY_REPORT)
	members.clear()
	_queue.clear()
	flow = null


func _process(delta: float) -> void:
	if not active or Game.session == null:
		return
	var elapsed: float = Game.session.clock.total_minutes - _started_min
	var waves: Array = plan.get("waves", [])
	while _wave_i < waves.size() and float(waves[_wave_i]["start_min"]) <= elapsed:
		var w: Dictionary = waves[_wave_i]
		for enemy_id: Variant in (w["units"] as Dictionary).keys():
			for i: int in int(w["units"][enemy_id]):
				_queue.append({"enemy": StringName(str(enemy_id)), "sector": int(w["sector"]), "role": str(w["role"])})
		_wave_i += 1
		Audio.play_2d(&"music/hum_wave", -6.0, &"Music")
	var cap: int = GameRules.current().integer("hum_max_alive")
	var spawned_now: int = 0
	while not _queue.is_empty() and _alive_count() < cap and spawned_now < 3:
		_spawn(_queue.pop_front())
		spawned_now += 1
	_flow_t += delta
	if _flow_task >= 0 and WorkerThreadPool.is_task_completed(_flow_task):
		WorkerThreadPool.wait_for_task_completion(_flow_task)
		_flow_task = -1
		flow = _flow_next
	if _flow_t > 3.0 and _flow_task < 0:
		_flow_t = 0.0
		_rebuild_flow()


func _alive_count() -> int:
	var n: int = 0
	for id: StringName in members:
		var e: Variant = members[id].get("node")
		if e != null and is_instance_valid(e) and (e as Enemy).is_alive():
			n += 1
	return n


func _spawn(u: Dictionary) -> void:
	var sector: int = int(u["sector"])
	var rng: RandomNumberGenerator = Game.session.rng.stream("hum_spawn")
	var r: Array = _cfg.get("spawn_radius", [55.0, 85.0])
	var pos := Vector3.INF
	for attempt: int in 12:
		var dir: Vector3 = HordeMemory.sector_dir(sector).rotated(Vector3.UP, rng.randf_range(-0.35, 0.35))
		if str(u["role"]) == "flank":
			dir = dir.rotated(Vector3.UP, 0.6 * (1.0 if rng.randf() < 0.5 else -1.0))
		# Later tries widen the arc; every try must pass the shared spawn rules (dry, not inside
		# a building or the base, not on a cliff, never on top of the player).
		dir = dir.rotated(Vector3.UP, rng.randf_range(-0.12, 0.12) * float(attempt))
		var cand: Vector3 = base + dir * rng.randf_range(float(r[0]), float(r[1]))
		cand.y = Game.world.height_at(cand.x, cand.z)
		if ai == null or not ai.has_method(&"spawn_point_ok") or bool(ai.call(&"spawn_point_ok", cand)):
			pos = cand
			break
	if pos == Vector3.INF:
		_queue.append(u)  # try again next frame from a fresh angle
		return
	var e: Enemy = ai.call(&"spawn", u["enemy"], pos + Vector3.UP * 0.3, {"horde_sector": sector})
	if e == null:
		return
	members[e.entity_id] = {"sector": sector, "node": e, "role": u["role"]}
	(report["spawned"] as Array)[sector] = int(report["spawned"][sector]) + 1
	_spawned_total += 1


func direction(pos: Vector3) -> Vector3:
	if flow != null and flow.ready:
		return flow.direction_at(pos)
	var p: Player = Game.world.player if Game.world != null else null
	var tgt: Vector3 = p.global_position if p != null else base
	var d: Vector3 = tgt - pos
	d.y = 0.0
	return d.normalized() if d.length() > 0.5 else Vector3.ZERO


func _rebuild_flow() -> void:
	var w: Node = Game.world
	if w == null or w.player == null:
		return
	var cfg: Dictionary = _cfg.get("flow_field", {})
	var f := FlowField.new()
	f.setup(base, float(_cfg.get("spawn_radius", [55.0, 85.0])[1]) + 10.0, float(cfg.get("cell", 1.5)))
	var pieces: Array = []
	var building: Node = w.get(&"building")
	if building != null:
		for p: StructurePiece in building.call(&"pieces_in_radius", base, f.cell * f.n * 0.5):
			if p.is_log():
				var seg: PackedVector3Array = LogSnapper.segment(p.global_transform)
				pieces.append({"a": seg[0], "b": seg[1], "hp": p.hp})
			else:
				pieces.append({"a": p.global_position, "b": p.global_position, "hp": p.hp})
	# A player in a cave is reached through its mouth (TD-279: the field is one surface layer).
	var targets: Array[Vector3] = FlowField.surface_targets([(w.player as Node3D).global_position], w.get(&"terrain"))
	# Buildings the horde should walk around (not the one the player is sheltering in).
	var houses: Array = []
	var pois: Node = w.get(&"pois")
	if pois != null:
		var inside: PoiInstance = pois.call(&"poi_at", (w.player as Node3D).global_position) as PoiInstance
		for inst: PoiInstance in (pois.get(&"instances") as Dictionary).values():
			if inst != inside and inst.global_position.distance_to(base) < f.cell * f.n:
				houses.append({"xf": inst.global_transform, "rect": inst.layout.extent()})
	var height_fn: Callable = w.height_at
	var wsys: Node = w.get(&"water")
	var water_fn: Callable = Callable(wsys, &"water_level_at") if wsys != null and wsys.has_method(&"water_level_at") else Callable()
	var max_slope: float = float(cfg.get("slope_max_deg", 42.0))
	var per_hp: float = float(cfg.get("structure_cost_per_hp", 0.02))
	# A build still in flight (the Hum ended mid-build, then a new one starts) is joined before its
	# handle is overwritten, so no task is left unjoined.
	if _flow_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_flow_task)
		_flow_task = -1
	_flow_next = f
	var job := func() -> void:
		f.build_terrain(height_fn, water_fn, max_slope)
		f.add_buildings(houses)
		f.add_structures(pieces, per_hp)
		f.integrate(targets)
	_flow_task = WorkerThreadPool.add_task(job, false, "hum flow field")


## The base is the centroid of player structures near the player (or the player themself).
func _find_base() -> Vector3:
	var p: Player = Game.world.player
	var pos: Vector3 = p.global_position
	var building: Node = Game.world.get(&"building")
	if building == null:
		return pos
	var near: Array = building.call(&"pieces_in_radius", pos, float(_cfg.get("base_search_radius", 40.0)))
	if near.is_empty():
		return pos
	var sum := Vector3.ZERO
	for s: StructurePiece in near:
		sum += s.global_position
	return sum / float(near.size())


func _on_enemy_killed(entity_id: StringName, _enemy_id: StringName, _pos: Vector3, killer: Dictionary) -> void:
	if not active or not members.has(entity_id):
		return
	# A kill out on an approach marks that approach a killing field; one at the walls counts for
	# the sector the attacker came from.
	var s: int = int(members[entity_id]["sector"])
	if _pos.distance_to(base) > 8.0:
		s = HordeMemory.sector_of(base, _pos)
	(report["killed"] as Array)[s] = int(report["killed"][s]) + 1
	var cause: String = str(killer.get("cause", "melee"))
	var causes: Dictionary = report["causes"]
	causes[cause] = int(causes.get(cause, 0)) + 1


func _on_structure_destroyed(_piece_id: StringName, _def_id: StringName, pos: Vector3) -> void:
	if not active:
		return
	var s: int = HordeMemory.sector_of(base, pos)
	(report["breaches"] as Array)[s] = int(report["breaches"][s]) + 1


static func _zeros() -> Array:
	var a: Array = []
	a.resize(HordeMemory.SECTORS)
	a.fill(0)
	return a


static func _sum(a: Array) -> int:
	var t: int = 0
	for v: Variant in a:
		t += int(v)
	return t
