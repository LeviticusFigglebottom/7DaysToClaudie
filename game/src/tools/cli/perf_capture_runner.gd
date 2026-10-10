extends Node
## Perf capture logic (loaded by perf_capture.gd once autoloads exist). See perf_capture.gd.

const VIEWS: Array[Dictionary] = [
	{"name": "drop_site", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296)},
	{"name": "forest", "pos": Vector3(-201, 1.8, 2227), "look": Vector3(-160, 3, 2200)},
	{"name": "town_street", "pos": Vector3(-45, 1.7, 2068), "look": Vector3(-95, 2, 2064)},
	{"name": "town_road", "pos": Vector3(-30, 6.0, 2170), "look": Vector3(-60, 0, 2070)},
	{"name": "river", "pos": Vector3(150, 1.7, 2075), "look": Vector3(118, 0.0, 2100)},
	# Caves WS-F: deep conifer forest away from every place (the scatter at its densest).
	{"name": "dense_forest", "pos": Vector3(300, 1.7, 1650), "look": Vector3(340, 3.0, 1610)},
]
## Caves WS-F: Larch Hollow's grotto, from its mouth and from its chamber (ADR-0056).
const CAVE_VIEW: StringName = &"larch_hollow_grotto"

var _out: String = "res://../build/perf"
var _frames: int = 120
var _ablate: bool = true
## Quit once the load's report and its first frames in the world are logged (LoadMeter).
var _load_only: bool = false
## Start the main map built whole (GameWorld.poi_ring off): the after-spawn window then shows what
## isn't the ring's background builds.
var _poi_whole: bool = false
## Also measure a Hum night at the town (--hum): the horde's waves on the main thread (TD-003).
var _hum: bool = false
## --hum-full: the night's plan is a late game's (gamestage HUM_FULL_STAGE), every wave is due at
## once and the alive cap is the rule's maximum, so a whole horde is measured, not the first few.
var _hum_full: bool = false
const HUM_FULL_STAGE: int = 60
## Headless triangle census per view (what each layer submits within its visibility range).
var _census: bool = false
var _model_of: Dictionary = {}
var _report: Dictionary = {}
var w: GameWorld
var p: Player
## Stamps taken first and last in every process and physics step (process priorities sort the
## whole tree), so their difference is the step's script time on the main thread.
var _first: Stamp
var _last: Stamp


class Stamp:
	extends Node
	var proc_us: int = 0
	var phys_us: int = 0
	func _process(_d: float) -> void:
		proc_us = Time.get_ticks_usec()
	func _physics_process(_d: float) -> void:
		phys_us = Time.get_ticks_usec()


func _stamps() -> void:
	_first = Stamp.new()
	_first.process_priority = -1000000
	_first.process_physics_priority = -1000000
	_last = Stamp.new()
	_last.process_priority = 1000000
	_last.process_physics_priority = 1000000
	get_tree().root.add_child(_first)
	get_tree().root.add_child(_last)


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--out":
				_out = args[i + 1]
			"--frames":
				_frames = int(args[i + 1])
			"--no-ablate":
				_ablate = false
			"--load-only":
				_load_only = true
			"--poi-whole":
				_poi_whole = true
			"--census":
				_census = true
			"--hum":
				_hum = true
			"--hum-full":
				_hum = true
				_hum_full = true
			"--no-crowd":
				Crowd.enabled = false  # TD-011: the Hum without separation steering, to compare
			"--crowd":
				Crowd.enabled = true  # TD-011: with it (off by default)
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var rules: Dictionary = {"hum_max_alive": 64, "hum_size": 2.0} if _hum_full else {}
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "perf", "rules": rules, "poi_ring": not _poi_whole})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	w = game.world
	p = w.player
	if _load_only:
		for i: int in 40:
			await get_tree().process_frame
		# How long the building ring takes to raise everything in range after the spawn (a world
		# that builds by distance: the main map's background builds, a streamed world's ring).
		var pm: Node = w.get(&"pois")
		if pm != null:
			var t0: int = Time.get_ticks_msec()
			var worst: float = 0.0
			var mem0: Dictionary = _mem()
			# The ring's steps run in each frame (a world built whole runs its own StepRunner).
			var ran: Array = []
			var own: Variant = pm.get(&"_own_steps")
			if own == null and pm.has_method(&"_ring_steps"):
				own = pm.call(&"_ring_steps")
			if own is StepRunner:
				(own as StepRunner).step_ran.connect(func(n: String, us: int, _f: bool) -> void: ran.append("%s %.1f" % [n, us / 1000.0]))
			var slow: Array = []
			# Each module's own _process time (StreamMeter.note, over 2 ms) in the slow frames.
			if StreamMeter.current == null:
				StreamMeter.current = StreamMeter.new()
				StreamMeter.current.log_windows = false
			var meter: StreamMeter = StreamMeter.current
			while Time.get_ticks_msec() - t0 < 600000:
				var t1: int = Time.get_ticks_usec()
				ran.clear()
				meter._frame_kinds.clear()
				await get_tree().process_frame
				var ks: Array = meter._frame_kinds.keys()
				ks.sort_custom(func(a: String, b: String) -> bool: return float(meter._frame_kinds[a]) > float(meter._frame_kinds[b]))
				for k: String in ks.slice(0, 9):
					if float(meter._frame_kinds[k]) >= 1.0:
						ran.append("%s %.1f" % [k, float(meter._frame_kinds[k])])
				var ms: float = float(Time.get_ticks_usec() - t1) / 1000.0
				worst = maxf(worst, ms)
				if ms > 33.0:
					slow.append([ms, "%.0f ms (process %.0f, physics %.0f): %s" % [ms, Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
						Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, ", ".join(ran) if not ran.is_empty() else "no ring steps"]])
				var steps: Variant = pm.get(&"_own_steps")
				var idle: bool = (pm.get(&"_jobs") as Dictionary).is_empty() and (steps == null or (steps as StepRunner).is_idle())
				# Built whole: the same 40 s window, for comparison.
				if (pm.get(&"registry") != null and idle) or (pm.get(&"registry") == null and Time.get_ticks_msec() - t0 > 40000):
					break
			slow.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]))
			print("[perf] frames over 33 ms while they rose: %d" % slow.size())
			for sl: Array in slow.slice(0, 12):
				print("[perf]   %s" % sl[1])
			print("[perf] buildings settled %.1f s after the spawn: %d built, %d in the registry; longest frame meanwhile %.0f ms" % [
				float(Time.get_ticks_msec() - t0) / 1000.0, (pm.get(&"instances") as Dictionary).size(), (pm.get(&"registry") as PoiRegistry).entries.size(), worst])
			# What the buildings rising added (TD-324: RSS grew ~165 MB over the window).
			var mem1: Dictionary = _mem()
			var grew: PackedStringArray = []
			for k: String in mem1:
				grew.append("%s %s -> %s" % [k, mem0[k], mem1[k]])
			print("[perf] memory at the spawn -> settled: %s" % ", ".join(grew))
		get_tree().quit(0)
		return
	_stamps()
	p.god_mode = true
	p.input_enabled = false
	game.session.clock.set_time(1, 12.0)
	_report["renderer"] = RenderingServer.get_video_adapter_name()
	_report["headless"] = DisplayServer.get_name() == "headless"
	_report["views"] = {}
	for v: Dictionary in VIEWS:
		await _goto(v["pos"], v["look"])
		var m: Dictionary = await _measure(_frames)
		if _census:
			m["census"] = _triangle_census(p.global_position + Vector3.UP * 1.65)
		if _ablate:
			m["modules"] = await _ablate_modules()
		_report["views"][v["name"]] = m
		print("[perf] %s %s" % [v["name"], _brief(m)])
	var ridge: Dictionary = _ridge_view()
	if not ridge.is_empty():
		await _goto(ridge["pos"], ridge["look"])
		await _coarse_settle()
		var mr: Dictionary = await _measure(_frames)
		mr["coarse_quads"] = int(w.vegetation.call(&"coarse_count"))
		if _census:
			mr["census"] = _triangle_census(p.global_position + Vector3.UP * 1.65)
		# The same view without the coarse forest (TD-006): its cost is the difference.
		w.vegetation.set(&"coarse_enabled", false)
		await get_tree().process_frame
		mr["without_coarse"] = await _measure(_frames)
		w.vegetation.set(&"coarse_enabled", true)
		_report["views"]["ridge"] = mr
		print("[perf] ridge %s coarse_quads=%d | without coarse: %s" % [_brief(mr), mr["coarse_quads"], _brief(mr["without_coarse"])])
	for cv: Dictionary in _cave_views():
		await _goto_at(cv["pos"], cv["look"])
		var mc: Dictionary = await _measure(_frames)
		_report["views"][cv["name"]] = mc
		print("[perf] %s %s" % [cv["name"], _brief(mc)])
	if _hum:
		_report["hum"] = await _hum_night()
		print("[perf] hum %s" % _brief(_report["hum"]))
	_report["sprint"] = await _sprint(Vector3(-300, 0, 2302), Vector3(1, 0, -0.35).normalized(), 20.0)
	print("[perf] sprint %s" % _brief(_report["sprint"]))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out))
	var path: String = ProjectSettings.globalize_path(_out).path_join("perf_%s.json" % ("headless" if _report["headless"] else "rendered"))
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(_report, "  "))
	f.close()
	print("[perf] done -> %s" % path)
	get_tree().quit(0)


func _goto(pos: Vector3, look: Vector3) -> void:
	p.global_position = Vector3(pos.x, w.height_at(pos.x, pos.z) + 0.1, pos.z)
	var d: Vector3 = look - pos
	p.rotation.y = atan2(-d.x, -d.z)
	p.head.rotation.x = clampf(atan2(look.y - 1.7 - (pos.y - w.height_at(pos.x, pos.z)), Vector2(d.x, d.z).length()), -1.2, 1.2)
	w.terrain.update_streaming(p.global_position, true)
	# Let streaming, scatter and POI sleepers settle before measuring.
	var end: int = Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame
		var veg: Node = w.vegetation
		if veg != null and veg.call(&"is_settled") and w.terrain.is_ready_around(p.global_position, 1):
			break
	for i: int in 30:
		await get_tree().process_frame


## The cave views: 8 m out from CAVE_VIEW's mouth looking in, and on its spine's last point (the
## chamber) looking back out. Empty when the world has no such cave.
func _cave_views() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var caves: Object = w.terrain.get(&"caves")
	if caves == null:
		return out
	for plan: Variant in caves.get(&"plans"):
		if StringName(str((plan as Object).get(&"id"))) != CAVE_VIEW:
			continue
		var mouth: Transform3D = (plan as Object).get(&"mouth")
		var spine: PackedVector3Array = (plan as Object).get(&"spine")
		var outside: Vector3 = mouth.origin + mouth.basis.z * 8.0
		out.append({"name": "cave_mouth", "pos": outside, "look": mouth.origin - mouth.basis.z * 4.0})
		if spine.size() > 2:
			out.append({"name": "cave_chamber", "pos": spine[spine.size() - 1], "look": mouth.origin})
	return out


## The ridge view (TD-006): the highest ground of the player's region within 160 m of its edge,
## looking out over the next regions (coarse on the main map: the far forest's cluster layer).
func _ridge_view() -> Dictionary:
	var rt: RegionTerrain = w.terrain.region_terrain_at(p.global_position.x, p.global_position.z)
	if rt == null:
		return {}
	var r: Rect2 = rt.rect
	var best := Vector3(0, -INF, 0)
	for z: float in range(int(r.position.y) + 16, int(r.end.y) - 16, 32):
		for x: float in range(int(r.position.x) + 16, int(r.end.x) - 16, 32):
			var edge: float = minf(minf(x - r.position.x, r.end.x - x), minf(z - r.position.y, r.end.y - z))
			var h: float = w.height_at(x, z)
			if edge < 160.0 and h > best.y:
				best = Vector3(x, h, z)
	if best.y == -INF:
		return {}
	var out_dir := Vector2(best.x, best.z) - r.get_center()
	out_dir = out_dir.normalized() if out_dir.length() > 1.0 else Vector2(1, 0)
	# _goto pitches by look.y + ground - 3.4 over the distance: about 2 degrees down.
	var look := Vector3(best.x + out_dir.x * 800.0, 3.4 - best.y - 30.0, best.z + out_dir.y * 800.0)
	return {"pos": Vector3(best.x, 1.7, best.z), "look": look}


## Waits (up to 60 s) for the coarse regions in view to be built.
func _coarse_settle() -> void:
	var veg: Node = w.vegetation
	if veg == null or not veg.has_method(&"coarse_pending"):
		return
	var end: int = Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame
		if int(veg.call(&"coarse_pending")) == 0 and int(veg.call(&"coarse_count")) > 0:
			break
	for i: int in 30:
		await get_tree().process_frame


## As _goto, standing on the ground below `pos` (a cave's floor) rather than on the surface.
func _goto_at(pos: Vector3, look: Vector3) -> void:
	var g: float = float(w.call(&"ground_below", pos + Vector3.UP * 1.0))
	p.global_position = Vector3(pos.x, (g if not is_nan(g) else w.height_at(pos.x, pos.z)) + 0.1, pos.z)
	var d: Vector3 = look - pos
	p.rotation.y = atan2(-d.x, -d.z)
	w.terrain.update_streaming(p.global_position, true)
	var end: int = Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame
		var veg: Node = w.vegetation
		if veg != null and veg.call(&"is_settled") and w.terrain.is_ready_around(p.global_position, 1):
			break
	for i: int in 60:
		await get_tree().process_frame


## Frame wall time, script process/physics time and render counts over n frames.
func _measure(n: int) -> Dictionary:
	var walls: PackedFloat32Array = []
	var proc: float = 0.0
	var phys: float = 0.0
	var dc: int = 0
	var prim: int = 0
	var objs: int = 0
	var last: int = Time.get_ticks_usec()
	for i: int in n:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		walls.append(float(now - last) / 1000.0)
		last = now
		proc += maxf(0.0, float(_last.proc_us - _first.proc_us) / 1000.0)
		phys += maxf(0.0, float(_last.phys_us - _first.phys_us) / 1000.0)
		dc += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
		prim += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
		objs += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)
	var sorted: PackedFloat32Array = walls.duplicate()
	sorted.sort()
	return {"frame_ms_avg": _avg(walls), "frame_ms_p95": sorted[int(n * 0.95)], "frame_ms_max": sorted[n - 1],
		"process_ms": proc / n, "physics_ms": phys / n, "draw_calls": dc / n, "primitives": prim / n, "objects": objs / n,
		"nodes": get_tree().get_node_count()}


## A Hum night at the town street view: the waves spawned and pathing toward the player (in god
## mode, standing still), measured once the horde reaches `members` bodies or 60 s pass.
func _hum_night() -> Dictionary:
	var v: Dictionary = VIEWS[2]
	await _goto(v["pos"], v["look"])
	var game: Node = get_node("/root/Game")
	var ai: Node = w.get(&"ai")
	var day: int = game.session.clock.next_horde_day(1)
	game.session.clock.set_time(day, 21.8)
	var want: int = 20
	if _hum_full:
		# Wait for the night to start, then hand it a late game's plan with every wave due now.
		var t_start: int = Time.get_ticks_msec() + 120000
		while not bool(ai.hum.active) and Time.get_ticks_msec() < t_start:
			await get_tree().process_frame
		var rng := RandomNumberGenerator.new()
		rng.seed = 7
		# A seventh Hum's plan at a late gamestage (the horde grows by Hums survived as well).
		game.session.horde.horde_index = 6
		var big: Dictionary = game.session.horde.plan(HUM_FULL_STAGE, rng)
		ai.hum.set(&"_wave_i", 0)
		for wv: Dictionary in big.get("waves", []):
			wv["start_min"] = 0.0
		ai.hum.plan = big
		want = mini(GameRules.current().integer("hum_max_alive"), int(big.get("total", 0)))
	if _hum_full:
		print("[perf] hum: forced plan of %d, waiting for %d alive (cap %d)" % [int((ai.hum.plan as Dictionary).get("total", 0)), want, GameRules.current().integer("hum_max_alive")])
	var end: int = Time.get_ticks_msec() + (120000 if _hum_full else 60000)
	var next_log: int = 0
	while Time.get_ticks_msec() < end and _alive(ai) < want:
		await get_tree().process_frame
		if _hum_full and Time.get_ticks_msec() > next_log:
			next_log = Time.get_ticks_msec() + 10000
			print("[perf] hum: active %s, wave %d/%d, queued %d, spawned %d, alive %d, hour %.2f" % [ai.hum.active, int(ai.hum.get(&"_wave_i")),
				((ai.hum.plan as Dictionary).get("waves", []) as Array).size(), (ai.hum.get(&"_queue") as Array).size(), int(ai.hum.get(&"_spawned_total")),
				_alive(ai), float(game.session.clock.hour())])
	if _hum_full:
		print("[perf] hum: waited until %d ms left, alive %d, spawned %d, queued %d" % [end - Time.get_ticks_msec(), _alive(ai), int(ai.hum.get(&"_spawned_total")), (ai.hum.get(&"_queue") as Array).size()])
	if _hum_full:
		# Let them run in and path round the town before measuring (spawned 55-85 m out).
		var settle: int = Time.get_ticks_msec() + 20000
		while Time.get_ticks_msec() < settle:
			await get_tree().process_frame
	Enemy.prof = {}
	Enemy.prof_on = true
	var m: Dictionary = await _measure(_frames)
	Enemy.prof_on = false
	# Where the bodies' physics step goes (ms a frame, summed over every body; phase 2 of TD-003).
	var sections: Dictionary = {}
	for k: Variant in Enemy.prof:
		sections[str(k)] = snappedf(float(Enemy.prof[k]) / 1000.0 / float(_frames), 0.01)
	m["enemy_ms"] = sections
	print("[perf] hum enemy sections (ms a frame): %s" % JSON.stringify(sections))
	# The physics span with the bodies' own steps off (30 frames): what the rest of the tick costs.
	var bodies: Array = get_tree().get_nodes_in_group(&"enemies")
	for b: Node in bodies:
		b.set_physics_process(false)
	var off: Dictionary = await _measure(30)
	for b2: Node in bodies:
		if is_instance_valid(b2):
			b2.set_physics_process(true)
	m["physics_ms_bodies_off"] = off["physics_ms"]
	print("[perf] hum physics with the %d bodies' steps off: %.2f ms" % [bodies.size(), float(off["physics_ms"])])
	m["members"] = (ai.hum.members as Dictionary).size()
	m["alive"] = _alive(ai)
	m["planned"] = int((ai.hum.plan as Dictionary).get("total", 0))
	m["spawned"] = int(ai.hum.get(&"_spawned_total"))
	m["queued"] = (ai.hum.get(&"_queue") as Array).size()
	if _ablate:
		m["modules"] = await _ablate_modules()
	game.session.clock.set_time(day + 1, 7.0)
	return m


## Hum members still standing.
func _alive(ai: Node) -> int:
	var n: int = 0
	for e: Dictionary in (ai.hum.members as Dictionary).values():
		var node: Variant = e.get("node")
		if node != null and is_instance_valid(node) and (node as Enemy).is_alive():
			n += 1
	return n


## Each world module's cost: process + physics time with it on minus with it off.
func _ablate_modules() -> Dictionary:
	var out: Dictionary = {}
	var n: int = maxi(30, _frames / 2)
	var base: Dictionary = await _measure(n)
	var base_ms: float = float(base["process_ms"]) + float(base["physics_ms"])
	for prop: String in ["terrain", "env", "clock_driver", "stimuli", "actions", "water", "bridges", "road_markings",
			"vegetation", "loose", "building", "pois", "ai", "ambience", "supply_drops", "directives", "wildlife"]:
		var c: Node = w.get(prop) as Node
		if c == null or not is_instance_valid(c):
			continue
		var mode: Node.ProcessMode = c.process_mode
		c.process_mode = Node.PROCESS_MODE_DISABLED
		var m: Dictionary = await _measure(n)
		c.process_mode = mode
		await get_tree().process_frame
		out[prop] = snappedf(base_ms - (float(m["process_ms"]) + float(m["physics_ms"])), 0.01)
	out["_total_ms"] = snappedf(base_ms, 0.01)
	return out


## Sprints the player along `dir` for `seconds` with real input: streaming terrain, scatter, POIs.
func _sprint(start: Vector3, dir: Vector3, seconds: float) -> Dictionary:
	await _goto(start, start + dir * 10.0)
	p.input_enabled = true
	p.rotation.y = atan2(-dir.x, -dir.z)
	Input.action_press(&"move_forward")
	Input.action_press(&"sprint")
	var walls: PackedFloat32Array = []
	var last: int = Time.get_ticks_usec()
	var end: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		walls.append(float(now - last) / 1000.0)
		last = now
		p.state.stats.stamina = 100.0
	Input.action_release(&"move_forward")
	Input.action_release(&"sprint")
	p.input_enabled = false
	var sorted: PackedFloat32Array = walls.duplicate()
	sorted.sort()
	var over: int = 0
	for f: float in walls:
		if f > 33.3:
			over += 1
	return {"frames": walls.size(), "frame_ms_avg": _avg(walls), "frame_ms_p95": sorted[int(walls.size() * 0.95)],
		"frame_ms_max": sorted[walls.size() - 1], "frames_over_33ms": over, "distance_m": p.global_position.distance_to(start)}


## Triangles each source submits from `eye`: instances x mesh triangles (the base LOD: import LODs
## make the GPU's share smaller near nothing) for every geometry whose visibility range holds the
## eye, grouped by a readable source name. Before frustum culling and shadow passes, which multiply.
func _triangle_census(eye: Vector3) -> Dictionary:
	var by: Dictionary = {}
	var tri_cache: Dictionary = {}
	_model_of.clear()
	for id: Variant in ModelLibrary._meshes:
		_model_of[ModelLibrary._meshes[id]] = str(id)
	for n: Node in get_tree().root.find_children("*", "GeometryInstance3D", true, false):
		var gi: GeometryInstance3D = n
		if not gi.is_visible_in_tree():
			continue
		var d: float = gi.global_position.distance_to(eye) if not gi is MultiMeshInstance3D else _mm_distance(gi as MultiMeshInstance3D, eye)
		if gi.visibility_range_end > 0.0 and d > gi.visibility_range_end + gi.visibility_range_end_margin:
			continue
		if d < gi.visibility_range_begin - gi.visibility_range_begin_margin:
			continue
		var mesh: Mesh = null
		var count: int = 1
		if gi is MultiMeshInstance3D:
			var mm: MultiMesh = (gi as MultiMeshInstance3D).multimesh
			if mm == null:
				continue
			mesh = mm.mesh
			count = mm.visible_instance_count if mm.visible_instance_count >= 0 else mm.instance_count
		elif gi is MeshInstance3D:
			mesh = (gi as MeshInstance3D).mesh
		if mesh == null:
			continue
		if not tri_cache.has(mesh):
			var t: int = 0
			for si: int in mesh.get_surface_count():
				var arr: Array = mesh.surface_get_arrays(si)
				var idx: Variant = arr[Mesh.ARRAY_INDEX]
				t += (idx as PackedInt32Array).size() / 3 if idx != null and (idx as PackedInt32Array).size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
			tri_cache[mesh] = t
		var key: String = _source_name(gi)
		var e: Array = by.get(key, [0, 0, 0])
		e[0] += int(tri_cache[mesh]) * count
		e[1] += count
		e[2] += 1 if gi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF else 0
		by[key] = e
	var keys: Array = by.keys()
	keys.sort_custom(func(a: String, b: String) -> bool: return int(by[a][0]) > int(by[b][0]))
	var out: Dictionary = {}
	var total: int = 0
	for k: String in keys:
		total += int(by[k][0])
	for k2: String in keys.slice(0, 400):
		out[k2] = {"triangles": by[k2][0], "instances": by[k2][1], "shadow_casters": by[k2][2]}
	out["_total_triangles"] = total
	return out


## Distance from the eye to a MultiMesh: headless, the dummy renderer keeps neither its AABB nor
## its instance transforms, so a vegetation chunk's centre comes from its holder ("V_x_y", 64 m
## chunks; Godot measures visibility ranges from the bounds' centre) and anything else's from its
## node (a POI's batches sit under the POI).
func _mm_distance(mmi: MultiMeshInstance3D, eye: Vector3) -> float:
	var holder: String = String(mmi.get_parent().name)
	if holder.begins_with("V_"):
		var xy: PackedStringArray = holder.substr(2).split("_")
		if xy.size() == 2:
			var c := Vector3((int(xy[0]) + 0.5) * TerrainManager.CHUNK, eye.y, (int(xy[1]) + 0.5) * TerrainManager.CHUNK)
			return c.distance_to(eye)
	var n: Node = mmi
	while n != null and n is Node3D and (n as Node3D).global_position == Vector3.ZERO:
		n = n.get_parent()
	return (n as Node3D).global_position.distance_to(eye) if n is Node3D else 0.0


## "veg tree grey_fir lod0", "poi kit", "terrain chunk"... from the node's path.
func _source_name(gi: GeometryInstance3D) -> String:
	var path: String = String(gi.get_path())
	for sys: String in ["Vegetation", "Terrain", "Pois", "Wildlife", "Water", "Ai", "Building", "Loose", "Environment", "Bridges", "Road_markings"]:
		if path.contains("/%s/" % sys):
			var tail: String = gi.name
			if gi is MultiMeshInstance3D and (gi as MultiMeshInstance3D).multimesh != null and (gi as MultiMeshInstance3D).multimesh.mesh != null:
				var mesh: Mesh = (gi as MultiMeshInstance3D).multimesh.mesh
				tail = _model_of.get(mesh, mesh.resource_path.get_file().get_basename())
				if tail == "":
					tail = gi.name.rstrip("0123456789@_")
			elif gi is MeshInstance3D and (gi as MeshInstance3D).mesh != null and (gi as MeshInstance3D).mesh.resource_path != "":
				tail = (gi as MeshInstance3D).mesh.resource_path.get_file().get_basename()
			elif gi is MeshInstance3D and _model_of.has((gi as MeshInstance3D).mesh):
				tail = "mesh " + str(_model_of[(gi as MeshInstance3D).mesh]).split("/")[0]
			elif gi is MeshInstance3D:
				tail = "mesh under " + String(gi.get_parent().name).rstrip("0123456789@_-")
			else:
				tail = tail.rstrip("0123456789@_-")
			return "%s %s" % [sys.to_lower(), tail]
	return "other " + String(gi.name).rstrip("0123456789@_-")


func _avg(a: PackedFloat32Array) -> float:
	var s: float = 0.0
	for x: float in a:
		s += x
	return snappedf(s / maxf(1.0, a.size()), 0.01)


func _brief(m: Dictionary) -> String:
	var parts: PackedStringArray = []
	for k: String in ["frame_ms_avg", "frame_ms_p95", "frame_ms_max", "process_ms", "physics_ms", "draw_calls", "primitives", "frames_over_33ms"]:
		if m.has(k):
			parts.append("%s=%s" % [k, str(snappedf(float(m[k]), 0.1))])
	if m.has("modules"):
		var mods: Array = (m["modules"] as Dictionary).keys().filter(func(k: String) -> bool: return not k.begins_with("_"))
		mods.sort_custom(func(a: String, b: String) -> bool: return float(m["modules"][a]) > float(m["modules"][b]))
		var top: PackedStringArray = []
		for k2: String in mods.slice(0, 5):
			top.append("%s %.2f" % [k2, float(m["modules"][k2])])
		parts.append("top: " + ", ".join(top))
	return " ".join(parts)


## Process and engine memory now: RSS and static memory in MB, live objects, resources, nodes,
## and the rendering server's buffer and texture memory in MB.
static func _mem() -> Dictionary:
	var rss: int = 0
	# /proc files report no length: read them a line at a time.
	var f := FileAccess.open("/proc/self/status", FileAccess.READ)
	while f != null and not f.eof_reached():
		var line: String = f.get_line()
		if line.begins_with("VmRSS:"):
			rss = int(line.split(":")[1].strip_edges().split(" ")[0]) / 1024
	return {"rss MB": rss, "static MB": int(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0),
		"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
		"resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
		"nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"buffers MB": int(Performance.get_monitor(Performance.RENDER_BUFFER_MEM_USED) / 1048576.0),
		"textures MB": int(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0)}
