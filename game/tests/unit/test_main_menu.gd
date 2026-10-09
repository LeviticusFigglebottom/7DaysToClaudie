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
