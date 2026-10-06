extends GutTest
## Organic towns (ADR-0040, RwgTownPlanner; docs/RWG_V2_PLAN.md §3 and §6 Phase 5). Every size class
## on rolling and hilly synthetic land (closed-form heights below, a river in a valley on some
## seeds; the site moved to the lowest, levellest ground nearby as §3.3 picks sites), with arterials
## routed over it by RwgStreets.route_fine, is checked for what the composer and the POI system rely
## on (no lot overlaps, lots clear of every street corridor, a street graph joined to the arterials,
## street grades, level frames, fronts that face their streets the way PoiManager.lot_xf turns a
## building, every lot fitting a real building through LotPicker) and for what makes it a town
## (counts within the class's ranges, shops nearest the centre, cul-de-sacs, streets that follow
## the land, irregular lot yaw), plus determinism and the time budget. Four seeds per class and
## land; SLOW_TESTS=1 runs twelve.

const Planner := preload("res://src/worldgen/rwg/rwg_town_planner.gd")
const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")
const LotPicker := preload("res://src/poi/lot_picker.gd")
const Generator := preload("res://src/poi/building_generator.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")
const PoiManagerScript := preload("res://src/poi/poi_manager.gd")

const KINDS: Array[String] = ["hamlet", "village", "town"]
const LANDS: Array[String] = ["rolling", "hilly"]
## Planning one town, headless on the shared 4-core container (ms).
const BUDGET_MS: float = 1000.0
## Steepest street grade the composer may build (its own profile smoothing applied).
const MAX_GRADE: float = 0.12
const RINGS: Array[String] = ["core", "inner", "outer", "edge"]

var tuning: Dictionary = {}
var cases: Array[Dictionary] = []


func before_all() -> void:
	tuning = Planner.default_tuning()
	var n: int = 12 if OS.get_environment("SLOW_TESTS") == "1" else 4
	for kind: String in KINDS:
		for land: String in LANDS:
			for seed: int in range(1, n + 1):
				var c: Dictionary = make_case(kind, land, seed, tuning)
				var t0: int = Time.get_ticks_usec()
				c["plan"] = Planner.plan(c["site"], c["world"], c["arterials"], tuning, seed)
				c["ms"] = (Time.get_ticks_usec() - t0) / 1000.0
				cases.append(c)


# --- Synthetic land -------------------------------------------------------------------------------

## A test case: {kind, land, seed, site, world: {height, water}, arterials}. The land is a sum of
## sines (rolling: 12 m, hilly: 30 m amplitude) with, on some seeds, a river in a valley; the
## town's centre is moved to the lowest, levellest dry spot within 400 m of the origin.
static func make_case(kind: String, land: String, seed: int, t: Dictionary) -> Dictionary:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.derive_seed(seed, "town_case:%s:%s" % [kind, land])
	var kd: Dictionary = t["kinds"][kind]
	var radius: float = r.randf_range(float(kd["radius"][0]), float(kd["radius"][1]))
	var ph: Array[float] = []
	for k: int in 8:
		ph.append(r.randf_range(0.0, TAU))
	var amp: float = 12.0 if land == "rolling" else 30.0
	var has_river: bool = r.randf() < (0.5 if land == "rolling" else 0.7)
	var rv_angle: float = r.randf_range(0.0, TAU)
	var rv_off: float = r.randf_range(radius * 0.7, radius * 1.1) * (1.0 if r.randf() < 0.5 else -1.0)
	var raw_h := func(x: float, z: float) -> float:
		var v: float = amp * (0.55 * sin(x / 260.0 + ph[0]) * cos(z / 310.0 + ph[1]) + 0.3 * sin((x * 0.8 + z * 0.6) / 150.0 + ph[2])
			+ 0.15 * sin(x / 75.0 + ph[3]) * sin(z / 90.0 + ph[4]))
		if has_river:
			var q := Vector2(x, z).rotated(-rv_angle)
			var dz: float = q.y - (rv_off + 50.0 * sin(q.x / 170.0 + ph[5]))
			v -= amp * 0.5 * exp(-dz * dz / (160.0 * 160.0))
		return v + 100.0
	var raw_w := func(x: float, z: float) -> float:
		if not has_river:
			return 1.0e6
		var q2 := Vector2(x, z).rotated(-rv_angle)
		var f: float = rv_off + 50.0 * sin(q2.x / 170.0 + ph[5])
		var fp: float = 50.0 / 170.0 * cos(q2.x / 170.0 + ph[5])
		return absf(q2.y - f) / sqrt(1.0 + fp * fp) - 9.0
	# The site (§3.3): dry, low against its surroundings, level in its core.
	var core: float = float(kd["core"])
	var best := Vector2.ZERO
	var best_score: float = INF
	for j: int in range(-4, 5):
		for i: int in range(-4, 5):
			var p := Vector2(i, j) * 100.0
			if float(raw_w.call(p.x, p.y)) < 90.0:
				continue
			var acc: float = 0.0
			for k2: int in 25:
				acc += float(raw_h.call(p.x + (k2 % 5 - 2) * 250.0, p.y + (k2 / 5 - 2) * 250.0))
			var lo: float = INF
			var hi: float = -INF
			for k3: int in 25:
				var v2: float = float(raw_h.call(p.x + (k3 % 5 - 2) * core * 0.5, p.y + (k3 / 5 - 2) * core * 0.5))
				lo = minf(lo, v2)
				hi = maxf(hi, v2)
			var score: float = (float(raw_h.call(p.x, p.y)) - acc / 25.0) + 0.5 * (hi - lo) + p.length() * 0.004
			if score < best_score:
				best_score = score
				best = p
	var height := func(x: float, z: float) -> float:
		return float(raw_h.call(x + best.x, z + best.y))
	var water := func(x: float, z: float) -> float:
		return float(raw_w.call(x + best.x, z + best.y))
	var world: Dictionary = {"height": height, "water": water}
	var site: Dictionary = {"id": "%s_%s_%d" % [kind, land, seed], "kind": kind, "center": [0.0, 0.0], "radius": radius, "name": "Test %s" % kind}
	var arterials: Array = make_arterials(kind, radius, float((t["lots"] as Dictionary).get("outskirts", 400.0)), world, r)
	return {"kind": kind, "land": land, "seed": seed, "site": site, "world": world, "arterials": arterials}


## Arterials as the generator brings them: routed over the land from the edge of the outskirts
## through the centre and out the far side (route_fine: gentle grades, valleys, a bridge where it
## must cross the river); villages may have a second crossing it, towns have one and may have a
## county road teeing into the main street.
static func make_arterials(kind: String, radius: float, outskirts: float, world: Dictionary, r: RandomNumberGenerator) -> Array:
	var reach: float = radius + outskirts + 60.0
	var g := Streets.Ground.new(world, Vector2.ZERO, reach + 200.0)
	var count: int = 1
	match kind:
		"village":
			count = 1 if r.randf() < 0.5 else 2
		"town":
			count = 2 if r.randf() < 0.5 else 3
	var out: Array = []
	var th: float = r.randf_range(0.0, TAU)
	var opts: Dictionary = {"bridge": 400.0, "margin": 200.0}
	for k: int in count:
		var a0: float = th + (0.0 if k == 0 else (PI * 0.5 + r.randf_range(-0.3, 0.3) if k == 1 else r.randf_range(PI * 0.3, PI * 0.7) + (PI if r.randf() < 0.5 else 0.0)))
		var a: Vector2 = Vector2(cos(a0), sin(a0)) * reach
		var pts := PackedVector2Array()
		if k < 2:
			var a1: float = a0 + PI + r.randf_range(-0.3, 0.3)
			var b: Vector2 = Vector2(cos(a1), sin(a1)) * reach
			var p1: PackedVector2Array = Streets.route_fine(g, a, Vector2.ZERO, opts)
			var p2: PackedVector2Array = Streets.route_fine(g, Vector2.ZERO, b, opts)
			if p1.is_empty() or p2.is_empty():
				continue
			# Through the centre (the generator routes arterials to town centres): each half is
			# relaxed on its own, and points crowding the joint go so the line bends smoothly there.
			for q: Vector2 in p1:
				if q.length() > 40.0 or q == Vector2.ZERO:
					pts.append(q)
			for q2: Vector2 in p2:
				if q2.length() > 40.0:
					pts.append(q2)
		else:
			var main: Polyline2 = Polyline2.from_array(out[0]["points"])
			var tee: Vector2 = main.point_at(main.closest(Vector2.ZERO).y + r.randf_range(120.0, 200.0) * (1.0 if r.randf() < 0.5 else -1.0))
			pts = Streets.route_fine(g, a, tee, opts)
			if pts.is_empty():
				continue
		var arr: Array = []
		for p: Vector2 in pts:
			arr.append([snappedf(p.x, 0.1), snappedf(p.y, 0.1)])
		var county: bool = k == 2 or kind == "hamlet"
		out.append({"id": "road_%d" % k, "points": arr, "width": 5.0 if county else 8.0, "shoulder": 1.5 if county else 2.5,
			"surface": "gravel" if county else "asphalt", "markings": not county, "class": "county" if county else "highway"})
	return out


# --- Helpers ------------------------------------------------------------------------------------

static func _label(c: Dictionary) -> String:
	return "%s %s seed %d" % [c["kind"], c["land"], int(c["seed"])]


static func _frame_poly(f: Array) -> PackedVector2Array:
	var ctr := Vector2(float(f[0]), float(f[1]))
	var yaw: float = deg_to_rad(float(f[4]))
	var az := Vector2(sin(yaw), cos(yaw))
	var ax := Vector2(az.y, -az.x)
	var hx: Vector2 = ax * float(f[2]) * 0.5
	var hz: Vector2 = az * float(f[3]) * 0.5
	return PackedVector2Array([ctr - hx + hz, ctr + hx + hz, ctr + hx - hz, ctr - hx - hz])


static func _area(poly: PackedVector2Array) -> float:
	var a: float = 0.0
	for i: int in poly.size():
		a += poly[i].cross(poly[(i + 1) % poly.size()])
	return absf(a) * 0.5


static func _seg_poly_distance(a: Vector2, b: Vector2, poly: PackedVector2Array) -> float:
	if Geometry2D.is_point_in_polygon(a, poly) or Geometry2D.is_point_in_polygon(b, poly):
		return 0.0
	var best: float = INF
	for k: int in poly.size():
		var c: Vector2 = poly[k]
		var d: Vector2 = poly[(k + 1) % poly.size()]
		if Geometry2D.segment_intersects_segment(a, b, c, d) != null:
			return 0.0
		var pts: PackedVector2Array = Geometry2D.get_closest_points_between_segments(a, b, c, d)
		best = minf(best, pts[0].distance_to(pts[1]))
	return best


static func _line_poly_distance(line: Polyline2, poly: PackedVector2Array) -> float:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	var best: float = INF
	for k: int in line.points.size() - 1:
		var sb := Rect2(line.points[k], Vector2.ZERO).expand(line.points[k + 1])
		if not sb.grow(30.0).intersects(bb):
			continue
		best = minf(best, _seg_poly_distance(line.points[k], line.points[k + 1], poly))
	return best


## Every street a case has: [{id, class, line, need (half width + shoulder)}], arterials first.
static func _lines(c: Dictionary) -> Array:
	var out: Array = []
	for a: Dictionary in c["arterials"]:
		out.append({"id": a["id"], "class": "arterial", "line": Polyline2.from_array(a["points"]), "need": float(a["width"]) * 0.5 + float(a["shoulder"])})
	for rd: Dictionary in c["plan"]["roads"]:
		out.append({"id": rd["id"], "class": rd["class"], "line": Polyline2.from_array(rd["points"]), "need": float(rd["width"]) * 0.5 + float(rd["shoulder"])})
	return out


static func _report(bad: PackedStringArray) -> String:
	return "%d problems: %s" % [bad.size(), "; ".join(bad.slice(0, 8))]


# --- What the composer and the POI system rely on -------------------------------------------------

func test_config_is_valid() -> void:
	assert_false(tuning.is_empty(), "data/config/town_planner.json loads")
	assert_eq(Planner.config_errors(tuning), PackedStringArray(), "the tuning has every class, range and lot size")


func test_no_lot_overlaps() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var polys: Array[PackedVector2Array] = []
		for l: Dictionary in c["plan"]["lots"]:
			polys.append(_frame_poly(l["frame"]))
		if not (c["plan"]["plaza"] as Dictionary).is_empty():
			polys.append(_frame_poly(c["plan"]["plaza"]["frame"]))
		for i: int in polys.size():
			for j: int in range(i + 1, polys.size()):
				if polys[i][0].distance_to(polys[j][0]) > 160.0:
					continue
				var over: float = 0.0
				for part: PackedVector2Array in Geometry2D.intersect_polygons(polys[i], polys[j]):
					over += _area(part)
				if over >= 0.5:
					bad.append("%s: frames %d and %d overlap by %.1f m2" % [_label(c), i, j, over])
	assert_eq(bad.size(), 0, _report(bad))


func test_lots_clear_of_street_corridors() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var lines: Array = _lines(c)
		var frames: Array = []
		for l: Dictionary in c["plan"]["lots"]:
			frames.append([l["id"], l["frame"]])
		if not (c["plan"]["plaza"] as Dictionary).is_empty():
			frames.append(["plaza", c["plan"]["plaza"]["frame"]])
		for fr: Array in frames:
			var poly: PackedVector2Array = _frame_poly(fr[1])
			for ln: Dictionary in lines:
				var d: float = _line_poly_distance(ln["line"], poly)
				if d < float(ln["need"]) - 0.05:
					bad.append("%s: %s is %.2f m from %s (corridor %.2f)" % [_label(c), fr[0], d, ln["id"], float(ln["need"])])
	assert_eq(bad.size(), 0, _report(bad))


func test_street_graph_joins_the_arterials() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var lines: Array = _lines(c)
		var n_art: int = (c["arterials"] as Array).size()
		var parent: Array[int] = []
		for i: int in lines.size():
			parent.append(i)
		var find := func(i: int) -> int:
			while parent[i] != i:
				i = parent[i]
			return i
		# A street is joined where one of its ends lies on another street's centre line.
		for i2: int in range(n_art, lines.size()):
			var line: Polyline2 = lines[i2]["line"]
			for e: Vector2 in [line.points[0], line.points[line.points.size() - 1]]:
				for j: int in lines.size():
					if j != i2 and (lines[j]["line"] as Polyline2).closest(e).x < 1.0:
						parent[find.call(i2)] = find.call(j)
		for i3: int in range(n_art, lines.size()):
			var joined: bool = false
			for a: int in n_art:
				if find.call(i3) == find.call(a):
					joined = true
			if not joined:
				bad.append("%s: %s is not joined to an arterial" % [_label(c), lines[i3]["id"]])
	assert_eq(bad.size(), 0, _report(bad))


func test_street_grades_within_the_limit() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var height: Callable = c["world"]["height"]
		for rd: Dictionary in c["plan"]["roads"]:
			if str(rd["class"]) == "bulb":
				continue
			# The composer's profile: ground every 4 m, three passes of a 9-tap moving average.
			var line: Polyline2 = Polyline2.from_array(rd["points"])
			var count: int = int(ceil(line.total_length / 4.0)) + 1
			var prof := PackedFloat32Array()
			for k: int in count:
				var p: Vector2 = line.point_at(k * 4.0)
				prof.append(float(height.call(p.x, p.y)))
			for pass_i: int in 3:
				var cp: PackedFloat32Array = prof.duplicate()
				for k2: int in count:
					var acc: float = 0.0
					for o: int in range(-4, 5):
						acc += cp[clampi(k2 + o, 0, count - 1)]
					prof[k2] = acc / 9.0
			# The composer reads the profile at s / 4 m (its last sample stands for the street's end).
			var worst: float = 0.0
			for k3: int in count - 1:
				worst = maxf(worst, absf(prof[k3 + 1] - prof[k3]) / 4.0)
			if worst > MAX_GRADE:
				bad.append("%s: %s (%s) climbs %.3f" % [_label(c), rd["id"], rd["class"], worst])
	assert_eq(bad.size(), 0, _report(bad))


func test_frame_relief_within_limits() -> void:
	var bad: PackedStringArray = []
	var limits: Dictionary = tuning["lots"]["relief"]
	for c: Dictionary in cases:
		var height: Callable = c["world"]["height"]
		for l: Dictionary in c["plan"]["lots"]:
			var f: Array = l["frame"]
			var poly: PackedVector2Array = _frame_poly(f)
			var lo: float = INF
			var hi: float = -INF
			for k: int in 25:
				# poly: front-left, front-right, back-right, back-left; bilinear over the frame.
				var u: float = (k % 5) / 4.0
				var v: float = (k / 5) / 4.0
				var p: Vector2 = poly[0].lerp(poly[1], u).lerp(poly[3].lerp(poly[2], u), v)
				var hv: float = float(height.call(p.x, p.y))
				lo = minf(lo, hv)
				hi = maxf(hi, hv)
			var zone: String = str(l["zoning"][0])
			# Zones on their fallback ground get a metre more (the planner's quota fallback).
			var limit: float = float(limits.get(zone, 3.5)) + (1.0 if zone in ["commercial", "civic"] else 0.0) + 0.15
			if hi - lo > limit:
				bad.append("%s: %s (%s) stands on %.2f m of relief" % [_label(c), l["id"], zone, hi - lo])
			if absf(float(l["y"]) - (lo + hi) * 0.5) > (hi - lo) * 0.5 + 0.2:
				bad.append("%s: %s pad height %.2f is off its ground %.2f-%.2f" % [_label(c), l["id"], float(l["y"]), lo, hi])
	assert_eq(bad.size(), 0, _report(bad))


func test_lot_fronts_face_their_streets_as_lot_xf_turns_buildings() -> void:
	# The convention (plan A10): PoiManager.lot_xf turns a building facing S, E, N, W by these yaws.
	for facing: String in ["S", "E", "N", "W"]:
		var yaw: float = {"S": 0.0, "E": 90.0, "N": 180.0, "W": -90.0}[facing]
		var xf: Transform3D = PoiManagerScript.lot_xf({"rect": [0, 0, 20, 30], "facing": facing}, Vector2i(10, 10))
		assert_true(xf.basis.is_equal_approx(Basis(Vector3.UP, deg_to_rad(yaw))), "lot_xf facing %s is yaw %d" % [facing, int(yaw)])
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var by_id: Dictionary = {}
		for ln: Dictionary in _lines(c):
			by_id[ln["id"]] = ln["line"]
		var plaza: Dictionary = c["plan"]["plaza"]
		for l: Dictionary in c["plan"]["lots"]:
			var f: Array = l["frame"]
			var ctr := Vector2(float(f[0]), float(f[1]))
			var front3: Vector3 = Basis(Vector3.UP, deg_to_rad(float(f[4]))) * Vector3(0.0, 0.0, 1.0)
			var front := Vector2(front3.x, front3.z)
			var target: Vector2
			if str(l["street"]) == "plaza":
				target = Vector2(float(plaza["frame"][0]), float(plaza["frame"][1]))
			else:
				var line: Polyline2 = by_id[str(l["street"])]
				target = line.point_at(line.closest(ctr).y)
			if (target - ctr).normalized().dot(front) < 0.7:
				bad.append("%s: %s faces %.0f degrees off its street %s" % [_label(c), l["id"], rad_to_deg(acos(clampf((target - ctr).normalized().dot(front), -1.0, 1.0))), l["street"]])
	assert_eq(bad.size(), 0, _report(bad))


func test_every_lot_holds_a_building() -> void:
	var db: Node = ContentDB.instance
	var pois: Array = db.call(&"all", &"poi")
	var templates: Array = db.call(&"all", &"building_template")
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var fw_lots: Array = []
		for l: Dictionary in c["plan"]["lots"]:
			var f: Array = l["frame"]
			var size := Vector2i(int(f[2]), int(f[3]))
			var zon := PackedStringArray(l["zoning"])
			var fits: bool = false
			for pd: PoiDef in pois:
				if pd.tier <= 2 and LotPicker._zoned(pd.zoning, zon) and pd.footprint.x <= size.x and pd.footprint.y <= size.y:
					fits = true
					break
			if not fits:
				for td: TemplateDef in templates:
					if LotPicker._zoned(td.zoning, zon) and Generator.fits(td, size):
						fits = true
						break
			if not fits:
				bad.append("%s: %s (%s, %d x %d) fits no building" % [_label(c), l["id"], ",".join(zon), size.x, size.y])
			fw_lots.append({"id": l["id"], "rect": [0, 0, size.x, size.y], "zoning": l["zoning"], "facing": "S"})
		# What LotPicker really makes of them (one authored building per framework, tier 1-2).
		var fw := FrameworkDef.new()
		var errs: PackedStringArray = fw.parse({"id": "test_town", "size": [1000, 1000], "tier_range": [1, 2], "lots": fw_lots}, &"framework", "test")
		assert_eq(errs, PackedStringArray())
		for res: Dictionary in LotPicker.resolve(fw, str(c["site"]["id"]), 4471):
			if str(res["kind"]) == "empty":
				bad.append("%s: LotPicker leaves %s (%s) empty" % [_label(c), (res["lot"] as Dictionary)["id"], ",".join(PackedStringArray((res["lot"] as Dictionary)["zoning"]))])
	assert_eq(bad.size(), 0, _report(bad))


func test_parcels_hold_their_frames_and_keep_off_the_streets() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var lines: Array = _lines(c)
		for l: Dictionary in c["plan"]["lots"]:
			var parcel := PackedVector2Array()
			for q: Variant in l["poly"]:
				parcel.append(Vector2(float(q[0]), float(q[1])))
			var frame: PackedVector2Array = _frame_poly(l["frame"])
			var inside: float = 0.0
			for part: PackedVector2Array in Geometry2D.intersect_polygons(parcel, frame):
				inside += _area(part)
			# Frames and parcels are each rounded to 0.1 m: a parcel edge on its frame's may miss a sliver.
			var slack: float = 0.12 * 2.0 * (float(l["frame"][2]) + float(l["frame"][3]))
			if parcel.size() < 3 or inside < _area(frame) - slack:
				bad.append("%s: %s's parcel leaves out %.1f m2 of its frame" % [_label(c), l["id"], _area(frame) - inside])
			for ln: Dictionary in lines:
				var d: float = _line_poly_distance(ln["line"], parcel)
				if d < float(ln["need"]) - 0.25:
					bad.append("%s: %s's parcel reaches %.2f m into %s" % [_label(c), l["id"], float(ln["need"]) - d, ln["id"]])
	assert_eq(bad.size(), 0, _report(bad))


func test_fixtures_are_real_props_off_the_lots() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var ids: Dictionary = {}
		var frames: Array[PackedVector2Array] = []
		for l: Dictionary in c["plan"]["lots"]:
			frames.append(_frame_poly(l["frame"]))
		for fx: Dictionary in c["plan"]["fixtures"]:
			if not Content.has_def(&"prop", StringName(str(fx["prop"]))):
				bad.append("%s: unknown prop %s" % [_label(c), fx["prop"]])
			if ids.has(fx["id"]):
				bad.append("%s: fixture id %s twice" % [_label(c), fx["id"]])
			ids[fx["id"]] = true
			var p := Vector2(float(fx["pos"][0]), float(fx["pos"][1]))
			for fr: PackedVector2Array in frames:
				if Geometry2D.is_point_in_polygon(p, fr):
					bad.append("%s: %s %s stands in a lot" % [_label(c), fx["id"], fx["prop"]])
					break
	assert_eq(bad.size(), 0, _report(bad))


func test_framework_shape() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var fw: Dictionary = Planner.to_framework(c["plan"], "rwg_x_%s" % c["site"]["id"], "Test")
		for k: Variant in fw:
			if not Planner.FRAMEWORK_KEYS.has(str(k)):
				bad.append("%s: framework key %s" % [_label(c), k])
		assert_eq(str(fw["layout"]), "organic")
		var ids: Dictionary = {}
		for l: Dictionary in fw["lots"]:
			if ids.has(l["id"]):
				bad.append("%s: lot id %s twice" % [_label(c), l["id"]])
			ids[l["id"]] = true
			if (l["frame"] as Array).size() != 5 or (l["poly"] as Array).size() < 3 or (l["zoning"] as Array).is_empty() or not RINGS.has(str(l["ring"])) \
					or str(l["street"]) == "" or not (l["y"] is float):
				bad.append("%s: lot %s is malformed: %s" % [_label(c), l["id"], JSON.stringify(l).left(200)])
		for rd: Dictionary in fw["roads"]:
			if (rd["points"] as Array).size() < 2 or float(rd["width"]) <= 0.0 or not str(rd["surface"]) in ["asphalt", "gravel", "dirt"]:
				bad.append("%s: road %s is malformed" % [_label(c), rd["id"]])
	assert_eq(bad.size(), 0, _report(bad))


# --- What makes it a town ------------------------------------------------------------------------

func test_counts_within_class_ranges() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		var kd: Dictionary = tuning["kinds"][c["kind"]]
		var st: Dictionary = c["plan"]["stats"]
		var zones: Dictionary = st["zones"]
		var lots: int = (c["plan"]["lots"] as Array).size()
		if lots < int(kd["lots"][0]) or lots > int(kd["lots"][1]):
			bad.append("%s: %d lots (%s)" % [_label(c), lots, str(kd["lots"])])
		for z: String in ["commercial", "civic", "industrial", "rural"]:
			var n: int = int(zones.get(z, 0))
			var lo: int = int(kd[z][0]) if z in ["commercial", "civic"] else 0
			if n < lo or n > int(kd[z][1]):
				bad.append("%s: %d %s lots (%s)" % [_label(c), n, z, str(kd[z])])
		for key: String in ["side_streets", "loops", "culdesacs"]:
			if int(st[key]) > int(kd[key][1]):
				bad.append("%s: %d %s (%s)" % [_label(c), int(st[key]), key, str(kd[key])])
		if str(c["kind"]) == "town":
			if int(st["side_streets"]) < int(kd["side_streets"][0]):
				bad.append("%s: only %d side streets" % [_label(c), int(st["side_streets"])])
			if (c["plan"]["plaza"] as Dictionary).is_empty():
				bad.append("%s: no plaza" % _label(c))
	assert_eq(bad.size(), 0, _report(bad))


func test_shops_nearest_the_centre_then_civic_then_houses() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		if str(c["kind"]) == "hamlet":
			continue
		var sums: Dictionary = {}
		var counts: Dictionary = {}
		for l: Dictionary in c["plan"]["lots"]:
			var z: String = str(l["zoning"][0])
			var d: float = Vector2(float(l["frame"][0]), float(l["frame"][1])).length()
			sums[z] = float(sums.get(z, 0.0)) + d
			counts[z] = int(counts.get(z, 0)) + 1
		if not counts.has("commercial") or not counts.has("civic") or not counts.has("residential"):
			bad.append("%s: zones missing %s" % [_label(c), str(counts)])
			continue
		var com: float = float(sums["commercial"]) / int(counts["commercial"])
		var civ: float = float(sums["civic"]) / int(counts["civic"])
		var res: float = float(sums["residential"]) / int(counts["residential"])
		if not (com < civ and civ <= res):
			bad.append("%s: mean distances commercial %.0f, civic %.0f, residential %.0f" % [_label(c), com, civ, res])
	assert_eq(bad.size(), 0, _report(bad))


func test_towns_have_culdesacs() -> void:
	for c: Dictionary in cases:
		if str(c["kind"]) != "town":
			continue
		var bulbs: int = 0
		for rd: Dictionary in c["plan"]["roads"]:
			if str(rd["class"]) == "bulb":
				bulbs += 1
				assert_eq(float(rd["width"]), 18.0, "a turning circle is 18 m across")
		assert_true(bulbs >= int(tuning["kinds"]["town"]["culdesacs"][0]), "%s: %d cul-de-sacs" % [_label(c), bulbs])


func test_streets_follow_the_land() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		if str(c["land"]) != "hilly" or str(c["kind"]) == "hamlet":
			continue
		var height: Callable = c["world"]["height"]
		var radius: float = float(c["site"]["radius"])
		# The disc's mean slope.
		var slope_sum: float = 0.0
		var n: int = 0
		for j: int in range(-20, 21):
			for i: int in range(-20, 21):
				var p := Vector2(i, j) * radius / 20.0
				if p.length() > radius:
					continue
				var dx: float = float(height.call(p.x + 2.0, p.y)) - float(height.call(p.x - 2.0, p.y))
				var dz: float = float(height.call(p.x, p.y + 2.0)) - float(height.call(p.x, p.y - 2.0))
				slope_sum += Vector2(dx, dz).length() / 4.0
				n += 1
		var disc_slope: float = slope_sum / n
		# The side streets' mean grade, by length.
		var g_sum: float = 0.0
		var len_sum: float = 0.0
		for rd: Dictionary in c["plan"]["roads"]:
			if not str(rd["class"]) in ["street", "lane"]:
				continue
			var line: Polyline2 = Polyline2.from_array(rd["points"])
			var s: float = 0.0
			while s + 8.0 <= line.total_length:
				var a: Vector2 = line.point_at(s)
				var b: Vector2 = line.point_at(s + 8.0)
				g_sum += absf(float(height.call(b.x, b.y)) - float(height.call(a.x, a.y)))
				len_sum += 8.0
				s += 8.0
		if len_sum > 0.0 and g_sum / len_sum > 0.6 * disc_slope:
			bad.append("%s: side streets climb %.3f on average on land of slope %.3f" % [_label(c), g_sum / len_sum, disc_slope])
		# The arterials run below their surroundings (valleys) through the town.
		var rel_sum: float = 0.0
		var rel_n: int = 0
		for a2: Dictionary in c["arterials"]:
			var line2: Polyline2 = Polyline2.from_array(a2["points"])
			var s2: float = 0.0
			while s2 <= line2.total_length:
				var p2: Vector2 = line2.point_at(s2)
				s2 += 16.0
				if p2.length() > radius:
					continue
				var acc: float = 0.0
				for k: int in 49:
					acc += float(height.call(p2.x + (k % 7 - 3) * 50.0, p2.y + (k / 7 - 3) * 50.0))
				rel_sum += float(height.call(p2.x, p2.y)) - acc / 49.0
				rel_n += 1
		if rel_n > 0 and rel_sum / rel_n >= 0.0:
			bad.append("%s: arterials run %.2f m above their surroundings" % [_label(c), rel_sum / rel_n])
	assert_eq(bad.size(), 0, _report(bad))


func test_lot_yaw_is_irregular() -> void:
	var bad: PackedStringArray = []
	for c: Dictionary in cases:
		if str(c["kind"]) == "hamlet":
			continue
		# Spread of the yaws about a common right-angled grid (period 90 degrees): 0 for any grid.
		var sx: float = 0.0
		var sy: float = 0.0
		var lots: Array = c["plan"]["lots"]
		for l: Dictionary in lots:
			var a: float = deg_to_rad(float(l["frame"][4])) * 4.0
			sx += cos(a)
			sy += sin(a)
		var r_len: float = Vector2(sx, sy).length() / maxi(1, lots.size())
		var spread: float = rad_to_deg(sqrt(-2.0 * log(maxf(r_len, 1.0e-9)))) / 4.0
		if spread <= 10.0:
			bad.append("%s: yaw spread %.1f degrees" % [_label(c), spread])
	assert_eq(bad.size(), 0, _report(bad))


func test_same_inputs_same_town_other_seed_other_town() -> void:
	for kind: String in KINDS:
		var c: Dictionary = {}
		for cc: Dictionary in cases:
			if str(cc["kind"]) == kind:
				c = cc
				break
		var seed: int = int(c["seed"])
		var a: Dictionary = Planner.plan(c["site"], c["world"], c["arterials"], tuning, seed)
		var b: Dictionary = Planner.plan(c["site"], c["world"], c["arterials"], tuning, seed + 1000)
		for p: Dictionary in [a, b, c["plan"]]:
			(p["stats"] as Dictionary).erase("ms")
			(p["stats"] as Dictionary).erase("ms_parts")
		var ha: String = JSON.stringify(a, "", false).md5_text()
		assert_eq(ha, JSON.stringify(c["plan"], "", false).md5_text(), "%s: the same inputs plan the same town, byte for byte" % kind)
		assert_ne(ha, JSON.stringify(b, "", false).md5_text(), "%s: another seed plans another town" % kind)


func test_planning_time() -> void:
	var worst: float = 0.0
	var worst_case: String = ""
	var total: float = 0.0
	for c: Dictionary in cases:
		var ms: float = float(c["ms"])
		total += ms
		if ms > worst:
			worst = ms
			worst_case = _label(c)
	gut.p("town plans: mean %.0f ms, worst %.0f ms (%s)" % [total / maxi(1, cases.size()), worst, worst_case])
	assert_lt(worst, BUDGET_MS, "every town plans in under a second (%s took %.0f ms)" % [worst_case, worst])
