extends GutTest
## The viewmodel indoors (ViewModel.sheltered_at / set_exposure): under a POI's roof or a built one
## the arms and the held item draw with weather_exposure 0, so the skin and sleeves don't take the
## rain gloss and snow; outside they take the weather again.


class FakePois extends Node:
	var inside: bool = false

	func is_indoors(_pos: Vector3) -> bool:
		return inside


class FakeBuilding extends Node:
	var roofed: bool = false

	func is_sheltered(_pos: Vector3) -> bool:
		return roofed


class FakeWorld extends Node:
	var pois: Node = null
	var building: Node = null


func _world() -> FakeWorld:
	var w := FakeWorld.new()
	w.pois = FakePois.new()
	w.building = FakeBuilding.new()
	w.add_child(w.pois)
	w.add_child(w.building)
	add_child_autofree(w)
	return w


func test_sheltered_indoors_or_under_a_roof() -> void:
	var w: FakeWorld = _world()
	assert_false(ViewModel.sheltered_at(null, Vector3.ZERO), "no world: outside")
	assert_false(ViewModel.sheltered_at(w, Vector3.ZERO), "open sky")
	(w.pois as FakePois).inside = true
	assert_true(ViewModel.sheltered_at(w, Vector3.ZERO), "in a POI room")
	(w.pois as FakePois).inside = false
	(w.building as FakeBuilding).roofed = true
	assert_true(ViewModel.sheltered_at(w, Vector3.ZERO), "under a built roof")
	var bare := Node.new()
	add_child_autofree(bare)
	assert_false(ViewModel.sheltered_at(bare, Vector3.ZERO), "a world without pois or building: outside")


func test_exposure_reaches_every_mesh_and_comes_back() -> void:
	var vm := ViewModel.new()
	add_child_autofree(vm)
	var mi := MeshInstance3D.new()
	mi.mesh = BoxMesh.new()
	vm.add_child(mi)
	vm.set_exposure(0.0)
	assert_eq(float(mi.get_instance_shader_parameter(&"weather_exposure")), 0.0, "indoors: no weather")
	vm.set_exposure(1.0)
	assert_eq(float(mi.get_instance_shader_parameter(&"weather_exposure")), 1.0, "outside again")
