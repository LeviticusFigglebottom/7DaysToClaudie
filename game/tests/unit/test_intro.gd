extends GutTest
## The new-game intro (ADR-0064): its script is valid, placeholders fill, the load gate.


func test_shipped_script_is_valid() -> void:
	var errors: PackedStringArray = []
	var d: Dictionary = IntroPlayer.load_script(IntroPlayer.SCRIPT_PATH, errors)
	assert_eq(errors, PackedStringArray(), "data/intro/intro.json")
	assert_gt((d.get("cards", []) as Array).size(), 3)


func test_validate_names_problems() -> void:
	var bad: Dictionary = {"cards": [{"kind": "slideshow", "lines": ["x"]}, {"kind": "radio", "lines": ["no speaker"]},
		{"kind": "caption", "lines": [], "hold": 40.0, "colour": "red"}], "speed": 3}
	var errs: PackedStringArray = IntroPlayer.validate(bad)
	var text: String = "\\n".join(errs)
	assert_string_contains(text, "unknown key 'speed'")
	assert_string_contains(text, "kind 'slideshow'")
	assert_string_contains(text, "SPEAKER|text")
	assert_string_contains(text, "no lines")
	assert_string_contains(text, "out of 1..15")
	assert_string_contains(text, "unknown key 'colour'")


func test_fill_and_hum_line() -> void:
	assert_eq(IntroPlayer.fill("DAY {day} · {time}", {"day": 1, "time": "07:30"}), "DAY 1 · 07:30")
	assert_eq(IntroPlayer.hum_line(true, 6), "Six days until the ground hums.")
	assert_eq(IntroPlayer.hum_line(true, 1), "One day until the ground hums.")
	assert_eq(IntroPlayer.hum_line(true, 0), "The ground hums tonight.")
	assert_string_contains(IntroPlayer.hum_line(false, 3), "nothing")


func test_vars_follow_the_session() -> void:
	var s: GameSession = GameSession.create_new({"game_mode": "survival", "seed": 4471})
	var v: Dictionary = IntroPlayer.vars_for(s)
	assert_eq(int(v["day"]), s.clock.day())
	assert_eq(str(v["hum_in"]), IntroPlayer.hum_line(s.clock.hordes_enabled(), s.clock.next_horde_day(s.clock.day()) - s.clock.day()))


func test_calm_only_while_a_card_holds() -> void:
	var intro := IntroPlayer.new()
	add_child_autofree(intro)
	assert_true(intro.is_calm(), "not playing: the load may run")
	intro.play()
	assert_true(intro.is_playing())
	assert_false(intro.is_calm(), "fading in")
	intro.show_card(3)
	assert_true(intro.is_calm(), "a fully typed card holding")
	var done: Array = [false]
	intro.finished.connect(func() -> void: done[0] = true)
	intro.skip_intro()
	assert_true(done[0])
	assert_false(intro.is_playing())
	assert_true(intro.is_calm())


func test_world_card_targets_the_lift3_wreck() -> void:
	var d: Dictionary = IntroPlayer.load_script()
	var world: Array = (d["cards"] as Array).filter(func(c: Dictionary) -> bool: return str(c.get("kind", "")) == "world")
	assert_eq(world.size(), 1)
	assert_eq(str(world[0]["poi"]), "lift3_crash_site")
	assert_null(IntroPlayer.shot_target(world[0]), "no world up: the card plays as a caption on black")
