extends GutTest
## fp_measure's read of a bolt key from the camera (TD-294): a hand measured on the knob still read
## as a hand on the scope when the knob sat inside the scope's screen footprint.

const Runner: GDScript = preload("res://src/tools/cli/fp_measure_runner.gd")


func _box_at(pos: Vector3, size: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3.ONE * size
	mi.mesh = box
	add_child_autofree(mi)
	mi.global_position = pos
	return mi


func test_screen_is_tan_units() -> void:
	var s: Vector2 = Runner.to_screen(Vector3(0.5, -0.25, -2.0))
	assert_almost_eq(s.x, 0.25, 1e-6)
	assert_almost_eq(s.y, -0.125, 1e-6)


func test_a_point_behind_the_scope_is_inside_its_footprint() -> void:
	var scope: MeshInstance3D = _box_at(Vector3(0.0, 0.0, -1.0), 0.2)
	# Straight behind the box from the eye: inside the footprint (negative gap).
	assert_lt(Runner.scope_gap(Transform3D.IDENTITY, scope, Vector3(0.0, 0.0, -2.0)), 0.0)


func test_the_gap_is_metres_at_the_points_depth() -> void:
	var scope: MeshInstance3D = _box_at(Vector3(0.0, 0.0, -1.0), 0.2)
	# The box's near face (z -0.9, half-width 0.1) spans x up to 0.1 / 0.9 on screen; a point at
	# x 0.5, depth 1 is 0.5 - 0.111 tan units off it, which is that many metres at depth 1.
	var gap: float = Runner.scope_gap(Transform3D.IDENTITY, scope, Vector3(0.5, 0.0, -1.0))
	assert_almost_eq(gap, 0.5 - 0.1 / 0.9, 1e-3)


func test_no_scope_reads_as_clear() -> void:
	assert_gt(Runner.scope_gap(Transform3D.IDENTITY, null, Vector3(0.0, 0.0, -1.0)), 1.0)
