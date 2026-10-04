extends GutTest
## Every shipped content file must load with zero errors and valid cross references.


func test_content_loads_without_errors() -> void:
	var errs: PackedStringArray = Content.load_all()
	assert_eq(errs.size(), 0, "content errors:\n" + "\n".join(errs))


func test_core_kinds_present() -> void:
	for kind: StringName in [&"item", &"recipe", &"loot_table", &"container", &"enemy", &"structure", &"blueprint", &"perk", &"attribute", &"species", &"biome", &"weather"]:
		assert_gt(Content.all(kind).size(), 0, "no %s defs" % kind)


func test_every_container_table_rolls() -> void:
	for c: ContainerDef in Content.all(&"container"):
		var rng := RandomNumberGenerator.new()
		rng.seed = 7
		for tier: int in range(1, 6):
			var out: Array[ItemStack] = LootRoller.roll(c.loot_table, LootRoller.Context.new(tier, 10, rng))
			for s: ItemStack in out:
				assert_not_null(s.def(), "%s rolled unknown item %s" % [c.id, s.item_id])
				assert_gt(s.count, 0)


func test_def_reader_reports_typos() -> void:
	var d := ItemDef.new()
	var errs: PackedStringArray = d.parse({"id": "x_item", "stak_max": 5}, &"item", "test.json")
	assert_eq(errs.size(), 1)
	assert_string_contains(errs[0], "unknown field 'stak_max'")


func test_def_reader_rejects_bad_id() -> void:
	var d := ItemDef.new()
	var errs: PackedStringArray = d.parse({"id": "Bad Id"}, &"item", "test.json")
	assert_gt(errs.size(), 0)
