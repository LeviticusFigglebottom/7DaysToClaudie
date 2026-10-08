extends Node
## The work of plan_main_town.gd. The planner sees what it must keep off as water: its `water(x, z)`
## is the least of the real water's distance and the distance to every keep-out (pads grown by a
## margin, other roads' corridors, paths, spawns, caves, the region's edge), so streets stop short
## of them and lots keep 12 m away.

const Planner := preload("res://src/worldgen/rwg/rwg_town_planner.gd")
const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")

const PAD_MARGIN: float = 14.0
const ROAD_MARGIN: float = 10.0
## The drop site keeps its opening moment: no lot within 150 m of its marker (the hub's call).
const SPAWN_R: float = 150.0
const CAVE_R: float = 70.0
const EDGE: float = 70.0

var rt: RegionTerrain
## Every composed region the town may reach (--regions a,b): the ground is read from the one holding
## a point.
var rts: Array[RegionTerrain] = []
var polys: Array[PackedVector2Array] = []
var lines: Array = []   # [Polyline2, half width + margin]
var circles: Array[Vector3] = []
var rect := Rect2()


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	var rids: PackedStringArray = _arg(a, "--regions", _arg(a, "--region", "d6_larch_hollow")).split(",")
	for r0: String in rids:
		rts.append(TerrainComposer.compose(world, r0, 2.0))
	rt = rts[0]
	rect = rt.rect
	for r1: RegionTerrain in rts:
		rect = rect.merge(r1.rect)
	rect = rect.grow(-EDGE)
	var rid: String = rids[0]
	var art_id: String = _arg(a, "--arterial", "route9")
	var arterials: Array = []
	for rd: Dictionary in world.roads:
		var line: Polyline2 = rd["line"]
		if str(rd["id"]) == art_id:
			var pts: Array = []
			for p: Vector2 in line.points:
				pts.append([p.x, p.y])
			arterials.append({"id": rd["id"], "points": pts, "width": rd["width"], "shoulder": rd["shoulder"], "surface": rd["surface"], "markings": rd["markings"]})
		else:
			lines.append([line, float(rd["width"]) * 0.5 + float(rd["shoulder"]) + ROAD_MARGIN])
	# A new arterial of the extension's own (written into region.json as a road feature).
	if _arg(a, "--arterial-points", "") != "":
		var pts2: Array = []
		for pv: String in _arg(a, "--arterial-points", "").split(";"):
			pts2.append([float(pv.get_slice(",", 0)), float(pv.get_slice(",", 1))])
		arterials.push_front({"id": _arg(a, "--arterial-id", "new_street"), "points": pts2, "width": float(_arg(a, "--arterial-width", "6")),
			"shoulder": 1.0, "surface": "asphalt", "markings": true})
	var feats: Array = []
	for r2: String in rids:
		feats.append_array(world.region_data(r2).get("features", []))
	for f: Dictionary in feats:
		match str(f.get("type", "")):
			"road":
				lines.append([Polyline2.from_array(f["points"]), float(f.get("width", 5.0)) * 0.5 + float(f.get("shoulder", 1.5)) + ROAD_MARGIN])
			"path":
				lines.append([Polyline2.from_array(f["points"]), float(f.get("width", 2.0)) * 0.5 + 6.0])
			"cave":
				var m: Array = f.get("mouth", [0, 0])
				circles.append(Vector3(float(m[0]), float(m[1]), CAVE_R))
			"spawn", "clearing":
				var sp: Array = f.get("pos", [0, 0])
				circles.append(Vector3(float(sp[0]), float(sp[1]), SPAWN_R if str(f.get("type")) == "spawn" else float(f.get("radius", 10.0)) + 10.0))
	var pls: Array = []
	for r3: RegionTerrain in rts:
		pls.append_array(r3.placements)
	for pl: Dictionary in pls:
		if not pl.has("size") or str(pl.get("kind", "")) == "town":
			continue
		var o: Array = pl["origin"]
		var sz: Array = pl["size"]
		var rot: float = deg_to_rad(float(pl.get("rotation", 0.0)))
		var org := Vector2(float(o[0]), float(o[2]))
		var poly := PackedVector2Array()
		for c: Vector2 in [Vector2(-PAD_MARGIN, -PAD_MARGIN), Vector2(float(sz[0]) + PAD_MARGIN, -PAD_MARGIN), Vector2(float(sz[0]) + PAD_MARGIN, float(sz[1]) + PAD_MARGIN), Vector2(-PAD_MARGIN, float(sz[1]) + PAD_MARGIN)]:
			poly.append(org + c.rotated(rot))
		polys.append(poly)
	var cv: PackedStringArray = _arg(a, "--center", "-74,2172").split(",")
	var site: Dictionary = {"id": _arg(a, "--id", "pell_outskirts"), "kind": _arg(a, "--kind", "village"), "center": [float(cv[0]), float(cv[1])],
		"radius": float(_arg(a, "--radius", "300")), "name": _arg(a, "--name", "Pell's Crossing")}
	var ground: Dictionary = {"height": _h, "water": _keep_out}
	if _arg(a, "--grid", "") != "":
		# The keep-out field on an 8 m grid round the centre (debugging a plan that won't grow).
		var img := Image.create(150, 150, false, Image.FORMAT_RGB8)
		for j: int in 150:
			for i: int in 150:
				var x: float = float(cv[0]) + (i - 75) * 8.0
				var z: float = float(cv[1]) + (j - 75) * 8.0
				var k: float = _keep_out(x, z)
				var hgt: float = _h(x, z)
				var shade: float = fposmod(hgt, 4.0) / 8.0 + 0.4
				img.set_pixel(i, j, Color(0.9, 0.2, 0.2) if k < 0.0 else (Color(0.9, 0.7, 0.2) if k < 15.0 else Color(shade, shade, shade)))
		img.save_png(_arg(a, "--grid", ""))
	var t0: int = Time.get_ticks_msec()
	var plan: Dictionary = Planner.plan(site, ground, arterials, Planner.default_tuning(), int(_arg(a, "--seed", "7")))
	print("[plan] %d lots, stats %s in %d ms" % [(plan.get("lots", []) as Array).size(), JSON.stringify(plan.get("stats", {})), Time.get_ticks_msec() - t0])
	for lv: Variant in plan.get("lots", []):
		(lv as Dictionary)["y"] = _frame_height((lv as Dictionary)["frame"])
		# --residential: an extension of an authored town keeps its shops and civic buildings in the
		# old core; its own lots are houses (and farms out along the roads).
		if a.has("--residential") and not "rural" in Array((lv as Dictionary).get("zoning", [])):
			(lv as Dictionary)["zoning"] = ["residential"]
	# A new arterial is one of the town's own streets (graded the same in every region it crosses).
	if _arg(a, "--arterial-points", "") != "":
		var art: Dictionary = (arterials[0] as Dictionary).duplicate()
		art["class"] = "street"
		(plan["roads"] as Array).push_front(art)
	var fw: Dictionary = Planner.to_framework(plan, str(site["id"]), str(site["name"]))
	fw["tier_range"] = [1, 2]
	fw["authored"] = []
	var b: Rect2 = _bounds(plan)
	var town: Dictionary = {"id": site["id"], "name": site["name"], "kind": site["kind"], "framework": site["id"], "origin": [0.0, 0.0], "rotation": 0.0,
		"center": site["center"], "radius": site["radius"], "bounds": [snappedf(b.position.x, 0.1), snappedf(b.position.y, 0.1), ceilf(b.size.x), ceilf(b.size.y)]}
	var f2 := FileAccess.open(_arg(a, "--out", "/tmp/plan.json"), FileAccess.WRITE)
	f2.store_string(JSON.stringify({"framework": fw, "town": town}, "\t"))
	f2.close()
	get_tree().quit(0)


## The composed ground at (x, z): the region holding it (the first's, clamped, outside them all).
func _h(x: float, z: float) -> float:
	for r5: RegionTerrain in rts:
		if r5.height.contains(x, z):
			return r5.height.sample(x, z)
	return rt.height.sample(x, z)


## The planner's "water": the least distance to real water or to a keep-out (negative inside one).
func _keep_out(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var best: float = minf(minf(p.x - rect.position.x, rect.end.x - p.x), minf(p.y - rect.position.y, rect.end.y - p.y))
	var waters: Array = []
	for r4: RegionTerrain in rts:
		waters.append_array(r4.water)
	for w: Dictionary in waters:
		if str(w["kind"]) == "lake":
			var poly := PackedVector2Array()
			for q: Variant in w["polygon"]:
				poly.append(Vector2(float(q[0]), float(q[1])))
			best = minf(best, _poly_d(poly, p))
		else:
			var pts: Array = w["points"]
			var widths: Array = w["widths"]
			for k: int in pts.size() - 1:
				var a2 := Vector2(float(pts[k][0]), float(pts[k][1]))
				var b2 := Vector2(float(pts[k + 1][0]), float(pts[k + 1][1]))
				best = minf(best, Geometry2D.get_closest_point_to_segment(p, a2, b2).distance_to(p) - float(widths[k]) * 0.5)
	for poly2: PackedVector2Array in polys:
		best = minf(best, _poly_d(poly2, p))
	for ln: Array in lines:
		var line: Polyline2 = ln[0]
		if line.bounds.grow(float(ln[1]) + 60.0).has_point(p):
			best = minf(best, line.closest(p).x - float(ln[1]))
	for c: Vector3 in circles:
		best = minf(best, p.distance_to(Vector2(c.x, c.y)) - c.z)
	return best


static func _poly_d(poly: PackedVector2Array, p: Vector2) -> float:
	var d: float = INF
	for k: int in poly.size():
		d = minf(d, Geometry2D.get_closest_point_to_segment(p, poly[k], poly[(k + 1) % poly.size()]).distance_to(p))
	return -d if Streets.point_in(p, poly) else d


func _frame_height(f: Array) -> float:
	var c := Vector2(float(f[0]), float(f[1]))
	var yaw: float = deg_to_rad(float(f[4]))
	var az := Vector2(sin(yaw), cos(yaw))
	var ax := Vector2(az.y, -az.x)
	var acc: float = 0.0
	for k: int in 25:
		var p: Vector2 = c + ax * (((k % 5) / 4.0 - 0.5) * float(f[2])) + az * (((k / 5) / 4.0 - 0.5) * float(f[3]))
		acc += _h(p.x, p.y)
	return snappedf(acc / 25.0, 0.01)


func _bounds(plan: Dictionary) -> Rect2:
	var c: Array = plan.get("center", [0.0, 0.0])
	var bb := Rect2(Vector2(float(c[0]), float(c[1])), Vector2.ZERO)
	for lv: Variant in plan.get("lots", []):
		for q: Variant in lv.get("poly", []):
			bb = bb.expand(Vector2(float(q[0]), float(q[1])))
		var f: Array = lv["frame"]
		var half: float = Vector2(float(f[2]), float(f[3])).length() * 0.5
		bb = bb.merge(Rect2(Vector2(float(f[0]), float(f[1])), Vector2.ZERO).grow(half))
	for rd: Variant in plan.get("roads", []):
		var line: Polyline2 = Polyline2.from_array(rd["points"])
		bb = bb.merge(line.bounds.grow(float(rd["width"]) * 0.5 + float(rd.get("shoulder", 0.5))))
	for fv: Variant in plan.get("fixtures", []):
		bb = bb.expand(Vector2(float(fv["pos"][0]), float(fv["pos"][1])))
	return bb.grow(4.0)


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default
