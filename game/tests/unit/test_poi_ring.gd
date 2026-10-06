extends GutTest
## PoiManager's build ring in a streamed world (RWG v2 Phase 3): the nearest buildings within the
## build radius whose regions are attached are queued nearest first, at most max_built, and the
## ones that fall beyond the free radius are dropped.

const PICK: String = "calder_hardware"


class FakeWorld:
	extends Node
	var terrain: TerrainManager
	var ai: Node = null
	var poi_registry: PoiRegistry
	var streaming: bool = true
	var boot_focus := Vector3.ZERO
	var player: Node = null
	var is_ready: bool = false


func _poi(id: String, x: float) -> Dictionary:
	return {"kind": "poi", "def": PICK, "id": id, "origin": [x, 0.0, 0.0], "rotation": 0.0, "size": [12, 12]}


func _setup(placements: Dictionary) -> Array:
	var regions: Dictionary = {}
	for rid: String in placements:
		var rt := RegionTerrain.new()
		rt.region_id = rid
		rt.placements = placements[rid]
		regions[rid] = rt
	var w := FakeWorld.new()
	w.terrain = autofree(TerrainManager.new())
	w.terrain.regions = {"near": regions.get("near")}
	w.poi_registry = PoiRegistry.build(null, regions, {}, 0)
	var pm := PoiManager.new()
	pm.world = w
	pm.registry = w.poi_registry
	pm._queueing = true
	add_child_autofree(w)
	add_child_autofree(pm)
	return [w, pm]


func _queued(pm: PoiManager) -> Array:
	var out: Array = []
	for st: Array in pm._queue:
		out.append(str(st[2]).trim_prefix("poi plan "))
	return out


func test_nearest_first_within_the_radius_and_attached_regions() -> void:
	var s: Array = _setup({"near": [_poi("a", 300.0), _poi("b", 100.0), _poi("c", 700.0)], "far": [_poi("d", 50.0)]})
	var pm: PoiManager = s[1]
	pm._update_ring(Vector3.ZERO, 450.0)
	assert_eq(_queued(pm), ["b", "a"], "nearest first; c is beyond the radius; d's region isn't attached")
	assert_eq(pm._jobs.size(), 2)
	assert_eq(pm._region_of.get(&"b"), "near")
	pm._update_ring(Vector3.ZERO, 450.0)
	assert_eq(pm._jobs.size(), 2, "nothing queued twice")


func test_max_built_caps_the_ring() -> void:
	var s: Array = _setup({"near": [_poi("a", 100.0), _poi("b", 120.0), _poi("c", 140.0)]})
	var pm: PoiManager = s[1]
	pm._max_built = 2
	pm._update_ring(Vector3.ZERO, 450.0)
	assert_eq(_queued(pm), ["a", "b"], "the two nearest")


func test_buildings_beyond_the_free_radius_are_dropped() -> void:
	var s: Array = _setup({"near": [_poi("a", 100.0), _poi("b", 1000.0)]})
	var pm: PoiManager = s[1]
	pm._update_ring(Vector3.ZERO, 450.0)
	assert_true(pm._jobs.has(&"a"))
	pm._update_ring(Vector3(1000.0, 0.0, 0.0), 450.0)
	assert_false(pm._jobs.has(&"a"), "a is ~890 m away now, beyond the free radius")
	assert_false(pm._region_of.has(&"a"))
	assert_true(pm._jobs.has(&"b"), "and b came into the ring")


func test_footprint_at_sees_buildings_not_built_yet() -> void:
	var s: Array = _setup({"near": [_poi("a", 100.0)], "far": [_poi("d", 2000.0)]})
	var pm: PoiManager = s[1]
	assert_eq(pm.footprint_at(Vector3(106.0, 0.0, 6.0)), &"a", "on a's footprint, though nothing is built")
	assert_eq(pm.footprint_at(Vector3(2006.0, 0.0, 6.0)), &"d", "in a region not even attached")
	assert_eq(pm.footprint_at(Vector3(130.0, 0.0, 6.0)), &"", "18 m past its edge")
	assert_eq(pm.footprint_at(Vector3(130.0, 0.0, 6.0), 20.0), &"a", "within a 20 m margin")
