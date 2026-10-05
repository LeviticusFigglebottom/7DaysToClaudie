extends GutTest
## Lots that pick (ADR-0030, LotPicker): authored picks stand, reserved lots stay empty, lots without
## a pick choose by zoning and tier from the authored pool or a template, deterministically from the
## world seed; Pell's Crossing's residential street fills with generated houses.

const Dressing := preload("res://src/poi/poi_dressing.gd")
const Generator := preload("res://src/poi/building_generator.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")



func _fw(lots: Array, tier_range: Array = [1, 3]) -> FrameworkDef:
	var fw := FrameworkDef.new()
	var errs: PackedStringArray = fw.parse({"id": "test_fw", "size": [200, 200], "tier_range": tier_range, "lots": lots}, &"framework", "test")
	assert_eq(errs, PackedStringArray())
	return fw


func test_picks_and_reserved_lots() -> void:
	var fw: FrameworkDef = _fw([
		{"id": "a", "rect": [0, 0, 26, 26], "zoning": ["residential"], "facing": "S", "pick": "merrow_house"},
		{"id": "b", "rect": [30, 0, 30, 30], "zoning": ["civic"], "facing": "S", "reserved": "school"}])
	var res: Array[Dictionary] = Lots.resolve(fw, "p", 4471)
	assert_eq(str(res[0]["kind"]), "authored")
	assert_eq(String(res[0]["def_id"]), "merrow_house")
	assert_eq(str(res[1]["kind"]), "reserved")
	assert_null(Lots.def_for(res[1]))


func test_lots_without_a_pick_choose_deterministically() -> void:
	var lots: Array = []
	for i: int in 8:
		lots.append({"id": "lot_%d" % i, "rect": [i * 26, 0, 24, 26], "zoning": ["residential"], "facing": "S"})
	var fw: FrameworkDef = _fw(lots)
	var a: Array[Dictionary] = Lots.resolve(fw, "street", 4471)
	var b: Array[Dictionary] = Lots.resolve(fw, "street", 4471)
	var c: Array[Dictionary] = Lots.resolve(fw, "street", 999)
	var sig := func(rs: Array[Dictionary]) -> String:
		var parts: PackedStringArray = []
		for r: Dictionary in rs:
			parts.append("%s:%s:%s:%d" % [r["kind"], r.get("def_id", ""), r.get("template", ""), int(r["seed"])])
		return ",".join(parts)
	assert_eq(sig.call(a), sig.call(b), "same world seed, same lots")
	assert_ne(sig.call(a), sig.call(c), "another run, another street")
	var authored: Dictionary = {}
	for r: Dictionary in a:
		assert_true(str(r["kind"]) in ["authored", "generated"], "every lot holds something")
		if str(r["kind"]) == "authored":
			assert_false(authored.has(r["def_id"]), "an authored building stands once per framework")
			authored[r["def_id"]] = true
			var pd: PoiDef = Content.get_def(&"poi", r["def_id"])
			assert_true(pd.zoning.has("residential"), "zoned for the lot")
			assert_true(pd.footprint.x <= 24 and pd.footprint.y <= 26, "fits the lot")


func test_pool_and_templates_narrow_the_choice() -> void:
	var fw: FrameworkDef = _fw([
		{"id": "gen", "rect": [0, 0, 26, 28], "zoning": ["residential"], "facing": "S", "pool": "generated"},
		{"id": "only", "rect": [30, 0, 26, 28], "zoning": ["residential"], "facing": "E", "templates": ["duplex"]},
		{"id": "authored", "rect": [60, 0, 30, 30], "zoning": ["residential"], "facing": "S", "pool": "authored"}])
	for ws: int in [1, 2, 3, 4, 5]:
		var res: Array[Dictionary] = Lots.resolve(fw, "p", ws)
		assert_eq(str(res[0]["kind"]), "generated")
		assert_eq(str(res[1]["kind"]), "generated")
		assert_eq(String(res[1]["template"]), "duplex")
		assert_eq(Lots.lot_size(res[1]["lot"]), Vector2i(28, 26), "an east-facing lot is seen along its depth")
		assert_eq(str(res[2]["kind"]), "authored")


func test_the_pool_skips_buildings_already_standing() -> void:
	var fw: FrameworkDef = _fw([
		{"id": "m", "rect": [0, 0, 26, 26], "zoning": ["residential"], "facing": "S", "pick": "merrow_house"},
		{"id": "x", "rect": [30, 0, 26, 26], "zoning": ["residential"], "facing": "S", "pool": "authored"}])
	for ws: int in [1, 2, 3, 4, 5, 6]:
		var res: Array[Dictionary] = Lots.resolve(fw, "p", ws)
		assert_ne(String(res[1].get("def_id", "")), "merrow_house", "no second Merrow House in the same town")


func test_generated_lots_build_a_building_that_fits() -> void:
	var fw: FrameworkDef = _fw([{"id": "h", "rect": [10, 10, 24, 27], "zoning": ["residential"], "facing": "N", "pool": "generated"}])
	var res: Array[Dictionary] = Lots.resolve(fw, "p", 4471)
	var pd: PoiDef = Lots.def_for(res[0])
	assert_not_null(pd)
	assert_eq(pd.footprint, Vector2i(24, 27))
	var v: PoiValidator = PoiValidator.validate(pd)
	assert_eq(v.errors, PackedStringArray())
	assert_eq(v.warnings, PackedStringArray())
	var again: PoiDef = Lots.def_for(Lots.resolve(fw, "p", 4471)[0])
	assert_eq(JSON.stringify(pd.layout, "", true), JSON.stringify(again.layout, "", true), "the same lot regenerates the same house")


func test_pell_crossing_has_a_street_of_generated_houses_and_reserved_civic_lots() -> void:
	var fw: FrameworkDef = Content.get_def(&"framework", &"pell_crossing")
	var generated: int = 0
	var reserved: PackedStringArray = []
	var names: Dictionary = {}
	for res: Dictionary in Lots.resolve(fw, "pell_crossing", 4471):
		match str(res["kind"]):
			"generated":
				generated += 1
				var pd: PoiDef = Lots.def_for(res)
				assert_not_null(pd)
				if pd != null:
					names[pd.display_name] = true
					assert_eq(PoiValidator.validate(pd).errors, PackedStringArray(), "%s validates" % res["instance"])
			"reserved":
				reserved.append(str(res["lot"].get("reserved", "")))
			"empty":
				fail_test("lot %s holds nothing" % res["lot"].get("id"))
	assert_between(generated, 6, 10, "a residential street of 6-10 generated houses")
	assert_eq(reserved.size(), 3, "lots held for the school, the fire station and the bank")
	assert_gt(names.size(), generated - 2, "the houses have their own names")


func test_terrain_holes_resolve_lots_like_the_manager() -> void:
	var pl: Dictionary = {"kind": "framework", "def": "pell_crossing", "id": "pell_crossing", "origin": [0.0, 0.0, 0.0], "rotation": 0.0}
	var placed: Array[Dictionary] = TerrainHoles.placed_pois([pl])
	var authored: int = 0
	for res: Dictionary in Lots.resolve(Content.get_def(&"framework", &"pell_crossing"), "pell_crossing", Lots.session_seed()):
		if str(res["kind"]) == "authored":
			authored += 1
	assert_eq(placed.size(), authored, "every authored building is offered to the cellar cut, generated ones have no cellars")
