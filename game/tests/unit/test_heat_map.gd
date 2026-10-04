extends GutTest


func test_heat_accumulates_triggers_and_decays() -> void:
	var h := HeatMap.new()
	h.configure(Content.config(&"heat"))
	var pos := Vector3(100, 0, 100)
	h.add(pos, 40.0)
	var trig: Array[Dictionary] = h.tick(1.0)
	assert_eq(trig.size(), 1)
	assert_eq(trig[0]["kind"], "scout")
	assert_eq(h.tick(1.0).size(), 0, "cooldown prevents spam")
	h.tick(60.0 * 10.0)
	assert_eq(h.heat_at(pos), 0.0, "decays away")


func test_strongest_threshold_wins() -> void:
	var h := HeatMap.new()
	h.configure(Content.config(&"heat"))
	h.add(Vector3.ZERO, 200.0)
	assert_eq(h.tick(1.0)[0]["kind"], "pack")
