extends Node
## The work of rwg_town_preview.gd: for each size class, land and seed, the closed-form synthetic
## land of test_town_planner.gd (rolling or hilly, sometimes a river in a valley, the site moved to
## low level ground), arterials routed over it by RwgStreets.route_fine (valley-seeking, bridged
## where they must cross the river), a planned town
## (RwgTownPlanner), and two PNGs: shaded relief with 2 m contours, water, blocks, parcels, lot
## frames by zoning (a tick on each front), streets by class, cul-de-sac bulbs, the plaza, fixtures,
## and the core / 0.6 r / radius rings.

const Planner := preload("res://src/worldgen/rwg/rwg_town_planner.gd")
const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")

const ZONE_COLORS: Dictionary = {
	"residential": Color(0.93, 0.8, 0.55), "commercial": Color(0.95, 0.5, 0.25), "civic": Color(0.62, 0.48, 0.85),
	"industrial": Color(0.55, 0.57, 0.62), "rural": Color(0.62, 0.78, 0.35),
}
const FIXTURE_COLORS: Dictionary = {
	"street_lamp": Color(1.0, 0.95, 0.4), "utility_pole": Color(0.45, 0.3, 0.15), "fire_hydrant": Color(0.95, 0.1, 0.1),
	"road_sign_stop": Color(1.0, 0.2, 0.3), "road_sign_speed": Color(1.0, 1.0, 1.0), "mailbox_rural": Color(0.2, 0.35, 0.95),
	"car_sedan_wreck": Color(0.5, 0.1, 0.1), "pickup_wreck": Color(0.5, 0.1, 0.1), "bench_park": Color(0.1, 0.6, 0.2),
}

var img: Image
var px: int = 1400
var view := Rect2()


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = _arg(a, "--out", "/home/user/7DaysToClaudie/build/agentT")
	var kinds: PackedStringArray = _arg(a, "--kind", "hamlet,village,town").split(",")
	var lands: PackedStringArray = _arg(a, "--land", "rolling,hilly").split(",")
	var seeds: PackedStringArray = _arg(a, "--seeds", "1,2,3").split(",")
	px = int(_arg(a, "--px", "1400"))
	# --draw all | core | none: none prints the counts only (fast, for tuning).
	var draw_mode: String = _arg(a, "--draw", "all")
	DirAccess.make_dir_recursive_absolute(out)
	var tuning: Dictionary = Planner.default_tuning()
	var errs: PackedStringArray = Planner.config_errors(tuning)
	if not errs.is_empty():
		printerr("[towns] config: %s" % ", ".join(errs))
	for kind: String in kinds:
		for land: String in lands:
			for sv: String in seeds:
				var seed: int = int(sv)
				var tc: int = Time.get_ticks_usec()
				var case: Dictionary = make_case(kind, land, seed, tuning)
				case["ms"] = (Time.get_ticks_usec() - tc) / 1000.0
				var t0: int = Time.get_ticks_usec()
				var p: Dictionary = Planner.plan(case["site"], case["world"], case["arterials"], tuning, seed)
				var ms: float = (Time.get_ticks_usec() - t0) / 1000.0
				var st: Dictionary = p["stats"]
				print("[towns] %-7s %-7s seed %-3d r %3d: %3d lots %s | side %d cross %d loops %d cul %d back %d | %d m streets, %d blocks, %d fixtures | %.0f ms (arterials %.0f ms)" % [kind, land, seed,
					int(case["site"]["radius"]), int(st["lots"]), JSON.stringify(st["zones"]), int(st["side_streets"]), int(st.get("cross_streets", 0)), int(st["loops"]), int(st["culdesacs"]),
					int(st["back_lanes"]), int(st["street_length"]), (p["blocks"] as Array).size(), (p["fixtures"] as Array).size(), ms, float(case["ms"])])
				print("         parts %s" % JSON.stringify(st["ms_parts"]))
				print("         extent along / across the main street %s, why %s" % [JSON.stringify(st.get("extent", [])), JSON.stringify(st.get("why", {}))])
				if draw_mode == "none":
					continue
				var base: String = out.path_join("%s_%s_%d" % [kind, land, seed])
				var c := Vector2(float(p["center"][0]), float(p["center"][1]))
				var r: float = float(p["radius"])
				if draw_mode == "all":
					draw(p, case, Rect2(c - Vector2.ONE * (r + 300.0), Vector2.ONE * (r + 300.0) * 2.0)).save_png(base + ".png")
				draw(p, case, Rect2(c - Vector2.ONE * (r + 30.0), Vector2.ONE * (r + 30.0) * 2.0)).save_png(base + "_core.png")
	get_tree().quit(0)


static func _arg(a: PackedStringArray, key: String, def: String) -> String:
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else def


# --- Synthetic land and arterials (the same closed forms as test_town_planner.gd) ---------------

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
				if q.length() > 70.0 or q == Vector2.ZERO:
					pts.append(q)
			for q2: Vector2 in p2:
				if q2.length() > 70.0:
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


# --- Drawing -----------------------------------------------------------------------------------

func draw(p: Dictionary, case: Dictionary, area: Rect2) -> Image:
	view = area
	img = Image.create(px, px, false, Image.FORMAT_RGB8)
	var height: Callable = case["world"]["height"]
	var water: Callable = case["world"]["water"]
	# Shaded relief with 2 m contours, water over it.
	var hs := PackedFloat32Array()
	hs.resize(px * px)
	var mpp: float = view.size.x / px
	for j: int in px:
		for i: int in px:
			hs[j * px + i] = float(height.call(view.position.x + (i + 0.5) * mpp, view.position.y + (j + 0.5) * mpp))
	var lo: float = INF
	var hi: float = -INF
	for v: float in hs:
		lo = minf(lo, v)
		hi = maxf(hi, v)
	var light := Vector3(-0.6, 0.75, -0.5).normalized()
	for j2: int in px:
		for i2: int in px:
			var k: int = j2 * px + i2
			var hx: float = hs[mini(k + 1, j2 * px + px - 1)] - hs[maxi(k - 1, j2 * px)]
			var hz: float = hs[mini(k + px, px * px - 1)] - hs[maxi(k - px, 0)]
			var n := Vector3(-hx / (2.0 * mpp), 1.0, -hz / (2.0 * mpp)).normalized()
			var shade: float = clampf(n.dot(light), 0.0, 1.0)
			var e: float = (hs[k] - lo) / maxf(1.0, hi - lo)
			var col := Color(0.42, 0.52, 0.33).lerp(Color(0.66, 0.62, 0.48), e) * (0.55 + 0.6 * shade)
			var x: float = view.position.x + (i2 + 0.5) * mpp
			var z: float = view.position.y + (j2 + 0.5) * mpp
			if float(water.call(x, z)) < 0.0:
				col = Color(0.22, 0.4, 0.58)
			elif floori(hs[k] / 2.0) != floori(hs[mini(k + 1, px * px - 1)] / 2.0) or floori(hs[k] / 2.0) != floori(hs[mini(k + px, px * px - 1)] / 2.0):
				col = col.darkened(0.25 if floori(hs[k] / 2.0) % 5 == 0 else 0.12)
			col.a = 1.0
			img.set_pixel(i2, j2, col)
	# Rings: core, 0.6 r, radius.
	var c := Vector2(float(p["center"][0]), float(p["center"][1]))
	var radius: float = float(p["radius"])
	var core: float = 50.0 if str(p["kind"]) == "hamlet" else (80.0 if str(p["kind"]) == "village" else 130.0)
	for rr: float in [core, radius * 0.6, radius]:
		var steps: int = int(rr * TAU / 6.0)
		for s: int in steps:
			if s % 2 == 0:
				var ang: float = float(s) / steps * TAU
				_line(c + Vector2(cos(ang), sin(ang)) * rr, c + Vector2(cos(ang + TAU / steps), sin(ang + TAU / steps)) * rr, Color(1, 1, 1, 0.5), 1.0)
	# Blocks (faint), parcels, lots.
	for b: Variant in p["blocks"]:
		_fill(_pts(b["poly"]), Color(0.3, 0.75, 0.3, 0.12))
	for l: Variant in p["lots"]:
		var col2: Color = ZONE_COLORS.get(str(l["zoning"][0]), Color.WHITE)
		_outline(_pts(l["poly"]), Color(col2.r, col2.g, col2.b, 0.55), 1.0)
		var f: Array = l["frame"]
		var corners: PackedVector2Array = frame_corners(f)
		_fill(corners, Color(col2.r, col2.g, col2.b, 0.85))
		_outline(corners, Color(0.1, 0.08, 0.05, 0.9), 1.0)
		# A tick from the centre to the front, so a lot's facing shows.
		var yaw: float = deg_to_rad(float(f[4]))
		var fc := Vector2(float(f[0]), float(f[1]))
		_line(fc, fc + Vector2(sin(yaw), cos(yaw)) * float(f[3]) * 0.5, Color(0.1, 0.08, 0.05, 0.9), 1.0)
	if not (p["plaza"] as Dictionary).is_empty():
		var pc: PackedVector2Array = frame_corners(p["plaza"]["frame"])
		_fill(pc, Color(0.78, 0.76, 0.72, 0.95))
		_outline(pc, Color(0.2, 0.2, 0.2), 1.5)
	# Streets: arterials (from the case), then the town's own.
	for a: Variant in case["arterials"]:
		var line: Polyline2 = Polyline2.from_array(a["points"])
		_stroke(line, Color(0.1, 0.1, 0.1), float(a["width"]) + 2.0 * float(a["shoulder"]))
		_stroke(line, Color(0.25, 0.25, 0.27), float(a["width"]))
		_stroke(line, Color(0.95, 0.85, 0.3), 0.6)
	for rd: Variant in p["roads"]:
		var cls: String = str(rd["class"])
		var line2: Polyline2 = Polyline2.from_array(rd["points"])
		var col3: Color = Color(0.32, 0.32, 0.34) if str(rd["surface"]) == "asphalt" else Color(0.55, 0.47, 0.35)
		if cls == "bulb":
			_dot(Vector2(float(rd["points"][0][0]), float(rd["points"][0][1])), float(rd["width"]) * 0.5 / (view.size.x / px), col3)
			continue
		_stroke(line2, Color(0.12, 0.12, 0.12), float(rd["width"]) + 1.6)
		_stroke(line2, col3, float(rd["width"]))
	for fx: Variant in p["fixtures"]:
		var fp := Vector2(float(fx["pos"][0]), float(fx["pos"][1]))
		_dot(fp, maxf(1.2, 1.0 / (view.size.x / px)), FIXTURE_COLORS.get(str(fx["prop"]), Color(0.9, 0.9, 0.9)))
	for j3: Variant in p["junctions"]:
		var jp := Vector2(float(j3["pos"][0]), float(j3["pos"][1]))
		if str(j3["kind"]) == "cross":
			_dot(jp, 1.5, Color(0.0, 0.9, 1.0))
	return img


static func frame_corners(f: Array) -> PackedVector2Array:
	var c := Vector2(float(f[0]), float(f[1]))
	var yaw: float = deg_to_rad(float(f[4]))
	var az := Vector2(sin(yaw), cos(yaw))
	var ax := Vector2(az.y, -az.x)
	var hx: Vector2 = ax * float(f[2]) * 0.5
	var hz: Vector2 = az * float(f[3]) * 0.5
	return PackedVector2Array([c - hx + hz, c + hx + hz, c + hx - hz, c - hx - hz])


static func _pts(arr: Variant) -> PackedVector2Array:
	var out := PackedVector2Array()
	for q: Variant in arr:
		out.append(Vector2(float(q[0]), float(q[1])))
	return out


func _to_px(p: Vector2) -> Vector2:
	return (p - view.position) / view.size.x * px


func _blend(i: int, j: int, col: Color) -> void:
	if i < 0 or j < 0 or i >= px or j >= px:
		return
	if col.a >= 0.999:
		img.set_pixel(i, j, col)
	else:
		var b: Color = img.get_pixel(i, j)
		img.set_pixel(i, j, Color(lerpf(b.r, col.r, col.a), lerpf(b.g, col.g, col.a), lerpf(b.b, col.b, col.a)))


func _dot(p: Vector2, r_px: float, col: Color) -> void:
	var c: Vector2 = _to_px(p)
	var r: int = int(ceil(r_px))
	for j: int in range(-r, r + 1):
		for i: int in range(-r, r + 1):
			if i * i + j * j <= r_px * r_px + 0.5:
				_blend(int(c.x) + i, int(c.y) + j, col)


func _line(a: Vector2, b: Vector2, col: Color, w_px: float) -> void:
	var pa: Vector2 = _to_px(a)
	var pb: Vector2 = _to_px(b)
	var n: int = maxi(1, int(ceil(pa.distance_to(pb) * 2.0)))
	var r: float = w_px * 0.5
	for k: int in n + 1:
		var q: Vector2 = pa.lerp(pb, float(k) / n)
		if r <= 0.75:
			_blend(int(q.x), int(q.y), col)
		else:
			for j: int in range(-int(ceil(r)), int(ceil(r)) + 1):
				for i: int in range(-int(ceil(r)), int(ceil(r)) + 1):
					if i * i + j * j <= r * r:
						_blend(int(q.x) + i, int(q.y) + j, col)


func _stroke(line: Polyline2, col: Color, width_m: float) -> void:
	var w_px: float = maxf(1.0, width_m / (view.size.x / px))
	for k: int in line.points.size() - 1:
		if not view.grow(20.0).has_point(line.points[k]) and not view.grow(20.0).has_point(line.points[k + 1]):
			continue
		_line(line.points[k], line.points[k + 1], col, w_px)


func _outline(poly: PackedVector2Array, col: Color, w_px: float) -> void:
	for k: int in poly.size():
		_line(poly[k], poly[(k + 1) % poly.size()], col, w_px)


func _fill(poly: PackedVector2Array, col: Color) -> void:
	if poly.size() < 3:
		return
	var pp := PackedVector2Array()
	var y0: float = INF
	var y1: float = -INF
	for q: Vector2 in poly:
		var v: Vector2 = _to_px(q)
		pp.append(v)
		y0 = minf(y0, v.y)
		y1 = maxf(y1, v.y)
	for j: int in range(maxi(0, int(floor(y0))), mini(px - 1, int(ceil(y1))) + 1):
		var y: float = j + 0.5
		var xs: Array[float] = []
		for k: int in pp.size():
			var a: Vector2 = pp[k]
			var b: Vector2 = pp[(k + 1) % pp.size()]
			if (a.y <= y and b.y > y) or (b.y <= y and a.y > y):
				xs.append(a.x + (y - a.y) / (b.y - a.y) * (b.x - a.x))
		xs.sort()
		for m: int in range(0, xs.size() - 1, 2):
			for i: int in range(maxi(0, int(ceil(xs[m] - 0.5))), mini(px - 1, int(floor(xs[m + 1] - 0.5))) + 1):
				_blend(i, j, col)
