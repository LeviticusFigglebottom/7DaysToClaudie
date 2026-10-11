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


## Player report 5: the buildings of the towns off the minimap were drawn where they fell, in grey
## clumps over the readouts round the map. Only those on the map are drawn.
func test_only_buildings_on_the_minimap_are_drawn() -> void:
	assert_true(Tether.on_map(Vector2(10.0, 200.0)))
	assert_true(Tether.on_map(Vector2(0.0, 0.0)), "the map's own corner")
	assert_false(Tether.on_map(Vector2(-30.0, 120.0)), "left of the map: over the readouts")
	assert_false(Tether.on_map(Vector2(120.0, Tether.MAP_PX + 40.0)), "below it: over the directives")
	assert_false(Tether.on_map(Vector2(Tether.MAP_PX + 1.0, 5.0)))


## The hub's nit: a 20-letter world name was cut ("THE UNMAPPED COUN…") at the fixed 14 px. The
## caption now shrinks to fit, so the whole name shows beside the sector.
func test_a_mid_length_name_shows_whole_at_a_smaller_size() -> void:
	var rw := WorldDef.new()
	rw._parse({"id": "rw_unmapped", "name": "The Unmapped Country", "cols": 1, "rows": 1, "region_size": 1024,
		"regions": [{"id": "a1_grey_woods", "cell": "A1"}]})
	var cap: String = Tether.map_caption(rw, Vector3(500.0, 0.0, 500.0))
	assert_eq(cap, "THE UNMAPPED COUNTRY  ·  SECTOR A1")
	var font: Font = ThemeDB.fallback_font
	var width: float = font.get_string_size("HOLLOWMERE VALLEY  ·  SECTOR D6", HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x + 2.0
	var fs: int = Tether.caption_size(cap, font, width)
	assert_lt(fs, 14, "a longer caption steps down")
	assert_lte(font.get_string_size(cap, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x, width, "and fits")
	assert_eq(Tether.caption_size("HOLLOWMERE VALLEY  ·  SECTOR D6", font, width), 14, "a short one keeps 14 px")
