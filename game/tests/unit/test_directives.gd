extends GutTest
## Remand Program directives: targets and tier filters, chapters opening in order, level goals
## met on arrival, save round trip, and that every directive's data is valid; building goals
## fitted to worlds without their buildings, and the Hum counting only for the living.


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


func test_dungeon_directives() -> void:
	var dr := Directives.new()
	_finish_chapter(dr, 1)
	dr.record("disarm_trap", &"bear_trap")
	assert_false(dr.done.has(&"cordon_disarm"), "one trap is not two")
	dr.record("disarm_trap", &"shotgun")
	assert_true(dr.done.has(&"cordon_disarm"), "any two armed traps")
	_finish_chapter(dr, 2)
	assert_true(dr.record("clear_poi", &"merrow_house").is_empty(), "the Merrow house is not a tier-3 building")
	assert_eq(dr.record("clear_poi", &"okafor_farmhouse").size(), 1, "the Okafor farmhouse is")


func test_any_building_counts_for_going_inside() -> void:
	var d: DirectiveDef = Content.get_def(&"directive", &"cordon_enter") as DirectiveDef
	assert_true(d.targets.is_empty(), "any building counts")
	assert_false(d.display_name.contains("Pell"), "so the goal names no town")


## A building as PoiManager.all_buildings() lists it, `x` metres east of the drop site.
func _b(id: String, def_id: String, tier: int, x: float, kind: String = "authored", name_: String = "") -> Dictionary:
	return {"id": StringName(id), "def": StringName(def_id), "name": name_ if name_ != "" else def_id, "tier": tier, "kind": kind, "pos": Vector3(x, 0.0, 0.0)}


## Every chapter-3 goal but the hard building.
func _hold_all_but_the_building(dr: Directives) -> void:
	for d: DirectiveDef in Directives.chapter_defs(3):
		if d.id == &"hold_tier3":
			continue
		if d.event == "level":
			dr.record("level", &"", d.count)
		else:
			for t: int in d.count:
				dr.record(d.event)


func test_a_world_without_the_targets_gets_the_nearest_building_like_them() -> void:
	var world: Array = [
		_b("t1/a", "pell_crossing_school", 3, 600.0, "authored", "Pell's Crossing School"),
		_b("t1/b", "pell_savings_loan", 3, -300.0, "authored", "Tamsin Valley Savings & Loan"),
		_b("t2/c", "bungalow_t2_c", 3, 20.0, "generated"),
		_b("t2/d", "merrow_house", 1, 10.0),
	]
	var fit: Dictionary = Directives.for_world(world, Vector3.ZERO, 7)
	var tier3: Dictionary = (fit["stand_ins"] as Dictionary).get(&"hold_tier3", {})
	assert_eq(tier3.get("targets"), PackedStringArray(["pell_savings_loan"]),
		"the nearest building of the same tier and kind stands in (not the nearer generated or tier-1 ones)")
	assert_true((fit["spent"] as Dictionary).has(&"bloom_sawmill"), "no tier-4 building: the sawmill goal is spent")
	var dr := Directives.new()
	dr.set_world(fit)
	assert_eq(dr.label(Content.get_def(&"directive", &"hold_tier3") as DirectiveDef), "Clear Tamsin Valley Savings & Loan", "the tether names it")
	_finish_chapter(dr, 1)
	_finish_chapter(dr, 2)
	_hold_all_but_the_building(dr)
	assert_eq(dr.chapter, 3, "the building is still to do")
	assert_true(dr.record("clear_poi", &"pell_crossing_school").is_empty(), "only the stand-in counts")
	assert_eq(dr.record("clear_poi", &"pell_savings_loan").size(), 1)
	assert_eq(dr.chapter, 4)


func test_a_spent_directive_does_not_hold_up_its_chapter() -> void:
	var dr := Directives.new()
	dr.set_world(Directives.for_world([], Vector3.ZERO, 1))
	assert_true(dr.spent.has(&"hold_tier3") and dr.spent.has(&"bloom_sawmill"), "a world without buildings offers neither")
	_finish_chapter(dr, 1)
	_finish_chapter(dr, 2)
	_hold_all_but_the_building(dr)
	assert_eq(dr.chapter, 4, "chapter 3 is finished without the hard building")
	assert_false(dr.open().has(Content.get_def(&"directive", &"bloom_sawmill")), "the sawmill is not offered")
	_finish_chapter(dr, 4)
	assert_true(dr.all_done(), "and the chain ends")


func test_worlds_with_the_targets_keep_them_and_stand_ins_are_stable() -> void:
	var main: Array = [_b("p/school", "pell_crossing_school", 3, 10.0), _b("p/farm", "okafor_farmhouse", 3, 900.0),
		_b("p/mill", "larch_hollow_sawmill", 4, 50.0)]
	var fit: Dictionary = Directives.for_world(main, Vector3.ZERO, 3)
	assert_true((fit["stand_ins"] as Dictionary).is_empty(), "a world with the Okafor farmhouse and the sawmill keeps its own targets")
	assert_true((fit["spent"] as Dictionary).is_empty())
	# Two equally near candidates: the world seed decides, the same way every time and in any order.
	var twins: Array = [_b("a/x", "pell_crossing_school", 3, 100.0), _b("b/y", "pell_savings_loan", 3, -100.0)]
	var pick: Variant = ((Directives.for_world(twins, Vector3.ZERO, 42)["stand_ins"] as Dictionary)[&"hold_tier3"] as Dictionary)["targets"]
	twins.reverse()
	assert_eq(((Directives.for_world(twins, Vector3.ZERO, 42)["stand_ins"] as Dictionary)[&"hold_tier3"] as Dictionary)["targets"], pick)


func test_a_hum_survived_dead_does_not_count() -> void:
	var prev: GameSession = Game.session
	Game.session = GameSession.create_new({"seed": 5, "game_mode": "slice"})
	var p: PlayerState = Game.local_player()
	for ch: int in [1, 2, 3]:
		_finish_chapter(p.directives, ch)
	assert_eq(p.directives.chapter, 4, "the three-Hums goal is open")
	var tracker := DirectiveTracker.new()
	p.stats.alive = false
	tracker._on_hum_ended(10, {})
	assert_eq(p.directives.count_of(&"bloom_hums"), 0, "dead at dawn: no Hum survived (and no XP either)")
	p.stats.alive = true
	tracker._on_hum_ended(17, {})
	assert_eq(p.directives.count_of(&"bloom_hums"), 1, "alive at dawn: it counts")
	tracker.free()
	Game.session = prev
