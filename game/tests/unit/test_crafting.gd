extends GutTest

var _knows_all: Callable = func(_r: RecipeDef) -> bool: return true


func test_exact_slate_matches_recipe() -> void:
	var r: RecipeDef = Crafting.match_recipe({&"stick": 1, &"stone": 1, &"cordage": 1}, &"", _knows_all)
	assert_not_null(r)
	assert_eq(r.id, &"stone_axe")


func test_non_exact_slate_does_not_match() -> void:
	assert_null(Crafting.match_recipe({&"stick": 2, &"stone": 1, &"cordage": 1}, &"", _knows_all))
	assert_null(Crafting.match_recipe({}, &"", _knows_all))


func test_unknown_recipe_hidden() -> void:
	var knows_default: Callable = func(r: RecipeDef) -> bool: return r.unlock == "default"
	assert_null(Crafting.match_recipe({&"empty_can": 3, &"cordage": 1}, &"", knows_default), "can_chime requires schematic")


func test_craft_consumes_and_produces() -> void:
	var inv := Inventory.new()
	inv.add_item(&"plant_fiber", 7)
	var res: Crafting.Result = Crafting.craft(Content.recipe(&"cordage"), inv, &"")
	assert_true(res.ok, res.reason)
	assert_eq(inv.count_of(&"plant_fiber"), 4)
	assert_eq(inv.count_of(&"cordage"), 1)


func test_craft_fails_without_ingredients() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stick", 1)
	var res: Crafting.Result = Crafting.craft(Content.recipe(&"stone_axe"), inv, &"")
	assert_false(res.ok)
	assert_eq(inv.count_of(&"stick"), 1, "unchanged")


func test_station_required() -> void:
	var inv := Inventory.new()
	inv.add_item(&"water_bottle_dirty", 1)
	assert_false(Crafting.craft(Content.recipe(&"boil_water"), inv, &"").ok)
	assert_true(Crafting.craft(Content.recipe(&"boil_water"), inv, &"campfire").ok)
	assert_eq(inv.count_of(&"water_bottle_clean"), 1)


func test_craft_atomic_when_no_room() -> void:
	var inv := Inventory.new(&"c", 1)
	inv.add_item(&"plant_fiber", 3)
	# Result needs its own slot but the fiber slot frees up — this must succeed.
	assert_true(Crafting.craft(Content.recipe(&"cordage"), inv, &"").ok)
	var inv2 := Inventory.new(&"c", 1)
	inv2.add_item(&"plant_fiber", 6)
	# Fiber remains (3 left) so the cordage has no slot: must fail and change nothing.
	var res: Crafting.Result = Crafting.craft(Content.recipe(&"cordage"), inv2, &"")
	assert_false(res.ok)
	assert_eq(inv2.count_of(&"plant_fiber"), 6)


func test_required_tool() -> void:
	var inv := Inventory.new()
	inv.add_item(&"log", 1)
	assert_false(Crafting.check(Content.recipe(&"saw_planks"), inv, &"workbench").ok, "needs an axe")
	inv.add_item(&"stone_axe")
	assert_true(Crafting.craft(Content.recipe(&"saw_planks"), inv, &"workbench").ok)
	assert_eq(inv.count_of(&"wood_plank"), 6)


func test_crafted_quality_scales_with_skill() -> void:
	var r: RecipeDef = Content.recipe(&"stone_axe")
	assert_eq(Crafting.quality_for(r, 0), 1)
	assert_eq(Crafting.quality_for(r, 3), 4)
	assert_eq(Crafting.quality_for(r, 20), 6)
	assert_eq(Crafting.quality_for(Content.recipe(&"cordage"), 5), 0, "non-quality result")
