extends Node
## The work of rwg_preview_shots.gd: a slice game on a generated world, then one PNG per shot. Shot
## positions come from the world's files (towns, rivers, places, the drop site), so any seed works.

const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const MapImage := preload("res://src/worldgen/rwg/rwg_map.gd")

var _out: String = "res://../build/rwg_shots"
var _settle: float = 4.0
var _only: PackedStringArray = []


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--out":
				_out = args[i + 1]
			"--settle":
				_settle = float(args[i + 1])
			"--only":
				_only = args[i + 1].split(",")
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _wait(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var gen: Dictionary = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 7)
	game.call(&"start_new_game", {"game_mode": "slice", "skip_intro": true, "slot": "rwg_shots", "world_gen": gen})
	var t0: int = Time.get_ticks_msec()
	while (game.get(&"world") == null or not bool(game.world.is_ready)) and Time.get_ticks_msec() - t0 < 1200000:
		await get_tree().process_frame
	var w: Node = game.world
	if w == null or not bool(w.is_ready):
		printerr("SHOT world did not load")
		get_tree().quit(1)
		return
	print("SHOT world %s ready in %.1fs" % [Game.session.world_id, (Time.get_ticks_msec() - t0) / 1000.0])
	(w.get(&"ui") as CanvasLayer).visible = false
	var debug: Node = w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	var cam := Camera3D.new()
	cam.far = 4000.0
	cam.fov = 70.0
	w.add_child(cam)
	cam.make_current()
	var p: Player = w.player
	p.input_enabled = false
	(w.get(&"clock_driver") as WorldClockDriver).paused = true
	var shots: Array[Dictionary] = _shots(Worlds.dir_for(String(Game.session.world_id)), (w as GameWorld).world_def)
	print("SHOT %d shots planned" % shots.size())
	for shot: Dictionary in shots:
		if not _only.is_empty() and not _only.has(str(shot["name"])):
			continue
		await _shoot(w, cam, p, shot)
	print("SHOT done in %.1fs" % ((Time.get_ticks_msec() - t0) / 1000.0))
	get_tree().quit(0)


## Shots from the world's data: {name, pos: Vector3 (y over ground), look: Vector3, hour, weather}.
## Read from the loaded world (its regions and registered towns) when there is one: the files on
## disk may have been pruned since it loaded.
func _shots(dir: String, wd: WorldDef = null) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var world: Dictionary = MapImage._read(dir.path_join("world.json"))
	var regions: Array = []
	var fw_by_id: Dictionary = {}
	if wd != null:
		world = {"rivers": [], "generator": wd.generator}
		for rv: Dictionary in wd.rivers:
			var pts: Array = []
			for p0: Vector2 in (rv["line"] as Polyline2).points:
				pts.append([p0.x, p0.y])
			world["rivers"].append({"points": pts})
		for rid: String in wd.regions:
			regions.append(wd.region_data(rid))
		for fd: ContentDef in Content.all(&"framework"):
			var f0: FrameworkDef = fd as FrameworkDef
			fw_by_id[String(f0.id)] = {"lots": f0.lots, "roads": f0.roads, "size": [f0.size.x, f0.size.y]}
	else:
		var fws: Dictionary = MapImage._read(dir.path_join("frameworks.json"))
		for d: Variant in fws.get("defs", []):
			fw_by_id[str(d["id"])] = d
		for r: Variant in world.get("regions", []):
			regions.append(MapImage._read(dir.path_join("regions").path_join(str(r["id"])).path_join("region.json")))
	var gen: Dictionary = world.get("generator", {})
	# The biggest town: along its main street, and from above.
	var best_fw: Dictionary = {}
	var best_f: Dictionary = {}
	for reg: Dictionary in regions:
		for f: Variant in reg.get("features", []):
			if str(f.get("type", "")) == "framework" and fw_by_id.has(str(f.get("framework", ""))):
				var fw: Dictionary = fw_by_id[str(f["framework"])]
				if best_fw.is_empty() or (fw["lots"] as Array).size() > (best_fw["lots"] as Array).size():
					best_fw = fw
					best_f = f
	if not best_fw.is_empty():
		var o := Vector2(float(best_f["origin"][0]), float(best_f["origin"][1]))
		var rot: float = deg_to_rad(float(best_f["rotation"]))
		var main: Array = (best_fw["roads"] as Array)[0]["points"]
		var zm: float = float(main[0][1])
		var wdt: float = float(best_fw["size"][0])
		var a: Vector2 = o + Vector2(wdt * 0.12, zm + 2.0).rotated(rot)
		var b: Vector2 = o + Vector2(wdt * 0.55, zm - 1.0).rotated(rot)
		out.append({"name": "town_street", "pos": Vector3(a.x, 1.7, a.y), "look": Vector3(b.x, 2.0, b.y), "hour": 10.5, "weather": "clear"})
		var c: Vector2 = o + Vector2(wdt * 0.5, float(best_fw["size"][1]) * 0.5).rotated(rot)
		var back: Vector2 = c + Vector2(0.0, -1.0).rotated(rot) * 150.0 + Vector2(1.0, 0.0).rotated(rot) * -60.0
		out.append({"name": "town_aerial", "pos": Vector3(back.x, 70.0, back.y), "look": Vector3(c.x, 0.0, c.y), "hour": 16.0, "weather": "clear"})
	# The longest river: from its bank a third of the way down.
	var best_r: Dictionary = {}
	for rv: Variant in world.get("rivers", []):
		if best_r.is_empty() or (rv["points"] as Array).size() > (best_r["points"] as Array).size():
			best_r = rv
	if not best_r.is_empty():
		# Over the water itself (nothing grows there), a few metres up, looking down the river.
		var line: Polyline2 = Polyline2.from_array(best_r["points"])
		var s: float = line.total_length * 0.35
		var cam_p: Vector2 = line.point_at(s)
		var look_p: Vector2 = line.point_at(s + 110.0)
		out.append({"name": "river_valley", "pos": Vector3(cam_p.x, 6.0, cam_p.y), "look": Vector3(look_p.x, 1.0, look_p.y), "hour": 9.0, "weather": "clear"})
	# A wilderness place, from in front of it: inside its pad's skirt (meadow, 10 m round the
	# footprint), so the forest frames the place instead of standing between it and the lens.
	for want: String in ["trappers_cabin", "tamsin_logging_camp", "cedar_ridge_lookout", "tamsin_campground", "cordon_gas_garage"]:
		var found: bool = false
		for reg2: Dictionary in regions:
			for f2: Variant in reg2.get("features", []):
				if str(f2.get("type", "")) == "poi" and str(f2.get("poi", "")) == want:
					var pd: PoiDef = Content.get_def(&"poi", StringName(want)) as PoiDef
					var fp: Vector2 = Vector2(pd.footprint) if pd != null else Vector2(24, 24)
					var o2 := Vector2(float(f2["origin"][0]), float(f2["origin"][1]))
					var r2: float = deg_to_rad(float(f2["rotation"]))
					var centre: Vector2 = o2 + (fp * 0.5).rotated(r2)
					var front: Vector2 = o2 + Vector2(fp.x * 0.5, fp.y).rotated(r2) + Vector2(0.0, 1.0).rotated(r2) * 8.0 + Vector2(1.0, 0.0).rotated(r2) * 5.0
					out.append({"name": "wilderness_%s" % want, "pos": Vector3(front.x, 2.6, front.y), "look": Vector3(centre.x, 1.6, centre.y), "hour": 11.5, "weather": "clear"})
					found = true
					break
			if found:
				break
		if found:
			break
	var dp: Array = gen.get("drop_site", [0, 0])
	var dpos := Vector2(float(dp[0]), float(dp[1]))
	for reg3: Dictionary in regions:
		for f3: Variant in reg3.get("features", []):
			if str(f3.get("type", "")) == "spawn" and str(f3.get("id", "")) == "drop_site":
				var yaw: float = deg_to_rad(float(f3.get("yaw", 0.0)))
				var fwd := Vector2(-sin(yaw), -cos(yaw))
				var at: Vector2 = dpos - fwd * 6.0
				var lk: Vector2 = dpos + fwd * 40.0
				out.append({"name": "drop_site", "pos": Vector3(at.x, 1.7, at.y), "look": Vector3(lk.x, 1.0, lk.y), "hour": 7.8, "weather": "clear"})
				var up: Vector2 = dpos - fwd * 260.0
				out.append({"name": "land_aerial", "pos": Vector3(up.x, 150.0, up.y), "look": Vector3(lk.x + fwd.x * 400.0, 0.0, lk.y + fwd.y * 400.0), "hour": 17.0, "weather": "clear"})
	return out


func _shoot(w: Node, cam: Camera3D, p: Player, shot: Dictionary) -> void:
	var pos: Vector3 = shot["pos"]
	var look: Vector3 = shot["look"]
	var ground: float = w.call(&"height_at", pos.x, pos.z)
	pos.y += ground
	look.y += w.call(&"height_at", look.x, look.z)
	p.global_position = Vector3(pos.x, ground + 0.2, pos.z)
	var clock: WorldClock = Game.session.clock
	clock.set_time(clock.day(), float(shot["hour"]))
	Game.session.weather.force(StringName(str(shot["weather"])))
	Game.session.weather.blend = 1.0
	Game.session.weather.current = StringName(str(shot["weather"]))
	(w.get(&"terrain") as TerrainManager).update_streaming(p.global_position, true)
	cam.global_position = pos
	cam.look_at(look, Vector3.UP)
	cam.fov = 70.0
	var vm: Node3D = p.get_node_or_null(^"Head/Camera3D/ViewModel") as Node3D
	if vm != null:
		vm.visible = false
	var veg: Node = w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled", 2)):
		if Time.get_ticks_msec() - t0 > 240000:
			print("SHOT warning: vegetation still streaming after 240 s")
			break
		await get_tree().process_frame
	await _wait(_settle)
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("SHOT %s at %s" % [path, pos])
