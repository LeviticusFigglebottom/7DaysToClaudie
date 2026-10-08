extends GutTest
## The full map's sheet (TD-014): shaded from region terrains, with water and roads inked on.


func test_sheet_covers_a_region_with_water_and_roads() -> void:
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	var rid: String = "d6_larch_hollow"
	var rt: RegionTerrain = TerrainComposer.get_or_compose(world, rid, 16.0)
	var r: Rect2 = world.region_rect(rid)
	var img: Image = WorldMap.shade(r, [rt], world.rivers, world.lakes, world.roads)
	assert_eq(img.get_width(), int(r.size.x * WorldMap.PX_PER_M))
	var water: int = 0
	var road: int = 0
	var plain: int = 0
	for y: int in range(0, img.get_height(), 2):
		for x: int in range(0, img.get_width(), 2):
			var c: Color = img.get_pixel(x, y)
			if _near(c, WorldMap.WATER):
				water += 1
			elif _near(c, WorldMap.ROAD):
				road += 1
			elif _near(c, WorldMap.PAPER):
				plain += 1
	assert_gt(water, 20, "the Tamsin and Larch Pond")
	assert_gt(road, 20, "Route 9")
	assert_lt(plain, img.get_width() * img.get_height() / 8, "the region is shaded, not blank paper")


func test_reveal_marks_cells_in_a_circle() -> void:
	var ex := ExploredMap.new()
	assert_true(ex.is_empty())
	var n: int = ex.reveal(Vector3(-300, 80, 2300), 90.0)
	assert_gt(n, 20)
	assert_eq(ex.reveal(Vector3(-300, 80, 2300), 90.0), 0, "nothing new the second time")
	assert_true(ex.is_explored(-300, 2300))
	assert_true(ex.is_explored(-300 + 60, 2300))
	assert_false(ex.is_explored(-300 + 200, 2300))
	# Negative cells and block borders.
	ex.reveal(Vector3(-512, 0, -512), 40.0)
	assert_true(ex.is_explored(-512 + 5, -512 + 5))
	assert_true(ex.is_explored(-512 - 5, -512 - 5))


func test_explored_survives_a_save_round_trip() -> void:
	var p := PlayerState.new()
	p.explored.reveal(Vector3(100, 0, 100), 150.0)
	var d: Dictionary = p.to_dict()
	var json: String = JSON.stringify(d)
	var back := PlayerState.new()
	back.from_dict(JSON.parse_string(json))
	assert_eq(back.explored.blocks.size(), p.explored.blocks.size())
	assert_true(back.explored.is_explored(100, 100))
	assert_false(back.explored.is_explored(400, 400))


func test_an_old_save_without_the_field_loads_unexplored() -> void:
	var p := PlayerState.new()
	var d: Dictionary = p.to_dict()
	d.erase("explored")
	var back := PlayerState.new()
	back.explored.reveal(Vector3.ZERO, 50.0)
	back.from_dict(d)
	assert_true(back.explored.is_empty(), "the map reveals round the bed or drop site on its first tick")


func test_fog_image_clears_explored_cells() -> void:
	var ex := ExploredMap.new()
	ex.reveal(Vector3(48, 0, 48), 10.0)
	var img: Image = WorldMap.fog_image(ex, Rect2(0, 0, 320, 320))
	assert_eq(img.get_width(), 10)
	assert_eq(img.get_pixel(1, 1).a, 0.0)
	assert_gt(img.get_pixel(8, 8).a, 0.5)


## Image colours are 8-bit: compare within a step.
static func _near(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) < 0.01 and absf(a.g - b.g) < 0.01 and absf(a.b - b.b) < 0.01
