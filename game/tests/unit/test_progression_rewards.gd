extends GutTest
## Progression that changes the character and the world: stats derived from attributes and perks,
## XP sources, the reasons the Record tab shows, loot quality, structure toughness, weapon stagger
## and quality tiers.


func test_attributes_and_perks_change_derived_stats() -> void:
	var ps := PlayerState.new()
	var base_bulk: float = ps.inventory.max_bulk
	var base_hp: float = ps.stats.max_health
	ps.progression.skill_points = 20
	assert_true(ps.progression.raise_attribute(&"sinew"))
	assert_almost_eq(ps.inventory.max_bulk, base_bulk + 2.0, 0.001, "Sinew: +2 pack space a level")
	assert_true(ps.progression.buy_perk(&"packhorse"))
	assert_almost_eq(ps.inventory.max_bulk, base_bulk + 10.0, 0.001, "Packhorse rank 1: +8")
	ps.stats.health = 60.0
	assert_true(ps.progression.raise_attribute(&"grit"))
	assert_almost_eq(ps.stats.max_health, base_hp + 5.0, 0.001)
	assert_almost_eq(ps.stats.health, 65.0, 0.001, "the new health is filled in")
	assert_true(ps.progression.buy_perk(&"second_wind"))
	assert_almost_eq(ps.stats.stamina_regen_mult, 1.0 + 0.03 + 0.2, 0.0001)


func test_stamina_recovers_faster_with_second_wind() -> void:
	var slow := SurvivalStats.new()
	var fast := SurvivalStats.new()
	fast.set_bonuses(0.0, 1.5)
	for s: SurvivalStats in [slow, fast]:
		s.stamina = 10.0
		s.tick_realtime(2.0)
	assert_gt(fast.stamina, slow.stamina)


func test_timberwright_carries_a_third_log() -> void:
	var ps := PlayerState.new()
	ps.progression.skill_points = 20
	assert_eq(ps.inventory.carry_limit(&"log"), 2)
	ps.progression.buy_perk(&"timberwright")
	ps.progression.raise_attribute(&"sinew")
	ps.progression.raise_attribute(&"sinew")
	assert_true(ps.progression.buy_perk(&"timberwright"))
	assert_eq(ps.inventory.carry_limit(&"log"), 3)
	assert_eq(ps.inventory.add_item(&"log", 4), 1, "the fourth log does not fit")
	assert_eq(ps.inventory.count_of(&"log"), 3)


func test_derived_stats_are_recomputed_on_load() -> void:
	var ps := PlayerState.new()
	ps.progression.skill_points = 5
	ps.progression.raise_attribute(&"grit")
	ps.stats.health = 101.0
	var d: Dictionary = ps.to_dict()
	(d["inventory"] as Dictionary)["bulk"] = 1.0
	var back := PlayerState.new()
	back.from_dict(d)
	assert_almost_eq(back.stats.max_health, ps.stats.max_health, 0.001)
	assert_almost_eq(back.stats.health, 101.0, 0.001, "saved health is kept, not topped up")
	assert_almost_eq(back.inventory.max_bulk, ps.inventory.max_bulk, 0.001, "capacity comes from progression, not the save")


func test_block_reasons_explain_locked_choices() -> void:
	var p := Progression.new()
	p.skill_points = 0
	assert_eq(p.perk_block_reason(&"packhorse"), "needs Sinew 2")
	assert_eq(p.attribute_block_reason(&"sinew"), "needs 1 point")
	p.skill_points = 1
	assert_eq(p.perk_block_reason(&"timberwright"), "")
	assert_true(p.can_buy_perk(&"timberwright"))
	assert_eq(p.perk_block_reason(&"no_such_perk"), "unknown perk")
	p.attributes[&"sinew"] = 10
	assert_eq(p.attribute_block_reason(&"sinew"), "at its peak")


func test_award_reads_the_xp_table() -> void:
	var p := Progression.new()
	var table: Dictionary = Content.config(&"progression").get("xp", {})
	p.award("loot_container", 3)
	assert_eq(p.xp, int(table["loot_container"]) * 3)
	for source: String in ["build_piece", "upgrade_piece", "complete_blueprint", "discover_poi", "survive_hum", "clear_poi_per_tier"]:
		assert_true(table.has(source), "%s pays XP" % source)


func _avg_quality(bonus: float) -> float:
	var total: float = 0.0
	var n: int = 0
	for i: int in 400:
		var rng := RandomNumberGenerator.new()
		rng.seed = 5000 + i
		var ctx := LootRoller.Context.new(2, 10, rng)
		ctx.quality_bonus = bonus
		for st: ItemStack in LootRoller.roll(&"weapons_rare", ctx):
			if st.quality > 0:
				total += float(st.quality)
				n += 1
	return total / maxf(1.0, float(n))


func test_loot_quality_bonus_finds_better_gear() -> void:
	var plain: float = _avg_quality(0.0)
	var keen: float = _avg_quality(1.2)
	assert_gt(keen, plain + 0.6, "Keen/Scavenger raise the quality you find (%.2f -> %.2f)" % [plain, keen])


func test_structure_toughness_follows_the_builder() -> void:
	var def: StructureDef = Content.structure(BuildingManager.LOG_DEF)
	var piece := StructurePiece.new()
	piece.setup(&"s:1", def, null, -1.0, 1.3)
	assert_almost_eq(piece.max_hp(), def.hp * 1.3, 0.01)
	assert_almost_eq(piece.hp, def.hp * 1.3, 0.01, "placed at full (bonus) health")
	piece.free()
	var ps := PlayerState.new()
	ps.progression.skill_points = 5
	assert_almost_eq(BuildingManager._hp_mult(ps), 1.0, 0.001)
	ps.progression.buy_perk(&"builder")
	assert_almost_eq(BuildingManager._hp_mult(ps), 1.15, 0.001)


func test_heavier_blows_stagger_with_less_damage() -> void:
	var e := Enemy.new()
	e.setup(&"t:stagger", Content.enemy(&"hollow"), null, {})
	var light := DamageInfo.make(10.0, &"blunt", &"melee", &"")
	light.stagger = 0.3
	var heavy := DamageInfo.make(10.0, &"blunt", &"melee", &"")
	heavy.stagger = 0.6
	assert_lt(e._stagger_threshold(heavy), e._stagger_threshold(light))
	var unset := DamageInfo.make(10.0, &"fire", &"fire", &"")
	assert_almost_eq(e._stagger_threshold(unset), e._stagger_threshold(light), 0.001, "sources without a stagger keep the old threshold")
	e.free()


func test_quality_tiers_have_names_and_scale_damage() -> void:
	assert_eq(ItemStack.quality_name(1), "Scrap")
	assert_eq(ItemStack.quality_name(6), "Pristine")
	assert_ne(ItemStack.quality_color(1), ItemStack.quality_color(6))
	assert_gt(ItemStack.quality_damage_mult(6), ItemStack.quality_damage_mult(1))
	assert_almost_eq(ItemStack.quality_damage_mult(0), 1.0, 0.001)
