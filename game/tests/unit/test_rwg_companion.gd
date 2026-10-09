extends GutTest
## Random worlds' `companion` site (ADR-0058, generator v8): Ezra Vane's camp stands once in every
## world, 300-900 m from the drop site, off the roads, with no trail to it; it is placed after
## everything else from its own stream.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")

const CAMP: String = "ezra_camp"


func _gen(seed: int, size: int = 4) -> RefCounted:
	return Generator.generate(GenSettings.resolve(&"standard", {"size": size}, seed))


func test_config_has_one_unique_companion_entry() -> void:
	assert_eq(GenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json is valid with the companion site")
	var entries: Array = (((GenSettings.tuning().get("wilderness", {}) as Dictionary).get("pool", []) as Array)
		.filter(func(e: Dictionary) -> bool: return str(e.get("site", "")) == "companion"))
	assert_eq(entries.size(), 1)
	if entries.size() == 1:
		assert_eq(str(entries[0]["poi"]), CAMP)
		assert_true(bool(entries[0].get("unique", false)))
		assert_eq(str(entries[0]["access"]), "none", "found, not reached by a path")
	assert_gte(Generator.VERSION, 8, "the companion's camp moved the output (ADR-0058); later versions keep it")


func test_one_camp_in_a_ring_round_the_drop_site_off_the_roads() -> void:
	for seed: int in [11, 2024, 90210]:
		var g: RefCounted = _gen(seed)
		var camps: Array = (g.get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["def"]) == CAMP)
		assert_eq(camps.size(), 1, "seed %d: one camp" % seed)
		if camps.is_empty():
			continue
		var c: Dictionary = camps[0]
		assert_eq(str(c["site"]), "companion")
		var drop: Vector2 = (g.get(&"drop") as Dictionary).get("pos", Vector2.ZERO)
		var d: float = (c["center"] as Vector2).distance_to(drop)
		assert_between(d, 280.0, 920.0, "seed %d: %.0f m from the drop site" % [seed, d])
		assert_gte(float(g.call(&"road_clearance", c["poly"])), 18.0, "seed %d: off the roads" % seed)
		# The camp is placed after every other wilderness place; only later stages (the Lift 3
		# wreck's `crash` site, generator VERSION 13) may come after it.
		var places: Array = g.get(&"places") as Array
		for later: Dictionary in places.slice(places.find(c) + 1):
			assert_eq(str(later.get("site", "")), "crash", "seed %d: only the crash site is placed after the camp" % seed)


func test_deterministic() -> void:
	var a: Array = (_gen(777).get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["def"]) == CAMP)
	var b: Array = (_gen(777).get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["def"]) == CAMP)
	assert_eq(a.size(), b.size())
	if not a.is_empty() and not b.is_empty():
		assert_eq(a[0]["origin"], b[0]["origin"])
		assert_eq(a[0]["rot"], b[0]["rot"])
