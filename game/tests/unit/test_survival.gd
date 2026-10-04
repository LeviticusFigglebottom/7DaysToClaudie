extends GutTest


func _env(extra: Dictionary = {}) -> Dictionary:
	var e: Dictionary = {"ambient_c": 18.0, "wind": 0.1, "raining": false, "sheltered": false, "fire_warmth": 0.0, "sleeping": false, "exertion": 0.0}
	e.merge(extra, true)
	return e


func test_needs_decay_over_game_time() -> void:
	var s := SurvivalStats.new()
	var f0: float = s.fullness
	var h0: float = s.hydration
	s.tick_game(120.0, _env())
	assert_almost_eq(s.fullness, f0 - 8.0, 0.01, "4/h for 2h")
	assert_almost_eq(s.hydration, h0 - 12.0, 0.01, "6/h for 2h")


func test_starvation_damages() -> void:
	var s := SurvivalStats.new()
	s.fullness = 0.0
	var hp: float = s.health
	s.tick_game(60.0, _env())
	assert_lt(s.health, hp)
	assert_true(s.has_status(&"starving"))


func test_consume_applies_effects_and_clamps() -> void:
	var s := SurvivalStats.new()
	s.fullness = 90.0
	s.consume(Content.item(&"canned_stew"))
	assert_eq(s.fullness, 100.0)
	s.hydration = 50.0
	s.consume(Content.item(&"water_bottle_clean"))
	assert_eq(s.hydration, 85.0)


func test_bandage_stops_bleeding() -> void:
	var s := SurvivalStats.new()
	s.add_wound(0.6)
	assert_true(s.has_status(&"bleeding"))
	s.consume(Content.item(&"cloth_bandage"))
	assert_eq(s.bleeding, 0.0)
	assert_false(s.has_status(&"bleeding"))


func test_cold_lowers_body_temperature_and_fire_helps() -> void:
	var cold := SurvivalStats.new()
	cold.tick_game(240.0, _env({"ambient_c": -10.0, "wind": 0.8}))
	assert_lt(cold.body_temp, 36.0)
	var warm := SurvivalStats.new()
	warm.tick_game(240.0, _env({"ambient_c": -10.0, "wind": 0.8, "fire_warmth": 20.0, "sheltered": true}))
	assert_gt(warm.body_temp, cold.body_temp)


func test_rain_soaks_unless_sheltered() -> void:
	var s := SurvivalStats.new()
	s.tick_game(60.0, _env({"raining": true}))
	assert_gt(s.wetness, 0.5)
	var dry := SurvivalStats.new()
	dry.tick_game(60.0, _env({"raining": true, "sheltered": true}))
	assert_eq(dry.wetness, 0.0)


func test_stamina_spend_and_regen() -> void:
	var s := SurvivalStats.new()
	assert_true(s.spend_stamina(40.0))
	assert_almost_eq(s.stamina, 60.0, 0.01)
	s.tick_realtime(0.5)
	assert_almost_eq(s.stamina, 60.0, 0.01, "regen delayed after spending")
	s.tick_realtime(1.0)
	assert_gt(s.stamina, 60.0)


func test_hunger_shrinks_stamina_cap() -> void:
	var s := SurvivalStats.new()
	var full_cap: float = s.stamina_cap()
	s.fullness = 0.0
	s.rest = 0.0
	assert_lt(s.stamina_cap(), full_cap * 0.5)


func test_death_signal_once() -> void:
	var s := SurvivalStats.new()
	watch_signals(s)
	s.apply_damage(500.0, &"test")
	s.apply_damage(5.0, &"test")
	assert_signal_emit_count(s, "died", 1)
	assert_false(s.alive)


func test_sleep_restores_rest_and_slows_needs() -> void:
	var s := SurvivalStats.new()
	s.rest = 20.0
	var f0: float = s.fullness
	s.tick_game(480.0, _env({"sleeping": true}))
	assert_gt(s.rest, 90.0)
	assert_gt(s.fullness, f0 - 32.0 * 0.6, "needs decay slower while sleeping")


func test_round_trip() -> void:
	var s := SurvivalStats.new()
	s.add_wound(0.3, 12.0)
	s.tick_game(30.0, _env())
	var t := SurvivalStats.new()
	t.from_dict(JSON.parse_string(JSON.stringify(s.to_dict())))
	assert_eq(t.to_dict(), s.to_dict())
