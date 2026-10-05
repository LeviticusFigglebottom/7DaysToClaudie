extends GutTest
## Generated ordinary buildings (ADR-0030, BuildingGenerator): every template makes valid buildings
## (no validator errors or warnings) across many seeds, the same seed always makes the same
## building, a street of twelve seeds makes twelve different ones, and they fit their lots.

const Dressing := preload("res://src/poi/poi_dressing.gd")
const Generator := preload("res://src/poi/building_generator.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")


const SEEDS: int = 50


func _templates() -> Array:
	var out: Array = Content.all(&"building_template")
	assert_gt(out.size(), 5, "at least six templates (bungalow, two-storey, cape cod, duplex, corner store, workshop)")
	return out


func _signature(pd: PoiDef) -> String:
	return JSON.stringify(pd.layout, "", true)


func test_every_template_makes_valid_buildings_across_many_seeds() -> void:
	for t: TemplateDef in _templates():
		var bad: PackedStringArray = []
		for i: int in SEEDS:
			var seed: int = Ids.hash64("gen_test:%s:%d" % [t.id, i])
			var pd: PoiDef = Generator.generate(t, seed)
			if pd == null:
				bad.append("seed %d: nothing generated" % i)
				continue
			var v: PoiValidator = PoiValidator.validate(pd)
			for e: String in v.errors:
				bad.append("seed %d: ERROR %s" % [i, e])
			for w: String in v.warnings:
				bad.append("seed %d: warn %s" % [i, w])
			assert_eq(String(pd.template), String(t.id))
			assert_true(pd.tier == t.tier, "tier from the template")
		assert_eq(bad, PackedStringArray(), "%s: %d seeds validate clean" % [t.id, SEEDS])


func test_same_seed_same_building() -> void:
	for t: TemplateDef in _templates():
		var a: PoiDef = Generator.generate(t, 777)
		var b: PoiDef = Generator.generate(t, 777)
		assert_eq(_signature(a), _signature(b), "%s is deterministic" % t.id)
		assert_eq(a.display_name, b.display_name)


func test_a_street_of_twelve_is_twelve_different_houses() -> void:
	for t: TemplateDef in _templates():
		var plans: Dictionary = {}
		var looks: Dictionary = {}
		for i: int in 12:
			var pd: PoiDef = Generator.generate(t, 1000 + i)
			plans[JSON.stringify(pd.layout["levels"])] = true
			var st: Dictionary = pd.layout["style"]
			looks[JSON.stringify([pd.layout["levels"], st.get("exterior"), st.get("roof"), st.get("porch", {})])] = true
		assert_gt(plans.size(), 8, "%s: most of twelve seeds give their own plan (%d)" % [t.id, plans.size()])
		assert_eq(looks.size(), 12, "%s: twelve seeds, twelve different buildings" % t.id)


func test_buildings_fit_their_lot() -> void:
	for t: TemplateDef in _templates():
		for lot: Vector2i in [Vector2i(22, 24), Vector2i(26, 28), Vector2i(t.width.x + 6, t.depth.x + t.setback.x + 4)]:
			if not Generator.fits(t, lot):
				continue
			var pd: PoiDef = Generator.generate(t, 5150, lot)
			assert_not_null(pd, "%s fits %s" % [t.id, lot])
			if pd == null:
				continue
			assert_eq(pd.footprint, lot, "%s fills the lot it was made for" % t.id)
			var v: PoiValidator = PoiValidator.validate(pd)
			assert_eq(v.errors, PackedStringArray(), "%s in a %s lot validates" % [t.id, lot])
	assert_false(Generator.fits(Content.get_def(&"building_template", &"bungalow"), Vector2i(8, 8)), "a tiny lot fits no bungalow")


func test_generated_buildings_have_the_dungeon_lite_beats() -> void:
	for t: TemplateDef in _templates():
		var pd: PoiDef = Generator.generate(t, 31337)
		var lay: Dictionary = pd.layout
		var bolted: int = 0
		for op: Dictionary in lay["openings"]:
			if str(op.get("state", "")) == "locked_inside":
				bolted += 1
		assert_gt(bolted, 0, "%s: a bolted way out" % t.id)
		assert_eq((lay["shortcuts"] as Array).size(), 1, "%s: one shortcut" % t.id)
		assert_between((lay["sleepers"] as Array).size(), t.sleepers.x, t.sleepers.y, "%s: a few sleepers" % t.id)
		assert_gt((lay["triggers"] as Array).size(), 0, "%s: an ambush" % t.id)
		assert_lt((lay["traps"] as Array).size(), 2, "%s: at most one gentle trap" % t.id)
		assert_gt((lay["route"] as Array).size(), 4, "%s: a route with beats" % t.id)
		assert_true(pd.display_name != "" and pd.story != "", "%s: named, with a story" % t.id)


func test_generated_buildings_build() -> void:
	for t: TemplateDef in _templates():
		var pd: PoiDef = Generator.generate(t, 2024)
		var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), StringName("test/gen_%s" % t.id))
		assert_not_null(inst.shell, "%s builds" % t.id)
		assert_gt(inst.shell.get_child_count(), 10, "%s has a collision shell" % t.id)
		inst.free()


func test_two_storey_houses_have_stairs_and_an_upstairs() -> void:
	for id: StringName in [&"two_storey", &"cape_cod"]:
		var t: TemplateDef = Content.get_def(&"building_template", id)
		for i: int in 5:
			var pd: PoiDef = Generator.generate(t, 40 + i)
			assert_eq((pd.layout["levels"] as Array).size(), 2, "%s: two storeys" % id)
			assert_eq((pd.layout["stairs"] as Array).size(), 1, "%s: a flight" % id)
			if id == &"cape_cod":
				var up: Array = (pd.layout["levels"] as Array)[1]["plan"]
				assert_true(str(up.back()).replace(".", "") == "", "cape cod: the upper floor is set back from the front")
