extends GutTest
## Crowd separation (TD-011): bodies lean off each other without speeding up or turning back.


func after_each() -> void:
	Crowd.reset()


func test_a_lone_body_keeps_its_way() -> void:
	var want := Vector3(0, 0, -3)
	assert_eq(Crowd.steer(want, Vector3.ZERO, 0.3, 1, []), want)
	assert_eq(Crowd.steer(want, Vector3.ZERO, 0.3, 1, [[1, Vector3.ZERO, 0.3]]), want, "it ignores itself")
	assert_eq(Crowd.steer(want, Vector3.ZERO, 0.3, 1, [[2, Vector3(3, 0, 0), 0.3]]), want, "far ones don't count")


func test_a_close_body_pushes_it_aside_never_faster() -> void:
	var want := Vector3(0, -1, -3)
	var out: Vector3 = Crowd.steer(want, Vector3.ZERO, 0.3, 1, [[2, Vector3(0.4, 0, 0), 0.3]])
	assert_lt(out.x, -0.3, "leans away from the neighbour on its right")
	assert_lt(out.z, 0.0, "still heading on")
	assert_true(Vector2(out.x, out.z).length() <= 3.0 + 0.001, "never faster than it wanted")
	assert_eq(out.y, -1.0, "the fall is left alone")


func test_one_straight_ahead_is_passed_not_stopped_at() -> void:
	var want := Vector3(0, 0, -3)
	var out: Vector3 = Crowd.steer(want, Vector3.ZERO, 0.3, 1, [[2, Vector3(0.05, 0, -0.5), 0.3]])
	assert_lt(out.z, -1.0, "keeps going forward")
	assert_ne(out.x, 0.0, "slides to one side")


func test_two_on_one_spot_split_apart() -> void:
	var want := Vector3(0, 0, -3)
	var a: Vector3 = Crowd.steer(want, Vector3.ZERO, 0.3, 2, [[3, Vector3.ZERO, 0.3]])
	var b: Vector3 = Crowd.steer(want, Vector3.ZERO, 0.3, 3, [[2, Vector3.ZERO, 0.3]])
	assert_lt(a.x * b.x, 0.0, "they go opposite ways")


func test_the_grid_shows_last_frames_neighbours() -> void:
	Crowd.enter(5, Vector3(1, 0, 1), 0.3)
	assert_eq(Crowd.near(Vector3(1, 0, 1)).size(), 0, "this frame's entries are not read yet")
	await get_tree().physics_frame
	Crowd.enter(6, Vector3(10, 0, 10), 0.3)
	var n: Array = Crowd.near(Vector3(2.5, 0, 1))
	assert_eq(n.size(), 1, "the neighbour cell sees it a frame later")
	assert_eq(int(n[0][0]), 5)
	assert_eq(Crowd.near(Vector3(9, 0, 9)).size(), 0, "far cells don't")
