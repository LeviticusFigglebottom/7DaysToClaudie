extends GutTest
## PoiRegistry (RWG v2 Phase 3): every building of a world as data, chosen exactly as PoiManager's
## build-everything path chose them, with footprint boxes the streamed world can query before any
## building exists.

const TOWN_ID: StringName = &"test_registry_town"
const PICK: StringName = &"calder_hardware"

var _fw: FrameworkDef


func before_each() -> void:
	# An organic town's framework: frame lots (two in the region's rect, one outside it), a
	# reserved lot and an empty one. Authored picks, so nothing is generated.
	_fw = FrameworkDef.new()
	_fw.id = TOWN_ID
	_fw.kind = &"framework"
	_fw.lots = [
		{"id": "a", "frame": [120.0, 80.0, 16.0, 20.0, 35.0], "y": 7.5, "pick": String(PICK)},
		{"id": "b", "frame": [60.0, 40.0, 16.0, 20.0, -90.0], "y": 4.0, "pick": String(PICK)},
		{"id": "c", "frame": [700.0, 80.0, 16.0, 20.0, 0.0], "y": 2.0, "pick": String(PICK)},
		{"id": "d", "frame": [90.0, 140.0, 16.0, 20.0, 0.0], "reserved": "plaza"},
	]
	_fw.fixtures = []
	ContentDB.instance.add_runtime_def(_fw)


func after_each() -> void:
	ContentDB.instance.remove_runtime_def(&"framework", TOWN_ID)


func _rt(placements: Array) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = "r0"
	rt.placements = placements
	return rt


func _seed() -> int:
	return Game.session.world_seed if Game.session != null else 0


## PoiManager's own path, queueing instead of building: instance id -> the queued transform.
func _manager_xfs(pl: Dictionary) -> Dictionary:
	var pm := PoiManager.new()
	var host := Node.new()
	pm.world = host
	pm._queueing = true
	pm._place_framework(pl)
	var out: Dictionary = {}
	for step: Array in pm._queue_builds:
		var job: Dictionary = (step[1] as Callable).get_bound_arguments()[0]
		out[job["id"]] = job["xf"]
	pm.free()
	host.free()
	return out


func test_town_lots_match_the_build_everything_path() -> void:
	var town := {"kind": "town", "def": String(TOWN_ID), "id": "t1", "origin": [0.0, 0.0, 0.0], "rotation": 0.0, "rect": [0.0, 0.0, 512.0, 512.0]}
	var reg := PoiRegistry.build(null, {"r0": _rt([town])}, {}, _seed())
	var want: Dictionary = _manager_xfs(town)
	assert_eq(want.size(), 2, "PoiManager places the two lots inside the rect")
	assert_eq(reg.entries.size(), want.size(), "and the registry has exactly those")
	var pd: PoiDef = Content.get_def(&"poi", PICK) as PoiDef
	for id: StringName in want:
		assert_true(reg.entries.has(id), "%s registered" % id)
		if not reg.entries.has(id):
			continue
		var e: Dictionary = reg.entries[id]
		assert_eq(e["region"], "r0")
		assert_eq(reg.def_id(id), PICK, "an authored pick's def is known without generating")
		var got: Transform3D = PoiRegistry.building_xf(e, pd)
		assert_true(got.is_equal_approx(want[id]), "%s: the same transform as the build path" % id)
		assert_eq(reg.footprint_at(e["center"]), id, "%s: its centre is on its footprint" % id)
	assert_false(reg.entries.has(&"t1/c"), "a lot outside the region's rect belongs to another region")
	assert_false(reg.entries.has(&"t1/d"), "a reserved lot has no building")


func test_rect_lots_of_a_main_map_framework_match() -> void:
	var fw: FrameworkDef = Content.get_def(&"framework", &"pell_crossing") as FrameworkDef
	assert_not_null(fw, "Pell's Crossing framework")
	if fw == null:
		return
	var pl := {"kind": "framework", "def": "pell_crossing", "id": "pell_crossing", "origin": [-112.0, 30.0, 2004.0], "rotation": 0.0}
	var fixtures: Array = fw.fixtures
	fw.fixtures = []
	var want: Dictionary = _manager_xfs(pl)
	fw.fixtures = fixtures
	var lots: Dictionary = {}
	var reg := PoiRegistry.build(null, {"d6": _rt([pl])}, lots, _seed())
	assert_gt(want.size(), 5, "the town has buildings (%d)" % want.size())
	assert_eq(reg.entries.size(), want.size(), "one entry per building the build path places")
	assert_true(lots.has("pell_crossing"), "the registry resolved and cached the lots")
	for id: StringName in want:
		var e: Dictionary = reg.entries.get(id, {})
		assert_false(e.is_empty(), "%s registered" % id)
		if e.is_empty():
			continue
		var res: Dictionary = e["res"]
		var pd: PoiDef = PoiManager.Lots.def_for(res)
		if pd == null:
			continue
		assert_true(PoiRegistry.building_xf(e, pd).is_equal_approx(want[id]), "%s: the same transform" % id)


func test_a_turned_poi_footprint_and_nearest_first() -> void:
	# A 20 x 10 building turned 90 degrees: its footprint runs 10 along x and 20 along z.
	# No such def: the box is the pad (a known def's footprint would widen it, see below).
	var p1 := {"kind": "poi", "def": "test_registry_shed", "id": "p1", "origin": [100.0, 5.0, 100.0], "rotation": 90.0, "size": [20, 10]}
	var p2 := {"kind": "poi", "def": "test_registry_shed", "id": "p2", "origin": [300.0, 5.0, 100.0], "rotation": 0.0, "size": [12, 12]}
	var reg := PoiRegistry.build(null, {"r0": _rt([p1, p2])}, {}, _seed())
	var e: Dictionary = reg.entries[&"p1"]
	var c: Vector2 = e["center"]
	var xf: Transform3D = PoiRegistry.placement_xf(p1)
	var want: Vector3 = xf * Vector3(10.0, 0.0, 5.0)
	assert_almost_eq(c, Vector2(want.x, want.z), Vector2.ONE * 1e-4, "centre of the turned footprint")
	assert_eq(reg.footprint_at(c + Vector2(4.0, 0.0)), &"p1", "4 m along x is inside (half width 5)")
	assert_eq(reg.footprint_at(c + Vector2(0.0, 9.0)), &"p1", "9 m along z is inside (half length 10)")
	assert_eq(reg.footprint_at(c + Vector2(7.0, 0.0)), &"", "7 m along x is outside")
	var near: Array = reg.near(c + Vector2(0.0, 30.0), 400.0)
	assert_eq(near.size(), 2)
	assert_eq(near[0][0], &"p1", "nearest first")
	assert_almost_eq(float(near[0][1]), 20.0, 1e-3, "distance to the box edge")
	assert_eq(reg.near(c, 50.0).size(), 1, "the far one is outside 50 m")
	assert_eq((reg.by_region["r0"] as Array).size(), 2)


func test_a_poi_box_covers_its_buried_levels() -> void:
	# The Corvane adit (ADR-0044): a 24 x 14 pad, levels running 70 m along its x under the ground.
	# The ring builds and frees by the box, so the box is the def's footprint, not the pad.
	var pd: PoiDef = Content.get_def(&"poi", &"corvane_larkspur_adit") as PoiDef
	assert_not_null(pd)
	var pl := {"kind": "poi", "def": "corvane_larkspur_adit", "id": "adit", "origin": [0.0, 0.0, 0.0], "rotation": 0.0, "size": [24, 14]}
	var reg := PoiRegistry.build(null, {"r0": _rt([pl])}, {}, _seed())
	var e: Dictionary = reg.entries[&"adit"]
	assert_almost_eq(e["half"], Vector2(pd.footprint) * 0.5, Vector2.ONE * 1e-4, "half extents of the footprint")
	assert_eq(reg.footprint_at(Vector2(60.0, 7.0)), &"adit", "60 m in, past the pad, is still the adit")

