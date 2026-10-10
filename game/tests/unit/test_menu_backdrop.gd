extends GutTest
## The menu backdrop's pure parts (ADR-0063, ADR-0065): the pan over the pictures, and the
## photographed flight's stills, water winding and path over the real D6 region.


func test_the_pan_never_shows_a_picture_edge() -> void:
	for i: int in MenuBackdrop.COUNT:
		for step: int in 11:
			var k: float = step / 10.0
			var spare: float = (MenuBackdrop.pan_zoom(i, k) - 1.0) * 0.5
			var d: Vector2 = MenuBackdrop.pan_drift(i, k)
			assert_true(absf(d.x) <= spare and absf(d.y) <= spare, "picture %d at %.1f stays inside its zoom" % [i, k])


func test_the_pan_alternates_and_moves() -> void:
	assert_gt(MenuBackdrop.pan_zoom(0, 1.0), MenuBackdrop.pan_zoom(0, 0.0), "even pictures zoom in")
	assert_lt(MenuBackdrop.pan_zoom(1, 1.0), MenuBackdrop.pan_zoom(1, 0.0), "odd ones zoom out")
	assert_gt(MenuBackdrop.pan_drift(0, 1.0).x, MenuBackdrop.pan_drift(0, 0.0).x)
	assert_lt(MenuBackdrop.pan_drift(1, 1.0).x, MenuBackdrop.pan_drift(1, 0.0).x)


func test_the_dissolve_dips_instead_of_doubling_the_pictures() -> void:
	assert_eq(MenuBackdrop.dissolve_alphas(0.0), Vector2(1, 0), "starts on the old picture")
	assert_eq(MenuBackdrop.dissolve_alphas(1.0), Vector2(0, 1), "ends on the new one")
	var mid: Vector2 = MenuBackdrop.dissolve_alphas(0.5)
	assert_lt(mid.x, 0.3, "the old picture is mostly gone halfway")
	assert_lt(mid.y, 0.3, "and the new one barely up: never two riverbeds at half strength")
	assert_gt(mid.x + mid.y, 0.4, "a dip through dusk, not a blink to black")
	var last: Vector2 = Vector2(1, 0)
	for i: int in range(1, 21):
		var a: Vector2 = MenuBackdrop.dissolve_alphas(i / 20.0)
		assert_true(a.x <= last.x and a.y >= last.y, "fades only one way")
		last = a


func test_stills_are_spread_along_the_flight() -> void:
	var last: float = -1.0
	for share: float in MenuFlight.STILLS:
		var s: float = MenuFlight.still_distance(share, 1000.0)
		assert_gt(s, last)
		assert_lte(s, 880.0, "kept back from the path's end (the camera looks 110 m ahead)")
		last = s
	assert_eq(MenuFlight.STILLS.size(), MenuBackdrop.COUNT, "the menu shows every still")


func test_water_surfaces_face_up() -> void:
	var river: Dictionary = {"points": [[0.0, 0.0], [0.0, 10.0], [3.0, 20.0]], "levels": [5.0, 5.0, 5.0], "widths": [8.0, 8.0, 8.0]}
	var lake: Dictionary = {"level": 2.0, "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]}
	for arrays: Array in [MenuFlight.river_arrays(river), MenuFlight.lake_arrays(lake), MenuFlight.lake_arrays(
			{"level": 2.0, "polygon": [[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0]]})]:
		var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		assert_gt(idx.size(), 0)
		for t: int in range(0, idx.size(), 3):
			var n: Vector3 = (v[idx[t + 1]] - v[idx[t]]).cross(v[idx[t + 2]] - v[idx[t]])
			assert_lt(n.y, 0.0, "clockwise from above: Godot's front face points up")


func test_path_follows_the_river_above_its_banks() -> void:
	var world: WorldDef = WorldDef.load_from(MenuFlight.MAIN_WORLD_DIR)
	var rt: RegionTerrain = TerrainComposer.get_or_compose(world, MenuFlight.REGION, 16.0)
	var river: Dictionary = {}
	for w: Variant in rt.water:
		if str((w as Dictionary).get("id", "")) == MenuFlight.RIVER:
			river = w
	assert_false(river.is_empty(), "the Tamsin runs through D6")
	var path: PackedVector3Array = MenuFlight.river_path(river, rt)
	assert_gt(path.size(), 50)
	# Long enough that the stills are well apart.
	assert_gt((path.size() - 1) * 6.0 - 120.0, 300.0)
	for p: Vector3 in path:
		assert_true(rt.rect.has_point(Vector2(p.x, p.z)))
		assert_gt(p.y, rt.height.sample(p.x, p.z) + 10.0, "the camera clears the ground")


func test_one_still_is_a_misty_dawn() -> void:
	assert_eq(MenuFlight.STILL_MOODS.size(), MenuFlight.STILLS.size(), "a light for every still")
	assert_eq(MenuFlight.STILL_MOODS.count("dawn_mist"), 1)
	for mood: String in MenuFlight.STILL_MOODS:
		assert_true(MenuFlight.MOODS.has(mood))
	assert_gt(float(MenuFlight.MOODS["dawn_mist"]["mist"]), 0.0)
	# Dawn's sun stands in the east, dusk's in the west.
	assert_gt((MenuFlight.MOODS["dawn_mist"]["sun_dir"] as Vector3).x, 0.0)
	assert_lt((MenuFlight.MOODS["dusk"]["sun_dir"] as Vector3).x, 0.0)


func test_ground_cover_grows_in_front_of_the_camera() -> void:
	var rect := Rect2(0, 0, 1024, 1024)
	var chunks: Array[Vector2i] = MenuFlight.chunks_in_view(Vector2(512, 512), Vector2(0, -1), 300.0, rect)
	assert_gt(chunks.size(), 4)
	var ahead: bool = false
	for k: Vector2i in chunks:
		var c := Vector2((k.x + 0.5) * 64.0, (k.y + 0.5) * 64.0)
		assert_true(rect.has_point(c))
		ahead = ahead or c.y < 300.0
		assert_false(c.y > 512.0 + 128.0, "nothing far behind the lens")
	assert_true(ahead, "chunks well ahead")


func test_the_scatter_keeps_out_of_the_water() -> void:
	var grid: Dictionary = MenuFlight.water_grid([
		{"kind": "river", "points": [[0.0, 0.0], [0.0, 100.0]], "levels": [10.0, 6.0], "widths": [20.0, 20.0]},
		{"kind": "lake", "level": 3.0, "polygon": [[200.0, 200.0], [260.0, 200.0], [260.0, 260.0], [200.0, 260.0]]}])
	assert_almost_eq(MenuFlight.water_level(grid, 5.0, 50.0), 8.0, 0.01, "mid-river, between its levels")
	assert_eq(MenuFlight.water_level(grid, 15.0, 50.0), -INF, "past its half width")
	assert_eq(MenuFlight.water_level(grid, 230.0, 230.0), 3.0, "in the lake")
	assert_eq(MenuFlight.water_level(grid, 400.0, 400.0), -INF)
