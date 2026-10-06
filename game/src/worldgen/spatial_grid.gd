class_name SpatialGrid
extends RefCounted
## A uniform grid of buckets over the world plane (ADR-0038). Each item, an int id, is registered
## in every cell its bounding rect touches; `query(rect)` returns the ids registered in the cells
## the rect touches, ascending and without repeats. The grid only drops what cannot be near:
## callers keep their exact tests, and walking the candidates in ascending order visits them in the
## order an exhaustive loop over the ids would have, so ties resolve the same way.
##
## RwgGenerator indexes road segments and road vertices (as `pack(road, part)`) and places with
## 256 m cells; a query of a rect larger than a few cells walks those cells, so search outward in
## growing squares rather than with one large rect.

## An item with parts (a road's segments or vertices) packs its owner above PART_BITS bits.
const PART_BITS: int = 20
const PART_MASK: int = (1 << PART_BITS) - 1

var cell: float = 256.0
var _cells: Dictionary = {}
## The occupied cells' bounds: a query never walks cells beyond them.
var _lo := Vector2i(2147483647, 2147483647)
var _hi := Vector2i(-2147483648, -2147483648)


func _init(p_cell: float = 256.0) -> void:
	cell = p_cell


static func pack(owner: int, part: int) -> int:
	return (owner << PART_BITS) | part


## Registers `id` in every cell `r` touches. Ids registered in ascending order stay ascending in
## each cell (query sorts anyway).
func insert(id: int, r: Rect2) -> void:
	var x0: int = floori(r.position.x / cell)
	var x1: int = floori(r.end.x / cell)
	var z0: int = floori(r.position.y / cell)
	var z1: int = floori(r.end.y / cell)
	_lo = Vector2i(mini(_lo.x, x0), mini(_lo.y, z0))
	_hi = Vector2i(maxi(_hi.x, x1), maxi(_hi.y, z1))
	for cz: int in range(z0, z1 + 1):
		for cx: int in range(x0, x1 + 1):
			var k := Vector2i(cx, cz)
			var ids: PackedInt64Array = _cells.get(k, PackedInt64Array())
			ids.append(id)
			_cells[k] = ids


## The ids registered in the cells `r` touches, ascending, each once.
func query(r: Rect2) -> PackedInt64Array:
	var x0: int = maxi(floori(r.position.x / cell), _lo.x)
	var x1: int = mini(floori(r.end.x / cell), _hi.x)
	var z0: int = maxi(floori(r.position.y / cell), _lo.y)
	var z1: int = mini(floori(r.end.y / cell), _hi.y)
	var out := PackedInt64Array()
	var cells: int = 0
	for cz: int in range(z0, z1 + 1):
		for cx: int in range(x0, x1 + 1):
			var ids: Variant = _cells.get(Vector2i(cx, cz))
			if ids != null:
				out.append_array(ids)
				cells += 1
	if cells <= 1:
		return out
	out.sort()
	var uniq := PackedInt64Array()
	for i: int in out.size():
		if i == 0 or out[i] != out[i - 1]:
			uniq.append(out[i])
	return uniq


func is_empty() -> bool:
	return _cells.is_empty()
