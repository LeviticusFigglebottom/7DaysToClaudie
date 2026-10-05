extends GutTest
## World settings (GameRules): resolution order, clamping, saves, and the systems that read them.


func test_defaults_match_the_schema_and_survivor_preset() -> void:
	var r: GameRules = GameRules.resolve({}, &"survivor", {})
	for key: String in GameRules.options():
		assert_eq(r.values[key], GameRules.coerce(GameRules.options()[key], GameRules.options()[key]["default"]), key)
	assert_true(r.customised().is_empty())


func test_resolution_order_mode_then_preset_then_player() -> void:
	var r: GameRules = GameRules.resolve({"hum_first_day": 3, "enemy_damage": 1.25}, &"drifter", {"hum_size": 2.0})
	assert_eq(r.integer("hum_first_day"), 3, "mode rule applies")
	assert_almost_eq(r.num("enemy_damage"), 0.5, 0.001, "preset beats the mode")
	assert_almost_eq(r.num("hum_size"), 2.0, 0.001, "player beats the preset")
	assert_eq(r.choice("death_penalty"), "none")


func test_values_are_clamped_and_validated() -> void:
	var r: GameRules = GameRules.resolve({}, &"survivor", {"xp_multiplier": 99.0, "hum_every_days": -4,
		"enemy_speed_day": "teleport", "special_hollowed": "false", "no_such_option": 1})
	assert_almost_eq(r.num("xp_multiplier"), 3.0, 0.001)
	assert_eq(r.integer("hum_every_days"), 0)
	assert_eq(r.choice("enemy_speed_day"), "walk", "unknown enum value falls back to the default")
	assert_false(r.flag("special_hollowed"))
	assert_false(r.values.has("no_such_option"))
	assert_eq(GameRules.resolve({}, &"no_such_preset", {}).preset, &"survivor")


func test_save_round_trip_keeps_values_and_fills_new_options() -> void:
	var r: GameRules = GameRules.resolve({}, &"remanded", {"loot_abundance": 1.75})
	var d: Dictionary = r.to_dict()
	(d["values"] as Dictionary).erase("needs_rate")
	var back: GameRules = GameRules.from_dict(d)
	assert_eq(back.preset, &"remanded")
	assert_almost_eq(back.num("loot_abundance"), 1.75, 0.001)
	assert_almost_eq(back.num("needs_rate"), 1.25, 0.001, "a missing option takes the preset's value")


func test_speed_scale_is_relative_to_each_periods_default() -> void:
	var r: GameRules = GameRules.resolve({}, &"survivor", {})
	assert_almost_eq(r.speed_scale("day"), 1.0, 0.001)
	assert_almost_eq(r.speed_scale("night"), 1.0, 0.001)
	var fast: GameRules = GameRules.resolve({}, &"survivor", {"enemy_speed_day": "run", "enemy_speed_night": "sprint"})
	assert_almost_eq(fast.speed_scale("day"), 1.0 / 0.6, 0.001)
	assert_almost_eq(fast.speed_scale("night"), 1.25, 0.001)
	assert_gt(GameRules.resolve({}, &"survivor", {"sleeper_alertness": "light"}).sleeper_wake_factor(), 1.0)


func _clock(first: int, every: int, variance: int, seed: int = 7) -> WorldClock:
	var c := WorldClock.new()
	c.configure({}, {"first_day": first, "interval_days": every, "variance_days": variance, "seed": seed})
	c.set_time(1, 8.0)
	return c


func test_hum_variance_stays_ordered_and_near_its_base_day() -> void:
	var c: WorldClock = _clock(7, 7, 2)
	var prev: int = 0
	var shifted: int = 0
	for k: int in 20:
		var d: int = c.horde_day_of(k)
		assert_gt(d, prev, "Hums never reorder")
		assert_true(absi(d - (7 + 7 * k)) <= 2, "within the variance")
		assert_true(c.is_horde_day(d))
		assert_eq(c.next_horde_day(d), d)
		if d != 7 + 7 * k:
			shifted += 1
		prev = d
	assert_gt(shifted, 0, "the variance actually moves some Hums")
	assert_true(c.is_horde_day(7), "the first Hum is never shifted")


func test_hum_can_be_disabled() -> void:
	var c: WorldClock = _clock(7, 0, 0)
	assert_false(c.hordes_enabled())
	for d: int in range(1, 60):
		assert_false(c.is_horde_day(d))
	assert_eq(c.next_horde_day(), -1)
	assert_eq(c.hours_until_horde(), INF)


func test_new_session_applies_rules_to_clock_and_gamestage() -> void:
	var s: GameSession = GameSession.create_new({"seed": 99, "game_mode": "slice", "preset": "hollowed",
		"rules": {"day_length_minutes": 90, "gamestage_days_weight": 2.0}})
	assert_eq(s.rules.preset, &"hollowed")
	assert_almost_eq(s.clock.day_length_real_minutes, 90.0, 0.001)
	assert_eq(s.clock.horde_first_day, 3, "slice mode's first Hum")
	assert_eq(s.clock.horde_interval_days, 5, "hollowed preset's interval")
	s.clock.set_time(6, 9.0)
	# (level 1 + 5 days x 2.0) x 1.4 = 15.4
	assert_eq(s.gamestage(), 15)
	var back: GameSession = GameSession.from_dict(s.to_dict())
	assert_eq(back.rules.preset, &"hollowed")
	assert_almost_eq(back.clock.day_length_real_minutes, 90.0, 0.001)


func _items_rolled(abundance: float) -> int:
	var total: int = 0
	for i: int in 200:
		var rng := RandomNumberGenerator.new()
		rng.seed = 1000 + i
		var ctx := LootRoller.Context.new(2, 10, rng)
		ctx.abundance = abundance
		for st: ItemStack in LootRoller.roll(&"kitchen_cabinet", ctx):
			total += st.count
	return total


func test_loot_abundance_scales_what_containers_hold() -> void:
	var low: int = _items_rolled(0.5)
	var normal: int = _items_rolled(1.0)
	var high: int = _items_rolled(2.0)
	assert_lt(low, normal)
	assert_gt(high, normal)
