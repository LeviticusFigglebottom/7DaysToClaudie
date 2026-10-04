class_name RegionTerrain
extends RefCounted
## Composed terrain data for one region: heights, splat weights, biome map, vegetation mask and
## metadata (water bodies, roads, bridges, spawns, POI placements). Produced by TerrainComposer;
## cached to disk (user://cache/worlds/<world>/<region>.bin) keyed by an input hash.

const MAGIC: String = "HMRT"

var region_id: String = ""
var rect := Rect2()
var spacing: float = 1.0
var height: HeightField
## Per-sample splat weights for palette layers 0..3 and 4..7 (RGBA8, row-major, size = samples²).
var splat0: PackedByteArray = []
var splat1: PackedByteArray = []
## Per-sample biome index into `biome_ids`.
var biome: PackedByteArray = []
## Per-sample vegetation allowance 0..255 (0 = roads, water, pads, clearings).
var vegmask: PackedByteArray = []
var palette: PackedStringArray = []
var biome_ids: PackedStringArray = []
## [{kind: "river"|"lake", id, level, points: [[x,z]...], widths: [..], levels: [..]} | polygon]
var water: Array = []
## [{id, surface, width, points: [[x,y,z]...]}] road centre lines with final heights
var roads: Array = []
## [{from: [x,y,z], to: [x,y,z], width}]
var bridges: Array = []
## id -> {pos: [x,y,z], yaw, props}
var spawns: Dictionary = {}
## [{kind: "framework"|"poi", def: id, id, origin: [x,y,z], rotation, size: [w,d]}]
var placements: Array = []
## Frontier markers for docs/debug.
var frontiers: Array = []


func samples() -> int:
	return height.width


func index_of(x: float, z: float) -> int:
	var ix: int = clampi(int(round((x - rect.position.x) / spacing)), 0, height.width - 1)
	var iz: int = clampi(int(round((z - rect.position.y) / spacing)), 0, height.depth - 1)
	return iz * height.width + ix


func biome_at(x: float, z: float) -> String:
	return biome_ids[biome[index_of(x, z)]] if not biome.is_empty() else ""


func veg_at(x: float, z: float) -> float:
	return float(vegmask[index_of(x, z)]) / 255.0 if not vegmask.is_empty() else 1.0


## Splat weights (8 floats) at a sample.
func splat_at(x: float, z: float) -> PackedFloat32Array:
	var i: int = index_of(x, z) * 4
	var out := PackedFloat32Array()
	out.resize(8)
	for c: int in 4:
		out[c] = float(splat0[i + c]) / 255.0
		out[c + 4] = float(splat1[i + c]) / 255.0
	return out


## Dominant palette layer name at a position (footstep sounds, particles).
func surface_at(x: float, z: float) -> String:
	var w: PackedFloat32Array = splat_at(x, z)
	var best: int = 0
	for c: int in 8:
		if w[c] > w[best]:
			best = c
	return palette[best] if best < palette.size() else ""


func splat_images() -> Array[Image]:
	var n: int = height.width
	return [Image.create_from_data(n, n, false, Image.FORMAT_RGBA8, splat0),
		Image.create_from_data(n, n, false, Image.FORMAT_RGBA8, splat1)]


# --- Persistence --------------------------------------------------------------------------

func save(path: String, input_hash: String) -> Error:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var meta: Dictionary = {
		"region": region_id, "rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y], "spacing": spacing,
		"palette": Array(palette), "biomes": Array(biome_ids), "water": water, "roads": roads, "bridges": bridges,
		"spawns": spawns, "placements": placements, "frontiers": frontiers, "hash": input_hash,
	}
	var blob := PackedByteArray()
	blob.append_array(height.to_bytes())
	var parts: Array[PackedByteArray] = [blob, splat0, splat1, biome, vegmask]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_buffer(MAGIC.to_ascii_buffer())
	f.store_pascal_string(JSON.stringify(meta))
	for p: PackedByteArray in parts:
		var c: PackedByteArray = p.compress(FileAccess.COMPRESSION_ZSTD)
		f.store_64(p.size())
		f.store_64(c.size())
		f.store_buffer(c)
	f.close()
	return OK


## Loads a cached region; returns null if missing or if the stored hash differs.
static func load_cached(path: String, input_hash: String) -> RegionTerrain:
	if not FileAccess.file_exists(path):
		return null
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null or f.get_buffer(4).get_string_from_ascii() != MAGIC:
		return null
	var meta: Variant = JSON.parse_string(f.get_pascal_string())
	if not meta is Dictionary or str(meta.get("hash", "")) != input_hash:
		return null
	var parts: Array[PackedByteArray] = []
	for i: int in 5:
		var raw_size: int = f.get_64()
		var comp_size: int = f.get_64()
		parts.append(f.get_buffer(comp_size).decompress(raw_size, FileAccess.COMPRESSION_ZSTD))
	var rt := RegionTerrain.new()
	rt.region_id = str(meta["region"])
	var r: Array = meta["rect"]
	rt.rect = Rect2(float(r[0]), float(r[1]), float(r[2]), float(r[3]))
	rt.spacing = float(meta["spacing"])
	rt.height = HeightField.from_bytes(parts[0])
	rt.splat0 = parts[1]
	rt.splat1 = parts[2]
	rt.biome = parts[3]
	rt.vegmask = parts[4]
	rt.palette = PackedStringArray(meta["palette"])
	rt.biome_ids = PackedStringArray(meta["biomes"])
	rt.water = meta["water"]
	rt.roads = meta["roads"]
	rt.bridges = meta["bridges"]
	rt.spawns = meta["spawns"]
	rt.placements = meta["placements"]
	rt.frontiers = meta.get("frontiers", [])
	return rt
