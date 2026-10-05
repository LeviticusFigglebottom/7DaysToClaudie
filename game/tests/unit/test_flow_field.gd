extends GutTest
## Hum flow field: routes toward the player, detours through gaps, and when the base is sealed
## converges on the weakest wall (weak-point targeting).


func _flat(x: float, z: float) -> float:
	return 0.0


func _field(radius: float = 30.0) -> FlowField:
	var f := FlowField.new()
	f.setup(Vector3.ZERO, radius, 1.0)
	f.build_terrain(_flat, Callable(), 42.0)
	return f


func _walk(f: FlowField, from: Vector3, steps: int = 200) -> Vector3:
	var p: Vector3 = from
	for i: int in steps:
		var d: Vector3 = f.direction_at(p)
		if d == Vector3.ZERO:
			break
		p += d * 0.5
	return p


func test_open_ground_leads_to_target() -> void:
	var f := _field()
	f.integrate([Vector3.ZERO] as Array[Vector3])
	var d: Vector3 = f.direction_at(Vector3(20, 0, 0))
	assert_almost_eq(d.x, -1.0, 0.05)
	assert_lt(_walk(f, Vector3(20, 0, 15)).length(), 1.5)


func test_walls_with_a_gap_route_through_the_gap() -> void:
	var f := _field()
	# Wall along x = 8 from z = -25 to z = 25 except a 4 m gap at z = 14..18.
	f.add_structures([{"a": Vector3(8, 0, -25), "b": Vector3(8, 0, 12), "hp": 800.0},
		{"a": Vector3(8, 0, 20), "b": Vector3(8, 0, 25), "hp": 800.0}], 0.05, 0.6)
	f.integrate([Vector3.ZERO] as Array[Vector3])
	assert_false(f.path_crosses_structure(Vector3(20, 0, 0)), "walks round through the gap")


func test_sealed_base_converges_on_the_weak_wall() -> void:
	var f := _field()
	# A 12 m square around the target: north wall weak (60 hp), the rest strong (900 hp).
	f.add_structures([
		{"a": Vector3(-6, 0, -6), "b": Vector3(6, 0, -6), "hp": 60.0},
		{"a": Vector3(6, 0, -6), "b": Vector3(6, 0, 6), "hp": 900.0},
		{"a": Vector3(6, 0, 6), "b": Vector3(-6, 0, 6), "hp": 900.0},
		{"a": Vector3(-6, 0, 6), "b": Vector3(-6, 0, -6), "hp": 900.0}], 0.05, 0.6)
	f.integrate([Vector3.ZERO] as Array[Vector3])
	assert_true(f.path_crosses_structure(Vector3(0, 0, 20)), "the south side has no way in")
	# An attacker from the south-east goes round to the weak north wall instead of the strong one.
	var p: Vector3 = Vector3(10, 0, 20)
	var reached_north: bool = false
	for i: int in 300:
		var d: Vector3 = f.direction_at(p)
		if d == Vector3.ZERO:
			break
		p += d * 0.5
		if p.z < -5.0 and absf(p.x) < 6.0:
			reached_north = true
			break
	assert_true(reached_north, "converged on the weak wall")


func test_deep_water_is_impassable() -> void:
	var f := FlowField.new()
	f.setup(Vector3.ZERO, 20.0, 1.0)
	var water := func(x: float, z: float) -> float: return 2.0 if absf(x - 8.0) < 2.0 and z > -15.0 else -INF
	f.build_terrain(_flat, water, 42.0)
	f.integrate([Vector3.ZERO] as Array[Vector3])
	var end: Vector3 = _walk(f, Vector3(16, 0, 0), 400)
	assert_lt(end.length(), 1.5, "walked round the river")


func test_horde_walks_around_a_town_building() -> void:
	var f := _field()
	# An 8 x 8 m house centred at x = 12 (rotated 30 degrees) between the spawn and the base.
	var xf := Transform3D(Basis(Vector3.UP, deg_to_rad(30.0)), Vector3(12, 0, 0))
	f.add_buildings([{"xf": xf, "rect": Rect2(-4, -4, 8, 8)}])
	f.integrate([Vector3.ZERO] as Array[Vector3])
	var p: Vector3 = Vector3(24, 0, 0)
	var entered: bool = false
	for i: int in 200:
		var d: Vector3 = f.direction_at(p)
		if d == Vector3.ZERO:
			break
		p += d * 0.5
		var lp: Vector3 = xf.affine_inverse() * p
		if absf(lp.x) < 3.5 and absf(lp.z) < 3.5:
			entered = true
	assert_false(entered, "the route goes round the house, not through its walls")
	assert_lt(p.length(), 1.5, "and still reaches the base")
