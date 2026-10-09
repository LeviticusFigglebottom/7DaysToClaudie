extends GutTest
## The main menu hides developer entries from players: QA save slots and the slice demo.

const Main := preload("res://src/app/main.gd")


func test_players_never_see_qa_slots() -> void:
	var slots: Array[Dictionary] = [{"slot": "run3"}, {"slot": "smoke"}, {"slot": "tour"}, {"slot": "qa_new_probe"}, {"slot": "run1"}]
	var shown: Array[Dictionary] = Main.menu_slots(slots, false)
	assert_eq(shown.map(func(s: Dictionary) -> String: return str(s["slot"])), ["run3", "run1"])
	assert_eq(Main.menu_slots(slots, true).size(), 5, "a developer sees every slot")


func test_every_runner_slot_is_listed() -> void:
	# A QA runner that saves under a name the menu doesn't know would show up to players.
	for path: String in DirAccess.get_files_at("res://src/tools/cli"):
		if not path.ends_with(".gd"):
			continue
		var src: String = FileAccess.get_file_as_string("res://src/tools/cli".path_join(path))
		var re := RegEx.create_from_string('"slot": *"([a-z_0-9]+)"')
		for m: RegExMatch in re.search_all(src):
			var slot: String = m.get_string(1)
			assert_true(Main.QA_SLOTS.has(slot) or slot.begins_with("qa_"), "%s saves to '%s'" % [path, slot])


func test_dev_menu_flag() -> void:
	assert_true(Main.dev_menu(PackedStringArray(["--dev"])))
	assert_false(Main.dev_menu(PackedStringArray(["--player"])), "a player's menu, even from the editor")


func test_the_menu_fits_a_720p_window() -> void:
	# A player's longest menu: Continue, New Game, Random World, Load, Options, The Intro,
	# What's New, Quit. It must end above the version line at 720p (it ran 4 px into it).
	for n: int in [8, 9]:
		var fit: Dictionary = Main.menu_fit(720.0, n)
		var bottom: float = float(fit["top"]) + n * float(fit["entry"]) + (n - 1) * Main.ENTRY_GAP
		assert_lte(bottom, 720.0 - Main.BOTTOM_ROOM, "%d entries end above the version line" % n)
		assert_gte(float(fit["top"]), Main.MENU_TOP_MIN, "and stay under the subtitle")
	assert_eq(Main.menu_fit(1080.0, 8), {"top": Main.MENU_TOP, "entry": Main.ENTRY_HEIGHT}, "a tall window keeps the roomy layout")


func test_every_menu_panel_fits_a_720p_window() -> void:
	var view := Vector2(1280, 720)
	var ng: Vector2 = NewGamePanel.panel_size(view)
	assert_lte(ng.y, 680.0, "New Game leaves room above and below")
	assert_lte(ng.x, 1232.0)
	assert_eq(NewGamePanel.panel_size(Vector2(1920, 1080)), NewGamePanel.FULL_SIZE, "a big window keeps the full panel")
	assert_eq(NewGamePanel.preview_side(ng.y), NewGamePanel.PREVIEW_SHORT)
	assert_lte(OptionsPanel.tab_height(720.0) + 210.0, 720.0, "Options' Back stays on screen")
	assert_eq(OptionsPanel.tab_height(1080.0), 600.0)
	assert_eq(Main.centred(view, Vector2(1400, 800)), Vector2.ZERO, "a panel too big still starts on screen")
	assert_eq(Main.centred(view, Vector2(1000, 600)), Vector2(140, 60))
