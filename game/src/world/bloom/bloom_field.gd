class_name BloomField
extends RefCounted
## Where the Bloom has taken the ground (ADR-0025): colonisation 0 (clean) .. 1 (the litter bound in
## mycelium, threads up the trunks, the plants dying back) on a low-resolution world-space grid over
## the built regions.
##
## Authored, not simulated: each built region's `bloom` features (a patch at a point, a seep along a
## polyline, or a patch anchored to one of the region's POI placements) plus the per-POI defaults in
## data/config/bloom.json (`poi_defaults`: buildings whose story kept the sick there). Seeded noise
## warps every zone into lobes and ragged tongues, so the same world always grows the same Bloom.
##
## Shaders read the grid as the global `hm_bloom_map` (R8, bilinear) over `hm_bloom_rect`; `at()`
## reads the same texels on the CPU, from any thread once built: the fungus scatter uses it, and so
## can infection exposure, Hollowed density or audio. `base` holds the authored field; `data` adds
## the dynamic spots (rooting mounds) on top, and is what the shaders and `at()` see.

const DEFAULT_TEXEL: float = 2.0
## Region feature type.
const FEATURE: String = "bloom"
## Keys a `bloom` feature may carry (anything else is reported: unknown fields are errors).
const FEATURE_KEYS: PackedStringArray = ["type", "id", "at", "points", "poi", "offset", "radius", "strength", "edge", "_doc"]

## One authored zone: a single point is a patch, two or more make a seep along the polyline.
class Zone:
	extends RefCounted
	var id: String = ""
	var points := PackedVector2Array()
	## Metres from the core (point or polyline) to the middle of the edge band.
	var radius: float = 30.0
	## Peak colonisation 0..1.
	var strength: float = 0.7
	## How ragged the edge is: 0 a soft circle .. 1 deep tongues.
	var edge: float = 0.5
	## Noise seed (world seed + zone id), so each zone grows its own shape.
	var seed: int = 0

	## Distance (m) from p to the zone's core.
	func core_distance(p: Vector2) -> float:
		if points.size() == 1:
			return p.distance_to(points[0])
		var best: float = INF
		for i: int in points.size() - 1:
			best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, points[i], points[i + 1])))
		return best

	## Where p lies around the zone's boundary, as a point on a loop as long as that boundary (m):
	## for a patch, the circle at the zone's radius in p's direction; for a seep, out along one side
	## of the line and back along the other, closed into a circle. Noise sampled there lobes the edge
	## and pushes tongues out, with no seam anywhere round the zone.
	func boundary_point(p: Vector2) -> Vector2:
		if points.size() == 1:
			var d: Vector2 = p - points[0]
			return d.normalized() * radius if d != Vector2.ZERO else Vector2(radius, 0.0)
		var best: float = INF
		var along: float = 0.0
		var acc: float = 0.0
		var side: float = 0.0
		for i: int in points.size() - 1:
			var a: Vector2 = points[i]
			var b: Vector2 = points[i + 1]
			var c: Vector2 = Geometry2D.get_closest_point_to_segment(p, a, b)
			var dist: float = p.distance_to(c)
			if dist < best:
				best = dist
				along = acc + a.distance_to(c)
				side = signf((b - a).cross(p - a))
			acc += a.distance_to(b)
		# The loop runs twice the line's length: the far side comes back the way the near side went.
		var s: float = along if side >= 0.0 else 2.0 * acc - along
		var ang: float = s / maxf(acc, 0.01) * PI
		return Vector2(cos(ang), sin(ang)) * (acc / PI)

	func bounds(margin: float) -> Rect2:
		var r := Rect2(points[0], Vector2.ZERO)
		for q: Vector2 in points:
			r = r.expand(q)
		return r.grow(margin)


## World rect the grid covers (the built regions).
var rect := Rect2()
var texel: float = DEFAULT_TEXEL
var width: int = 0
var depth: int = 0
## Authored field, R8 row-major (rows run along +Z).
var base := PackedByteArray()
## base + dynamic spots: what shaders and at() read.
var data := PackedByteArray()
var zones: Array[Zone] = []

# Shape parameters (data/config/bloom.json "field"); see _configure().
var _warp: float = 0.4
var _warp_scale: float = 0.9
var _lobe: float = 0.25
var _lobe_len: float = 0.8
var _tongue: float = 0.9
var _tongue_len: float = 0.22
var _edge_scale: float = 16.0
var _softness: float = 0.25
var _mottle: float = 0.3
var _mottle_scale: float = 12.0
var _default_edge: float = 0.5
var _spot_reach: float = 1.6
var _spots: Array = []
## The zones' texel boxes from compose() (mask_ground visits only these).
var _boxes: Array[Rect2i] = []


## The field of every built region in `regions` (region id -> RegionTerrain, as TerrainManager holds
## them), shaped by the config `cfg` (data/config/bloom.json). An empty field when nothing is authored.
static func build(world: WorldDef, regions: Dictionary, cfg: Dictionary) -> BloomField:
	var f := BloomField.new()
	f._configure(cfg.get("field", {}))
	var ids: Array = regions.keys()
	ids.sort()
	var cover := Rect2()
	for rid: Variant in ids:
		var rt: RegionTerrain = regions[rid]
		cover = rt.rect if cover.size == Vector2.ZERO else cover.merge(rt.rect)
		f.zones.append_array(region_zones(world.region_data(str(rid)) if world != null else {}, rt, cfg, world.seed if world != null else 0))
	f.compose(cover)
	f.mask_ground(regions)
	return f


## A field from explicit zones over `cover` (tests, tools).
static func from_zones(p_zones: Array[Zone], cover: Rect2, cfg: Dictionary = {}) -> BloomField:
	var f := BloomField.new()
	f._configure(cfg.get("field", {}))
	f.zones = p_zones
	f.compose(cover)
	return f


func _configure(c: Dictionary) -> void:
	texel = maxf(0.5, float(c.get("texel", DEFAULT_TEXEL)))
	_warp = float(c.get("warp", _warp))
	_warp_scale = maxf(0.05, float(c.get("warp_scale", _warp_scale)))
	_lobe = float(c.get("lobe", _lobe))
	_lobe_len = maxf(0.05, float(c.get("lobe_len", _lobe_len)))
	_tongue = float(c.get("tongue", _tongue))
	_tongue_len = maxf(0.02, float(c.get("tongue_len", _tongue_len)))
	_edge_scale = maxf(1.0, float(c.get("edge_scale", _edge_scale)))
	_softness = clampf(float(c.get("softness", _softness)), 0.02, 0.9)
	_mottle = clampf(float(c.get("mottle", _mottle)), 0.0, 1.0)
	_mottle_scale = maxf(1.0, float(c.get("mottle_scale", _mottle_scale)))
	_default_edge = float(c.get("edge", _default_edge))
	_spot_reach = maxf(1.0, float(c.get("spot_reach", _spot_reach)))


# --- Authoring -----------------------------------------------------------------------------------

## Zones of one region: its `bloom` features, then the POI defaults (cfg "poi_defaults", keyed by POI
## def) of its standalone POI placements. A feature anchored to a placement ("poi": placement id)
## replaces that placement's default. Malformed features are reported and skipped.
static func region_zones(region: Dictionary, rt: RegionTerrain, cfg: Dictionary, world_seed: int) -> Array[Zone]:
	var out: Array[Zone] = []
	var placements: Dictionary = {}
	if rt != null:
		for pl: Variant in rt.placements:
			if pl is Dictionary:
				placements[str((pl as Dictionary).get("id", ""))] = pl
	var rid: String = str(region.get("id", rt.region_id if rt != null else ""))
	var default_edge: float = float((cfg.get("field", {}) as Dictionary).get("edge", 0.5))
	var anchored: Dictionary = {}
	var k: int = 0
	for fv: Variant in region.get("features", []):
		if not fv is Dictionary or str((fv as Dictionary).get("type", "")) != FEATURE:
			continue
		var f: Dictionary = fv
		var where: String = "%s bloom #%d" % [rid, k]
		k += 1
		for key: Variant in f.keys():
			if not FEATURE_KEYS.has(str(key)) and not str(key).begins_with("_"):
				push_error("BloomField: %s has unknown field '%s'" % [where, key])
		var z := Zone.new()
		z.id = str(f.get("id", "%s:bloom_%d" % [rid, k - 1]))
		z.radius = float(f.get("radius", 30.0))
		z.strength = clampf(float(f.get("strength", 0.7)), 0.0, 1.0)
		z.edge = clampf(float(f.get("edge", default_edge)), 0.0, 1.0)
		if f.has("poi"):
			var pid: String = str(f["poi"])
			if not placements.has(pid):
				push_error("BloomField: %s anchors to unknown placement '%s'" % [where, pid])
				continue
			anchored[pid] = true
			z.points = PackedVector2Array([anchor(placements[pid], _v2(f.get("offset", [0, 0])))])
		elif f.has("points"):
			for q: Variant in f["points"]:
				z.points.append(_v2(q))
		elif f.has("at"):
			z.points = PackedVector2Array([_v2(f["at"])])
		if z.points.is_empty() or z.radius <= 0.0:
			push_error("BloomField: %s needs 'at', 'points' or 'poi' and a radius > 0" % where)
			continue
		z.seed = _zone_seed(world_seed, z.id)
		out.append(z)
	var defaults: Dictionary = cfg.get("poi_defaults", {})
	var pids: Array = placements.keys()
	pids.sort()
	for pid: Variant in pids:
		var pl: Dictionary = placements[pid]
		var def_id: String = str(pl.get("def", ""))
		if str(pl.get("kind", "")) != "poi" or anchored.has(pid) or not defaults.has(def_id):
			continue
		var d: Dictionary = defaults[def_id]
		var z := Zone.new()
		z.id = "%s:poi:%s" % [rid, pid]
		z.points = PackedVector2Array([anchor(pl, _v2(d.get("offset", [0, 0])))])
		z.radius = float(d.get("radius", 20.0))
		z.strength = clampf(float(d.get("strength", 0.6)), 0.0, 1.0)
		z.edge = clampf(float(d.get("edge", default_edge)), 0.0, 1.0)
		z.seed = _zone_seed(world_seed, z.id)
		out.append(z)
	return out


## World XZ of a point given in a placement's own frame: `offset` metres from the footprint's centre,
## +x along its width, +z toward its front (POI plans face +Z; ADR-0009).
static func anchor(placement: Dictionary, offset: Vector2) -> Vector2:
	var o: Array = placement.get("origin", [0, 0, 0])
	var origin := Vector2(float(o[0]), float(o[2]) if o.size() > 2 else float(o[1]))
	var s: Array = placement.get("size", [0, 0])
	var rot: float = deg_to_rad(float(placement.get("rotation", 0.0)))
	return origin + (Vector2(float(s[0]), float(s[1])) * 0.5 + offset).rotated(rot)


static func _zone_seed(world_seed: int, id: String) -> int:
	return Ids.derive_seed(world_seed, "bloom:" + id) & 0x7FFFFFFF


static func _v2(a: Variant) -> Vector2:
	if a is Array and (a as Array).size() >= 2:
		return Vector2(float(a[0]), float(a[1]))
	return Vector2.ZERO


# --- Composition ---------------------------------------------------------------------------------

## How far (in radii) from its core a zone can reach once lobed, tongued, warped and frayed.
func reach(z: Zone) -> float:
	return (1.0 + _lobe * 0.6 + _tongue * z.edge * 0.6) * (1.0 + _softness) + 0.5 * z.edge + _warp


## Rasterises every zone onto a grid over `cover` (texel centres), merged as a soft union so overlaps
## thicken without creasing.
func compose(cover: Rect2) -> void:
	width = maxi(0, int(ceil(cover.size.x / texel)))
	depth = maxi(0, int(ceil(cover.size.y / texel)))
	# The grid's own extent (whole texels), so at() and the shaders map positions the same way.
	rect = Rect2(cover.position, Vector2(width, depth) * texel)
	base = PackedByteArray()
	base.resize(width * depth)
	if width == 0 or depth == 0 or zones.is_empty():
		data = base.duplicate()
		return
	var clean := PackedFloat32Array()
	clean.resize(width * depth)
	clean.fill(1.0)
	var boxes: Array[Rect2i] = []
	var mottle := FastNoiseLite.new()
	mottle.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	mottle.fractal_octaves = 2
	mottle.frequency = 1.0 / _mottle_scale
	for z: Zone in zones:
		mottle.seed = z.seed ^ 0x5bd1
		var warp := FastNoiseLite.new()
		warp.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		warp.seed = z.seed
		warp.fractal_octaves = 2
		warp.frequency = 1.0 / (z.radius * _warp_scale)
		var edge := FastNoiseLite.new()
		edge.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		edge.seed = z.seed ^ 0x2c1b
		edge.fractal_octaves = 3
		edge.frequency = 1.0 / _edge_scale
		# Along the boundary: broad lobes, and sparse tongues pushing far out (tapering, since a
		# spike in the radius narrows the further out it reaches).
		var lobes := FastNoiseLite.new()
		lobes.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		lobes.seed = z.seed ^ 0x4e7
		lobes.fractal_octaves = 2
		lobes.frequency = 1.0 / (_lobe_len * z.radius)
		var tongues := FastNoiseLite.new()
		tongues.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		tongues.seed = z.seed ^ 0x77f3
		tongues.fractal_octaves = 1
		tongues.frequency = 1.0 / (_tongue_len * z.radius)
		var box: Rect2 = z.bounds(z.radius * reach(z) + texel).intersection(cover)
		if box.size == Vector2.ZERO:
			continue
		var i0: int = clampi(int(floor((box.position.x - cover.position.x) / texel)), 0, width - 1)
		var i1: int = clampi(int(ceil((box.end.x - cover.position.x) / texel)), 0, width - 1)
		var j0: int = clampi(int(floor((box.position.y - cover.position.y) / texel)), 0, depth - 1)
		var j1: int = clampi(int(ceil((box.end.y - cover.position.y) / texel)), 0, depth - 1)
		var far: float = reach(z)
		boxes.append(Rect2i(i0, j0, i1 - i0 + 1, j1 - j0 + 1))
		for j: int in range(j0, j1 + 1):
			var pz: float = cover.position.y + (j + 0.5) * texel
			for i: int in range(i0, i1 + 1):
				var p := Vector2(cover.position.x + (i + 0.5) * texel, pz)
				if z.core_distance(p) > far * z.radius:
					continue
				var v: float = _zone_value(z, p, warp, edge, mottle, lobes, tongues)
				if v > 0.0:
					clean[j * width + i] *= 1.0 - v
	# Only the zones' boxes hold anything (the rest of the region stays 0).
	_boxes = boxes
	for b: Rect2i in boxes:
		for j: int in range(b.position.y, b.end.y):
			for i: int in range(b.position.x, b.end.x):
				base[j * width + i] = int(round(clampf(1.0 - clean[j * width + i], 0.0, 1.0) * 255.0))
	data = base.duplicate()
	if not _spots.is_empty():
		_apply_spots(Rect2i(0, 0, width, depth))


## Nothing takes on water, roads, paths, building pads or clearings: the authored field is scaled by
## the regions' vegetation allowance (RegionTerrain.vegmask, 1 m), averaged over each texel.
func mask_ground(regions: Dictionary) -> void:
	if width == 0 or depth == 0:
		return
	var h: float = texel * 0.25
	# Only the zones' boxes can hold anything (compose); a whole-map field of a streamed world is
	# tens of millions of texels, nearly all empty. Boxes overlap: each texel is masked once.
	var done := PackedByteArray()
	done.resize(width * depth)
	for b: Rect2i in _boxes:
		for j: int in range(b.position.y, b.end.y):
			var z: float = rect.position.y + (j + 0.5) * texel
			for i: int in range(b.position.x, b.end.x):
				var k: int = j * width + i
				if base[k] == 0 or done[k] != 0:
					continue
				done[k] = 1
				_mask_texel(regions, k, rect.position.x + (i + 0.5) * texel, z, h)
	data = base.duplicate()
	if not _spots.is_empty():
		_apply_spots(Rect2i(0, 0, width, depth))


func _mask_texel(regions: Dictionary, k: int, x: float, z: float, h: float) -> void:
	for rv: Variant in regions.values():
		var rt: RegionTerrain = rv
		if rt.rect.has_point(Vector2(x, z)):
			var veg: float = (rt.veg_at(x - h, z - h) + rt.veg_at(x + h, z - h) + rt.veg_at(x - h, z + h) + rt.veg_at(x + h, z + h)) * 0.25
			base[k] = int(round(base[k] * smoothstep(0.05, 0.6, veg)))
			return


## A zone's colonisation at p, before quantisation. The radius swells and shrinks along the
## boundary (lobes) and shoots out tongues; the point is taken through a domain warp, which bends
## them, and the edge frays at metre scale; then the value fades across the edge band and is
## mottled inside, so the colonised ground isn't one even sheet.
func _zone_value(z: Zone, p: Vector2, warp: FastNoiseLite, edge: FastNoiseLite, mottle: FastNoiseLite,
		lobes: FastNoiseLite, tongues: FastNoiseLite) -> float:
	var q: Vector2 = p + Vector2(warp.get_noise_2d(p.x, p.y), warp.get_noise_2d(p.x + 731.0, p.y - 419.0)) * (_warp * z.radius)
	var b: Vector2 = z.boundary_point(q)
	var spike: float = maxf(0.0, tongues.get_noise_2dv(b))
	var r_eff: float = z.radius * (1.0 + _lobe * lobes.get_noise_2dv(b) + _tongue * z.edge * spike * spike * 2.2)
	var d: float = z.core_distance(q) / r_eff + edge.get_noise_2d(p.x, p.y) * z.edge * 0.35
	var v: float = 1.0 - smoothstep(1.0 - _softness, 1.0 + _softness, d)
	if v <= 0.0:
		return 0.0
	v *= 1.0 - _mottle * (0.5 + 0.5 * mottle.get_noise_2d(p.x, p.y)) * smoothstep(0.2, 0.8, v)
	return z.strength * v


# --- Dynamic spots (rooting mounds) --------------------------------------------------------------

## Replaces the dynamic spots: [{pos: Vector2, radius: float, strength: float}]. Returns the texel
## rect that changed (empty when nothing did), for a partial texture update.
func set_spots(spots: Array) -> Rect2i:
	var dirty := Rect2i()
	for s: Variant in _spots + spots:
		var r: Rect2i = _spot_texels(s)
		if r.size != Vector2i.ZERO:
			dirty = r if dirty.size == Vector2i.ZERO else dirty.merge(r)
	_spots = spots.duplicate(true)
	if dirty.size != Vector2i.ZERO:
		_apply_spots(dirty)
	return dirty


func _spot_texels(s: Dictionary) -> Rect2i:
	if width == 0 or depth == 0:
		return Rect2i()
	var p: Vector2 = s.get("pos", Vector2.ZERO)
	var r: float = float(s.get("radius", 2.0)) * _spot_reach + texel
	if not rect.grow(r).has_point(p):
		return Rect2i()
	var i0: int = clampi(int(floor((p.x - r - rect.position.x) / texel)), 0, width - 1)
	var i1: int = clampi(int(ceil((p.x + r - rect.position.x) / texel)), 0, width - 1)
	var j0: int = clampi(int(floor((p.y - r - rect.position.y) / texel)), 0, depth - 1)
	var j1: int = clampi(int(ceil((p.y + r - rect.position.y) / texel)), 0, depth - 1)
	return Rect2i(i0, j0, i1 - i0 + 1, j1 - j0 + 1)


## data = base, then each spot unioned in over `area` (texels).
func _apply_spots(area: Rect2i) -> void:
	for j: int in range(area.position.y, area.end.y):
		for i: int in range(area.position.x, area.end.x):
			data[j * width + i] = base[j * width + i]
	for sv: Variant in _spots:
		var s: Dictionary = sv
		var r: Rect2i = _spot_texels(s).intersection(area)
		if r.size == Vector2i.ZERO:
			continue
		var p: Vector2 = s.get("pos", Vector2.ZERO)
		var rad: float = maxf(0.1, float(s.get("radius", 2.0)))
		var st: float = clampf(float(s.get("strength", 0.8)), 0.0, 1.0)
		for j: int in range(r.position.y, r.end.y):
			for i: int in range(r.position.x, r.end.x):
				var q := Vector2(rect.position.x + (i + 0.5) * texel, rect.position.y + (j + 0.5) * texel)
				var v: float = st * (1.0 - smoothstep(rad * 0.5, rad * _spot_reach, q.distance_to(p)))
				if v <= 0.0:
					continue
				var cur: float = data[j * width + i] / 255.0
				data[j * width + i] = int(round(clampf(1.0 - (1.0 - cur) * (1.0 - v), 0.0, 1.0) * 255.0))


# --- Queries -------------------------------------------------------------------------------------

func is_empty() -> bool:
	return width == 0 or depth == 0 or (zones.is_empty() and _spots.is_empty())


## Colonisation at world (x, z), 0..1, as the shaders see it (bilinear between texel centres; 0 off
## the grid). Thread-safe for reads.
func at(x: float, z: float) -> float:
	return _sample(data, x, z)


## The authored field only, without the dynamic spots: deterministic for a given world, which the
## vegetation scatter needs.
func base_at(x: float, z: float) -> float:
	return _sample(base, x, z)


func _sample(arr: PackedByteArray, x: float, z: float) -> float:
	if width == 0 or depth == 0 or not rect.has_point(Vector2(x, z)):
		return 0.0
	var fx: float = (x - rect.position.x) / texel - 0.5
	var fz: float = (z - rect.position.y) / texel - 0.5
	var i0: int = clampi(int(floor(fx)), 0, width - 1)
	var j0: int = clampi(int(floor(fz)), 0, depth - 1)
	var i1: int = mini(i0 + 1, width - 1)
	var j1: int = mini(j0 + 1, depth - 1)
	var tx: float = clampf(fx - i0, 0.0, 1.0)
	var tz: float = clampf(fz - j0, 0.0, 1.0)
	var a: float = lerpf(arr[j0 * width + i0], arr[j0 * width + i1], tx)
	var b: float = lerpf(arr[j1 * width + i0], arr[j1 * width + i1], tx)
	return lerpf(a, b, tz) / 255.0


## The strongest zone whose core is within `radius` of (x, z) metres, or null.
func zone_near(x: float, z: float, radius: float = 0.0) -> Zone:
	var best: Zone = null
	var best_d: float = INF
	for zn: Zone in zones:
		var d: float = zn.core_distance(Vector2(x, z)) - zn.radius - radius
		if d <= 0.0 and d < best_d:
			best = zn
			best_d = d
	return best


## Shader global hm_bloom_rect: (x0, z0, 1/width, 1/depth) in metres; zero when empty.
func shader_rect() -> Vector4:
	if width == 0 or depth == 0:
		return Vector4.ZERO
	return Vector4(rect.position.x, rect.position.y, 1.0 / (width * texel), 1.0 / (depth * texel))


## The grid as an R8 image (row 0 = the rect's -Z edge), for the shader global.
func image() -> Image:
	if width == 0 or depth == 0:
		return Image.create(1, 1, false, Image.FORMAT_R8)
	return Image.create_from_data(width, depth, false, Image.FORMAT_R8, data)
