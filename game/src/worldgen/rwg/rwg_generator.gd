class_name RwgGenerator
extends RefCounted
## The random world generator (ADR-0031, DESIGN §10.2). A pure function of (map seed, resolved
## WorldGenSettings, VERSION) that writes the same structure as the handcrafted map: a world.json
## (macro grid, rivers, lakes, roads, biome map, region roster) and one region.json feature list per
## region in the vocabulary of docs/REGIONS.md, plus the generated towns as frameworks. Composing,
## vegetation, water, POI placement and streaming then work unchanged.
##
## Stages: land (Terrain: shape, lakes, hydrology, valleys, rivers) -> towns (sites on flat dry
## ground, street plans from Towns) -> the road network (spanning tree between towns plus loops
## and exits off the map, Roads) -> the drop site and its trail -> danger by distance from it ->
## the biome map -> places (roadside, lake shore, summit, waterside, forest, remote; farmsteads)
## with their drives, tracks and trails -> bridges -> Bloom patches far from the start -> regions.
## Every stage draws from its own derived stream, so a change in one does not reshuffle the others.
## Run it on a worker thread (`progress` is called with (stage, 0..1)); content comes from
## ContentDB.instance.

## New ADR-0031 scripts by path, so this compiles before the editor registers their class names.
const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")
const Roads := preload("res://src/worldgen/rwg/rwg_roads.gd")
const Towns := preload("res://src/worldgen/rwg/rwg_towns.gd")

## Bump when the output for a given seed and settings changes: it is part of every world's id, so
## saves made with an older generator regenerate their world as it was (cached) or as now (TD-082).
const VERSION: int = 1
const BIOMES: PackedStringArray = ["conifer_forest", "birch_grove", "meadow", "rocky_slope"]

var settings: GenSettings
var tun: Dictionary
var names: Dictionary
var terrain := Terrain.new()
var router := Roads.new()
var world_id: String = ""
var size: int = 4
## {id, name, kind, fw_id, plan, origin: Vector2, rot: degrees, poly, center, entries: [Vector2],
##  leads: [Vector2], cell: region cell, tier: [lo, hi]}
var towns: Array[Dictionary] = []
## {id, kind: "poi" | "framework", def, origin: Vector2, rot, size: Vector2, poly, biome, skirt,
##  keep_water, access: Vector2, site, cell}
var places: Array[Dictionary] = []
## {id, name, class, points: PackedVector2Array, width, shoulder, surface, markings, bridges}
var roads: Array[Dictionary] = []
## {id, points: PackedVector2Array, width, surface}
var paths: Array[Dictionary] = []
## {pos: Vector2, yaw: degrees, cell}
var drop: Dictionary = {}
## {id, at: Vector2, radius, strength, edge, cell}
var blooms: Array[Dictionary] = []
## cell -> {cell, id, name, biome, danger, rect}
var regions: Dictionary = {}
var biome_cols: int = 0
var biome_step: float = 64.0
var biome_cells := PackedByteArray()
## Water distance per macro cell (m, chamfer), for quick site tests.
var water_dist := PackedFloat32Array()
var timings: Dictionary = {}
var warnings: PackedStringArray = []
var progress: Callable = Callable()

var _t0: int = 0


static func world_id_for(s: GenSettings) -> String:
	return "rwg_%s" % ("%x" % (Ids.hash64("v%d|%s" % [VERSION, s.key()]) & 0xffffffffffff)).lpad(12, "0")


## Runs the generator. Returns the generator (an RwgGenerator) with everything it made.
static func generate(s: GenSettings, p_progress: Callable = Callable()) -> RefCounted:
	var g: RefCounted = (load("res://src/worldgen/rwg/rwg_generator.gd") as GDScript).new()
	g.set(&"settings", s)
	g.set(&"progress", p_progress)
	g.call(&"run")
	return g


func rng(key: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.derive_seed(settings.seed, "rwg:" + key)
	return r


func _stage(name: String, t: float) -> void:
	var now: int = Time.get_ticks_msec()
	if _t0 > 0:
		timings[name] = now - _t0
	_t0 = now
	if progress.is_valid():
		progress.call(name, t)


func run() -> void:
	tun = GenSettings.tuning()
	names = GenSettings.names()
	size = settings.integer("size")
	world_id = world_id_for(settings)
	var t_all: int = Time.get_ticks_msec()
	_t0 = t_all
	if progress.is_valid():
		progress.call("Raising the land", 0.0)
	terrain.build(settings, tun, names)
	_stage("Raising the land", 0.3)
	_regions()
	_water_distance()
	_towns()
	_stage("Laying out towns", 0.45)
	router.setup(terrain, tun.get("roads", {}))
	for tw: Dictionary in towns:
		router.block_polygon(tw["poly"], 16.0)
	_road_network()
	_stage("Building roads", 0.6)
	_drop_site()
	_danger()
	_biome_map()
	_stage("Planting forests", 0.7)
	_places()
	_stage("Placing camps and cabins", 0.85)
	_bridges()
	_bloom()
	_name_regions()
	_stage("Mapping", 1.0)
	timings["total"] = Time.get_ticks_msec() - t_all


# --- Regions ---------------------------------------------------------------------------------------

func _regions() -> void:
	for r: int in size:
		for c: int in size:
			var cell: String = "%s%d" % [char(65 + c), r + 1]
			var rect := Rect2(Vector2(-size * 512.0 + c * 1024.0, -size * 512.0 + r * 1024.0), Vector2(1024.0, 1024.0))
			regions[cell] = {"cell": cell, "id": "", "name": "", "biome": "conifer_forest", "danger": 1, "rect": rect}


func cell_at(p: Vector2) -> String:
	var c: int = int(floor((p.x + size * 512.0) / 1024.0))
	var r: int = int(floor((p.y + size * 512.0) / 1024.0))
	if c < 0 or r < 0 or c >= size or r >= size:
		return ""
	return "%s%d" % [char(65 + c), r + 1]


## True when the whole polygon, grown by `margin`, lies inside one region (local features fade out
## within 48 m of a region border; a pad there would not be graded).
func inside_one_region(poly: PackedVector2Array, margin: float) -> bool:
	var cell: String = cell_at(poly[0])
	if cell == "":
		return false
	var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(-margin)
	for p: Vector2 in poly:
		if not rect.has_point(p):
			return false
	return true


## Chamfer distance (m) from every macro cell to the nearest lake or river cell.
func _water_distance() -> void:
	var n: int = terrain.n
	water_dist.resize(n * n)
	for c: int in n * n:
		water_dist[c] = 0.0 if terrain.lake_of[c] >= 0 or terrain.river_of[c] >= 0 else 1.0e9
	var s: float = terrain.step
	var sd: float = s * 1.4142
	for j: int in n:
		for i: int in n:
			var k: int = j * n + i
			var v: float = water_dist[k]
			if i > 0:
				v = minf(v, water_dist[k - 1] + s)
			if j > 0:
				v = minf(v, water_dist[k - n] + s)
				if i > 0:
					v = minf(v, water_dist[k - n - 1] + sd)
				if i < n - 1:
					v = minf(v, water_dist[k - n + 1] + sd)
			water_dist[k] = v
	for j2: int in range(n - 1, -1, -1):
		for i2: int in range(n - 1, -1, -1):
			var k2: int = j2 * n + i2
			var v2: float = water_dist[k2]
			if i2 < n - 1:
				v2 = minf(v2, water_dist[k2 + 1] + s)
			if j2 < n - 1:
				v2 = minf(v2, water_dist[k2 + n] + s)
				if i2 < n - 1:
					v2 = minf(v2, water_dist[k2 + n + 1] + sd)
				if i2 > 0:
					v2 = minf(v2, water_dist[k2 + n - 1] + sd)
			water_dist[k2] = v2


func water_at(p: Vector2) -> float:
	return water_dist[terrain.cell(p.x, p.y)]


## Exact clearance (m) from a polygon to the water: rivers' banks and lakes' shores (negative when
## it touches). Quick-rejects with the chamfer field.
func water_clearance(poly: PackedVector2Array) -> float:
	var best: float = INF
	for p: Vector2 in _dense(poly, 16.0):
		if water_at(p) > 220.0:
			continue
		best = minf(best, terrain.water_distance(p))
	return best


static func _dense(poly: PackedVector2Array, spacing: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for k: int in poly.size():
		var a: Vector2 = poly[k]
		var b: Vector2 = poly[(k + 1) % poly.size()]
		var steps: int = maxi(1, int(ceil(a.distance_to(b) / spacing)))
		for s: int in steps:
			out.append(a.lerp(b, float(s) / steps))
	var c := Vector2.ZERO
	for p: Vector2 in poly:
		c += p
	out.append(c / poly.size())
	return out


static func rect_poly(origin: Vector2, sz: Vector2, rot_deg: float) -> PackedVector2Array:
	var a: float = deg_to_rad(rot_deg)
	return PackedVector2Array([origin, origin + Vector2(sz.x, 0.0).rotated(a), origin + sz.rotated(a), origin + Vector2(0.0, sz.y).rotated(a)])


# --- Towns ---------------------------------------------------------------------------------------

func _towns() -> void:
	var want: int = settings.integer("towns")
	if want <= 0:
		return
	var tcfg: Dictionary = tun.get("towns", {})
	var mix: Dictionary = (tcfg.get("mix", {}) as Dictionary).get(settings.choice("town_size"), {"village": 1.0})
	var r := rng("towns")
	var kinds: Array[String] = []
	for k: int in want:
		kinds.append(_weighted(mix, r))
	# Big towns first: they need the most room.
	kinds.sort_custom(func(a: String, b: String) -> bool: return Towns.KINDS.find(a) > Towns.KINDS.find(b))
	var pool: Array = (names.get("towns", []) as Array).duplicate()
	var max_relief: float = float(tcfg.get("max_relief", 9.0))
	var spacing: float = float(tcfg.get("spacing", 650.0))
	var margin: float = float(tun.get("region_margin", 72.0))
	var hmin: float = INF
	var hmax: float = -INF
	for v: float in terrain.h:
		hmin = minf(hmin, v)
		hmax = maxf(hmax, v)
	for kind: String in kinds:
		var plan: Dictionary = Towns.plan(kind, tcfg, r)
		var sz := Vector2(float(plan["size"][0]), float(plan["size"][1]))
		var best: Dictionary = {}
		var best_score: float = INF
		for attempt: int in 260:
			var rot: float = 90.0 * float(r.randi() % 4)
			var half: Vector2 = (sz if int(rot) % 180 == 0 else Vector2(sz.y, sz.x)) * 0.5
			var c := Vector2(r.randf_range(-size * 512.0 + margin + half.x, size * 512.0 - margin - half.x),
				r.randf_range(-size * 512.0 + margin + half.y, size * 512.0 - margin - half.y))
			# The placement origin is the pad's corner: centre minus the rotated half size.
			var origin: Vector2 = c - (sz * 0.5).rotated(deg_to_rad(rot))
			var poly: PackedVector2Array = rect_poly(origin, sz, rot)
			if not inside_one_region(poly, margin):
				continue
			var too_close: bool = false
			for other: Dictionary in towns:
				if (other["center"] as Vector2).distance_to(c) < spacing:
					too_close = true
					break
			if too_close or water_at(c) < 90.0:
				continue
			var st: Dictionary = terrain.stats_in(poly)
			var relief: float = float(st["max"]) - float(st["min"])
			if relief > max_relief * 1.8:
				continue
			var clear: float = water_clearance(poly)
			if clear < 45.0:
				continue
			var elev: float = (float(st["mean"]) - hmin) / maxf(1.0, hmax - hmin)
			var central: float = c.length() / (size * 512.0)
			var near_water: float = 0.0 if clear < 320.0 else 4.0
			var score: float = relief + elev * 14.0 + central * 5.0 + near_water + r.randf() * 3.0
			if score < best_score:
				best_score = score
				best = {"origin": origin, "rot": rot, "poly": poly, "center": c, "mean": float(st["mean"])}
		if best.is_empty():
			warnings.append("no room for a %s" % kind)
			continue
		var ti: int = towns.size()
		var name: String = str(pool.pop_at(r.randi() % pool.size())) if not pool.is_empty() else "Town %d" % (ti + 1)
		var tid: String = _slug(name)
		var a: float = deg_to_rad(float(best["rot"]))
		# Roads arrive along the main street's axis: an approach point 22 m out and a lead 46 m out,
		# where the route over the land starts (a road meeting the entry at an angle swung its last
		# curve into the pad).
		var entries: Array[Vector2] = []
		var approaches: Array[Vector2] = []
		var leads: Array[Vector2] = []
		var dirs: Array = plan.get("entry_dirs", [])
		for ei: int in (plan["entries"] as Array).size():
			var e: Array = plan["entries"][ei]
			var local := Vector2(float(e[0]), float(e[1]))
			var outward := Vector2(float(dirs[ei][0]), float(dirs[ei][1])) if ei < dirs.size() else Vector2(-1.0 if local.x < 1.0 else 1.0, 0.0)
			entries.append((best["origin"] as Vector2) + local.rotated(a))
			approaches.append((best["origin"] as Vector2) + (local + outward * 22.0).rotated(a))
			leads.append((best["origin"] as Vector2) + (local + outward * 46.0).rotated(a))
		terrain.flatten(best["poly"], float(best["mean"]), 56.0)
		towns.append({"id": tid, "name": name, "kind": kind, "fw_id": "%s_%s" % [world_id, tid], "plan": plan,
			"origin": best["origin"], "rot": best["rot"], "poly": best["poly"], "center": best["center"],
			"entries": entries, "approaches": approaches, "leads": leads, "cell": cell_at(best["center"]), "tier": [1, 2]})


static func _weighted(w: Dictionary, r: RandomNumberGenerator) -> String:
	var total: float = 0.0
	for k: Variant in w:
		total += float(w[k])
	var x: float = r.randf() * total
	var last: String = ""
	for k2: Variant in w:
		last = str(k2)
		x -= float(w[k2])
		if x < 0.0:
			return last
	return last


static func _slug(s: String) -> String:
	var out: String = ""
	for ch: String in s.to_lower():
		out += ch if ((ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9")) else "_"
	while out.contains("__"):
		out = out.replace("__", "_")
	return out.strip_edges().trim_suffix("_").trim_prefix("_")


# --- Roads -----------------------------------------------------------------------------------------

func _road_network() -> void:
	var rcfg: Dictionary = tun.get("roads", {})
	var r := rng("roads")
	var density: String = settings.choice("roads")
	# Spanning tree between towns (Prim, by the gap between their nearest entries), plus loops.
	var edges: Array = []
	for i: int in towns.size():
		for j: int in range(i + 1, towns.size()):
			var best: Array = _closest_entries(towns[i], towns[j])
			edges.append([float(best[0]), i, j, best[1], best[2]])
	edges.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]) or (float(a[0]) == float(b[0]) and int(a[1]) * 100 + int(a[2]) < int(b[1]) * 100 + int(b[2])))
	var parent: Array[int] = []
	for i2: int in towns.size():
		parent.append(i2)
	var chosen: Array = []
	var rest: Array = []
	for e: Array in edges:
		var ra: int = _find(parent, int(e[1]))
		var rb: int = _find(parent, int(e[2]))
		if ra != rb:
			parent[ra] = rb
			chosen.append(e)
		else:
			rest.append(e)
	var extra: int = int((rcfg.get("extra", {}) as Dictionary).get(density, 1))
	var longest: float = 0.0
	for e2: Array in chosen:
		longest = maxf(longest, float(e2[0]))
	for e3: Array in rest:
		if extra <= 0:
			break
		if float(e3[0]) < maxf(longest * 1.5, 1800.0):
			chosen.append(e3)
			extra -= 1
	for e4: Array in chosen:
		var ta: Dictionary = towns[int(e4[1])]
		var tb: Dictionary = towns[int(e4[2])]
		var big: bool = str(ta["kind"]) != "hamlet" and str(tb["kind"]) != "hamlet"
		_connect(ta, int(e4[3]), tb, int(e4[4]), "highway" if big else "county", "%s to %s" % [ta["name"], tb["name"]])
	# Roads off the map: the biggest towns' far entries to the nearest edge.
	var exits: int = int((rcfg.get("exits", {}) as Dictionary).get(density, 1))
	var order: Array = []
	for i3: int in towns.size():
		order.append([Towns.KINDS.find(str(towns[i3]["kind"])), i3])
	order.sort_custom(func(a: Array, b: Array) -> bool: return int(a[0]) > int(b[0]) or (int(a[0]) == int(b[0]) and int(a[1]) < int(b[1])))
	for o: Array in order:
		if exits <= 0:
			break
		var tw: Dictionary = towns[int(o[1])]
		# The easiest way off the map: from either entry to the nearest point of any edge, the
		# cheapest route (not simply the nearest edge, which in mountains meant switchbacks over a
		# range).
		var best_route := PackedVector2Array()
		var best_cost: float = INF
		for lead_i: int in (tw["leads"] as Array).size():
			var from: Vector2 = tw["leads"][lead_i]
			for to: Vector2 in _edge_points(from):
				var pts: PackedVector2Array = _route_from_entry(tw, lead_i, to)
				if pts.is_empty():
					continue
				var c: float = router.last_cost
				if c < best_cost:
					best_cost = c
					best_route = pts
		if _add_road(best_route, "highway", "%s road" % tw["name"], true):
			exits -= 1
	if towns.is_empty():
		# No towns: one county road across the map still gives the land a way through.
		var a := Vector2(-size * 512.0, r.randf_range(-size * 300.0, size * 300.0))
		var b := Vector2(size * 512.0, r.randf_range(-size * 300.0, size * 300.0))
		_add_road(router.route(a + Vector2(16, 0), b - Vector2(16, 0), 900.0), "county", "Old county road", true)


static func _find(parent: Array[int], i: int) -> int:
	while parent[i] != i:
		parent[i] = parent[parent[i]]
		i = parent[i]
	return i


func _closest_entries(a: Dictionary, b: Dictionary) -> Array:
	var best: Array = [INF, 0, 0]
	for i: int in (a["leads"] as Array).size():
		for j: int in (b["leads"] as Array).size():
			var d: float = (a["leads"][i] as Vector2).distance_to(b["leads"][j])
			if d < float(best[0]):
				best = [d, i, j]
	return best


## The entry of a town nearer the map edge.
func _edge_side_entry(tw: Dictionary) -> int:
	var best: int = 0
	var bd: float = INF
	for i: int in (tw["leads"] as Array).size():
		var p: Vector2 = tw["leads"][i]
		var d: float = size * 512.0 - maxf(absf(p.x), absf(p.y))
		if d < bd:
			bd = d
			best = i
	return best


## The nearest point of each map edge to p (8 m inside it).
func _edge_points(p: Vector2) -> Array[Vector2]:
	var e: float = size * 512.0 - 8.0
	return [Vector2(-e, p.y), Vector2(e, p.y), Vector2(p.x, -e), Vector2(p.x, e)]


func _edge_point(p: Vector2) -> Vector2:
	var e: float = size * 512.0 - 8.0
	var dx: float = e - absf(p.x)
	var dz: float = e - absf(p.y)
	if dx < dz:
		return Vector2(signf(p.x) * e if p.x != 0.0 else e, p.y)
	return Vector2(p.x, signf(p.y) * e if p.y != 0.0 else e)


## Route from a town's entry: the main street's end, its lead-out, then A* to `to`.
func _route_from_entry(tw: Dictionary, entry: int, to: Vector2) -> PackedVector2Array:
	var mid: PackedVector2Array = router.route(tw["leads"][entry], to, 700.0, 0.9)
	if mid.is_empty():
		return mid
	var out := PackedVector2Array([tw["entries"][entry], tw["approaches"][entry]])
	out.append_array(mid)
	return out


func _connect(ta: Dictionary, ea: int, tb: Dictionary, eb: int, cls: String, name: String) -> void:
	var a: Vector2 = ta["leads"][ea]
	var b: Vector2 = tb["leads"][eb]
	var pieces: Array[Dictionary] = router.route_pieces(a, b, 900.0, 0.9 if cls == "highway" else 0.7)
	if pieces.is_empty():
		warnings.append("no road from %s to %s" % [ta["name"], tb["name"]])
		return
	# Where the route meets roads already built it joins them (a T-junction snapped onto the other
	# road's line) instead of running beside them.
	for pc: Dictionary in pieces:
		var mid: PackedVector2Array = pc["points"]
		var pts := PackedVector2Array()
		if bool(pc["start_exact"]):
			pts.append_array([ta["entries"][ea], ta["approaches"][ea]])
		else:
			mid[0] = _snap_to_road(mid[0])
		if not bool(pc["end_exact"]):
			mid[mid.size() - 1] = _snap_to_road(mid[mid.size() - 1])
		pts.append_array(mid)
		if bool(pc["end_exact"]):
			pts.append_array([tb["approaches"][eb], tb["entries"][eb]])
		_add_road(pts, cls, name, false)


## The nearest point on a road already built (a junction), or p itself when none is near.
func _snap_to_road(p: Vector2) -> Vector2:
	var nr: Array = nearest_road(p)
	return nr[1] if float(nr[0]) < terrain.step * 1.5 else p


func _add_road(pts: PackedVector2Array, cls: String, name: String, off_map: bool) -> bool:
	if pts.size() < 2:
		return false
	var spec: Dictionary = (tun.get("roads", {}) as Dictionary).get(cls, {"surface": "gravel", "width": 5.0, "shoulder": 1.5})
	if off_map:
		var last: Vector2 = pts[pts.size() - 1]
		if absf(last.x) > size * 512.0 - 20.0 or absf(last.y) > size * 512.0 - 20.0:
			var out: Vector2 = (last - pts[pts.size() - 2]).normalized()
			pts.append(last + out * 60.0)
	router.mark(pts, roads.size())
	roads.append({"id": "road_%d" % roads.size(), "name": name, "class": cls, "points": pts, "width": float(spec["width"]),
		"shoulder": float(spec["shoulder"]), "surface": str(spec["surface"]), "markings": cls == "highway", "bridges": [],
		"line": Polyline2.from_array(Terrain._arr(pts))})
	return true


## The nearest point on any road to p: [distance, point, road index, arc]. `clear_of_towns`: only
## points at least 30 m outside every town pad (a track must not start on a town's street).
func nearest_road(p: Vector2, classes: PackedStringArray = [], clear_of_towns: bool = false) -> Array:
	var best: Array = [INF, p, -1, 0.0]
	for i: int in roads.size():
		if not classes.is_empty() and not classes.has(str(roads[i]["class"])):
			continue
		var line: Polyline2 = roads[i]["line"]
		if not clear_of_towns:
			if line.bounds.grow(minf(float(best[0]), 4000.0)).has_point(p) or float(best[0]) == INF:
				var q: Vector3 = line.closest(p)
				if q.x < float(best[0]):
					best = [q.x, line.point_at(q.y), i, q.y]
			continue
		for k: int in line.points.size():
			var q2: Vector2 = line.points[k]
			var d: float = q2.distance_to(p)
			if d >= float(best[0]) or _near_town(q2, 30.0):
				continue
			best = [d, q2, i, line.lengths[k]]
	return best


func _near_town(p: Vector2, gap: float) -> bool:
	for tw: Dictionary in towns:
		var poly: PackedVector2Array = tw["poly"]
		if Geometry2D.is_point_in_polygon(p, poly) or Terrain._poly_distance(poly, p) < gap:
			return true
	return false


## Clearance (m) between a polygon and every road's edge (shoulder included).
func road_clearance(poly: PackedVector2Array, skip: int = -1) -> float:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	var best: float = INF
	for i: int in roads.size():
		if i == skip:
			continue
		var rd: Dictionary = roads[i]
		var line: Polyline2 = rd["line"]
		var half: float = float(rd["width"]) * 0.5 + float(rd["shoulder"])
		if not line.bounds.grow(half + 60.0).intersects(bb.grow(60.0)):
			continue
		for k: int in line.points.size():
			var q: Vector2 = line.points[k]
			if not bb.grow(half + 60.0).has_point(q):
				continue
			var d: float = 0.0 if Geometry2D.is_point_in_polygon(q, poly) else Terrain._poly_distance(poly, q)
			best = minf(best, d - half)
	return best


# --- Drop site -------------------------------------------------------------------------------------

func _drop_site() -> void:
	var dcfg: Dictionary = tun.get("drop_site", {})
	var r := rng("drop")
	var town_d: float = float(dcfg.get("town_distance", 380.0))
	var rd: Array = dcfg.get("road_distance", [40, 220])
	var best: Dictionary = {}
	var best_score: float = INF
	for attempt: int in 600:
		var p := Vector2(r.randf_range(-size * 512.0 + 90.0, size * 512.0 - 90.0), r.randf_range(-size * 512.0 + 90.0, size * 512.0 - 90.0))
		if not inside_one_region(PackedVector2Array([p - Vector2(24, 24), p + Vector2(24, 24)]), 60.0):
			continue
		if water_at(p) < 70.0 or terrain.slope(p.x, p.y) > 0.12:
			continue
		var near_town: float = INF
		for tw: Dictionary in towns:
			near_town = minf(near_town, Terrain._poly_distance(tw["poly"], p))
		if near_town < town_d:
			continue
		var nr: Array = nearest_road(p)
		var road_d: float = float(nr[0])
		if not roads.is_empty() and (road_d < float(rd[0]) or road_d > float(rd[1])):
			continue
		if terrain.water_distance(p) < 50.0:
			continue
		# Close enough to walk to a town on the first day, central rather than at the edge.
		var score: float = (absf(near_town - 750.0) / 100.0 if near_town < INF else 0.0) + p.length() / (size * 512.0) * 4.0 + terrain.slope(p.x, p.y) * 30.0 + r.randf() * 2.0
		if score < best_score:
			best_score = score
			best = {"pos": p, "road": nr}
	if best.is_empty():
		# Fallback: the flattest dry spot near the middle.
		var p2 := Vector2.ZERO
		for k: int in 400:
			var q := Vector2(r.randf_range(-size * 300.0, size * 300.0), r.randf_range(-size * 300.0, size * 300.0))
			if water_at(q) > 70.0 and terrain.slope(q.x, q.y) < 0.15 and inside_one_region(PackedVector2Array([q - Vector2(24, 24), q + Vector2(24, 24)]), 60.0):
				p2 = q
				break
		best = {"pos": p2, "road": nearest_road(p2)}
		warnings.append("drop site placed by fallback")
	var pos: Vector2 = best["pos"]
	var target: Vector2 = (best["road"] as Array)[1] if int((best["road"] as Array)[2]) >= 0 else pos + Vector2(40, 0)
	var v: Vector2 = (target - pos).normalized()
	drop = {"pos": pos, "yaw": snappedf(rad_to_deg(atan2(-v.x, -v.y)), 1.0), "cell": cell_at(pos)}
	if int((best["road"] as Array)[2]) >= 0:
		var trail: PackedVector2Array = router.route(pos, target, 300.0)
		if trail.size() >= 2:
			paths.append({"id": "drop_trail", "points": trail, "width": 2.2, "surface": "dirt"})


func _danger() -> void:
	var p: Vector2 = drop.get("pos", Vector2.ZERO)
	var far: float = 0.0
	for cell: String in regions:
		far = maxf(far, ((regions[cell]["rect"] as Rect2).get_center()).distance_to(p))
	for cell2: String in regions:
		var d: float = ((regions[cell2]["rect"] as Rect2).get_center()).distance_to(p)
		regions[cell2]["danger"] = clampi(1 + int(round(d / maxf(1.0, far) * 4.0)), 1, 5)
	regions[drop.get("cell", "A1")]["danger"] = 1
	for tw: Dictionary in towns:
		var dg: int = int(regions[tw["cell"]]["danger"])
		tw["tier"] = [1, 2] if dg <= 2 else [1, 3]


# --- Biomes ------------------------------------------------------------------------------------------

func _biome_map() -> void:
	biome_step = float(tun.get("biome_step", 64.0))
	biome_cols = int(round(size * 1024.0 / biome_step))
	biome_cells.resize(biome_cols * biome_cols)
	var w: Array[float] = [settings.num("conifer"), settings.num("birch"), settings.num("meadow"), settings.num("rocky")]
	if w[0] + w[1] + w[2] + w[3] <= 0.0:
		w[0] = 1.0
	var noises: Array[FastNoiseLite] = []
	for k: int in 4:
		var nz := FastNoiseLite.new()
		nz.seed = Ids.derive_seed(settings.seed, "rwg:biome%d" % k) & 0x7fffffff
		nz.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		nz.fractal_type = FastNoiseLite.FRACTAL_FBM
		nz.fractal_octaves = 3
		nz.frequency = 1.0 / 650.0
		noises.append(nz)
	var hmin: float = INF
	var hmax: float = -INF
	for v: float in terrain.h:
		hmin = minf(hmin, v)
		hmax = maxf(hmax, v)
	var raw := PackedByteArray()
	raw.resize(biome_cols * biome_cols)
	for j: int in biome_cols:
		for i: int in biome_cols:
			var p := Vector2(-size * 512.0 + (i + 0.5) * biome_step, -size * 512.0 + (j + 0.5) * biome_step)
			var e: float = (terrain.height(p.x, p.y) - hmin) / maxf(1.0, hmax - hmin)
			var s: float = terrain.slope(p.x, p.y)
			var wet: float = 1.0 - smoothstep(0.0, 260.0, water_at(p))
			var town_ring: float = 0.0
			for tw: Dictionary in towns:
				var d: float = (tw["center"] as Vector2).distance_to(p)
				# Cleared ground round a town (yards, pasture), then the trees close in again.
				town_ring = maxf(town_ring, 1.0 - smoothstep(110.0, 260.0, d))
			var nc: float = noises[0].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nb: float = noises[1].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nm: float = noises[2].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nr: float = noises[3].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var sc: Array[float] = [
				w[0] * (0.55 + 0.6 * nc),
				w[1] * (0.3 + 0.85 * nb) * (0.8 + 0.6 * wet),
				w[2] * (0.25 + 0.95 * nm) * (1.25 - 0.9 * smoothstep(0.05, 0.22, s)) * (1.0 - 0.6 * e) + town_ring * (0.6 + w[2]),
				# Bare rock on the heights and the steepest ground only: the composer already turns
				# slopes past ~35 degrees to rock, and highlands should keep their forested sides.
				w[3] * (smoothstep(0.62, 0.97, e) * 1.5 + smoothstep(0.32, 0.65, s) * 0.8 + 0.1 * nr),
			]
			var bi: int = 0
			for k2: int in range(1, 4):
				if sc[k2] > sc[bi]:
					bi = k2
			raw[j * biome_cols + i] = bi
	# One majority pass: no lone cells.
	for j2: int in biome_cols:
		for i2: int in biome_cols:
			var counts: Array[int] = [0, 0, 0, 0]
			for dj: int in range(-1, 2):
				for di: int in range(-1, 2):
					var ii: int = clampi(i2 + di, 0, biome_cols - 1)
					var jj: int = clampi(j2 + dj, 0, biome_cols - 1)
					counts[raw[jj * biome_cols + ii]] += 1
			var own: int = raw[j2 * biome_cols + i2]
			var top: int = own
			for k3: int in 4:
				if counts[k3] > counts[top]:
					top = k3
			biome_cells[j2 * biome_cols + i2] = top if counts[own] <= 2 else own
	# Each region's dominant biome (its default and summary).
	for cell: String in regions:
		var rect: Rect2 = regions[cell]["rect"]
		var counts2: Array[int] = [0, 0, 0, 0]
		for j3: int in biome_cols:
			for i3: int in biome_cols:
				var p2 := Vector2(-size * 512.0 + (i3 + 0.5) * biome_step, -size * 512.0 + (j3 + 0.5) * biome_step)
				if rect.has_point(p2):
					counts2[biome_cells[j3 * biome_cols + i3]] += 1
		var top2: int = 0
		for k4: int in 4:
			if counts2[k4] > counts2[top2]:
				top2 = k4
		regions[cell]["biome"] = BIOMES[top2]


func biome_at(p: Vector2) -> String:
	var i: int = clampi(int(floor((p.x + size * 512.0) / biome_step)), 0, biome_cols - 1)
	var j: int = clampi(int(floor((p.y + size * 512.0) / biome_step)), 0, biome_cols - 1)
	return BIOMES[biome_cells[j * biome_cols + i]]


# --- Places --------------------------------------------------------------------------------------

func _places() -> void:
	var wcfg: Dictionary = tun.get("wilderness", {})
	var density: float = settings.num("wilderness")
	var r := rng("places")
	var db: Node = ContentDB.instance
	var max_danger: int = 1
	for cell: String in regions:
		max_danger = maxi(max_danger, int(regions[cell]["danger"]))
	var order: Array[String] = ["roadside", "lake_shore", "summit", "waterside", "remote", "forest"]
	var pool: Array = wcfg.get("pool", [])
	for site: String in order:
		for e: Variant in pool:
			var pe: Dictionary = e
			if str(pe.get("site", "")) != site or int(pe.get("min_danger", 1)) > max_danger:
				continue
			var pd: PoiDef = db.call(&"get_def", &"poi", StringName(str(pe.get("poi", "")))) as PoiDef if db != null else null
			if pd == null:
				continue
			var expected: float = float(pe.get("per_region", 0.1)) * size * size * density
			var count: int = mini(int(pe.get("max", 2)), int(floor(expected + r.randf())))
			for k: int in count:
				_place_one(pe, Vector2(pd.footprint), r, wcfg)
	var farm: Dictionary = wcfg.get("farmsteads", {})
	var fw: FrameworkDef = db.call(&"get_def", &"framework", StringName(str(farm.get("framework", "")))) as FrameworkDef if db != null and not farm.is_empty() else null
	if fw != null and int(farm.get("min_danger", 1)) <= max_danger:
		var fcount: int = mini(int(farm.get("max", 1)), int(floor(float(farm.get("per_region", 0.1)) * size * size * density + r.randf())))
		for k2: int in fcount:
			var fe: Dictionary = farm.duplicate()
			fe["site"] = "farm"
			fe["access"] = "track"
			_place_one(fe, Vector2(fw.size), r, wcfg)


## Tries to place one place of a pool entry: candidates for its site, the first that fits.
func _place_one(pe: Dictionary, fp: Vector2, r: RandomNumberGenerator, wcfg: Dictionary) -> void:
	var site: String = str(pe.get("site", "forest"))
	var is_fw: bool = pe.has("framework")
	var def_id: String = str(pe.get("framework", pe.get("poi", "")))
	var keep_water: bool = bool(pe.get("keep_water", false))
	var min_danger: int = int(pe.get("min_danger", 1))
	var spacing: float = float(wcfg.get("spacing", 160.0))
	var max_relief: float = float(wcfg.get("max_relief", 7.0))
	var margin: float = float(tun.get("region_margin", 72.0)) - 8.0
	for attempt: int in 90:
		var cand: Dictionary = _candidate(site, fp, r)
		if cand.is_empty():
			continue
		var origin: Vector2 = cand["origin"]
		var rot: float = cand["rot"]
		var poly: PackedVector2Array = rect_poly(origin, fp, rot)
		var centre: Vector2 = origin + (fp * 0.5).rotated(deg_to_rad(rot))
		var cell: String = cell_at(centre)
		if cell == "" or int(regions[cell]["danger"]) < min_danger or not inside_one_region(poly, margin):
			continue
		if (drop.get("pos", Vector2(1e9, 1e9)) as Vector2).distance_to(centre) < float((tun.get("drop_site", {}) as Dictionary).get("poi_distance", 160.0)) + fp.length() * 0.5:
			continue
		if _hits_built(poly, spacing * 0.5):
			continue
		var road_gap: float = road_clearance(poly)
		if road_gap < (4.0 if site == "roadside" else 18.0):
			continue
		if not keep_water:
			if water_clearance(poly) < 14.0:
				continue
			var st: Dictionary = terrain.stats_in(poly)
			if float(st["max"]) - float(st["min"]) > max_relief:
				continue
			terrain.flatten(poly, float(st["mean"]), 26.0)
		var pid: String = "%s_%d" % [def_id, places.size()]
		var fwd: Vector2 = Vector2(0.0, 1.0).rotated(deg_to_rad(rot))
		var access: Vector2 = origin + Vector2(fp.x * 0.5, fp.y).rotated(deg_to_rad(rot)) + fwd * 3.0
		var place: Dictionary = {"id": pid, "kind": "framework" if is_fw else "poi", "def": def_id, "origin": origin, "rot": rot, "size": fp,
			"poly": poly, "biome": str(pe.get("biome", "meadow")), "skirt": float(pe.get("skirt", 10.0)), "keep_water": keep_water,
			"access": access, "site": site, "cell": cell, "center": centre}
		places.append(place)
		router.block_polygon(poly, 6.0)
		_access(place, str(pe.get("access", "trail")), cand)
		return


## A candidate frame {origin, rot} for a site, or {} (the caller tries again).
func _candidate(site: String, fp: Vector2, r: RandomNumberGenerator) -> Dictionary:
	var lim: float = size * 512.0 - 100.0
	match site:
		"roadside":
			var cands: Array[int] = []
			for i: int in roads.size():
				if str(roads[i]["class"]) in ["highway", "county"]:
					cands.append(i)
			if cands.is_empty():
				return {}
			var rd: Dictionary = roads[cands[r.randi() % cands.size()]]
			var line: Polyline2 = rd["line"]
			if line.total_length < 300.0:
				return {}
			var s: float = r.randf_range(120.0, line.total_length - 120.0)
			var p: Vector2 = line.point_at(s)
			var tg: Vector2 = line.tangent_at(s)
			# A straight stretch only: the drive and the frontage must line up with the road.
			if tg.dot(line.tangent_at(s - 30.0)) < 0.97 or tg.dot(line.tangent_at(s + 30.0)) < 0.97:
				return {}
			var nrm := Vector2(-tg.y, tg.x) * (1.0 if r.randf() < 0.5 else -1.0)
			var gap: float = float(rd["width"]) * 0.5 + float(rd["shoulder"]) + 9.0
			var front: Vector2 = p + nrm * gap
			# The building's front (+Z) faces the road: local +Z maps to -nrm.
			var rot: float = rad_to_deg(atan2(nrm.x, -nrm.y))
			var origin: Vector2 = front - Vector2(fp.x * 0.5, fp.y).rotated(deg_to_rad(rot))
			return {"origin": origin, "rot": snappedf(rot, 0.1), "road": rd, "road_point": p + nrm * (float(rd["width"]) * 0.5)}
		"lake_shore":
			if terrain.lakes.is_empty():
				return {}
			var lk: Dictionary = terrain.lakes[r.randi() % terrain.lakes.size()]
			var poly: PackedVector2Array = lk["polygon"]
			var k: int = r.randi() % poly.size()
			var sp: Vector2 = poly[k]
			var outward: Vector2 = (sp - (lk["center"] as Vector2)).normalized()
			# Back to the water, front to the land; the back third stands on piles over the lake.
			var rot2: float = rad_to_deg(atan2(-outward.x, outward.y))
			var back_mid: Vector2 = sp - outward * fp.y * 0.32
			var origin2: Vector2 = back_mid - Vector2(fp.x * 0.5, 0.0).rotated(deg_to_rad(rot2))
			return {"origin": origin2, "rot": snappedf(rot2, 0.1)}
		_:
			var best: Dictionary = {}
			var best_score: float = INF
			for k2: int in 14:
				var p2 := Vector2(r.randf_range(-lim, lim), r.randf_range(-lim, lim))
				var score: float = 0.0
				var wd: float = water_at(p2)
				var e: float = terrain.height(p2.x, p2.y)
				var biome: String = biome_at(p2)
				match site:
					"summit":
						score = -e + terrain.slope(p2.x, p2.y) * 300.0
					"waterside":
						if wd < 60.0 or wd > 200.0:
							continue
						score = wd + terrain.slope(p2.x, p2.y) * 300.0
					"forest":
						if biome != "conifer_forest" and biome != "birch_grove":
							continue
						score = terrain.slope(p2.x, p2.y) * 300.0 + r.randf() * 20.0
					"remote":
						score = -(drop.get("pos", Vector2.ZERO) as Vector2).distance_to(p2) * 0.05 - e * 0.2 + terrain.slope(p2.x, p2.y) * 200.0
					"farm":
						if biome != "meadow" and biome != "birch_grove":
							score += 30.0
						score += terrain.slope(p2.x, p2.y) * 400.0 + r.randf() * 10.0
				if score < best_score:
					best_score = score
					best = {"p": p2}
			if best.is_empty():
				return {}
			var rot3: float = 15.0 * float(r.randi() % 24)
			var origin3: Vector2 = (best["p"] as Vector2) - (fp * 0.5).rotated(deg_to_rad(rot3))
			return {"origin": origin3, "rot": rot3}
	return {}


## True when a polygon (grown by `gap`) touches a town, another place, or the drop site's clearing.
func _hits_built(poly: PackedVector2Array, gap: float) -> bool:
	var grown: PackedVector2Array = poly
	var off: Array = Geometry2D.offset_polygon(poly, gap)
	if not off.is_empty():
		grown = off[0]
	for tw: Dictionary in towns:
		var tg: Array = Geometry2D.offset_polygon(tw["poly"], 40.0)
		if not Geometry2D.intersect_polygons(grown, tg[0] if not tg.is_empty() else tw["poly"]).is_empty():
			return true
	for pl: Dictionary in places:
		if not Geometry2D.intersect_polygons(grown, pl["poly"]).is_empty():
			return true
	return false


## The way to a place: a short asphalt drive off the road it fronts, a dirt track or a footpath
## from the nearest road to its front.
func _access(place: Dictionary, kind: String, cand: Dictionary) -> void:
	var to: Vector2 = place["access"]
	if kind == "drive" and cand.has("road_point"):
		var from: Vector2 = cand["road_point"]
		var pts := PackedVector2Array([from, from.lerp(to, 0.5), to + (to - from).normalized() * 2.0])
		_add_road(pts, "drive", "%s drive" % place["def"], false)
		return
	var nr: Array = nearest_road(to, ["highway", "county", "track"] if kind == "track" else [], true)
	# Far from any road a place is reached cross-country: a trail kilometres long reads as a
	# scribble across the map.
	if int(nr[2]) < 0 or float(nr[0]) > (900.0 if kind == "track" else 700.0):
		return
	var start: Vector2 = nr[1]
	var route: PackedVector2Array = router.route(start, to, 500.0, 0.6, 1.5 if kind == "trail" else 1.25)
	if route.size() < 2:
		return
	# A track that would have to wind up a slope (half as long again as the straight line) is a
	# footpath instead: switchbacks of dirt road read as scribble.
	var length: float = 0.0
	for k: int in route.size() - 1:
		length += route[k].distance_to(route[k + 1])
	if kind == "track" and length < start.distance_to(to) * 1.5:
		_add_road(route, "track", "%s track" % place["def"], false)
	else:
		paths.append({"id": "%s_trail" % place["id"], "points": route, "width": 1.6, "surface": "dirt"})


# --- Bridges ---------------------------------------------------------------------------------------

## Every road crossing a river gets a bridge span over its channel and banks.
func _bridges() -> void:
	for rd: Dictionary in roads:
		var line: Polyline2 = rd["line"]
		for rv: Dictionary in terrain.rivers:
			var rl: Polyline2 = rv["line"]
			if not line.bounds.grow(20.0).intersects(rl.bounds.grow(20.0)):
				continue
			var spans: Array = []
			for k: int in line.points.size() - 1:
				var a: Vector2 = line.points[k]
				var b: Vector2 = line.points[k + 1]
				if not rl.bounds.grow(4.0).has_point(a) and not rl.bounds.grow(4.0).has_point(b):
					continue
				var qa: Vector3 = rl.closest(a)
				var qb: Vector3 = rl.closest(b)
				if qa.x > 40.0 and qb.x > 40.0:
					continue
				if signf(qa.z) == signf(qb.z):
					continue
				var tt: float = qa.x / maxf(0.001, qa.x + qb.x)
				var x: Vector2 = a.lerp(b, tt)
				var s_road: float = line.lengths[k] + a.distance_to(b) * tt
				var q: Vector3 = rl.closest(x)
				var half_w: float = rl.value_at(Array(rv["widths"]), q.y) * 0.5
				var sin_a: float = absf(line.tangent_at(s_road).cross(rl.tangent_at(q.y)))
				var reach: float = (half_w + float(rv["bank"]) + 4.0) / maxf(0.4, sin_a) + 6.0
				var dup: bool = false
				for sp: Array in spans:
					if absf(float(sp[0]) - s_road) < 60.0:
						dup = true
				if dup:
					continue
				spans.append([s_road, reach])
			for sp2: Array in spans:
				var s0: float = maxf(0.0, float(sp2[0]) - float(sp2[1]))
				var s1: float = minf(line.total_length, float(sp2[0]) + float(sp2[1]))
				var p0: Vector2 = line.point_at(s0)
				var p1: Vector2 = line.point_at(s1)
				(rd["bridges"] as Array).append({"from": [snappedf(p0.x, 0.1), snappedf(p0.y, 0.1)], "to": [snappedf(p1.x, 0.1), snappedf(p1.y, 0.1)], "deck": "auto"})


# --- The Bloom -----------------------------------------------------------------------------------

func _bloom() -> void:
	var bcfg: Dictionary = tun.get("bloom", {})
	var per: Array = bcfg.get("per_danger", [0, 0, 0.6, 1.2, 2.0])
	var rr: Array = bcfg.get("radius", [40, 110])
	var r := rng("bloom")
	for cell: String in regions:
		var dg: int = int(regions[cell]["danger"])
		var want: int = int(floor(float(per[clampi(dg - 1, 0, per.size() - 1)]) + r.randf()))
		var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(-120.0)
		for k: int in want:
			for attempt: int in 30:
				var p := Vector2(r.randf_range(rect.position.x, rect.end.x), r.randf_range(rect.position.y, rect.end.y))
				var b: String = biome_at(p)
				if b != "conifer_forest" and b != "birch_grove":
					continue
				if water_at(p) < 40.0 or float(nearest_road(p)[0]) < 40.0:
					continue
				var clear: bool = true
				for tw: Dictionary in towns:
					if Terrain._poly_distance(tw["poly"], p) < 120.0:
						clear = false
				for pl: Dictionary in places:
					if (pl["center"] as Vector2).distance_to(p) < 60.0:
						clear = false
				if not clear:
					continue
				blooms.append({"id": "bloom_%s_%d" % [cell.to_lower(), k], "at": p, "radius": snappedf(r.randf_range(float(rr[0]), float(rr[1])), 1.0),
					"strength": snappedf(clampf(0.45 + 0.15 * (dg - 3) + r.randf() * 0.25, 0.3, 1.0), 0.01), "edge": snappedf(r.randf_range(0.45, 0.75), 0.01), "cell": cell})
				break


# --- Names -----------------------------------------------------------------------------------------

func _name_regions() -> void:
	var r := rng("names")
	var words: Array = (names.get("region_words", ["Grey"]) as Array).duplicate()
	var kinds: Array = names.get("regions", ["Woods"])
	var used: Dictionary = {}
	for cell: String in regions:
		var nm: String = ""
		for tw: Dictionary in towns:
			if str(tw["cell"]) == cell:
				nm = str(tw["name"])
		if nm == "":
			for k: int in 20:
				var cand: String = "%s %s" % [words[r.randi() % words.size()], kinds[r.randi() % kinds.size()]]
				if not used.has(cand):
					nm = cand
					break
		used[nm] = true
		regions[cell]["name"] = nm
		regions[cell]["id"] = "%s_%s" % [cell.to_lower(), _slug(nm)]


# --- Output --------------------------------------------------------------------------------------

func world_name() -> String:
	var biggest: String = ""
	for tw: Dictionary in towns:
		biggest = str(tw["name"])
		break
	return ("%s County" % biggest) if biggest != "" else "The Unmapped Country"


func world_json() -> Dictionary:
	var rows: Array = []
	for j: int in terrain.n:
		var row: Array = []
		for i: int in terrain.n:
			row.append(snappedf(terrain.h[j * terrain.n + i], 0.1))
		rows.append(row)
	var bm_rows: Array = []
	for j2: int in biome_cols:
		var s: String = ""
		for i2: int in biome_cols:
			s += str(biome_cells[j2 * biome_cols + i2])
		bm_rows.append(s)
	var rivers: Array = []
	for rv: Dictionary in terrain.rivers:
		rivers.append({"id": rv["id"], "name": rv["name"], "points": Terrain._arr(rv["control"]), "width": _rounded(rv["widths"], 0.1),
			"depth": rv["depth"], "bank": rv["bank"], "level": _rounded(rv["levels"], 0.01), "valley_width": rv["valley_width"], "valley_slope": rv["valley_slope"]})
	var lakes: Array = []
	for l: Dictionary in terrain.lakes:
		lakes.append({"id": l["id"], "name": l["name"], "level": l["level"], "depth": l["depth"], "shore": l["shore"], "polygon": Terrain._arr(l["polygon"])})
	var road_out: Array = []
	for rd: Dictionary in roads:
		road_out.append({"id": rd["id"], "name": rd["name"], "class": rd["class"], "surface": rd["surface"], "width": rd["width"],
			"shoulder": rd["shoulder"], "points": Terrain._arr(rd["points"]), "bridges": rd["bridges"], "markings": rd["markings"]})
	var reg: Array = []
	for cell: String in regions:
		var rg: Dictionary = regions[cell]
		reg.append({"cell": cell, "id": rg["id"], "name": rg["name"], "biome": rg["biome"], "danger": rg["danger"], "status": "built",
			"summary": _region_summary(cell)})
	var town_out: Array = []
	for tw: Dictionary in towns:
		town_out.append({"id": tw["id"], "name": tw["name"], "kind": tw["kind"], "framework": tw["fw_id"], "region": regions[tw["cell"]]["id"],
			"center": Terrain._arr(PackedVector2Array([tw["center"]]))[0], "lots": (tw["plan"]["lots"] as Array).size(),
			"polygon": Terrain._arr(tw["poly"])})
	var place_out: Array = []
	for pl: Dictionary in places:
		place_out.append({"id": pl["id"], "kind": pl["kind"], "def": pl["def"], "site": pl["site"], "region": regions[pl["cell"]]["id"],
			"polygon": Terrain._arr(pl["poly"])})
	return {
		"_doc": "A random world (ADR-0031), generated by RwgGenerator v%d. Same schema as game/world/main_map/world.json (docs/REGIONS.md)." % VERSION,
		"id": world_id, "name": world_name(), "seed": settings.seed & 0x7fffffff, "region_size": 1024, "cols": size, "rows": size, "sea_level": 0.0,
		"road_grade": "world",
		"generator": {"version": VERSION, "settings": settings.to_dict(), "key": settings.key(), "towns": town_out, "places": place_out,
			"drop_site": Terrain._arr(PackedVector2Array([drop.get("pos", Vector2.ZERO)]))[0], "timings_ms": timings, "warnings": Array(warnings)},
		"macro": {"step": terrain.step, "corner_heights": rows, "noise": {"frequency": 0.001, "octaves": 1, "amplitude": 0.0, "ridged_amplitude": 0.0, "mountain_boost": 0.0}},
		"biome_map": {"ids": Array(BIOMES), "step": biome_step, "cols": biome_cols, "rows": biome_cols, "rows_data": bm_rows},
		"rivers": rivers, "lakes": lakes, "roads": road_out, "regions": reg,
	}


## Float32 values as an Array of float64s on a grid step (float32 noise stays out of the JSON).
static func _rounded(values: PackedFloat32Array, step_v: float) -> Array:
	var out: Array = []
	for v: float in values:
		out.append(snappedf(v, step_v))
	return out


func _region_summary(cell: String) -> String:
	var parts: PackedStringArray = []
	for tw: Dictionary in towns:
		if str(tw["cell"]) == cell:
			parts.append("the %s of %s" % [tw["kind"], tw["name"]])
	var n_places: int = 0
	for pl: Dictionary in places:
		if str(pl["cell"]) == cell:
			n_places += 1
	if n_places > 0:
		parts.append("%d place%s off the roads" % [n_places, "" if n_places == 1 else "s"])
	if str(drop.get("cell", "")) == cell:
		parts.append("the drop site")
	return ("%s, %s." % [str(regions[cell]["biome"]).replace("_", " ").capitalize(), ", ".join(parts)]) if not parts.is_empty() else "%s." % str(regions[cell]["biome"]).replace("_", " ").capitalize()


func region_json(cell: String) -> Dictionary:
	var rg: Dictionary = regions[cell]
	var rect: Rect2 = rg["rect"]
	var feats: Array = []
	var rough: float = settings.num("roughness")
	for tw: Dictionary in towns:
		if str(tw["cell"]) == cell:
			feats.append({"type": "framework", "id": tw["id"], "framework": tw["fw_id"], "origin": Terrain._arr(PackedVector2Array([tw["origin"]]))[0],
				"rotation": tw["rot"], "skirt": 14})
	for pl: Dictionary in places:
		if str(pl["cell"]) != cell:
			continue
		var f: Dictionary = {"type": pl["kind"], "id": pl["id"], "origin": Terrain._arr(PackedVector2Array([pl["origin"]]))[0], "rotation": pl["rot"],
			"biome": pl["biome"], "skirt": pl["skirt"]}
		f[pl["kind"]] = pl["def"]
		if bool(pl["keep_water"]):
			f["keep_water"] = true
			f["freeboard"] = 0.6
		feats.append(f)
	# Paths are painted per region: a trail crossing a border is listed in both, each painting its side.
	for pt: Dictionary in paths:
		var line_pts: PackedVector2Array = pt["points"]
		var bb := Rect2(line_pts[0], Vector2.ZERO)
		for p: Vector2 in line_pts:
			bb = bb.expand(p)
		if bb.grow(8.0).intersects(rect):
			feats.append({"type": "path", "id": pt["id"], "surface": pt["surface"], "width": pt["width"], "points": Terrain._arr(line_pts)})
	if str(drop.get("cell", "")) == cell:
		var dp: Array = Terrain._arr(PackedVector2Array([drop["pos"]]))[0]
		feats.append({"type": "clearing", "pos": dp, "radius": 16})
		feats.append({"type": "spawn", "id": "drop_site", "pos": dp, "yaw": drop["yaw"],
			"props": [{"prop": "supply_canister", "offset": [2.0, 0.0, 1.0], "rot": 30}]})
	for bl: Dictionary in blooms:
		if str(bl["cell"]) == cell:
			feats.append({"type": "bloom", "id": bl["id"], "at": Terrain._arr(PackedVector2Array([bl["at"]]))[0], "radius": bl["radius"],
				"strength": bl["strength"], "edge": bl["edge"]})
	return {
		"_doc": "Generated region (ADR-0031) of %s; regenerated from its world's seed and settings, never edited." % world_id,
		"id": rg["id"], "cell": cell, "name": rg["name"], "default_biome": rg["biome"],
		"detail_noise": {"layers": [{"frequency": 0.012, "octaves": 4, "amplitude": 2.5}, {"frequency": 0.03, "octaves": 3, "amplitude": snappedf(0.5 + 0.9 * rough, 0.01)},
			{"frequency": 0.075, "octaves": 2, "amplitude": 0.3}]},
		"features": feats,
	}


func frameworks_json() -> Dictionary:
	var defs: Array = []
	for tw: Dictionary in towns:
		var plan: Dictionary = tw["plan"]
		defs.append({"id": tw["fw_id"], "name": tw["name"], "size": plan["size"], "tier_range": tw["tier"],
			"lots": plan["lots"], "roads": plan["roads"], "fixtures": plan["fixtures"]})
	return {"_doc": "Generated towns of %s (ADR-0031): frameworks whose lots pick or generate their buildings (ADR-0030)." % world_id, "defs": defs}


## Region ids by cell (after run()).
func region_ids() -> Dictionary:
	var out: Dictionary = {}
	for cell: String in regions:
		out[cell] = regions[cell]["id"]
	return out
