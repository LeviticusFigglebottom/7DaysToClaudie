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
			if c.is_equal_approx(WorldMap.WATER):
				water += 1
			elif c.is_equal_approx(WorldMap.ROAD):
				road += 1
			elif c.is_equal_approx(WorldMap.PAPER):
				plain += 1
	assert_gt(water, 20, "the Tamsin and Larch Pond")
	assert_gt(road, 20, "Route 9")
	assert_lt(plain, img.get_width() * img.get_height() / 8, "the region is shaded, not blank paper")
