extends GutTest
## The death screen's words (the tether's incident log, ADR-0063).


func test_death_text_says_cause_consequence_and_where_you_wake() -> void:
	var t: Array[String] = GameUI.death_text("zombie", "Your pack lies where you fell.", false, 3, 1, false)
	assert_eq(t[0], "TETHER 4471  ·  DAY 3  ·  VITALS FLAT")
	assert_eq(t[1], "The Hollowed got you.")
	assert_string_contains(t[2], "the drop site")
	assert_false(t[2].contains("Deaths logged"), "the first death isn't counted aloud")
	var bed: Array[String] = GameUI.death_text("cold", "You keep everything you carried.", false, 9, 3, true)
	assert_string_contains(bed[2], "at your bed")
	assert_string_contains(bed[2], "Deaths logged: 3.")
	var last: Array[String] = GameUI.death_text("turned", "Your run is over.", true, 12, 1, true)
	assert_false(last[2].contains("wake"), "permadeath promises no waking")
	assert_eq(GameUI.death_text("unknown", "", false, 1, 1, false)[1], "You died.")


func test_skipping_the_intro_opens_the_load_gate_at_once() -> void:
	# The load's heavy steps wait while an intro card moves; a skipper must not pay for that.
	var ui := GameUI.new()
	add_child_autofree(ui)
	var intro := IntroPlayer.new()
	ui.add_child(intro)
	ui.intro = intro
	intro.finished.connect(ui._on_intro_finished)
	intro.play()
	assert_false(ui.load_may_step(), "a card fading in holds the steps")
	intro.skip_intro()
	assert_true(ui.load_may_step(), "skipped: the gate is open the same frame")
	assert_null(ui.intro, "and the intro is let go (it fades out on its own)")
	assert_false(ui.is_intro_playing())


func test_loading_tips_keep_the_finds_hidden() -> void:
	var tips: Array[Array] = FieldManual.loading_tips()
	assert_gt(tips.size(), 5)
	for t: Array in tips:
		assert_false(FieldManual.TIPS_NOT_WHILE_LOADING.has(str(t[0])), "%s gives away a find" % t[0])
		for hidden: String in FieldManual.TIPS_NOT_WHILE_LOADING:
			assert_false(str(t[1]).contains(hidden), "%s names %s" % [t[0], hidden])
	assert_eq(GameUI.tip_seconds("a b c"), 8.0)
	assert_gt(GameUI.tip_seconds(str(FieldManual.TIPS[6][1])), 30.0)


func test_loading_relief_shows_only_what_was_walked() -> void:
	var r := Rect2(0, 0, 1024, 512)
	var ex := ExploredMap.new()
	ex.reveal(Vector3(200, 0, 200), 60.0)
	var img: Image = GameUI.relief_image(null, WorldMap.fog_image(ex, r), r, null)
	assert_eq(img.get_size(), Vector2i(128, 128), "square, the sheet's long side")
	var walked: Color = img.get_pixel(25, 25 + 32)
	var unwalked: Color = img.get_pixel(110, 20 + 32)
	assert_lt(_diff(walked, WorldMap.PAPER), 0.01, "walked ground is clear")
	assert_gt(_diff(unwalked, WorldMap.PAPER), 0.02, "the rest is under fog")
	assert_true(img.get_pixel(2, 2).r < 0.05, "the square's margin is the loading screen's dark")


func _diff(a: Color, b: Color) -> float:
	return absf(a.r - b.r) + absf(a.g - b.g) + absf(a.b - b.b)
