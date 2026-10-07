class_name BloomTiles
extends RefCounted
## The Bloom field (ADR-0025) of a whole world, held as tiles (RWG_V2_PLAN §2, ADR-0038 §7): the
## same 2 m grid BloomField rasterises, cut into 256 m tiles (128 x 128 texels) so a streamed
## world never holds or composes the whole map at once (a 10 km map was a 25 MB field, 50 MB
## with the spots copy, and a 100 MB float array while it composed: 16 s of a 27 s load).
##
## * Every zone of the world is known from the start (region features and POI defaults are data);
##   a tile is composed from the zones that reach it, exactly as BloomField.compose() would compose
##   those texels over the whole map, then masked by the ground of the region it lies in.
## * Only tiles some zone reaches hold anything. The tiles of the regions loaded at 1 m are
##   composed up front (WorldLoader, on its thread); in a streamed world the rest are composed on a
##   worker as the player comes near (BloomWorld) with the region's 16 m vegetation mask, composed
##   again with its 1 m mask when the region attaches (on the region streamer's worker, installed
##   by TerrainManager.attach_region), and freed when the player is far away.
## * at()/base_at() answer anywhere, from any thread: from a tile when it is there, else from the
##   zones directly (the four texels around the point, the same numbers a tile would hold).
## * The dynamic spots (rooting mounds) are applied per tile on top of the authored base.
##
## Threads: the zones, their noises and the zone index never change after build(). Tiles are
## immutable once published (a re-mask or a spot change publishes a new Tile); `_tiles` and
## `_spots` are only touched under `_mutex`, by the main thread when writing.

## Texels per tile side (256 m at 2 m texels).
const TILE: int = 128

## One published tile: never written after install().
class Tile:
	extends RefCounted
	var key := Vector2i.ZERO
	## Texels of this tile (edge tiles of a map whose size isn't a whole number of tiles are smaller).
	var w: int = 0
	var d: int = 0
	## Authored field, masked (R8, row-major); `data` adds the spots (the same array when none
	## reach the tile).
	var base := PackedByteArray()
	var data := PackedByteArray()
	## Masked by a 1 m vegetation mask (an attached region's), not a coarse one.
	var fine: bool = false
	## `data` is an array of its own (spots reach the tile), not `base`.
	var own_data: bool = false


## The grid's extent (whole texels from the cover's corner), as BloomField.rect.
var rect := Rect2()
var texel: float = BloomField.DEFAULT_TEXEL
var width: int = 0
var depth: int = 0
## Tiles across and down.
var cols: int = 0
var rows: int = 0
var zones: Array[BloomField.Zone] = []
## Tiles not composed up front are composed near the player by BloomWorld, and freed far away
## (streamed worlds). Otherwise every tile is composed by build() and kept.
var lazy: bool = false
## (x, z) -> RegionTerrain whose ground masks a texel there (null: unmasked). Set before any
## reader runs and never replaced (thread-safe callables only: TerrainManager.ground_terrain_at).
var mask_fn: Callable

var _shape: BloomField
## Per zone: its noises (BloomField.noises).
var _noise: Array = []
## Tile key -> PackedInt32Array of the zones (indices, in zone order) that reach it.
var _zone_tiles: Dictionary = {}
var _mutex := Mutex.new()
## Tile key -> Tile. Under _mutex.
var _tiles: Dictionary = {}
## The spots, each [texel box (Rect2i), pos, radius, strength]. Replaced whole under _mutex.
var _spots: Array = []
## Tile keys published since the last take_dirty() (main thread).
var _dirty: Dictionary = {}


## The field of `regions` (region id -> RegionTerrain: every region the field covers, its zones'
## source and its ground). The tiles of 1 m regions are composed now; the others too unless
## `streamed`, when BloomWorld composes them near the player.
static func build(world: WorldDef, regions: Dictionary, cfg: Dictionary, streamed: bool) -> BloomTiles:
	var ids: Array = regions.keys()
	ids.sort()
	var cover := Rect2()
	var zs: Array[BloomField.Zone] = []
	for rid: Variant in ids:
		var rt: RegionTerrain = regions[rid]
		cover = rt.rect if cover.size == Vector2.ZERO else cover.merge(rt.rect)
		zs.append_array(BloomField.region_zones(world.region_data(str(rid)) if world != null else {}, rt, cfg, world.seed if world != null else 0))
	var t := BloomTiles.new()
	t.lazy = streamed
	t._setup(zs, cover, cfg)
	# Until the terrain takes over (BloomWorld.setup), the ground is these regions'.
	var by_rect: Array = []
	for rid2: Variant in ids:
		by_rect.append(regions[rid2])
	t.mask_fn = func(x: float, z: float) -> RegionTerrain:
		for rv: Variant in by_rect:
			if (rv as RegionTerrain).rect.has_point(Vector2(x, z)):
				return rv
		return null
	var made: Dictionary = {}
	for rid3: Variant in ids:
		var rt3: RegionTerrain = regions[rid3]
		if streamed and rt3.spacing > 1.0:
			continue
		for tv: Variant in t.compose_region(rt3, regions):
			made[(tv as Tile).key] = tv
	if not streamed:
		# Tiles in no given region (inside the cover's box, between built regions) stay unmasked,
		# as the whole-map field left them.
		for key: Vector2i in t._zone_tiles:
			if not made.has(key):
				var g: Dictionary = {}
				for rid4: Variant in ids:
					if (regions[rid4] as RegionTerrain).rect.intersects(t.tile_rect(key)):
						g[rid4] = regions[rid4]
				made[key] = t.compose_tile(key, g)
	t.install(made.values())
	t._dirty.clear()
	return t


## A field of explicit zones over `cover` (tests, tools), masked by `ground` (region id ->
## RegionTerrain; unmasked where none is); every tile composed now unless not `compose_now`.
static func from_zones(p_zones: Array[BloomField.Zone], cover: Rect2, cfg: Dictionary = {}, ground: Dictionary = {},
		compose_now: bool = true) -> BloomTiles:
	var t := BloomTiles.new()
	t._setup(p_zones, cover, cfg)
	var rts: Array = ground.values()
	t.mask_fn = func(x: float, z: float) -> RegionTerrain:
		for rv: Variant in rts:
			if (rv as RegionTerrain).rect.has_point(Vector2(x, z)):
				return rv
		return null
	if compose_now:
		var made: Array = []
		for key: Vector2i in t._zone_tiles:
			var g: Dictionary = {}
			for rid: Variant in ground:
				if (ground[rid] as RegionTerrain).rect.intersects(t.tile_rect(key)):
					g[rid] = ground[rid]
			made.append(t.compose_tile(key, g))
		t.install(made)
		t._dirty.clear()
	return t


func _setup(p_zones: Array[BloomField.Zone], cover: Rect2, cfg: Dictionary) -> void:
	_shape = BloomField.shaped(cfg)
	texel = _shape.texel
	zones = p_zones
	width = maxi(0, int(ceil(cover.size.x / texel)))
	depth = maxi(0, int(ceil(cover.size.y / texel)))
	rect = Rect2(cover.position, Vector2(width, depth) * texel)
	cols = (width + TILE - 1) / TILE
	rows = (depth + TILE - 1) / TILE
	for zi: int in zones.size():
		var z: BloomField.Zone = zones[zi]
		_noise.append(_shape.noises(z))
		# The texels compose() would visit for the zone (its box), as tiles.
		var box: Rect2 = z.bounds(z.radius * _shape.reach(z) + texel).intersection(rect)
		if box.size == Vector2.ZERO or width == 0 or depth == 0:
			continue
		var i0: int = clampi(int(floor((box.position.x - rect.position.x) / texel)), 0, width - 1)
		var i1: int = clampi(int(ceil((box.end.x - rect.position.x) / texel)), 0, width - 1)
		var j0: int = clampi(int(floor((box.position.y - rect.position.y) / texel)), 0, depth - 1)
		var j1: int = clampi(int(ceil((box.end.y - rect.position.y) / texel)), 0, depth - 1)
		for tj: int in range(j0 / TILE, j1 / TILE + 1):
			for ti: int in range(i0 / TILE, i1 / TILE + 1):
				var key := Vector2i(ti, tj)
				var list: PackedInt32Array = _zone_tiles.get(key, PackedInt32Array())
				list.append(zi)
				_zone_tiles[key] = list


# --- Tiles ---------------------------------------------------------------------------------------

## A tile's texels in the grid.
func tile_texels(key: Vector2i) -> Rect2i:
	return Rect2i(key * TILE, Vector2i(TILE, TILE)).intersection(Rect2i(0, 0, width, depth))


## A tile's world rect.
func tile_rect(key: Vector2i) -> Rect2:
	var r: Rect2i = tile_texels(key)
	return Rect2(rect.position + Vector2(r.position) * texel, Vector2(r.size) * texel)


## The tile holding world (x, z) (may lie off the grid).
func tile_of(x: float, z: float) -> Vector2i:
	return Vector2i(int(floor((x - rect.position.x) / (TILE * texel))), int(floor((z - rect.position.y) / (TILE * texel))))


## Whether any zone reaches the tile.
func has_zones(key: Vector2i) -> bool:
	return _zone_tiles.has(key)


## Tiles some zone reaches (the only ones that can hold the authored field).
func zone_tiles() -> Array:
	return _zone_tiles.keys()


func is_composed(key: Vector2i) -> bool:
	_mutex.lock()
	var has: bool = _tiles.has(key)
	_mutex.unlock()
	return has


## The published tile at `key`, or null. Any thread.
func tile(key: Vector2i) -> Tile:
	_mutex.lock()
	var t: Tile = _tiles.get(key)
	_mutex.unlock()
	return t


## Composes one tile from the zones that reach it, masked by the ground of `ground` (region id ->
## RegionTerrain; a texel in none of them stays unmasked). Pure: any thread.
func compose_tile(key: Vector2i, ground: Dictionary) -> Tile:
	var t := Tile.new()
	t.key = key
	var tr: Rect2i = tile_texels(key)
	t.w = tr.size.x
	t.d = tr.size.y
	var idx: PackedInt32Array = _zone_tiles.get(key, PackedInt32Array())
	if idx.is_empty():
		t.base.resize(t.w * t.d)
		t.data = t.base
		return t
	var f := BloomField.new()
	f.texel = texel
	_shape_into(f)
	var noise: Array = []
	for zi: int in idx:
		f.zones.append(zones[zi])
		noise.append(_noise[zi])
	f.compose(tile_rect(key), noise)
	if not ground.is_empty():
		f.mask_ground(ground)
	t.base = f.base
	t.data = t.base
	var fine: bool = not ground.is_empty()
	for rv: Variant in ground.values():
		fine = fine and (rv as RegionTerrain).spacing <= 1.0
	t.fine = fine
	return t


## The tiles over a region that some zone reaches, masked by its ground (and `ground`'s, for a tile
## reaching past it; default: the region alone). Pure: any thread (the region streamer's worker).
func compose_region(rt: RegionTerrain, ground: Dictionary = {}) -> Array:
	var out: Array = []
	if width == 0 or depth == 0:
		return out
	var a: Vector2i = tile_of(rt.rect.position.x + 0.5 * texel, rt.rect.position.y + 0.5 * texel)
	var b: Vector2i = tile_of(rt.rect.end.x - 0.5 * texel, rt.rect.end.y - 0.5 * texel)
	for tj: int in range(maxi(a.y, 0), mini(b.y, rows - 1) + 1):
		for ti: int in range(maxi(a.x, 0), mini(b.x, cols - 1) + 1):
			var key := Vector2i(ti, tj)
			if not _zone_tiles.has(key):
				continue
			var tr: Rect2 = tile_rect(key)
			var g: Dictionary = {rt.region_id: rt}
			for rv: Variant in ground.values():
				var o: RegionTerrain = rv
				if o != rt and o.rect.intersects(tr):
					g[o.region_id] = o
			out.append(compose_tile(key, g))
	return out


## Publishes composed tiles (main thread): the spots go on top. A tile masked at 16 m never
## replaces one masked at 1 m (a worker's coarse tile can land after its region attached).
func install(made: Array) -> void:
	_mutex.lock()
	var spots: Array = _spots
	_mutex.unlock()
	for tv: Variant in made:
		var t: Tile = tv
		var cur: Tile = tile(t.key)
		if cur != null and cur.fine and not t.fine:
			continue
		var pub: Tile = _with_spots(t, spots)
		_mutex.lock()
		_tiles[t.key] = pub
		_mutex.unlock()
		_dirty[t.key] = true


## Frees the tiles farther than `radius` tiles (Chebyshev) from `centre`, unless `keep(key)`
## (main thread). Returns how many went.
func free_far(centre: Vector2i, radius: int, keep: Callable = Callable()) -> int:
	var gone: Array = []
	_mutex.lock()
	for k: Variant in _tiles.keys():
		var key: Vector2i = k
		if maxi(absi(key.x - centre.x), absi(key.y - centre.y)) > radius and not (keep.is_valid() and bool(keep.call(key))):
			gone.append(key)
	for key2: Vector2i in gone:
		_tiles.erase(key2)
	_mutex.unlock()
	return gone.size()


## Tiles within `area` (tile coords) that should hold something and aren't composed, nearest to
## `centre` first.
func missing(area: Rect2i, centre: Vector2i) -> Array:
	var out: Array = []
	_mutex.lock()
	var spots: Array = _spots
	for tj: int in range(maxi(area.position.y, 0), mini(area.end.y, rows)):
		for ti: int in range(maxi(area.position.x, 0), mini(area.end.x, cols)):
			var key := Vector2i(ti, tj)
			if not _tiles.has(key) and (_zone_tiles.has(key) or _spot_reaches(spots, key)):
				out.append(key)
	_mutex.unlock()
	out.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return maxi(absi(a.x - centre.x), absi(a.y - centre.y)) < maxi(absi(b.x - centre.x), absi(b.y - centre.y)))
	return out


## Tile keys published since the last call (main thread; BloomWorld redraws them).
func take_dirty() -> Array:
	var out: Array = _dirty.keys()
	_dirty.clear()
	return out


## Bytes the published tiles hold (a tile without spots shares one array for base and data).
func memory_bytes() -> int:
	var n: int = 0
	_mutex.lock()
	for tv: Variant in _tiles.values():
		var t: Tile = tv
		n += t.base.size() + (t.data.size() if t.own_data else 0)
	_mutex.unlock()
	return n


func tile_count() -> int:
	_mutex.lock()
	var n: int = _tiles.size()
	_mutex.unlock()
	return n


## The tiles' data over `texels` (grid texels, clipped to the grid) as one R8 image: the window
## BloomWorld puts on screen. Tiles not composed read clean. Any thread.
func window_image(texels: Rect2i) -> Image:
	var r: Rect2i = texels.intersection(Rect2i(0, 0, width, depth))
	if r.size.x <= 0 or r.size.y <= 0:
		return Image.create(1, 1, false, Image.FORMAT_R8)
	var img := Image.create(r.size.x, r.size.y, false, Image.FORMAT_R8)
	for tj: int in range(r.position.y / TILE, (r.end.y - 1) / TILE + 1):
		for ti: int in range(r.position.x / TILE, (r.end.x - 1) / TILE + 1):
			blit_tile(img, r.position, Vector2i(ti, tj))
	return img


## Draws one tile into a window image whose texel (0, 0) is grid texel `origin` (clean where the
## tile isn't composed). Any thread.
func blit_tile(img: Image, origin: Vector2i, key: Vector2i) -> void:
	var tr: Rect2i = tile_texels(key)
	var dst: Rect2i = tr.intersection(Rect2i(origin, img.get_size()))
	if dst.size.x <= 0 or dst.size.y <= 0:
		return
	var t: Tile = tile(key)
	if t == null:
		img.fill_rect(Rect2i(dst.position - origin, dst.size), Color(0, 0, 0))
		return
	var src := Image.create_from_data(t.w, t.d, false, Image.FORMAT_R8, t.data)
	img.blit_rect(src, Rect2i(dst.position - tr.position, dst.size), dst.position - origin)


# --- Spots ---------------------------------------------------------------------------------------

## Replaces the dynamic spots: [{pos: Vector2, radius: float, strength: float}] (main thread).
## Every tile either set touches is published again; a spot over a tile nothing composed yet
## (no zone reaches it) gets a tile of its own. Returns the tiles that changed.
func set_spots(spots: Array) -> Array:
	var next: Array = []
	for sv: Variant in spots:
		var s: Dictionary = sv
		var box: Rect2i = _spot_texels(s)
		if box.size != Vector2i.ZERO:
			next.append([box, s.get("pos", Vector2.ZERO) as Vector2, maxf(0.1, float(s.get("radius", 2.0))), clampf(float(s.get("strength", 0.8)), 0.0, 1.0)])
	_mutex.lock()
	var prev: Array = _spots
	_spots = next
	_mutex.unlock()
	var touched: Dictionary = {}
	for sp: Variant in prev + next:
		var box2: Rect2i = (sp as Array)[0]
		for tj: int in range(box2.position.y / TILE, (box2.end.y - 1) / TILE + 1):
			for ti: int in range(box2.position.x / TILE, (box2.end.x - 1) / TILE + 1):
				touched[Vector2i(ti, tj)] = true
	var changed: Array = []
	for k: Variant in touched:
		var key: Vector2i = k
		var cur: Tile = tile(key)
		if cur == null:
			# A tile no zone reaches holds just the spots; one waiting for its compose gets them then
			# (at() reads them from the zones meanwhile).
			if _zone_tiles.has(key) or not _spot_reaches(next, key):
				continue
			cur = compose_tile(key, {})
		var pub: Tile = _with_spots(cur, next)
		_mutex.lock()
		_tiles[key] = pub
		_mutex.unlock()
		_dirty[key] = true
		changed.append(key)
	return changed


## The grid texels a spot can reach (BloomField._spot_texels over the whole grid).
func _spot_texels(s: Dictionary) -> Rect2i:
	if width == 0 or depth == 0:
		return Rect2i()
	var p: Vector2 = s.get("pos", Vector2.ZERO)
	var r: float = float(s.get("radius", 2.0)) * _shape.spot_reach() + texel
	if not rect.grow(r).has_point(p):
		return Rect2i()
	var i0: int = clampi(int(floor((p.x - r - rect.position.x) / texel)), 0, width - 1)
	var i1: int = clampi(int(ceil((p.x + r - rect.position.x) / texel)), 0, width - 1)
	var j0: int = clampi(int(floor((p.y - r - rect.position.y) / texel)), 0, depth - 1)
	var j1: int = clampi(int(ceil((p.y + r - rect.position.y) / texel)), 0, depth - 1)
	return Rect2i(i0, j0, i1 - i0 + 1, j1 - j0 + 1)


func _spot_reaches(spots: Array, key: Vector2i) -> bool:
	var tr: Rect2i = tile_texels(key)
	for sp: Variant in spots:
		if ((sp as Array)[0] as Rect2i).intersects(tr):
			return true
	return false


## A new tile with `t`'s base and the spots on top (t itself is never written: readers may hold it).
func _with_spots(t: Tile, spots: Array) -> Tile:
	var out := Tile.new()
	out.key = t.key
	out.w = t.w
	out.d = t.d
	out.base = t.base
	out.fine = t.fine
	out.data = t.base
	var tr: Rect2i = tile_texels(t.key)
	var copied: bool = false
	for sp: Variant in spots:
		var box: Rect2i = ((sp as Array)[0] as Rect2i).intersection(tr)
		if box.size.x <= 0 or box.size.y <= 0:
			continue
		if not copied:
			out.data = t.base.duplicate()
			out.own_data = true
			copied = true
		for j: int in range(box.position.y, box.end.y):
			for i: int in range(box.position.x, box.end.x):
				var k: int = (j - tr.position.y) * t.w + (i - tr.position.x)
				out.data[k] = _spot_on(out.data[k], i, j, sp)
	return out


## A texel's value with one spot unioned in (BloomField._apply_spots).
func _spot_on(cur: int, i: int, j: int, sp: Array) -> int:
	var q := Vector2(rect.position.x + (i + 0.5) * texel, rect.position.y + (j + 0.5) * texel)
	var rad: float = sp[2]
	var v: float = float(sp[3]) * (1.0 - smoothstep(rad * 0.5, rad * _shape.spot_reach(), q.distance_to(sp[1])))
	if v <= 0.0:
		return cur
	return int(round(clampf(1.0 - (1.0 - cur / 255.0) * (1.0 - v), 0.0, 1.0) * 255.0))


# --- Queries -------------------------------------------------------------------------------------

func is_empty() -> bool:
	_mutex.lock()
	var no_spots: bool = _spots.is_empty()
	_mutex.unlock()
	return width == 0 or depth == 0 or (zones.is_empty() and no_spots)


## Colonisation at world (x, z), 0..1, as the shaders see it (bilinear between texel centres; 0 off
## the grid): BloomField.at() over the whole map. Any thread.
func at(x: float, z: float) -> float:
	return _sample(x, z, true)


## The authored field only, without the spots (the vegetation scatter). Any thread.
func base_at(x: float, z: float) -> float:
	return _sample(x, z, false)


func _sample(x: float, z: float, dyn: bool) -> float:
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
	# The (up to four) tiles under the four texels, and the spots, in one lock.
	var k00 := Vector2i(i0 / TILE, j0 / TILE)
	var k11 := Vector2i(i1 / TILE, j1 / TILE)
	_mutex.lock()
	var t00: Tile = _tiles.get(k00)
	var t10: Tile = t00 if k11.x == k00.x else _tiles.get(Vector2i(k11.x, k00.y))
	var t01: Tile = t00 if k11.y == k00.y else _tiles.get(Vector2i(k00.x, k11.y))
	var t11: Tile = t00 if k11 == k00 else _tiles.get(k11)
	var spots: Array = _spots
	_mutex.unlock()
	var a: float = lerpf(_texel(t00, i0, j0, dyn, spots), _texel(t10, i1, j0, dyn, spots), tx)
	var b: float = lerpf(_texel(t01, i0, j1, dyn, spots), _texel(t11, i1, j1, dyn, spots), tx)
	return lerpf(a, b, tz) / 255.0


## Grid texel (i, j): from its tile, else from the zones and spots directly.
func _texel(t: Tile, i: int, j: int, dyn: bool, spots: Array) -> int:
	if t != null:
		var k: int = (j - t.key.y * TILE) * t.w + (i - t.key.x * TILE)
		return t.data[k] if dyn else t.base[k]
	var v: int = texel_from_zones(i, j)
	if dyn:
		for sp: Variant in spots:
			if ((sp as Array)[0] as Rect2i).has_point(Vector2i(i, j)):
				v = _spot_on(v, i, j, sp)
	return v


## Grid texel (i, j) of the authored field, masked, computed from the zones (what compose_tile
## gives it; mask_fn's ground). Any thread.
func texel_from_zones(i: int, j: int) -> int:
	var idx: PackedInt32Array = _zone_tiles.get(Vector2i(i / TILE, j / TILE), PackedInt32Array())
	if idx.is_empty():
		return 0
	var p := Vector2(rect.position.x + (i + 0.5) * texel, rect.position.y + (j + 0.5) * texel)
	# Multiplied in single precision, as compose() keeps it in a PackedFloat32Array.
	var clean := PackedFloat32Array([1.0])
	for zi: int in idx:
		var v: float = _shape.zone_at(zones[zi], p, _noise[zi])
		if v > 0.0:
			clean[0] *= 1.0 - v
	var b: int = int(round(clampf(1.0 - clean[0], 0.0, 1.0) * 255.0))
	if b == 0 or not mask_fn.is_valid():
		return b
	var rt: RegionTerrain = mask_fn.call(p.x, p.y)
	return BloomField.masked(rt, p.x, p.y, texel * 0.25, b) if rt != null else b


# --- Shape ---------------------------------------------------------------------------------------

func _shape_into(f: BloomField) -> void:
	f.copy_shape(_shape)
