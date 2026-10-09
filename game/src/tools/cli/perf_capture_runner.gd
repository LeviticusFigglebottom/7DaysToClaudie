extends Node
## Perf capture logic (loaded by perf_capture.gd once autoloads exist). See perf_capture.gd.

const VIEWS: Array[Dictionary] = [
	{"name": "drop_site", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296)},
	{"name": "forest", "pos": Vector3(-201, 1.8, 2227), "look": Vector3(-160, 3, 2200)},
	{"name": "town_street", "pos": Vector3(-45, 1.7, 2068), "look": Vector3(-95, 2, 2064)},
	{"name": "town_road", "pos": Vector3(-30, 6.0, 2170), "look": Vector3(-60, 0, 2070)},
	{"name": "river", "pos": Vector3(150, 1.7, 2075), "look": Vector3(118, 0.0, 2100)},
]

var _out: String = "res://../build/perf"
var _frames: int = 120
var _ablate: bool = true
## Quit once the load's report and its first frames in the world are logged (LoadMeter).
var _load_only: bool = false
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
			"--census":
				_census = true
			"--hum":
				_hum = true
			"--hum-full":
				_hum = true
				_hum_full = true
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var rules: Dictionary = {"hum_max_alive": 64, "hum_size": 2.0} if _hum_full else {}
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "perf", "rules": rules})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	w = game.world
	p = w.player
	if _load_only:
		for i: int in 40:
			await get_tree().process_frame
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
	var m: Dictionary = await _measure(_frames)
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
