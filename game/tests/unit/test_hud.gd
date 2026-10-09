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


func test_pickups_show_and_add_up() -> void:
	var ui := GameUI.new()
	add_child_autofree(ui)
	ui.feed_pickup("Plant Fibre", 2)
	ui.feed_pickup("Plant Fibre", 1)
	ui.feed_pickup("Stick", 3)
	assert_eq(ui.pickup_lines(), PackedStringArray(["+3 Plant Fibre", "+3 Stick"]))
	for i: int in 8:
		ui.feed_pickup("Thing %d" % i, 1)
	assert_eq(ui.pickup_lines().size(), 5, "a burst keeps the last few lines")


func test_pad_b_closes_the_companion_card() -> void:
	var ui := GameUI.new()
	add_child_autofree(ui)
	var card := CompanionScreen.new()
	ui.add_child(card)
	# Opened as its director would leave it (open() reads the companion's state).
	card.set(&"_open", true)
	card.visible = true
	assert_true(card.is_open())
	assert_true(ui.close_top_screen(), "B finds the card")
	assert_false(card.is_open())


func test_long_messages_wrap_and_stay_to_be_read() -> void:
	assert_eq(GameUI.message_seconds("Saved."), 4.0)
	var call: String = " ".join(PackedStringArray(range(60).map(func(i: int) -> String: return "word")))
	assert_gt(GameUI.message_seconds(call), 20.0)
	var ui := GameUI.new()
	add_child_autofree(ui)
	ui.message(call, &"level")
	var l: Label = ui.get(&"_messages").get_child(0) as Label
	assert_eq(l.autowrap_mode, TextServer.AUTOWRAP_WORD_SMART)
	assert_lte(l.custom_minimum_size.x, 820.0)


func test_manual_lights_one_tab() -> void:
	var m := FieldManual.new()
	add_child_autofree(m)
	m.open("journal")
	m.close()
	m.open("build")
	assert_eq(m.lit_tabs(), PackedStringArray(["build"]))
	assert_true(m.get(&"_selected") is BlueprintDef, "Blueprints opens on a blueprint, not the last tab's page")


func test_roll_strips_shrink_to_fit_a_small_window() -> void:
	assert_eq(SalvageRoll.strip_scale(600.0, 800.0), 1.0)
	assert_almost_eq(SalvageRoll.strip_scale(800.0, 640.0), 0.8, 0.001)
	assert_eq(SalvageRoll.strip_scale(800.0, 100.0), 0.7, "never smaller than 70%")


func test_journal_line_folds_the_reward() -> void:
	assert_eq(GameUI.journal_line("Make a stone axe", "+40 XP", "Fell a tree", "B"), "Journal: Make a stone axe ✓  +40 XP   Next: Fell a tree  [B]")
	assert_eq(GameUI.journal_line("Sleep in your bed", "", "", "B"), "Journal: Sleep in your bed ✓")


func test_prompt_hangs_centred_under_the_crosshair() -> void:
	var ui := GameUI.new()
	add_child_autofree(ui)
	var l: Label = ui.get(&"_prompt") as Label
	l.text = "[E] Use Campfire · burns 58m · [G] add fuel"
	ui.call(&"_hug", l, 28.0)
	var mid: float = l.get_parent_control().size.x * 0.5
	assert_almost_eq(l.position.x + l.size.x * 0.5, mid, 1.0)
	assert_almost_eq(l.position.y, l.get_parent_control().size.y * 0.5 + 28.0, 1.0)
