extends Node
## The work of rwg_preview_shots.gd: a slice game on a generated world, then one PNG per shot. Shot
## positions come from the world's files (towns, rivers, places, the drop site), so any seed works.
## An organic town (RWG v2, ADR-0040) gives three: its main street from 70 m out looking at the
## centre (town_street), its steepest side street looking up it (town_slope), and the town from
## above (town_aerial); a v1 town (a region framework) its street and aerial as before.

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
	# The biggest organic town (world-level): its main street, its steepest side street, from above.
	if wd != null and not wd.towns.is_empty():
		out.append_array(_organic_town_shots(wd))
	# The biggest v1 town: along its main street, and from above.
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
	# A wilderness place, from a front corner of its own footprint across its yard: the pad grows
	# nothing, but the forest comes right up to its edge (the skirt only grades the ground), so a
	# camera anywhere outside it looked at the place through trunks.
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
					var front: Vector2 = o2 + Vector2(1.5, fp.y - 0.8).rotated(r2)
					out.append({"name": "wilderness_%s" % want, "pos": Vector3(front.x, 3.0, front.y), "look": Vector3(centre.x, 1.4, centre.y), "hour": 11.5, "weather": "clear"})
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
	if wd != null:
		out.append_array(_biome_shots(wd, regions))
	return out


## The burnt forest and the fen (ADR-0041), from the world's biome map and the fen's pools: in the
## heart of the biggest burn at midday and at dusk, out of the burn across its edge into the live
## forest, a charred snag at eye level (framed on the nearest one), the fen at dawn in mist and in
## rain by its biggest cluster of pools, and one pool's edge up close.
func _biome_shots(wd: WorldDef, regions: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var n: int = wd.biome_cols
	if n == 0:
		return out
	var wr: Rect2 = wd.world_rect()
	var st: float = wd.biome_step
	var burn: int = wd.biome_ids.find("burnt_forest")
	var forest: int = wd.biome_ids.find("conifer_forest")
	var centre := func(k: int) -> Vector2: return wr.position + Vector2((k % n) + 0.5, (k / n) + 0.5) * st
	# The burn's heart: the burnt cell with the most burnt cells within three.
	var heart: int = -1
	var best: int = -1
	for k: int in wd.biome_cells.size():
		if wd.biome_cells[k] != burn:
			continue
		var c: int = 0
		for dj: int in range(-3, 4):
			for di: int in range(-3, 4):
				var i: int = k % n + di
				var j: int = k / n + dj
				if i >= 0 and j >= 0 and i < n and j < n and wd.biome_cells[j * n + i] == burn:
					c += 1
		if c > best:
			best = c
			heart = k
	# A conifer-forest reference for the perf numbers: the deepest forest cell.
	var deep: int = -1
	var dbest: int = -1
	for k0: int in range(0, wd.biome_cells.size(), 3):
		if wd.biome_cells[k0] != forest:
			continue
		var c0: int = 0
		for dj0: int in range(-3, 4):
			for di0: int in range(-3, 4):
				var i0: int = k0 % n + di0
				var j0: int = k0 / n + dj0
				if i0 >= 0 and j0 >= 0 and i0 < n and j0 < n and wd.biome_cells[j0 * n + i0] == forest:
					c0 += 1
		if c0 > dbest:
			dbest = c0
			deep = k0
	if deep >= 0:
		var fc: Vector2 = centre.call(deep)
		out.append({"name": "forest_ref", "pos": Vector3(fc.x, 1.7, fc.y), "look": Vector3(fc.x + 90.0, 4.0, fc.y + 10.0), "hour": 12.5, "weather": "clear"})
	if heart >= 0:
		var hc: Vector2 = centre.call(heart)
		# Look along the burn: the heading with the most burnt cells over the next 300 m.
		var dir := Vector2.RIGHT
		var most: int = -1
		for h: int in 8:
			var d := Vector2.from_angle(TAU * h / 8.0)
			var cnt: int = 0
			for step: int in range(1, 6):
				if wd.biome_at(hc.x + d.x * step * 60.0, hc.y + d.y * step * 60.0) == "burnt_forest":
					cnt += 1
			if cnt > most:
				most = cnt
				dir = d
		var lk: Vector2 = hc + dir * 90.0
		out.append({"name": "burn_midday", "pos": Vector3(hc.x, 1.7, hc.y), "look": Vector3(lk.x, 4.0, lk.y), "hour": 12.5, "weather": "clear"})
		var west: Vector2 = hc + Vector2(-90.0, 15.0)
		out.append({"name": "burn_dusk", "pos": Vector3(hc.x, 1.7, hc.y), "look": Vector3(west.x, 6.0, west.y), "hour": 18.7, "weather": "clear"})
		out.append({"name": "burn_snag", "pos": Vector3(hc.x, 1.6, hc.y), "look": Vector3(lk.x, 1.6, lk.y), "hour": 14.5, "weather": "clear",
			"frame_species": "burnt_snag"})
		# The edge nearest the heart where the burn meets live forest.
		var edge: int = -1
		var ed: float = INF
		var to_live := Vector2.ZERO
		for k2: int in wd.biome_cells.size():
			if wd.biome_cells[k2] != burn:
				continue
			for o: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var i2: int = k2 % n + o.x
				var j2: int = k2 / n + o.y
				if i2 < 0 or j2 < 0 or i2 >= n or j2 >= n or wd.biome_cells[j2 * n + i2] != forest:
					continue
				var dd: float = (centre.call(k2) as Vector2).distance_to(hc)
				if dd < ed:
					ed = dd
					edge = k2
					to_live = Vector2(o)
		if edge >= 0:
			# Stand in the burn near the cells' boundary and look obliquely across it, so the frame
			# holds both: snags and ash near, the live forest's wall beyond (looking square on from
			# deep in the burn, the forest was a grey band in the haze).
			var b: Vector2 = centre.call(edge) + to_live * st * 0.5
			var along: Vector2 = to_live.orthogonal()
			var cam_e: Vector2 = b - to_live * 16.0 - along * 18.0
			var look_e: Vector2 = b + to_live * 30.0 + along * 40.0
			out.append({"name": "burn_edge", "pos": Vector3(cam_e.x, 1.7, cam_e.y), "look": Vector3(look_e.x, 6.0, look_e.y), "hour": 15.5, "weather": "clear"})
	# The fen: the pool with the most pools round it.
	var pools: Array[Vector4] = []
	for reg: Dictionary in regions:
		for f: Variant in reg.get("features", []):
			var fd: Dictionary = f
			if str(fd.get("type", "")) == "lake" and str(fd.get("id", "")).begins_with("fen_") and fd.has("ellipse"):
				var el: Array = fd["ellipse"]
				pools.append(Vector4(float(el[0]), float(el[1]), float(el[2]), float(el[3])))
	var pick: int = -1
	var pc: int = -1
	for a: int in pools.size():
		var c2: int = 0
		for b: int in pools.size():
			if Vector2(pools[a].x, pools[a].y).distance_to(Vector2(pools[b].x, pools[b].y)) < 90.0:
				c2 += 1
		if c2 > pc:
			pc = c2
			pick = a
	if pick >= 0:
		var pl: Vector4 = pools[pick]
		var pcen := Vector2(pl.x, pl.y)
		var away := Vector2(0.6, 0.8)
		var cam_f: Vector2 = pcen + away * (pl.z + 14.0)
		out.append({"name": "fen_dawn", "pos": Vector3(cam_f.x, 1.7, cam_f.y), "look": Vector3(pcen.x - away.x * 40.0, 1.2, pcen.y - away.y * 40.0),
			"hour": 6.4, "weather": "mist", "wet": 0.6})
		var cam_r: Vector2 = pcen + away.orthogonal() * (pl.z + 10.0)
		out.append({"name": "fen_rain", "pos": Vector3(cam_r.x, 1.7, cam_r.y), "look": Vector3(pcen.x, 0.6, pcen.y), "hour": 13.0,
			"weather": "rain", "wet": 1.0, "puddles": 0.8})
		var edge_p: Vector2 = pcen + away * (pl.w + 2.2)
		out.append({"name": "fen_pool_edge", "pos": Vector3(edge_p.x, 1.25, edge_p.y), "look": Vector3(pcen.x, 0.0, pcen.y), "hour": 10.5, "weather": "clear"})
	return out


## Shots of the organic town with the most lots: down its main street (the world road through its
## centre) from 70 m out, up its steepest side street from its foot, and from above.
func _organic_town_shots(wd: WorldDef) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var best: FrameworkDef = null
	var best_c := Vector2.ZERO
	for tw: Dictionary in wd.towns:
		var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(tw["framework"]))) as FrameworkDef
		if fw != null and (best == null or fw.lots.size() > best.lots.size()):
			best = fw
			best_c = tw["center"]
	if best == null:
		return out
	# The main street: the world road passing nearest the centre.
	var main: Polyline2 = null
	var md: float = INF
	for rd: Dictionary in wd.roads:
		var q: Vector3 = (rd["line"] as Polyline2).closest(best_c)
		if q.x < md:
			md = q.x
			main = rd["line"]
	if main != null:
		var sc: float = main.closest(best_c).y
		var s0: float = clampf(sc - 70.0, 0.0, main.total_length)
		var a: Vector2 = main.point_at(s0)
		var t: Vector2 = main.tangent_at(s0)
		var cam_p: Vector2 = a + Vector2(-t.y, t.x) * 2.5
		var look: Vector2 = main.point_at(minf(sc + 30.0, main.total_length))
		out.append({"name": "town_street", "pos": Vector3(cam_p.x, 1.7, cam_p.y), "look": Vector3(look.x, 2.5, look.y), "hour": 10.5, "weather": "clear"})
	# The steepest side street (rise over its first 120 m of the reference ground the composer grades it from).
	var steep: Dictionary = {}
	var rise: float = -1.0
	for rv: Variant in best.roads:
		var rd2: Dictionary = rv
		if not str(rd2.get("class", "")) in ["street", "lane"]:
			continue
		var line: Polyline2 = Polyline2.from_array(rd2["points"])
		if line.total_length < 60.0:
			continue
		var e: float = minf(120.0, line.total_length)
		var dh: float = absf(wd.macro_height(line.point_at(e).x, line.point_at(e).y) - wd.macro_height(line.points[0].x, line.points[0].y))
		if dh > rise:
			rise = dh
			steep = {"line": line, "e": e, "up": wd.macro_height(line.point_at(e).x, line.point_at(e).y) > wd.macro_height(line.points[0].x, line.points[0].y)}
	if not steep.is_empty():
		var sl: Polyline2 = steep["line"]
		var e2: float = float(steep["e"])
		var from_s: float = 4.0 if bool(steep["up"]) else e2 - 4.0
		var to_s: float = e2 if bool(steep["up"]) else 0.0
		var p0: Vector2 = sl.point_at(from_s)
		var p1: Vector2 = sl.point_at(to_s)
		out.append({"name": "town_slope", "pos": Vector3(p0.x, 1.7, p0.y), "look": Vector3(p1.x, 3.0, p1.y), "hour": 15.0, "weather": "clear"})
	var back: Vector2 = best_c + Vector2(-0.6, 1.0).normalized() * (best.radius * 0.55 + 90.0)
	out.append({"name": "town_aerial", "pos": Vector3(back.x, best.radius * 0.35 + 60.0, back.y), "look": Vector3(best_c.x, 0.0, best_c.y), "hour": 16.0, "weather": "clear"})
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
	# What the weather has left (the clock stands still between shots): the biome shots' rain.
	var ws: WeatherState = Game.session.weather
	ws.wetness = float(shot.get("wet", 0.0))
	if &"puddles" in ws:
		ws.set(&"puddles", float(shot.get("puddles", 0.0)))
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
	if shot.has("frame_species"):
		# Up to a trunk at eye level: the nearest instance, 3 m off it on its sunlit side with the sun
		# 50 degrees off the view, so the light rakes across the char (seen from the shot's own side
		# the trunk stood against the sun, its char one black shape).
		var near: Array = veg.call(&"instances_near", pos, 80.0, StringName(str(shot["frame_species"]))) if veg != null else []
		if near.is_empty():
			print("SHOT warning: no %s near %s" % [shot["frame_species"], pos])
		else:
			var inst: VegetationScatter.Instance = (near[0] as Array)[1]
			var from := Vector2(pos.x - inst.pos.x, pos.z - inst.pos.z).normalized()
			var envc: EnvironmentController = w.get(&"env") as EnvironmentController
			if envc != null and envc.sun != null and envc.sun.visible:
				var to_sun: Vector3 = envc.sun.global_transform.basis.z
				if Vector2(to_sun.x, to_sun.z).length() > 0.05:
					from = Vector2(to_sun.x, to_sun.z).normalized().rotated(deg_to_rad(50.0))
			if from == Vector2.ZERO:
				from = Vector2.RIGHT
			var c3: Vector2 = Vector2(inst.pos.x, inst.pos.z) + from * 3.2
			cam.global_position = Vector3(c3.x, float(w.call(&"height_at", c3.x, c3.y)) + 1.6, c3.y)
			cam.look_at(inst.pos + Vector3.UP * 2.2, Vector3.UP)
			print("SHOT framing %s at %s" % [inst.species, inst.pos])
	var wx_env: EnvironmentController = w.get(&"env") as EnvironmentController
	if shot.has("wet") and wx_env != null and wx_env.fx != null:
		# Build the weather map round the camera now (its rays take minutes of software frames) and
		# hold the rain still for the capture (ADR-0033), as the screenshot runner's weather shots do.
		if not wx_env.fx.settle_map():
			print("SHOT warning: %s: no weather map round the camera" % shot["name"])
		await _wait(2.0)
		wx_env.fx.hold_still(true)
	await _wait(_settle)
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	if wx_env != null and wx_env.fx != null:
		wx_env.fx.hold_still(false)
	print("SHOT %s at %s" % [path, pos])
	# What the view costs (ADR-0041 compares the biomes with a conifer forest): wall time per frame
	# (software Vulkan here: compare shots with each other, not with a GPU) and what was submitted.
	var walls: Array[float] = []
	var dc: int = 0
	var prim: int = 0
	var objs: int = 0
	var last: int = Time.get_ticks_usec()
	for i: int in 4:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		walls.append(float(now - last) / 1000.0)
		last = now
		dc += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
		prim += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
		objs += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)
	walls.sort()
	print("SHOT perf %s: frame %.0f ms (median of 4), %d draw calls, %d primitives, %d objects" % [shot["name"], (walls[1] + walls[2]) * 0.5,
		dc / 4, prim / 4, objs / 4])
