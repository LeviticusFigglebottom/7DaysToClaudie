extends GutTest
## The Bloom field in tiles and a window (TD-106, ADR-0038 §7, RWG_V2_PLAN §2): the tiles hold
## exactly the texels the whole-map BloomField composes (masked or not, read from tiles or from
## the zones directly), the window texture shows the same texels wherever it is moved, a region's
## tiles are masked again by its 1 m ground when it attaches, and a 10 km world holds a bounded set
## of tiles as the player walks across it.


func _zone(id: String, pts: Array, radius: float, strength: float, edge: float = 0.6) -> BloomField.Zone:
	var z := BloomField.Zone.new()
	z.id = id
	for p: Vector2 in pts:
		z.points.append(p)
	z.radius = radius
	z.strength = strength
	z.edge = edge
	z.seed = Ids.hash31(id)
	return z


## Zones over and across tile borders: a patch on a tile corner, a seep across three tiles, two
## overlapping patches and one reaching off the cover's edge.
func _zones() -> Array[BloomField.Zone]:
	var out: Array[BloomField.Zone] = [
		_zone("corner", [Vector2(0, 0)], 45.0, 0.9),
		_zone("seep", [Vector2(-300, 140), Vector2(-60, 200), Vector2(260, 120)], 16.0, 0.8, 0.4),
		_zone("a", [Vector2(180, -200)], 60.0, 0.7),
		_zone("b", [Vector2(230, -170)], 40.0, 0.8, 0.9),
		_zone("edge", [Vector2(-500, -330)], 50.0, 1.0),
	]
	return out


## A cover that isn't a whole number of tiles (smaller edge tiles).
const COVER := Rect2(-512, -384, 1100, 780)


func _cfg() -> Dictionary:
	return Content.config(&"bloom")


func _assert_same_texels(tiles: BloomTiles, old: BloomField, what: String) -> void:
	assert_eq(Vector2i(tiles.width, tiles.depth), Vector2i(old.width, old.depth), "%s: the same grid" % what)
	assert_eq(tiles.rect, old.rect, "%s: the same extent" % what)
	var img: Image = tiles.window_image(Rect2i(0, 0, tiles.width, tiles.depth))
	var got: PackedByteArray = img.get_data()
	var bad: int = 0
	var lit: int = 0
	for k: int in old.data.size():
		if got[k] != old.data[k]:
			bad += 1
		if old.data[k] > 0:
			lit += 1
	assert_gt(lit, 1000, "%s: the field holds something" % what)
	assert_eq(bad, 0, "%s: every texel equals the whole-map field's" % what)


func _assert_same_samples(tiles: BloomTiles, old: BloomField, what: String) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 99
	var worst: float = 0.0
	for k: int in 3000:
		var p := Vector2(rng.randf_range(COVER.position.x - 20, COVER.end.x + 20), rng.randf_range(COVER.position.y - 20, COVER.end.y + 20))
		# A third of them on tile borders, where the bilinear read spans two or four tiles.
		if k % 3 == 0:
			p.x = tiles.rect.position.x + round((p.x - tiles.rect.position.x) / 256.0) * 256.0 + rng.randf_range(-1.5, 1.5)
		worst = maxf(worst, absf(tiles.at(p.x, p.y) - old.at(p.x, p.y)))
		worst = maxf(worst, absf(tiles.base_at(p.x, p.y) - old.base_at(p.x, p.y)))
	assert_lt(worst, 1e-6, "%s: at() and base_at() equal the whole-map field's" % what)


func test_tiles_hold_the_whole_fields_texels() -> void:
	var old: BloomField = BloomField.from_zones(_zones(), COVER, _cfg())
	var tiles: BloomTiles = BloomTiles.from_zones(_zones(), COVER, _cfg())
	assert_gt(tiles.tile_count(), 3, "several tiles")
	_assert_same_texels(tiles, old, "tiles")
	_assert_same_samples(tiles, old, "tiles")


func test_uncomposed_tiles_read_the_zones_directly() -> void:
	var old: BloomField = BloomField.from_zones(_zones(), COVER, _cfg())
	var tiles: BloomTiles = BloomTiles.from_zones(_zones(), COVER, _cfg(), {}, false)
	assert_eq(tiles.tile_count(), 0, "nothing composed")
	_assert_same_samples(tiles, old, "from the zones")


func test_spots_cross_tiles_like_the_whole_field() -> void:
	var old: BloomField = BloomField.from_zones(_zones(), COVER, _cfg())
	var tiles: BloomTiles = BloomTiles.from_zones(_zones(), COVER, _cfg())
	# On a tile corner (by the corner zone), on a zone, and in clean ground no zone reaches.
	var spots: Array = [{"pos": Vector2(0.5, 128.5), "radius": 3.0, "strength": 0.9},
		{"pos": Vector2(185, -195), "radius": 2.4, "strength": 0.85},
		{"pos": Vector2(470, 300), "radius": 2.0, "strength": 0.8}]
	old.set_spots(spots)
	var changed: Array = tiles.set_spots(spots)
	assert_eq(changed.size(), 6, "every tile a spot touches is published again (four round the corner)")
	_assert_same_texels(tiles, old, "with spots")
	_assert_same_samples(tiles, old, "with spots")
	assert_gt(tiles.at(470, 300), 0.6, "a mound in clean ground takes it")
	assert_eq(tiles.base_at(470, 300), 0.0, "the authored field is untouched")
	old.set_spots([])
	tiles.set_spots([])
	_assert_same_texels(tiles, old, "spots gone")
	assert_eq(tiles.at(470, 300), 0.0, "gone with the mound")


## Two regions with roads, masked the old way (BloomField.build) and tiled (BloomTiles.build, the
## main map's path): the same texels.
func test_a_world_built_whole_equals_its_tiles() -> void:
	var s: Array = _world_with_roads()
	var w: WorldDef = s[0]
	var regions: Dictionary = {"a": _rt(w, "a", 2.0, true), "b": _rt(w, "b", 2.0, true)}
	var old: BloomField = BloomField.build(w, regions, _cfg())
	var tiles: BloomTiles = BloomTiles.build(w, regions, _cfg(), false)
	assert_false(tiles.lazy)
	assert_eq(tiles.zones.size(), old.zones.size())
	_assert_same_texels(tiles, old, "masked world")
	var road: Vector2 = s[1]
	assert_eq(tiles.at(road.x, road.y), 0.0, "nothing on the road")


## The window texture shows the field's texels wherever it is, and follows the player.
func test_the_window_shows_the_same_texels_and_follows_the_player() -> void:
	var cover := Rect2(-1024, -1024, 2048, 2048)
	var zs: Array[BloomField.Zone] = []
	for k: int in 7:
		zs.append(_zone("w%d" % k, [Vector2(-900 + k * 290, -800 + k * 270)], 45.0, 0.9))
	var old: BloomField = BloomField.from_zones(zs, cover, _cfg())
	var tiles: BloomTiles = BloomTiles.from_zones(zs, cover, _cfg())
	var bw := BloomWorld.new()
	add_child_autofree(bw)
	var cfg: Dictionary = _cfg().duplicate(true)
	(cfg["field"] as Dictionary)["window"] = 1024.0
	bw.setup(tiles, null, Vector2(-900, -800), cfg)
	assert_eq(bw.window_tiles, 4)
	_assert_window(bw, old, "at the start")
	var before: Rect2i = bw.window
	bw.plan(Vector2(800, 700))
	while bw.collect():
		await get_tree().process_frame
	assert_ne(bw.window, before, "recentred on the player")
	assert_true(bw.window_tile_rect().has_point(tiles.tile_of(800, 700)), "the player is inside it")
	_assert_window(bw, old, "after moving")
	# A spot in the window shows next frame.
	tiles.set_spots([{"pos": Vector2(700, 650), "radius": 3.0, "strength": 0.9}])
	old.set_spots([{"pos": Vector2(700, 650), "radius": 3.0, "strength": 0.9}])
	bw.collect()
	_assert_window(bw, old, "with a spot")


func _assert_window(bw: BloomWorld, old: BloomField, what: String) -> void:
	var img: Image = bw.window_image()
	var w: Rect2i = bw.window
	assert_eq(img.get_size(), w.size, "%s: the image is the window" % what)
	var data: PackedByteArray = img.get_data()
	var bad: int = 0
	for j: int in w.size.y:
		for i: int in w.size.x:
			if data[j * w.size.x + i] != old.data[(w.position.y + j) * old.width + w.position.x + i]:
				bad += 1
	assert_eq(bad, 0, "%s: window texels equal the whole field's" % what)
	var sr: Vector4 = bw.shader_rect()
	assert_almost_eq(sr.x, old.rect.position.x + w.position.x * old.texel, 1e-4, "%s: the shaders map the window's x" % what)
	assert_almost_eq(sr.w, 1.0 / (w.size.y * old.texel), 1e-9, "%s: and its depth" % what)


## A streamed world: region b is coarse (no road in its 16 m mask) until it attaches at 1 m with
## its road; its tile is composed near the player with the coarse mask, then again with the 1 m
## one on attach; a late coarse tile never replaces the fine one.
func test_a_region_is_masked_again_at_1m_when_it_attaches() -> void:
	var s: Array = _world_with_roads()
	var w: WorldDef = s[0]
	var road: Vector2 = s[1]
	var a: RegionTerrain = _rt(w, "a", 1.0, true)
	var coarse_b: RegionTerrain = _rt(w, "b", 16.0, false)
	var fine_b: RegionTerrain = _rt(w, "b", 1.0, true)
	var tiles: BloomTiles = BloomTiles.build(w, {"a": a, "b": coarse_b}, _cfg(), true)
	var key: Vector2i = tiles.tile_of(road.x, road.y)
	assert_true(tiles.lazy)
	assert_false(tiles.is_composed(key), "a coarse region's tile waits for the player")
	var tm := TerrainManager.new()
	tm.defer_far_tiles = true
	add_child_autofree(tm)
	tm.prebuilt_bloom = tiles
	tm.setup(w, {"a": a}, {"b": coarse_b})
	assert_gt(tm.bloom_at(road.x, road.y), 0.3, "coarse ground: the 16 m mask has no road")
	var direct: float = tm.bloom_base_at(road.x + 5.0, road.y)
	tm.bloom.plan(road)
	while tm.bloom.collect():
		await get_tree().process_frame
	assert_true(tiles.is_composed(key), "composed near the player")
	assert_false(tiles.tile(key).fine, "with the coarse mask")
	assert_eq(tm.bloom_base_at(road.x + 5.0, road.y), direct, "the tile holds what the zones gave")
	tm.attach_region(fine_b)
	assert_true(tiles.tile(key).fine, "masked again at 1 m on attach")
	assert_eq(tm.bloom_at(road.x, road.y), 0.0, "nothing on the road now")
	assert_gt(tm.bloom_at(road.x + 30.0, road.y), 0.3, "the wood beside it keeps it")
	var whole: BloomField = BloomField.build(w, {"a": a, "b": fine_b}, _cfg())
	var worst: float = 0.0
	var r: Rect2 = w.region_rect("b")
	for k: int in 400:
		var p: Vector2 = r.position + Vector2(fposmod(k * 37.3, r.size.x), fposmod(k * 91.7, r.size.y))
		worst = maxf(worst, absf(tm.bloom_at(p.x, p.y) - whole.at(p.x, p.y)))
	assert_lt(worst, 1e-6, "the attached region reads as a whole field masked at 1 m")
	tiles.install([tiles.compose_tile(key, {"b": coarse_b})])
	assert_true(tiles.tile(key).fine, "a late coarse tile doesn't replace it")
	tm.bloom.collect()


## A 10 km streamed world (the New Game cap): walking across it, the tiles held stay within the
## window and its margin, and the window texture is 3 km at 2 m whatever the map's size (the
## whole-map field was 5120 x 5120 texels, 26 MB, twice over with the spots copy).
func test_a_10km_world_holds_a_bounded_set_of_tiles() -> void:
	var size: float = 10240.0
	var cover := Rect2(-size * 0.5, -size * 0.5, size, size)
	var zs: Array[BloomField.Zone] = []
	var rng := RandomNumberGenerator.new()
	rng.seed = 10
	for k: int in 140:
		zs.append(_zone("z%d" % k, [Vector2(rng.randf_range(-5000, 5000), rng.randf_range(-5000, 5000))], rng.randf_range(25, 45), 0.8))
	var tiles: BloomTiles = BloomTiles.from_zones(zs, cover, _cfg(), {}, false)
	tiles.lazy = true
	var bw := BloomWorld.new()
	add_child_autofree(bw)
	bw.setup(tiles, null, Vector2(-4500, -4500), _cfg())
	assert_eq(bw.window_image().get_size(), Vector2i(1536, 1536), "a 3 km window")
	var most: int = 0
	var most_bytes: int = 0
	for step: int in 19:
		var p := Vector2(-4500, -4500) + Vector2(500, 500) * step
		for guard: int in 100:
			bw.plan(p)
			while bw.collect():
				await get_tree().process_frame
			most = maxi(most, tiles.tile_count())
			most_bytes = maxi(most_bytes, tiles.memory_bytes())
			if tiles.missing(bw.window_tile_rect(), tiles.tile_of(p.x, p.y)).is_empty():
				break
		assert_true(bw.window_tile_rect().has_point(tiles.tile_of(p.x, p.y)), "the window follows (step %d)" % step)
		assert_eq(tiles.missing(bw.window_tile_rect(), tiles.tile_of(p.x, p.y)).size(), 0, "the window's tiles composed (step %d)" % step)
	var span: int = bw.window_tiles + 2 * (1 + BloomWorld.FREE_MARGIN) + 1
	assert_lte(most, span * span, "at most the window and its margin are held (%d tiles)" % most)
	assert_lt(most_bytes, 4 * 1048576, "a few MB of tiles at most (%.1f MB)" % (most_bytes / 1048576.0))
	assert_lt(tiles.tile_count(), tiles.zone_tiles().size(), "the far tiles were freed")
	# A far point still reads the field (from the zones).
	var far: BloomField.Zone = zs[0]
	assert_gt(tiles.at(far.points[0].x, far.points[0].y), 0.2, "a far zone's core reads colonised")


# --- A synthetic 2x1 world of 512 m regions with Bloom features and roads -------------------------

func _world_with_roads() -> Array:
	var w := WorldDef.new()
	w.id = "bloom_tiles_test"
	w.cols = 2
	w.rows = 1
	w.region_size = 512.0
	w.regions = {"a": {"id": "a", "cell": "A1"}, "b": {"id": "b", "cell": "B1"}}
	w.cells = {"A1": "a", "B1": "b"}
	w.seed = 31
	var ra: Rect2 = w.region_rect("a")
	var rb: Rect2 = w.region_rect("b")
	var road := Vector2(rb.position.x + 200.0, rb.get_center().y)
	w._region_cache["a"] = {"id": "a", "features": [
		{"type": "bloom", "id": "a1", "at": [ra.get_center().x + 120.0, ra.get_center().y], "radius": 60, "strength": 0.9},
		# Across the border into b.
		{"type": "bloom", "id": "a2", "points": [[ra.end.x - 90.0, ra.get_center().y - 150.0], [ra.end.x + 60.0, ra.get_center().y - 100.0]], "radius": 18}]}
	w._region_cache["b"] = {"id": "b", "features": [
		{"type": "bloom", "id": "b1", "at": [road.x, road.y], "radius": 70, "strength": 1.0}]}
	return [w, road]


## A region's terrain at `spacing`; with `roads`, a road 8 m wide runs north-south through each
## region 200 m from its west edge (a 16 m mask can't hold one: it is left out of the coarse ones).
func _rt(w: WorldDef, rid: String, spacing: float, roads: bool) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = rid
	rt.rect = w.region_rect(rid)
	rt.spacing = spacing
	var n: int = int(rt.rect.size.x / spacing) + 1
	rt.height = HeightField.create(rt.rect.position, spacing, n, n, 5.0)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.vegmask.fill(255)
	if roads:
		for i: int in n:
			var x: float = rt.rect.position.x + i * spacing
			if absf(x - (rt.rect.position.x + 200.0)) <= 4.0:
				for j: int in n:
					rt.vegmask[j * n + i] = 0
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	return rt
