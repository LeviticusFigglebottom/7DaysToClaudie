extends GutTest
## Volume terrain streaming (CAVES_PLAN WS-B): densities built on workers equal the synchronous
## build, attach builds a region's cave chunks through jobs, detach frees them and keeps digs as
## blobs that come back on the next attach and go into saves, a load builds nothing for regions
## that aren't attached, ground_below finds a cave's floor, and a column never becomes a heightmap
## hole before its volume meshes are installed. Caves are test stand-ins (helpers/fake_caves.gd).
## The synthetic 2x1 world of test_terrain_streaming: "a" detailed, "b" coarse until attached.

const Fakes := preload("res://tests/unit/helpers/fake_caves.gd")
const A_Y: float = 12.0
const B_Y: float = 20.0
const COARSE_Y: float = 5.0
## A box of air under region b's flat ground (y 20): air from y 12 to 16, floor at 12.
const CAVE_CENTER := Vector3(100.0, 14.0, 8.0)
const CAVE_HALF := Vector3(6.0, 2.0, 6.0)
## A point in the rock beside the cave, dug in the tests, and a sample inside the dig.
const DIG_AT := Vector3(100.0, 14.0, 15.0)
const DIG_SAMPLE := Vector3(100.0, 14.0, 15.0)


class SlopeTerrain:
	extends Node
	var textures: Variant = null
	var holes: TerrainHoles = null
	var caves: Object = null

	func base_height_at(x: float, z: float) -> float:
		return 10.0 + 0.3 * x + 2.0 * sin(z * 0.2)


func _world() -> WorldDef:
	var w := WorldDef.new()
	w.id = "volume_streaming_test"
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


func _cave() -> RefCounted:
	return Fakes.FakeCave.new(&"test_cave", CAVE_CENTER, CAVE_HALF)


## Region b's 1 m terrain carrying its caves as the compose worker leaves them (meta "caves").
func _rt_b(w: WorldDef) -> RegionTerrain:
	var rt: RegionTerrain = _rt(w, "b", 1.0, B_Y)
	rt.set_meta(&"caves", Fakes.FakeCaveSet.new([_cave()]))
	return rt


func _setup() -> Array:
	var w: WorldDef = _world()
	var tm := TerrainManager.new()
	tm.defer_far_tiles = true
	tm.cave_set_fn = func(parts: Array, extra: Dictionary) -> Object: return Fakes.FakeCaveSet.combined(parts, extra)
	add_child_autofree(tm)
	tm.setup(w, {"a": _rt(w, "a", 1.0, A_Y)}, {"b": _rt(w, "b", 16.0, COARSE_Y)})
	return [tm, w]


## Runs the volume's jobs to the end the way frames do (start under the cap, apply in budget).
func _drain(tm: TerrainManager, budget_ms: float = 3.0, each: Callable = Callable()) -> void:
	var until: int = Time.get_ticks_msec() + 60000
	while not tm.volume.is_idle() and Time.get_ticks_msec() < until:
		tm.start_queued()
		tm.volume.pump(budget_ms)
		if each.is_valid():
			each.call()
		OS.delay_msec(1)
	assert_true(tm.volume.is_idle(), "every volume job came back")


func _cave_columns() -> Array:
	return (_cave() as Object).call(&"columns").keys()


func test_worker_density_equals_the_synchronous_build() -> void:
	var t := SlopeTerrain.new()
	var cave: RefCounted = Fakes.FakeCave.new(&"c", Vector3(6.0, 9.0, 6.0), Vector3(3.0, 1.5, 3.0))
	t.caves = Fakes.FakeCaveSet.new([cave])
	add_child_autofree(t)
	var vol := VolumeTerrain.new()
	t.add_child(vol)
	vol.setup(t)
	vol.activate_column(Vector2i(0, 0), 0.0)
	var key := Vector3i(0, 0, 0)
	var sync_d: PackedFloat32Array = (vol.chunks[key] as VolumeTerrain.VChunk).density
	var out: Array = [null]
	var height_fn := Callable(t, &"base_height_at")
	var caves: Object = t.caves
	var task: int = WorkerThreadPool.add_task(func() -> void:
		out[0] = VolumeTerrain.run_job(key, height_fn, null, caves, PackedByteArray(), PackedFloat32Array()))
	WorkerThreadPool.wait_for_task_completion(task)
	var worker_d: PackedFloat32Array = (out[0] as Dictionary)["density"]
	assert_eq(worker_d.to_byte_array(), sync_d.to_byte_array(), "byte for byte")
	# And both are the pre-streaming build: clamp(h - y) with the cave min()ed in.
	var s: int = VolumeTerrain.N + 3
	var bad: int = 0
	var carved: int = 0
	for k: int in s:
		for j: int in s:
			for i: int in s:
				var p := Vector3(i - 1, j - 1, k - 1) * VolumeTerrain.VOXEL
				var want: float = clampf(t.base_height_at(p.x, p.z) - p.y, -2.0, 2.0)
				var cave_d: float = clampf(float((cave as Object).call(&"sdf", p)), -2.0, 2.0)
				if cave_d < want:
					want = cave_d
					carved += 1
				if absf(worker_d[(k * s + j) * s + i] - want) > 1e-5:
					bad += 1
	assert_eq(bad, 0, "every sample is the old formula's")
	assert_gt(carved, 100, "the cave was carved in")
	assert_gt(((out[0] as Dictionary)["indices"] as PackedInt32Array).size(), 0, "and meshed in the same job")
	vol.flush()


func test_attach_builds_the_cave_chunks_through_jobs() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var vol: VolumeTerrain = tm.volume
	assert_true(vol.chunks.is_empty(), "no caves in region a")
	tm.attach_region(_rt_b(s[1]))
	assert_not_null(tm.caves, "the region's caves are published")
	for col: Vector2i in _cave_columns():
		assert_true(vol.columns.has(col), "cave column %s owned" % col)
		assert_false(vol.committed.has(col), "but not a hole before its meshes")
	assert_false(vol.is_idle(), "the chunks are worker jobs")
	_drain(tm)
	var meshed: int = 0
	for key: Vector3i in vol.chunks:
		var c: VolumeTerrain.VChunk = vol.chunks[key]
		assert_true(c.applied, "chunk %s installed" % key)
		if c.mesh_node != null and c.mesh_node.mesh != null:
			meshed += 1
			assert_eq(c.mesh_node.visibility_range_end, VolumeTerrain.VISIBILITY_END)
	assert_gt(meshed, 0, "the cave's walls are meshed")
	for col2: Vector2i in _cave_columns():
		assert_true(vol.committed.has(col2), "committed once installed")
	var r := Rect2(CAVE_CENTER.x - 8.0, CAVE_CENTER.z - 8.0, 16.0, 16.0)
	assert_true(vol.is_rect_ready(r))
	assert_gt(vol.faces_in_rect(r).size(), 0, "faces by column")
	assert_eq(vol.faces_in_rect(Rect2(-200.0, -100.0, 50.0, 50.0)).size(), 0, "none where there is no volume")
	assert_gt(int(vol.apply_stats["chunks"]), 0)
	gut.p("volume applies (3 ms budget): %s" % vol.apply_stats)


func test_detach_frees_the_chunks_keeps_the_dig_and_reattach_restores_it() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var vol: VolumeTerrain = tm.volume
	tm.attach_region(_rt_b(s[1]))
	_drain(tm)
	var removed: float = vol.edit_sphere(DIG_AT, 1.2, 2.0)
	assert_gt(removed, 0.1, "dug into the cave wall")
	vol.flush()
	var dug: float = vol.density_at(DIG_SAMPLE)
	assert_lt(dug, 0.0, "air where the dig was")
	var dug_key: Vector3i = VolumeTerrain.chunk_of(DIG_SAMPLE)
	tm.detach_region("b")
	assert_true(vol.chunks.is_empty(), "the region's chunks are freed")
	assert_true(vol.columns.is_empty() and vol.committed.is_empty(), "and its columns")
	assert_true(vol._blobs.has(dug_key), "the dig is kept as a blob")
	assert_true(vol.is_idle())
	# A save while it is away carries the blob and the dug column, never the cave's own columns.
	var ws := WorldState.new()
	tm.save_into(ws)
	assert_true(ws.chunk_blobs.has("v:%d_%d_%d" % [dug_key.x, dug_key.y, dug_key.z]), "the blob is saved")
	var saved_cols: Array = []
	for e: Array in ws.flags["volume_columns"]:
		saved_cols.append(Vector2i(int(e[0]), int(e[1])))
	assert_true(saved_cols.has(Vector2i(dug_key.x, dug_key.z)), "the dug column is saved")
	for col: Vector2i in _cave_columns():
		if col != Vector2i(dug_key.x, dug_key.z):
			assert_false(saved_cols.has(col), "cave column %s derived, not saved" % col)
	await get_tree().process_frame
	assert_eq(vol.get_child_count(), 0, "every mesh and body node is gone")
	tm.attach_region(_rt_b(s[1]))
	_drain(tm)
	assert_almost_eq(vol.density_at(DIG_SAMPLE), dug, 0.03, "the dig is back")
	assert_false(vol._blobs.has(dug_key), "decoded into its chunk again")
	assert_true(vol.committed.has(Vector2i(dug_key.x, dug_key.z)))


func test_a_load_builds_nothing_for_regions_that_are_not_attached() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	tm.attach_region(_rt_b(s[1]))
	_drain(tm)
	tm.volume.edit_sphere(DIG_AT, 1.2, 2.0)
	tm.volume.flush()
	var dug: float = tm.volume.density_at(DIG_SAMPLE)
	var ws := WorldState.new()
	tm.save_into(ws)
	var s2: Array = _setup()
	var tm2: TerrainManager = s2[0]
	tm2.load_from(ws)
	assert_true(tm2.volume.chunks.is_empty(), "region b isn't attached: nothing built")
	assert_true(tm2.volume.is_idle(), "and nothing queued")
	tm2.attach_region(_rt_b(s2[1]))
	_drain(tm2)
	assert_almost_eq(tm2.volume.density_at(DIG_SAMPLE), dug, 0.03, "the saved dig lands on attach")


func test_ground_below_in_a_cave_is_its_floor() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	tm.attach_region(_rt_b(s[1]))
	var in_air := Vector3(CAVE_CENTER.x + 2.0, CAVE_CENTER.y + 1.0, CAVE_CENTER.z - 1.0)
	var floor_y: float = CAVE_CENTER.y - CAVE_HALF.y
	# Not built yet: the plan answers.
	assert_true(is_nan(tm.volume.ground_below(in_air)))
	assert_almost_eq(tm.ground_below(in_air), floor_y, 0.01, "the cave plan's floor before the chunks")
	_drain(tm)
	assert_almost_eq(tm.volume.ground_below(in_air), floor_y, 0.1, "the volume's density says the same")
	assert_almost_eq(tm.ground_below(in_air), floor_y, 0.1)
	# Above the hill over the cave: the surface; outside any volume column: NAN, then the heights.
	assert_almost_eq(tm.ground_below(Vector3(in_air.x, B_Y + 5.0, in_air.z)), B_Y, 0.1, "the surface over the cave")
	assert_true(is_nan(tm.volume.ground_below(Vector3(200.0, 30.0, 100.0))))
	assert_almost_eq(tm.ground_below(Vector3(200.0, 30.0, 100.0)), B_Y, 0.01)


func test_a_column_is_never_a_hole_without_its_volume_mesh() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var vol: VolumeTerrain = tm.volume
	var bad: Array = [0]
	var check := func() -> void:
		for col: Vector2i in vol.committed:
			for key: Vector3i in vol._by_column.get(col, []):
				if not (vol.chunks[key] as VolumeTerrain.VChunk).applied:
					bad[0] += 1
		for col2: Vector2i in vol.columns:
			var x: float = (col2.x + 0.5) * VolumeTerrain.SIZE
			var z: float = (col2.y + 0.5) * VolumeTerrain.SIZE
			if vol.is_hole_column(x, z) != vol.committed.has(col2):
				bad[0] += 1
	tm.attach_region(_rt_b(s[1]))
	check.call()
	# A tiny budget: one chunk at a time, checked after each.
	_drain(tm, 0.01, check)
	assert_eq(bad[0], 0, "no committed column had a chunk not installed")
	# The dig path too: a new column is owned at once (editable) but a hole only once meshed.
	var at := Vector3(-100.0, A_Y - 1.0, 20.0)
	vol.edit_sphere(at, 1.2, 2.0)
	var col3: Vector2i = VolumeTerrain.column_of(at.x, at.z)
	assert_true(vol.is_volume_column(at.x, at.z), "owned at once")
	assert_false(vol.is_hole_column(at.x, at.z), "not a hole before its mesh")
	assert_false(tm._chunk_has_volume(TerrainManager.chunk_of(at.x, at.z)), "the heightmap keeps drawing there")
	_drain(tm, 0.01, check)
	assert_true(vol.committed.has(col3), "committed once meshed")
	assert_true(tm._chunk_has_volume(TerrainManager.chunk_of(at.x, at.z)))
	assert_eq(bad[0], 0)
	assert_lt(tm._collision_height(at.x, at.z), A_Y - 30.0, "the heightmap collision sinks there now")


func test_collision_only_near_the_focus() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var vol: VolumeTerrain = tm.volume
	var focus := Node3D.new()
	add_child_autofree(focus)
	focus.global_position = Vector3(-200.0, 0.0, 0.0)
	tm.focus = focus
	tm.attach_region(_rt_b(s[1]))
	_drain(tm)
	var meshed: Array = []
	for key: Vector3i in vol.chunks:
		var c: VolumeTerrain.VChunk = vol.chunks[key]
		if not c.tris.is_empty():
			meshed.append(c)
			assert_null(c.body, "300 m from the focus: no body")
	assert_false(meshed.is_empty())
	focus.global_position = CAVE_CENTER
	vol._gate_collision()
	vol.pump(1000.0)
	for c2: VolumeTerrain.VChunk in meshed:
		assert_not_null(c2.body, "within range: a body")
	focus.global_position = Vector3(-200.0, 0.0, 0.0)
	vol._gate_collision()
	vol.pump(1000.0)
	for c3: VolumeTerrain.VChunk in meshed:
		assert_null(c3.body, "dropped again past the hysteresis")
	tm.focus = null


func test_place_and_remove_a_runtime_cave() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var vol: VolumeTerrain = tm.volume
	watch_signals(tm)
	var cave: RefCounted = Fakes.FakeCave.new(&"rt_cave", Vector3(-100.0, 8.0, -40.0), Vector3(4.0, 1.5, 4.0))
	assert_same(tm.place_cave(&"rt_cave", cave), cave)
	assert_same(tm.place_cave(&"rt_cave", cave), cave, "idempotent by id")
	assert_signal_emit_count(tm, "caves_changed", 1)
	assert_same(tm.cave_at(Vector3(-100.0, 8.0, -40.0)), cave)
	assert_null(tm.cave_at(Vector3(-100.0, A_Y + 3.0, -40.0)))
	_drain(tm)
	var cols: Array = (cave as Object).call(&"columns").keys()
	for col: Vector2i in cols:
		assert_true(vol.committed.has(col))
	assert_lt(vol.density_at(Vector3(-100.0, 8.0, -40.0)), 0.0, "carved")
	tm.remove_cave(&"rt_cave")
	assert_signal_emit_count(tm, "caves_changed", 2)
	for col2: Vector2i in cols:
		assert_false(vol.columns.has(col2), "a cave-only column goes when its cave does")
	_drain(tm)
	assert_null(tm.cave_at(Vector3(-100.0, 8.0, -40.0)))
