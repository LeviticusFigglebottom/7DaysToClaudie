class_name CaveSet
extends RefCounted
## An immutable set of CavePlans (TD-104: published whole, never mutated, so worker threads may
## hold one while the main thread swaps in a new set). Queries go through a 64 m grid, so
## is_inside / floor_below / keep_out cost one dictionary lookup away from caves.

const CELL: float = 64.0

var plans: Array[CavePlan] = []
var _grid: Dictionary = {}


## Combines CaveSets and/or CavePlans (parts) with the runtime plans in `extra` (id -> CavePlan).
## Failed plans (ok = false) are left out; the first plan of an id wins.
static func combined(parts: Array, extra: Dictionary) -> CaveSet:
	var s := CaveSet.new()
	var seen: Dictionary = {}
	for part: Variant in parts:
		if part is CaveSet:
			for p: CavePlan in (part as CaveSet).plans:
				s._add(p, seen)
		elif part is CavePlan:
			s._add(part as CavePlan, seen)
	for k: Variant in extra:
		if extra[k] is CavePlan:
			s._add(extra[k] as CavePlan, seen)
	return s


func _add(p: CavePlan, seen: Dictionary) -> void:
	if p == null or not p.ok or seen.has(p.id):
		return
	seen[p.id] = true
	plans.append(p)
	# Indexed by the footprint (air plus mouth apron) so keep_out finds the apron too.
	var fp: Rect2 = p.footprint()
	for c: Vector2i in _cells(AABB(Vector3(fp.position.x, 0.0, fp.position.y), Vector3(fp.size.x, 0.0, fp.size.y))):
		if not _grid.has(c):
			_grid[c] = []
		(_grid[c] as Array).append(p)


static func _cells(box: AABB) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for cz: int in range(int(floor(box.position.z / CELL)), int(floor(box.end.z / CELL)) + 1):
		for cx: int in range(int(floor(box.position.x / CELL)), int(floor(box.end.x / CELL)) + 1):
			out.append(Vector2i(cx, cz))
	return out


## The plans whose bounds meet `box`.
func touching(box: AABB) -> Array[CavePlan]:
	var out: Array[CavePlan] = []
	for c: Vector2i in _cells(box):
		for p: CavePlan in _grid.get(c, []):
			if not out.has(p) and p.aabb.intersects(box):
				out.append(p)
	return out


## Whether any cave's footprint (its air and mouth apron) meets the XZ rect `r`: lets a caller skip
## per-point keep_out tests for a chunk no cave reaches (the vegetation's keep-out).
func any_in_rect(r: Rect2) -> bool:
	for c: Vector2i in _cells(AABB(Vector3(r.position.x, 0.0, r.position.y), Vector3(r.size.x, 0.0, r.size.y))):
		for p: CavePlan in _grid.get(c, []):
			if p.footprint().intersects(r):
				return true
	return false


func _at(x: float, z: float) -> Array:
	return _grid.get(Vector2i(int(floor(x / CELL)), int(floor(z / CELL))), [])


func is_inside(p: Vector3, ground_y: float) -> bool:
	for plan: CavePlan in _at(p.x, p.z):
		if plan.aabb.has_point(p) and plan.is_inside(p, ground_y):
			return true
	return false


## The highest cave floor under p over all caves; NAN when p is over no cave air.
func floor_below(p: Vector3) -> float:
	var best: float = NAN
	for plan: CavePlan in _at(p.x, p.z):
		var f: float = plan.floor_below(p)
		if not is_nan(f) and (is_nan(best) or f > best):
			best = f
	return best


func keep_out(x: float, z: float) -> bool:
	for plan: CavePlan in _at(x, z):
		if plan.keep_out(x, z):
			return true
	return false


func is_empty() -> bool:
	return plans.is_empty()
