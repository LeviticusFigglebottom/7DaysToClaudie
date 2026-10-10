class_name ImpostorLibrary
extends RefCounted
## Far-tree impostors: per species, an atlas of FRAMES side views taken around the trunk axis
## (frame i = camera at local direction (sin a, 0, cos a), a = i * TAU / FRAMES), one row per model
## variant (row v = the species' models[v], top row first), used by assets/shaders/impostor.gdshader
## on camera-facing quads; each far tree shows its own variant's row (MultiMesh custom data).
##
## Baked from the generated tree models by `make bake` (src/tools/cli/bake.gd) into
## assets/generated/impostors/<species>.png (+ _n.png normals, _winter.png bare branches for a
## deciduous species, .json: quad size, frame width, variant rows). A frame is FRAME_H pixels high
## and as wide as the species' crown needs (frame_w, TD-005: a fixed 1:2 frame left a broad crown
## half its texels). Until it is baked a procedural silhouette per species stands in, one row, so
## the far forest never disappears.

const FRAMES: int = 8
const DIR: String = "res://assets/generated/impostors"
## The stand-in's frame width; a baked species' own is in its .json (frame_w, FRAME_W_MIN..MAX).
const FRAME_W: int = 128
const FRAME_H: int = 256
const FRAME_W_MIN: int = 64
const FRAME_W_MAX: int = 256

static var _atlases: Dictionary = {}
static var _normals: Dictionary = {}
static var _sizes: Dictionary = {}
static var _meta: Dictionary = {}
static var _winter: Dictionary = {}
static var _mutex := Mutex.new()


static func atlas_path(sp_id: StringName) -> String:
	return "%s/%s.png" % [DIR, sp_id]


static func is_baked(sp: SpeciesDef) -> bool:
	return ResourceLoader.exists(atlas_path(sp.id))


## Albedo (rgb) + coverage (a) atlas, FRAMES frames side by side.
static func atlas_for(sp: SpeciesDef) -> Texture2D:
	_mutex.lock()
	var tex: Texture2D = _atlases.get(sp.id)
	_mutex.unlock()
	if tex != null:
		return tex
	if is_baked(sp):
		tex = load(atlas_path(sp.id)) as Texture2D
	if tex == null:
		tex = ImageTexture.create_from_image(_placeholder(sp))
	_mutex.lock()
	_atlases[sp.id] = tex
	_mutex.unlock()
	return tex


## Frame-space normals (x right, y up, z toward camera, packed 0..1), or null (shader fakes them).
static func normal_atlas_for(sp: SpeciesDef) -> Texture2D:
	if _normals.has(sp.id):
		return _normals[sp.id]
	var path: String = "%s/%s_n.png" % [DIR, sp.id]
	var tex: Texture2D = load(path) as Texture2D if ResourceLoader.exists(path) else null
	_normals[sp.id] = tex
	return tex


## Bare-branch atlas of a deciduous species (same layout, baked in winter), or null.
static func winter_atlas_for(sp: SpeciesDef) -> Texture2D:
	_mutex.lock()
	var known: bool = _winter.has(sp.id)
	var tex: Texture2D = _winter.get(sp.id)
	_mutex.unlock()
	if known:
		return tex
	var path: String = "%s/%s_winter.png" % [DIR, sp.id]
	tex = load(path) as Texture2D if sp.deciduous and ResourceLoader.exists(path) else null
	_mutex.lock()
	_winter[sp.id] = tex
	_mutex.unlock()
	return tex


## A frame's pixel width for a crown `width` m across in a frame `height` m high (FRAME_H pixels):
## the crown's own aspect, in steps of 16 pixels.
static func frame_width(width: float, height: float) -> int:
	var px: float = float(FRAME_H) * width / maxf(height, 0.01)
	return clampi(int(ceil(px / 16.0)) * 16, FRAME_W_MIN, FRAME_W_MAX)


## Quad (width, height) in metres for an instance scale of 1 (instance scale multiplies it).
static func size_for(sp: SpeciesDef) -> Vector2:
	_mutex.lock()
	var known: bool = _sizes.has(sp.id)
	var cached: Vector2 = _sizes.get(sp.id, Vector2.ZERO)
	_mutex.unlock()
	if known:
		return cached
	var dims := Vector2(6.4, 21.0) if not _is_broadleaf(sp) else Vector2(6.4, 14.5)
	var d: Dictionary = _meta_of(sp)
	if not d.is_empty():
		dims = Vector2(float(d.get("width", dims.x)), float(d.get("height", dims.y)))
	_mutex.lock()
	_sizes[sp.id] = dims
	_mutex.unlock()
	return dims


## Variant rows in the species' atlas: 1 for an atlas baked before rows (the first model only) or
## the stand-in. A tree whose variant has no row shows the first.
static func variants_for(sp: SpeciesDef) -> int:
	return maxi(1, int(_meta_of(sp).get("variants", 1)))


## The bake's .json for a species ({} if not baked), read once.
static func _meta_of(sp: SpeciesDef) -> Dictionary:
	_mutex.lock()
	var known: bool = _meta.has(sp.id)
	var out: Dictionary = _meta.get(sp.id, {})
	_mutex.unlock()
	if known:
		return out
	var meta_path: String = "%s/%s.json" % [DIR, sp.id]
	if FileAccess.file_exists(meta_path) and is_baked(sp):
		var j := JSON.new()
		if j.parse(FileAccess.get_file_as_string(meta_path)) == OK and j.data is Dictionary:
			out = j.data
	_mutex.lock()
	_meta[sp.id] = out
	_mutex.unlock()
	return out


## Seasonal foliage tints of a species ({"spring_tint": Color, ...}), read from the first
## foliage ShaderMaterial on its model, so far impostors follow the near canopy. Empty if none.
static func season_tints(sp: SpeciesDef) -> Dictionary:
	if sp.models.is_empty() or not ModelLibrary.has_model(sp.models[0]):
		return {}
	var mesh: Mesh = ModelLibrary.mesh(sp.models[0])
	for i: int in mesh.get_surface_count():
		var mat := mesh.surface_get_material(i) as ShaderMaterial
		if mat == null or mat.get_shader_parameter("autumn_tint") == null:
			continue
		var out: Dictionary = {}
		for k: String in ["spring_tint", "summer_tint", "autumn_tint", "winter_tint"]:
			var v: Variant = mat.get_shader_parameter(k)
			if v is Color:
				out[k] = v
		return out
	return {}


static func _is_broadleaf(sp: SpeciesDef) -> bool:
	return String(sp.id).contains("birch")


# --- Procedural stand-in ----------------------------------------------------------------------

## One silhouette frame repeated FRAMES times: conifer tiers or a broadleaf crown with a pale
## trunk, colour-varied with hashed noise so it does not read as a flat cut-out at distance.
static func _placeholder(sp: SpeciesDef) -> Image:
	var frame := Image.create(FRAME_W, FRAME_H, false, Image.FORMAT_RGBA8)
	frame.fill(Color(0, 0, 0, 0))
	var seed_i: int = Ids.hash31(String(sp.id))
	var broad: bool = _is_broadleaf(sp)
	var dead: bool = String(sp.id).contains("dead") or String(sp.id).contains("snag")
	var leaf := Color(0.09, 0.15, 0.08)
	if String(sp.id).contains("larch"):
		leaf = Color(0.33, 0.29, 0.1)
	elif broad:
		leaf = Color(0.42, 0.36, 0.12)
	var bark := Color(0.2, 0.15, 0.11) if not broad else Color(0.72, 0.7, 0.66)
	var cx: float = FRAME_W * 0.5
	for y: int in FRAME_H:
		# h: 0 at the top of the frame, 1 at the base.
		var h: float = float(y) / float(FRAME_H - 1)
		var trunk_half: float = lerpf(1.2, 3.5, h)
		for x: int in FRAME_W:
			var dx: float = absf(float(x) - cx)
			var n: float = _hash_noise(x, y, seed_i)
			var c := Color(0, 0, 0, 0)
			if dx < trunk_half and h > 0.08:
				c = bark * (0.85 + 0.3 * n)
				c.a = 1.0
			var crown: float = 0.0
			if dead:
				crown = 0.0
				if h < 0.75 and fposmod(h * 9.0 + n * 0.3, 1.0) < 0.12 and dx < (h * 0.9) * cx:
					c = bark * 0.8
					c.a = 1.0
			elif broad:
				var cy: float = 0.36
				var ry: float = 0.3
				var rx: float = cx * 0.92
				var e: float = pow(dx / rx, 2.0) + pow((h - cy) / ry, 2.0)
				crown = 1.0 - e - n * 0.35
			else:
				# Tiered cone: radius grows downwards with a saw-tooth per tier.
				if h > 0.02 and h < 0.86:
					var tier: float = fposmod(h * 7.0, 1.0)
					var r: float = (h - 0.02) * cx * 1.05 * (0.72 + 0.28 * tier)
					crown = 1.0 - dx / maxf(r, 0.001) - n * 0.25
			if crown > 0.0:
				var shade: float = 0.75 + 0.35 * n - 0.25 * h + 0.15 * (1.0 - dx / cx)
				c = Color(leaf.r * shade, leaf.g * shade, leaf.b * shade, 1.0)
			if c.a > 0.0:
				frame.set_pixel(x, y, c)
	var atlas := Image.create(FRAME_W * FRAMES, FRAME_H, false, Image.FORMAT_RGBA8)
	for i: int in FRAMES:
		atlas.blit_rect(frame, Rect2i(0, 0, FRAME_W, FRAME_H), Vector2i(i * FRAME_W, 0))
	atlas.generate_mipmaps()
	return atlas


static func _hash_noise(x: int, y: int, s: int) -> float:
	var h: int = (x * 374761393 + y * 668265263 + s * 2147483647) & 0x7fffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0x7fffffff
	return float(h & 0xffff) / 65535.0
