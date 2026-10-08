extends GutTest
## Terrain edits while worker threads read the terrain (TD-104, ADR-0036): digging writes heights
## in place (one float at a time: a reader sees each sample either before or after the edit, never
## a released array), and the containers that are replaced or grown (the region grid, `regions`,
## volume columns) are read and written under a mutex. Swapping a new array into a member is not
## safe on its own: the old one is released before the new one is stored. The stress tests dig on
## the main thread while workers mesh chunks and sample heights; a race here crashed the engine
## rather than failing an assert, so passing means surviving.

const PAD_Y: float = 12.0


func _flat_world() -> Array:
	var w := WorldDef.new()
	w.id = "threads_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var rt := RegionTerrain.new()
	rt.region_id = "t"
	rt.rect = w.region_rect("t")
	rt.spacing = 1.0
	var n: int = 257
	rt.height = HeightField.create(rt.rect.position, 1.0, n, n, PAD_Y)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	return [w, rt]


func _manager() -> Array:
	var wr: Array = _flat_world()
	var tm := TerrainManager.new()
	add_child_autofree(tm)
	tm.setup(wr[0], {"t": wr[1]}, {})
	return [tm, wr[1]]


func test_a_dig_writes_the_live_heights() -> void:
	var m: Array = _manager()
	var tm: TerrainManager = m[0]
	var rt: RegionTerrain = m[1]
	var c: Vector2 = rt.rect.get_center()
	var before: float = tm.height_at(c.x, c.y)
	var moved: float = tm.modify(Vector3(c.x, before, c.y), 2.0, 0.5)
	assert_gt(moved, 0.0, "earth moved")
	assert_lt(tm.height_at(c.x, c.y), before, "the new heights are live")
	assert_almost_eq(rt.height.sample(c.x, c.y), tm.height_at(c.x, c.y), 1e-4, "edited in the region's own array")


func test_digging_while_workers_mesh_and_sample() -> void:
	var m: Array = _manager()
	var tm: TerrainManager = m[0]
	var rt: RegionTerrain = m[1]
	var o: Vector2 = rt.rect.position
	var stop: Array = [false]
	var bad: Array = [0]
	var readers: Array[int] = []
	for r: int in 6:
		readers.append(WorkerThreadPool.add_task(func() -> void:
			var rng := RandomNumberGenerator.new()
			rng.seed = r
			while not stop[0]:
				var h: float = tm.height_at(o.x + rng.randf() * 256.0, o.y + rng.randf() * 256.0)
				if not is_finite(h) or h > PAD_Y + 0.01 or h < PAD_Y - 10.0:
					bad[0] += 1
		))
	# Chunk meshes on worker threads as the player's streaming makes them, over the dug area.
	for i: int in 40:
		var key := Vector2i(int(o.x / TerrainManager.CHUNK) + i % 4, int(o.y / TerrainManager.CHUNK) + (i / 4) % 4)
		if not tm._chunks.has(key):
			var ch := TerrainManager.Chunk.new()
			ch.key = key
			tm._chunks[key] = ch
		if not tm._pending.has(key):
			tm._request_mesh(key, i % 3, false)
		tm.modify(Vector3(o.x + 8.0 + (i % 8) * 28.0, PAD_Y, o.y + 8.0 + (i / 8) * 28.0), 3.0, 0.3)
	stop[0] = true
	for t: int in readers:
		WorkerThreadPool.wait_for_task_completion(t)
	var until: int = Time.get_ticks_msec() + 60000
	while not tm._pending.is_empty() and Time.get_ticks_msec() < until:
		# Chunk jobs wait in TerrainManager's queue until a worker slot is free (TD-196).
		tm._start_queued()
		tm._collect_finished()
		OS.delay_msec(5)
	assert_true(tm._pending.is_empty(), "every chunk mesh came back")
	assert_eq(bad[0], 0, "every sample a reader took was a whole height")
	assert_lt(tm.height_at(o.x + 8.0, o.y + 8.0), PAD_Y, "the digs landed")


func test_volume_columns_grow_while_workers_read() -> void:
	var m: Array = _manager()
	var tm: TerrainManager = m[0]
	var vol: VolumeTerrain = tm.volume
	var stop: Array = [false]
	var seen: Array = [0]
	var tasks: Array[int] = []
	for r: int in 4:
		tasks.append(WorkerThreadPool.add_task(func() -> void:
			while not stop[0]:
				if vol.is_volume_column(24.0, 24.0):
					seen[0] += 1
		))
	for i: int in 12:
		vol.activate_column(Vector2i(i % 4, i / 4), PAD_Y - 6.0)
	stop[0] = true
	for t: int in tasks:
		WorkerThreadPool.wait_for_task_completion(t)
	assert_true(vol.columns.has(Vector2i(1, 1)))
	assert_true(vol.is_volume_column(24.0, 24.0), "a worker's hole test sees the new column")
	vol.flush()


## CAVES_PLAN WS-B: a region with a cave attaches and detaches over and over while its volume
## jobs (density and mesh) run on workers under the terrain's task cap, and digs land in the
## region that stays. Jobs of freed chunks are retired and joined, never applied.
func test_volume_jobs_survive_attach_and_detach_churn() -> void:
	var fakes: GDScript = load("res://tests/unit/helpers/fake_caves.gd")
	var w := WorldDef.new()
	w.id = "threads_churn"
	w.cols = 2
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"t": {"id": "t", "cell": "A1"}, "u": {"id": "u", "cell": "B1"}}
	w.cells = {"A1": "t", "B1": "u"}
	var make := func(rid: String) -> RegionTerrain:
		var rt := RegionTerrain.new()
		rt.region_id = rid
		rt.rect = w.region_rect(rid)
		rt.spacing = 1.0
		rt.height = HeightField.create(rt.rect.position, 1.0, 257, 257, PAD_Y)
		rt.splat0.resize(257 * 257 * 4)
		rt.splat1.resize(257 * 257 * 4)
		rt.biome.resize(257 * 257)
		rt.vegmask.resize(257 * 257)
		rt.palette = TerrainComposer.DEFAULT_PALETTE
		rt.biome_ids = PackedStringArray(["meadow"])
		return rt
	var tm := TerrainManager.new()
	tm.cave_set_fn = func(parts: Array, extra: Dictionary) -> Object: return fakes.FakeCaveSet.combined(parts, extra)
	add_child_autofree(tm)
	tm.setup(w, {"t": make.call("t")}, {})
	var vol: VolumeTerrain = tm.volume
	var stop: Array = [false]
	var readers: Array[int] = []
	for r: int in 3:
		readers.append(WorkerThreadPool.add_task(func() -> void:
			var rng := RandomNumberGenerator.new()
			rng.seed = r
			while not stop[0]:
				vol.is_hole_column(rng.randf_range(0.0, 256.0), rng.randf_range(-128.0, 128.0))
				tm.height_at(rng.randf_range(-256.0, 256.0), rng.randf_range(-128.0, 128.0))
		))
	var end: int = Time.get_ticks_msec() + 3000
	var n: int = 0
	while Time.get_ticks_msec() < end:
		var rt: RegionTerrain = make.call("u")
		rt.set_meta(&"caves", fakes.FakeCaveSet.new([fakes.FakeCave.new(&"churn", Vector3(60.0 + (n % 3) * 40.0, PAD_Y - 6.0, 0.0), Vector3(8.0, 2.0, 8.0))]))
		tm.attach_region(rt)
		for f: int in 3:
			tm.start_queued()
			vol.pump(3.0)
			OS.delay_msec(2)
		if n % 4 == 0:
			vol.edit_sphere(Vector3(-128.0 + n % 8, PAD_Y - 1.0, 4.0), 1.0, 1.5)
		tm.detach_region("u")
		n += 1
	stop[0] = true
	for t: int in readers:
		WorkerThreadPool.wait_for_task_completion(t)
	var until: int = Time.get_ticks_msec() + 60000
	while not vol.is_idle() and Time.get_ticks_msec() < until:
		tm.start_queued()
		vol.pump(5.0)
		OS.delay_msec(2)
	assert_gt(n, 3, "churned %d times" % n)
	assert_true(vol.is_idle(), "every volume job came back or was retired")
	for key: Vector3i in vol.chunks:
		assert_lt(key.x, 0, "nothing of the detached region is left (%s)" % key)
	assert_true(vol.committed.has(VolumeTerrain.column_of(-128.0, 4.0)), "the dug column in the region that stayed committed")
	assert_lt(vol.density_at(Vector3(-128.0, PAD_Y - 1.0, 4.0)), 0.0, "and its dig is there")
