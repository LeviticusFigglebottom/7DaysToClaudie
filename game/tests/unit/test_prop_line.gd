extends GutTest
## A region's `prop_line` feature (TD-369): pieces every pitch along the line, turned to it, off its
## gaps, standing on the lowest ground under them.


func _build() -> RefCounted:
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	var b: RefCounted = TerrainComposer._Build.new(world, "d6_larch_hollow", 4.0, Callable())
	b.set(&"rect", Rect2(-512, 1536, 1024, 1024))
	return b


## Ground rising 0.1 m a metre east.
func _slope() -> HeightField:
	var hf := HeightField.create(Vector2(-512, 1536), 4.0, 257, 257, 0.0)
	for iz: int in 257:
		for ix: int in 257:
			hf.set_h(ix, iz, (ix * 4.0) * 0.1)
	return hf


func test_pieces_follow_the_line_skip_gaps_and_stand_low() -> void:
	var b: RefCounted = _build()
	var f: Dictionary = {"type": "prop_line", "id": "wall", "prop": "cordon_wall_panel", "pitch": 6.0,
		"points": [[0, 2000], [60, 2000]], "gaps": [[33, 2000, 4.0]], "sink": 0.0}
	var items: Array = b.call(&"_prop_line_items", f, _slope())
	assert_eq(items.size(), 9, "10 pitches, the one at x 33 left out")
	var first: Dictionary = items[0]
	assert_almost_eq(float(first["pos"][0]), 3.0, 0.01, "piece 0 at half a pitch")
	assert_almost_eq(float(first["rot"]), 0.0, 0.01, "+X along an eastward line")
	# Standing on the lowest ground under it: its west end (x 0) is 3 m x 0.1 lower than its middle.
	assert_almost_eq(float(first["pos"][1]), (0.0 + 512.0) * 0.1, 0.05)
	for it: Dictionary in items:
		assert_false(absf(float(it["pos"][0]) - 33.0) < 4.0, "nothing in the gap")
	var west: Array = b.call(&"_prop_line_items", {"prop": "cordon_wall_panel", "pitch": 6.0, "points": [[60, 2000], [0, 2000]]}, _slope())
	assert_almost_eq(absf(float((west[0] as Dictionary)["rot"])), 180.0, 0.01, "a westward line turns it round (+Z faces north)")


func test_props_items_take_the_ground_plus_their_offset() -> void:
	var b: RefCounted = _build()
	var items: Array = b.call(&"_props_items", {"items": [{"prop": "cordon_river_gate", "pos": [10, 2000], "rot": 90, "y_offset": -2.0},
		{"prop": "cordon_wall_gate", "pos": [20, 2000], "y": 5.0}, {"prop": "cordon_wall_gate", "pos": [9999, 2000]}]}, _slope())
	assert_eq(items.size(), 2, "one outside the region left out")
	assert_almost_eq(float(items[0]["pos"][1]), (10.0 + 512.0) * 0.1 - 2.0, 0.05)
	assert_eq(float(items[1]["pos"][1]), 5.0)
	assert_eq(float(items[0]["rot"]), 90.0)
