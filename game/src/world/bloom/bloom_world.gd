class_name BloomWorld
extends Node
## Puts the Bloom field on screen (ADR-0025). TerrainManager owns one: it publishes the field as the
## shader globals `hm_bloom_map` / `hm_bloom_rect`, drives the night glow (`hm_bloom_night`) from
## the sun, hands the terrain its mycelium-web textures and keeps the map in step with the dynamic
## spots (rooting mounds, BloomMounds). The globals are cleared on exit, so menus and tools that
## run after a game never show a stale field.

const WEB_MASK: String = "res://assets/generated/textures/bloom_web_mask.png"
const WEB_NORMAL: String = "res://assets/generated/textures/bloom_web_normal.png"
const WEB_COV: String = "res://assets/generated/textures/bloom_web_cov.png"
## Sun elevations (degrees) between which the threads' glow fades in at dusk: full in deep twilight,
## gone just above the horizon, so it never shows by day and is full once the forest is dark.
const GLOW_FADE: Vector2 = Vector2(-9.0, 3.0)

static var _web: Dictionary = {}

var field: BloomField
var _image: Image
var _texture: ImageTexture
var _night: float = -1.0


## Takes the field and publishes it (an empty field switches the Bloom off in every shader).
func setup(p_field: BloomField) -> void:
	field = p_field
	_publish()


func _publish() -> void:
	if field == null or field.is_empty():
		RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", Vector4.ZERO)
		return
	_image = field.image()
	_texture = ImageTexture.create_from_image(_image)
	RenderingServer.global_shader_parameter_set(&"hm_bloom_map", _texture)
	RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", field.shader_rect())


## Re-uploads the map after the dynamic spots changed (`dirty` texels, from BloomField.set_spots).
func refresh(dirty: Rect2i) -> void:
	if field == null or dirty.size == Vector2i.ZERO:
		return
	if _texture == null:
		_publish()
		return
	_image = field.image()
	_texture.update(_image)


## Dynamic spots by source ([{pos: Vector2, radius, strength}] each), merged into the field's one
## spot list, so the rooting mounds (&"mounds") and the Bloom nests (&"nests", ADR-0055) never
## clobber each other. An empty list removes the source; fading is calling again with a lower
## strength. (Same API as the hub's BloomTiles version, f5dbc8a; this one recomposes via
## BloomField.set_spots.)
func set_spot_source(source: StringName, spots: Array) -> void:
	if spots.is_empty():
		_spot_sources.erase(source)
	else:
		_spot_sources[source] = spots.duplicate(true)
	if field == null:
		return
	var keys: Array = _spot_sources.keys()
	keys.sort()
	var all: Array = []
	for k: Variant in keys:
		all.append_array(_spot_sources[k])
	refresh(field.set_spots(all))


## Source -> its spots (set_spot_source), merged in source order.
var _spot_sources: Dictionary = {}


func _process(_delta: float) -> void:
	var night: float = 0.0
	if Game.session != null and Game.session.clock != null:
		night = night_level(Game.session.clock.sun_elevation_deg())
	if absf(night - _night) > 0.002:
		_night = night
		RenderingServer.global_shader_parameter_set(&"hm_bloom_night", night)


## How much the threads glow (0..1) at a sun elevation (degrees).
static func night_level(sun_elevation_deg: float) -> float:
	return 1.0 - smoothstep(GLOW_FADE.x, GLOW_FADE.y, sun_elevation_deg)


func _exit_tree() -> void:
	RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", Vector4.ZERO)
	RenderingServer.global_shader_parameter_set(&"hm_bloom_night", 0.0)


## Binds the mycelium-web textures to a terrain material (near chunks; generated textures, or a
## procedural stand-in before `make assets`).
static func apply_web(mat: ShaderMaterial) -> void:
	if _web.is_empty():
		var mask: Texture2D = load(WEB_MASK) if ResourceLoader.exists(WEB_MASK) else null
		var nrm: Texture2D = load(WEB_NORMAL) if ResourceLoader.exists(WEB_NORMAL) else null
		var cov: Texture2D = load(WEB_COV) if ResourceLoader.exists(WEB_COV) else null
		if mask == null or nrm == null or cov == null:
			var fb: Array[Texture2D] = _fallback_web()
			mask = fb[0]
			nrm = fb[1]
			cov = fb[2]
		_web = {"mask": mask, "normal": nrm, "cov": cov}
	mat.set_shader_parameter("bloom_web_mask", _web["mask"])
	mat.set_shader_parameter("bloom_web_normal", _web["normal"])
	mat.set_shader_parameter("bloom_web_cov", _web["cov"])


## A crude web from cellular noise (cell borders as threads), so the terrain still shows the Bloom
## before the generated textures exist. Channels as the generated mask: R priority, G age, B mat,
## A thread body; and its coverage map (the threads the shader's thresholds reveal at a third, two
## thirds and all of full growth, for bloom_web_cover 0.33).
static func _fallback_web() -> Array[Texture2D]:
	var size: int = 256
	var cells := FastNoiseLite.new()
	cells.noise_type = FastNoiseLite.TYPE_CELLULAR
	cells.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	cells.frequency = 0.045
	cells.seed = 2501
	var soft := FastNoiseLite.new()
	soft.frequency = 0.02
	soft.seed = 2502
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var cov := Image.create(size, size, false, Image.FORMAT_RGBA8)
	for y: int in size:
		for x: int in size:
			var edge: float = 1.0 - clampf(absf(cells.get_noise_2d(x, y)) * 6.0, 0.0, 1.0)
			var s: float = soft.get_noise_2d(x, y) * 0.5 + 0.5
			img.set_pixel(x, y, Color(edge * 0.9, s, clampf(s * 1.4 - 0.5, 0.0, 1.0), edge))
			var e: float = edge * 0.9
			cov.set_pixel(x, y, Color(float(e > 0.89), float(e > 0.78), float(e > 0.67), float(e > 0.67)))
	img.generate_mipmaps()
	cov.generate_mipmaps()
	var flat := Image.create(4, 4, false, Image.FORMAT_RGB8)
	flat.fill(Color(0.5, 0.5, 1.0))
	flat.generate_mipmaps()
	var out: Array[Texture2D] = [ImageTexture.create_from_image(img), ImageTexture.create_from_image(flat), ImageTexture.create_from_image(cov)]
	return out
