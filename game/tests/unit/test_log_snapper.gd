extends GutTest
## Freeform log building: snap candidates, contact relations and overlap rules (LogSnapper), plus
## a wall built purely from snaps feeding the structural graph.


func _log(pos: Vector3, yaw_deg: float = 0.0) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)), pos)


func test_stacked_course_snaps_and_rests_on_the_one_below() -> void:
	var base := _log(Vector3(0, 0.17, 0))
	var free := _log(Vector3(0.3, 0.5, 0.1))
	var snap: Dictionary = LogSnapper.best_snap(free, [base] as Array[Transform3D])
	assert_true(snap["ok"])
	var xf: Transform3D = snap["xform"]
	assert_almost_eq(xf.origin.y, 0.17 + LogSnapper.STACK, 0.001)
	assert_almost_eq(xf.origin.x, 0.0, 0.001)
	assert_eq(LogSnapper.relation(xf, base), &"on")
	assert_eq(LogSnapper.relation(base, xf), &"under")
	assert_false(LogSnapper.overlaps(xf, base))


func test_end_to_end_continues_the_wall_without_overlap() -> void:
	var a := _log(Vector3(0, 0.17, 0))
	var snap: Dictionary = LogSnapper.best_snap(_log(Vector3(3.7, 0.2, 0.05)), [a] as Array[Transform3D])
	assert_true(snap["ok"])
	var b: Transform3D = snap["xform"]
	assert_almost_eq(b.origin.x, LogSnapper.LENGTH, 0.001)
	assert_eq(LogSnapper.relation(b, a), &"side")
	assert_false(LogSnapper.overlaps(a, b))


func test_rotating_the_held_log_selects_the_corner_notch() -> void:
	var a := _log(Vector3(0, 0.17, 0))
	# Held log turned 90 degrees, aimed near the wall's end.
	var free := _log(Vector3(1.9, 0.35, 1.7), 90.0)
	var snap: Dictionary = LogSnapper.best_snap(free, [a] as Array[Transform3D])
	assert_true(snap["ok"])
	var c: Transform3D = snap["xform"]
	assert_almost_eq(absf(c.basis.x.normalized().dot(Vector3.RIGHT)), 0.0, 0.01, "perpendicular")
	assert_almost_eq(c.origin.y, 0.17 + LogSnapper.CORNER_RISE, 0.001)
	assert_eq(LogSnapper.relation(c, a), &"on")
	assert_false(LogSnapper.overlaps(c, a))


func test_crossing_at_the_same_height_is_blocked() -> void:
	var a := _log(Vector3(0, 0.17, 0))
	var b := _log(Vector3(0, 0.17, 0), 90.0)
	assert_true(LogSnapper.overlaps(a, b))


func test_far_aim_does_not_snap() -> void:
	var a := _log(Vector3(0, 0.17, 0))
	var snap: Dictionary = LogSnapper.best_snap(_log(Vector3(0, 3.0, 6.0)), [a] as Array[Transform3D])
	assert_false(snap["ok"])


func test_crossbeam_rests_on_a_post() -> void:
	var post := Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(0, 2.0, 0))
	assert_true(LogSnapper.is_vertical(post.basis))
	var snap: Dictionary = LogSnapper.best_snap(_log(Vector3(0.2, 4.3, 0)), [post] as Array[Transform3D])
	assert_true(snap["ok"])
	var beam: Transform3D = snap["xform"]
	assert_false(LogSnapper.is_vertical(beam.basis))
	assert_eq(LogSnapper.relation(beam, post), &"on")


func test_snapped_wall_is_stable_and_collapses_when_cut_at_the_base() -> void:
	# Six courses built only from snaps; the bottom course is grounded.
	var xfs: Array[Transform3D] = [_log(Vector3(0, 0.17, 0))]
	for i: int in 5:
		var snap: Dictionary = LogSnapper.best_snap(_log(xfs.back().origin + Vector3(0.1, 0.3, 0)), [xfs.back()] as Array[Transform3D])
		assert_true(snap["ok"])
		xfs.append(snap["xform"])
	var g := StructureGraph.new()
	for i: int in xfs.size():
		g.add_piece(StringName("w%d" % i), &"log_piece", 4.0, 0.035, i == 0)
	for i: int in xfs.size():
		for j: int in xfs.size():
			if i != j and LogSnapper.relation(xfs[i], xfs[j]) == &"on":
				g.link(StringName("w%d" % i), StringName("w%d" % j), StructureGraph.Link.ON)
	assert_eq(g.recompute(), [] as Array[StringName])
	assert_almost_eq(g.stability(&"w5"), 1.0 - 5 * 0.035, 0.0001)
	var collapsed: Array[StringName] = g.remove_and_cascade(&"w0")
	assert_eq(collapsed.size(), 5, "everything above the cut falls")
