extends GutTest
## Sleepers in the yard (TD-269): PoiValidator lets a sleeper stand on a walkable ground-floor yard
## cell inside the footprint, off solid yard props, where the route can reach it; it spawns on the
## ground (the pad), not at the building's floor height, and keeps its floor pose (no seats outside).


## A 3 x 3 hut at the footprint's corner, its front door open to the yard; a chain-link fence
## (2.06 m long, along x) stands south of it at z = 4.5.
func _def(sleepers: Array) -> PoiDef:
	var raw: Dictionary = {"id": "t_yard_sleepers", "name": "T", "tier": 1, "footprint": [8, 8],
		"style": {"floor_height": 0.6},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"props": [{"id": "fence", "prop": "fence_chainlink_2m", "pos": [1.5, 4.5], "rot": 0}],
		"sleepers": sleepers,
		"route": [{"at": [-3, 3]}, {"at": [1, 1]}]}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	return d


func _about(v: PoiValidator, sid: String) -> PackedStringArray:
	var out: PackedStringArray = []
	for e: String in v.errors:
		if e.contains("sleeper '%s'" % sid) or e.contains("sleeper 0 "):
			out.append(e)
	return out


func test_a_sleeper_on_the_yard_is_valid() -> void:
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "out_a", "pos": [4.5, 5.5], "pose": "stand"}]))
	assert_eq(_about(v, "out_a"), PackedStringArray(), "a yard sleeper validates")
	for e: String in v.errors:
		assert_false(e.contains("not inside a room"), e)
	for w: String in v.warnings:
		assert_false(w.contains("out_a"), w)


func test_a_sleeper_in_the_room_still_validates() -> void:
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "in_a", "pos": [1.5, 1.5], "pose": "stand"}]))
	assert_eq(_about(v, "in_a"), PackedStringArray(), "an indoor sleeper validates")


func test_a_yard_sleeper_off_the_footprint_is_an_error() -> void:
	# x = -1.5 is on the validator's yard ring but off the 8 x 8 pad.
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "out_b", "pos": [-1.5, 1.5], "pose": "stand"}]))
	var found: bool = false
	for e: String in v.errors:
		found = found or (e.contains("out_b") and e.contains("footprint"))
	assert_true(found, "reported: %s" % [v.errors])


func test_a_yard_sleeper_in_a_fence_is_an_error() -> void:
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "out_c", "pos": [1.5, 4.6], "pose": "stand"}]))
	var found: bool = false
	for e: String in v.errors:
		found = found or (e.contains("out_c") and e.contains("yard prop 'fence'"))
	assert_true(found, "reported: %s" % [v.errors])
	# Clear of the fence on its far side: fine.
	var v2: PoiValidator = PoiValidator.validate(_def([{"id": "out_c", "pos": [1.5, 5.4], "pose": "stand"}]))
	assert_eq(_about(v2, "out_c"), PackedStringArray(), "a body's width off the fence")


func test_a_sleeper_outside_on_an_upper_level_is_still_an_error() -> void:
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "up_a", "pos": [4.5, 5.5], "level": 1, "pose": "stand"}]))
	var found: bool = false
	for e: String in v.errors:
		found = found or e.contains("not inside a room")
	assert_true(found, "reported: %s" % [v.errors])


func test_a_walled_in_yard_sleeper_is_unreachable() -> void:
	# A pen of fences round (4, 4): no gap, so the route's yard never reaches it.
	var d: PoiDef = _def([{"id": "penned", "pos": [4.5, 4.5], "pose": "stand"}])
	var props: Array = d.layout["props"]
	props.append_array([
		{"id": "pen_n", "prop": "fence_chainlink_2m", "pos": [4.5, 3.6], "rot": 0},
		{"id": "pen_s", "prop": "fence_chainlink_2m", "pos": [4.5, 5.4], "rot": 0},
		{"id": "pen_w", "prop": "fence_chainlink_2m", "pos": [3.6, 4.5], "rot": 90},
		{"id": "pen_e", "prop": "fence_chainlink_2m", "pos": [5.4, 4.5], "rot": 90}])
	var v: PoiValidator = PoiValidator.validate(d)
	var found: bool = false
	for e: String in v.errors:
		found = found or e.contains("unreachable cell")
	assert_true(found, "reported: %s" % [v.errors])


func test_a_yard_sleeper_spawns_on_the_ground() -> void:
	var l: PoiLayout = PoiLayout.compile(_def([{"id": "out_a", "pos": [4.5, 5.5]}, {"id": "in_a", "pos": [1.5, 1.5]}]))
	assert_almost_eq(l.floor_height, 0.6, 0.001, "a raised floor")
	var out_a: Dictionary = l.sleepers[0]
	var in_a: Dictionary = l.sleepers[1]
	assert_true(l.is_yard(0, out_a["cell"]), "the yard")
	assert_false(l.is_yard(0, in_a["cell"]), "the hut")
	assert_almost_eq(PoiInstance.sleeper_local(l, out_a).y, 0.0, 0.001, "the yard sleeper stands on the pad")
	assert_almost_eq(PoiInstance.sleeper_local(l, in_a).y, 0.6, 0.001, "the hut's sleeper stands on its floor")
	var p: Vector3 = PoiInstance.sleeper_local(l, out_a)
	assert_almost_eq(p.x, 4.5, 0.001, "where authored (x)")
	assert_almost_eq(p.z, 5.5, 0.001, "where authored (z)")


func test_a_yard_sleeper_keeps_its_floor_pose() -> void:
	# A lying sleeper in the yard looks for no bed (no warning), and one pinned to an anchor is told
	# that seats and beds are indoors.
	var l: PoiLayout = PoiLayout.compile(_def([{"id": "out_a", "pos": [4.5, 5.5], "pose": "lie"}]))
	var res: Dictionary = SleeperAnchors.check(l)
	assert_eq(res["warnings"], PackedStringArray(), "no bed wanted outside")
	assert_eq(SleeperAnchors.assign(l)["by_sleeper"], {}, "lies on the ground")
	var l2: PoiLayout = PoiLayout.compile(_def([{"id": "out_a", "pos": [4.5, 5.5], "pose": "lie", "anchor": "fence"}]))
	var errs: PackedStringArray = SleeperAnchors.check(l2)["errors"]
	assert_eq(errs.size(), 1, "a pinned anchor in the yard: %s" % [errs])
