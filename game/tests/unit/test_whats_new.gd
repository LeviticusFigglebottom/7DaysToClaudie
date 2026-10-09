extends GutTest
## The main menu's What's new: its data reads, it opens once per new entry, and closing marks it
## seen.


func test_data_has_a_newest_entry_with_short_items() -> void:
	var e: Dictionary = WhatsNewPanel.newest()
	assert_ne(str(e.get("id", "")), "")
	var items: Array = e.get("items", [])
	assert_gt(items.size(), 8)
	for it: Dictionary in items:
		assert_ne(str(it.get("head", "")), "")
		assert_lt(str(it.get("text", "")).length(), 220, "%s: a line or two" % it.get("head", ""))


func test_no_lore_trail_words() -> void:
	# docs/LORE_TRAIL.md: the cause is found in the world, never told by the UI.
	var text: String = JSON.stringify(WhatsNewPanel.entries()).to_lower()
	for word: String in ["bore", "corvane", "voss", "bloom core", "chemical release"]:
		assert_false(text.contains(word), "names '%s'" % word)


func test_shows_once_per_entry() -> void:
	assert_true(WhatsNewPanel.should_show("round-4", ""))
	assert_false(WhatsNewPanel.should_show("round-4", "round-4"))
	assert_true(WhatsNewPanel.should_show("round-5", "round-4"))
	assert_false(WhatsNewPanel.should_show("", ""))


func test_closing_marks_it_seen() -> void:
	var was: String = Settings.whats_new_seen
	Settings.whats_new_seen = ""
	var p := WhatsNewPanel.new()
	add_child_autofree(p)
	watch_signals(p)
	p.call(&"_close")
	assert_eq(Settings.whats_new_seen, str(WhatsNewPanel.newest().get("id", "")))
	assert_signal_emitted(p, "closed")
	Settings.whats_new_seen = was
	Settings.save()
