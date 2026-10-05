extends GutTest
## Wildlife rules (ADR-0027) without a scene: deterministic spawn plans by biome and time of day,
## when a deer looks up or bolts (sight, stance, scent downwind, the Hollowed, noise), when a flock
## flushes, the Hum night's silence, and what a carcass yields to which tool.


func _defs() -> Array:
	return Content.all(&"wildlife")


func _meadow(_p: Vector2) -> Dictionary:
	return {"biome": "meadow", "edge": false, "ok": true}


func _town(_p: Vector2) -> Dictionary:
	return {"biome": "town", "edge": false, "ok": true}


func _water(_p: Vector2) -> Dictionary:
	return {"biome": "meadow", "edge": false, "ok": false}


func _deer() -> WildlifeDef:
	return Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef


func test_wildlife_defs_load() -> void:
	assert_eq(_defs().size(), 5, "deer, hare, two songbird flocks and crows")
	for d: WildlifeDef in _defs():
		assert_false(d.biomes.is_empty(), "%s lives somewhere" % d.id)
	assert_eq(_deer().pick_model(0.0), "animals/deer_buck", "models are picked by weight in id order")
	assert_eq(_deer().pick_model(0.9), "animals/deer_doe")


func test_spawn_plans_are_deterministic() -> void:
	var a: Array[Dictionary] = WildlifeSpawner.plans_near(1234, Vector2(100, -40), 400.0, 3, "dawn", _defs(), _meadow)
	var b: Array[Dictionary] = WildlifeSpawner.plans_near(1234, Vector2(100, -40), 400.0, 3, "dawn", _defs(), _meadow)
	assert_gt(a.size(), 0, "a dawn meadow has life in it")
	assert_eq(a.size(), b.size())
	for i: int in a.size():
		assert_eq(a[i]["id"], b[i]["id"])
		assert_eq(a[i]["pos"], b[i]["pos"])
		assert_eq(a[i]["count"], b[i]["count"])
	var other: Array[Dictionary] = WildlifeSpawner.plans_near(1235, Vector2(100, -40), 400.0, 3, "dawn", _defs(), _meadow)
	var same: bool = other.size() == a.size()
	if same:
		for i: int in a.size():
			same = same and other[i]["pos"] == a[i]["pos"]
	assert_false(same, "another world seed puts the animals elsewhere")


func test_spawn_follows_biome_time_and_ground() -> void:
	var town: Array[Dictionary] = WildlifeSpawner.plans_near(7, Vector2.ZERO, 600.0, 2, "day", _defs(), _town)
	for p: Dictionary in town:
		assert_ne(p["def"], &"snowshoe_hare", "no hares in town")
	var night: Array[Dictionary] = WildlifeSpawner.plans_near(7, Vector2.ZERO, 600.0, 2, "night", _defs(), _meadow)
	for p: Dictionary in night:
		var d := Content.get_def(&"wildlife", p["def"]) as WildlifeDef
		assert_ne(d.wkind, "flock", "the birds are roosting at night")
	var wet: Array[Dictionary] = WildlifeSpawner.plans_near(7, Vector2.ZERO, 600.0, 2, "dawn", _defs(), _water)
	assert_eq(wet.size(), 0, "nothing spawns where the ground is no good")
	# deer favour dawn over midday
	var dawn_deer: int = 0
	var day_deer: int = 0
	for s: int in 40:
		for p: Dictionary in WildlifeSpawner.plans_near(s, Vector2.ZERO, 500.0, 1, "dawn", _defs(), _meadow):
			dawn_deer += int(p["def"] == &"white_tailed_deer")
		for p: Dictionary in WildlifeSpawner.plans_near(s, Vector2.ZERO, 500.0, 1, "day", _defs(), _meadow):
			day_deer += int(p["def"] == &"white_tailed_deer")
	assert_gt(dawn_deer, day_deer * 2, "deer come out at dawn (%d) far more than at midday (%d)" % [dawn_deer, day_deer])


func test_period_of_the_day() -> void:
	assert_eq(WildlifeSpawner.period_of(6.0, 6.25, 19.25), "dawn")
	assert_eq(WildlifeSpawner.period_of(12.0, 6.25, 19.25), "day")
	assert_eq(WildlifeSpawner.period_of(20.0, 6.25, 19.25), "dusk")
	assert_eq(WildlifeSpawner.period_of(1.0, 6.25, 19.25), "night")


func test_a_deer_sees_hears_and_smells_you() -> void:
	var d: WildlifeDef = _deer()
	var deer := Vector3.ZERO
	var calm := Vector2(1, 0)
	assert_eq(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, 20), 1.0, false, calm, 0.0), WildlifeBrain.Threat.FLEE, "too close: it bolts")
	assert_eq(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, 50), 1.0, false, calm, 0.0), WildlifeBrain.Threat.ALERT, "it looks up at 50 m")
	assert_eq(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, 150), 1.0, false, calm, 0.0), WildlifeBrain.Threat.NONE)
	# crouched in shadow, a hunter gets inside the flight distance
	assert_ne(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, 25), 0.25, true, calm, 0.0), WildlifeBrain.Threat.FLEE, "a crouched stalker in shadow")
	# the wind: blowing from the hunter (at -Z) towards the deer, it smells him at 70 m; the other way, nothing
	var towards := Vector2(0, 1)
	assert_eq(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, -70), 0.25, true, towards, 0.6), WildlifeBrain.Threat.FLEE, "downwind it smells you")
	assert_eq(WildlifeBrain.person_threat(d, deer, Vector3(0, 0, -70), 0.25, true, -towards, 0.6), WildlifeBrain.Threat.NONE, "upwind you're a ghost")


func test_a_deer_runs_from_the_hollowed_and_gunshots() -> void:
	var d: WildlifeDef = _deer()
	assert_eq(WildlifeBrain.hollowed_threat(d, Vector3.ZERO, Vector3(30, 0, 0)), WildlifeBrain.Threat.FLEE)
	assert_eq(WildlifeBrain.hollowed_threat(d, Vector3.ZERO, Vector3(200, 0, 0)), WildlifeBrain.Threat.NONE)
	assert_eq(WildlifeBrain.sound_threat(d, 120.0, 80.0), WildlifeBrain.Threat.FLEE, "a gunshot sends the herd off")
	assert_eq(WildlifeBrain.sound_threat(d, 6.0, 7.0), WildlifeBrain.Threat.ALERT, "a snapped twig makes it look")
	assert_eq(WildlifeBrain.sound_threat(d, 6.0, 30.0), WildlifeBrain.Threat.NONE)


func test_flee_direction_runs_away() -> void:
	var dir: Vector3 = WildlifeBrain.flee_direction(Vector3.ZERO, [Vector3(10, 0, 0)] as Array[Vector3])
	assert_lt(dir.x, -0.9, "away from the threat")
	var two: Vector3 = WildlifeBrain.flee_direction(Vector3.ZERO, [Vector3(5, 0, 0), Vector3(0, 0, 40)] as Array[Vector3])
	assert_lt(two.x, -0.5, "the nearer threat counts more")


func test_flock_flushes_for_people_hollowed_and_noise() -> void:
	var crow := Content.get_def(&"wildlife", &"crow") as WildlifeDef
	var at := Vector3.ZERO
	var none: Array[Vector3] = []
	var near := {"pos": Vector3(crow.flush_radius * 0.8, 0, 0), "crouched": false, "speed": 1.5}
	assert_eq(WildlifeBrain.flush_cause(crow, at, [near], none, {}), "person")
	var sneaking := {"pos": Vector3(crow.flush_radius * 0.6, 0, 0), "crouched": true, "speed": 1.0}
	assert_eq(WildlifeBrain.flush_cause(crow, at, [sneaking], none, {}), "", "a crouched, slow stalker slips past")
	assert_eq(WildlifeBrain.flush_cause(crow, at, [], [Vector3(5, 0, 0)] as Array[Vector3], {}), "hollowed")
	assert_eq(WildlifeBrain.flush_cause(crow, at, [], none, {"pos": Vector3(30, 0, 0), "loudness": 120.0}), "noise", "a gunshot")
	assert_eq(WildlifeBrain.flush_cause(crow, at, [], none, {"pos": Vector3(30, 0, 0), "loudness": 8.0}), "")


func test_the_valley_falls_silent_before_the_hum() -> void:
	var c := WorldClock.new()
	c.configure({"day_length_minutes": 30}, {"first_day": 3, "interval_days": 7, "start_hour": 22.0, "end_hour": 4.0})
	c.set_time(2, 12.0)
	assert_false(WildlifeManager.silence_due(c), "the day before the Hum is ordinary")
	c.set_time(3, 12.0)
	assert_false(WildlifeManager.silence_due(c), "Hum day, noon: still birdsong")
	c.set_time(3, 20.5)
	assert_true(WildlifeManager.silence_due(c), "the evening of the Hum: silence")
	c.set_time(4, 2.0)
	assert_true(WildlifeManager.silence_due(c), "during the Hum")
	c.set_time(4, 7.0)
	assert_false(WildlifeManager.silence_due(c), "morning after: they come back")


func test_butchering_yields_are_deterministic_and_tool_dependent() -> void:
	var d: WildlifeDef = _deer()
	var a: Dictionary = WildlifeManager.butcher_yields(d, &"w:deer:1", 99, &"kitchen_knife")
	var b: Dictionary = WildlifeManager.butcher_yields(d, &"w:deer:1", 99, &"kitchen_knife")
	assert_eq(a, b, "the same carcass gives the same cuts")
	for k: String in a:
		var r: Array = (d.carcass["yields"] as Dictionary)[k]
		assert_between(int(a[k]), int(r[0]), int(r[1]), "%s in its range" % k)
	assert_true(a.has("raw_venison") and a.has("deer_hide"), "meat and the hide")
	var axe: Dictionary = WildlifeManager.butcher_yields(d, &"w:deer:1", 99, &"stone_axe")
	assert_eq(int(axe.get("sinew", 0)), maxi(0, int(a.get("sinew", 0)) - 1), "an axe spoils a strand of sinew")
	assert_eq(int(axe.get("raw_venison", 0)), int(a.get("raw_venison", 0)), "but takes the same meat")
