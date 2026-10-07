extends GutTest
## Regions in and out of a running TerrainManager (ADR-0038, RWG v2 Phase 2): attach and detach
## swap 1 m and coarse terrain under height_at, digs survive a detach and come back on attach
## (with the dig limit still taken from pristine heights), digs saved for a region that was not
## loaded apply when it attaches, and workers reading heights survive attach/detach churn.
## A synthetic 2x1 world of 256 m regions: "a" detailed from the start, "b" coarse until attached.

const A_Y: float = 12.0
const B_Y: float = 20.0
const COARSE_Y: float = 5.0


func _world() -> WorldDef:
	var w := WorldDef.new()
	w.id = "streaming_test"
	w.cols = 2
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"a": {"id": "a", "cell": "A1"}, "b": {"id": "b", "cell": "B1"}}
	w.cells = {"A1": "a", "B1": "b"}
	return w


func _rt(w: WorldDef, rid: String, spacing: float, y: float) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = rid
	rt.rect = w.region_rect(rid)
	rt.spacing = spacing
	var n: int = int(256.0 / spacing) + 1
	rt.height = HeightField.create(rt.rect.position, spacing, n, n, y)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	return rt


func _setup() -> Array:
	var w: WorldDef = _world()
	var tm := TerrainManager.new()
	tm.defer_far_tiles = true
	add_child_autofree(tm)
	tm.setup(w, {"a": _rt(w, "a", 1.0, A_Y)}, {"b": _rt(w, "b", 16.0, COARSE_Y)})
	return [tm, w]


func test_attach_and_detach_swap_the_terrain_under_height_at() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var b_mid: Vector2 = (s[1] as WorldDef).region_rect("b").get_center()
	assert_almost_eq(tm.height_at(b_mid.x, b_mid.y), COARSE_Y, 1e-3, "coarse before")
	assert_null(tm.region_terrain_at(b_mid.x, b_mid.y))
	watch_signals(tm)
	tm.attach_region(_rt(s[1], "b", 1.0, B_Y))
	assert_signal_emitted_with_parameters(tm, "region_attached", ["b"])
	assert_almost_eq(tm.height_at(b_mid.x, b_mid.y), B_Y, 1e-3, "1 m terrain after attach")
	assert_not_null(tm.region_terrain_at(b_mid.x, b_mid.y))
	tm.detach_region("b")
	assert_signal_emitted_with_parameters(tm, "region_detached", ["b"])
	assert_almost_eq(tm.height_at(b_mid.x, b_mid.y), COARSE_Y, 1e-3, "coarse again after detach")
	assert_false(tm.regions.has("b"))


func test_a_dig_comes_back_after_detach_and_the_limit_still_holds() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var rt: RegionTerrain = _rt(s[1], "b", 1.0, B_Y)
	tm.attach_region(rt)
	var c: Vector2 = rt.rect.get_center()
	tm.modify(Vector3(c.x, B_Y, c.y), 2.0, 1.5)
	var dug: float = tm.height_at(c.x, c.y)
	assert_lt(dug, B_Y - 1.0, "dug")
	tm.detach_region("b")
	tm.attach_region(rt)
	assert_almost_eq(tm.height_at(c.x, c.y), dug, 1e-3, "the dig is back, once")
	for i: int in 20:
		tm.modify(Vector3(c.x, B_Y, c.y), 2.0, 1.5)
	assert_almost_eq(tm.height_at(c.x, c.y), B_Y - TerrainManager.MAX_DIG_DEPTH, 0.05, "the dig limit counts from pristine ground")


func test_digs_saved_for_an_unloaded_region_apply_when_it_attaches() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var rt: RegionTerrain = _rt(s[1], "b", 1.0, B_Y)
	tm.attach_region(rt)
	var c: Vector2 = rt.rect.get_center()
	tm.modify(Vector3(c.x, B_Y, c.y), 2.0, 1.0)
	var dug: float = tm.height_at(c.x, c.y)
	var ws := WorldState.new()
	tm.save_into(ws)
	# A new session where "b" is not loaded at start.
	var s2: Array = _setup()
	var tm2: TerrainManager = s2[0]
	tm2.load_from(ws)
	assert_almost_eq(tm2.height_at(c.x, c.y), COARSE_Y, 1e-3, "nothing to apply it to yet")
	tm2.attach_region(_rt(s2[1], "b", 1.0, B_Y))
	assert_almost_eq(tm2.height_at(c.x, c.y), dug, 1e-3, "the saved dig lands on attach")


func test_workers_reading_heights_survive_attach_and_detach_churn() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var w: WorldDef = s[1]
	var stop: Array = [false]
	var bad: Array = [0]
	var tasks: Array[int] = []
	for r: int in 4:
		tasks.append(WorkerThreadPool.add_task(func() -> void:
			var rng := RandomNumberGenerator.new()
			rng.seed = r
			while not stop[0]:
				var h: float = tm.height_at(rng.randf_range(-256.0, 256.0), rng.randf_range(-128.0, 128.0))
				if not (is_equal_approx(h, A_Y) or is_equal_approx(h, B_Y) or is_equal_approx(h, COARSE_Y)) and h > B_Y + 0.01:
					bad[0] += 1
		))
	var end: int = Time.get_ticks_msec() + 2000
	var n: int = 0
	while Time.get_ticks_msec() < end:
		tm.attach_region(_rt(w, "b", 1.0, B_Y))
		tm.detach_region("b")
		n += 1
	stop[0] = true
	for t: int in tasks:
		WorkerThreadPool.wait_for_task_completion(t)
	assert_gt(n, 2, "churned %d times" % n)
	assert_eq(bad[0], 0, "every read was a real height")


## TD-197 / TD-106: the pure-data half of a region's terrain (cellars, splat images) is made on
## the thread that composed it and only taken on the main thread; with defer_materials the
## textures and materials are boot steps of their own.
func test_prepared_holes_and_splats_are_taken_and_materials_come_in_steps() -> void:
	var w: WorldDef = _world()
	var a: RegionTerrain = _rt(w, "a", 1.0, A_Y)
	var th := TerrainHoles.new()
	a.set_meta(&"holes", th)
	TerrainManager.prepare_splat(a)
	var tm := TerrainManager.new()
	tm.defer_far_tiles = true
	tm.defer_materials = true
	tm.prepared_textures = TerrainTextures.prepare()
	add_child_autofree(tm)
	tm.setup(w, {"a": a}, {"b": _rt(w, "b", 16.0, COARSE_Y)})
	assert_false(a.has_meta(&"holes"), "the prepared cellars were taken")
	assert_same(tm._region_holes["a"], th)
	assert_false(tm._materials.has("a"), "no material before its boot step")
	var steps: Array = tm.boot_steps()
	var names: Array = steps.map(func(s: Array) -> String: return str(s[2]))
	assert_eq(names.slice(0, 2), ["terrain textures", "terrain material a"])
	(steps[0][1] as Callable).call()
	(steps[1][1] as Callable).call()
	assert_true(tm._materials.has("a"))
	assert_false(a.has_meta(&"splat"), "the prepared splat images were used")
	var b: RegionTerrain = _rt(w, "b", 1.0, B_Y)
	TerrainManager.prepare_splat(b)
	tm.attach_region(b)
	assert_false(b.has_meta(&"splat"), "an attach uploads the prepared images")
	assert_not_null((tm._materials["b"] as ShaderMaterial).get_shader_parameter("splat0"))
