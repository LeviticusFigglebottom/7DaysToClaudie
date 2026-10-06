extends GutTest
## The tether's map caption names the world and the sector the player is in (it was fixed to
## "LARCH HOLLOW · CORDON SECTOR D6", even in random worlds).


func test_caption_names_the_world_and_the_sector() -> void:
	var main: WorldDef = WorldDef.load_from("res://world/main_map")
	assert_eq(Tether.map_caption(main, Vector3(-292.0, 0.0, 2296.0)), "HOLLOWMERE VALLEY  ·  SECTOR D6", "the drop site lies in D6")
	assert_eq(Tether.map_caption(main, Vector3(0.0, 0.0, 0.0)), "HOLLOWMERE VALLEY  ·  SECTOR D4", "the sector follows the player")


func test_a_long_world_name_is_cut_short_but_the_sector_shows() -> void:
	var rw := WorldDef.new()
	rw._parse({"id": "rw_test", "name": "Saint Bartholomew's Crossing County", "cols": 2, "rows": 2, "region_size": 1024,
		"regions": [{"id": "a1_grey_woods", "cell": "A1"}, {"id": "b2_ashford", "cell": "B2"}]})
	var cap: String = Tether.map_caption(rw, Vector3(500.0, 0.0, 500.0))
	assert_true(cap.ends_with("SECTOR B2"), "the sector always shows: %s" % cap)
	assert_true(cap.begins_with("SAINT BARTHOLOMEW"), "the name is cut short, not dropped: %s" % cap)
	assert_lte(cap.length(), Tether.CAPTION_CHARS, "it fits beside the map")
	assert_true(Tether.map_caption(rw, Vector3(-500.0, 0.0, -500.0)).ends_with("SECTOR A1"))
	assert_eq(Tether.map_caption(null, Vector3.ZERO), "", "no world, no caption")
