extends GutTest


func test_sector_mapping() -> void:
	var base := Vector3.ZERO
	assert_eq(HordeMemory.sector_of(base, Vector3(0, 0, -10)), 0, "north is -Z")
	assert_eq(HordeMemory.sector_of(base, Vector3(10, 0, 0)), 2, "east")
	assert_eq(HordeMemory.sector_of(base, Vector3(0, 0, 10)), 4, "south")
	assert_eq(HordeMemory.sector_of(base, Vector3(-10, 0, 0)), 6, "west")
	assert_eq(HordeMemory.sector_of(base, Vector3(7, 0, -7)), 1, "north-east")
	for s: int in 8:
		assert_eq(HordeMemory.sector_of(base, HordeMemory.sector_dir(s) * 20.0), s)


func _report(killed_north: int) -> Dictionary:
	var spawned: Array = [10, 10, 10, 10, 10, 10, 10, 10]
	var killed: Array = [killed_north, 2, 2, 2, 2, 2, 2, 2]
	var breaches: Array = [0, 3, 3, 3, 3, 3, 3, 3]
	return {"day": 7, "spawned": spawned, "killed": killed, "breaches": breaches, "causes": {"spikes": 12, "melee": 3}, "clear_time": 0.3}


func test_plan_is_deterministic() -> void:
	var m := HordeMemory.new()
	m.record_night(_report(9))
	var r1 := RandomNumberGenerator.new()
	r1.seed = 5
	var r2 := RandomNumberGenerator.new()
	r2.seed = 5
	assert_eq(m.plan(10, r1), m.plan(10, r2))


func test_memory_avoids_killing_fields_and_sieges_strong_walls() -> void:
	var m := HordeMemory.new()
	m.record_night(_report(10))
	m.record_night(_report(10))
	assert_gt(m.lethality[0], 0.6)
	var counts: Array[int] = [0, 0, 0, 0, 0, 0, 0, 0]
	for seed: int in 40:
		var rng := RandomNumberGenerator.new()
		rng.seed = seed
		var plan: Dictionary = m.plan(10, rng)
		assert_true((plan["avoid_sectors"] as Array).has(0))
		assert_eq(plan["focus_sector"], 0, "north held (no breaches) -> siege group goes there")
		for w: Dictionary in plan["waves"]:
			if w["role"] != "siege":
				counts[int(w["sector"])] += 1
	var north: int = counts[0]
	var avg_other: float = 0.0
	for s: int in range(1, 8):
		avg_other += counts[s]
	avg_other /= 7.0
	assert_lt(float(north), avg_other, "assault waves avoid the lethal north sector")


func test_fast_clears_escalate_and_tactics_explain() -> void:
	var m := HordeMemory.new()
	m.record_night(_report(9))
	var rng := RandomNumberGenerator.new()
	var plan: Dictionary = m.plan(10, rng)
	var text: String = " ".join(plan["tactics"])
	assert_string_contains(text, "faster")
	assert_string_contains(text, "stakes")


func test_horde_grows_each_night() -> void:
	var m := HordeMemory.new()
	var rng := RandomNumberGenerator.new()
	var t0: int = m.plan(5, rng)["total"]
	m.record_night(_report(3))
	var t1: int = m.plan(5, rng)["total"]
	assert_gt(t1, t0)


func test_round_trip() -> void:
	var m := HordeMemory.new()
	m.record_night(_report(6))
	var n := HordeMemory.new()
	n.from_dict(JSON.parse_string(JSON.stringify(m.to_dict())))
	assert_eq(JSON.stringify(JSON.parse_string(JSON.stringify(n.to_dict())), "", true), JSON.stringify(JSON.parse_string(JSON.stringify(m.to_dict())), "", true))


func test_the_first_wave_is_front_loaded() -> void:
	var m := HordeMemory.new()
	var share: float = float((Content.config(&"horde").get("planner", {}) as Dictionary).get("first_wave_share", 0.25))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var plan: Dictionary = m.plan(5, rng)
	var sizes: Array[int] = []
	for w: Dictionary in plan["waves"]:
		var n: int = 0
		for k: String in w["units"]:
			n += int(w["units"][k])
		sizes.append(n)
	var total: int = 0
	for n: int in sizes:
		total += n
	assert_eq(total, int(plan["total"]), "every planned Hollowed is in a wave")
	assert_almost_eq(float(sizes[0]), total * share, 1.0, "the first wave carries its share")
	for i: int in range(1, sizes.size()):
		assert_gt(sizes[0], sizes[i], "the first wave is the biggest")
