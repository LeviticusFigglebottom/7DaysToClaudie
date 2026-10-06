class_name RwgRoads
extends RefCounted
## Road routing for a random world (ADR-0031): A* over the macro grid (RwgTerrain), costed by
## length, grade (gentle grades preferred, steep ones heavily penalised), water (lakes are
## impassable; a river costs a bridge to enter and more to follow), and places already built
## (town pads and POIs are impassable). Cells an earlier road uses are cheaper, so later roads join
## the network instead of running beside it. A route becomes control points: the cell path
## simplified (Ramer-Douglas-Peucker), which Polyline2 then smooths into curves.

## New ADR-0031 scripts by path, so this compiles before the editor registers their class names.
const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")

const NB8: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
	Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]

var t: Terrain
## 1 = impassable.
var blocked := PackedByteArray()
## 1 = on or beside a river (bridge country).
var water := PackedByteArray()
## Road index + 1 of a road already running here (0: none).
var on_road := PackedInt32Array()
var grade_ok: float = 0.07
var grade_max: float = 0.16
var bridge_cost: float = 420.0
var reuse: float = 0.4


func setup(terrain: Terrain, cfg: Dictionary) -> void:
	t = terrain
	var count: int = t.n * t.n
	blocked.resize(count)
	water.resize(count)
	on_road.resize(count)
	var g: Array = cfg.get("grade", [0.07, 0.16])
	grade_ok = float(g[0])
	grade_max = float(g[1])
	bridge_cost = float(cfg.get("bridge_cost", 420.0))
	reuse = float(cfg.get("reuse", 0.4))
	for c: int in count:
		if t.lake_of[c] >= 0:
			blocked[c] = 1
		if t.river_of[c] >= 0:
			var ci: int = c % t.n
			var cj: int = c / t.n
			water[c] = 1
			for d: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var ni: int = ci + d.x
				var nj: int = cj + d.y
				if ni >= 0 and nj >= 0 and ni < t.n and nj < t.n:
					water[nj * t.n + ni] = 1


## Blocks every cell whose centre lies inside the polygon grown by `grow` metres.
func block_polygon(poly: PackedVector2Array, grow: float) -> void:
	var big: PackedVector2Array = poly
	if grow > 0.0:
		var off: Array = Geometry2D.offset_polygon(poly, grow)
		if not off.is_empty():
			big = off[0]
	var bb := Rect2(big[0], Vector2.ZERO)
	for p: Vector2 in big:
		bb = bb.expand(p)
	var i0: int = clampi(int(floor((bb.position.x - t.x0) / t.step)), 0, t.n - 1)
	var i1: int = clampi(int(ceil((bb.end.x - t.x0) / t.step)), 0, t.n - 1)
	var j0: int = clampi(int(floor((bb.position.y - t.z0) / t.step)), 0, t.n - 1)
	var j1: int = clampi(int(ceil((bb.end.y - t.z0) / t.step)), 0, t.n - 1)
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			if Geometry2D.is_point_in_polygon(Vector2(t.x0 + i * t.step, t.z0 + j * t.step), big):
				blocked[j * t.n + i] = 1


## Marks the cells along a polyline as road `road_index` (cheaper for later routes).
func mark(points: PackedVector2Array, road_index: int) -> void:
	for k: int in points.size() - 1:
		var a: Vector2 = points[k]
		var b: Vector2 = points[k + 1]
		var steps: int = maxi(1, int(ceil(a.distance_to(b) / (t.step * 0.5))))
		for s: int in steps + 1:
			var p: Vector2 = a.lerp(b, float(s) / steps)
			var c: int = t.cell(p.x, p.y)
			if on_road[c] == 0:
				on_road[c] = road_index + 1


## A route from a to b: control points (a and b exact), or empty when there is none. `margin`
## bounds the search to the pair's box grown by that much; `smooth` (0..1) how freely the grid's
## corners are cut (highways most).
func route(a: Vector2, b: Vector2, margin: float = 700.0, smooth: float = 0.5, grade_scale: float = 1.0) -> PackedVector2Array:
	var g_ok: float = grade_ok * grade_scale
	var g_max: float = grade_max * grade_scale
	var n: int = t.n
	var start: int = t.cell(a.x, a.y)
	var goal: int = t.cell(b.x, b.y)
	var box := Rect2(a, Vector2.ZERO).expand(b).grow(margin)
	var i0: int = clampi(int(floor((box.position.x - t.x0) / t.step)), 0, n - 1)
	var i1: int = clampi(int(ceil((box.end.x - t.x0) / t.step)), 0, n - 1)
	var j0: int = clampi(int(floor((box.position.y - t.z0) / t.step)), 0, n - 1)
	var j1: int = clampi(int(ceil((box.end.y - t.z0) / t.step)), 0, n - 1)
	var count: int = n * n
	var g := PackedFloat32Array()
	g.resize(count)
	g.fill(INF)
	var came := PackedInt32Array()
	came.resize(count)
	came.fill(-1)
	var closed := PackedByteArray()
	closed.resize(count)
	var heap := Terrain._Heap.new()
	g[start] = 0.0
	var gp: Vector2 = t.pos(goal)
	heap.push(t.pos(start).distance_to(gp) * reuse, start)
	var found: bool = false
	while not heap.is_empty():
		var c: int = heap.pop()
		if closed[c] != 0:
			continue
		if c == goal:
			found = true
			break
		closed[c] = 1
		var ci: int = c % n
		var cj: int = c / n
		var hc: float = t.h[c]
		for d: Vector2i in NB8:
			var ni: int = ci + d.x
			var nj: int = cj + d.y
			if ni < i0 or nj < j0 or ni > i1 or nj > j1:
				continue
			var nb: int = nj * n + ni
			if closed[nb] != 0 or (blocked[nb] != 0 and nb != goal):
				continue
			var dist: float = t.step * (1.4142 if d.x != 0 and d.y != 0 else 1.0)
			var gr: float = absf(t.h[nb] - hc) / dist
			var cost: float = dist * (1.0 + 30.0 * gr * gr)
			if gr > g_ok:
				cost *= 1.0 + (gr - g_ok) * 25.0
			if gr > g_max:
				cost *= 1.0 + (gr - g_max) * 120.0
			if water[nb] != 0:
				cost += bridge_cost if water[c] == 0 else dist * 3.0
			if on_road[nb] != 0:
				cost *= reuse
			var ng: float = g[c] + cost
			if ng < g[nb]:
				g[nb] = ng
				came[nb] = c
				heap.push(ng + t.pos(nb).distance_to(gp) * reuse, nb)
	if not found:
		_last_cells = PackedInt32Array()
		last_cost = INF
		return PackedVector2Array()
	last_cost = g[goal]
	var cells := PackedInt32Array()
	var k: int = goal
	while k >= 0:
		cells.append(k)
		if k == start:
			break
		k = came[k]
	cells.reverse()
	_last_cells = cells
	return _points(cells, a, b, smooth)


## The cells of the last route (empty when none was found) and its cost.
var _last_cells := PackedInt32Array()
var last_cost: float = INF


func _points(cells: PackedInt32Array, a: Vector2, b: Vector2, smooth: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for c2: int in cells:
		pts.append(t.pos(c2))
	if pts.size() >= 1:
		pts[0] = a
		pts[pts.size() - 1] = b
	if pts.size() == 1:
		pts.append(b)
	return relax(simplify(pts, t.step * lerpf(0.4, 0.85, smooth)), smooth)


## A route split where it would run along roads already built: one piece per stretch over open
## land, each ending on the road it meets (the caller snaps such ends onto that road's line), plus a
## short connector wherever the route steps from one road straight onto another. The whole route
## when it meets none; [] when there is no route. Each piece: {points, start_exact, end_exact}.
func route_pieces(a: Vector2, b: Vector2, margin: float = 700.0, smooth: float = 0.5) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var whole: PackedVector2Array = route(a, b, margin, smooth)
	if whole.is_empty():
		return out
	var cells: PackedInt32Array = _last_cells
	var n: int = cells.size()
	var runs: Array[Vector2i] = []
	var cur_start: int = -1
	for k: int in n:
		var anchor: bool = k == 0 or k == n - 1
		var road: int = 0 if anchor else on_road[cells[k]]
		if road == 0:
			if cur_start < 0:
				cur_start = maxi(0, k - 1) if k > 0 else 0
			continue
		if cur_start >= 0:
			runs.append(Vector2i(cur_start, k))
			cur_start = -1
		elif k > 1 and on_road[cells[k - 1]] != 0 and on_road[cells[k - 1]] != road:
			runs.append(Vector2i(k - 1, k))
	if cur_start >= 0:
		runs.append(Vector2i(cur_start, n - 1))
	if runs.size() == 1 and runs[0] == Vector2i(0, n - 1):
		out.append({"points": whole, "start_exact": true, "end_exact": true})
		return out
	for r: Vector2i in runs:
		var pa: Vector2 = a if r.x == 0 else t.pos(cells[r.x])
		var pb: Vector2 = b if r.y == n - 1 else t.pos(cells[r.y])
		out.append({"points": _points(cells.slice(r.x, r.y + 1), pa, pb, smooth), "start_exact": r.x == 0, "end_exact": r.y == n - 1})
	if out.is_empty():
		out.append({"points": whole, "start_exact": true, "end_exact": true})
	return out


## Cuts sharp corners: a point where the route turns hard is dropped when the straight line between
## its neighbours is passable (no blocked cell, no steeper than the steepest grade allowed), so a
## grid route's stair steps and doglegs become one bend.
func relax(pts: PackedVector2Array, smooth: float) -> PackedVector2Array:
	var limit: float = lerpf(0.75, 0.35, smooth)
	for pass_i: int in 4:
		var changed: bool = false
		var i: int = 1
		while i < pts.size() - 1:
			var d0: Vector2 = (pts[i] - pts[i - 1]).normalized()
			var d1: Vector2 = (pts[i + 1] - pts[i]).normalized()
			if d0.dot(d1) < limit and _passable(pts[i - 1], pts[i + 1]):
				pts.remove_at(i)
				changed = true
			else:
				i += 1
		if not changed:
			break
	return pts


func _passable(a: Vector2, b: Vector2) -> bool:
	var len_ab: float = a.distance_to(b)
	if len_ab < 1.0:
		return true
	var steps: int = maxi(2, int(ceil(len_ab / (t.step * 0.5))))
	var prev_h: float = t.height(a.x, a.y)
	for k: int in range(1, steps + 1):
		var p: Vector2 = a.lerp(b, float(k) / steps)
		var c: int = t.cell(p.x, p.y)
		if blocked[c] != 0 or (water[c] != 0 and on_road[c] == 0):
			return false
		var hv: float = t.height(p.x, p.y)
		if absf(hv - prev_h) / (len_ab / steps) > grade_max * 1.1:
			return false
		prev_h = hv
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
			var q: Vector2 = Geometry2D.get_closest_point_to_segment(pts[i], pts[seg.x], pts[seg.y])
			var d: float = q.distance_to(pts[i])
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
