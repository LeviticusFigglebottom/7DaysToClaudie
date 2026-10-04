extends GutTest


func _roll(table: StringName, tier: int, seed: int, gamestage: int = 5) -> Array[ItemStack]:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	return LootRoller.roll(table, LootRoller.Context.new(tier, gamestage, rng))


func _sig(stacks: Array[ItemStack]) -> String:
	var parts: PackedStringArray = []
	for s: ItemStack in stacks:
		parts.append(str(s))
	return ",".join(parts)


func test_deterministic_for_same_seed() -> void:
	for seed: int in [1, 2, 3, 99]:
		assert_eq(_sig(_roll(&"duffel_bag", 3, seed)), _sig(_roll(&"duffel_bag", 3, seed)))


func test_different_seeds_vary() -> void:
	var sigs: Dictionary = {}
	for seed: int in 30:
		sigs[_sig(_roll(&"kitchen_cabinet", 2, seed))] = true
	assert_gt(sigs.size(), 5)


func test_guaranteed_items_always_present() -> void:
	for seed: int in 20:
		var out: Array[ItemStack] = _roll(&"weapons_locker", 3, seed)
		assert_true(out.any(func(s: ItemStack) -> bool: return s.item_id == &"ammo_38"))


func test_higher_tier_yields_more_on_average() -> void:
	var low: int = 0
	var high: int = 0
	for seed: int in 300:
		low += _roll(&"kitchen_cabinet", 1, seed).size()
		high += _roll(&"kitchen_cabinet", 5, seed + 10000).size()
	assert_gt(high, low, "tier 5 (%d) should out-yield tier 1 (%d)" % [high, low])


func test_tier_gated_entries() -> void:
	for seed: int in 200:
		for s: ItemStack in _roll(&"weapons_rare", 1, seed):
			assert_ne(s.item_id, &"revolver", "revolver is tier_min 3")


func test_quality_within_bounds_and_scales() -> void:
	var low_sum: float = 0.0
	var high_sum: float = 0.0
	var n_low: int = 0
	var n_high: int = 0
	for seed: int in 300:
		for s: ItemStack in _roll(&"tools_common", 1, seed, 1):
			if s.quality > 0:
				assert_between(s.quality, 1, 6)
				low_sum += s.quality
				n_low += 1
		for s: ItemStack in _roll(&"tools_common", 5, seed, 60):
			if s.quality > 0:
				assert_between(s.quality, 1, 6)
				high_sum += s.quality
				n_high += 1
	assert_gt(n_low, 0)
	assert_gt(n_high, 0)
	assert_gt(high_sum / n_high, low_sum / n_low)
