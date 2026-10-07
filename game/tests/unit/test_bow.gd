extends GutTest
## The hunting bow and its arrows as content and rules (ADR-0057): the items, recipes and loot
## validate; the draw fraction scales an arrow's speed and damage (and steadies it); the bow shoots
## the first arrow it lists that is carried.

const BOW: StringName = &"hunting_bow"


func _bow() -> ItemDef:
	return Content.item(BOW)


func test_bow_arrows_and_recipes_are_content() -> void:
	var bow: ItemDef = _bow()
	assert_not_null(bow, "hunting_bow")
	if bow == null:
		return
	assert_true(BowHandler.is_bow(bow))
	assert_eq(ViewModelHolds.hold_class(bow), &"bow", "drawn in the bow hold")
	assert_gt(bow.equip_num("draw_time"), 0.1)
	assert_true(bow.has_quality and bow.durability > 0.0)
	var arrows: Dictionary = bow.equip.get("arrows", {})
	assert_eq(arrows.keys(), ["arrow_bone", "arrow_stone"], "bone first: the better arrow is nocked first")
	for k: Variant in arrows:
		var a: ItemDef = Content.item(StringName(str(k)))
		assert_not_null(a, "%s is an item" % k)
		if a != null:
			assert_eq(a.category, "ammo")
			assert_true(a.equip.is_empty(), "arrows are not toolbelt items")
		var st: Dictionary = arrows[k]
		assert_gt(float(st.get("damage", 0.0)), 0.0)
		assert_between(float(st.get("break", -1.0)), 0.0, 1.0)
	for id: StringName in [&"hunting_bow", &"arrow_stone", &"arrow_bone"]:
		var r: RecipeDef = Content.get_def(&"recipe", id) as RecipeDef
		assert_not_null(r, "recipe %s" % id)
		if r != null:
			assert_eq(r.result, id)
			assert_true(r.is_hand_recipe(), "made by hand on the salvage roll")
	assert_eq((Content.get_def(&"recipe", &"arrow_stone") as RecipeDef).result_count, 3)
	var table: Dictionary = {}
	var lt: LootTableDef = Content.get_def(&"loot_table", &"wild_trapper_cache") as LootTableDef
	assert_not_null(lt)
	if lt != null:
		for e: Variant in lt.entries:
			table[str((e as Dictionary).get("item", ""))] = true
		assert_true(table.has("hunting_bow") and table.has("arrow_stone"), "a trapper's cache may hold a bow and arrows")
	var vm: Dictionary = ViewModelHolds.config()
	for use: String in ["draw_bow", "release_bow"]:
		assert_true((vm.get("uses", {}) as Dictionary).has(use), use)
	assert_true((vm.get("holds", {}) as Dictionary).has("bow_drawn"))
	assert_eq(ViewModelHolds.problems(), PackedStringArray())


func test_draw_fraction_scales_speed_and_damage() -> void:
	var bow: ItemDef = _bow()
	var dt: float = bow.equip_num("draw_time")
	assert_eq(BowHandler.draw_fraction(0.0, dt), 0.0)
	assert_almost_eq(BowHandler.draw_fraction(dt * 0.5, dt), 0.5, 0.001)
	assert_eq(BowHandler.draw_fraction(dt * 3.0, dt), 1.0, "a held draw stays full")
	var sp: Array = bow.equip["speed"]
	assert_almost_eq(BowHandler.shot_speed(bow, 1.0), float(sp[1]), 0.001, "full draw: full speed")
	assert_almost_eq(BowHandler.shot_speed(bow, 0.0), float(sp[0]), 0.001)
	assert_gt(BowHandler.shot_speed(bow, 0.6), BowHandler.shot_speed(bow, 0.3), "more draw, faster")
	var full: float = float((bow.equip["arrows"] as Dictionary)["arrow_bone"]["damage"])
	assert_almost_eq(BowHandler.shot_damage(bow, &"arrow_bone", 1.0), full, 0.001)
	var half: float = BowHandler.shot_damage(bow, &"arrow_bone", 0.5)
	assert_lt(half, full)
	assert_gt(half, BowHandler.shot_damage(bow, &"arrow_bone", 0.2))
	assert_gt(BowHandler.shot_damage(bow, &"arrow_bone", 1.0), BowHandler.shot_damage(bow, &"arrow_stone", 1.0), "bone bites deeper")
	assert_gt(BowHandler.shot_damage(bow, &"arrow_bone", 1.0, 6), full, "a good bow hits harder")
	assert_eq(BowHandler.shot_damage(bow, &"ammo_38", 1.0), 0.0, "it can't shoot what it doesn't take")
	assert_gt(BowHandler.shot_spread(bow, 0.3, false), BowHandler.shot_spread(bow, 1.0, false), "a part draw wobbles")
	assert_lt(BowHandler.shot_spread(bow, 1.0, true), BowHandler.shot_spread(bow, 1.0, false), "steadier crouched")


func test_the_bow_nocks_the_first_listed_arrow_carried() -> void:
	var bow: ItemDef = _bow()
	var inv := Inventory.new()
	assert_eq(BowHandler.arrow_for(bow, inv), &"", "none carried")
	inv.add_item(&"arrow_stone", 4)
	assert_eq(BowHandler.arrow_for(bow, inv), &"arrow_stone")
	inv.add_item(&"arrow_bone", 1)
	assert_eq(BowHandler.arrow_for(bow, inv), &"arrow_bone")


func test_an_arrows_arc_is_ballistic() -> void:
	var p: Vector3 = Arrow.position_at(Vector3(0, 2, 0), Vector3(10, 5, 0), 10.0, 1.0)
	assert_almost_eq(p.x, 10.0, 0.0001)
	assert_almost_eq(p.y, 2.0 + 5.0 - 5.0, 0.0001)
