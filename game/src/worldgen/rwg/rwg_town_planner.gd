class_name RwgTownPlanner
extends RefCounted
## The organic town planner of random worlds v2 (ADR-0040, docs/RWG_V2_PLAN.md §3). From a site
## (centre, radius, size class), the world's ground (callables), the arterials through the town
## (world roads) and a seed, it plans a small American town that grows out of its land: side
## streets that bend with the contours (RwgStreets), lots by frontage subdivision whose fronts face
## their streets (RwgLots), zoning by rings and quotas (shops on the main street nearest the
## centre, civic buildings round the square, industry and farms out on the arterials, houses
## everywhere else, thinning to a ragged edge), a paved plaza in towns, and the street furniture.
##
## Pure: a function of its inputs only, no scene tree, no autoloads (content is not needed; lot
## sizes come from the tuning, which fits the real buildings: see test_town_planner.gd), so the
## generator can plan several towns on worker threads. Determinism: every random draw comes from
## streams derived from `seed` and the site id (`streets`, `lots`, `fixtures`).
##
## Coordinates are world XZ throughout (x east, z south): a v2 town is a world-level feature, its
## framework origin is [0, 0] with rotation 0. Frames and fixture rotations follow PoiManager.lot_xf
## (degrees; `Basis(Vector3.UP, yaw)`; facing south is 0, east 90). The composer's 2D `rot` and a
## placement's `rotation` turn the other way (`Vector2.rotated(a)` is `Basis(UP, -a)`), so a lot's
## pad and placement take `-yaw` there.

const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")
const Lots := preload("res://src/worldgen/rwg/rwg_lots.gd")

const KINDS: PackedStringArray = ["hamlet", "village", "town"]
const CONFIG_PATH: String = "res://data/config/town_planner.json"
## The keys of a v2 town framework def (§3.12); the plan carries more (junctions, blocks, stats).
const FRAMEWORK_KEYS: PackedStringArray = ["id", "name", "layout", "kind", "size", "center", "radius", "tier_range", "lots", "roads", "fixtures", "plaza"]


## Plans a town.
## * `site`: {id, kind: "hamlet" | "village" | "town", center: [x, z] | Vector2, radius, name?}.
## * `world`: {height: Callable(x, z) -> float (the reference ground streets and pads are graded
##   from), water: Callable(x, z) -> float (distance to water, negative in it; optional),
##   slope: Callable(x, z) -> float (optional)}.
## * `arterials`: the world roads through the town: [{id, points: [[x, z], ...], width, shoulder,
##   surface, markings}], the main street first.
## * `tuning`: data/config/town_planner.json (`default_tuning()`).
## * `seed`: the town's seed.
## Returns {layout, kind, name, center, radius, size, bounds, tier_range, lots, roads, fixtures,
## plaza, junctions, blocks, stats} (see `to_framework` for the framework def's own keys).
static func plan(site: Dictionary, world: Dictionary, arterials: Array, tuning: Dictionary, seed: int) -> Dictionary:
	var t0: int = Time.get_ticks_usec()
	var kind: String = str(site.get("kind", "village"))
	var sid: String = str(site.get("id", "town"))
	var center: Vector2 = _v2(site.get("center", [0.0, 0.0]))
	var radius: float = float(site.get("radius", 220.0))
	var kd: Dictionary = (tuning.get("kinds", {}) as Dictionary).get(kind, {})
	var scfg: Dictionary = tuning.get("streets", {})
	var lcfg: Dictionary = tuning.get("lots", {})
	var fcfg: Dictionary = tuning.get("fixtures", {})
	var outskirts: float = float(lcfg.get("outskirts", 400.0))
	var reach: float = radius + outskirts + 100.0
	var ground := Streets.Ground.new(world, center, reach)
	var net := Streets.new()
	net.setup(ground, center, radius, kd, scfg, reach)
	for a: Variant in arterials:
		net.add_arterial(a)
	net.arterial_junctions()
	var lots := Lots.new()
	lots.setup(net, lcfg)
	var rs := _rng(seed, sid, "streets")
	var rl := _rng(seed, sid, "lots")
	var rf := _rng(seed, sid, "fixtures")
	var stats: Dictionary = {}
	# The square first: streets keep out of it and of the civic yard behind it.
	var plaza: Lots.Lot = _plaza(net, lots, kd, rl)
	if plaza != null:
		lots.add(plaza)
		var back: float = float((lots.size_of("civic")[1] as Array)[1]) + lots.verge + 6.0
		net.obstacles.append(PackedVector2Array([plaza.at(-plaza.w * 0.5 - 8.0, plaza.d * 0.5), plaza.at(plaza.w * 0.5 + 8.0, plaza.d * 0.5),
			plaza.at(plaza.w * 0.5 + 8.0, -plaza.d * 0.5 - back), plaza.at(-plaza.w * 0.5 - 8.0, -plaza.d * 0.5 - back)]))
	var t_net: int = Time.get_ticks_usec()
	net.grow(rs)
	if bool(kd.get("back_lanes", false)):
		net.add_back_lanes(rs, float(scfg.get("back_lane_offset", 44.0)))
	net.add_bulbs()
	var t_lots: int = Time.get_ticks_usec()
	# Lots, quota by quota (§3.7), then houses everywhere else.
	var quota: Dictionary = {}
	for z: String in ["commercial", "civic", "industrial", "rural"]:
		var qr: Array = kd.get(z, [0, 0])
		quota[z] = rl.randi_range(int(qr[0]), int(qr[1]))
	var counts: Dictionary = {"commercial": 0, "civic": 0, "industrial": 0, "rural": 0}
	for z2: String in ["commercial", "civic"]:
		if z2 == "civic" and plaza != null:
			counts["civic"] += _plaza_civic(lots, plaza, rl, int(quota["civic"]))
		# Shops nearest the centre on the arterials; civic just beyond them (also on the first
		# stretch of the side streets); then anywhere in town; then on ground a metre steeper.
		var want: int = int(quota[z2]) - int(counts[z2])
		var lo_q: int = int((kd.get(z2, [0, 0]) as Array)[0])
		var d_at: float = 0.0
		var d_lo: float = 0.0
		if z2 == "civic":
			d_lo = _mean_distance(lots, "commercial", net.center)
			d_at = d_lo * 1.05
		counts[z2] += _frontage_quota(net, lots, rl, z2, want, d_lo, radius * 0.6, d_at, z2 == "civic")
		# Short of the class's minimum: the inner ring on ground a metre steeper, then anywhere.
		if int(counts[z2]) < lo_q:
			counts[z2] += _frontage_quota(net, lots, rl, z2, lo_q - int(counts[z2]), d_lo, radius * 0.6, d_at, true, 1.0)
		if int(counts[z2]) < lo_q:
			counts[z2] += _frontage_quota(net, lots, rl, z2, lo_q - int(counts[z2]), 0.0, radius, d_at, true, 1.0)
	counts["industrial"] += _frontage_quota(net, lots, rl, "industrial", int(quota["industrial"]), radius * 0.72, radius + 140.0, radius * 0.92, false)
	counts["rural"] += _rural(net, lots, rl, int(quota["rural"]), radius, outskirts, lcfg)
	var fixed: int = lots.lots.size() - (1 if plaza != null else 0)
	_residential(net, lots, rl, radius)
	var lr: Array = kd.get("lots", [10, 20])
	var span: int = int(lr[1]) - int(lr[0])
	var target: int = rl.randi_range(int(lr[0]) + span / 6, int(lr[1]) - span / 8)
	var candidates: int = lots.lots.size() - (1 if plaza != null else 0)
	_thin(lots, rl, maxi(0, target - fixed), center, radius, float(lcfg.get("thin", 2.5)))
	_finish(net, lots, kd, radius)
	var t_parcels: int = Time.get_ticks_usec()
	lots.parcels(float(lcfg.get("parcel_back", 8.0)))
	var t_fix: int = Time.get_ticks_usec()
	var fixtures: Array = _fixtures(net, lots, plaza, kd, fcfg, rf)
	var t_blocks: int = Time.get_ticks_usec()
	var blocks: Array[Dictionary] = net.blocks()
	var t_end: int = Time.get_ticks_usec()
	stats = _stats(net, lots, quota, target, candidates)
	stats["ground_calls"] = ground.calls
	stats["ms"] = (t_end - t0) / 1000.0
	stats["ms_parts"] = {"setup": (t_net - t0) / 1000.0, "streets": (t_lots - t_net) / 1000.0, "lots": (t_parcels - t_lots) / 1000.0,
		"parcels": (t_fix - t_parcels) / 1000.0, "fixtures": (t_blocks - t_fix) / 1000.0, "blocks": (t_end - t_blocks) / 1000.0}
	return _output(site, net, lots, plaza, fixtures, blocks, stats)


## The framework def of a plan (§3.12): exactly the keys FrameworkDef v2 reads.
static func to_framework(p: Dictionary, fw_id: String, name: String) -> Dictionary:
	var out: Dictionary = {"id": fw_id, "name": name}
	for k: String in FRAMEWORK_KEYS:
		if p.has(k) and not out.has(k):
			out[k] = p[k]
	return out


## The planner's tuning: data/config/town_planner.json (through ContentDB when it is loaded, which
## is safe from worker threads; else read from the file).
static func default_tuning() -> Dictionary:
	var db: Node = ContentDB.instance
	if db != null:
		var c: Dictionary = db.call(&"config", &"town_planner")
		if not c.is_empty():
			return c
	var j := JSON.new()
	if FileAccess.file_exists(CONFIG_PATH) and j.parse(FileAccess.get_file_as_string(CONFIG_PATH)) == OK and j.data is Dictionary:
		return j.data
	return {}


## Problems with a tuning dictionary (empty when it is usable).
static func config_errors(t: Dictionary) -> PackedStringArray:
	var out: PackedStringArray = []
	var kinds: Dictionary = t.get("kinds", {})
	for k: String in KINDS:
		if not kinds.has(k):
			out.append("kinds.%s missing" % k)
			continue
		var kd: Dictionary = kinds[k]
		for key: String in ["radius", "side_streets", "lots", "commercial", "civic", "industrial", "rural", "loops", "culdesacs"]:
			var v: Variant = kd.get(key, null)
			if not v is Array or (v as Array).size() != 2 or float(v[0]) > float(v[1]):
				out.append("kinds.%s.%s must be [lo, hi]" % [k, key])
		for key2: String in ["core", "street_budget"]:
			if not kd.has(key2):
				out.append("kinds.%s.%s missing" % [k, key2])
	var sizes: Dictionary = (t.get("lots", {}) as Dictionary).get("sizes", {})
	for sk: String in Lots.SIZE_ZONES:
		if sk == "plaza":
			continue
		var sz: Variant = sizes.get(sk, null)
		if not sz is Array or (sz as Array).size() != 2 or float(sz[0][0]) > float(sz[0][1]) or float(sz[1][0]) > float(sz[1][1]):
			out.append("lots.sizes.%s must be [[w lo, w hi], [d lo, d hi]]" % sk)
	return out


# --- The square and the quotas -----------------------------------------------------------------

## Mean distance from the centre of the lots of a zone (0 without any).
static func _mean_distance(lots: Lots, zone: String, center: Vector2) -> float:
	var acc: float = 0.0
	var n: int = 0
	for l: Lots.Lot in lots.lots:
		if l.zone == zone:
			acc += l.c.distance_to(center)
			n += 1
	return acc / n if n > 0 else 0.0


## The plaza (towns): a paved square on the main street a step out from the crossing (the shops
## take the corners), on whichever side has room and level ground, in the core.
static func _plaza(net: Streets, lots: Lots, kd: Dictionary, r: RandomNumberGenerator) -> Lots.Lot:
	var pr: Array = kd.get("plaza", [0, 0])
	if float(pr[1]) <= 0.0:
		return null
	var arts: Array = []
	for si: int in net.streets.size():
		if net.streets[si].cls == "arterial":
			arts.append([net.streets[si].line.closest(net.center).x, si])
	arts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var first: int = 1 if r.randf() < 0.5 else -1
	var sizes: Array[float] = [r.randf_range(float(pr[0]), float(pr[1])), float(pr[0])]
	for attempt: int in 2:
		var size: float = sizes[attempt]
		var relief: float = lots.relief_of("plaza") + attempt * 1.0
		for ar: Array in arts:
			var si2: int = int(ar[1])
			var st: Streets.Street = net.streets[si2]
			var sc: float = st.line.closest(net.center).y
			for k: float in [1.0, -1.0, 2.0, -2.0, 0.0, 3.0, -3.0]:
				for side: int in [first, -first]:
					var lo: float = sc + k * (size * 0.5 + 18.0) - size * 0.5
					var hi: float = lo + size
					if lo < 0.0 or hi > st.length() or not is_nan(Lots._jump(lots.blocked(si2, side), lo, hi, 1.0)):
						continue
					var l: Lots.Lot = lots.frame_on(si2, side, lo, hi, size)
					if l.c.distance_to(net.center) < float(kd.get("core", 130.0)) and lots.fits(l, relief):
						l.zone = "plaza"
						l.size_key = "plaza"
						l.fixed = true
						return l
	return null


## Civic lots round the square: one behind it and one at either side, facing it.
static func _plaza_civic(lots: Lots, plaza: Lots.Lot, r: RandomNumberGenerator, quota: int) -> int:
	var sz: Array = lots.size_of("civic")
	var made: int = 0
	var gap: float = lots.verge
	for where: int in [0, 1, -1]:
		if made >= quota:
			break
		for attempt: Array in [[r.randf_range(float(sz[0][0]), float(sz[0][1])), r.randf_range(float(sz[1][0]), float(sz[1][1]))], [float(sz[0][0]), float(sz[1][0])]]:
			var w: float = float(attempt[0])
			var d: float = float(attempt[1])
			var l := Lots.Lot.new()
			if where == 0:
				l.set_frame(plaza.at(0.0, -plaza.d * 0.5 - gap - d * 0.5), w, d, plaza.az)
			else:
				# Beside the square, its front towards it, its side on the main street's lot line.
				l.set_frame(plaza.at(where * (plaza.w * 0.5 + gap + d * 0.5), plaza.d * 0.5 - w * 0.5), w, d, plaza.ax * -where)
			l.street = -1
			if lots.fits(l, lots.relief_of("civic")):
				l.zone = "civic"
				l.size_key = "civic"
				l.fixed = true
				lots.add(l)
				made += 1
				break
	return made


## A quota of `zone` lots on arterial frontage (and, for civic, the first stretch of the side
## streets) between `d_lo` and `d_hi` m from the centre: candidates from walks out from the centre,
## taken nearest `d_at` first while they still fit.
static func _frontage_quota(net: Streets, lots: Lots, r: RandomNumberGenerator, zone: String, quota: int, d_lo: float, d_hi: float, d_at: float, side_streets: bool,
		extra_relief: float = 0.0) -> int:
	if quota <= 0:
		return 0
	var keep_relief: float = lots.relief_of(zone)
	if extra_relief > 0.0:
		lots.reliefs[zone] = keep_relief + extra_relief
	var center: Vector2 = net.center
	var zone_at := func(p: Vector2, _si: int) -> String:
		var d: float = p.distance_to(center)
		return "stop" if d > d_hi else ("" if d < d_lo else zone)
	var cands: Array[Lots.Lot] = []
	for si: int in net.streets.size():
		var st: Streets.Street = net.streets[si]
		if st.cls == "arterial":
			var sc: float = st.line.closest(center).y
			for side: int in [1, -1]:
				cands.append_array(lots.walk(si, side, sc + 0.5, st.length(), zone_at, r, false, 12))
				cands.append_array(lots.walk(si, side, sc - 0.5, 0.0, zone_at, r, false, 12))
		elif side_streets and st.gen >= 1 and st.cls in ["street", "lane"] and st.line.points[0].distance_to(center) < d_hi:
			for side2: int in [1, -1]:
				cands.append_array(lots.walk(si, side2, 0.0, minf(st.length(), 130.0), zone_at, r, false, 2))
	cands.sort_custom(func(a: Lots.Lot, b: Lots.Lot) -> bool: return absf(a.c.distance_to(center) - d_at) < absf(b.c.distance_to(center) - d_at))
	var made: int = 0
	for l: Lots.Lot in cands:
		if made >= quota:
			break
		if l.c.distance_to(center) < d_lo:
			continue
		if lots.fits(l, lots.relief_of(zone)):
			l.fixed = true
			lots.add(l)
			made += 1
	lots.reliefs[zone] = keep_relief
	return made


## Rural lots out along the arterials past the town (§3.9 outskirts), every 150-300 m, taking the
## arterials' ends in turn; then on stubs (dead ends at the edge) if the quota is not met.
static func _rural(net: Streets, lots: Lots, r: RandomNumberGenerator, quota: int, radius: float, outskirts: float, lcfg: Dictionary) -> int:
	if quota <= 0:
		return 0
	var center: Vector2 = net.center
	var sp: Array = lcfg.get("rural_spacing", [150.0, 300.0])
	var zone_at := func(p: Vector2, _si: int) -> String:
		return "rural" if p.distance_to(center) < radius + outskirts else "stop"
	# One cursor per arterial end: [street, dir, arc].
	var ends: Array = []
	for si: int in net.streets.size():
		var st: Streets.Street = net.streets[si]
		if st.cls != "arterial":
			continue
		var sc: float = st.line.closest(center).y
		for dir: float in [1.0, -1.0]:
			var s: float = sc
			while s > 0.0 and s < st.length() and st.line.point_at(s).distance_to(center) < radius + 30.0:
				s += dir * 8.0
			if s > 0.0 and s < st.length():
				ends.append([si, dir, s + dir * r.randf_range(0.0, 60.0)])
	var made: int = 0
	var idle: int = 0
	var k: int = 0
	while made < quota and not ends.is_empty() and idle < ends.size():
		var e: Array = ends[k % ends.size()]
		k += 1
		var si2: int = int(e[0])
		var dir2: float = float(e[1])
		var s2: float = float(e[2])
		var st2: Streets.Street = net.streets[si2]
		if s2 <= 0.0 or s2 >= st2.length() or st2.line.point_at(s2).distance_to(center) > radius + outskirts:
			idle += 1
			continue
		var side: int = 1 if r.randf() < 0.5 else -1
		var got: Array[Lots.Lot] = lots.walk(si2, side, s2, s2 + dir2 * 90.0, zone_at, r, true, 1)
		if got.is_empty():
			got = lots.walk(si2, -side, s2, s2 + dir2 * 90.0, zone_at, r, true, 1)
		if got.is_empty():
			e[2] = s2 + dir2 * 40.0
			continue
		idle = 0
		got[0].fixed = true
		made += 1
		e[2] = s2 + dir2 * (got[0].w + r.randf_range(float(sp[0]), float(sp[1])))
	return made


## Houses on every street side inside the town (inner sizes within 0.6 r, outer beyond), the
## turning circles' head lots first.
static func _residential(net: Streets, lots: Lots, r: RandomNumberGenerator, radius: float) -> void:
	var center: Vector2 = net.center
	var zone_at := func(p: Vector2, _si: int) -> String:
		var d: float = p.distance_to(center)
		return "stop" if d > radius else ("inner_residential" if d < radius * 0.6 else "outer_residential")
	for si: int in net.streets.size():
		var st: Streets.Street = net.streets[si]
		if st.bulb >= 0:
			var key: String = "inner_residential" if st.line.points[st.line.points.size() - 1].distance_to(center) < radius * 0.6 else "outer_residential"
			lots.head_lots(si, key, r)
	for si2: int in net.streets.size():
		var st2: Streets.Street = net.streets[si2]
		match st2.cls:
			"arterial":
				var sc: float = st2.line.closest(center).y
				for side: int in [1, -1]:
					lots.walk(si2, side, sc + 0.5, st2.length(), zone_at, r, true)
					lots.walk(si2, side, sc - 0.5, 0.0, zone_at, r, true)
			"street", "lane":
				for side2: int in [1, -1]:
					lots.walk(si2, side2, 0.0, st2.length(), zone_at, r, true)


## Thins the houses to `keep`: a weighted draw without replacement (exponential race), the weight
## falling with distance from the centre, so the core stays full and the edge goes ragged.
static func _thin(lots: Lots, r: RandomNumberGenerator, keep: int, center: Vector2, radius: float, k: float) -> void:
	var keys: Array = []
	for l: Lots.Lot in lots.lots:
		if l.fixed:
			continue
		var x: float = l.c.distance_to(center) / radius
		keys.append([-log(maxf(r.randf(), 1.0e-9)) / exp(-k * x * x), l])
	if keys.size() <= keep:
		return
	keys.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var drop: Dictionary = {}
	for i: int in range(keep, keys.size()):
		drop[keys[i][1]] = true
	lots.retain(func(l: Lots.Lot) -> bool: return not drop.has(l))


## Ids, rings, zoning lists and pad heights.
static func _finish(net: Streets, lots: Lots, kd: Dictionary, radius: float) -> void:
	var core: float = float(kd.get("core", 80.0))
	var civic_pure: int = int(kd.get("civic_pure", 2))
	var n: int = 0
	var civic_n: int = 0
	for l: Lots.Lot in lots.lots:
		var st: Vector3 = lots.ground_stats(l)
		l.y = st.z
		l.relief = st.y - st.x
		if l.zone == "plaza":
			l.id = "plaza"
			continue
		l.id = "lot_%d" % n
		n += 1
		var d: float = l.c.distance_to(net.center)
		l.ring = "core" if d < core else ("inner" if d < radius * 0.6 else ("outer" if d < radius else "edge"))
		var on_arterial: bool = l.street >= 0 and net.streets[l.street].cls == "arterial"
		match l.zone:
			"commercial":
				l.zoning = PackedStringArray(["commercial", "roadside"] if on_arterial else ["commercial"])
			"civic":
				# Past the first few, a civic lot may take a shop: the authored civic pool is small.
				l.zoning = PackedStringArray(["civic"] if civic_n < civic_pure else ["civic", "commercial"])
				civic_n += 1
			_:
				l.zoning = PackedStringArray([l.zone])


# --- Fixtures ------------------------------------------------------------------------------------

## Street furniture (§3.9) on the verges, never in a lot: lamps in the core and inner rings, poles
## along the arterials out past the edge, hydrants in the inner ring, stop signs on the minor leg of
## each junction, speed signs at the entries, shop and civic dressing, mailboxes at the houses and
## farms, the square's benches, a few wrecks and the Cordon's barricade across one entry.
static func _fixtures(net: Streets, lots: Lots, plaza: Lots.Lot, kd: Dictionary, fcfg: Dictionary, r: RandomNumberGenerator) -> Array:
	var out: Array = []
	var center: Vector2 = net.center
	var radius: float = net.radius
	var free := func(p: Vector2) -> bool:
		for oi: int in lots._query(Rect2(p, Vector2.ZERO).grow(1.0)):
			var o: Lots.Lot = lots.lots[oi]
			if o.zone == "plaza":
				continue
			var lp := Vector2((p - o.c).dot(o.ax), (p - o.c).dot(o.az))
			if absf(lp.x) < o.w * 0.5 + 0.4 and absf(lp.y) < o.d * 0.5 + 0.4:
				return false
		return true
	var add := func(prop: String, p: Vector2, rot: float) -> void:
		out.append({"id": "fx_%d" % out.size(), "prop": prop, "pos": [snappedf(p.x, 0.1), snappedf(p.y, 0.1)], "rot": snappedf(wrapf(rot, -180.0, 180.0), 1.0)})
	var lamp_sp: Array = fcfg.get("lamp_spacing", [30.0, 38.0])
	var hyd_sp: Array = fcfg.get("hydrant_spacing", [60.0, 90.0])
	var pole_sp: Array = fcfg.get("pole_spacing", [38.0, 44.0])
	var pole_far: Array = fcfg.get("pole_spacing_rural", [50.0, 60.0])
	# Lamps and hydrants along every street in the core and inner rings.
	for si: int in net.streets.size():
		var st: Streets.Street = net.streets[si]
		if not st.cls in ["arterial", "street", "lane"]:
			continue
		var arcs: Array = []
		for stn: Array in st.stations:
			arcs.append(float(stn[0]))
		var kerb: float = st.half() + st.shoulder * 0.6 + 0.6
		for kind: int in 2:
			var sp: Array = lamp_sp if kind == 0 else hyd_sp
			var s: float = r.randf_range(6.0, 16.0) if kind == 0 else r.randf_range(20.0, 40.0)
			var k: int = 0
			while s < st.length() - 4.0:
				var p: Vector2 = st.line.point_at(s)
				if p.distance_to(center) < radius * 0.6 and not _near_arc(arcs, s, 9.0):
					var t: Vector2 = st.line.tangent_at(s)
					var n: Vector2 = Vector2(-t.y, t.x) * (1.0 if k % 2 == 0 else -1.0)
					var q: Vector2 = p + n * (kerb if kind == 0 else kerb + 0.7)
					if free.call(q):
						add.call("street_lamp" if kind == 0 else "fire_hydrant", q, _yaw(n) if kind == 0 else 0.0)
					k += 1
				s += r.randf_range(float(sp[0]), float(sp[1]))
	# Poles along the arterials, from the centre out past the farms.
	var far: float = radius + float(fcfg.get("pole_reach", 150.0))
	for l: Lots.Lot in lots.lots:
		if l.zone == "rural":
			far = maxf(far, l.c.distance_to(center) + 30.0)
	for si2: int in net.streets.size():
		var art: Streets.Street = net.streets[si2]
		if art.cls != "arterial":
			continue
		var arcs2: Array = []
		for stn2: Array in art.stations:
			arcs2.append(float(stn2[0]))
		var side: float = 1.0 if r.randf() < 0.5 else -1.0
		var off: float = lots.front_offset(art) - 0.9
		var sc: float = art.line.closest(center).y
		for dir: float in [1.0, -1.0]:
			var s2: float = sc + dir * r.randf_range(8.0, 20.0)
			while s2 > 0.0 and s2 < art.length():
				var p2: Vector2 = art.line.point_at(s2)
				var dist: float = p2.distance_to(center)
				if dist > far:
					break
				if not _near_arc(arcs2, s2, 12.0):
					var t2: Vector2 = art.line.tangent_at(s2)
					var q2: Vector2 = p2 + Vector2(-t2.y, t2.x) * side * off
					if free.call(q2):
						add.call("utility_pole", q2, _yaw(t2))
				var spr: Array = pole_sp if dist < radius else pole_far
				s2 += dir * r.randf_range(float(spr[0]), float(spr[1]))
	# Stop signs on the minor leg of each junction, on the right of the traffic coming up to it.
	for si3: int in net.streets.size():
		var st3: Streets.Street = net.streets[si3]
		if st3.gen < 1 or not st3.cls in ["street", "lane", "back_lane"]:
			continue
		for end_i: int in 2:
			if end_i == 1 and not st3.snapped:
				continue
			var major: Streets.Street = net.streets[st3.parent] if end_i == 0 else null
			var major_half: float = major.half() if major != null else 3.0
			var back: float = major_half + 3.5
			var s3: float = back if end_i == 0 else st3.length() - back
			if s3 <= 0.0 or s3 >= st3.length():
				continue
			var t3: Vector2 = st3.line.tangent_at(s3)
			var u: Vector2 = -t3 if end_i == 0 else t3
			var q3: Vector2 = st3.line.point_at(s3) + Vector2(-u.y, u.x) * (st3.half() + 1.2)
			if free.call(q3):
				add.call("road_sign_stop", q3, _yaw(-u))
	# Speed signs where the arterials come into town, and the Cordon's barricade across one entry.
	var entries: Array = []
	for si4: int in net.streets.size():
		var art2: Streets.Street = net.streets[si4]
		if art2.cls != "arterial":
			continue
		var sc2: float = art2.line.closest(center).y
		for dir2: float in [1.0, -1.0]:
			var s4: float = sc2
			while s4 > 0.0 and s4 < art2.length() and art2.line.point_at(s4).distance_to(center) < radius:
				s4 += dir2 * 4.0
			if s4 <= 0.0 or s4 >= art2.length():
				continue
			entries.append([si4, dir2, s4])
			var out_t: Vector2 = art2.line.tangent_at(s4) * dir2
			var u2: Vector2 = -out_t
			var q4: Vector2 = art2.line.point_at(s4) + Vector2(-u2.y, u2.x) * (art2.half() + art2.shoulder + 0.8)
			if free.call(q4):
				add.call("road_sign_speed", q4, _yaw(-u2))
	if not entries.is_empty() and bool(fcfg.get("barricade", true)):
		var e: Array = entries[r.randi() % entries.size()]
		var art3: Streets.Street = net.streets[int(e[0])]
		var dir3: float = float(e[1])
		var s5: float = float(e[2]) - dir3 * 12.0
		var p5: Vector2 = art3.line.point_at(s5)
		var t5: Vector2 = art3.line.tangent_at(s5) * dir3
		var n5: Vector2 = Vector2(-t5.y, t5.x)
		add.call("jersey_barrier", p5 - n5 * 2.1, _yaw(t5) + r.randf_range(-6.0, 6.0))
		add.call("jersey_barrier", p5 + n5 * 2.0 - t5 * 1.5, _yaw(t5) + r.randf_range(-6.0, 6.0))
		add.call("sawhorse_barricade", p5 - t5 * 3.5 + n5 * r.randf_range(-1.0, 1.0), _yaw(t5) + r.randf_range(-10.0, 10.0))
		var q5: Vector2 = p5 - t5 * 6.5 + n5 * (art3.half() + 1.6)
		if free.call(q5):
			add.call("oil_drum_fire", q5, 0.0)
	# Shops and civic buildings: dumpsters, litter, benches, a payphone, collection boxes, papers.
	var did_phone: bool = false
	var did_box: bool = false
	for l2: Lots.Lot in lots.lots:
		var front: float = l2.d * 0.5 + lots.verge * 0.5
		match l2.zone:
			"commercial":
				if r.randf() < 0.5:
					var q6: Vector2 = l2.at((l2.w * 0.5 - 1.6) * (1.0 if r.randf() < 0.5 else -1.0), front)
					if free.call(q6):
						add.call("dumpster", q6, _yaw(l2.ax))
				if not did_phone:
					add.call("payphone", l2.at(l2.w * 0.3, front), _yaw(-l2.az))
					did_phone = true
				elif r.randf() < 0.3:
					add.call("road_newspaper_box", l2.at(-l2.w * 0.3, front), _yaw(l2.az))
				if r.randf() < 0.4:
					add.call("trash_bag" if r.randf() < 0.6 else "trash_pile", l2.at(r.randf_range(-0.4, 0.4) * l2.w, front), r.randf_range(-180.0, 180.0))
			"civic":
				if l2.street >= 0:
					add.call("bench_park", l2.at(-4.0, front), _yaw(l2.az))
				if not did_box:
					add.call("civic_collection_mailbox", l2.at(5.0, front), _yaw(l2.ax))
					did_box = true
			"residential", "rural":
				if l2.street >= 0 and l2.side != 0:
					var q7: Vector2 = l2.at((l2.w * 0.5 - 2.5) * (1.0 if r.randf() < 0.5 else -1.0), l2.d * 0.5 + lots.verge * 0.55)
					if free.call(q7):
						add.call("mailbox_rural", q7, _yaw(-l2.az))
	# The square: benches facing in along three sides, lamps at its corners, a collection box.
	if plaza != null:
		for k2: int in 3:
			var where: Vector2 = [Vector2(0.0, -0.5), Vector2(-0.5, 0.0), Vector2(0.5, 0.0)][k2]
			var bp: Vector2 = plaza.at(where.x * (plaza.w - 3.0), where.y * (plaza.d - 3.0))
			add.call("bench_park", bp, _yaw(plaza.c - bp))
		for k3: int in 4:
			add.call("street_lamp", plaza.at((0.5 if k3 % 2 == 0 else -0.5) * (plaza.w - 1.5), (0.5 if k3 < 2 else -0.5) * (plaza.d - 1.5)), _yaw(plaza.az if k3 < 2 else -plaza.az))
		if not did_box:
			add.call("civic_collection_mailbox", plaza.at(plaza.w * 0.5 - 4.0, plaza.d * 0.5 - 1.0), _yaw(plaza.az))
	# Wrecks where they stopped: in the lanes of the streets, a few slewed across.
	var wr: Array = kd.get("wrecks", [1, 3])
	var lanes: Array[int] = []
	for si5: int in net.streets.size():
		if net.streets[si5].cls in ["arterial", "street", "lane"]:
			lanes.append(si5)
	for wi: int in r.randi_range(int(wr[0]), int(wr[1])):
		if lanes.is_empty():
			break
		var st5: Streets.Street = net.streets[lanes[r.randi() % lanes.size()]]
		var s6: float = r.randf_range(10.0, maxf(10.0, st5.length() - 10.0))
		var p6: Vector2 = st5.line.point_at(s6)
		if p6.distance_to(center) > radius:
			continue
		var t6: Vector2 = st5.line.tangent_at(s6)
		var rot: float = _yaw(t6) + (180.0 if r.randf() < 0.5 else 0.0) + r.randf_range(-14.0, 14.0)
		if r.randf() < 0.25:
			rot += r.randf_range(-60.0, 60.0)
		add.call("car_sedan_wreck" if r.randf() < 0.7 else "pickup_wreck", p6 + Vector2(-t6.y, t6.x) * r.randf_range(-0.4, 0.4) * st5.half(), rot)
	return out


static func _near_arc(arcs: Array, s: float, d: float) -> bool:
	for a: Variant in arcs:
		if absf(float(a) - s) < d:
			return true
	return false


## Degrees, lot_xf convention: the yaw whose local +Z points along v.
static func _yaw(v: Vector2) -> float:
	return rad_to_deg(atan2(v.x, v.y))


# --- Output --------------------------------------------------------------------------------------

static func _stats(net: Streets, lots: Lots, quota: Dictionary, target: int, candidates: int) -> Dictionary:
	var zones: Dictionary = {}
	var rings: Dictionary = {}
	var n: int = 0
	for l: Lots.Lot in lots.lots:
		if l.zone == "plaza":
			continue
		n += 1
		zones[l.zone] = int(zones.get(l.zone, 0)) + 1
		rings[l.ring] = int(rings.get(l.ring, 0)) + 1
	var cul: int = 0
	var back: int = 0
	var length: float = 0.0
	for st: Streets.Street in net.streets:
		if st.cls == "bulb":
			cul += 1
		elif st.cls == "back_lane":
			back += 1
		if st.gen >= 1 and st.cls != "bulb":
			length += st.length()
	return {"lots": n, "zones": zones, "rings": rings, "quota": quota, "lot_target": target, "lot_candidates": candidates, "plaza": lots.lots.any(func(l: Lots.Lot) -> bool: return l.zone == "plaza"),
		"side_streets": net.side_count, "loops": net.loops, "culdesacs": cul, "back_lanes": back, "street_length": snappedf(length, 1.0),
		"junctions": net.junctions.size()}


static func _output(site: Dictionary, net: Streets, lots: Lots, plaza: Lots.Lot, fixtures: Array, blocks: Array[Dictionary], stats: Dictionary) -> Dictionary:
	var out_lots: Array = []
	var bb := Rect2(net.center, Vector2.ZERO)
	for l: Lots.Lot in lots.lots:
		if l.zone == "plaza":
			continue
		var street: String = "plaza" if l.street < 0 else net.streets[l.street].id
		out_lots.append({"id": l.id, "frame": frame_of(l), "poly": _arr(l.poly), "zoning": Array(l.zoning), "street": street, "ring": l.ring,
			"y": snappedf(l.y, 0.01)})
		for p: Vector2 in l.poly:
			bb = bb.expand(p)
	var roads: Array = []
	for st: Streets.Street in net.streets:
		if st.gen < 1:
			continue
		roads.append({"id": st.id, "class": st.cls, "points": _arr(st.ctrl), "width": st.width, "surface": st.surface, "shoulder": st.shoulder,
			"markings": false})
		for p2: Vector2 in st.ctrl:
			bb = bb.expand(p2)
	var junctions: Array = []
	for ji: int in net.junctions.size():
		var j: Streets.Junction = net.junctions[ji]
		var legs: int = 0
		var ids: Array = []
		for si: int in j.streets:
			var st2: Streets.Street = net.streets[si]
			ids.append(st2.id)
			var arc: float = st2.line.closest(j.pos).y
			legs += 1 if arc < 1.0 or arc > st2.length() - 1.0 else 2
		junctions.append({"id": "j_%d" % ji, "pos": _arr(PackedVector2Array([j.pos]))[0], "streets": ids,
			"kind": "cross" if legs >= 4 else ("tee" if legs == 3 else ("bend" if legs == 2 else "end"))})
	var out_blocks: Array = []
	for bi: int in blocks.size():
		out_blocks.append({"id": "b_%d" % bi, "poly": _arr(blocks[bi]["poly"]), "area": snappedf(float(blocks[bi]["area"]), 1.0)})
	var plaza_out: Dictionary = {}
	if plaza != null:
		plaza_out = {"frame": frame_of(plaza), "y": snappedf(plaza.y, 0.01)}
		for p3: Vector2 in plaza.corners():
			bb = bb.expand(p3)
	bb = bb.grow(4.0)
	return {"layout": "organic", "kind": str(site.get("kind", "village")), "name": str(site.get("name", "")), "id": str(site.get("id", "town")),
		"center": _arr(PackedVector2Array([net.center]))[0], "radius": net.radius,
		"size": [int(ceil(bb.size.x)), int(ceil(bb.size.y))], "bounds": [snappedf(bb.position.x, 0.1), snappedf(bb.position.y, 0.1), ceilf(bb.size.x), ceilf(bb.size.y)],
		"tier_range": [1, 2], "lots": out_lots, "roads": roads, "fixtures": fixtures, "plaza": plaza_out, "junctions": junctions,
		"blocks": out_blocks, "stats": stats}


## [cx, cz, w, d, yaw degrees] of a lot.
static func frame_of(l: Lots.Lot) -> Array:
	return [snappedf(l.c.x, 0.1), snappedf(l.c.y, 0.1), snappedf(l.w, 0.1), snappedf(l.d, 0.1), snappedf(rad_to_deg(l.yaw), 0.1)]


static func _arr(pts: PackedVector2Array) -> Array:
	var out: Array = []
	for p: Vector2 in pts:
		out.append([snappedf(p.x, 0.1), snappedf(p.y, 0.1)])
	return out


static func _v2(v: Variant) -> Vector2:
	if v is Vector2:
		return v
	return Vector2(float(v[0]), float(v[1]))


static func _rng(seed: int, sid: String, stream: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.derive_seed(seed, "town:%s:%s" % [sid, stream])
	return r
