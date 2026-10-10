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
	assert_null(IntroPlayer.shot_target(world[0]), "no world up: nothing to frame (the film is made from a loaded world)")


func test_the_world_card_film_pushes_in_along_its_framing() -> void:
	var path := PackedVector3Array([Vector3(0, 10, 50), Vector3(0, 10, 40), Vector3(0, 1.5, 6)])
	var length: float = 13.0
	var start: Transform3D = IntroPlayer.shot_pose(path, Vector3.ZERO, 0.0, length, null)
	var end: Transform3D = IntroPlayer.shot_pose(path, Vector3.ZERO, length, length, null)
	assert_almost_eq(start.origin.distance_to(path[0]), 0.0, 0.001, "starts over `from`")
	assert_almost_eq(end.origin.distance_to(path[1]), 0.0, 0.001, "ends the push in")
	assert_almost_eq(IntroPlayer.shot_pose(path, Vector3.ZERO, length * 2.0, length, null).origin.distance_to(path[1]), 0.0, 0.001, "then holds")
	var ahead: Vector3 = -start.basis.z
	assert_gt(ahead.dot((path[2] - path[0]).normalized()), 0.99, "looking at `to`")
	assert_gt(IntroPlayer.shot_length({"hold": 7.0}), 7.0 + 2.0 * IntroPlayer.FADE, "long enough for the card's fades and its words")


func test_the_world_card_keeps_its_words_off_the_wreck() -> void:
	# The picture is framed on the wreck at its centre: the words and their shade stay low.
	assert_gt(IntroPlayer.WORLD_TEXT_AT, 0.7)
	assert_gt(IntroPlayer.WORLD_SHADE_TOP, 0.5)
	var g: Gradient = IntroPlayer.world_shade().gradient
	assert_almost_eq(g.sample(0.0).a, 0.0, 0.01, "clear where it starts")
	assert_gt(g.sample(0.7).a, 0.6, "dark behind the words")


func test_the_engines_fail_under_the_last_radio_call() -> void:
	# The bed starts as its line types (two labels a radio line: speaker, words) and the impact
	# card after it cuts it.
	var script: Dictionary = IntroPlayer.load_script()
	var cards: Array = script.get("cards", [])
	var bed_card: int = -1
	for i: int in cards.size():
		if (cards[i] as Dictionary).has("bed"):
			bed_card = i
	assert_gt(bed_card, -1, "a card has a bed")
	assert_eq(str((cards[bed_card] as Dictionary)["kind"]), "radio")
	assert_eq(str((cards[bed_card + 1] as Dictionary)["kind"]), "impact", "the crash cuts it")
	assert_eq(IntroPlayer.bed_label_index({"kind": "radio", "bed": {"sound": "x", "line": 3}}), 6)
	assert_eq(IntroPlayer.bed_label_index({"kind": "caption", "bed": {"sound": "x", "line": 1}}), 1)
	assert_eq(IntroPlayer.bed_label_index({"kind": "radio"}), -1)
	var bad: Dictionary = {"cards": [{"kind": "radio", "lines": ["A|b"], "bed": {"sound": "x", "line": 4}},
		{"kind": "radio", "lines": ["A|b"], "bed": {"line": 0, "when": 2}}]}
	var problems: PackedStringArray = IntroPlayer.validate(bad)
	assert_eq(problems.size(), 3, "a line past the card, no sound, an unknown key: %s" % str(problems))
	assert_eq(IntroPlayer.validate(script).size(), 0, "the shipped script is clean")
