class_name WorldDef
extends RefCounted
## A world definition (main map or an RWG output): grid of regions, macro elevation, and the
## world-scale water/road networks that must stay continuous across region borders.
## Loaded from <dir>/world.json; regions from <dir>/regions/<id>/region.json.

var dir_path: String = ""
var id: String = ""
var display_name: String = ""
var seed: int = 0
var region_size: float = 1024.0
var cols: int = 7
var rows: int = 7
var sea_level: float = 0.0
var corner_heights: Array = []
var macro_noise_cfg: Dictionary = {}
## [{id, line: Polyline2, width, depth, bank, level}]
var rivers: Array[Dictionary] = []
## [{id, polygon: PackedVector2Array, level, depth, shore, bounds: Rect2}]
var lakes: Array[Dictionary] = []
## [{id, line: Polyline2, width, shoulder, surface, bridges: [{from, to, deck}]}]
var roads: Array[Dictionary] = []
## region id -> summary dict (from world.json)
var regions: Dictionary = {}
var cells: Dictionary = {}

## Flattened corner grid for allocation-free bicubic sampling.
var _corners := PackedFloat32Array()
var _corner_rows: int = 0
var _corner_cols: int = 0
var _noise := FastNoiseLite.new()
var _ridge := FastNoiseLite.new()
var _region_cache: Dictionary = {}


static func load_from(path: String) -> WorldDef:
	var text: String = FileAccess.get_file_as_string(path.path_join("world.json"))
	var data: Variant = JSON.parse_string(text)
	if not data is Dictionary:
		push_error("WorldDef: cannot parse %s/world.json" % path)
		return null
	var w := WorldDef.new()
	w.dir_path = path
	w._parse(data)
	return w


func _parse(d: Dictionary) -> void:
	id = str(d.get("id", "world"))
	display_name = str(d.get("name", id))
	seed = int(d.get("seed", 1))
	region_size = float(d.get("region_size", 1024.0))
	cols = int(d.get("cols", 7))
	rows = int(d.get("rows", 7))
	sea_level = float(d.get("sea_level", 0.0))
	var macro: Dictionary = d.get("macro", {})
	corner_heights = macro.get("corner_heights", [])
	_corner_rows = corner_heights.size()
	_corner_cols = (corner_heights[0] as Array).size() if _corner_rows > 0 else 0
	for row: Variant in corner_heights:
		for v: Variant in row:
			_corners.append(float(v))
	macro_noise_cfg = macro.get("noise", {})
	for r: Dictionary in d.get("rivers", []):
		rivers.append({"id": str(r.get("id", "")), "line": Polyline2.from_array(r["points"]), "width": r.get("width", 16.0),
			"depth": float(r.get("depth", 2.5)), "bank": float(r.get("bank", 6.0)), "level": r.get("level", 0.0),
			"valley_width": float(r.get("valley_width", 130.0)), "valley_slope": float(r.get("valley_slope", 0.16))})
	for l: Dictionary in d.get("lakes", []):
		var poly := PackedVector2Array()
		for p: Variant in l["polygon"]:
			poly.append(Vector2(float(p[0]), float(p[1])))
		var b := Rect2(poly[0], Vector2.ZERO)
		for p: Vector2 in poly:
			b = b.expand(p)
		lakes.append({"id": str(l.get("id", "")), "polygon": poly, "level": float(l.get("level", 0.0)),
			"depth": float(l.get("depth", 10.0)), "shore": float(l.get("shore", 20.0)), "bounds": b})
	for r: Dictionary in d.get("roads", []):
		roads.append({"id": str(r.get("id", "")), "line": Polyline2.from_array(r["points"]), "width": float(r.get("width", 7.0)),
			"shoulder": float(r.get("shoulder", 2.0)), "surface": str(r.get("surface", "asphalt")), "bridges": r.get("bridges", []),
			"markings": bool(r.get("markings", true))})
	for r: Dictionary in d.get("regions", []):
		regions[str(r["id"])] = r
		cells[str(r["cell"])] = str(r["id"])
	_noise.seed = seed
	_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_noise.fractal_octaves = int(macro_noise_cfg.get("octaves", 5))
	_noise.frequency = float(macro_noise_cfg.get("frequency", 0.001))
	_ridge.seed = seed + 17
	_ridge.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_ridge.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	_ridge.fractal_octaves = 5
	_ridge.frequency = float(macro_noise_cfg.get("frequency", 0.001)) * 2.2


# --- Geometry ---------------------------------------------------------------------------------

## World rect of the whole map.
func world_rect() -> Rect2:
	return Rect2(Vector2(-cols * 0.5, -rows * 0.5) * region_size, Vector2(cols, rows) * region_size)


## "D6" -> Vector2i(col 3, row 5)
static func cell_coords(cell: String) -> Vector2i:
	return Vector2i(cell.unicode_at(0) - "A".unicode_at(0), int(cell.substr(1)) - 1)


func region_rect(region_id: String) -> Rect2:
	var r: Dictionary = regions.get(region_id, {})
	if r.is_empty():
		return Rect2()
	var c: Vector2i = cell_coords(str(r["cell"]))
	var o: Vector2 = world_rect().position + Vector2(c.x, c.y) * region_size
	return Rect2(o, Vector2(region_size, region_size))


func region_at(x: float, z: float) -> String:
	var wr: Rect2 = world_rect()
	var c: int = int(floor((x - wr.position.x) / region_size))
	var r: int = int(floor((z - wr.position.y) / region_size))
	if c < 0 or r < 0 or c >= cols or r >= rows:
		return ""
	return str(cells.get("%s%d" % [char("A".unicode_at(0) + c), r + 1], ""))


func region_data(region_id: String) -> Dictionary:
	if _region_cache.has(region_id):
		return _region_cache[region_id]
	var p: String = dir_path.path_join("regions").path_join(region_id).path_join("region.json")
	var d: Dictionary = {}
	if FileAccess.file_exists(p):
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
		if v is Dictionary:
			d = v
	_region_cache[region_id] = d
	return d


func is_region_built(region_id: String) -> bool:
	return str((regions.get(region_id, {}) as Dictionary).get("status", "")) == "built"


# --- Macro elevation --------------------------------------------------------------------------

## Smooth large-scale elevation (corner grid, Catmull-Rom) + elevation-scaled macro noise.
## Rivers/lakes/roads are NOT included (TerrainComposer applies them).
func macro_height(x: float, z: float) -> float:
	var base: float = _corner_bicubic(x, z)
	var amp: float = float(macro_noise_cfg.get("amplitude", 30.0))
	var ridged_amp: float = float(macro_noise_cfg.get("ridged_amplitude", 20.0))
	var boost: float = float(macro_noise_cfg.get("mountain_boost", 2.5))
	var mount: float = clampf((base - 60.0) / 500.0, 0.0, 1.0)
	var scale: float = 0.35 + mount * boost
	var n: float = _noise.get_noise_2d(x, z) * amp * scale
	var rn: float = (_ridge.get_noise_2d(x, z) * 0.5 + 0.5) * ridged_amp * mount * boost
	return base + n + rn


func _corner_bicubic(x: float, z: float) -> float:
	if _corners.is_empty():
		return 0.0
	var gx: float = (x + cols * 0.5 * region_size) / region_size
	var gz: float = (z + rows * 0.5 * region_size) / region_size
	var ix: int = int(floor(gx))
	var iz: int = int(floor(gz))
	var fx: float = gx - ix
	var fz: float = gz - iz
	var r0: float = _row_cubic(iz - 1, ix, fx)
	var r1: float = _row_cubic(iz, ix, fx)
	var r2: float = _row_cubic(iz + 1, ix, fx)
	var r3: float = _row_cubic(iz + 2, ix, fx)
	return _catmull(r0, r1, r2, r3, fz)


func _row_cubic(j: int, ix: int, fx: float) -> float:
	var r: int = clampi(j, 0, _corner_rows - 1) * _corner_cols
	var c0: float = _corners[r + clampi(ix - 1, 0, _corner_cols - 1)]
	var c1: float = _corners[r + clampi(ix, 0, _corner_cols - 1)]
	var c2: float = _corners[r + clampi(ix + 1, 0, _corner_cols - 1)]
	var c3: float = _corners[r + clampi(ix + 2, 0, _corner_cols - 1)]
	return _catmull(c0, c1, c2, c3, fx)


static func _catmull(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
	var t2: float = t * t
	var t3: float = t2 * t
	return 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)
