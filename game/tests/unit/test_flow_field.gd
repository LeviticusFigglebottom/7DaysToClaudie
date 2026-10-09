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


class FakeCave:
	extends RefCounted
	var mouth := Transform3D(Basis.IDENTITY, Vector3(20.0, 5.0, 0.0))


class FakeTerrain:
	extends RefCounted
	## A cave whose air fills x in [0, 10], y below 3.
	func cave_at(p: Vector3) -> Object:
		return FakeCave.new() if p.x >= 0.0 and p.x <= 10.0 and p.y < 3.0 else null


func test_a_target_in_a_cave_is_reached_through_its_mouth() -> void:
	# TD-279: the field is one layer over the surface; inside a cave the nav mesh takes over.
	var t: Array[Vector3] = FlowField.surface_targets([Vector3(5.0, 0.0, 0.0), Vector3(-30.0, 10.0, 0.0)], FakeTerrain.new())
	assert_eq(t.size(), 2)
	assert_eq(t[0], Vector3(20.0, 5.0, 0.0), "the cave's mouth stands in for the target inside it")
	assert_eq(t[1], Vector3(-30.0, 10.0, 0.0), "a target on the surface stays")
	assert_eq(FlowField.surface_targets([Vector3(1, 0, 0)], null), [Vector3(1, 0, 0)] as Array[Vector3], "no terrain, no caves")


func test_a_body_underground_gets_no_direction() -> void:
	var f := FlowField.new()
	f.setup(Vector3.ZERO, 20.0, 1.0)
	f.build_terrain(func(_x: float, _z: float) -> float: return 10.0, Callable(), 45.0)
	var tg: Array[Vector3] = [Vector3(10.0, 10.0, 0.0)]
	f.integrate(tg)
	assert_ne(f.direction_at(Vector3(-5.0, 10.0, 0.0)), Vector3.ZERO, "on the surface it points the way")
	assert_eq(f.direction_at(Vector3(-5.0, 4.0, 0.0)), Vector3.ZERO, "6 m under the surface: a cave, the nav mesh's")
