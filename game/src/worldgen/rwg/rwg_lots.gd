class_name RwgLots
extends RefCounted
## The lots of an organic town (ADR-0040, docs/RWG_V2_PLAN.md §3.6): frontage subdivision along
## each street side. A lot is a frame, an oriented rectangle whose local +Z (its front) faces its
## street, accepted only when it overlaps no other frame (1 m apart), stays clear of every street
## corridor (half width + shoulder), keeps 12 m from water and stands on ground level enough for its
## zoning; otherwise it shrinks to its zone's minimum, then the walk skips ahead. Around each frame a
## parcel (the yard: grown sideways towards its neighbours and back, clipped by the streets) for
## the map, fences and yard ground. Pure geometry over RwgStreets and its Ground: worker-safe.
##
## Frame convention (PoiManager.lot_xf, plan assumption A10): `yaw` such that
## `Basis(Vector3.UP, yaw)` is the building's basis, so the front (local +Z) points along
## (sin yaw, cos yaw) in world XZ and local +X along (cos yaw, -sin yaw): a lot facing south has
## yaw 0, east 90, north 180, west -90 (degrees in the output).

const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")

## The zone each size class belongs to.
const SIZE_ZONES: Dictionary = {
	"inner_residential": "residential", "outer_residential": "residential", "commercial": "commercial",
	"civic": "civic", "industrial": "industrial", "rural": "rural", "plaza": "plaza",
}


## One lot: its frame, zoning and where it fronts.
class Lot:
	var id: String = ""
	var c := Vector2.ZERO
	## Frontage (local x) and depth (local z), metres.
	var w: float = 20.0
	var d: float = 30.0
	## Radians, lot_xf convention (see the script's doc).
	var yaw: float = 0.0
	var ax := Vector2.RIGHT
	var az := Vector2(0.0, 1.0)
	## residential, commercial, civic, industrial, rural, or plaza (the town square, not a lot).
	var zone: String = "residential"
	var size_key: String = ""
	var zoning := PackedStringArray()
	## The street it fronts (index), -1 for the plaza; side of that street; the frontage's arcs.
	var street: int = -1
	var side: int = 0
	var s0: float = 0.0
	var s1: float = 0.0
	var ring: String = ""
	var y: float = 0.0
	var relief: float = 0.0
	var poly := PackedVector2Array()
	## Placed by a quota pass (kept when residential lots are thinned).
	var fixed: bool = false

	## Sets the frame from its centre, size and front direction (the way its local +Z points).
	func set_frame(center: Vector2, width: float, depth: float, front: Vector2) -> void:
		c = center
		w = width
		d = depth
		az = front.normalized()
		ax = Vector2(az.y, -az.x)
		yaw = atan2(az.x, az.y)

	## World point at local (x, z), both from the centre (z towards the front).
	func at(lx: float, lz: float) -> Vector2:
		return c + ax * lx + az * lz

	## Front-left, front-right, back-right, back-left.
	func corners() -> PackedVector2Array:
		var hx: Vector2 = ax * (w * 0.5)
		var hz: Vector2 = az * (d * 0.5)
		return PackedVector2Array([c - hx + hz, c + hx + hz, c + hx - hz, c - hx - hz])

	func front_mid() -> Vector2:
		return c + az * (d * 0.5)


var net: Streets
var ground: Streets.Ground
var lots: Array[Lot] = []
var cfg: Dictionary = {}
var sizes: Dictionary = {}
var reliefs: Dictionary = {}
var verge: float = 3.0
var overlap_gap: float = 1.0
var water_min: float = 12.0
var margin: float = 0.4
var junction_extra: float = 8.0
var skip: float = 6.0
var gaps: Array = [1.0, 4.0]
## Arc intervals taken on each street side: "si:side" -> [[s0, s1], ...].
var occupied: Dictionary = {}
var _cells: Dictionary = {}
var _cell: float = 32.0
var _qstamp := PackedInt32Array()
var _qn: int = 0


func setup(p_net: Streets, p_cfg: Dictionary) -> void:
	net = p_net
	ground = p_net.ground
	cfg = p_cfg
	sizes = cfg.get("sizes", {})
	reliefs = cfg.get("relief", {})
	verge = float(cfg.get("verge", 3.0))
	overlap_gap = float(cfg.get("overlap_gap", 1.0))
	water_min = float(cfg.get("water", 12.0))
	margin = float(cfg.get("corridor_margin", 0.4))
	junction_extra = float(cfg.get("junction_gap", 8.0))
	skip = float(cfg.get("skip", 6.0))
	gaps = cfg.get("side_gap", [1.0, 4.0])


## [[frontage lo, hi], [depth lo, hi]] of a size class.
func size_of(key: String) -> Array:
	return sizes.get(key, [[20.0, 24.0], [28.0, 32.0]])


## Steepest relief (m) a lot of this zone may stand on.
func relief_of(zone: String) -> float:
	return float(reliefs.get(zone, 3.5))


## Distance from a street's centre line to the front of the lots along it: half its width plus the
## verge (at least its shoulder and a metre).
func front_offset(st: Streets.Street) -> float:
	return st.half() + maxf(verge, st.shoulder + 1.0)


## A frame on side `side` of street si over the arc [lo, hi], `depth` deep: its front edge runs
## along the chord of that stretch, out past the verge from wherever the street bulges nearest.
func frame_on(si: int, side: int, lo: float, hi: float, depth: float) -> Lot:
	var st: Streets.Street = net.streets[si]
	var pa: Vector2 = st.line.point_at(lo)
	var pb: Vector2 = st.line.point_at(hi)
	var t: Vector2 = pb - pa
	t = st.line.tangent_at(lo) if t.length() < 0.5 else t.normalized()
	var n: Vector2 = Vector2(-t.y, t.x) * side
	var m: Vector2 = (pa + pb) * 0.5
	var level: float = 0.0
	for k: int in 5:
		level = maxf(level, (st.line.point_at(lerpf(lo, hi, k / 4.0)) - m).dot(n))
	var front: Vector2 = m + n * (level + front_offset(st))
	var l := Lot.new()
	l.set_frame(front + n * depth * 0.5, hi - lo, depth, -n)
	l.street = si
	l.side = side
	l.s0 = lo
	l.s1 = hi
	return l


## Whether a frame may stand: clear of every lot (and of `extra`, candidates not yet added), on
## ground within `relief` m, dry, and clear of every street corridor (cheapest tests first).
func fits(l: Lot, relief: float, extra: Array[Lot] = []) -> bool:
	var cs: PackedVector2Array = l.corners()
	var bb := Rect2(cs[0], Vector2.ZERO)
	for p: Vector2 in cs:
		bb = bb.expand(p)
	for oi: int in _query(bb.grow(overlap_gap)):
		if not clear_of(l, lots[oi], overlap_gap):
			return false
	for e: Lot in extra:
		if not clear_of(l, e, overlap_gap):
			return false
	if not relief_ok(l, relief):
		return false
	for k: int in 9:
		if ground.water(l.at((k % 3 - 1) * l.w * 0.5, (k / 3 - 1) * l.d * 0.5)) < water_min:
			return false
	return corridor_clearance(l, cs, true) >= 0.0


## The 5 x 5 samples of a frame, corners and middle first (so a steep frame fails early).
const _ORDER: Array[int] = [0, 4, 20, 24, 12, 2, 10, 14, 22, 6, 8, 16, 18, 1, 3, 5, 9, 15, 19, 21, 23, 7, 11, 13, 17]


func relief_ok(l: Lot, limit: float) -> bool:
	var lo: float = INF
	var hi: float = -INF
	for k: int in _ORDER:
		var v: float = ground.h(l.at(((k % 5) / 4.0 - 0.5) * l.w, ((k / 5) / 4.0 - 0.5) * l.d))
		lo = minf(lo, v)
		hi = maxf(hi, v)
		if hi - lo > limit:
			return false
	l.relief = hi - lo
	return true


## The smallest clearance (m) from the frame to any street corridor (negative: inside one);
## `early`: stop at the first corridor it enters.
func corridor_clearance(l: Lot, cs: PackedVector2Array, early: bool = false) -> float:
	var best: float = INF
	var half_diag: float = Vector2(l.w, l.d).length() * 0.5
	for sid: int in net.near(l.c, half_diag + 14.0):
		var si: int = net.seg_st[sid]
		if si < 0:
			continue
		var st: Streets.Street = net.streets[si]
		var need: float = st.half() + st.shoulder + margin
		var a: Vector2 = net.seg_a[sid]
		var b: Vector2 = net.seg_b[sid]
		# No part of the frame is nearer the segment than its centre less its half diagonal: skip
		# segments that cannot beat the best so far (or, early, cannot reach into the frame).
		var bound: float = l.c.distance_to(Geometry2D.get_closest_point_to_segment(l.c, a, b)) - half_diag - need
		if bound >= (0.0 if early else best):
			continue
		best = minf(best, seg_rect_distance(a, b, l, cs) - need)
		if early and best < 0.0:
			return best
	return best


## Distance between the segment a-b and the frame (0 when they touch).
static func seg_rect_distance(a: Vector2, b: Vector2, l: Lot, cs: PackedVector2Array) -> float:
	var la := Vector2((a - l.c).dot(l.ax), (a - l.c).dot(l.az))
	var lb := Vector2((b - l.c).dot(l.ax), (b - l.c).dot(l.az))
	var hw: float = l.w * 0.5
	var hd: float = l.d * 0.5
	var da: float = Vector2(maxf(absf(la.x) - hw, 0.0), maxf(absf(la.y) - hd, 0.0)).length()
	var db: float = Vector2(maxf(absf(lb.x) - hw, 0.0), maxf(absf(lb.y) - hd, 0.0)).length()
	if da == 0.0 or db == 0.0:
		return 0.0
	for k: int in 4:
		if Geometry2D.segment_intersects_segment(a, b, cs[k], cs[(k + 1) % 4]) != null:
			return 0.0
	var best: float = minf(da, db)
	for p: Vector2 in cs:
		best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)))
	return best


## Separating-axis test: true when the two frames are at least `gap` apart along some axis.
static func clear_of(a: Lot, b: Lot, gap: float) -> bool:
	var dc: Vector2 = b.c - a.c
	for u: Vector2 in [a.ax, a.az, b.ax, b.az]:
		var ra: float = absf(a.ax.dot(u)) * a.w * 0.5 + absf(a.az.dot(u)) * a.d * 0.5
		var rb: float = absf(b.ax.dot(u)) * b.w * 0.5 + absf(b.az.dot(u)) * b.d * 0.5
		if absf(dc.dot(u)) >= ra + rb + gap:
			return true
	return false


## (min, max, mean) of the reference ground over the frame, 5 x 5 samples.
func ground_stats(l: Lot) -> Vector3:
	var lo: float = INF
	var hi: float = -INF
	var acc: float = 0.0
	for k: int in 25:
		var v: float = ground.h(l.at(((k % 5) / 4.0 - 0.5) * l.w, ((k / 5) / 4.0 - 0.5) * l.d))
		lo = minf(lo, v)
		hi = maxf(hi, v)
		acc += v
	return Vector3(lo, hi, acc / 25.0)


func add(l: Lot) -> int:
	var li: int = lots.size()
	lots.append(l)
	_insert(li)
	if l.street >= 0 and l.side != 0:
		var key: String = "%d:%d" % [l.street, l.side]
		if not occupied.has(key):
			occupied[key] = []
		(occupied[key] as Array).append([minf(l.s0, l.s1), maxf(l.s0, l.s1)])
	return li


## Keeps only the lots `keep` says (rebuilding the index and the taken frontage).
func retain(keep: Callable) -> void:
	var old: Array[Lot] = lots
	lots = []
	_cells.clear()
	_qstamp.clear()
	occupied.clear()
	for l: Lot in old:
		if bool(keep.call(l)):
			add(l)


func _insert(li: int) -> void:
	var l: Lot = lots[li]
	var r: float = Vector2(l.w, l.d).length() * 0.5
	var i0: int = int(floor((l.c.x - r) / _cell))
	var i1: int = int(floor((l.c.x + r) / _cell))
	var j0: int = int(floor((l.c.y - r) / _cell))
	var j1: int = int(floor((l.c.y + r) / _cell))
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var key := Vector2i(i, j)
			if not _cells.has(key):
				_cells[key] = []
			(_cells[key] as Array).append(li)


func _query(bb: Rect2) -> PackedInt32Array:
	var out := PackedInt32Array()
	_qn += 1
	if _qstamp.size() < lots.size():
		_qstamp.resize(lots.size())
	for j: int in range(int(floor(bb.position.y / _cell)), int(floor(bb.end.y / _cell)) + 1):
		for i: int in range(int(floor(bb.position.x / _cell)), int(floor(bb.end.x / _cell)) + 1):
			for li: int in _cells.get(Vector2i(i, j), []):
				if _qstamp[li] != _qn:
					_qstamp[li] = _qn
					out.append(li)
	return out


## Arc intervals a walk on side `side` of street si must not cover: the junctions on that side
## (the crossing street's half width + 8 m each way), the street's turning circle, and the frontage
## lots already hold.
func blocked(si: int, side: int) -> Array:
	var st: Streets.Street = net.streets[si]
	var out: Array = []
	for stn: Array in st.stations:
		if (int(stn[2]) & Streets.side_bit(side)) == 0:
			continue
		var gap: float = 0.0
		for so: int in net.junctions[int(stn[1])].streets:
			if so != si:
				gap = maxf(gap, net.streets[so].half() + junction_extra)
		out.append([float(stn[0]) - gap, float(stn[0]) + gap])
	if st.bulb >= 0:
		out.append([st.length() - net.streets[st.bulb].half() - 2.0, st.length() + 1.0])
	elif st.dead_end:
		out.append([st.length() - 4.0, st.length() + 1.0])
	for iv: Variant in occupied.get("%d:%d" % [si, side], []):
		out.append([float(iv[0]) - overlap_gap, float(iv[1]) + overlap_gap])
	return out


## Walks side `side` of street si from arc `from` towards `to` placing lots where `zone_at(p, si)`
## names a size class ("" skips ahead, "stop" ends the walk). Each lot tries its drawn size, then a
## shallower one, then its class minimum; after a lot the walk leaves a 1-4 m side gap, after a
## miss it skips 6 m. `commit` adds lots as they are accepted; otherwise they are only candidates
## (checked against each other). Returns the lots placed, in walk order.
func walk(si: int, side: int, from: float, to: float, zone_at: Callable, r: RandomNumberGenerator, commit: bool, max_lots: int = 1000) -> Array[Lot]:
	var st: Streets.Street = net.streets[si]
	var dir: float = 1.0 if to >= from else -1.0
	var bl: Array = blocked(si, side)
	var out: Array[Lot] = []
	var none: Array[Lot] = []
	var s: float = from
	var guard: int = 0
	while (to - s) * dir > 1.0 and out.size() < max_lots and guard < 4000:
		guard += 1
		var key: String = zone_at.call(st.line.point_at(clampf(s + dir * 10.0, 0.0, st.length())), si)
		if key == "stop":
			break
		if key == "":
			s += dir * skip
			continue
		var sz: Array = size_of(key)
		var w: float = r.randf_range(float(sz[0][0]), float(sz[0][1]))
		var dd: float = r.randf_range(float(sz[1][0]), float(sz[1][1]))
		var relief: float = relief_of(SIZE_ZONES.get(key, "residential"))
		var placed: Lot = null
		var jump: float = NAN
		for attempt: Array in [[w, dd], [w, float(sz[1][0])], [float(sz[0][0]), float(sz[1][0])]]:
			var tw: float = float(attempt[0])
			var lo: float = s if dir > 0.0 else s - tw
			var hi: float = lo + tw
			if lo < 0.0 or hi > st.length() or (dir > 0.0 and hi > to + 0.5) or (dir < 0.0 and lo < to - 0.5):
				break
			jump = _jump(bl, lo, hi, dir)
			if not is_nan(jump):
				break
			var l: Lot = frame_on(si, side, lo, hi, float(attempt[1]))
			if fits(l, relief, none if commit else out):
				placed = l
				break
		if not is_nan(jump):
			s = jump
			continue
		if placed == null:
			s += dir * skip
			if is_nan(jump) and (s < 0.0 or s > st.length()):
				break
			continue
		placed.size_key = key
		placed.zone = SIZE_ZONES.get(key, "residential")
		out.append(placed)
		if commit:
			add(placed)
		s += dir * (placed.w + r.randf_range(float(gaps[0]), float(gaps[1])))
	return out


## Where a walk must jump to when [lo, hi] runs into a blocked interval (NAN: it doesn't).
static func _jump(bl: Array, lo: float, hi: float, dir: float) -> float:
	var to: float = NAN
	for iv: Variant in bl:
		var b0: float = float(iv[0])
		var b1: float = float(iv[1])
		if hi > b0 and lo < b1:
			var t: float = b1 + 0.01 if dir > 0.0 else b0 - 0.01
			if is_nan(to) or (dir > 0.0 and t > to) or (dir < 0.0 and t < to):
				to = t
	return to


## Lots round the turning circle at the end of cul-de-sac si: up to three frames facing the bulb,
## straight on and swung 62 degrees either way. Returns how many stood.
func head_lots(si: int, key: String, r: RandomNumberGenerator, limit: int = 3) -> int:
	var st: Streets.Street = net.streets[si]
	if st.bulb < 0:
		return 0
	var bulb: Streets.Street = net.streets[st.bulb]
	var e: Vector2 = bulb.ctrl[0]
	var u: Vector2 = (bulb.ctrl[1] - bulb.ctrl[0]).normalized()
	var sz: Array = size_of(key)
	var made: int = 0
	for ang: float in [0.0, 62.0, -62.0]:
		if made >= limit:
			break
		var dir: Vector2 = u.rotated(deg_to_rad(ang))
		for attempt: Array in [[r.randf_range(float(sz[0][0]), float(sz[0][1])), r.randf_range(float(sz[1][0]), float(sz[1][1]))], [float(sz[0][0]), float(sz[1][0])]]:
			var l := Lot.new()
			var tw: float = float(attempt[0])
			var td: float = float(attempt[1])
			# The front's corners must clear the circle too, not just its middle.
			var off: float = sqrt(pow(bulb.half() + verge, 2.0) + pow(tw * 0.5, 2.0)) if ang == 0.0 else bulb.half() + verge + tw * 0.2
			l.set_frame(e + dir * (off + td * 0.5), tw, td, -dir)
			l.street = si
			l.side = 0
			l.s0 = st.length()
			l.s1 = st.length()
			if fits(l, relief_of(SIZE_ZONES.get(key, "residential"))):
				l.size_key = key
				l.zone = SIZE_ZONES.get(key, "residential")
				add(l)
				made += 1
				break
	return made


## Parcels: each frame grown sideways towards its neighbours (to half the gap, at most 4 m) and back
## (half the gap behind it, at most `back` m), then clipped by every street corridor.
func parcels(back: float) -> void:
	for l: Lot in lots:
		if l.zone == "plaza":
			l.poly = l.corners()
			continue
		var left: float = _grow_room(l, -1, 4.0)
		var right: float = _grow_room(l, 1, 4.0)
		var rear: float = _grow_room(l, 0, back)
		var hx: float = l.w * 0.5
		var hz: float = l.d * 0.5
		var poly := PackedVector2Array([l.at(-hx - left, hz), l.at(hx + right, hz), l.at(hx + right, -hz - rear), l.at(-hx - left, -hz - rear)])
		for sid: int in net.near(l.c, maxf(l.w, l.d) * 0.75 + back + 14.0):
			var si: int = net.seg_st[sid]
			if si < 0:
				continue
			var st: Streets.Street = net.streets[si]
			var a: Vector2 = net.seg_a[sid]
			var b: Vector2 = net.seg_b[sid]
			var t: Vector2 = (b - a).normalized() if a.distance_to(b) > 0.01 else Vector2.RIGHT
			var n: Vector2 = Vector2(-t.y, t.x) * (st.half() + st.shoulder)
			var ext: Vector2 = t * (st.half() + st.shoulder if st.cls == "bulb" else 0.5)
			var corridor := PackedVector2Array([a - ext + n, b + ext + n, b + ext - n, a - ext - n])
			var parts: Array[PackedVector2Array] = Geometry2D.clip_polygons(poly, corridor)
			if parts.is_empty():
				continue
			var best: PackedVector2Array = parts[0]
			for part: PackedVector2Array in parts:
				if Geometry2D.is_point_in_polygon(l.c, part):
					best = part
					break
			poly = best
		l.poly = poly


## How far the frame can grow on one side (-1 left, 1 right: along local x; 0: back) before it
## comes within the same distance of another frame (so neighbours meet halfway), up to `most` m.
func _grow_room(l: Lot, which: int, most: float) -> float:
	var ext: float = most
	while ext > 0.25:
		var probe := Lot.new()
		if which == 0:
			probe.set_frame(l.at(0.0, -l.d * 0.5 - ext), l.w, ext * 2.0, l.az)
		else:
			probe.set_frame(l.at(which * (l.w * 0.5 + ext), 0.0), ext * 2.0, l.d, l.az)
		var hit: bool = false
		var bb := Rect2(probe.c, Vector2.ZERO).grow(Vector2(probe.w, probe.d).length())
		for oi: int in _query(bb):
			var o: Lot = lots[oi]
			if o != l and not clear_of(probe, o, 0.0):
				hit = true
				break
		if not hit:
			return ext
		ext -= 1.0
	return 0.0
