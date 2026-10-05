extends GutTest
## Gamestage scaling of the Hollowed: infected tiers, spawn gates, the Hum's special mix, and the
## multipliers an enemy takes at spawn.


func test_tier_brackets_follow_gamestage() -> void:
	assert_eq(InfectedTiers.bracket(1), {"normal": 1.0})
	assert_false(InfectedTiers.bracket(14).has("seeded"))
	assert_true(InfectedTiers.bracket(15).has("seeded"))
	assert_true(InfectedTiers.bracket(200).has("bloomed"))


func _count_tiers(gs: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var n: Dictionary = {"normal": 0, "seeded": 0, "bloomed": 0}
	for i: int in 2000:
		var t: String = String(InfectedTiers.pick(gs, rng))
		n[t] = int(n[t]) + 1
	return n


func test_higher_gamestage_rolls_tougher_tiers() -> void:
	var early: Dictionary = _count_tiers(5)
	var late: Dictionary = _count_tiers(90)
	assert_eq(early["normal"], 2000, "nothing infected-tier at the start")
	assert_gt(late["bloomed"], 300)
	assert_gt(late["seeded"], late["bloomed"])


func test_special_types_respect_gamestage_and_authoring() -> void:
	assert_eq(AIDirector.allowed_enemy(&"rammer", 10, false), &"hollow", "too early for a Rammer wandering in")
	assert_eq(AIDirector.allowed_enemy(&"rammer", 45, false), &"rammer")
	assert_eq(AIDirector.allowed_enemy(&"husk", 1, true), &"husk", "an authored sleeper keeps its type")
	assert_eq(AIDirector.allowed_enemy(&"hollow", 1, false), &"hollow")


func test_hum_mix_adds_specials_as_gamestage_rises() -> void:
	var hm := HordeMemory.new()
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var early: Dictionary = hm.plan(5, rng)["mix"]
	var late: Dictionary = hm.plan(70, rng)["mix"]
	for k: String in ["blister", "husk", "rammer"]:
		assert_false(early.has(k) and float(early[k]) > 0.0, "%s absent early" % k)
		assert_gt(float(late.get(k, 0.0)), 0.0, "%s present late" % k)


func test_enemy_takes_rule_and_tier_multipliers() -> void:
	var def: EnemyDef = Content.enemy(&"hollow")
	var e := Enemy.new()
	e.setup(&"t:1", def, null, {"tier": "bloomed"})
	var t: Dictionary = InfectedTiers.tier(&"bloomed")
	assert_almost_eq(e.max_health, def.health * float(t["hp"]), 0.01)
	assert_almost_eq(e.damage_mult, float(t["damage"]), 0.001)
	assert_gt(e.xp_mult, 1.0)
	var plain := Enemy.new()
	plain.setup(&"t:2", def, null, {})
	assert_eq(plain.tier, &"normal")
	assert_almost_eq(plain.max_health, def.health, 0.01)
	e.free()
	plain.free()


func test_special_definitions_carry_their_abilities() -> void:
	assert_false((Content.enemy(&"blister").beh("spit", {}) as Dictionary).is_empty())
	assert_false((Content.enemy(&"blister").beh("death_burst", {}) as Dictionary).is_empty())
	assert_false((Content.enemy(&"husk").beh("armor", {}) as Dictionary).is_empty())
	assert_false((Content.enemy(&"rammer").beh("charge", {}) as Dictionary).is_empty())
	for id: StringName in [&"blister", &"husk", &"rammer"]:
		assert_true(bool(Content.enemy(id).beh("special", false)), "%s is a special" % id)
		assert_gt(Content.enemy(id).gamestage_min, 0)
