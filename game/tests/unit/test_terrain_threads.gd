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
