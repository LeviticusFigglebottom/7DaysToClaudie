extends GutTest
## Vegetation keeps off cave mouths (CAVES_PLAN WS-E, ADR-0056), by index like a clearing so the
## scatter and the saved trees keep their indices: on cave_hill's real grotto, the near chunks hide
## every layer's instances on the mouth's apron (CaveSet.keep_out) and show them again when the
## cave is removed (caves_changed), and the far layer's scatter leaves the apron's trees out.

const Hill := preload("res://tests/unit/helpers/cave_hill.gd")

var _hw: Node3D
var _tm: TerrainManager
var _plan: CavePlan


func before_all() -> void:
	_hw = Hill.make()
	add_child(_hw)
	Hill.setup(_hw)
	_tm = _hw.get(&"terrain")
	_plan = Hill.place_grotto(_tm)


func after_all() -> void:
	_hw.free()


func _inst(index: int, x: float, z: float) -> VegetationScatter.Instance:
	var i := VegetationScatter.Instance.new()
	i.index = index
	i.species = &"test"
	i.pos = Vector3(x, _tm.height_at(x, z), z)
	return i


## A point on the mouth's apron (keep_out), outside the cave's air box.
func _apron_point() -> Vector2:
	var m: Vector3 = _plan.mouth.origin
	var out: Vector3 = _plan.mouth.basis.z
	for d: float in [3.0, 2.0, 1.0, 0.5]:
		var p := Vector2(m.x + out.x * d, m.z + out.z * d)
		if _plan.keep_out(p.x, p.y):
			return p
	return Vector2(m.x, m.z)


func test_near_chunks_hide_the_apron_and_show_it_again() -> void:
	assert_true(_plan != null and _plan.ok, "the grotto planned")
	var a: Vector2 = _apron_point()
	assert_true(_tm.caves.call(&"keep_out", a.x, a.y), "a point on the apron at %s" % a)
	var key := Vector2i(floori(a.x / VegetationManager.CHUNK), floori(a.y / VegetationManager.CHUNK))
	# Far enough from the mouth, in the same chunk.
	var far := Vector2(key.x * VegetationManager.CHUNK + 60.0, key.y * VegetationManager.CHUNK + 60.0)
	assert_false(_tm.caves.call(&"keep_out", far.x, far.y))
	var vm := VegetationManager.new()
	vm.terrain = _tm
	add_child_autofree(vm)
	_tm.caves_changed.connect(vm._on_caves_changed)
	vm._data[key] = {"tree": [_inst(3, a.x, a.y), _inst(4, far.x, far.y)], "ground": [_inst(17, a.x + 0.2, a.y)]}
	vm._recompute_cleared(key)
	assert_true(vm._is_removed(key, 3), "the tree on the apron is hidden")
	assert_true(vm._is_removed(key, 17), "and the grass")
	assert_false(vm._is_removed(key, 4), "a tree away from the mouth stays")
	_tm.remove_cave(_plan.id)
	assert_false(vm._is_removed(key, 3), "the cave gone: the apron grows again")
	_tm.place_cave(_plan.id, _plan)
	assert_true(vm._is_removed(key, 3), "and placed again: hidden again")
	_tm.caves_changed.disconnect(vm._on_caves_changed)


func test_far_scatter_leaves_the_apron_out() -> void:
	var a: Vector2 = _apron_point()
	var key := Vector2i(floori(a.x / VegetationManager.CHUNK), floori(a.y / VegetationManager.CHUNK))
	var rt: RegionTerrain = _tm.region_terrain_at(a.x, a.y)
	# The hill is meadow: make it forest so the far layer has trees to leave out.
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	rt.vegmask.fill(255)
	var none: Object = CaveSet.combined([], {})
	var trees: int = 0
	var on_apron: int = 0
	for seed_v: int in range(1, 13):
		var all: Array = VegetationManager._scatter_far_chunk(rt, key, seed_v, _tm.height_at, {}, [], null)
		var kept: Array = VegetationManager._scatter_far_chunk(rt, key, seed_v, _tm.height_at, {}, [], _tm.caves)
		var here: int = 0
		for inst: VegetationScatter.Instance in all:
			if _plan.keep_out(inst.pos.x, inst.pos.z):
				here += 1
		for inst2: VegetationScatter.Instance in kept:
			assert_false(_plan.keep_out(inst2.pos.x, inst2.pos.z), "no far tree on the apron")
		assert_eq(kept.size(), all.size() - here, "only the apron's trees are left out (seed %d)" % seed_v)
		assert_eq(VegetationManager._scatter_far_chunk(rt, key, seed_v, _tm.height_at, {}, [], none).size(), all.size(), "no caves: nothing left out")
		trees += all.size()
		on_apron += here
	gut.p("[cave veg] far chunk %s, 12 seeds: %d trees, %d on the apron" % [key, trees, on_apron])
	assert_gt(on_apron, 0, "some seed put a tree on the apron (the check is not vacuous)")
