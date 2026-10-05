extends GutTest
## RoadMarkings: dashed centre line and edge lines along a road profile, none on bridge decks,
## nothing twice when two regions record the same road.


func _markings() -> RoadMarkings:
	var rm := RoadMarkings.new()
	var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	rm._albedo = [ImageTexture.create_from_image(img)]
	rm._normal = [null]
	add_child_autofree(rm)
	return rm


func _road(id: String, length: float) -> Dictionary:
	var pts: Array = []
	var x: float = 0.0
	while x <= length:
		pts.append([x, 5.0, 0.0])
		x += 4.0
	return {"id": id, "surface": "asphalt", "width": 8.0, "points": pts}


func test_dashes_and_edge_lines_follow_the_road() -> void:
	var rm := _markings()
	rm._mark(_road("route", 120.0))
	var centre: int = 0
	var edges: int = 0
	for d: Decal in rm.get_children():
		assert_almost_eq(d.position.y, 5.0, 0.01, "decal sits on the road profile")
		if absf(d.position.z) < 0.01:
			centre += 1
			assert_eq(d.modulate, RoadMarkings.YELLOW)
			assert_almost_eq(d.size.x, RoadMarkings.DASH + 0.08, 0.01)
		else:
			edges += 1
			assert_almost_eq(absf(d.position.z), 4.0 - RoadMarkings.EDGE_INSET, 0.01)
	assert_between(centre, 9, 10, "a 3 m dash every 12 m over 120 m")
	assert_eq(edges, 2 * 20, "both edges in 6 m segments")


func test_no_paint_on_bridges_and_no_duplicates() -> void:
	var rm := _markings()
	rm._spans.append({"from": Vector3(40.0, 0.0, 0.0), "to": Vector3(70.0, 0.0, 0.0), "width": 9.0})
	var road: Dictionary = _road("route", 120.0)
	rm._mark(road)
	var n: int = rm.count
	rm._mark(road)
	assert_eq(rm.count, n, "a road recorded by a second region adds nothing")
	for d: Decal in rm.get_children():
		assert_false(d.position.x > 41.0 and d.position.x < 69.0, "no decal on the deck at x %.1f" % d.position.x)


func test_only_two_lane_asphalt_that_wants_lines() -> void:
	var road: Dictionary = _road("route", 40.0)
	assert_true(RoadMarkings.paints(road), "8 m asphalt is painted")
	var lot: Dictionary = road.duplicate()
	lot["markings"] = false
	assert_false(RoadMarkings.paints(lot), "a parking lot opts out")
	var lane: Dictionary = road.duplicate()
	lane["width"] = 5.0
	assert_false(RoadMarkings.paints(lane), "narrow lanes stay bare")
	var track: Dictionary = road.duplicate()
	track["surface"] = "gravel"
	assert_false(RoadMarkings.paints(track), "gravel stays bare")
