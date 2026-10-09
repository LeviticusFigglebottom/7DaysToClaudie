extends GutTest
## Random worlds' forest caves (ADR-0056, CAVES_PLAN WS-E; RwgGenerator._caves, tuning.caves): a
## few grottos and shelters per world in steep forest and rocky ground, each one the real planner
## accepts on the reference ground, off roads, towns, places, trader posts and the drop site, apart
## from each other, inside their region, and written into their region's features.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")

var _g: RefCounted


func before_all() -> void:
	_g = Generator.generate(GenSettings.resolve(&"standard", {"size": 4}, 7))


func test_config_is_valid() -> void:
	assert_eq(GenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json is valid with tuning.caves")
	var t: Dictionary = GenSettings.tuning().get("caves", {})
	assert_gt(float(t.get("per_region", 0.0)), 0.0, "caves are on")
	var styles: Dictionary = (Content.config(&"caves") as Dictionary).get("styles", {})
	for st: Variant in (t.get("styles", {}) as Dictionary).keys():
		assert_true(styles.has(str(st)), "style '%s' is a caves.json style" % st)


func test_caves_keep_their_distances() -> void:
	var caves: Array = _g.get(&"caves")
	gut.p("[rwg caves] %d caves: %s" % [caves.size(), caves.map(func(c: Dictionary) -> String: return "%s %s %s" % [c["id"], c["style"], c["mouth"]])])
	assert_gt(caves.size(), 0, "a 4x4 world has caves")
	var t: Dictionary = GenSettings.tuning().get("caves", {})
	var clear: Dictionary = t.get("clearance", {})
	var biomes: Array = t.get("biomes", [])
	var regions: Dictionary = _g.get(&"regions")
	var drop: Dictionary = _g.get(&"drop")
	var ids: Dictionary = {}
	for c: Dictionary in caves:
		var m: Vector2 = c["mouth"]
		assert_false(ids.has(c["id"]), "unique id %s" % c["id"])
		ids[c["id"]] = true
		assert_true(biomes.has(_g.call(&"biome_at", m)), "%s in a forest or rocky biome" % c["id"])
		assert_true((regions[c["cell"]]["rect"] as Rect2).grow(-float(t.get("inset", 96.0)) + 12.0).has_point(m), "%s inside its region" % c["id"])
		assert_gte(float(_g.call(&"nearest_road", m)[0]), float(clear["road"]) - 0.5, "%s off the roads" % c["id"])
		assert_gte(float(_g.call(&"_town_distance", m)), float(clear["town"]) - 0.5, "%s away from the towns" % c["id"])
		assert_gte((drop["pos"] as Vector2).distance_to(m), float(clear["drop"]) - 0.5, "%s away from the drop site" % c["id"])
		for pl: Dictionary in _g.get(&"places"):
			assert_gte((pl["center"] as Vector2).distance_to(m), float(clear["place"]) - 0.5, "%s away from %s" % [c["id"], pl["id"]])
		for c2: Dictionary in caves:
			if c2 != c:
				assert_gte((c2["mouth"] as Vector2).distance_to(m), float(clear["cave"]) - 0.5, "%s apart from %s" % [c["id"], c2["id"]])


func test_caves_are_region_features_the_planner_takes() -> void:
	var caves: Array = _g.get(&"caves")
	var regions: Dictionary = _g.get(&"regions")
	var cfg: Dictionary = Content.config(&"caves")
	var ground: Variant = _g.get(&"_ref")
	var terrain: RefCounted = _g.get(&"terrain")
	if ground == null:
		ground = Generator.RefGround.new(terrain, int(_g.get(&"settings").get(&"seed")) & 0x7fffffff, 4)
	for c: Dictionary in caves:
		var feats: Array = (_g.call(&"region_json", c["cell"]) as Dictionary)["features"]
		var found: Array = feats.filter(func(f: Dictionary) -> bool: return str(f.get("type", "")) == "cave" and str(f.get("id", "")) == str(c["id"]))
		assert_eq(found.size(), 1, "%s is a feature of %s" % [c["id"], c["cell"]])
		if found.size() != 1:
			continue
		var spec: Dictionary = CaveSites.feature_spec(found[0], cfg)
		assert_false(spec.is_empty(), "%s reads as a cave spec" % c["id"])
		spec["region_id"] = str(regions[c["cell"]]["id"])
		spec["region_rect"] = regions[c["cell"]]["rect"]
		# The shape the game gives it: seeded per world and cave id.
		var plan: CavePlan = CavePlan.build(spec, CaveSites.shape_seed(str(_g.get(&"world_id")), str(c["id"])), Callable(ground, &"h"), cfg)
		assert_true(plan.ok, "%s plans on the reference ground: %s" % [c["id"], plan.reason])
