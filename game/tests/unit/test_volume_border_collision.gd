extends GutTest
## The ground along a converted area's border (TD-010, ADR-0056): surface nets stop the volume's
## surface VOXEL / 2 short of a column's +X / +Z edge, and the heightmap collision used to leave a
## hole over the whole column, so a 0.25 m slit ran along those borders that small things fell
## through. On cave_hill's real grotto (committed columns x -2..1, z 0..1, so the +X border is
## x = 32 and the +Z border z = 32): rays and a small dropped body find the ground all along the
## strip, and a dig into the strip opens it (no lid left over the hole).

const Hill := preload("res://tests/unit/helpers/cave_hill.gd")

var _hw: Node3D
var _tm: TerrainManager
var _plan: CavePlan
var _focus: Node3D


func before_all() -> void:
	_hw = Hill.make()
	add_child(_hw)
	Hill.setup(_hw)
	_tm = _hw.get(&"terrain")
	_plan = Hill.place_grotto(_tm)
	_focus = Node3D.new()
	_hw.add_child(_focus)
	_focus.position = Vector3(24.0, _tm.height_at(24.0, 24.0), 24.0)
	_tm.focus = _focus
	Hill.drain(_tm)
	_tm.volume.flush()
	_tm.update_streaming(_focus.position, true)


func after_all() -> void:
	_hw.free()


func _ray_ground(x: float, z: float) -> float:
	var h: float = _tm.height_at(x, z)
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, h + 3.0, z), Vector3(x, h - 60.0, z))
	var hit: Dictionary = _hw.get_world_3d().direct_space_state.intersect_ray(q)
	return float(hit["position"].y) if not hit.is_empty() else -INF


func _settle() -> void:
	for i: int in 3:
		await get_tree().physics_frame


func test_a_rays_find_the_ground_along_the_borders() -> void:
	assert_true(_plan != null and _plan.ok, "the grotto planned")
	assert_true(_tm.volume.committed.has(Vector2i(1, 0)) and not _tm.volume.committed.has(Vector2i(2, 0)), "x = 32 is a +X border")
	assert_true(_tm.volume.committed.has(Vector2i(0, 1)) and not _tm.volume.committed.has(Vector2i(0, 2)), "z = 32 is a +Z border")
	await _settle()
	var worst: float = 0.0
	var n: int = 0
	for i: int in 19:
		var t: float = 31.05 + i * 0.05
		for along: float in [4.0, 9.5, 27.0]:
			for p: Vector2 in [Vector2(t, along), Vector2(along, t)]:
				var got: float = _ray_ground(p.x, p.y)
				worst = maxf(worst, _tm.height_at(p.x, p.y) - got)
				n += 1
	assert_lt(worst, 0.3, "%d rays over the border strips: the ground at most %.2f m under the surface" % [n, worst])


func test_b_a_small_body_dropped_on_the_strip_stays_on_it() -> void:
	var x: float = 31.88
	var z: float = 6.0
	var h: float = _tm.height_at(x, z)
	var b := RigidBody3D.new()
	var cs := CollisionShape3D.new()
	var s := SphereShape3D.new()
	s.radius = 0.06
	cs.shape = s
	b.add_child(cs)
	b.continuous_cd = true
	_hw.add_child(b)
	b.global_position = Vector3(x, h + 0.6, z)
	for i: int in 90:
		await get_tree().physics_frame
	# It may roll down the 21° hill: on the ground where it ended up, not fallen through.
	var at: Vector3 = b.global_position
	var g: float = _tm.height_at(at.x, at.z)
	assert_gt(at.y, g - 0.4, "it lies on the ground (at %s, ground %.2f)" % [at, g])
	b.free()


func test_c_a_dig_into_the_strip_opens_it() -> void:
	var x: float = 31.5
	var z: float = 4.0
	var h: float = _tm.height_at(x, z)
	var c := Vector3(x, h - 0.6, z)
	for i: int in 4:
		_tm.volume.edit_sphere(c, 1.1, 1.0)
	_tm._rebuild_strip_collision(AABB(c - Vector3.ONE * 1.1, Vector3.ONE * 2.2))
	Hill.drain(_tm)
	_tm.volume.flush()
	assert_true(_tm.volume.is_ground_hole(x, z, h), "the dug strip cell is a hole now")
	await _settle()
	assert_lt(_ray_ground(x, z), h - 0.8, "the ray goes into the pit: no lid of old surface over it")
