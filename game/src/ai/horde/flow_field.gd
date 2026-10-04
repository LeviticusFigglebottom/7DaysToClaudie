class_name FlowField
extends RefCounted
## Horde navigation for the Hum (ADR-0011): one integrated travel-cost field over a square grid
## around the base, shared by every attacker (no per-zombie pathfinding). Each Hollowed walks
## downhill to the lowest-cost neighbour. Player structures are passable at a cost proportional
## to their remaining hit points, so the horde converges on the weakest (or most damaged) part
## of the defences instead of walking the long way round — weak-point targeting falls out of the
## field for free. Pure model: built from callables, safe to integrate on a worker thread.

const SQRT2: float = 1.41421356

var cell: float = 1.5
var n: int = 0
var origin := Vector2.ZERO
var center := Vector3.ZERO
## Per-cell entry cost multiplier (1 = flat open ground, INF = impassable).
var cost := PackedFloat32Array()
## Extra cost (metres-equivalent) to break through structures occupying the cell.
var structure_cost := PackedFloat32Array()
## Integrated cost to the nearest target.
var dist := PackedFloat32Array()
var ready: bool = false


func setup(p_center: Vector3, radius_m: float, p_cell: float) -> void:
	cell = p_cell
	center = p_center
	n = int(ceil(radius_m * 2.0 / cell)) + 1
	origin = Vector2(p_center.x - (n - 1) * cell * 0.5, p_center.z - (n - 1) * cell * 0.5)
	cost.resize(n * n)
	structure_cost.resize(n * n)
	dist.resize(n * n)
	cost.fill(1.0)
	structure_cost.fill(0.0)
	dist.fill(INF)
	ready = false


func cell_of(pos: Vector3) -> Vector2i:
	return Vector2i(int(floor((pos.x - origin.x) / cell + 0.5)), int(floor((pos.z - origin.y) / cell + 0.5)))


func cell_pos(c: Vector2i) -> Vector3:
	return Vector3(origin.x + c.x * cell, 0.0, origin.y + c.y * cell)


func in_grid(c: Vector2i) -> bool:
	return c.x >= 0 and c.y >= 0 and c.x < n and c.y < n


## Terrain costs: slope penalty, impassable cliffs and deep water.
## height_fn(x, z) -> float; water_fn(x, z) -> water surface height (or -INF).
func build_terrain(height_fn: Callable, water_fn: Callable, max_slope_deg: float) -> void:
	var heights := PackedFloat32Array()
	heights.resize(n * n)
	for y: int in n:
		for x: int in n:
			heights[y * n + x] = float(height_fn.call(origin.x + x * cell, origin.y + y * cell))
	var max_grad: float = tan(deg_to_rad(max_slope_deg))
	for y: int in n:
		for x: int in n:
			var i: int = y * n + x
			var hx: float = heights[y * n + mini(x + 1, n - 1)] - heights[y * n + maxi(x - 1, 0)]
			var hz: float = heights[mini(y + 1, n - 1) * n + x] - heights[maxi(y - 1, 0) * n + x]
			var grad: float = Vector2(hx, hz).length() / (2.0 * cell)
			if grad > max_grad:
				cost[i] = INF
				continue
			var c: float = 1.0 + grad * 2.5
			if water_fn.is_valid():
				var wl: float = float(water_fn.call(origin.x + x * cell, origin.y + y * cell))
				var depth: float = wl - heights[i]
				if depth > 1.2:
					c = INF
				elif depth > 0.2:
					c *= 1.0 + depth * 3.0
			cost[i] = c


## Marks structure cells. pieces: [{"a": Vector3, "b": Vector3, "hp": float}] (segments; a == b
## for compact pieces, which are widened by `radius`).
func add_structures(pieces: Array, cost_per_hp: float, radius: float = 0.6) -> void:
	for p: Dictionary in pieces:
		var a: Vector3 = p["a"]
		var b: Vector3 = p["b"]
		var extra: float = maxf(1.0, float(p["hp"])) * cost_per_hp
		var steps: int = maxi(1, int(ceil(a.distance_to(b) / (cell * 0.5))))
		for s: int in steps + 1:
			var q: Vector3 = a.lerp(b, float(s) / float(steps))
			var r: int = int(ceil(radius / cell))
			var c0: Vector2i = cell_of(q)
			for dy: int in range(-r, r + 1):
				for dx: int in range(-r, r + 1):
					var c := Vector2i(c0.x + dx, c0.y + dy)
					if not in_grid(c) or cell_pos(c).distance_to(Vector3(q.x, 0, q.z)) > radius + cell * 0.5:
						continue
					var i: int = c.y * n + c.x
					structure_cost[i] = maxf(structure_cost[i], extra)


## Dijkstra from the target positions over 8-neighbour moves.
func integrate(targets: Array[Vector3]) -> void:
	dist.fill(INF)
	var heap := MinHeap.new()
	for t: Vector3 in targets:
		var c: Vector2i = cell_of(t)
		if in_grid(c):
			var i: int = c.y * n + c.x
			dist[i] = 0.0
			heap.push(0.0, i)
	var offs: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
		Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]
	while not heap.is_empty():
		var i: int = heap.pop()
		var d: float = dist[i]
		var cx: int = i % n
		var cy: int = i / n
		for k: int in 8:
			var o: Vector2i = offs[k]
			var nx: int = cx + o.x
			var ny: int = cy + o.y
			if nx < 0 or ny < 0 or nx >= n or ny >= n:
				continue
			var j: int = ny * n + nx
			var cj: float = cost[j]
			if cj == INF:
				continue
			var step: float = (SQRT2 if k >= 4 else 1.0) * cell * (cj + cost[i]) * 0.5 + structure_cost[j]
			var nd: float = d + step
			if nd < dist[j]:
				dist[j] = nd
				heap.push(nd, j)
	ready = true


## Unit XZ direction an attacker at `pos` should walk (towards the targets). Outside the grid it
## heads for the centre; ZERO when already at a target.
func direction_at(pos: Vector3) -> Vector3:
	var c: Vector2i = cell_of(pos)
	if not ready or not in_grid(c):
		var d: Vector3 = center - pos
		d.y = 0.0
		return d.normalized() if d.length() > 0.1 else Vector3.ZERO
	var best: float = dist[c.y * n + c.x]
	var best_c: Vector2i = c
	for dy: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var q := Vector2i(c.x + dx, c.y + dy)
			if (dx == 0 and dy == 0) or not in_grid(q):
				continue
			var v: float = dist[q.y * n + q.x]
			if v < best:
				best = v
				best_c = q
	if best_c == c:
		return Vector3.ZERO
	var to: Vector3 = cell_pos(best_c) - Vector3(pos.x, 0.0, pos.z)
	to.y = 0.0
	return to.normalized() if to.length() > 0.001 else Vector3.ZERO


func distance_at(pos: Vector3) -> float:
	var c: Vector2i = cell_of(pos)
	return dist[c.y * n + c.x] if ready and in_grid(c) else INF


## True when the cheapest way in from `pos` goes through a structure (the defences hold).
func path_crosses_structure(pos: Vector3, max_steps: int = 400) -> bool:
	var p: Vector3 = pos
	for i: int in max_steps:
		var c: Vector2i = cell_of(p)
		if not in_grid(c):
			return false
		if structure_cost[c.y * n + c.x] > 0.0:
			return true
		var d: Vector3 = direction_at(p)
		if d == Vector3.ZERO:
			return false
		p += d * cell
	return false
