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
	assert_eq(BuildingManager.dismantle_refund(Content.structure(&"workbench")), {"log": 1, "stick": 3, "cordage": 1, "nails": 6},
		"half, rounded down, of the bigger costs")
	assert_eq(BuildingManager.dismantle_refund(Content.structure(&"can_chime_trap")), {"can_chime": 1},
		"a placed can chime comes back: half of one is not nothing")
	for d: ContentDef in Content.all(&"structure"):
		var sd: StructureDef = d
		for k: Variant in sd.cost.keys():
			if int(sd.cost[k]) > 0 and sd.piece_kind != "log":
				assert_gte(int(BuildingManager.dismantle_refund(sd).get(k, 0)), 1, "%s gives back some %s" % [sd.id, k])


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


## The water shader culls back faces, so a surface wound the wrong way vanishes from above.
func test_water_surfaces_face_up() -> void:
	var ws := WaterSystem.new()
	# Both outline windings, and rivers flowing both ways.
	ws._add_lake({"id": "cw", "level": 2.0, "polygon": [[0.0, 0.0], [30.0, 0.0], [30.0, 20.0], [0.0, 20.0]]})
	ws._add_lake({"id": "ccw", "level": 2.0, "polygon": [[0.0, 0.0], [0.0, 20.0], [30.0, 20.0], [30.0, 0.0]]})
	ws._add_river_piece({"id": "south", "points": [[0.0, 0.0], [0.0, 40.0], [10.0, 80.0]], "widths": [8.0, 8.0, 8.0], "levels": [1.0, 1.0, 1.0]})
	ws._add_river_piece({"id": "west", "points": [[0.0, 0.0], [-40.0, 5.0]], "widths": [8.0, 8.0], "levels": [1.0, 1.0]})
	assert_eq(ws.get_child_count(), 4)
	for mi: Node in ws.get_children():
		var faces: PackedVector3Array = ((mi as MeshInstance3D).mesh as ArrayMesh).get_faces()
		assert_gt(faces.size(), 0, "%s has triangles" % mi.name)
		var down: int = 0
		for i: int in range(0, faces.size(), 3):
			# Plane(a, b, c) takes Godot's clockwise front-face convention.
			if Plane(faces[i], faces[i + 1], faces[i + 2]).normal.y < 0.99:
				down += 1
		assert_eq(down, 0, "every %s triangle faces up" % mi.name)
	ws.free()


func test_far_canopy_from_biome_trees() -> void:
	var canopy: Dictionary = TerrainManager.far_canopy(Content)
	var conifer: Vector2 = canopy["conifer_forest"]
	var birch: Vector2 = canopy["birch_grove"]
	assert_gt(conifer.x, 0.9, "conifer forest: a closed, tall canopy")
	assert_lt(conifer.y, 0.2, "mostly evergreen")
	assert_between(birch.x, 0.4, conifer.x - 0.1, "birch groves are closed but lower")
	assert_gt(birch.y, 0.7, "birch groves are mostly deciduous")
	assert_lt((canopy["meadow"] as Vector2).x, 0.1, "meadows stay open")
	# The shader's per-vertex decode (terrain_far.gdshader) recovers both values.
	for c: Vector2 in [Vector2(0.0, 0.0), Vector2(1.0, 1.0), Vector2(0.4, 0.8667), Vector2(0.0667, 0.0)]:
		var packed: float = roundf(TerrainManager.pack_canopy(c.x, c.y) * 255.0)
		assert_almost_eq(floorf(packed / 16.0) / 15.0, c.x, 0.034, "cover %s" % c)
		assert_almost_eq(fmod(packed, 16.0) / 15.0, c.y, 0.034, "deciduous %s" % c)


func _env() -> Dictionary:
	return {"ambient_c": 18.0, "wind": 0.1, "raining": false, "sheltered": false, "fire_warmth": 0.0, "sleeping": false, "exertion": 0.0}


## Ten game hours with food and water topped up (only the infection should change).
func _ten_hours(s: SurvivalStats) -> void:
	for i: int in 10:
		s.fullness = 100.0
		s.hydration = 100.0
		s.rest = 100.0
		s.tick_game(60.0, _env())


func test_a_bite_fades_but_a_mauling_grows() -> void:
	var s := SurvivalStats.new()
	s.add_wound(0.0, 5.0)
	_ten_hours(s)
	assert_eq(s.infection, 0.0, "one bite is fought off within hours")
	s.add_wound(0.0, 20.0)
	_ten_hours(s)
	assert_true(s.alive)
	assert_gt(s.infection, 20.0, "four bites' worth keeps growing until treated")
	s.consume(Content.item(&"antifungal"))
	assert_lt(s.infection, 12.0, "antifungals bring it back under the dormant line")


func test_bleeding_lasts_long_enough_to_matter() -> void:
	var s := SurvivalStats.new()
	s.add_wound(0.6, 0.0)
	var hp: float = s.health
	s.tick_game(30.0, _env())
	assert_gt(s.bleeding, 0.0, "four wounds still bleed half an hour later")
	assert_lt(s.health, hp - 15.0, "and it has cost real health")


func test_crafting_xp_follows_the_recipe() -> void:
	var pr := Progression.new()
	assert_true(pr.has_xp_source("craft_tools"))
	assert_gt(int(Content.config(&"progression")["xp"]["craft_tools"]), int(Content.config(&"progression")["xp"]["craft_materials"]),
		"a stone axe teaches more than cordage")
	assert_eq(int(Content.config(&"progression")["xp"]["dig"]), 0, "unlimited digging pays nothing")


func test_repair_kit_restores_the_most_worn_tool() -> void:
	var prev: GameSession = Game.session
	var s: GameSession = GameSession.create_new({"seed": 7, "game_mode": "slice"})
	Game.session = s
	var p: PlayerState = s.local_player()
	p.inventory.add_item(&"stone_axe", 1, 2)
	p.inventory.add_item(&"repair_kit", 1)
	var axe: ItemStack = p.inventory.first(&"stone_axe")
	var full: float = axe.durability
	axe.durability = 3.0
	var pa := PlayerActions.new()
	var res: Dictionary = pa._repair({"player": String(p.id), "item": "repair_kit"})
	assert_true(bool(res["ok"]))
	assert_almost_eq(axe.durability, full, 0.001, "back to its quality's full durability")
	assert_false(p.inventory.has(&"repair_kit"), "the kit is spent")
	assert_false(bool(pa._repair({"player": String(p.id), "item": "repair_kit"})["ok"]), "no kit left")
	pa.free()
	Game.session = prev


## Drinking says what it did (first-hour audit #25): the real gain, capped at full.
func test_drinking_says_how_much_water() -> void:
	var prev: GameSession = Game.session
	var s: GameSession = GameSession.create_new({"seed": 7, "game_mode": "slice"})
	Game.session = s
	var p: PlayerState = s.local_player()
	p.inventory.add_item(&"water_bottle_clean", 2)
	p.stats.hydration = 40.0
	var gain: int = roundi(float(Content.item(&"water_bottle_clean").consume.get("hydration", 0.0)))
	var said: Array[String] = []
	var on_msg := func(text: String, _k: StringName) -> void: said.append(text)
	Events.player_status_message.connect(on_msg)
	var pa := PlayerActions.new()
	assert_true(bool(pa._consume({"item": "water_bottle_clean"})["ok"]))
	assert_eq(said, ["You drink. (Water +%d)" % gain] as Array[String])
	p.stats.hydration = 95.0
	pa._consume({"item": "water_bottle_clean"})
	assert_eq(said[-1], "You drink. (Water +5)", "the real amount: it stops at full")
	assert_eq(PlayerActions.drink_line(18, -3), "You drink. (Water +18, Health -3)", "stream water's cost is said")
	Events.player_status_message.disconnect(on_msg)
	pa.free()
	Game.session = prev


func test_weather_lengths_vary_and_snow_lingers() -> void:
	var ws := WeatherState.new()
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var lengths: Dictionary = {}
	for i: int in 12:
		ws._start(&"rain", rng.randf())
		lengths[int(ws.minutes_left)] = true
	assert_gt(lengths.size(), 3, "rain does not always last exactly the same")
	ws.force(&"snow")
	for i: int in 8:
		ws.tick(30.0, "winter", rng)
	assert_gt(ws.snow_cover, 0.5, "snow settles while it falls")
	ws.force(&"clear")
	for i: int in 8:
		ws.tick(30.0, "winter", rng)
	assert_gt(float(ws.params()["snow_cover"]), 0.35, "and stays on the ground in winter after it stops")
	var back := WeatherState.new()
	back.from_dict(ws.to_dict())
	assert_almost_eq(back.snow_cover, ws.snow_cover, 0.0001, "saved")
	var wind: float = float(ws.params()["wind"])
	assert_true(wind >= 0.0 and wind <= 1.0)
