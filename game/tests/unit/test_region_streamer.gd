extends GutTest
## RegionRings, the pure ring logic of region streaming (ADR-0038, RWG_V2_PLAN §1.2): wanted and
## keep sets with hysteresis, priority by heading, the max_attached cap, pins, unbuilt regions,
## prefetch and several focus points. A 5x5 grid of 1 km regions named "c_r".

var regions: Dictionary = {}
var built: Dictionary = {}


func before_each() -> void:
	regions.clear()
	built.clear()
	for r: int in 5:
		for c: int in 5:
			var rid: String = "%d_%d" % [c, r]
			regions[rid] = Rect2(c * 1000.0, r * 1000.0, 1000.0, 1000.0)
			built[rid] = true


func _rings(cfg: Dictionary = {}) -> RegionRings:
	return RegionRings.new(cfg if not cfg.is_empty() else Content.config(&"streaming").get("region", {}))


func _sorted(a: Array) -> Array:
	var b: Array = a.duplicate()
	b.sort()
	return b


func test_the_config_is_loaded() -> void:
	var cfg: Dictionary = Content.config(&"streaming").get("region", {})
	assert_eq(float(cfg.get("load", 0)), 640.0)
	assert_eq(int(cfg.get("max_attached", 0)), 9)


func test_the_middle_of_a_region_wants_it_and_its_four_sides() -> void:
	var p: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3.ZERO, {})
	# Sides are 500 m away, corners 707 m (beyond 640).
	assert_eq(_sorted(p["target"]), _sorted(["2_2", "1_2", "3_2", "2_1", "2_3"]))
	assert_eq(p["attach"][0], "2_2", "the region under the player first")
	assert_eq(p["detach"], [])


func test_attached_regions_stay_until_the_unload_ring() -> void:
	var attached: Dictionary = {"1_1": true, "0_2": true, "2_2": true}
	var p: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3.ZERO, attached)
	assert_true((p["target"] as Array).has("1_1"), "a corner at 707 m is kept once attached")
	assert_true((p["detach"] as Array).has("0_2"), "a region 1500 m away goes")
	assert_false((p["attach"] as Array).has("1_1"), "a kept region is not attached again")


func test_the_regions_ahead_come_first() -> void:
	var east: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3(6, 0, 0), {})
	var west: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3(-6, 0, 0), {})
	assert_eq(east["attach"][1], "3_2", "running east: the east side right after the region underfoot")
	assert_eq(west["attach"][1], "1_2")
	assert_lt(float(east["priority"]["3_2"]), float(east["priority"]["1_2"]))


func test_max_attached_keeps_the_nearest_and_drops_the_rest() -> void:
	var rings: RegionRings = _rings({"load": 640.0, "unload": 1100.0, "max_attached": 3})
	var attached: Dictionary = {"1_2": true, "3_2": true, "2_1": true, "2_3": true}
	var p: Dictionary = rings.plan(regions, built, [Vector3(2500, 0, 2100)], Vector3.ZERO, attached)
	assert_eq((p["target"] as Array).size(), 3)
	assert_eq(p["target"][0], "2_2")
	assert_eq(p["target"][1], "2_1", "100 m to the north side")
	assert_true((p["detach"] as Array).has("2_3"), "the furthest attached region makes room")
	assert_eq(p["attach"], ["2_2"])


func test_a_pin_holds_a_region_wherever_the_player_goes() -> void:
	var pins: Dictionary = {&"hum": Rect2(200, 200, 100, 100)}
	var p: Dictionary = _rings().plan(regions, built, [Vector3(4500, 0, 4500)], Vector3.ZERO, {"0_0": true}, pins)
	assert_true((p["target"] as Array).has("0_0"), "the Hum's base stays loaded 5 km away")
	assert_eq(p["target"][0], "0_0", "pinned regions come before the cap")
	assert_false((p["detach"] as Array).has("0_0"))


func test_unbuilt_regions_never_attach_or_prefetch() -> void:
	built.erase("3_2")
	var p: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3(6, 0, 0), {})
	assert_false((p["target"] as Array).has("3_2"))
	assert_false((p["prefetch"] as Array).has("3_2"))
	assert_true((p["distance"] as Dictionary).has("3_2"), "distances still cover every region")


func test_prefetch_reaches_further_along_the_heading() -> void:
	var still: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3.ZERO, {})
	var east: Dictionary = _rings().plan(regions, built, [Vector3(2500, 0, 2500)], Vector3(6, 0, 0), {})
	assert_true((still["prefetch"] as Array).has("1_1"), "a corner at 707 m is prefetched")
	assert_false((still["prefetch"] as Array).has("4_2"), "1500 m is beyond 1400 standing still")
	assert_true((east["prefetch"] as Array).has("4_2"), "but within reach running towards it")
	for rid: String in still["prefetch"]:
		assert_false((still["target"] as Array).has(rid), "prefetch never repeats the attached set")


func test_every_focus_point_streams_its_own_area() -> void:
	var p: Dictionary = _rings().plan(regions, built, [Vector3(500, 0, 500), Vector3(4500, 0, 4500)], Vector3.ZERO, {})
	assert_true((p["target"] as Array).has("0_0"))
	assert_true((p["target"] as Array).has("4_4"))
	assert_false((p["target"] as Array).has("2_2"))


func test_rect_distance() -> void:
	var r := Rect2(0, 0, 10, 10)
	assert_eq(RegionRings.rect_distance(r, Vector2(5, 5)), 0.0)
	assert_eq(RegionRings.rect_distance(r, Vector2(13, 5)), 3.0)
	assert_almost_eq(RegionRings.rect_distance(r, Vector2(13, 14)), 5.0, 1e-4)
