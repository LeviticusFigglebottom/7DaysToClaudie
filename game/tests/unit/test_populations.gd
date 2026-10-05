extends GutTest
## Population looks (ADR-0028): which body a Hollowed wears is chosen by data (PopulationDef),
## deterministically per Hollowed, and every body a population names is a generated character.

## Character bodies are catalogued in the character catalog and, for some families (the Ashen),
## next to their props: every catalog is searched.
const CATALOGS: String = "../tools/assetgen/blender_catalogs"


func _pop(id: StringName) -> PopulationDef:
	return Content.get_def(&"population", id) as PopulationDef


func _catalogs() -> String:
	var dir: String = ProjectSettings.globalize_path("res://").path_join(CATALOGS)
	var text: String = ""
	for f: String in DirAccess.get_files_at(dir):
		if f.ends_with(".py"):
			text += FileAccess.get_file_as_string(dir.path_join(f))
	return text


func test_valley_populations_load() -> void:
	for id: StringName in [&"clinic", &"church", &"cordon", &"loggers", &"hunters", &"ashen"]:
		assert_not_null(_pop(id), "population %s" % id)
	for e: String in Content.errors():
		assert_false(e.contains("populations/"), e)


func test_pick_is_deterministic_per_hollowed() -> void:
	var pd: PopulationDef = _pop(&"clinic")
	var a: String = pd.pick(&"hollow", "sl:tamsin_clinic:waiting_1")
	assert_eq(pd.pick(&"hollow", "sl:tamsin_clinic:waiting_1"), a, "the same sleeper wears the same clothes")
	var seen: Dictionary = {}
	for i: int in 40:
		seen[pd.pick(&"hollow", "sl:tamsin_clinic:s%d" % i)] = true
	assert_gt(seen.size(), 2, "different sleepers dress differently")


func test_pick_follows_weights_and_mix() -> void:
	var pd: PopulationDef = _pop(&"clinic")
	var counts: Dictionary = {}
	var n: int = 3000
	for i: int in n:
		var b: String = pd.pick(&"hollow", "e:%d" % i)
		counts[b] = int(counts.get(b, 0)) + 1
	var table: Dictionary = pd.bodies_for(&"hollow")
	var total: float = 0.0
	for b: String in table:
		total += float(table[b])
	for b: String in table:
		var want: float = n * pd.mix * float(table[b]) / total
		assert_almost_eq(float(counts.get(b, 0)), want, want * 0.25 + 15.0, "share of %s" % b)
	assert_almost_eq(float(counts.get("", 0)), n * (1.0 - pd.mix), n * 0.04, "visitors keep their own clothes")


func test_types_a_population_does_not_name_keep_their_bodies() -> void:
	assert_eq(_pop(&"clinic").pick(&"husk", "e:1"), "", "a Husk stays a Husk in the clinic")
	assert_eq(_pop(&"church").pick(&"rammer", "e:2"), "")


func test_bad_population_data_is_reported() -> void:
	var pd := PopulationDef.new()
	var errs: PackedStringArray = pd.parse({"id": "bad", "bodies": {"hollow": {"models/hollow_a": 1, "characters/x": 0}},
		"colour": "red"}, &"population", "test.json")
	assert_eq(errs.size(), 3, "a non-character body, a zero weight and an unknown field: %s" % [errs])


func test_population_bodies_are_generated_characters() -> void:
	var text: String = _catalogs()
	assert_true(text.contains("\"hollow_a\": {"), "asset catalogs readable at %s" % CATALOGS)
	for pd: PopulationDef in Content.all(&"population"):
		for b: String in pd.all_bodies():
			var key: String = b.trim_prefix("characters/")
			assert_true(text.contains("\"%s\": {" % key), "%s: body %s is in the character catalog" % [pd.id, b])


func test_enemy_bodies_are_generated_characters() -> void:
	var text: String = _catalogs()
	for d: EnemyDef in Content.all(&"enemy"):
		for b: String in d.bodies:
			assert_true(text.contains("\"%s\": {" % b.trim_prefix("characters/")), "%s: body %s is in the character catalog" % [d.id, b])


func test_buildings_name_their_people() -> void:
	assert_eq((Content.get_def(&"poi", &"tamsin_clinic") as PoiDef).population, &"clinic")
	assert_eq((Content.get_def(&"poi", &"st_ansel_church") as PoiDef).population, &"church")


func test_without_a_world_a_hollowed_keeps_its_own_body() -> void:
	var e := Enemy.new()
	e.setup(&"test:pop", Content.enemy(&"hollow"), null, {"tier": "normal", "poi": "tamsin_clinic", "sleeper": "waiting_1"})
	assert_eq(EnemyVisual.population_body(e, "characters/hollow_a"), "characters/hollow_a")
	e.free()
