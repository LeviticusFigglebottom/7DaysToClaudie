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


func test_waking_after_turning_does_not_turn_again() -> void:
	var s := SurvivalStats.new()
	var causes: Array[String] = []
	s.died.connect(func(cause: String) -> void: causes.append(cause))
	s.infection = 99.9
	s.tick_game(60.0, _env())
	assert_eq(causes, ["turned"] as Array[String], "the Bloom turns the player at 100")
	s.revive(50.0)
	s.tick_game(240.0, _env())
	assert_true(s.alive, "waking up is not a second turning")
	assert_eq(causes.size(), 1)
	assert_false(s.has_status(&"infected"), "the infection ended with the turning")


func test_waking_after_another_death_keeps_the_infection() -> void:
	var s := SurvivalStats.new()
	s.infection = 40.0
	s.apply_damage(1000.0, &"fall")
	s.revive(50.0)
	assert_almost_eq(s.infection, 40.0, 0.001, "dying of a fall doesn't cure the Bloom")


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


## First-week audit W7: the cold hurts by how deep the body has gone below hypothermia, so a
## mildly chilled night costs little and a soaking one still does real harm.
func test_cold_damage_grows_with_depth_below_hypothermia() -> void:
	var s := SurvivalStats.new()
	s.body_temp = 35.5
	assert_eq(s.cold_damage_frac(), 0.0, "no harm above the line")
	s.body_temp = 34.8
	assert_almost_eq(s.cold_damage_frac(), 0.25, 0.001, "a little below: a quarter")
	s.body_temp = 34.0
	assert_almost_eq(s.cold_damage_frac(), 0.5, 0.001)
	s.body_temp = 32.0
	assert_eq(s.cold_damage_frac(), 1.0, "two degrees down: all of it")


## A player in starting gear outside a whole rainy autumn night (12 h at the night's low): unfed,
## badly hurt but alive; fed, in danger but keeping most of their health.
func test_a_wet_night_outside_is_dangerous_not_certain_death() -> void:
	var hungry := SurvivalStats.new()
	hungry.fullness = 49.0
	var fed := SurvivalStats.new()
	fed.fullness = 100.0
	fed.hydration = 100.0
	var env: Dictionary = _env({"ambient_c": -2.5, "wind": 0.5, "raining": true})
	for i: int in 12 * 6:
		hungry.tick_game(10.0, env)
		fed.tick_game(10.0, env)
	assert_true(hungry.alive, "a night of rain doesn't kill outright")
	assert_lt(hungry.health, 50.0, "but it hurts")
	assert_gt(fed.health, 60.0, "fed, the body holds")


func test_cold_warnings_speak_before_the_cold_hurts_and_rate_limit() -> void:
	var s := SurvivalStats.new()
	var w := SurvivalWarnings.new().ladder(&"cold")
	var said: Array[String] = []
	var freezing_body: float = 0.0
	for minute: int in range(0, 240, 5):
		s.tick_game(5.0, _env({"ambient_c": -2.5, "wind": 0.5, "raining": true}))
		var line: Dictionary = w.update(s, 5.0)
		if not line.is_empty():
			said.append(str(line["text"]))
			if str(line["text"]).contains("freezing") and freezing_body == 0.0:
				freezing_body = s.body_temp
	assert_gt(said.size(), 1, str(said))
	assert_eq(said[0], "You're cold. Find shelter or a fire.")
	assert_eq(said[1], "You're freezing. Find a fire, now.")
	assert_gt(freezing_body, 35.0, "freezing is said before the body reaches hypothermia")
	assert_lt(said.size(), 5, "rate limited over four hours: %s" % [said])
	# Warm again: quiet, and the next chill is announced afresh.
	s.body_temp = 37.0
	assert_true(w.update(s, 5.0).is_empty())
	s.body_temp = 36.0
	assert_eq(str(w.update(s, 5.0).get("text", "")), "You're cold. Find shelter or a fire.")
	# Asleep: nothing until waking.
	s.body_temp = 35.2
	assert_true(w.update(s, 5.0, true).is_empty(), "quiet while asleep")
	assert_eq(str(w.update(s, 5.0).get("text", "")), "You're freezing. Find a fire, now.", "said on waking")


func _texts(lines: Array[Dictionary]) -> Array[String]:
	var out: Array[String] = []
	for l: Dictionary in lines:
		out.append(str(l["text"]))
	return out


## Minutes from full to each line and to the first damage, for one need left to run out (the
## others kept topped up so only this one can hurt). W18: a player who stopped drinking died of
## thirst with no warning but the bar.
func _need_timeline(stat: String) -> Dictionary:
	var s := SurvivalStats.new()
	s.fullness = 100.0
	s.hydration = 100.0
	var w := SurvivalWarnings.new()
	var t: Dictionary = {}
	for minute: int in range(5, 40 * 60, 5):
		if stat != "hydration":
			s.hydration = 100.0
		if stat != "fullness":
			s.fullness = 100.0
		var hp: float = s.health
		s.tick_game(5.0, _env())
		for l: Dictionary in w.update(s, 5.0):
			if not t.has(str(l["text"])):
				t[str(l["text"])] = minute
		if s.health < hp and not t.has("damage"):
			t["damage"] = minute
			break
	gut.p("%s from full (game minutes): %s" % [stat, t])
	return t


func test_thirst_warns_hours_before_it_hurts() -> void:
	var t: Dictionary = _need_timeline("hydration")
	assert_true(t.has("You're thirsty.") and t.has("You're parched. Drink, now.") and t.has("damage"), str(t))
	assert_lt(int(t["You're thirsty."]), int(t["You're parched. Drink, now."]))
	assert_gt(int(t["damage"]) - int(t["You're thirsty."]), 4 * 60, "the first line with hours to spare")
	assert_gt(int(t["damage"]) - int(t["You're parched. Drink, now."]), 60, "the second before any harm")


func test_hunger_warns_hours_before_it_hurts() -> void:
	var t: Dictionary = _need_timeline("fullness")
	assert_true(t.has("You're hungry.") and t.has("You're starving. Eat something.") and t.has("damage"), str(t))
	assert_lt(int(t["You're hungry."]), int(t["You're starving. Eat something."]))
	assert_gt(int(t["damage"]) - int(t["You're hungry."]), 4 * 60, "the first line with hours to spare")
	assert_gt(int(t["damage"]) - int(t["You're starving. Eat something."]), 60, "the second before any harm")


## W19: waking in a blizzard said "freezing" with no "cold" first. A drop past several levels at
## once says each, in order, and only once.
func test_a_sudden_drop_says_every_step_in_order() -> void:
	var s := SurvivalStats.new()
	var w := SurvivalWarnings.new()
	s.body_temp = 35.2
	s.hydration = 5.0
	s.fullness = 5.0
	assert_eq(_texts(w.update(s, 5.0)), ["You're cold. Find shelter or a fire.", "You're freezing. Find a fire, now.",
		"You're thirsty.", "You're parched. Drink, now.", "You're hungry.", "You're starving. Eat something."] as Array[String])
	assert_true(w.update(s, 5.0).is_empty(), "each said once")


func test_need_warnings_quiet_asleep_and_dead_and_reset_when_recovered() -> void:
	var s := SurvivalStats.new()
	var w := SurvivalWarnings.new()
	# Slept through the drop: nothing while asleep, the whole ladder on waking.
	s.hydration = 10.0
	assert_true(w.update(s, 30.0, true).is_empty(), "quiet while asleep")
	assert_eq(_texts(w.update(s, 5.0)), ["You're thirsty.", "You're parched. Drink, now."] as Array[String], "said on waking, in order")
	# Rate limited: at a steady value the current line again only after the level's repeat_minutes
	# (parched: 150; it was the ladder's 60 before the M7 repeat rule).
	assert_true(w.update(s, 145.0).is_empty())
	assert_eq(_texts(w.update(s, 5.0)), ["You're parched. Drink, now."] as Array[String])
	# A sip that leaves the player thirsty doesn't reset the ladder...
	s.hydration = 40.0
	assert_true(w.update(s, 5.0).is_empty())
	s.hydration = 30.0
	assert_true(w.update(s, 5.0).is_empty(), "not recovered: no fresh 'thirsty' yet")
	# ...a real drink does, and the next thirst is announced afresh.
	s.hydration = 60.0
	assert_true(w.update(s, 5.0).is_empty())
	assert_eq(w.ladder(&"thirst").level, 0)
	s.hydration = 30.0
	assert_eq(_texts(w.update(s, 5.0)), ["You're thirsty."] as Array[String])
	# Dead: nothing, and the ladders start over after the respawn.
	s.fullness = 5.0
	s.apply_damage(1000.0, &"dehydration")
	assert_false(s.alive)
	assert_true(w.update(s, 5.0).is_empty(), "quiet while dead")
	s.revive(50.0)
	assert_eq(_texts(w.update(s, 5.0)), ["You're thirsty.", "You're hungry.", "You're starving. Eat something."] as Array[String])


## Mid-game audit M7: "You're freezing" every 90 minutes all night at a steady body temperature.
## A repeat comes sooner only when the stat has got a worse_by worse since the last line; the
## deepest level otherwise waits its own, longer, repeat_minutes.
func test_a_warning_repeats_when_it_gets_worse_or_after_a_long_while() -> void:
	var cfg: Dictionary = Content.config(&"survival")["warnings"]["cold"]
	var worse: float = float(cfg["worse_by"])
	var deep: float = float((cfg["levels"] as Array)[1]["repeat_minutes"])
	assert_gte(deep, 120.0, "the deepest level waits two hours or more")
	var s := SurvivalStats.new()
	var w := SurvivalWarnings.new()
	s.body_temp = 35.3
	s.hydration = 100.0
	s.fullness = 100.0
	assert_eq(_texts(w.update(s, 5.0)).size(), 2, "cold, then freezing: the first-time ladder as before")
	# A steady night: quiet until the long interval is up.
	var said: int = 0
	for i: int in int(deep / 30.0) - 1:
		said += w.update(s, 30.0).size()
	assert_eq(said, 0, "no hourly 'freezing' while it is no colder")
	assert_eq(_texts(w.update(s, 30.0)), ["You're freezing. Find a fire, now."] as Array[String], "then once again")
	# Colder by less than worse_by: still quiet; by worse_by: said at once.
	s.body_temp = 35.3 - worse * 0.5
	assert_true(w.update(s, 10.0).is_empty(), "a little colder is not news")
	s.body_temp = 35.3 - worse
	assert_eq(_texts(w.update(s, 10.0)), ["You're freezing. Find a fire, now."] as Array[String], "a lot colder is")
	assert_true(w.update(s, 10.0).is_empty(), "and the new value is the mark to beat")
	# Warming a little (still freezing) says nothing and doesn't move the mark.
	s.body_temp = 35.3
	assert_true(w.update(s, 10.0).is_empty())
	s.body_temp = 35.3 - worse - 0.01
	assert_true(w.update(s, 10.0).is_empty(), "back down to about the mark: no news")
