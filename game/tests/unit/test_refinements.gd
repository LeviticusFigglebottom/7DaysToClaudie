extends GutTest
## Second refinement pass: exact-stack removal, blueprint slots after a JSON load, repair and
## dismantle costs, fire fuel, POI piece health and the river lookup grid.


func test_take_keeps_quality_and_takes_the_worst_first() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stone_axe", 1, 4)
	inv.add_item(&"stone_axe", 1, 1)
	var out: Array[ItemStack] = inv.take(&"stone_axe", 1)
	assert_eq(out.size(), 1)
	assert_eq(out[0].quality, 1, "the scrap axe leaves, quality intact")
	assert_eq(inv.count_of(&"stone_axe"), 1)
	assert_eq(inv.first(&"stone_axe").quality, 4, "the good one stays")
	assert_true(inv.take(&"stone_axe", 2).is_empty(), "all-or-nothing")
	assert_eq(inv.count_of(&"stone_axe"), 1)


func test_take_spans_stacks() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stick", 25)
	var out: Array[ItemStack] = inv.take(&"stick", 22)
	var n: int = 0
	for s: ItemStack in out:
		n += s.count
	assert_eq(n, 22)
	assert_eq(inv.count_of(&"stick"), 3)


func test_blueprint_slots_survive_json_numbers() -> void:
	var bp: BlueprintDef = null
	for d: ContentDef in Content.all(&"blueprint"):
		if (d as BlueprintDef).mode == "pieces":
			bp = d
			break
	assert_not_null(bp, "a pieces blueprint exists")
	var site := BlueprintSite.new()
	site.setup(&"bp:test", bp, null, {}, JSON.parse_string("[0, 2, 2]"))
	assert_true(site.placed.has(0) and site.placed.has(2), "float slot ids from JSON match int slots")
	assert_eq(site.placed.size(), 2, "duplicates dropped")
	site.free()


func test_repair_costs_something_for_every_piece() -> void:
	for d: ContentDef in Content.all(&"structure"):
		var sd: StructureDef = d
		if sd.cost.is_empty():
			continue
		assert_false(BuildingManager.repair_cost(sd).is_empty(), "%s: repairs are not free" % sd.id)
	var fire: StructureDef = Content.structure(&"campfire")
	assert_eq(BuildingManager.repair_cost(fire), {"stone": 2, "stick": 1}, "a quarter of the build cost, rounded up")
	var log_def: StructureDef = Content.structure(&"log_piece")
	assert_eq(BuildingManager.repair_cost(log_def), log_def.repair["cost"], "an explicit repair cost wins")


func test_dismantle_refunds_half_and_logs_whole() -> void:
	assert_eq(BuildingManager.dismantle_refund(Content.structure(&"log_piece")), {"log": 1})
	assert_eq(BuildingManager.dismantle_refund(Content.structure(&"campfire")), {"stone": 3, "stick": 2})


func test_fire_fuel_data_and_text() -> void:
	var st: StationDef = Content.get_def(&"station", &"campfire") as StationDef
	assert_true(st.needs_fuel)
	assert_gt(st.start_fuel, 0.0, "a new campfire holds its kindling")
	assert_gt(st.max_fuel, st.start_fuel)
	var log_item: ItemDef = Content.item(&"log")
	assert_gt(BuildingManager.fuel_minutes(log_item), BuildingManager.fuel_minutes(Content.item(&"stick")), "a log outlasts a stick")
	assert_eq(StructurePiece.fuel_text(130.0), "2h 10m")
	assert_eq(StructurePiece.fuel_text(12.4), "12m")


func test_poi_piece_health_round_trip() -> void:
	var inst := PoiInstance.new()
	inst.state = {"visited": false, "cleared": false, "dead": [], "broken": [], "doors": {}, "traps": {}}
	assert_eq(inst.piece_hp("front_door", 380.0), 380.0, "untouched pieces have their full health")
	inst.set_piece_hp("front_door", 120.25)
	assert_almost_eq(inst.piece_hp("front_door", 380.0), 120.3, 0.01)
	assert_true(JSON.stringify(inst.state).contains("front_door"), "kept in the saved POI state")
	inst.free()


func test_river_grid_lookup() -> void:
	var ws := WaterSystem.new()
	ws._add_river_piece({"id": "r", "points": [[0.0, 0.0], [40.0, 0.0], [80.0, 30.0]], "widths": [10.0, 10.0, 6.0], "levels": [5.0, 4.5, 4.0]})
	assert_eq(ws.water_level_at(20.0, 2.0), 5.0, "inside the first reach")
	assert_eq(ws.water_level_at(60.0, 15.0), 4.5, "inside the second reach")
	assert_eq(ws.water_level_at(20.0, 9.0), -INF, "on the bank")
	assert_eq(ws.water_level_at(500.0, 500.0), -INF, "far away")
	ws.free()
