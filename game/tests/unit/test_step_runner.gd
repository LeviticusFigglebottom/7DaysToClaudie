extends GutTest
## StepRunner (ADR-0036, ADR-0038): budgeted main-thread steps in priority order, waiting steps
## that keep their place, steps queued after the running one, cancellation by name.

var log: Array = []


func _step(name: String) -> Array:
	return [name.capitalize(), func() -> void: log.append(name), name]


func before_each() -> void:
	log.clear()


func test_steps_run_in_priority_then_insertion_order() -> void:
	var r := StepRunner.new()
	r.budget_ms = 1000.0
	r.add(_step("c"), 5.0)
	r.add(_step("a"), 1.0)
	r.add(_step("b"), 1.0)
	r.add(_step("d"), 5.0)
	assert_eq(r.current_label(), "A")
	r.run_frame()
	assert_eq(log, ["a", "b", "c", "d"])
	assert_true(r.is_idle())
	assert_eq(r.progress(), 1.0)


func test_a_waiting_step_keeps_its_place_and_ends_the_frame() -> void:
	var r := StepRunner.new()
	r.budget_ms = 1000.0
	var ready: Array = [false]
	r.add(_step("first"))
	r.add(["Wait", func() -> bool:
		log.append("wait")
		return ready[0], "wait"])
	r.add(_step("after"))
	r.run_frame()
	assert_eq(log, ["first", "wait"], "the frame stops at a waiting step")
	r.run_frame()
	assert_eq(log, ["first", "wait", "wait"], "and asks it again next frame")
	ready[0] = true
	r.run_frame()
	assert_eq(log, ["first", "wait", "wait", "wait", "after"])


func test_a_step_can_queue_more_right_after_itself() -> void:
	var r := StepRunner.new()
	r.budget_ms = 1000.0
	r.add(["Parent", func() -> void:
		log.append("parent")
		r.insert_next([_step("child1"), _step("child2")]), "parent"])
	r.add(_step("later"))
	r.run_frame()
	assert_eq(log, ["parent", "child1", "child2", "later"])
	# Order still holds for steps added afterwards.
	r.add(_step("x"))
	r.insert_next([_step("y")])
	r.add(_step("z"))
	r.run_frame()
	assert_eq(log.slice(4), ["y", "x", "z"])


func test_the_budget_splits_work_across_frames() -> void:
	var r := StepRunner.new()
	r.budget_ms = 5.0
	for i: int in 6:
		r.add(["Slow", func() -> void:
			OS.delay_msec(3)
			log.append(i), "slow %d" % i])
	var frames: int = 0
	while not r.is_idle():
		assert_gt(r.run_frame(), 0, "every frame makes progress")
		frames += 1
	assert_eq(log.size(), 6)
	assert_between(frames, 2, 6, "a 5 ms budget runs two 3 ms steps a frame")


func test_cancel_drops_queued_steps_by_name() -> void:
	var r := StepRunner.new()
	r.add(_step("region a mesh"))
	r.add(_step("region b mesh"))
	r.add(_step("region a far"))
	assert_eq(r.cancel("region a"), 2)
	r.budget_ms = 1000.0
	r.run_frame()
	assert_eq(log, ["region b mesh"])
