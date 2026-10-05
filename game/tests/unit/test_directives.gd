extends GutTest
## Remand Program directives: targets and tier filters, chapters opening in order, level goals
## met on arrival, save round trip, and that every directive's data is valid.


func _finish_chapter(dr: Directives, ch: int) -> void:
	for d: DirectiveDef in Directives.chapter_defs(ch):
		if d.event == "level":
			dr.record("level", &"", d.count)
		else:
			for t: int in d.count:
				dr.record(d.event, StringName(d.targets[0]) if not d.targets.is_empty() else &"", 1,
					StringName(d.min_tier) if d.min_tier != "" else &"normal")


func test_chapters_exist_in_order_with_rewards() -> void:
	var chs: PackedInt32Array = Directives.chapters()
	assert_gte(chs.size(), 3, "several chapters")
	assert_eq(chs[0], 1)
	for ch: int in chs:
		var defs: Array[DirectiveDef] = Directives.chapter_defs(ch)
		assert_gt(defs.size(), 1, "chapter %d has goals" % ch)
		assert_ne(Directives.chapter_name(ch), "", "chapter %d is named" % ch)
		for d: DirectiveDef in defs:
			assert_true(d.reward_xp > 0 or not d.reward_items.is_empty(), "%s pays something" % d.id)


func test_targets_must_match() -> void:
	var dr := Directives.new()
	assert_true(dr.record("craft", &"cordage").is_empty(), "crafting cordage is not the stone axe")
	var done: Array[DirectiveDef] = dr.record("craft", &"stone_axe")
	assert_eq(done.size(), 1)
	assert_eq(done[0].id, &"arrival_axe")
	assert_true(dr.done.has(&"arrival_axe"))
	assert_true(dr.record("craft", &"stone_axe").is_empty(), "a directive pays once")


func test_counts_accumulate() -> void:
	var dr := Directives.new()
	dr.record("fell_tree")
	dr.record("fell_tree")
	assert_eq(dr.count_of(&"arrival_fell"), 2)
	assert_false(dr.done.has(&"arrival_fell"))
	dr.record("fell_tree")
	assert_true(dr.done.has(&"arrival_fell"))


func test_only_the_open_chapter_advances() -> void:
	var dr := Directives.new()
	dr.record("loot")
	assert_eq(dr.count_of(&"cordon_search"), 0, "chapter 2 is not open yet")
	_finish_chapter(dr, 1)
	assert_eq(dr.chapter, 2, "finishing chapter 1 opens chapter 2")
	dr.record("loot")
	assert_eq(dr.count_of(&"cordon_search"), 1)


func test_tier_filter_and_level_goals() -> void:
	var dr := Directives.new()
	for ch: int in [1, 2, 3]:
		_finish_chapter(dr, ch)
	assert_eq(dr.chapter, 4)
	assert_true(dr.record("kill", &"hollow", 1, &"normal").is_empty(), "a normal Hollow is not Seeded")
	assert_eq(dr.record("kill", &"hollow", 1, &"bloomed").size(), 1, "Bloomed counts as at least Seeded")
	assert_true(dr.record("level", &"", 9).is_empty())
	assert_eq(dr.record("level", &"", 12).size(), 1, "reaching past the level counts")


func test_round_trip() -> void:
	var dr := Directives.new()
	_finish_chapter(dr, 1)
	dr.record("loot")
	dr.record("loot")
	var back := Directives.new()
	back.from_dict(dr.to_dict())
	assert_eq(back.chapter, 2)
	assert_eq(back.count_of(&"cordon_search"), 2)
	assert_true(back.done.has(&"arrival_sleep"))
	var ps := PlayerState.new()
	ps.directives.record("fell_tree")
	var ps2 := PlayerState.new()
	ps2.from_dict(ps.to_dict())
	assert_eq(ps2.directives.count_of(&"arrival_fell"), 1, "saved with the player")


func test_all_done_after_the_last_chapter() -> void:
	var dr := Directives.new()
	for ch: int in Directives.chapters():
		_finish_chapter(dr, ch)
	assert_true(dr.all_done())
	assert_true(dr.open().is_empty())
