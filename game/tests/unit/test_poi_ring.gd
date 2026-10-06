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


func test_all_buildings_lists_the_unbuilt_ones_too() -> void:
	var s: Array = _setup({"near": [_poi("a", 100.0)], "far": [_poi("d", 2000.0)]})
	var pm: PoiManager = s[1]
	var all: Array = pm.all_buildings()
	assert_eq(all.size(), 2, "every building of the world, nothing built")
	var pd: PoiDef = Content.get_def(&"poi", StringName(PICK)) as PoiDef
	for b: Dictionary in all:
		assert_eq(b["def"], StringName(PICK))
		assert_eq(int(b["tier"]), pd.tier, "its tier from its def, for the directives")


func test_markers_show_every_building_without_touching_saved_state() -> void:
	var s: Array = _setup({"near": [_poi("a", 100.0)], "far": [_poi("d", 2000.0)]})
	var pm: PoiManager = s[1]
	var before: int = Game.session.world.pois.size() if Game.session != null else 0
	var ms: Array = pm.markers()
	assert_eq(ms.size(), 2, "both buildings on the map, nothing built")
	assert_false(bool(ms[0]["visited"]))
	if Game.session != null:
		assert_eq(Game.session.world.pois.size(), before, "drawing the map adds no saved state")


func test_poi_at_tests_turned_neighbours_in_their_own_frames() -> void:
	# Two buildings turned 45 degrees side by side: each one's world AABB covers the other's
	# corner, so only a test in the building's own frame tells them apart (TD-107).
	var pm := PoiManager.new()
	add_child_autofree(pm)
	var pd: PoiDef = Content.get_def(&"poi", StringName(PICK)) as PoiDef
	var turn := Basis(Vector3.UP, PI * 0.25)
	var a: PoiInstance = pm._build_poi(pd, &"ring_a", Transform3D(turn, Vector3(0.0, 0.0, 0.0)))
	var b: PoiInstance = pm._build_poi(pd, &"ring_b", Transform3D(turn, Vector3(42.0, 0.0, 0.0)))
	var la: AABB = a.local_bounds()
	var mid_a: Vector3 = a.global_transform * la.get_center()
	assert_eq(pm.poi_at(mid_a), a, "the middle of a")
	assert_eq(pm.poi_at(b.global_transform * b.local_bounds().get_center()), b, "the middle of b")
	# Just outside a's box along its own +x, still inside its world AABB.
	var out_a: Vector3 = a.global_transform * Vector3(la.end.x + 0.5, la.get_center().y, la.position.z + 0.5)
	assert_true(a.world_bounds().has_point(out_a), "the probe is inside a's world AABB")
	assert_ne(pm.poi_at(out_a), a, "but outside a itself")
	pm._free_building(&"ring_a", null, null)
	assert_null(pm.poi_at(mid_a), "freed buildings leave the grid")
	assert_eq(pm.poi_at(b.global_transform * b.local_bounds().get_center()), b)


func test_fixtures_batch_per_cell() -> void:
	# Plain street fixtures share one body and a MultiMesh per model in their 64 m cell (TD-107).
	var pm := PoiManager.new()
	add_child_autofree(pm)
	var a := Transform3D(Basis(), Vector3(10.0, 2.0, 10.0))
	var b := Transform3D(Basis(Vector3.UP, 0.5), Vector3(20.0, 3.0, 12.0))
	var cell := {"models": {"props/test_lamp": [a, b], "props/test_bench": [a]}, "boxes": [[a, Vector3(1, 2, 1)], [b, Vector3(1, 2, 1)]]}
	var body: StaticBody3D = pm.fixture_cell(cell, "Fixtures_test")
	var mmis: Array = body.find_children("*", "MultiMeshInstance3D", false, false)
	assert_eq(mmis.size(), 2, "one MultiMesh per model")
	var lamp: MultiMesh = (body.get_node("test_lamp") as MultiMeshInstance3D).multimesh
	assert_eq(lamp.instance_count, 2)
	# (Instance transforms aren't read back: the headless dummy renderer doesn't store them.)
	assert_eq(body.find_children("*", "CollisionShape3D", false, false).size(), 2, "a box per solid fixture")
	assert_true(body.global_transform.is_equal_approx(Transform3D.IDENTITY))
