extends GutTest
## The Corvane Larkspur Adit (ADR-0044): the caves' entrance in D6. A mine office over two buried
## levels (a timbered drift; a stope that broke into a limestone cave). It validates clean in every
## dressing; only the shaft under the building cuts the ground, the drift and the cave lie under it
## with floors the fell-through checks find; the route goes down both levels and back; both keys
## are found in the building; the Hollowed down there see as at night; and Larch Hollow places it
## at the foot of the Larkspur cliffs.

const ID := &"corvane_larkspur_adit"


func _def() -> PoiDef:
	return Content.get_def(&"poi", ID) as PoiDef


func test_validates_clean_in_every_dressing() -> void:
	var v: PoiValidator = PoiValidator.validate(_def())
	assert_eq(v.errors, PackedStringArray())
	assert_eq(v.warnings, PackedStringArray())
	assert_gt(int(v.stats.get("variants", 0)), 8, "it varies between runs")


func test_its_mine_levels_are_buried() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_true(bool((l.levels[-1] as Dictionary)["buried"]))
	assert_true(bool((l.levels[-2] as Dictionary)["buried"]))
	var th := TerrainHoles.new()
	th.add_poi(_def(), &"t/adit", Transform3D.IDENTITY)
	assert_true(th.has_buried())
	# The shaft station under the shaft house cuts the ground; the drift 30 m west does not.
	var shaft: Vector3 = l.cell_center(-1, Vector2i(15, 8))
	var drift: Vector3 = l.cell_center(-1, Vector2i(40, 8))
	assert_true(th.contains(shaft.x, shaft.z), "the shaft is cut")
	assert_false(th.contains(drift.x, drift.z), "the ground stays whole over the drift")
	assert_almost_eq(th.buried_floor(drift.x, drift.z, l.level_y(-1) + 1.0), l.level_y(-1), 1e-4)
	var cave: Vector3 = l.cell_center(-2, Vector2i(60, 3))
	assert_almost_eq(th.buried_floor(cave.x, cave.z, l.level_y(-2) + 1.0), l.level_y(-2), 1e-4)


func test_the_route_goes_down_and_back() -> void:
	var levels: Dictionary = {}
	for w: Variant in _def().layout.get("route", []):
		levels[int((w as Dictionary).get("level", 0))] = true
	assert_true(levels.has(-1) and levels.has(-2), "both mine levels are on the route")
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(str(l.loot_room.get("room", "")), "G", "the grotto is the loot room")
	assert_eq(int(l.loot_room.get("level", 0)), -2)
	var keys: Dictionary = {}
	for pk: Dictionary in l.pickups:
		keys[str(pk.get("item", ""))] = true
	assert_true(keys.has("corvane_magazine_key") and keys.has("corvane_winze_key"), "both keys are in the building")


func test_larch_hollow_places_it_by_the_sealed_cave() -> void:
	var region: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://world/main_map/regions/d6_larch_hollow/region.json"))
	var adit: Dictionary = {}
	var cave: Dictionary = {}
	for f: Variant in region["features"]:
		if str((f as Dictionary).get("id", "")) == "corvane_larkspur_adit":
			adit = f
		elif str((f as Dictionary).get("id", "")) == "larkspur_sealed_cave":
			cave = f
	assert_false(adit.is_empty(), "the adit is a D6 feature")
	var o: Array = adit["origin"]
	var c: Array = cave["pos"]
	assert_lt(Vector2(float(o[0]), float(o[1])).distance_to(Vector2(float(c[0]), float(c[1]))), 60.0, "at the sealed cave")
	var size: Array = adit["size"]
	assert_lt(float(size[0]) * float(size[1]), float(_def().footprint.x * _def().footprint.y) * 0.5,
		"the pad levels only the surface buildings, not the cliff over the drift")
