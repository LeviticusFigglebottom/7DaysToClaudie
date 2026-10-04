class_name HeightField
extends RefCounted
## Regular grid of heights on the XZ plane. Sample (ix, iz) sits at
## origin + Vector2(ix, iz) * spacing. Shared by terrain meshing, collision, scatter, AI.

var origin := Vector2.ZERO
var spacing: float = 1.0
var width: int = 0
var depth: int = 0
var heights: PackedFloat32Array = []


static func create(p_origin: Vector2, p_spacing: float, p_width: int, p_depth: int, fill: float = 0.0) -> HeightField:
	var hf := HeightField.new()
	hf.origin = p_origin
	hf.spacing = p_spacing
	hf.width = p_width
	hf.depth = p_depth
	hf.heights.resize(p_width * p_depth)
	hf.heights.fill(fill)
	return hf


func size_metres() -> Vector2:
	return Vector2((width - 1) * spacing, (depth - 1) * spacing)


func rect() -> Rect2:
	return Rect2(origin, size_metres())


func contains(x: float, z: float) -> bool:
	return x >= origin.x and z >= origin.y and x <= origin.x + (width - 1) * spacing and z <= origin.y + (depth - 1) * spacing


func get_h(ix: int, iz: int) -> float:
	ix = clampi(ix, 0, width - 1)
	iz = clampi(iz, 0, depth - 1)
	return heights[iz * width + ix]


func set_h(ix: int, iz: int, h: float) -> void:
	if ix >= 0 and iz >= 0 and ix < width and iz < depth:
		heights[iz * width + ix] = h


## Bilinear height at world (x, z); clamps at the edges.
func sample(x: float, z: float) -> float:
	var gx: float = (x - origin.x) / spacing
	var gz: float = (z - origin.y) / spacing
	var ix: int = clampi(int(floor(gx)), 0, width - 2)
	var iz: int = clampi(int(floor(gz)), 0, depth - 2)
	var fx: float = clampf(gx - ix, 0.0, 1.0)
	var fz: float = clampf(gz - iz, 0.0, 1.0)
	var i: int = iz * width + ix
	var h00: float = heights[i]
	var h10: float = heights[i + 1]
	var h01: float = heights[i + width]
	var h11: float = heights[i + width + 1]
	return lerpf(lerpf(h00, h10, fx), lerpf(h01, h11, fx), fz)


func normal_at(x: float, z: float) -> Vector3:
	var e: float = spacing
	var hl: float = sample(x - e, z)
	var hr: float = sample(x + e, z)
	var hd: float = sample(x, z - e)
	var hu: float = sample(x, z + e)
	return Vector3(hl - hr, 2.0 * e, hd - hu).normalized()


func slope_deg(x: float, z: float) -> float:
	return rad_to_deg(acos(clampf(normal_at(x, z).y, -1.0, 1.0)))


## Grid normal from central differences (index space, fast path for meshing).
func grid_normal(ix: int, iz: int) -> Vector3:
	var hl: float = get_h(ix - 1, iz)
	var hr: float = get_h(ix + 1, iz)
	var hd: float = get_h(ix, iz - 1)
	var hu: float = get_h(ix, iz + 1)
	return Vector3(hl - hr, 2.0 * spacing, hd - hu).normalized()


## Height range over a grid rect (inclusive).
func min_max(ix0: int, iz0: int, ix1: int, iz1: int) -> Vector2:
	var lo: float = INF
	var hi: float = -INF
	for iz: int in range(maxi(iz0, 0), mini(iz1, depth - 1) + 1):
		var row: int = iz * width
		for ix: int in range(maxi(ix0, 0), mini(ix1, width - 1) + 1):
			var h: float = heights[row + ix]
			lo = minf(lo, h)
			hi = maxf(hi, h)
	return Vector2(lo, hi)


func to_bytes() -> PackedByteArray:
	var header := PackedFloat64Array([origin.x, origin.y, spacing, float(width), float(depth)])
	return header.to_byte_array() + heights.to_byte_array()


static func from_bytes(b: PackedByteArray) -> HeightField:
	var header: PackedFloat64Array = b.slice(0, 40).to_float64_array()
	var hf := HeightField.new()
	hf.origin = Vector2(header[0], header[1])
	hf.spacing = header[2]
	hf.width = int(header[3])
	hf.depth = int(header[4])
	hf.heights = b.slice(40).to_float32_array()
	return hf


## Stable content hash (SHA-256 hex of the raw heights; for determinism tests and caches).
func content_hash() -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(heights.to_byte_array())
	return ctx.finish().hex_encode()
