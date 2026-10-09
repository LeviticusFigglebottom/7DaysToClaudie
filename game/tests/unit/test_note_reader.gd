extends GutTest
## The note reader and the manual's notes by place (the lore trail).


func test_paginate_keeps_pages_short_and_loses_nothing() -> void:
	var body: String = "First paragraph, short.\n" + "A long sentence that goes on. ".repeat(40) + "\nLast line."
	var pages: PackedStringArray = NoteReader.paginate(body, 300)
	assert_gt(pages.size(), 3)
	for pg: String in pages:
		assert_lte(pg.length(), 330, "a page stays near its budget")
	var joined: String = " ".join(pages).replace("\n", " ")
	for w: String in ["First", "Last line.", "goes on."]:
		assert_string_contains(joined, w)
	assert_eq(NoteReader.paginate("One line.", 300), PackedStringArray(["One line."]))


func test_every_note_style_has_a_sheet() -> void:
	for n: NoteDef in Content.all(&"note"):
		assert_true(NoteReader.STYLES.has(n.style), "%s: style %s" % [n.id, n.style])


func test_notes_group_by_place_newest_first() -> void:
	var found: Dictionary = {
		&"a": {"where": "Pell's Crossing Post Office", "day": 1, "order": 0},
		&"b": {"where": "the woods of Larch Hollow", "day": 2, "order": 1},
		&"c": {"where": "Pell's Crossing Post Office", "day": 3, "order": 2},
	}
	var groups: Array[Dictionary] = FieldManual.notes_by_place([&"a", &"b", &"c", &"old"], found)
	assert_eq(groups.size(), 3)
	assert_eq(groups[0]["where"], "Pell's Crossing Post Office", "the latest find's place first")
	assert_eq(groups[0]["notes"], [&"c", &"a"], "newest first within a place")
	assert_eq(groups[1]["where"], "the woods of Larch Hollow")
	assert_eq(groups[2]["where"], "Earlier", "notes read before places were kept come last")


func test_notes_found_survives_a_save() -> void:
	var p := PlayerState.new()
	p.read_notes[&"okafor_letter"] = true
	p.notes_found[&"okafor_letter"] = {"where": "Okafor Farmhouse", "day": 4, "order": 0}
	var back := PlayerState.new()
	back.from_dict(JSON.parse_string(JSON.stringify(p.to_dict())))
	assert_eq(str((back.notes_found[&"okafor_letter"] as Dictionary)["where"]), "Okafor Farmhouse")
	var old: Dictionary = p.to_dict()
	old.erase("notes_found")
	var back2 := PlayerState.new()
	back2.from_dict(old)
	assert_true(back2.notes_found.is_empty(), "an older save loads with no places")


func test_reader_pages_and_closes() -> void:
	var r := NoteReader.new()
	add_child_autofree(r)
	var n := NoteDef.new()
	n.title = "Test"
	n.style = "typed"
	n.body = "Word. ".repeat(400)
	r.show_note(n, {"where": "Somewhere", "day": 2})
	assert_true(r.is_open())
	assert_gt(r.page_count(), 1)
	r.turn(1)
	r.close_reader()
	assert_false(r.is_open())
