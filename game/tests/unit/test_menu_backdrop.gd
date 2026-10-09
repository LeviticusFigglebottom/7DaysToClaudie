extends GutTest
## The menu backdrop's pure parts (ADR-0063): the cost verdict, the loop's fade, water winding and
## the flight's path over the real D6 region.


func test_too_slow_is_a_mean_under_min_fps() -> void:
	assert_false(MenuBackdrop.too_slow(PackedFloat32Array()))
	assert_false(MenuBackdrop.too_slow(PackedFloat32Array([0.016, 0.017, 0.02])))
	assert_true(MenuBackdrop.too_slow(PackedFloat32Array([0.03, 0.03, 0.026])))
	# One long frame among quick ones doesn't freeze it; a slow average does.
	assert_false(MenuBackdrop.too_slow(PackedFloat32Array([0.016, 0.016, 0.016, 0.016, 0.05])))


func test_loop_black_fades_out_at_the_end_and_in_on_later_loops() -> void:
	var span: float = MenuBackdrop.SPEED * MenuBackdrop.LOOP_FADE
	assert_eq(MenuBackdrop.loop_black(100.0, 500.0, true), 0.0, "mid flight is clear")
	assert_almost_eq(MenuBackdrop.loop_black(500.0, 500.0, true), 1.0, 0.001, "black at the end")
	assert_almost_eq(MenuBackdrop.loop_black(500.0 - span * 0.5, 500.0, false), 0.5, 0.001)
	assert_eq(MenuBackdrop.loop_black(0.0, 500.0, false), 0.0, "the first loop fades in with the menu")
	assert_almost_eq(MenuBackdrop.loop_black(0.0, 500.0, true), 1.0, 0.001, "later loops fade in from black")


func test_water_surfaces_face_up() -> void:
	var river: Dictionary = {"points": [[0.0, 0.0], [0.0, 10.0], [3.0, 20.0]], "levels": [5.0, 5.0, 5.0], "widths": [8.0, 8.0, 8.0]}
	var lake: Dictionary = {"level": 2.0, "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]}
	for arrays: Array in [MenuBackdrop.river_arrays(river), MenuBackdrop.lake_arrays(lake), MenuBackdrop.lake_arrays(
			{"level": 2.0, "polygon": [[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0]]})]:
		var v: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		assert_gt(idx.size(), 0)
		for t: int in range(0, idx.size(), 3):
			var n: Vector3 = (v[idx[t + 1]] - v[idx[t]]).cross(v[idx[t + 2]] - v[idx[t]])
			assert_lt(n.y, 0.0, "clockwise from above: Godot's front face points up")


func test_path_follows_the_river_above_its_banks() -> void:
	var world: WorldDef = WorldDef.load_from(MenuBackdrop.MAIN_WORLD_DIR)
	var rt: RegionTerrain = TerrainComposer.get_or_compose(world, MenuBackdrop.REGION, 16.0)
	var river: Dictionary = {}
	for w: Variant in rt.water:
		if str((w as Dictionary).get("id", "")) == MenuBackdrop.RIVER:
			river = w
	assert_false(river.is_empty(), "the Tamsin runs through D6")
	var path: PackedVector3Array = MenuBackdrop.river_path(river, rt)
	assert_gt(path.size(), 50)
	for p: Vector3 in path:
		assert_true(rt.rect.has_point(Vector2(p.x, p.z)))
		assert_gt(p.y, rt.height.sample(p.x, p.z) + 10.0, "the camera clears the ground")
