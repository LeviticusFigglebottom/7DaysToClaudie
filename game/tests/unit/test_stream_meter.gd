extends GutTest
## StreamMeter (ADR-0038 §8): step costs by kind, the longest frame and what ran in it, late
## seconds, the 60 s window and over_budget.


func _meter() -> StreamMeter:
	var m := StreamMeter.new()
	m.log_windows = false
	return m


func test_kind_drops_the_id() -> void:
	assert_eq(StreamMeter.kind_of("poi plan merrow_house"), "poi plan")
	assert_eq(StreamMeter.kind_of("poi merrow_house"), "poi")
	assert_eq(StreamMeter.kind_of("poi region 3_4_pines"), "poi region")
	assert_eq(StreamMeter.kind_of("road markings 3_4_pines"), "road markings")
	assert_eq(StreamMeter.kind_of("attach 3_4_pines"), "attach")
	assert_eq(StreamMeter.kind_of("detach"), "detach")


func test_steps_aggregate_by_kind() -> void:
	var m := _meter()
	m.step("poi a", 2000)
	m.step("poi b", 12000)
	m.step("poi plan a", 500, false)
	m.step("attach r1", 40000)
	var k: Dictionary = m.report()["kinds"]
	assert_eq(k.size(), 3)
	assert_eq(int(k["poi"]["count"]), 2)
	assert_almost_eq(float(k["poi"]["total_ms"]), 14.0, 0.001)
	assert_almost_eq(float(k["poi"]["max_ms"]), 12.0, 0.001)
	assert_eq(str(k["poi"]["max_name"]), "poi b")
	assert_eq(int(k["poi plan"]["waits"]), 1)
	assert_eq(int(m.report()["steps"]), 4)
	assert_eq(m.worst_kind(), ["attach", 40.0])


func test_longest_frame_names_its_steps_and_late_seconds_add_up() -> void:
	var m := _meter()
	m.frame(0.016, false, 16.0)
	m.step("attach r1", 30000)
	m.step("poi x", 5000)
	m.frame(0.05, true, 55.0)
	m.frame(0.5, true, 20.0)
	var r: Dictionary = m.report()
	assert_eq(int(r["frames"]), 3)
	assert_almost_eq(float(r["longest_ms"]), 55.0, 0.001)
	assert_eq(str(r["longest_at"]), "attach 30 ms + poi 5 ms")
	# A stall counts at most MAX_LATE_STEP.
	assert_almost_eq(float(r["late_s"]), 0.05 + StreamMeter.MAX_LATE_STEP, 0.0001)


func test_window_resets_but_the_session_tally_keeps_going() -> void:
	var m := _meter()
	m.window_s = 1.0
	m.step("poi a", 9000)
	assert_false(m.frame(0.6, false, 10.0))
	assert_true(m.frame(0.6, false, 90.0), "the second frame closes the 1 s window")
	assert_eq(int(m.report()["steps"]), 0, "a new window starts empty")
	assert_eq((m.report()["kinds"] as Dictionary).size(), 0)
	assert_eq(int(m.last_window["steps"]), 1)
	assert_almost_eq(float(m.last_window["longest_ms"]), 90.0, 0.001)
	m.step("attach r", 1000)
	var all: Dictionary = m.report(true)
	assert_eq(int(all["steps"]), 2)
	assert_eq(int(all["frames"]), 2)
	assert_true(m.summary(true).contains("poi 1x"))


func test_over_budget_lists_kinds_worst_first() -> void:
	var m := _meter()
	m.step("poi a", 7000)
	m.step("poi region r", 9000)
	m.step("attach r", 30000)
	m.step("road markings r", 8000)
	assert_eq(m.over_budget(), PackedStringArray(["attach", "poi region"]))
	assert_eq(m.over_budget(5.0), PackedStringArray(["attach", "poi region", "road markings", "poi"]))
	assert_eq(m.over_budget(50.0), PackedStringArray())
	assert_true(m.summary().contains("over 8 ms: attach, poi region"))


func test_step_runner_feeds_the_meter() -> void:
	var m := _meter()
	var r := StepRunner.new()
	r.budget_ms = 1000.0
	r.step_ran.connect(m.step)
	r.add(["", func() -> void: pass, "poi a"])
	r.add(["", func() -> void: pass, "poi b"])
	r.run_frame()
	assert_eq(int(m.report()["kinds"]["poi"]["count"]), 2)
