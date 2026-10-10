extends GutTest
## Gardens and rain catchers (ADR-0049) through the farm.* commands on real pieces: planting spends
## a seed, watering spends the water and gives the bottle back, a ripe bed is harvested into food
## (a perennial grows back), dead plants are pulled, a catcher fills bottles and buckets and can be
## drunk from, the stand-in visuals follow the state, and a destroyed piece takes its state along.

var _prev: GameSession
var _bm: BuildingManager
var _fm: FarmManager
var _p: PlayerState
var _harvests: Array = []


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 23, "game_mode": "slice"})
	Game.session.clock.season_start_index = 0
	_p = Game.session.local_player()
	_bm = BuildingManager.new()
	add_child_autofree(_bm)
	_bm.set_physics_process(false)
	_fm = FarmManager.new()
	_fm.building = _bm
	add_child_autofree(_fm)
	_harvests.clear()
	Events.crop_harvested.connect(_on_harvest)


func after_each() -> void:
	Events.crop_harvested.disconnect(_on_harvest)
	Game.session = _prev


func _on_harvest(pid: StringName, crop_id: StringName, items: Dictionary) -> void:
	_harvests.append([pid, crop_id, items])


func _spawn(def_id: StringName, id: StringName) -> StructurePiece:
	var def: StructureDef = Content.structure(def_id)
	return _bm._spawn_piece(id, def, Transform3D.IDENTITY, def.hp)


func _args(id: String, extra: Dictionary = {}) -> Dictionary:
	return {"player": String(_p.id), "piece": id}.merged(extra)


func _plants_shown(bed: StructurePiece) -> int:
	var n: int = 0
	for i: int in Farming.plots_of(bed.def):
		if bed.farm_visual.get_node("Plot%d" % i).get_child_count() > 0:
			n += 1
	return n


func test_plant_water_grow_and_harvest_a_bed() -> void:
	var bed: StructurePiece = _spawn(&"garden_bed", &"s:bed")
	assert_not_null(bed.farm_visual, "a bed shows its plots")
	assert_false(bool(_fm._cmd_plant(_args("s:bed"))["ok"]), "nothing to plant")
	_p.inventory.add_item(&"seed_potato", 2)
	_p.inventory.add_item(&"carrot_seeds", 1)
	var xp0: int = _p.progression.xp
	var r: Dictionary = _fm._cmd_plant(_args("s:bed", {"seed": "seed_potato"}))
	assert_true(bool(r["ok"]))
	assert_eq(int(r["plot"]), 0)
	assert_eq(_p.inventory.count_of(&"seed_potato"), 1, "the seed is spent")
	assert_gt(_p.progression.xp, xp0, "planting teaches a little")
	assert_eq(str(_fm._cmd_plant(_args("s:bed"))["crop"]), "carrot", "with nothing held, the first carried seed (crops by id)")
	assert_eq(str(_fm._cmd_plant(_args("s:bed"))["crop"]), "potato")
	assert_eq(_plants_shown(bed), 3, "the stand-ins show what is planted")
	assert_false(bool(_fm._cmd_plant(_args("s:bed", {"seed": "stick"}))["ok"]), "a stick is no seed")
	# Water: a bottle of stream water gives its bottle back; a soaked bed takes no more.
	assert_false(bool(_fm._cmd_water(_args("s:bed"))["ok"]), "no water carried")
	_p.inventory.add_item(&"water_bottle_dirty", 3)
	assert_true(bool(_fm._cmd_water(_args("s:bed"))["ok"]))
	assert_eq(_p.inventory.count_of(&"water_bottle_empty"), 1, "the empty bottle comes back")
	assert_true(bool(_fm._cmd_water(_args("s:bed"))["ok"]))
	assert_false(bool(_fm._cmd_water(_args("s:bed"))["ok"]), "already soaked")
	assert_eq(_p.inventory.count_of(&"water_bottle_dirty"), 1)
	var st: Dictionary = Game.session.world.farms["s:bed"]
	assert_almost_eq(float(st["water"]), Farming.soil_capacity(), 0.001)
	assert_false(bool(_fm._cmd_harvest(_args("s:bed"))["ok"]), "nothing ripe yet")
	# Grow the potatoes to ripe.
	for i: int in [0, 2]:
		st["plots"][i]["grown"] = Farming.crop(&"potato").grow_days
	bed.farm_visual.refresh()
	var h: Dictionary = _fm._cmd_harvest(_args("s:bed"))
	assert_true(bool(h["ok"]))
	assert_eq(int(h["plots"]), 2, "both ripe plots")
	assert_between(_p.inventory.count_of(&"potato"), 6, 10, "3-5 potatoes a plot")
	assert_eq(_harvests.size(), 2, "each plot brought in is an event (directives)")
	assert_eq(_harvests[0][1], &"potato")
	assert_true(Farming.is_empty_plot(st["plots"][0]), "an annual leaves its plot empty")
	assert_false(Farming.is_empty_plot(st["plots"][1]), "the carrots grow on")
	assert_eq(_plants_shown(bed), 1)


func test_a_perennial_grows_back_and_dead_plants_are_pulled() -> void:
	var bed: StructurePiece = _spawn(&"garden_bed", &"s:bed2")
	_p.inventory.add_item(&"huckleberry_seeds", 1)
	_p.inventory.add_item(&"yarrow_seeds", 1)
	assert_true(bool(_fm._cmd_plant(_args("s:bed2", {"seed": "huckleberry_seeds"}))["ok"]))
	assert_true(bool(_fm._cmd_plant(_args("s:bed2", {"seed": "yarrow_seeds"}))["ok"]))
	var st: Dictionary = Game.session.world.farms["s:bed2"]
	var berry: CropDef = Farming.crop(&"huckleberry")
	st["plots"][0]["grown"] = berry.grow_days
	st["plots"][1]["dead"] = true
	assert_true(bool(_fm._cmd_harvest(_args("s:bed2"))["ok"]))
	assert_gt(_p.inventory.count_of(&"huckleberries"), 0)
	assert_false(Farming.is_empty_plot(st["plots"][0]), "the bush stays")
	assert_eq(Farming.stage_of(st["plots"][0]), berry.regrow_stage, "back to its regrow stage")
	var c: Dictionary = _fm._cmd_clear(_args("s:bed2"))
	assert_true(bool(c["ok"]) and int(c["cleared"]) == 1)
	assert_true(Farming.is_empty_plot(st["plots"][1]))
	assert_eq(_p.inventory.count_of(&"plant_fiber"), 1, "what's left is fibre")
	assert_false(bool(_fm._cmd_clear(_args("s:bed2"))["ok"]), "nothing dead now")
	assert_eq(_plants_shown(bed), 1)


func test_a_rain_catcher_fills_from_the_weather_and_fills_bottles() -> void:
	var catcher: StructurePiece = _spawn(&"rain_catcher", &"s:rain")
	assert_not_null(catcher.farm_visual)
	var st: Dictionary = FarmManager.state_of(catcher)
	assert_eq(float(st["water"]), 0.0)
	# The manager ticks it with the session's weather (rain under open sky).
	Game.session.weather.current = &"rain"
	Game.session.weather.target = Game.session.weather.current
	Game.session.weather.blend = 1.0
	var rain: float = float(Game.session.weather.params().get("rain", 0.0))
	assert_gt(rain, 0.0, "a rainy weather state")
	_fm.tick(180.0)
	assert_almost_eq(float(st["water"]), rain * float(Farming.cfg()["catcher"]["fill_per_hour"]) * 3.0, 0.01, "three hours of rain")
	assert_false(catcher.farm_visual._water == null)
	assert_true(catcher.farm_visual._water.visible, "the water shows")
	st["water"] = 6.0
	assert_false(bool(_fm._cmd_draw_water(_args("s:rain"))["ok"]), "nothing to fill")
	_p.inventory.add_item(&"water_bottle_empty", 3)
	_p.inventory.add_item(&"bucket", 1)
	var r: Dictionary = _fm._cmd_draw_water(_args("s:rain"))
	assert_true(bool(r["ok"]))
	assert_eq(_p.inventory.count_of(&"water_bottle_dirty"), 3, "three bottles of murky water")
	assert_eq(_p.inventory.count_of(&"bucket"), 1, "too little left for the bucket")
	assert_almost_eq(float(st["water"]), 3.0, 0.001)
	_p.stats.hydration = 40.0
	assert_true(bool(_fm._cmd_drink(_args("s:rain"))["ok"]))
	assert_gt(_p.stats.hydration, 40.0, "a drink")
	assert_almost_eq(float(st["water"]), 2.0, 0.001)
	# A bucket of it waters a whole bed.
	st["water"] = 10.0
	assert_true(bool(_fm._cmd_draw_water(_args("s:rain"))["ok"]))
	assert_eq(_p.inventory.count_of(&"bucket_water"), 1)
	_spawn(&"garden_bed", &"s:bed3")
	assert_true(bool(_fm._cmd_water(_args("s:bed3", {"item": "bucket_water"}))["ok"]))
	assert_almost_eq(float(Game.session.world.farms["s:bed3"]["water"]), 1.0, 0.001, "soaked")
	assert_eq(_p.inventory.count_of(&"bucket"), 1, "the bucket comes back")


func test_a_roof_keeps_the_rain_off_and_a_destroyed_piece_takes_its_state() -> void:
	var catcher: StructurePiece = _spawn(&"rain_catcher", &"s:rain2")
	FarmManager.state_of(catcher)
	var env: Dictionary = _fm.env_at(catcher, {"rain": 1.0, "snow": 0.0})
	assert_eq(float(env["rain"]), 1.0, "open sky")
	assert_has(env, "season")
	var roof: StructureDef = Content.structure(&"log_piece")
	for z: float in [-0.35, 0.0, 0.35]:
		_bm._add_piece(StringName("s:roof%d" % int(z * 100)), roof, Transform3D(Basis(), Vector3(0, 3.0, z)), 400.0, true)
	for i: int in 3:
		await get_tree().physics_frame
	assert_eq(float(_fm.env_at(catcher, {"rain": 1.0})["rain"]), 0.0, "under a roof it stays dry")
	assert_true(Game.session.world.farms.has("s:rain2"))
	_fm._on_structure_destroyed(&"s:rain2", &"rain_catcher", Vector3.ZERO)
	assert_false(Game.session.world.farms.has("s:rain2"))


func test_farm_prompts_read_the_state() -> void:
	var st: Dictionary = Farming.new_state(Content.structure(&"garden_bed"))
	assert_string_contains(FarmManager.bed_status(st), "empty")
	Farming.plant(st["plots"][0], Farming.crop(&"carrot"))
	st["water"] = 1.0
	assert_string_contains(FarmManager.bed_status(st), "carrots 0%")
	assert_string_contains(FarmManager.bed_status(st), "soil wet")


func test_a_beds_status_shows_under_an_action_prompt() -> void:
	# TD-217: harvest/plant/water prompts once hid growth and soil.
	var st: Dictionary = Farming.new_state(Content.structure(&"garden_bed"))
	Farming.plant(st["plots"][0], Farming.crop(&"carrot"))
	assert_string_contains(FarmManager.hint_for(&"farm.water", st), "carrots 0%")
	assert_string_contains(FarmManager.hint_for(&"farm.harvest", st), "soil dry")
	assert_eq(FarmManager.hint_for(&"", st), "", "the prompt is already the status")
	# The bed's status and "hold [X] to water the bed" share the line under the prompt.
	assert_eq(GameUI.hint_line("Garden bed · soil dry", "hold [X] to water the bed"), "Garden bed · soil dry  ·  hold [X] to water the bed")
	assert_eq(GameUI.hint_line("", "hold [X] to water the bed"), "hold [X] to water the bed")
	assert_eq(GameUI.hint_line("a", ""), "a")
