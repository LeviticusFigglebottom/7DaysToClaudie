class_name RwgStreets
extends RefCounted
## The streets of an organic town (ADR-0040, docs/RWG_V2_PLAN.md §3.5): the arterials the town is
## given, side streets grown from them by agents that weigh grade, turning and crowding (so they
## bend with the land instead of ruling a grid over it), T-junctions and loops where an agent runs
## into another street, cul-de-sac bulbs on long dead ends, second-generation branches, core back
## lanes, the junctions and the blocks (the faces of the street graph). Plain data built by pure
## functions of the inputs and an RNG: no scene tree, no autoloads, safe on a worker thread.
##
## Geometry is world XZ as Vector2 (x east, y = z south). A street's `ctrl` points are what the town
## writes out; its `line` is `Polyline2.from_array(ctrl)`, the very Catmull-Rom centre line the
## composer grades and paints, so every distance below is measured against the road the game will
## build. Side +1 of a street is the left of its travel direction as `Polyline2.closest` reports it:
## the normal `Vector2(-t.y, t.x)`.

## Agent headings tried each step, relative to the current one (degrees), straight ahead first.
const TURNS: Array[float] = [0.0, 6.0, -6.0, 12.0, -12.0, 24.0, -24.0, 36.0, -36.0]
## Street classes a town draws itself (arterials come from the world's roads).
const CLASSES: Dictionary = {
	"street": {"width": 6.0, "shoulder": 0.8, "surface": "asphalt"},
	"lane": {"width": 5.0, "shoulder": 0.6, "surface": "gravel"},
	"back_lane": {"width": 4.5, "shoulder": 0.5, "surface": "gravel"},
	"bulb": {"width": 18.0, "shoulder": 0.6, "surface": "asphalt"},
}


## The land a town is planned on: the world's reference ground and its distance to water, read
## through callables and sampled lazily on a grid around the town (heights every 4 m, water every
## 8 m), interpolated bilinearly; outside the grid the callables are asked directly. Sampling is a
## pure function of position, so the plan does not depend on the order of the queries.
class Ground:
	var height_fn: Callable
	var water_fn: Callable
	var slope_fn: Callable
	var o := Vector2.ZERO
	var cell: float = 4.0
	var cols: int = 0
	var hs := PackedFloat32Array()
	var wcell: float = 8.0
	var wcols: int = 0
	var ws := PackedFloat32Array()
	var calls: int = 0

	func _init(world: Dictionary, center: Vector2, reach: float) -> void:
		if world.get("height") is Callable:
			height_fn = world["height"]
		if world.get("water") is Callable:
			water_fn = world["water"]
		if world.get("slope") is Callable:
			slope_fn = world["slope"]
		o = center - Vector2(reach, reach)
		cols = int(ceil(2.0 * reach / cell)) + 2
		hs.resize(cols * cols)
		hs.fill(NAN)
		wcols = int(ceil(2.0 * reach / wcell)) + 2
		ws.resize(wcols * wcols)
		ws.fill(NAN)

	## Reference ground height at p.
	func h(p: Vector2) -> float:
		var gx: float = (p.x - o.x) / cell
		var gz: float = (p.y - o.y) / cell
		if gx < 0.0 or gz < 0.0 or gx >= cols - 1.0 or gz >= cols - 1.0:
			calls += 1
			return float(height_fn.call(p.x, p.y)) if height_fn.is_valid() else 0.0
		var i: int = int(gx)
		var j: int = int(gz)
		var fx: float = gx - i
		var fz: float = gz - j
		var k: int = j * cols + i
		var a: float = hs[k]
		if is_nan(a):
			a = _hfill(k)
		var b: float = hs[k + 1]
		if is_nan(b):
			b = _hfill(k + 1)
		var c: float = hs[k + cols]
		if is_nan(c):
			c = _hfill(k + cols)
		var e: float = hs[k + cols + 1]
		if is_nan(e):
			e = _hfill(k + cols + 1)
		return lerpf(lerpf(a, b, fx), lerpf(c, e, fx), fz)

	func _hfill(k: int) -> float:
		var v: float = 0.0
		if height_fn.is_valid():
			calls += 1
			v = float(height_fn.call(o.x + (k % cols) * cell, o.y + (k / cols) * cell))
		hs[k] = v
		return v

	## Distance from p to the nearest water (m; negative in it). Far from any water without a callable.
	func water(p: Vector2) -> float:
		if not water_fn.is_valid():
			return 1.0e9
		var gx: float = (p.x - o.x) / wcell
		var gz: float = (p.y - o.y) / wcell
		if gx < 0.0 or gz < 0.0 or gx >= wcols - 1.0 or gz >= wcols - 1.0:
			calls += 1
			return float(water_fn.call(p.x, p.y))
		var i: int = int(gx)
		var j: int = int(gz)
		var fx: float = gx - i
		var fz: float = gz - j
		var k: int = j * wcols + i
		var a: float = ws[k]
		if is_nan(a):
			a = _wfill(k)
		var b: float = ws[k + 1]
		if is_nan(b):
			b = _wfill(k + 1)
		var c: float = ws[k + wcols]
		if is_nan(c):
			c = _wfill(k + wcols)
		var e: float = ws[k + wcols + 1]
		if is_nan(e):
			e = _wfill(k + wcols + 1)
		return lerpf(lerpf(a, b, fx), lerpf(c, e, fx), fz)

	func _wfill(k: int) -> float:
		calls += 1
		var v: float = float(water_fn.call(o.x + (k % wcols) * wcell, o.y + (k / wcols) * wcell))
		ws[k] = v
		return v

	## Ground slope (rise over run) at p: the world's own when given, else central differences.
	func slope(p: Vector2) -> float:
		if slope_fn.is_valid():
			return float(slope_fn.call(p.x, p.y))
		var dx: float = h(p + Vector2(4.0, 0.0)) - h(p - Vector2(4.0, 0.0))
		var dz: float = h(p + Vector2(0.0, 4.0)) - h(p - Vector2(0.0, 4.0))
		return sqrt(dx * dx + dz * dz) / 8.0


## One street: its control points, the composer's centre line through them, class and links.
class Street:
	var id: String = ""
	## "arterial" (a world road), "street", "lane", "back_lane" or "bulb" (a cul-de-sac's turning circle).
	var cls: String = "street"
	var width: float = 6.0
	var shoulder: float = 0.8
	var surface: String = "asphalt"
	var markings: bool = false
	var ctrl := PackedVector2Array()
	var line: Polyline2 = null
	## 0 arterial, 1 side street, 2 second-generation branch, 3 back lane / bulb.
	var gen: int = 1
	var parent: int = -1
	var dead_end: bool = false
	var snapped: bool = false
	var at_edge: bool = false
	## Index of its cul-de-sac bulb piece (-1: none).
	var bulb: int = -1
	## Junctions along it: [arc, junction index, sides] (sides: 1 = side +1, 2 = side -1, 3 = both).
	var stations: Array = []

	func half() -> float:
		return width * 0.5

	func length() -> float:
		return line.total_length if line != null else 0.0


## Where streets meet.
class Junction:
	var pos := Vector2.ZERO
	var streets := PackedInt32Array()


var ground: Ground
var center := Vector2.ZERO
var radius: float = 300.0
var core: float = 100.0
var streets: Array[Street] = []
var junctions: Array[Junction] = []
## Convex polygons side streets keep out of (the plaza and its civic yard).
var obstacles: Array[PackedVector2Array] = []
## Loops closed by agents (T-junctions onto other streets) and side streets grown.
var loops: int = 0
var side_count: int = 0
## Total length of the side streets (m).
var length_total: float = 0.0
var cfg: Dictionary = {}
var kd: Dictionary = {}

# The segment index: every piece of every street's centre line in 32 m cells.
var seg_st := PackedInt32Array()
var seg_a := PackedVector2Array()
var seg_b := PackedVector2Array()
var seg_s := PackedFloat32Array()
var _cells: Array = []
var _g0 := Vector2.ZERO
var _gcell: float = 32.0
var _gcols: int = 0
var _stamp := PackedInt32Array()
var _stamp_n: int = 0

# Tuning, read once in setup().
var _step: float = 12.0
var _grade_k: float = 40.0
var _turn_k: float = 0.6
var _straight_k: float = 0.8
var _crowd_k: float = 0.35
var _crowd_reach: float = 45.0
var _snap: float = 16.0
var _snap_angle: float = 35.0
var _parallel: float = 60.0
var _parallel_angle: float = 25.0
var _keep_out: float = 30.0
var _water_stop: float = 15.0
var _max_grade: float = 0.11
var _max_turn_cos: float = -0.17
var _min_len: float = 40.0
var _wander: float = 4.0
var _wander_max: float = 28.0
var _aim_k: float = 0.35
var _junction_gap: float = 30.0
var _merge: float = 14.0
var _snap_bonus: float = 0.6
var _budget: float = 1600.0
var _max_loops: int = 4


## Prepares an empty network around a town: `reach` is the half size of the area the index covers.
func setup(p_ground: Ground, p_center: Vector2, p_radius: float, p_kd: Dictionary, p_cfg: Dictionary, reach: float) -> void:
	ground = p_ground
	center = p_center
	radius = p_radius
	kd = p_kd
	cfg = p_cfg
	core = float(kd.get("core", 80.0))
	_g0 = center - Vector2(reach, reach)
	_gcols = int(ceil(2.0 * reach / _gcell)) + 1
	_cells.resize(_gcols * _gcols)
	for i: int in _cells.size():
		_cells[i] = []
	_step = float(cfg.get("step", 12.0))
	_grade_k = float(cfg.get("grade_cost", 40.0))
	_turn_k = float(cfg.get("turn_cost", 0.6))
	_straight_k = float(cfg.get("core_straight_cost", 0.8))
	_crowd_k = float(cfg.get("crowd_cost", 0.35))
	_crowd_reach = float(cfg.get("crowd_reach", 45.0))
	_snap = float(cfg.get("snap", 16.0))
	_snap_angle = float(cfg.get("snap_angle", 35.0))
	_parallel = float(cfg.get("parallel", 60.0))
	_parallel_angle = float(cfg.get("parallel_angle", 25.0))
	_keep_out = float(cfg.get("keep_out", 30.0))
	_water_stop = float(cfg.get("water_stop", 15.0))
	_max_grade = float(cfg.get("max_grade", 0.11))
	_max_turn_cos = cos(deg_to_rad(float(cfg.get("max_turn", 100.0))))
	_min_len = float(cfg.get("min_length", 40.0))
	_wander = float(cfg.get("wander", 4.0))
	_wander_max = float(cfg.get("wander_max", 28.0))
	_aim_k = float(cfg.get("aim_cost", 0.35))
	_junction_gap = float(cfg.get("junction_spacing", 30.0))
	_merge = float(cfg.get("junction_merge", 14.0))
	_snap_bonus = float(cfg.get("snap_bonus", 0.6))
	_budget = float(kd.get("street_budget", 1600.0))
	_max_loops = int((kd.get("loops", [0, 4]) as Array)[1])


# --- Streets and the index ---------------------------------------------------------------------

## Adds a world road through the town. `a`: {id, points: [[x, z], ...] | PackedVector2Array, width,
## shoulder, surface, markings}. Returns its street index.
func add_arterial(a: Dictionary) -> int:
	var st := Street.new()
	st.id = str(a.get("id", "arterial_%d" % streets.size()))
	st.cls = "arterial"
	st.gen = 0
	st.width = float(a.get("width", 8.0))
	st.shoulder = float(a.get("shoulder", 1.5))
	st.surface = str(a.get("surface", "asphalt"))
	st.markings = bool(a.get("markings", true))
	st.ctrl = to_points(a.get("points", []))
	if st.ctrl.size() < 2:
		return -1
	st.line = Polyline2.from_array(Array(st.ctrl))
	return add(st)


## Registers a street (its line already built) and returns its index.
func add(st: Street) -> int:
	var si: int = streets.size()
	streets.append(st)
	_index(si)
	return si


## Puts street si's centre-line pieces in the segment index.
func _index(si: int) -> void:
	var st: Street = streets[si]
	var pts: PackedVector2Array = st.line.points
	var lens: PackedFloat32Array = st.line.lengths
	var area := Rect2(_g0, Vector2(_gcols, _gcols) * _gcell)
	for k: int in pts.size() - 1:
		var a: Vector2 = pts[k]
		var b: Vector2 = pts[k + 1]
		var sid: int = seg_st.size()
		seg_st.append(si)
		seg_a.append(a)
		seg_b.append(b)
		seg_s.append(lens[k])
		_stamp.append(0)
		var bb := Rect2(a, Vector2.ZERO).expand(b)
		if not bb.grow(1.0).intersects(area):
			continue
		var i0: int = clampi(int(floor((bb.position.x - _g0.x) / _gcell)), 0, _gcols - 1)
		var i1: int = clampi(int(floor((bb.end.x - _g0.x) / _gcell)), 0, _gcols - 1)
		var j0: int = clampi(int(floor((bb.position.y - _g0.y) / _gcell)), 0, _gcols - 1)
		var j1: int = clampi(int(floor((bb.end.y - _g0.y) / _gcell)), 0, _gcols - 1)
		for j: int in range(j0, j1 + 1):
			for i: int in range(i0, i1 + 1):
				(_cells[j * _gcols + i] as Array).append(sid)


## Segment ids within the square of half size r around p (each once).
func near(p: Vector2, r: float) -> PackedInt32Array:
	_stamp_n += 1
	var out := PackedInt32Array()
	var i0: int = int(floor((p.x - r - _g0.x) / _gcell))
	var i1: int = int(floor((p.x + r - _g0.x) / _gcell))
	var j0: int = int(floor((p.y - r - _g0.y) / _gcell))
	var j1: int = int(floor((p.y + r - _g0.y) / _gcell))
	if i1 < 0 or j1 < 0 or i0 >= _gcols or j0 >= _gcols:
		return out
	i0 = maxi(i0, 0)
	j0 = maxi(j0, 0)
	i1 = mini(i1, _gcols - 1)
	j1 = mini(j1, _gcols - 1)
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			for sid: int in _cells[j * _gcols + i]:
				if _stamp[sid] != _stamp_n:
					_stamp[sid] = _stamp_n
					out.append(sid)
	return out


## Distance from p to the nearest street centre line other than `skip` (INF beyond r).
func street_distance(p: Vector2, r: float, skip: int = -1) -> float:
	var best: float = INF
	for sid: int in near(p, r):
		if seg_st[sid] == skip:
			continue
		best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, seg_a[sid], seg_b[sid])))
	return best


## The junction at p (an existing one within `merge` m, else a new one).
func junction_at(p: Vector2, merge: float = 1.5) -> int:
	for ji: int in junctions.size():
		if junctions[ji].pos.distance_to(p) <= merge:
			return ji
	var j := Junction.new()
	j.pos = p
	junctions.append(j)
	return junctions.size() - 1


## Records that street si passes junction ji at arc `arc`, blocking `sides` (1: +1, 2: -1, 3: both).
func link(ji: int, si: int, arc: float, sides: int) -> void:
	var j: Junction = junctions[ji]
	if not j.streets.has(si):
		j.streets.append(si)
	var st: Street = streets[si]
	for stn: Array in st.stations:
		if int(stn[1]) == ji:
			stn[2] = int(stn[2]) | sides
			return
	st.stations.append([arc, ji, sides])


static func side_bit(side: int) -> int:
	return 1 if side > 0 else 2


## Where the arterials cross or meet each other: X and T junctions on both.
func arterial_junctions() -> void:
	var reach: float = (_gcols - 1) * _gcell * 0.5
	var art: Array[int] = []
	for si: int in streets.size():
		if streets[si].cls == "arterial":
			art.append(si)
	for ia: int in art.size():
		for ib: int in range(ia + 1, art.size()):
			var la: Polyline2 = streets[art[ia]].line
			var lb: Polyline2 = streets[art[ib]].line
			for ka: int in la.points.size() - 1:
				var a0: Vector2 = la.points[ka]
				var a1: Vector2 = la.points[ka + 1]
				if a0.distance_to(center) > reach and a1.distance_to(center) > reach:
					continue
				for kb: int in lb.points.size() - 1:
					var b0: Vector2 = lb.points[kb]
					var b1: Vector2 = lb.points[kb + 1]
					var x: Variant = Geometry2D.segment_intersects_segment(a0, a1, b0, b1)
					if x == null:
						continue
					var ji: int = junction_at(x, 8.0)
					link(ji, art[ia], la.lengths[ka] + a0.distance_to(x), 3)
					link(ji, art[ib], lb.lengths[kb] + b0.distance_to(x), 3)
	# A road that ends on another (the world network's T-junctions).
	for si2: int in art:
		var st: Street = streets[si2]
		for end_i: int in 2:
			var e: Vector2 = st.line.points[0] if end_i == 0 else st.line.points[st.line.points.size() - 1]
			if e.distance_to(center) > reach:
				continue
			for so: int in art:
				if so == si2:
					continue
				var q: Vector3 = streets[so].line.closest(e)
				if q.x < 3.0:
					var ji2: int = junction_at(e, 8.0)
					link(ji2, si2, 0.0 if end_i == 0 else st.length(), 3)
					var t: Vector2 = streets[so].line.tangent_at(q.y)
					var away: Vector2 = st.line.point_at(12.0 if end_i == 0 else st.length() - 12.0) - e
					link(ji2, so, q.y, side_bit(1 if t.cross(away) >= 0.0 else -1))


# --- Growth --------------------------------------------------------------------------------------

## Grows the side streets (§3.5): seeds along the arterials, nearest the centre first, each grown to
## its end by an agent; second-generation branches join the queue as their parents finish. Stops at
## the class's side-street count or street budget. Then closes loops while there are too few,
## and gives long dead ends their cul-de-sac bulbs.
func grow(r: RandomNumberGenerator) -> void:
	var want: Array = kd.get("side_streets", [0, 2])
	var target: int = r.randi_range(int(want[0]), int(want[1]))
	var queue: Array[Dictionary] = _arterial_seeds(r)
	queue.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["prio"]) < float(b["prio"]))
	var branch_chance: float = float(kd.get("branch_chance", 0.0))
	var bl: Array = cfg.get("branch_length", [60.0, 140.0])
	var ba: Array = cfg.get("branch_angle", [75.0, 105.0])
	while not queue.is_empty() and side_count < target and length_total < _budget - _min_len:
		var sd: Dictionary = queue.pop_front()
		var si: int = grow_one(sd, r)
		if si < 0:
			continue
		var st: Street = streets[si]
		if st.gen != 1 or st.length() < 100.0 or r.randf() >= branch_chance:
			continue
		var n_br: int = 1 if st.length() < 220.0 else 2
		for b: int in n_br:
			var sb: float = r.randf_range(40.0, st.length() - 40.0) if n_br == 1 else (st.length() * (0.3 + 0.4 * b) + r.randf_range(-15.0, 15.0))
			var bp: Vector2 = st.line.point_at(sb)
			var nb: Dictionary = {"from": si, "s": sb, "side": 1 if r.randf() < 0.5 else -1, "angle": r.randf_range(float(ba[0]), float(ba[1])),
				"gen": 2, "budget": r.randf_range(float(bl[0]), float(bl[1])), "prio": bp.distance_to(center) / radius + r.randf_range(0.1, 0.5), "cls": _class_at(bp),
				"seek": true}
			var at: int = queue.size()
			for qi: int in queue.size():
				if float(queue[qi]["prio"]) > float(nb["prio"]):
					at = qi
					break
			queue.insert(at, nb)
	var lp: Array = kd.get("loops", [0, 0])
	if loops < int(lp[0]):
		_connect_dead_ends(r, int(lp[0]))


## Seeds along each arterial inside the town, from the centre out both ways, alternating sides;
## core seeds branch square (`grid_bias`) and some cross the arterial (two streets from one point).
func _arterial_seeds(r: RandomNumberGenerator) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var sp: Array = kd.get("seed_spacing", [[55.0, 75.0], [70.0, 100.0], [90.0, 120.0]])
	var reach: float = radius * float(kd.get("seed_reach", 0.85))
	var sl: Array = kd.get("street_length", cfg.get("length", [80.0, 320.0]))
	var ba: Array = cfg.get("branch_angle", [75.0, 105.0])
	var cross_chance: float = float(kd.get("cross_chance", 0.0))
	var grid_bias: bool = bool(kd.get("grid_bias", true))
	for ai: int in streets.size():
		var st: Street = streets[ai]
		if st.cls != "arterial":
			continue
		var line: Polyline2 = st.line
		var sc: float = line.closest(center).y
		for dir: int in [1, -1]:
			var side: int = 1 if r.randf() < 0.5 else -1
			var s: float = sc + dir * r.randf_range(20.0, 45.0)
			while s > 20.0 and s < line.total_length - 20.0:
				var p: Vector2 = line.point_at(s)
				var dist: float = p.distance_to(center)
				if dist > reach:
					break
				var ring: int = 0 if dist < core else (1 if dist < radius * 0.6 else 2)
				var in_core: bool = ring == 0 and grid_bias
				var angle: float = 90.0 + r.randf_range(-4.0, 4.0) if in_core else r.randf_range(float(ba[0]), float(ba[1]))
				var cls: String = _class_at(p)
				# Core seeds first, the rest mixed across the rings, so the side-street count reaches
				# out to the edge instead of being spent round the centre.
				var prio: float = dist / radius + (0.0 if ring == 0 else r.randf_range(0.0, float(kd.get("seed_mix", 0.6))))
				out.append({"from": ai, "s": s, "side": side, "angle": angle, "gen": 1, "budget": r.randf_range(float(sl[0]), float(sl[1])),
					"prio": prio, "cls": cls, "seek": not in_core or ground.slope(p) > 0.04})
				if ring == 0 and r.randf() < cross_chance:
					out.append({"from": ai, "s": s, "side": -side, "angle": 180.0 - angle, "gen": 1,
						"budget": r.randf_range(float(sl[0]), float(sl[1])), "prio": prio + 0.001, "cls": cls})
				var spr: Array = sp[ring]
				s += dir * r.randf_range(float(spr[0]), float(spr[1]))
				side = -side
	return out


## The class of a street started at p: lanes in hamlets and out past 3/4 of the radius.
func _class_at(p: Vector2) -> String:
	if str(kd.get("street_class", "street")) == "lane" or p.distance_to(center) > radius * float(cfg.get("lane_from", 0.75)):
		return "lane"
	return "street"


## Grows one street from a seed {from, s, side, angle, gen, budget, cls}; returns its index, or -1
## when it came to nothing (no room to start, or a dead end shorter than `min_length`).
func grow_one(sd: Dictionary, r: RandomNumberGenerator) -> int:
	var pi: int = int(sd["from"])
	var par: Street = streets[pi]
	var s0: float = float(sd["s"])
	var side: int = int(sd["side"])
	if s0 < 15.0 or s0 > par.length() - 15.0:
		return -1
	var p0: Vector2 = par.line.point_at(s0)
	# Junctions keep their distance along a street, except a crossing (two streets from one point).
	var ignore: Dictionary = {pi: true}
	for stn: Array in par.stations:
		var gap: float = absf(float(stn[0]) - s0)
		if gap < 1.5:
			for so: int in junctions[int(stn[1])].streets:
				ignore[so] = true
		elif gap < _junction_gap:
			return -1
	var tan: Vector2 = par.line.tangent_at(s0)
	var angle: float = float(sd["angle"])
	if bool(sd.get("seek", false)):
		# Leave at whichever angle of the branching range climbs least over the first 36 m.
		var ba: Array = cfg.get("branch_angle", [75.0, 105.0])
		var h0: float = ground.h(p0)
		var best_g: float = INF
		for k2: int in 5:
			var a2: float = lerpf(float(ba[0]), float(ba[1]), k2 / 4.0)
			var g2: float = absf(ground.h(p0 + tan.rotated(deg_to_rad(a2) * side) * 36.0) - h0) + absf(a2 - angle) * 0.01
			if g2 < best_g:
				best_g = g2
				angle = a2
	var d: Vector2 = tan.rotated(deg_to_rad(angle) * side)
	var d0: Vector2 = d
	var pts := PackedVector2Array([p0])
	var p: Vector2 = p0
	var hp: float = ground.h(p0)
	var length: float = 0.0
	var budget: float = float(sd["budget"])
	var wander: float = 0.0
	var snap: Dictionary = {}
	var at_edge: bool = false
	var straight: float = _straight_k if p0.distance_to(center) < core and bool(kd.get("grid_bias", true)) else 0.0
	var k: int = 0
	var cos_turn: float = _max_turn_cos
	var look: float = maxf(_parallel, _crowd_reach) + _step + 2.0
	while length < budget and length_total + length < _budget:
		# The heading the street drifts towards: a slow random walk round its first heading (none in
		# a gridded core), so streets on open level ground still bend a little.
		if straight <= 0.0:
			wander = clampf(wander + r.randf_range(-_wander, _wander), -_wander_max, _wander_max)
		var aim: Vector2 = d0.rotated(deg_to_rad(wander))
		# On a slope the land, not the drift or the core's grid, decides where the street goes.
		var flat: float = clampf(1.0 - ground.slope(p) / 0.06, 0.0, 1.0)
		var aim_k: float = _aim_k * flat
		var straight_k: float = straight * flat
		k += 1
		var near_ids: PackedInt32Array = near(p, look)
		var best: float = INF
		var bq := Vector2.ZERO
		var bc := Vector2.ZERO
		var bh: float = 0.0
		var bsnap: Dictionary = {}
		for turn: float in TURNS:
			var c: Vector2 = d.rotated(deg_to_rad(turn))
			if c.dot(d0) < cos_turn:
				continue
			var q: Vector2 = p + c * _step
			if q.distance_to(center) > radius:
				at_edge = true
				continue
			var hq: float = ground.h(q)
			var g: float = absf(hq - hp) / _step
			if g > _max_grade:
				continue
			if ground.water(q) < _water_stop:
				continue
			if _blocked(p, q) or _curls(pts, q):
				continue
			var pr: Array = _probe(p, q, c, near_ids, ignore, length, hp)
			if not bool(pr[0]):
				continue
			var cost: float = _grade_k * g + _turn_k * absf(turn) / 12.0 + aim_k * rad_to_deg(acos(clampf(c.dot(aim), -1.0, 1.0))) / 12.0 \
				+ float(pr[2]) + straight_k * absf(turn) / 12.0
			var sn: Dictionary = pr[1]
			if not sn.is_empty():
				cost -= _snap_bonus
			if cost < best:
				best = cost
				bq = q
				bc = c
				bh = hq
				bsnap = sn
		if best == INF:
			break
		if not bsnap.is_empty():
			snap = bsnap
			var sp: Vector2 = bsnap["point"]
			length += p.distance_to(sp)
			pts.append(sp)
			break
		pts.append(bq)
		length += _step
		p = bq
		hp = bh
		d = bc
	# A dead end too short to hold a lot, or a link too short to be a street, is no street.
	if length < (_min_len if snap.is_empty() else _min_len * 0.75):
		return -1
	var cls: String = str(sd.get("cls", "street"))
	var st := make_street(cls, pts)
	st.gen = int(sd.get("gen", 1))
	st.parent = pi
	st.at_edge = at_edge
	var si: int = add(st)
	st.id = "st_%d" % si
	var j0: int = junction_at(p0, 1.5)
	link(j0, pi, s0, side_bit(side))
	link(j0, si, 0.0, 3)
	if snap.is_empty():
		st.dead_end = true
	else:
		st.snapped = true
		var ts: int = int(snap["street"])
		var ja: int = int(snap["junction"]) if int(snap["junction"]) >= 0 else junction_at(snap["point"], 1.0)
		var tt: Vector2 = streets[ts].line.tangent_at(float(snap["arc"]))
		link(ja, ts, float(snap["arc"]), side_bit(1 if tt.cross(pts[pts.size() - 2] - (snap["point"] as Vector2)) >= 0.0 else -1))
		link(ja, si, st.length(), 3)
		loops += 1
	length_total += st.length()
	side_count += 1
	return si


## A street of a class from its control points (line built, not yet added).
func make_street(cls: String, pts: PackedVector2Array) -> Street:
	var st := Street.new()
	var spec: Dictionary = (cfg.get("classes", {}) as Dictionary).get(cls, CLASSES.get(cls, CLASSES["street"]))
	st.cls = cls
	st.width = float(spec.get("width", 6.0))
	st.shoulder = float(spec.get("shoulder", 0.8))
	st.surface = str(spec.get("surface", "asphalt"))
	st.markings = false
	st.ctrl = pts
	st.line = Polyline2.from_array(Array(pts))
	return st


## How a step p -> q in direction c fares against the streets already built:
## [ok, snap {street, point, arc, junction} or {}, crowding cost]. A step crossing a street, or
## ending within `snap` m of one at `snap_angle` or more, joins it (a T-junction); nearer at a
## shallower angle, or running beside one within `parallel` m at under `parallel_angle`, is refused.
func _probe(p: Vector2, q: Vector2, c: Vector2, near_ids: PackedInt32Array, ignore: Dictionary, length: float, hp: float, skip: int = -1) -> Array:
	var crowd: float = 0.0
	var snap: Dictionary = {}
	var snap_d: float = INF
	var loops_ok: bool = loops < _max_loops
	for sid: int in near_ids:
		var si: int = seg_st[sid]
		if si == skip or (length < 30.0 and ignore.has(si)):
			continue
		var cls: String = streets[si].cls
		var a: Vector2 = seg_a[sid]
		var b: Vector2 = seg_b[sid]
		var ab: Vector2 = b - a
		var l2: float = ab.length_squared()
		if l2 < 1.0e-6:
			continue
		var u: Vector2 = ab / sqrt(l2)
		var ang: float = rad_to_deg(acos(clampf(absf(c.dot(u)), 0.0, 1.0)))
		var x: Variant = Geometry2D.segment_intersects_segment(p, q, a, b)
		if x != null:
			if ang < _snap_angle or not loops_ok or cls == "bulb":
				return [false, {}, 0.0]
			var dx: float = p.distance_to(x)
			if dx < snap_d:
				snap_d = dx
				snap = {"street": si, "point": x, "arc": seg_s[sid] + a.distance_to(x), "junction": -1}
			continue
		var tf: float = (q - a).dot(ab) / l2
		var cp: Vector2 = a + ab * clampf(tf, 0.0, 1.0)
		var dist: float = q.distance_to(cp)
		if dist < _snap:
			if ang >= _snap_angle and loops_ok and cls != "bulb":
				var dc: float = p.distance_to(cp)
				if dc < snap_d:
					snap_d = dc
					snap = {"street": si, "point": cp, "arc": seg_s[sid] + a.distance_to(cp), "junction": -1}
			else:
				return [false, {}, 0.0]
		elif not loops_ok and dist < _keep_out and ang >= _snap_angle:
			return [false, {}, 0.0]
		if tf >= 0.0 and tf <= 1.0 and dist < _parallel and ang < _parallel_angle:
			return [false, {}, 0.0]
		if dist < _crowd_reach:
			var f: float = 1.0 - dist / _crowd_reach
			crowd += _crowd_k * f * f
	if snap.is_empty():
		return [true, snap, crowd]
	# Join an existing junction close by instead of making a second one beside it.
	var ts: Street = streets[int(snap["street"])]
	var arc: float = float(snap["arc"])
	for stn: Array in ts.stations:
		var gap: float = absf(float(stn[0]) - arc)
		if gap < _merge:
			snap["point"] = junctions[int(stn[1])].pos
			snap["arc"] = float(stn[0])
			snap["junction"] = int(stn[1])
			break
		elif gap < _junction_gap:
			return [false, {}, 0.0]
	var sp: Vector2 = snap["point"]
	var run: float = p.distance_to(sp)
	if run > 0.5 and absf(ground.h(sp) - hp) / run > _max_grade:
		return [false, {}, 0.0]
	return [true, snap, crowd]


func _blocked(p: Vector2, q: Vector2) -> bool:
	for poly: PackedVector2Array in obstacles:
		if point_in(q, poly):
			return true
		for k: int in poly.size():
			if Geometry2D.segment_intersects_segment(p, q, poly[k], poly[(k + 1) % poly.size()]) != null:
				return true
	return false


## A step that would bring the street back near its own earlier points.
func _curls(pts: PackedVector2Array, q: Vector2) -> bool:
	var gap: float = float(cfg.get("curl_gap", 36.0))
	for i: int in pts.size() - 3:
		if q.distance_to(pts[i]) < gap:
			return true
	return false


## Too few loops: dead ends near another street reach for it (an agent pulled towards the nearest
## street, which joins it at a T).
func _connect_dead_ends(r: RandomNumberGenerator, want: int) -> void:
	var cands: Array = []
	for si: int in streets.size():
		var st: Street = streets[si]
		if not st.dead_end or st.gen < 1 or st.cls == "bulb" or st.cls == "back_lane":
			continue
		var e: Vector2 = st.ctrl[st.ctrl.size() - 1]
		var dn: float = street_distance(e, 110.0, si)
		if dn < 110.0:
			cands.append([dn, si])
	cands.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	for cd: Array in cands:
		if loops >= want:
			break
		_extend_to_join(int(cd[1]), r)


## Extends dead-end street si until it joins another street (or gives up, leaving it as it was).
func _extend_to_join(si: int, r: RandomNumberGenerator) -> void:
	var st: Street = streets[si]
	var pts: PackedVector2Array = st.ctrl.duplicate()
	var p: Vector2 = pts[pts.size() - 1]
	var d: Vector2 = (p - pts[pts.size() - 2]).normalized()
	var hp: float = ground.h(p)
	var ignore: Dictionary = {si: true}
	var extra: float = 0.0
	var snap: Dictionary = {}
	while extra < 120.0:
		var near_ids: PackedInt32Array = near(p, _parallel + _step + 2.0)
		# Pull towards the nearest other street.
		var target := Vector2.INF
		var td: float = INF
		for sid: int in near(p, 130.0):
			if seg_st[sid] == si or streets[seg_st[sid]].cls == "bulb":
				continue
			var cp: Vector2 = Geometry2D.get_closest_point_to_segment(p, seg_a[sid], seg_b[sid])
			if p.distance_to(cp) < td:
				td = p.distance_to(cp)
				target = cp
		if target == Vector2.INF:
			return
		var pull: Vector2 = (target - p).normalized()
		var best: float = INF
		var bq := Vector2.ZERO
		var bc := Vector2.ZERO
		var bh: float = 0.0
		var bsnap: Dictionary = {}
		for turn: float in TURNS:
			var c: Vector2 = d.rotated(deg_to_rad(turn))
			var q: Vector2 = p + c * _step
			if q.distance_to(center) > radius:
				continue
			var hq: float = ground.h(q)
			var g: float = absf(hq - hp) / _step
			if g > _max_grade or ground.water(q) < _water_stop or _blocked(p, q) or _curls(pts, q):
				continue
			var pr: Array = _probe(p, q, c, near_ids, ignore, 100.0, hp, si)
			if not bool(pr[0]):
				continue
			var cost: float = _grade_k * g + _turn_k * absf(turn) / 12.0 + 3.0 * (1.0 - c.dot(pull))
			if not (pr[1] as Dictionary).is_empty():
				cost -= 2.0
			if cost < best:
				best = cost
				bq = q
				bc = c
				bh = hq
				bsnap = pr[1]
		if best == INF:
			return
		if not bsnap.is_empty():
			snap = bsnap
			pts.append(bsnap["point"] as Vector2)
			break
		pts.append(bq)
		extra += _step
		p = bq
		hp = bh
		d = bc
	if snap.is_empty():
		return
	# Rebuild the street with its extension (its index stays; its old segments are retired).
	_retire_segments(si)
	var old_len: float = st.length()
	st.ctrl = pts
	st.line = Polyline2.from_array(Array(pts))
	_index(si)
	st.dead_end = false
	st.snapped = true
	var ts: int = int(snap["street"])
	var ja: int = int(snap["junction"]) if int(snap["junction"]) >= 0 else junction_at(snap["point"], 1.0)
	var tt: Vector2 = streets[ts].line.tangent_at(float(snap["arc"]))
	link(ja, ts, float(snap["arc"]), side_bit(1 if tt.cross(pts[pts.size() - 2] - (snap["point"] as Vector2)) >= 0.0 else -1))
	link(ja, si, st.length(), 3)
	length_total += st.length() - old_len
	loops += 1


## Takes a street's segments out of the index (before its line changes).
func _retire_segments(si: int) -> void:
	for sid: int in seg_st.size():
		if seg_st[sid] == si:
			seg_st[sid] = -1
	for cell: Variant in _cells:
		var arr: Array = cell
		var i: int = arr.size() - 1
		while i >= 0:
			if seg_st[int(arr[i])] == -1:
				arr.remove_at(i)
			i -= 1


## Turning circles at the ends of long dead ends (§3.5): a road piece {points: [end, end + dir *
## 0.1], width 18} the composer draws as a disc. Interior dead ends first, the longest first, up to
## the class's cul-de-sac count.
func add_bulbs() -> void:
	var want: Array = kd.get("culdesacs", [0, 2])
	var min_len: float = float(cfg.get("bulb_min", 60.0))
	var cands: Array = []
	for si: int in streets.size():
		var st: Street = streets[si]
		if not st.dead_end or st.gen < 1 or st.cls == "back_lane" or st.length() < min_len:
			continue
		cands.append([(1.0 if st.at_edge else 0.0) * 10000.0 - st.length(), si])
	cands.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var made: int = 0
	for cd: Array in cands:
		if made >= int(want[1]):
			break
		var st2: Street = streets[int(cd[1])]
		var e: Vector2 = st2.ctrl[st2.ctrl.size() - 1]
		var dir: Vector2 = (e - st2.line.point_at(st2.length() - 3.0)).normalized()
		var bulb := make_street("bulb", PackedVector2Array([e, e + dir * 0.1]))
		var clear: bool = true
		for sid: int in near(e, 30.0):
			var so: Street = streets[seg_st[sid]]
			if seg_st[sid] == int(cd[1]):
				continue
			if e.distance_to(Geometry2D.get_closest_point_to_segment(e, seg_a[sid], seg_b[sid])) < bulb.half() + so.half() + so.shoulder + 3.0:
				clear = false
				break
		if not clear:
			continue
		bulb.gen = 3
		bulb.parent = int(cd[1])
		var bi: int = add(bulb)
		bulb.id = "st_%d" % bi
		st2.bulb = bi
		made += 1


## Back lanes behind the main street's core frontage (towns): between two side streets leaving the
## same side of an arterial, at `offset` m from it, so shops back onto a service lane.
func add_back_lanes(r: RandomNumberGenerator, offset: float) -> void:
	for ai: int in streets.size():
		var art: Street = streets[ai]
		if art.cls != "arterial":
			continue
		for side: int in [1, -1]:
			# Side streets leaving this side of the arterial inside the core, in arc order.
			var legs: Array = []
			for stn: Array in art.stations:
				if (int(stn[2]) & side_bit(side)) == 0:
					continue
				var arc: float = float(stn[0])
				if art.line.point_at(arc).distance_to(center) > core + 40.0:
					continue
				for so: int in junctions[int(stn[1])].streets:
					var s2: Street = streets[so]
					if s2.gen == 1 and s2.parent == ai and s2.line.points[0].distance_to(junctions[int(stn[1])].pos) < 2.0:
						var away: Vector2 = s2.line.point_at(minf(20.0, s2.length())) - junctions[int(stn[1])].pos
						if away.dot(Vector2(-art.line.tangent_at(arc).y, art.line.tangent_at(arc).x) * side) > 0.0:
							legs.append([arc, so])
			legs.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
			for li: int in legs.size() - 1:
				var sa: float = float(legs[li][0])
				var sb: float = float(legs[li + 1][0])
				if sb - sa < 50.0 or sb - sa > 220.0:
					continue
				_back_lane(ai, side, sa, sb, int(legs[li][1]), int(legs[li + 1][1]), offset)


func _back_lane(ai: int, side: int, sa: float, sb: float, la: int, lb: int, offset: float) -> void:
	var art: Street = streets[ai]
	var pa: Variant = _point_at_offset(streets[la], art, offset)
	var pb: Variant = _point_at_offset(streets[lb], art, offset)
	if pa == null or pb == null:
		return
	var pts := PackedVector2Array([pa])
	var s: float = sa + 18.0
	while s < sb - 18.0:
		var t: Vector2 = art.line.tangent_at(s)
		pts.append(art.line.point_at(s) + Vector2(-t.y, t.x) * side * offset)
		s += 24.0
	pts.append(pb)
	var lane := make_street("back_lane", pts)
	# Clear of every other street but its two legs, level enough, dry and outside the plaza.
	for k: int in pts.size() - 1:
		var g: float = absf(ground.h(pts[k + 1]) - ground.h(pts[k])) / maxf(1.0, pts[k].distance_to(pts[k + 1]))
		if g > _max_grade or _blocked(pts[k], pts[k + 1]) or ground.water(pts[k + 1]) < _water_stop:
			return
	for q: Vector2 in lane.line.points:
		for sid: int in near(q, 20.0):
			var so: int = seg_st[sid]
			if so == la or so == lb:
				continue
			var o: Street = streets[so]
			if q.distance_to(Geometry2D.get_closest_point_to_segment(q, seg_a[sid], seg_b[sid])) < o.half() + o.shoulder + lane.half() + 6.0:
				return
	lane.gen = 3
	lane.parent = la
	var li: int = add(lane)
	lane.id = "st_%d" % li
	for end_i: int in 2:
		var leg: int = la if end_i == 0 else lb
		var e: Vector2 = pts[0] if end_i == 0 else pts[pts.size() - 1]
		var q: Vector3 = streets[leg].line.closest(e)
		var ji: int = junction_at(e, 1.0)
		var tt: Vector2 = streets[leg].line.tangent_at(q.y)
		var inward: Vector2 = (pts[1] if end_i == 0 else pts[pts.size() - 2]) - e
		link(ji, leg, q.y, side_bit(1 if tt.cross(inward) >= 0.0 else -1))
		link(ji, li, 0.0 if end_i == 0 else lane.length(), 3)


## The first point along street `st` at least `offset` m from street `from`'s line.
func _point_at_offset(st: Street, from: Street, offset: float) -> Variant:
	var s: float = 0.0
	while s <= st.length():
		var p: Vector2 = st.line.point_at(s)
		if from.line.closest(p).x >= offset:
			return p
		s += 2.0
	return null


# --- Blocks: faces of the street graph ---------------------------------------------------------

## The blocks: bounded faces of the planar street graph (junctions and street ends as nodes, the
## street pieces between them as edges), walked by always taking the next edge round each node.
## Dead-end spurs are dropped from a face's outline. [{poly: PackedVector2Array (counter-clockwise
## in atan2's sense), area}] in face-walk order (deterministic).
func blocks(min_area: float = 300.0) -> Array[Dictionary]:
	var reach: float = radius + 60.0
	var nodes: Array[Vector2] = []
	var node_of_j: Dictionary = {}
	var edges: Array = []  # [a, b, PackedVector2Array]
	for si: int in streets.size():
		var st: Street = streets[si]
		if st.cls == "bulb":
			continue
		# Breakpoints: junction stations plus the line's ends (arterials clipped to the town).
		var marks: Array = []
		for stn: Array in st.stations:
			marks.append([float(stn[0]), int(stn[1])])
		marks.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
		var s_lo: float = 0.0
		var s_hi: float = st.length()
		if st.cls == "arterial":
			var sc: float = st.line.closest(center).y
			s_lo = sc
			while s_lo > 0.0 and st.line.point_at(s_lo).distance_to(center) < reach:
				s_lo -= 8.0
			s_lo = maxf(0.0, s_lo)
			s_hi = sc
			while s_hi < st.length() and st.line.point_at(s_hi).distance_to(center) < reach:
				s_hi += 8.0
			s_hi = minf(st.length(), s_hi)
		var seq: Array = []
		if marks.is_empty() or float(marks[0][0]) > s_lo + 0.5:
			seq.append([s_lo, -1])
		for m: Array in marks:
			if float(m[0]) >= s_lo - 0.5 and float(m[0]) <= s_hi + 0.5:
				seq.append(m)
		if seq.is_empty() or float(seq[seq.size() - 1][0]) < s_hi - 0.5:
			seq.append([s_hi, -1])
		var prev_node: int = -1
		var prev_s: float = 0.0
		for e: Array in seq:
			var node: int
			if int(e[1]) >= 0:
				if not node_of_j.has(int(e[1])):
					node_of_j[int(e[1])] = nodes.size()
					nodes.append(junctions[int(e[1])].pos)
				node = node_of_j[int(e[1])]
			else:
				node = nodes.size()
				nodes.append(st.line.point_at(float(e[0])))
			if prev_node >= 0 and node != prev_node and float(e[0]) - prev_s > 0.5:
				edges.append([prev_node, node, _sub_line(st.line, prev_s, float(e[0]))])
			prev_node = node
			prev_s = float(e[0])
	# Half-edges 2e (a -> b) and 2e+1 (b -> a), sorted by angle round each node.
	var around: Array = []
	for n: int in nodes.size():
		around.append([])
	for ei: int in edges.size():
		var pts: PackedVector2Array = edges[ei][2]
		var a: int = int(edges[ei][0])
		var b: int = int(edges[ei][1])
		var da: Vector2 = pts[mini(1, pts.size() - 1)] - pts[0]
		var db: Vector2 = pts[maxi(pts.size() - 2, 0)] - pts[pts.size() - 1]
		(around[a] as Array).append([atan2(da.y, da.x), ei * 2])
		(around[b] as Array).append([atan2(db.y, db.x), ei * 2 + 1])
	for n2: int in nodes.size():
		(around[n2] as Array).sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
	var pos_in: Dictionary = {}
	for n3: int in nodes.size():
		var lst: Array = around[n3]
		for k: int in lst.size():
			pos_in[int(lst[k][1])] = [n3, k]
	var seen := PackedByteArray()
	seen.resize(edges.size() * 2)
	var out: Array[Dictionary] = []
	for h0: int in edges.size() * 2:
		if seen[h0] != 0:
			continue
		var walk: Array[int] = []
		var h: int = h0
		var guard: int = 0
		while seen[h] == 0 and guard < 4000:
			seen[h] = 1
			walk.append(h)
			guard += 1
			var twin: int = h ^ 1
			var at: Array = pos_in[twin]
			var lst2: Array = around[int(at[0])]
			h = int(lst2[(int(at[1]) + 1) % lst2.size()][1])
		# Drop spurs (edges walked both ways).
		var used: Dictionary = {}
		for hh: int in walk:
			used[hh >> 1] = int(used.get(hh >> 1, 0)) + 1
		var poly := PackedVector2Array()
		for hh2: int in walk:
			if int(used[hh2 >> 1]) > 1:
				continue
			var pts2: PackedVector2Array = edges[hh2 >> 1][2]
			if hh2 & 1 == 0:
				for i: int in pts2.size() - 1:
					poly.append(pts2[i])
			else:
				for i2: int in range(pts2.size() - 1, 0, -1):
					poly.append(pts2[i2])
		if poly.size() < 3:
			continue
		# Taking the rightmost turn at every node walks each bounded face clockwise (negative
		# shoelace area) and the outer face of each component counter-clockwise.
		var area: float = -signed_area(poly)
		if area > min_area:
			poly.reverse()
			out.append({"poly": poly, "area": area})
	return out


static func _sub_line(line: Polyline2, s0: float, s1: float) -> PackedVector2Array:
	var out := PackedVector2Array([line.point_at(s0)])
	for i: int in line.points.size():
		if line.lengths[i] > s0 + 0.01 and line.lengths[i] < s1 - 0.01:
			out.append(line.points[i])
	out.append(line.point_at(s1))
	return out


## Shoelace area: positive counter-clockwise in atan2's sense (x towards z).
static func signed_area(poly: PackedVector2Array) -> float:
	var a: float = 0.0
	for i: int in poly.size():
		var p: Vector2 = poly[i]
		var q: Vector2 = poly[(i + 1) % poly.size()]
		a += p.x * q.y - q.x * p.y
	return a * 0.5


# --- Helpers -------------------------------------------------------------------------------------

## Whether p lies inside the polygon (crossing number, half-open edges). Geometry2D's
## is_point_in_polygon casts its ray to a point past the polygon's bounds and was seen to count a
## point 240 m outside a lot frame as inside; this one has no such corner case.
static func point_in(p: Vector2, poly: PackedVector2Array) -> bool:
	var inside: bool = false
	var n: int = poly.size()
	for i: int in n:
		var a: Vector2 = poly[i]
		var b: Vector2 = poly[(i + 1) % n]
		if (a.y > p.y) != (b.y > p.y) and p.x < a.x + (b.x - a.x) * (p.y - a.y) / (b.y - a.y):
			inside = not inside
	return inside


## [[x, z], ...] or a PackedVector2Array as a PackedVector2Array.
static func to_points(v: Variant) -> PackedVector2Array:
	if v is PackedVector2Array:
		return v
	var out := PackedVector2Array()
	for p: Variant in v:
		if p is Vector2:
			out.append(p)
		else:
			out.append(Vector2(float(p[0]), float(p[1])))
	return out


## A road between a and b over the town's ground (an 8 m local grid A*, plan §2 `route_fine`):
## length, grade (gentle preferred, steep heavily penalised, past 1.5 x `grade_max` refused) and a
## valley term (height above the local mean costs); water is refused unless `bridge` gives the
## cost of a crossing. Control points simplified to `tol` m; empty
## when there is no way. Used for in-town arterial refinement and by the tests' synthetic roads.
static func route_fine(g: Ground, a: Vector2, b: Vector2, opts: Dictionary = {}) -> PackedVector2Array:
	var step: float = float(opts.get("step", 8.0))
	var margin: float = float(opts.get("margin", 160.0))
	var g_ok: float = float(opts.get("grade_ok", 0.05))
	var g_max: float = float(opts.get("grade_max", 0.12))
	var valley: float = float(opts.get("valley", 0.25))
	var water_min: float = float(opts.get("water", 10.0))
	var bridge: float = float(opts.get("bridge", 0.0))
	var box := Rect2(a, Vector2.ZERO).expand(b).grow(margin)
	var nx: int = int(ceil(box.size.x / step)) + 1
	var nz: int = int(ceil(box.size.y / step)) + 1
	var count: int = nx * nz
	var hh := PackedFloat32Array()
	hh.resize(count)
	var wet := PackedByteArray()
	wet.resize(count)
	for j: int in nz:
		for i: int in nx:
			var p := Vector2(box.position.x + i * step, box.position.y + j * step)
			hh[j * nx + i] = g.h(p)
			wet[j * nx + i] = 1 if g.water(p) < water_min else 0
	# Local mean over ~150 m (a summed-area table): the valley term prefers ground below it.
	var sat := PackedFloat64Array()
	sat.resize((nx + 1) * (nz + 1))
	for j1: int in nz:
		var row: float = 0.0
		for i1: int in nx:
			row += hh[j1 * nx + i1]
			sat[(j1 + 1) * (nx + 1) + i1 + 1] = sat[j1 * (nx + 1) + i1 + 1] + row
	var mean := PackedFloat32Array()
	mean.resize(count)
	var rad: int = maxi(1, int(round(75.0 / step)))
	for j2: int in nz:
		var ja: int = maxi(0, j2 - rad)
		var jb: int = mini(nz, j2 + rad + 1)
		for i2: int in nx:
			var ia: int = maxi(0, i2 - rad)
			var ib: int = mini(nx, i2 + rad + 1)
			var tot: float = sat[jb * (nx + 1) + ib] - sat[ja * (nx + 1) + ib] - sat[jb * (nx + 1) + ia] + sat[ja * (nx + 1) + ia]
			mean[j2 * nx + i2] = tot / float((jb - ja) * (ib - ia))
	var cell := func(p: Vector2) -> int:
		return clampi(int(round((p.y - box.position.y) / step)), 0, nz - 1) * nx + clampi(int(round((p.x - box.position.x) / step)), 0, nx - 1)
	var start: int = cell.call(a)
	var goal: int = cell.call(b)
	var gc := PackedFloat32Array()
	gc.resize(count)
	gc.fill(INF)
	var came := PackedInt32Array()
	came.resize(count)
	came.fill(-1)
	var closed := PackedByteArray()
	closed.resize(count)
	var heap := _Heap.new()
	gc[start] = 0.0
	var gx: int = goal % nx
	var gz: int = goal / nx
	heap.push(0.0, start)
	var nb: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1),
		Vector2i(2, 1), Vector2i(1, 2), Vector2i(-2, 1), Vector2i(-1, 2), Vector2i(2, -1), Vector2i(1, -2), Vector2i(-2, -1), Vector2i(-1, -2)]
	var found: bool = false
	while not heap.is_empty():
		var c: int = heap.pop()
		if closed[c] != 0:
			continue
		if c == goal:
			found = true
			break
		closed[c] = 1
		var ci: int = c % nx
		var cj: int = c / nx
		for dv: Vector2i in nb:
			var ni: int = ci + dv.x
			var nj: int = cj + dv.y
			if ni < 0 or nj < 0 or ni >= nx or nj >= nz:
				continue
			var n: int = nj * nx + ni
			if closed[n] != 0 or (wet[n] != 0 and n != goal and bridge <= 0.0):
				continue
			var dist: float = step * Vector2(dv).length()
			var gr: float = absf(hh[n] - hh[c]) / dist
			if gr > g_max * 1.5:
				continue
			var cost: float = dist * (1.0 + 20.0 * gr * gr + valley * maxf(0.0, hh[n] - mean[n]))
			if gr > g_ok:
				cost *= 1.0 + (gr - g_ok) * 30.0
			if gr > g_max:
				cost *= 1.0 + (gr - g_max) * 150.0
			if wet[n] != 0:
				cost += bridge if wet[c] == 0 else dist * 3.0
			var ng: float = gc[c] + cost
			if ng < gc[n]:
				gc[n] = ng
				came[n] = c
				heap.push(ng + step * Vector2(ni - gx, nj - gz).length(), n)
	if not found:
		return PackedVector2Array()
	var path := PackedVector2Array()
	var k: int = goal
	while k >= 0:
		path.append(Vector2(box.position.x + (k % nx) * step, box.position.y + (k / nx) * step))
		if k == start:
			break
		k = came[k]
	path.reverse()
	path[0] = a
	path[path.size() - 1] = b
	return relax(g, simplify(path, float(opts.get("tol", 7.0))), opts)


## Cuts a route's sharp corners: a point where it turns more than 35 degrees is dropped when the
## straight line between its neighbours is dry and no steeper than `grade_max` (grid zigzags and
## the joint of two routes become one bend).
static func relax(g: Ground, pts: PackedVector2Array, opts: Dictionary = {}) -> PackedVector2Array:
	var g_max: float = float(opts.get("grade_max", 0.12))
	var water_min: float = float(opts.get("water", 10.0))
	var bridge: float = float(opts.get("bridge", 0.0))
	for pass_i: int in 6:
		var changed: bool = false
		var i: int = 1
		while i < pts.size() - 1:
			var d0: Vector2 = (pts[i] - pts[i - 1]).normalized()
			var d1: Vector2 = (pts[i + 1] - pts[i]).normalized()
			if d0.dot(d1) < 0.82 and _passable(g, pts[i - 1], pts[i + 1], g_max, water_min if bridge <= 0.0 else -INF):
				pts.remove_at(i)
				changed = true
			else:
				i += 1
		if not changed:
			break
	return pts


static func _passable(g: Ground, a: Vector2, b: Vector2, g_max: float, water_min: float) -> bool:
	var n: int = maxi(2, int(ceil(a.distance_to(b) / 8.0)))
	var prev: float = g.h(a)
	for k: int in range(1, n + 1):
		var p: Vector2 = a.lerp(b, float(k) / n)
		var hv: float = g.h(p)
		if absf(hv - prev) / (a.distance_to(b) / n) > g_max or g.water(p) < water_min:
			return false
		prev = hv
	return true


## Ramer-Douglas-Peucker: drops points within `tol` of the line between kept ones.
static func simplify(pts: PackedVector2Array, tol: float) -> PackedVector2Array:
	if pts.size() < 3:
		return pts
	var keep := PackedByteArray()
	keep.resize(pts.size())
	keep[0] = 1
	keep[pts.size() - 1] = 1
	var stack: Array[Vector2i] = [Vector2i(0, pts.size() - 1)]
	while not stack.is_empty():
		var seg: Vector2i = stack.pop_back()
		var best: float = -1.0
		var bi: int = -1
		for i: int in range(seg.x + 1, seg.y):
			var d: float = Geometry2D.get_closest_point_to_segment(pts[i], pts[seg.x], pts[seg.y]).distance_to(pts[i])
			if d > best:
				best = d
				bi = i
		if bi >= 0 and best > tol:
			keep[bi] = 1
			stack.append(Vector2i(seg.x, bi))
			stack.append(Vector2i(bi, seg.y))
	var out := PackedVector2Array()
	for i2: int in pts.size():
		if keep[i2] != 0:
			out.append(pts[i2])
	return out


## Binary min-heap of (priority, int) for route_fine.
class _Heap:
	var prio := PackedFloat32Array()
	var vals := PackedInt32Array()
	var size: int = 0

	func is_empty() -> bool:
		return size == 0

	func push(p: float, v: int) -> void:
		if size >= prio.size():
			prio.resize(maxi(64, size * 2))
			vals.resize(maxi(64, size * 2))
		var i: int = size
		size += 1
		while i > 0:
			var par: int = (i - 1) >> 1
			if prio[par] < p or (prio[par] == p and vals[par] <= v):
				break
			prio[i] = prio[par]
			vals[i] = vals[par]
			i = par
		prio[i] = p
		vals[i] = v

	func pop() -> int:
		var top: int = vals[0]
		size -= 1
		if size == 0:
			return top
		var p: float = prio[size]
		var v: int = vals[size]
		var i: int = 0
		while true:
			var l: int = i * 2 + 1
			if l >= size:
				break
			var m: int = l
			if l + 1 < size and (prio[l + 1] < prio[l] or (prio[l + 1] == prio[l] and vals[l + 1] < vals[l])):
				m = l + 1
			if prio[m] > p or (prio[m] == p and vals[m] >= v):
				break
			prio[i] = prio[m]
			vals[i] = vals[m]
			i = m
		prio[i] = p
		vals[i] = v
		return top
