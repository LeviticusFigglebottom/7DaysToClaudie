extends GutTest


func test_xp_levels_up_and_grants_points() -> void:
	var p := Progression.new()
	var pts: int = p.skill_points
	var gained: int = p.add_xp(p.xp_to_next())
	assert_eq(gained, 1)
	assert_eq(p.level, 2)
	assert_eq(p.skill_points, pts + 1)


func test_perk_gated_by_attribute() -> void:
	var p := Progression.new()
	p.skill_points = 10
	assert_true(p.buy_perk(&"timberwright"))
	assert_false(p.can_buy_perk(&"timberwright"), "rank 2 needs sinew 3")
	p.raise_attribute(&"sinew")
	p.raise_attribute(&"sinew")
	assert_eq(p.attr_level(&"sinew"), 3)
	assert_true(p.buy_perk(&"timberwright"))
	assert_almost_eq(p.modifier("chop_damage_mult"), 0.4, 0.0001)
	assert_almost_eq(p.modifier("log_carry"), 1.0, 0.0001)


func test_attribute_per_level_modifiers() -> void:
	var p := Progression.new()
	p.skill_points = 10
	p.raise_attribute(&"grit")
	assert_almost_eq(p.modifier("max_health"), 5.0, 0.0001)


func test_perk_unlocks_blueprint() -> void:
	var p := Progression.new()
	p.skill_points = 5
	assert_false(p.knows_blueprint(Content.get_def(&"blueprint", &"spike_barrier") as BlueprintDef))
	p.buy_perk(&"builder")
	assert_true(p.knows_blueprint(Content.get_def(&"blueprint", &"spike_barrier") as BlueprintDef))


func test_learn_by_reading() -> void:
	var p := Progression.new()
	var r: RecipeDef = Content.recipe(&"can_chime")
	assert_false(p.knows_recipe(r))
	var learned: Dictionary = p.learn_from_item(Content.item(&"schematic_can_chime"))
	assert_eq(learned.get("id"), &"can_chime")
	assert_true(p.knows_recipe(r))
	assert_eq(p.learn_from_item(Content.item(&"schematic_can_chime")), {}, "already known")


func test_skill_track_unlocks_recipe() -> void:
	var p := Progression.new()
	var r: RecipeDef = Content.recipe(&"first_aid_kit_craft")
	p.learn_from_item(Content.item(&"journal_field_medicine"))
	assert_false(p.knows_recipe(r))
	p.learn_from_item(Content.item(&"journal_field_medicine"))
	assert_true(p.knows_recipe(r))


func test_round_trip() -> void:
	var p := Progression.new()
	p.skill_points = 4
	p.buy_perk(&"scavenger")
	p.raise_attribute(&"keen")
	p.learn_from_item(Content.item(&"schematic_log_cabin"))
	var q := Progression.new()
	q.from_dict(JSON.parse_string(JSON.stringify(p.to_dict())))
	assert_eq(q.to_dict(), p.to_dict())
