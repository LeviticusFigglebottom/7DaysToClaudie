extends GutTest
## The Load screen (LoadPanel): a card's words, the thumbnail's crop, the files beside a save, and
## Delete asking before it deletes.

const SLOT: String = "qa_test_load_panel"


func after_each() -> void:
	SaveSystem.delete_slot(SLOT)


func _meta(extra: Dictionary = {}) -> Dictionary:
	var m: Dictionary = {"slot": "run_3", "day": 4, "hour": 21.75, "preset": "survivor", "world_mode": "main",
		"play_seconds": 2 * 3600 + 5 * 60, "saved_unix": 1000}
	m.merge(extra, true)
	return m


func test_card_text() -> void:
	var t: PackedStringArray = LoadPanel.card_text(_meta(), {"place": "the woods of Larch Hollow", "region": "Larch Hollow"}, 1000 + 7200)
	assert_eq(t[0], "Run 3  ·  Day 4, 21:45")
	assert_eq(t[1], "The woods of Larch Hollow  ·  Survivor  ·  Hollowmere Valley  ·  played 2h 05m")
	assert_eq(t[2], "saved 2 hours ago")


func test_card_text_without_card_or_preset() -> void:
	var t: PackedStringArray = LoadPanel.card_text(_meta({"preset": "", "world_mode": "random", "game_mode": "slice"}), {}, 1030)
	assert_eq(t[1], "Random world  ·  Vertical slice  ·  played 2h 05m")
	assert_eq(t[2], "saved just now")


func test_ago() -> void:
	assert_eq(LoadPanel.ago(10), "just now")
	assert_eq(LoadPanel.ago(12 * 60), "12 minutes ago")
	assert_eq(LoadPanel.ago(3 * 3600), "3 hours ago")
	assert_eq(LoadPanel.ago(5 * 86400), "5 days ago")


func test_thumbnail_crops_to_the_card() -> void:
	# A 4:3 frame, left half red, right half blue: cut to 16:9 from the middle, then shrunk.
	var img := Image.create(800, 600, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(0, 0, 400, 600), Color.RED)
	img.fill_rect(Rect2i(400, 0, 400, 600), Color.BLUE)
	var t: Image = LoadPanel.thumbnail(img)
	assert_eq(t.get_size(), LoadPanel.THUMB_SIZE)
	assert_gt(t.get_pixel(10, 100).r, 0.9)
	assert_gt(t.get_pixel(370, 100).b, 0.9)
	# An ultrawide frame keeps its middle too.
	assert_eq(LoadPanel.thumbnail(Image.create(3440, 1440, false, Image.FORMAT_RGB8)).get_size(), LoadPanel.THUMB_SIZE)


func test_reads_the_files_beside_a_save() -> void:
	assert_eq(LoadPanel.read_card(SLOT), {})
	assert_null(LoadPanel.read_thumb(SLOT))
	var dir: String = SaveSystem.slot_dir(SLOT)
	DirAccess.make_dir_recursive_absolute(dir)
	var f := FileAccess.open(dir.path_join(LoadPanel.CARD_FILE), FileAccess.WRITE)
	f.store_string(JSON.stringify({"place": "Fire Station"}))
	f.close()
	var img := Image.create(LoadPanel.THUMB_SIZE.x, LoadPanel.THUMB_SIZE.y, false, Image.FORMAT_RGB8)
	img.fill(Color(0.2, 0.4, 0.3))
	img.save_webp(dir.path_join(LoadPanel.THUMB_FILE), true, 0.8)
	assert_eq(str(LoadPanel.read_card(SLOT).get("place")), "Fire Station")
	var tex: Texture2D = LoadPanel.read_thumb(SLOT)
	assert_not_null(tex)
	if tex != null:
		assert_eq(Vector2i(tex.get_size()), LoadPanel.THUMB_SIZE)


func test_delete_asks_first() -> void:
	DirAccess.make_dir_recursive_absolute(SaveSystem.slot_dir(SLOT))
	var panel := LoadPanel.new()
	panel.slots = [_meta({"slot": SLOT})]
	add_child_autofree(panel)
	var del: Button = null
	for b: Node in panel.find_children("*", "Button", true, false):
		if (b as Button).text == "Delete":
			del = b
	assert_not_null(del)
	del.pressed.emit()
	assert_true(DirAccess.dir_exists_absolute(SaveSystem.slot_dir(SLOT)), "the first press only asks")
	assert_string_contains(del.text, "again")
	del.pressed.emit()
	assert_false(DirAccess.dir_exists_absolute(SaveSystem.slot_dir(SLOT)), "the second press deletes")
	assert_true(panel.slots.is_empty())


func test_load_emits_the_slot() -> void:
	var panel := LoadPanel.new()
	panel.slots = [_meta()]
	add_child_autofree(panel)
	watch_signals(panel)
	for b: Node in panel.find_children("*", "Button", true, false):
		if (b as Button).text == "Load":
			(b as Button).pressed.emit()
	assert_signal_emitted_with_parameters(panel, "load_requested", ["run_3"])
