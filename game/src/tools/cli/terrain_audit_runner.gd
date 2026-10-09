extends Node
## The work of terrain_audit.gd (see there for the arguments). Composes each region without the
## cache and walks every road through it in 2 m stations:
## * cross: |h(left edge) - h(right edge)| / width over the paved width (a level bench is ~0);
## * grade: |dh| / ds along the centre line, over 8 m;
## * bank: on each side, the ground from the shoulder out 12 m: its height over the road and its mean
##   slope; a "face" is a bank at least FACE_H high and steeper than FACE_SLOPE, and a face run is
##   how far one side keeps such a face without a break (long runs read as cut planes);
## * uniform: within a face run, the spread of the bank's slope (a low spread is a planar ramp).
## Stations within JUNCTION m of another road's centre line are skipped (junctions blend two roads).
## Lots: each town lot's four sides, the steepest 2 m step from its edge out 8 m, and its bank height.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")

const STATION: float = 2.0
const BANK_OUT: float = 12.0
const FACE_H: float = 1.5
const FACE_SLOPE: float = 0.45
const JUNCTION: float = 14.0


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var dir: String = _arg(a, "--world", "")
	if dir == "":
		var overrides: Dictionary = {}
		for i: int in a.size() - 1:
			if a[i] == "--set" and a[i + 1].contains("="):
				var kv: PackedStringArray = a[i + 1].split("=", true, 1)
				overrides[kv[0]] = kv[1]
		overrides["size"] = _arg(a, "--size", "4")
		var settings: RefCounted = GenSettings.resolve(StringName(_arg(a, "--preset", "standard")), overrides, int(_arg(a, "--seed", "1")))
		var res: Dictionary = Worlds.ensure(settings, Callable(), false)
		if not bool(res.get("ok", false)):
			printerr("[audit] world FAILED: %s" % res.get("error", ""))
			get_tree().quit(1)
			return
		dir = str(res["dir"])
	if FileAccess.file_exists(dir.path_join("frameworks.json")):
		for e: String in Worlds.register_frameworks(dir):
			push_warning("terrain_audit: %s" % e)
	var world: WorldDef = WorldDef.load_from(dir)
	if world == null:
		get_tree().quit(1)
		return
	var spacing: float = float(_arg(a, "--spacing", "2"))
	var ids: Array = []
	if _arg(a, "--probe", "") != "":
		var pr: String = _arg(a, "--probe", "")
		ids = [world.region_at(float(pr.get_slice(",", 0)), float(pr.get_slice(",", 1)))]
	elif _arg(a, "--regions", "") != "":
		ids = Array(_arg(a, "--regions", "").split(","))
	else:
		ids = world.regions.keys()
		ids.sort()
	var total := _Stats.new()
	var per: Dictionary = {}
	for rid: String in ids:
		var t0: int = Time.get_ticks_msec()
		var rt: RegionTerrain = TerrainComposer.compose(world, rid, spacing)
		if rt == null:
			printerr("[audit] %s did not compose" % rid)
			continue
		var st := _Stats.new()
		_audit_roads(rt, st)
		if _arg(a, "--probe", "") != "":
			_probe(rt, _arg(a, "--probe", ""))
		if _arg(a, "--line", "") != "":
			var lv: PackedStringArray = _arg(a, "--line", "").split(",")
			var p0 := Vector2(float(lv[0]), float(lv[1]))
			var p1 := Vector2(float(lv[2]), float(lv[3]))
			var row: PackedStringArray = []
			for k: int in int(p0.distance_to(p1)) + 1:
				var q: Vector2 = p0.move_toward(p1, float(k))
				row.append("%.2f" % rt.height.sample(q.x, q.y))
			print("line: ", " ".join(row))
		if a.has("--debug"):
			print("roads %d placements %d rect %s" % [rt.roads.size(), rt.placements.size(), rt.height.rect()])
		_audit_lots(rt, st)
		total.merge(st)
		if _arg(a, "--shade", "") != "":
			_shade(rt, _arg(a, "--shade", "").path_join("%s.png" % rid))
		per[rid] = st.summary()
		print("[audit] %-24s %s (%d ms)" % [rid, st.line(), Time.get_ticks_msec() - t0])
	print("[audit] ALL %s" % total.line())
	var out: String = _arg(a, "--json", "")
	if out != "":
		var f := FileAccess.open(out, FileAccess.WRITE)
		f.store_string(JSON.stringify({"world": dir, "spacing": spacing, "all": total.summary(), "regions": per}, "\t"))
	get_tree().quit(0)


func _audit_roads(rt: RegionTerrain, st: _Stats) -> void:
	var hf: HeightField = rt.height
	var inner_rect: Rect2 = hf.rect().grow(-BANK_OUT - 4.0)
	var lines: Array[PackedVector2Array] = []
	for r: Dictionary in rt.roads:
		var pl := PackedVector2Array()
		for p: Variant in r["points"]:
			pl.append(Vector2(float(p[0]), float(p[2])))
		lines.append(pl)
	for ri: int in rt.roads.size():
		var r: Dictionary = rt.roads[ri]
		var pl: PackedVector2Array = lines[ri]
		if pl.size() < 2:
			continue
		var half: float = float(r["width"]) * 0.5
		var shoulder: float = 1.0
		var town: bool = str(r["id"]).contains("/")
		# Resample the polyline at STATION m.
		var stations: Array[Vector2] = []
		var dirs: Array[Vector2] = []
		for si: int in pl.size() - 1:
			var a: Vector2 = pl[si]
			var b: Vector2 = pl[si + 1]
			var seg: float = a.distance_to(b)
			if seg < 0.01:
				continue
			var d: Vector2 = (b - a) / seg
			var t: float = 0.0
			while t < seg:
				stations.append(a + d * t)
				dirs.append(d)
				t += STATION
		var runs: Array = [0.0, 0.0]
		var run_slopes: Array = [PackedFloat32Array(), PackedFloat32Array()]
		var prev_h: float = NAN
		var prev_p := Vector2.INF
		for k: int in stations.size():
			var c: Vector2 = stations[k]
			if not inner_rect.has_point(c) or _near_other(c, ri, lines, JUNCTION + half) or _on_bridge(c, rt.bridges):
				for side: int in 2:
					_close_run(st, runs, run_slopes, side, town)
				prev_h = NAN
				continue
			var nrm := Vector2(-dirs[k].y, dirs[k].x)
			var hc: float = hf.sample(c.x, c.y)
			var hl: float = hf.sample(c.x + nrm.x * half, c.y + nrm.y * half)
			var hr: float = hf.sample(c.x - nrm.x * half, c.y - nrm.y * half)
			st.add(&"cross" if not town else &"cross_town", absf(hl - hr) / (2.0 * half))
			if not is_nan(prev_h) and c.distance_to(prev_p) > 7.0:
				var g: float = absf(hc - prev_h) / c.distance_to(prev_p)
				st.add(&"grade" if not town else &"grade_town", g)
				if g > st.worst_grade:
					st.worst_grade = g
					st.worst_at = "%s at (%.0f, %.0f)" % [r["id"], c.x, c.y]
				prev_h = hc
				prev_p = c
			elif is_nan(prev_h):
				prev_h = hc
				prev_p = c
			for side: int in 2:
				var sgn: float = 1.0 if side == 0 else -1.0
				var e: Vector2 = c + nrm * sgn * (half + shoulder)
				var he: float = hf.sample(e.x, e.y)
				var o: Vector2 = c + nrm * sgn * (half + shoulder + BANK_OUT)
				var ho: float = hf.sample(o.x, o.y)
				var bank_h: float = absf(ho - he)
				var slope: float = bank_h / BANK_OUT
				# The steepest 2 m step out there (a short steep face counts too).
				var steep: float = 0.0
				for q: int in int(BANK_OUT / 2.0):
					var p0: Vector2 = e + nrm * sgn * q * 2.0
					var p1: Vector2 = p0 + nrm * sgn * 2.0
					steep = maxf(steep, absf(hf.sample(p1.x, p1.y) - hf.sample(p0.x, p0.y)) / 2.0)
				st.add(&"bank_h", bank_h)
				st.add(&"bank_steep", steep)
				if bank_h >= FACE_H and slope >= FACE_SLOPE:
					runs[side] = float(runs[side]) + STATION
					var rs: PackedFloat32Array = run_slopes[side]
					rs.append(slope)
					run_slopes[side] = rs
				else:
					_close_run(st, runs, run_slopes, side, town)
		for side: int in 2:
			_close_run(st, runs, run_slopes, side, town)


## Prints the road profile and the ground across it near a point (x,z): debugging an outlier.
func _probe(rt: RegionTerrain, at: String) -> void:
	var q := Vector2(float(at.get_slice(",", 0)), float(at.get_slice(",", 1)))
	for r: Dictionary in rt.roads:
		for p: Variant in r["points"]:
			var c := Vector2(float(p[0]), float(p[2]))
			if c.distance_to(q) < 40.0:
				var row: PackedStringArray = []
				for o: int in range(-20, 21, 4):
					row.append("%.1f" % rt.height.sample(c.x + o, c.y))
				print("%s (%.0f,%.0f) prof %.1f ground %.1f | x-20..20: %s | biome %s" % [r["id"], c.x, c.y, float(p[1]), rt.height.sample(c.x, c.y), " ".join(row), rt.biome_at(c.x, c.y)])


## A hillshade of the region (low sun, so banks and faces show), for before/after comparisons.
func _shade(rt: RegionTerrain, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var n: int = rt.height.width
	var img := Image.create(n, n, false, Image.FORMAT_RGB8)
	var light := Vector3(-0.7, 0.45, -0.55).normalized()
	for iz: int in n:
		for ix: int in n:
			var nrm: Vector3 = rt.height.grid_normal(ix, iz)
			var lit: float = clampf(nrm.dot(light), 0.0, 1.0)
			var slope: float = rad_to_deg(acos(clampf(nrm.y, -1.0, 1.0)))
			var c := Color(lit, lit, lit)
			if slope > 34.0:
				c = c.lerp(Color(0.8, 0.35, 0.2) * (0.4 + lit * 0.6), 0.5)
			img.set_pixel(ix, iz, c)
	img.save_png(path)


func _close_run(st: _Stats, runs: Array, run_slopes: Array, side: int, town: bool) -> void:
	var len_m: float = runs[side]
	if len_m >= 10.0:
		st.add(&"face_run", len_m)
		var sl: PackedFloat32Array = run_slopes[side]
		var mean: float = 0.0
		for v: float in sl:
			mean += v
		mean /= sl.size()
		var var_acc: float = 0.0
		for v: float in sl:
			var_acc += (v - mean) * (v - mean)
		st.add(&"face_spread", sqrt(var_acc / sl.size()))
	runs[side] = 0.0
	run_slopes[side] = PackedFloat32Array()


static func _on_bridge(c: Vector2, bridges: Array) -> bool:
	for b: Dictionary in bridges:
		var a := Vector2(float(b["from"][0]), float(b["from"][2]))
		var e := Vector2(float(b["to"][0]), float(b["to"][2]))
		if Geometry2D.get_closest_point_to_segment(c, a, e).distance_to(c) < float(b["width"]) + 6.0:
			return true
	return false


static func _near_other(c: Vector2, ri: int, lines: Array[PackedVector2Array], reach: float) -> bool:
	for oi: int in lines.size():
		if oi == ri:
			continue
		var pl: PackedVector2Array = lines[oi]
		for si: int in pl.size() - 1:
			var q: Vector2 = Geometry2D.get_closest_point_to_segment(c, pl[si], pl[si + 1])
			if q.distance_squared_to(c) < reach * reach:
				return true
	return false


func _audit_lots(rt: RegionTerrain, st: _Stats) -> void:
	var hf: HeightField = rt.height
	var inner_rect: Rect2 = hf.rect().grow(-12.0)
	for pl: Variant in rt.placements:
		var p: Dictionary = pl
		if str(p.get("kind", "")) != "lot":
			continue
		var o: Array = p["origin"]
		var c := Vector2(float(o[0]), float(o[2]))
		if not inner_rect.has_point(c):
			continue
		var size: Array = p["size"]
		var yaw: float = -deg_to_rad(float(p["rotation"]))
		var y: float = float(o[1])
		var ax := Vector2(cos(yaw), -sin(yaw))
		var az := Vector2(sin(yaw), cos(yaw))
		var hw: float = float(size[0]) * 0.5
		var hd: float = float(size[1]) * 0.5
		for side: int in 4:
			var n: Vector2 = [ax, -ax, az, -az][side]
			var ext: float = hw if side < 2 else hd
			var along: Vector2 = az if side < 2 else ax
			var span: float = hd if side < 2 else hw
			var steep: float = 0.0
			var bank: float = 0.0
			for t: int in 5:
				var base: Vector2 = c + n * ext + along * span * (t / 2.0 - 1.0) * 0.8
				for q: int in 4:
					var p0: Vector2 = base + n * q * 2.0
					var p1: Vector2 = p0 + n * 2.0
					if not inner_rect.has_point(p1):
						continue
					steep = maxf(steep, absf(hf.sample(p1.x, p1.y) - hf.sample(p0.x, p0.y)) / 2.0)
				var far: Vector2 = base + n * 8.0
				if inner_rect.has_point(far):
					bank = maxf(bank, absf(hf.sample(far.x, far.y) - y))
			st.add(&"lot_steep", steep)
			st.add(&"lot_bank", bank)
		# TD-318: the lip between the yard and its street, on the side facing the nearest road:
		# the steepest 1 m step from the frame's edge to the road's centre line (three lines).
		var q: Vector2 = _nearest_road_point(rt, c)
		if q.x == INF or c.distance_to(q) > maxf(hw, hd) + 14.0:
			continue
		var to: Vector2 = (q - c).normalized()
		var best_n: Vector2 = ax
		for n2: Vector2 in [ax, -ax, az, -az]:
			if n2.dot(to) > best_n.dot(to):
				best_n = n2
		var ext2: float = hw if absf(best_n.dot(ax)) > 0.5 else hd
		var along2: Vector2 = az if absf(best_n.dot(ax)) > 0.5 else ax
		var span2: float = hd if absf(best_n.dot(ax)) > 0.5 else hw
		var reach: float = maxf(2.0, (q - c).dot(best_n) - ext2)
		var lip: float = 0.0
		for t2: int in 3:
			var from: Vector2 = c + best_n * (ext2 - 2.0) + along2 * span2 * (t2 - 1.0) * 0.5
			for m: int in int(reach + 2.0):
				var a0: Vector2 = from + best_n * float(m)
				var a1: Vector2 = a0 + best_n
				if inner_rect.has_point(a1):
					lip = maxf(lip, absf(hf.sample(a1.x, a1.y) - hf.sample(a0.x, a0.y)))
		st.add(&"lot_lip", lip)
		if lip > 0.5 and OS.get_cmdline_user_args().has("--worst"):
			print("[worst] lip %.2f lot %s at %.0f,%.0f y %.2f road %.0f,%.0f" % [lip, p.get("id", ""), c.x, c.y, y, q.x, q.y])
	# TD-318: creases where a road ends on another: the steepest 1 m step on either carriageway
	# within 10 m of the junction.
	for r: Dictionary in rt.roads:
		var pts: Array = r["points"]
		if pts.size() < 2:
			continue
		for ep: Variant in [pts[0], pts[pts.size() - 1]]:
			var e := Vector2(float(ep[0]), float(ep[ep.size() - 1]))
			if not inner_rect.has_point(e):
				continue
			var other: Dictionary = {}
			for r2: Dictionary in rt.roads:
				if r2 != r and _road_dist(r2, e) < 4.0:
					other = r2
					break
			if other.is_empty():
				continue
			# Only on the two carriageways: the banks beside a junction are not its crease.
			var crease: float = 0.0
			for gz: int in range(-10, 11):
				for gx: int in range(-10, 10):
					var a2 := e + Vector2(gx, gz)
					if a2.distance_to(e) > 10.0:
						continue
					for nb: Vector2 in [a2 + Vector2(1, 0), a2 + Vector2(0, 1)]:
						var on: bool = true
						for q2: Vector2 in [a2, nb]:
							if _road_dist(r, q2) > float(r["width"]) * 0.5 and _road_dist(other, q2) > float(other["width"]) * 0.5:
								on = false
						if on:
							crease = maxf(crease, absf(hf.sample(nb.x, nb.y) - hf.sample(a2.x, a2.y)))
			st.add(&"junction_step", crease)
			if crease > 0.6 and OS.get_cmdline_user_args().has("--worst"):
				print("[worst] junction %.2f road %s at %.0f,%.0f" % [crease, r.get("id", ""), e.x, e.y])


func _road_dist(r: Dictionary, p: Vector2) -> float:
	var pts: Array = r["points"]
	var best: float = INF
	for i: int in pts.size() - 1:
		var a := Vector2(float(pts[i][0]), float(pts[i][pts[i].size() - 1]))
		var b := Vector2(float(pts[i + 1][0]), float(pts[i + 1][pts[i + 1].size() - 1]))
		best = minf(best, Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p))
	return best


func _nearest_road_point(rt: RegionTerrain, c: Vector2) -> Vector2:
	var best := Vector2(INF, INF)
	var bd: float = INF
	for r: Dictionary in rt.roads:
		var pts: Array = r["points"]
		for i: int in pts.size() - 1:
			var a := Vector2(float(pts[i][0]), float(pts[i][pts[i].size() - 1]))
			var b := Vector2(float(pts[i + 1][0]), float(pts[i + 1][pts[i + 1].size() - 1]))
			var q: Vector2 = Geometry2D.get_closest_point_to_segment(c, a, b)
			var d: float = q.distance_to(c)
			if d < bd:
				bd = d
				best = q
	return best


class _Stats:
	var v: Dictionary = {}
	var worst_grade: float = 0.0
	var worst_at: String = ""

	func add(k: StringName, x: float) -> void:
		# Packed arrays are values: append to the stored one, not a cast copy.
		var arr: PackedFloat32Array = v.get(k, PackedFloat32Array())
		arr.append(x)
		v[k] = arr

	func merge(o: _Stats) -> void:
		if o.worst_grade > worst_grade:
			worst_grade = o.worst_grade
			worst_at = o.worst_at
		for k: StringName in o.v:
			var arr: PackedFloat32Array = v.get(k, PackedFloat32Array())
			arr.append_array(o.v[k])
			v[k] = arr

	func pct(k: StringName, q: float) -> float:
		if count(k) == 0:
			return 0.0
		var a: PackedFloat32Array = (v[k] as PackedFloat32Array).duplicate()
		a.sort()
		return a[clampi(int(q * (a.size() - 1)), 0, a.size() - 1)]

	func frac_over(k: StringName, x: float) -> float:
		if not v.has(k):
			return 0.0
		var c: int = 0
		for e: float in v[k]:
			if e > x:
				c += 1
		return float(c) / maxf(1.0, (v[k] as PackedFloat32Array).size())

	func count(k: StringName) -> int:
		return (v[k] as PackedFloat32Array).size() if v.has(k) else 0

	func total(k: StringName) -> float:
		var s: float = 0.0
		for e: float in v.get(k, PackedFloat32Array()):
			s += e
		return s

	func summary() -> Dictionary:
		var d: Dictionary = {}
		for k: StringName in v:
			d[k] = {"n": count(k), "p50": pct(k, 0.5), "p95": pct(k, 0.95), "max": pct(k, 1.0)}
		d["cross_over_4pct"] = frac_over(&"cross", 0.04)
		d["cross_town_over_4pct"] = frac_over(&"cross_town", 0.04)
		d["grade_over_12pct"] = frac_over(&"grade", 0.12)
		d["face_run_total_m"] = total(&"face_run")
		return d

	func line() -> String:
		return ("cross p95 %.3f max %.3f >4%% %.1f%% | town cross p95 %.3f >4%% %.1f%% | grade p95 %.3f max %.3f >12%% %.1f%% | bank_h p95 %.1f steep p95 %.2f "
			+ "| faces %d runs, longest %.0f m, total %.0f m, spread p50 %.3f | lots steep p95 %.2f max %.2f bank p95 %.1f | lip p95 %.2f max %.2f (n %d) | junction step p95 %.2f max %.2f (n %d) | worst grade %s") % [
			pct(&"cross", 0.95), pct(&"cross", 1.0), frac_over(&"cross", 0.04) * 100.0, pct(&"cross_town", 0.95), frac_over(&"cross_town", 0.04) * 100.0,
			pct(&"grade", 0.95), pct(&"grade", 1.0), frac_over(&"grade", 0.12) * 100.0, pct(&"bank_h", 0.95), pct(&"bank_steep", 0.95),
			count(&"face_run"), pct(&"face_run", 1.0), total(&"face_run"), pct(&"face_spread", 0.5), pct(&"lot_steep", 0.95), pct(&"lot_steep", 1.0), pct(&"lot_bank", 0.95),
			pct(&"lot_lip", 0.95), pct(&"lot_lip", 1.0), count(&"lot_lip"), pct(&"junction_step", 0.95), pct(&"junction_step", 1.0), count(&"junction_step"), worst_at]


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default
