class_name TerrainTextures
extends RefCounted
## Provides the global terrain layer texture arrays + tile sizes. Uses the generated arrays
## (assets/generated/textures/terrain_*_array.png, see docs/ASSET_PIPELINE.md) when present and
## falls back to a procedural stand-in so the terrain always renders (e.g. before `make assets`).

const LAYERS_JSON: String = "res://data/materials/terrain_layers.json"
const DEFAULT_LAYERS: PackedStringArray = ["forest_floor", "moss_ground", "grass_ground", "dirt", "mud", "gravel",
	"rock_cliff", "sand", "snow", "asphalt_cracked", "concrete_slab"]
const DEFAULT_TILES: Dictionary = {"forest_floor": 3.0, "moss_ground": 2.5, "grass_ground": 2.5, "dirt": 2.5, "mud": 3.0,
	"gravel": 2.0, "rock_cliff": 6.0, "sand": 3.0, "snow": 4.0, "asphalt_cracked": 4.0, "concrete_slab": 4.0}
const FALLBACK_COLORS: Dictionary = {"forest_floor": Color(0.23, 0.16, 0.09), "moss_ground": Color(0.2, 0.27, 0.09),
	"grass_ground": Color(0.3, 0.36, 0.14), "dirt": Color(0.38, 0.29, 0.19), "mud": Color(0.22, 0.17, 0.12),
	"gravel": Color(0.45, 0.43, 0.4), "rock_cliff": Color(0.42, 0.41, 0.39), "sand": Color(0.62, 0.55, 0.4),
	"snow": Color(0.85, 0.87, 0.9), "asphalt_cracked": Color(0.13, 0.13, 0.14), "concrete_slab": Color(0.5, 0.5, 0.48),
	# ADR-0041's burn and fen (ADR-0047): charcoal under grey ash, and black-brown peat.
	"ash_char": Color(0.2, 0.19, 0.17), "peat": Color(0.15, 0.11, 0.08)}

static var _cached: TerrainTextures = null

var layers: PackedStringArray = []
var tiles := PackedFloat32Array()
# TextureLayered: imported arrays are CompressedTexture2DArray, which is not a Texture2DArray.
var albedo: TextureLayered
var normal: TextureLayered
var orm: TextureLayered
var macro_variation: Texture2D
## True when the layers are the procedural stand-in (no generated arrays).
var is_fallback: bool = false


static func get_shared() -> TerrainTextures:
	if _cached == null:
		_cached = TerrainTextures.prepare()
		_cached.finish()
	return _cached


## True once get_shared() has made the textures (later loads reuse them).
static func is_shared_ready() -> bool:
	return _cached != null


## The pure-data half of the textures, safe on a worker thread (WorldLoader, TD-197): the layer
## list and tiles, and the stand-in images when there are no generated arrays (~90 ms of
## per-pixel script). finish() turns it into textures on the main thread (texture RIDs: the
## headless dummy renderer's tables are not thread-safe, TD-103).
static func prepare() -> TerrainTextures:
	var t := TerrainTextures.new()
	t._prepare()
	return t


## Main thread: makes the textures from what prepare() left and, the first time, shares them.
## Returns the shared textures (an earlier one if another finish got there first).
func finish() -> TerrainTextures:
	if _finished:
		return self
	_finished = true
	if not _pending.is_empty():
		var arrs: Array[TextureLayered] = []
		for imgs: Array[Image] in _pending:
			var arr := Texture2DArray.new()
			arr.create_from_images(imgs)
			arrs.append(arr)
		albedo = arrs[0]
		normal = arrs[1]
		orm = arrs[2]
		is_fallback = true
		_pending.clear()
	var base: String = "res://assets/generated/textures/"
	if _generated:
		albedo = load(base + "terrain_albedo_array.png")
		normal = load(base + "terrain_normal_array.png")
		orm = load(base + "terrain_orm_array.png") if ResourceLoader.exists(base + "terrain_orm_array.png") else null
		if albedo == null or albedo.get_layers() < layers.size():
			# Imported but unusable: the stand-in, made here (rare: an out-of-date import).
			_pending = _fallback_images(layers)
			_generated = false
			_finished = false
			return finish()
	if _macro_image != null:
		macro_variation = ImageTexture.create_from_image(_macro_image)
		_macro_image = null
	elif ResourceLoader.exists(base + "terrain_macro_variation.png"):
		macro_variation = load(base + "terrain_macro_variation.png")
	return self


## Shares textures made from a prepare() on another thread (or makes them if `prepared` is null).
static func adopt(prepared: TerrainTextures) -> TerrainTextures:
	if _cached == null and prepared != null:
		_cached = prepared.finish()
	return get_shared()


var _finished: bool = false
## Whether finish() loads the generated arrays.
var _generated: bool = false
## Stand-in layer images [albedo, normal, orm] (each one Image per layer) for finish().
var _pending: Array = []
var _macro_image: Image = null


func layer_index(name: String) -> int:
	return layers.find(name)


func _prepare() -> void:
	layers = DEFAULT_LAYERS
	var tile_map: Dictionary = DEFAULT_TILES.duplicate()
	if FileAccess.file_exists(LAYERS_JSON):
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(LAYERS_JSON))
		if d is Dictionary:
			if d.has("layers"):
				layers = PackedStringArray(d["layers"])
			tile_map.merge(d.get("tile_metres", {}), true)
	tiles.resize(16)
	tiles.fill(3.0)
	for i: int in layers.size():
		tiles[i] = float(tile_map.get(layers[i], 3.0))
	var base: String = "res://assets/generated/textures/"
	_generated = ResourceLoader.exists(base + "terrain_albedo_array.png") and ResourceLoader.exists(base + "terrain_normal_array.png")
	if not _generated:
		_pending = _fallback_images(layers)
	if not ResourceLoader.exists(base + "terrain_macro_variation.png"):
		_macro_image = _noise_image(256, 7)


## The procedural stand-in's layer images: [albedo, normal, orm], one Image per layer each.
static func _fallback_images(p_layers: PackedStringArray) -> Array:
	var size: int = 128
	var albs: Array[Image] = []
	var nrms: Array[Image] = []
	var orms: Array[Image] = []
	var nz := FastNoiseLite.new()
	nz.frequency = 0.08
	nz.fractal_octaves = 4
	# Flat normal and ORM layers: one fill each, shared by every layer.
	var nimg := Image.create(size, size, false, Image.FORMAT_RGB8)
	nimg.fill(Color(0.5, 0.5, 1.0))
	nimg.generate_mipmaps()
	var o := Image.create(size, size, false, Image.FORMAT_RGB8)
	o.fill(Color(1.0, 0.85, 0.0))
	o.generate_mipmaps()
	for li: int in p_layers.size():
		var col: Color = FALLBACK_COLORS.get(p_layers[li], Color(0.4, 0.4, 0.4))
		var a := Image.create(size, size, false, Image.FORMAT_RGBA8)
		nz.seed = 11 + li
		for y: int in size:
			for x: int in size:
				var v: float = nz.get_noise_2d(x, y) * 0.5 + 0.5
				var c: Color = col * (0.75 + 0.5 * v)
				c.a = v
				a.set_pixel(x, y, c)
		a.generate_mipmaps()
		albs.append(a)
		nrms.append(nimg)
		orms.append(o)
	return [albs, nrms, orms]


static func _noise_image(size: int, seed: int) -> Image:
	var nz := FastNoiseLite.new()
	nz.seed = seed
	nz.frequency = 0.02
	nz.fractal_octaves = 5
	var img: Image = nz.get_seamless_image(size, size)
	img.generate_mipmaps()
	return img


## Applies arrays + tiles to a terrain ShaderMaterial (near or far).
func apply_to(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("layer_albedo", albedo)
	mat.set_shader_parameter("layer_normal", normal)
	mat.set_shader_parameter("layer_orm", orm)
	mat.set_shader_parameter("layer_tile", tiles)
	mat.set_shader_parameter("macro_variation", macro_variation)
	mat.set_shader_parameter("rock_layer", maxi(layer_index("rock_cliff"), 0))
	mat.set_shader_parameter("snow_layer", maxi(layer_index("snow"), 0))
