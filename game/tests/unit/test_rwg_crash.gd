extends GutTest
## Random worlds' `crash` site (generator v13): the lift's crash site (lift3_crash_site, from the
## intro) stands once in every world, 600-1600 m out from the drop site, its nose (the plan's -Z)
## toward the drop and its swath trailing back the way the lift came; placed last from its own
## stream, off the roads.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")

const WRECK: String = "lift3_crash_site"


func test_config_has_one_unique_crash_entry() -> void:
	assert_eq(GenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json is valid with the crash site")
	var entries: Array = (((GenSettings.tuning().get("wilderness", {}) as Dictionary).get("pool", []) as Array)
		.filter(func(e: Dictionary) -> bool: return str(e.get("site", "")) == "crash"))
	assert_eq(entries.size(), 1)
	if entries.size() == 1:
		assert_eq(str(entries[0]["poi"]), WRECK)
		assert_true(bool(entries[0].get("unique", false)))
	assert_gte(Generator.VERSION, 13)


func test_one_wreck_out_from_the_drop_site_nose_to_it() -> void:
	for seed: int in [7, 21, 1234]:
		var g: RefCounted = Generator.generate(GenSettings.resolve(&"standard", {"size": 4}, seed))
		var wrecks: Array = (g.get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["def"]) == WRECK)
		assert_eq(wrecks.size(), 1, "seed %d: one wreck" % seed)
		if wrecks.is_empty():
			continue
		var w: Dictionary = wrecks[0]
		var drop: Vector2 = (g.get(&"drop") as Dictionary).get("pos", Vector2.ZERO)
		var c: Vector2 = w["center"]
		assert_between(c.distance_to(drop), 580.0, 1620.0, "seed %d: %.0f m from the drop site" % [seed, c.distance_to(drop)])
		# The plan's -Z, turned as the composer turns a placement (Vector2.rotated(rot)).
		var nose: Vector2 = Vector2(0.0, -1.0).rotated(deg_to_rad(float(w["rot"])))
		assert_gt(nose.dot((drop - c).normalized()), 0.99, "seed %d: the nose points at the drop" % seed)
		assert_gte(float(g.call(&"road_clearance", w["poly"])), 10.0, "seed %d: off the roads" % seed)
