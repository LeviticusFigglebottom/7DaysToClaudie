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
## World-level towns of a random world (ADR-0040, RWG v2): [{id, name, framework, kind, center:
## Vector2, radius, bounds: Rect2}]. A town is a framework placed at the world origin (its lots are
## frames in world XZ); the composer applies it in every region its bounds come near, graded from
## world data alone, so it may straddle region borders. Empty on the main map and v1 worlds.
var towns: Array[Dictionary] = []
## A random world's places levelled from world data (TD-320): [{id, origin: Vector2 (corner), rot
## (radians), size: Vector2, level_at?: Vector2 (a roadside place: its road's edge where its drive
## leaves it)}], and their ids. The world roads are pinned to them.
var pads: Array[Dictionary] = []
var pad_ids: Dictionary = {}
## How far past a town's built bounds its ground reaches for town_at (m).
const TOWN_MARGIN: float = 20.0
## region id -> summary dict (from world.json)
var regions: Dictionary = {}
var cells: Dictionary = {}
## Spacing (m) of the macro elevation grid: region corners on the handcrafted map, a finer grid
## for a generated world (ADR-0031: `macro.step`), whose ranges and valleys live in the grid.
var macro_step: float = 1024.0
## How world roads are graded: "region" (each region from its own composed ground, the handcrafted
## map) or "world" (from macro + the world detail noise, identical in every region a road crosses,
## so a generated world's roads meet at region borders without a step).
var road_grade: String = "region"
## The generator's record ({version, seed, settings, ...}) for a generated world; {} otherwise.
var generator: Dictionary = {}
## World-level biome map of a generated world: ids, cell size and one index per cell (row-major,
## rows north to south); empty on the handcrafted map, whose regions paint their biomes.
var biome_ids: PackedStringArray = []
var biome_step: float = 0.0
var biome_cols: int = 0
var biome_rows: int = 0
var biome_cells := PackedByteArray()

## Flattened corner grid for allocation-free bicubic sampling.
var _corners := PackedFloat32Array()
var _corner_rows: int = 0
var _corner_cols: int = 0
var _noise := FastNoiseLite.new()
var _ridge := FastNoiseLite.new()
var _region_cache: Dictionary = {}
var _region_cache_mutex := Mutex.new()
## Per-world memos shared by every composer thread (ADR-0038), under `_memo_mutex`: the bytes of
## the files a region's input hash reads (world.json, frameworks.json, region.json and the
## frameworks and POIs it places: hashing a region re-read about 3 MB each time), the hashes by
## "region|spacing", and the profiles of world-graded roads by world road index.
var _bytes: Dictionary = {}
var _hashes: Dictionary = {}
var _profiles: Dictionary = {}
var _memo_mutex := Mutex.new()


static func load_from(path: String) -> WorldDef:
	# The bytes are kept for the composer's input hash, so world.json is read once.
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path.path_join("world.json"))
	var data: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if not data is Dictionary:
		push_error("WorldDef: cannot parse %s/world.json" % path)
		return null
	var w := WorldDef.new()
	w.dir_path = path
	w._bytes[path.path_join("world.json")] = bytes
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
	macro_step = float(macro.get("step", region_size))
	road_grade = str(d.get("road_grade", "region"))
	generator = d.get("generator", {})
	var bm: Dictionary = d.get("biome_map", {})
	if not bm.is_empty():
		biome_ids = PackedStringArray(bm.get("ids", []))
		biome_step = float(bm.get("step", 64.0))
		biome_cols = int(bm.get("cols", 0))
		biome_rows = int(bm.get("rows", 0))
		# One character per cell ("0".."9", "a".."z" index into ids), one string per row.
		for row: Variant in bm.get("rows_data", []):
			for ch: int in str(row).to_ascii_buffer():
				biome_cells.append(ch - 48 if ch < 58 else ch - 87)
		if biome_cells.size() != biome_cols * biome_rows:
			push_error("WorldDef: biome_map has %d cells, expected %d x %d" % [biome_cells.size(), biome_cols, biome_rows])
			biome_cells = PackedByteArray()
	corner_heights = macro.get("corner_heights", [])
	_corner_rows = corner_heights.size()
	_corner_cols = (corner_heights[0] as Array).size() if _corner_rows > 0 else 0
	for row: Variant in corner_heights:
		for v: Variant in row:
			_corners.append(float(v))
	# Only the flattened copy is read; the nested Arrays cost ~20 MB on a 513² generated grid.
	corner_heights = []
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
	for pv: Variant in d.get("pads", []):
		var pd: Dictionary = pv
		pads.append({"id": str(pd["id"]), "origin": Vector2(float(pd["origin"][0]), float(pd["origin"][1])),
			"rot": deg_to_rad(float(pd.get("rotation", 0.0))), "size": Vector2(float(pd["size"][0]), float(pd["size"][1]))})
		if pd.has("level_at"):
			pads.back()["level_at"] = Vector2(float(pd["level_at"][0]), float(pd["level_at"][1]))
		pad_ids[str(pd["id"])] = true
	for r: Dictionary in d.get("roads", []):
		roads.append({"id": str(r.get("id", "")), "line": Polyline2.from_array(r["points"]), "width": float(r.get("width", 7.0)),
			"shoulder": float(r.get("shoulder", 2.0)), "surface": str(r.get("surface", "asphalt")), "bridges": r.get("bridges", []),
			"markings": bool(r.get("markings", true))})
	for r: Dictionary in d.get("regions", []):
		regions[str(r["id"])] = r
		cells[str(r["cell"])] = str(r["id"])
	for t: Dictionary in d.get("towns", []):
		var tb: Array = t.get("bounds", [0, 0, 0, 0])
		var tc: Array = t.get("center", [0, 0])
		towns.append({"id": str(t.get("id", "")), "name": str(t.get("name", "")), "framework": str(t.get("framework", "")),
			"kind": str(t.get("kind", "")), "center": Vector2(float(tc[0]), float(tc[1])), "radius": float(t.get("radius", 0.0)),
			"bounds": Rect2(float(tb[0]), float(tb[1]), float(tb[2]), float(tb[3]))})
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


## A region's parsed region.json ({} when it has none). Cached; safe to call from several composer
## threads at once (a generated world composes its regions in parallel).
func region_data(region_id: String) -> Dictionary:
	_region_cache_mutex.lock()
	var cached: Variant = _region_cache.get(region_id)
	_region_cache_mutex.unlock()
	if cached != null:
		return cached
	var p: String = dir_path.path_join("regions").path_join(region_id).path_join("region.json")
	var d: Dictionary = {}
	if FileAccess.file_exists(p):
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
		if v is Dictionary:
			d = v
	_region_cache_mutex.lock()
	if _region_cache.has(region_id):
		d = _region_cache[region_id]
	else:
		_region_cache[region_id] = d
	_region_cache_mutex.unlock()
	return d


## Biome id of the world biome map at (x, z) ("" without one: the handcrafted map).
func biome_at(x: float, z: float) -> String:
	if biome_cells.is_empty():
		return ""
	var wr: Rect2 = world_rect()
	var c: int = clampi(int(floor((x - wr.position.x) / biome_step)), 0, biome_cols - 1)
	var r: int = clampi(int(floor((z - wr.position.y) / biome_step)), 0, biome_rows - 1)
	var i: int = biome_cells[r * biome_cols + c]
	return biome_ids[i] if i < biome_ids.size() else ""


## The organic town (ADR-0040) whose ground holds (x, z): inside its disc and its built bounds,
## grown TOWN_MARGIN m ("" outside every town; always on the main map). The composer paints `town`
## only on a town's streets (ADR-0047), so town ambience and spawns key on this mask instead.
func town_at(x: float, z: float) -> String:
	var p := Vector2(x, z)
	for tw: Dictionary in towns:
		if (tw["bounds"] as Rect2).grow(TOWN_MARGIN).has_point(p) and (tw["center"] as Vector2).distance_to(p) <= float(tw["radius"]):
			return str(tw["id"])
	return ""


## The biome whose ambience, spawns and spawn density apply at (x, z), given the composed biome
## there: "town" anywhere in an organic town but its yards (ADR-0047), else the composed one.
func behaviour_biome(composed: String, x: float, z: float) -> String:
	if composed == "town" or composed == "yard" or towns.is_empty():
		return composed
	return "town" if town_at(x, z) != "" else composed


func has_biome_map() -> bool:
	return not biome_cells.is_empty()


func is_region_built(region_id: String) -> bool:
	return str((regions.get(region_id, {}) as Dictionary).get("status", "")) == "built"


# --- Composer memos (ADR-0038; thread-safe) ----------------------------------------------------

## A file's bytes, read once per world (the composer's input hash reads the same files for every
## region and spacing).
func file_bytes(path: String) -> PackedByteArray:
	_memo_mutex.lock()
	var hit: Variant = _bytes.get(path)
	_memo_mutex.unlock()
	if hit != null:
		return hit
	var b: PackedByteArray = FileAccess.get_file_as_bytes(path)
	_memo_mutex.lock()
	if _bytes.has(path):
		b = _bytes[path]
	else:
		_bytes[path] = b
	_memo_mutex.unlock()
	return b


## A memoised input hash ("" when not computed yet); TerrainComposer.input_hash fills it.
func memo_hash(key: String) -> String:
	_memo_mutex.lock()
	var h: String = str(_hashes.get(key, ""))
	_memo_mutex.unlock()
	return h


func set_memo_hash(key: String, h: String) -> void:
	_memo_mutex.lock()
	_hashes[key] = h
	_memo_mutex.unlock()


## The profile of world road `index` ({profile, step, spans}), built by `build` the first time and
## shared by every region afterwards. Only for roads graded from world data alone (road_grade
## "world"), whose profile is the same whichever region builds it. Two threads may build one at
## once; the first stored wins, and both are identical. `index` is a world road's index, or a
## String key for a world town's street ("town:<town>:<street>", ADR-0040).
func road_profile(index: Variant, build: Callable) -> Dictionary:
	_memo_mutex.lock()
	var hit: Variant = _profiles.get(index)
	_memo_mutex.unlock()
	if hit != null:
		return hit
	var p: Dictionary = build.call()
	_memo_mutex.lock()
	if _profiles.has(index):
		p = _profiles[index]
	else:
		_profiles[index] = p
	_memo_mutex.unlock()
	return p


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
	# A zero amplitude (a generated world: its land is all in the grid) makes a term a signed
	# zero, and base + 0.0 + 0.0 is base (or +0.0) whichever zero it was: skip the noise calls.
	var n: float = 0.0 if amp == 0.0 else _noise.get_noise_2d(x, z) * amp * scale
	var rn: float = 0.0 if ridged_amp == 0.0 or boost == 0.0 else (_ridge.get_noise_2d(x, z) * 0.5 + 0.5) * ridged_amp * mount * boost
	return base + n + rn


func _corner_bicubic(x: float, z: float) -> float:
	if _corners.is_empty():
		return 0.0
	var gx: float = (x + cols * 0.5 * region_size) / macro_step
	var gz: float = (z + rows * 0.5 * region_size) / macro_step
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
