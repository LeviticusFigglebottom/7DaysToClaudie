extends Node
## nav_pad_check's work (see nav_pad_check.gd).

## A path this many times the straight line (or longer) is a detour.
const DETOUR: float = 2.5
## Directions round each building, and how far outside its footprint's edge the far ends stand.
const DIRS: int = 16
const OUT: float = 8.0

var _findings: int = 0


func _ready() -> void:
	_run.call_deferred()


func wait_until(cond: Callable, timeout_s: float) -> bool:
	var end: int = Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return false


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var opts: Dictionary = {"game_mode": "survival", "skip_intro": true, "slot": "navpad"}
	var wi: int = args.find("--world")
	if wi >= 0 and wi + 1 < args.size() and args[wi + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 7)
		opts["stream"] = true
	var only: PackedStringArray = []
	if args.find("--poi") >= 0:
		only = args[args.find("--poi") + 1].split(",")
	var max_n: int = int(args[args.find("--max") + 1]) if args.find("--max") >= 0 else 12
	game.call(&"start_new_game", opts)
	if not await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), 600.0):
		print("[navpad] world never got ready")
		get_tree().quit(2)
		return
	var w: Node = game.world
	var p: Player = w.player
	p.god_mode = true
	var pm: Node = w.get(&"pois")
	var nav: Node = (w.get(&"ai") as Node).get(&"nav")
	var reg: PoiRegistry = pm.get(&"registry")
	# Buildings by distance from the spawn, or the named ones.
	var ids: Array = []
	var spawn := Vector2(p.global_position.x, p.global_position.z)
	for id: StringName in reg.entries:
		var e: Dictionary = reg.entries[id]
		if not only.is_empty() and not (str(e.get("def", "")) in only or String(id) in only):
			continue
		ids.append([reg.distance_to(id, spawn), id])
	ids.sort()
	var done: int = 0
	for pair: Array in ids:
		if done >= max_n:
			break
		var id2: StringName = pair[1]
		var e2: Dictionary = reg.entries[id2]
		var c: Vector2 = e2["center"]
		# Beside it, on the ground.
		var at := Vector3(c.x + (e2["half"] as Vector2).length() + 12.0, 0.0, c.y)
		at.y = float(w.call(&"height_at", at.x, at.z)) + 1.0
		p.global_position = at
		w.terrain.update_streaming(at, true)
		if not await wait_until(func() -> bool: return (pm.get(&"instances") as Dictionary).has(id2), 120.0):
			print("[navpad] %s: not built within 120 s" % id2)
			continue
		var inst: PoiInstance = (pm.get(&"instances") as Dictionary)[id2]
		# Its tiles baked (built after them, it marked them dirty) and the map synced.
		await get_tree().create_timer(2.0).timeout
		if not await wait_until(func() -> bool: return _tiles_ready(nav), 120.0):
			print("[navpad] %s: tiles not baked within 120 s" % id2)
			continue
		for i: int in 20:
			await get_tree().physics_frame
		_check(w, inst, id2)
		done += 1
	print("[navpad] %d buildings checked, %d findings" % [done, _findings])
	get_tree().quit(0 if _findings == 0 else 1)


func _tiles_ready(nav: Node) -> bool:
	if int(nav.get(&"_busy")) > 0 or not (nav.get(&"_dirty") as Dictionary).is_empty():
		return false
	for t: Dictionary in (nav.get(&"_tiles") as Dictionary).values():
		if not (t["region"] as RID).is_valid() or bool(t.get("baking", false)) or t.has("assembly"):
			return false
	return true


func _check(w: Node, inst: PoiInstance, id: StringName) -> void:
	var map: RID = (w as Node3D).get_world_3d().navigation_map if w is Node3D else inst.get_world_3d().navigation_map
	var fp: Vector2 = Vector2(inst.layout.def.footprint)
	var xf: Transform3D = inst.global_transform * Transform3D(Basis.IDENTITY, Vector3(inst.layout.origin.x, 0, inst.layout.origin.y))
	var mid: Vector3 = xf * Vector3(fp.x * 0.5, 0, fp.y * 0.5)
	var bad: PackedStringArray = []
	for k: int in DIRS:
		var d := Vector3.FORWARD.rotated(Vector3.UP, TAU * k / DIRS)
		var inside: Vector3 = mid + d * minf(fp.x, fp.y) * 0.3
		# The far end: along d past the footprint's edge (its local box), OUT m out.
		var local_d: Vector3 = xf.basis.inverse() * d
		var t: float = minf(fp.x * 0.5 / maxf(absf(local_d.x), 0.001), fp.y * 0.5 / maxf(absf(local_d.z), 0.001))
		var outside: Vector3 = mid + d * (t + OUT)
		for q: Vector3 in [inside, outside]:
			q.y = float(w.call(&"height_at", q.x, q.z))
		inside.y = float(w.call(&"height_at", inside.x, inside.z))
		outside.y = float(w.call(&"height_at", outside.x, outside.z))
		var ci: Vector3 = NavigationServer3D.map_get_closest_point(map, inside)
		var co: Vector3 = NavigationServer3D.map_get_closest_point(map, outside)
		if ci.distance_to(inside) > 2.0 or co.distance_to(outside) > 2.0:
			bad.append("dir %d: off the mesh (inside %.1f m, outside %.1f m; %s)" % [k, ci.distance_to(inside), co.distance_to(outside), _ground_note(w, mid, outside)])
			continue
		var path: PackedVector3Array = NavigationServer3D.map_get_path(map, ci, co, true)
		var length: float = 0.0
		for j: int in range(1, path.size()):
			length += path[j - 1].distance_to(path[j])
		var straight: float = Vector2(ci.x, ci.z).distance_to(Vector2(co.x, co.z))
		if path.size() < 2 or path[path.size() - 1].distance_to(co) > 1.5:
			bad.append("dir %d: no path out (ends %.1f m short)" % [k, (path[path.size() - 1].distance_to(co) if path.size() > 0 else INF)])
		elif length > straight * DETOUR + 4.0:
			bad.append("dir %d: %.0f m for %.0f m" % [k, length, straight])
	if OS.has_environment("NAVPAD_DEBUG"):
		# A map of the ground around the building: '#' on the mesh, '.' off it (the closest mesh point
		# more than 0.6 m away), every 2 m, north up.
		var map2: RID = w.get_world_3d().navigation_map
		for zz: int in range(-14, 15):
			var row: String = ""
			for xx: int in range(-14, 15):
				var q := Vector3(mid.x + xx * 2.0, 0.0, mid.z + zz * 2.0)
				q.y = float(w.call(&"height_at", q.x, q.z))
				var cp: Vector3 = NavigationServer3D.map_get_closest_point(map2, q)
				row += "#" if Vector2(cp.x - q.x, cp.z - q.z).length() < 0.6 and absf(cp.y - q.y) < 1.5 else ("^" if Vector2(cp.x - q.x, cp.z - q.z).length() < 0.6 else ".")
			print("[navpad]   %s" % row)
		# The camp's tile baked again here, whole and piece by piece: which source empties it.
		var navn: Node = (w.get(&"ai") as Node).get(&"nav")
		var tk: Vector2i = NavTiles.tile_of(mid)
		var full: Array = navn.call(&"bake_inputs", tk)
		var srcf: NavigationMeshSourceGeometryData3D = full[1]
		print("[navpad]   tile %s source: %d verts, %d obstructions, bounds %s" % [tk, srcf.get_vertices().size(), srcf.get_projected_obstructions().size(), srcf.get_bounds()])
		NavigationServer3D.bake_from_source_geometry_data(full[0], srcf)
		print("[navpad]   whole: %d polygons" % (full[0] as NavigationMesh).get_polygon_count())
		for part: String in ["terrain", "terrain+obstructions", "terrain+pois"]:
			var nm2: NavigationMesh = (full[0] as NavigationMesh).duplicate()
			nm2.clear_polygons()
			var s2 := NavigationMeshSourceGeometryData3D.new()
			navn.call(&"_add_terrain", s2, tk)
			if part.contains("obstructions"):
				navn.call(&"_add_obstructions", s2, tk)
			if part.contains("pois"):
				navn.call(&"_add_pois", nm2, s2, tk)
			NavigationServer3D.bake_from_source_geometry_data(nm2, s2)
			print("[navpad]   %s: %d polygons (%d verts)" % [part, nm2.get_polygon_count(), s2.get_vertices().size()])
	_findings += bad.size()
	print("[navpad] %s (%s): %s" % [id, inst.layout.def.id, "ok" if bad.is_empty() else "%d of %d directions: %s" % [bad.size(), DIRS, "; ".join(bad)]])


## What stands between the building and a point: the steepest 1 m rise on the line from its middle
## to the point, and the trees (the navmesh's vegetation obstructions) within 3 m of the line.
func _ground_note(w: Node, a: Vector3, b: Vector3) -> String:
	var steep: float = 0.0
	var n: int = maxi(1, int(Vector2(a.x, a.z).distance_to(Vector2(b.x, b.z))))
	var prev: float = float(w.call(&"height_at", a.x, a.z))
	for i: int in range(1, n + 1):
		var q: Vector3 = a.lerp(b, float(i) / n)
		var h: float = float(w.call(&"height_at", q.x, q.z))
		steep = maxf(steep, absf(h - prev))
		prev = h
	var trees: int = 0
	var veg: Node = w.get(&"vegetation")
	if veg != null and veg.has_method(&"obstacles_in_rect"):
		var r := Rect2(Vector2(minf(a.x, b.x), minf(a.z, b.z)), Vector2(absf(a.x - b.x), absf(a.z - b.z))).grow(3.0)
		for o: Dictionary in veg.call(&"obstacles_in_rect", r):
			var pos: Vector3 = o["pos"]
			if Geometry2D.get_closest_point_to_segment(Vector2(pos.x, pos.z), Vector2(a.x, a.z), Vector2(b.x, b.z)).distance_to(Vector2(pos.x, pos.z)) < 3.0:
				trees += 1
	return "steepest %.2f m a metre, %d trees by the line" % [steep, trees]
