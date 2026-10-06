extends GutTest
## Gardens and rain catchers (ADR-0049), the rules alone (Farming): plants grow only in wet soil,
## by season and temperature and the crop_growth setting; dry soil wilts and kills them, frost hurts
## the tender ones; rain soaks a bed under open sky and fills a catcher; the state saves and an
## older save without it loads empty.

const SLOT: String = "unit_test_farming"
const SPRING: Dictionary = {"ambient_c": 18.0, "rain": 0.0, "season": "spring", "growth": 1.0}


func after_each() -> void:
	SaveSystem.delete_slot(SLOT)


func _bed() -> Dictionary:
	return Farming.new_state(Content.structure(&"garden_bed"))


func _planted(crop_id: StringName, water: float = 1.0) -> Dictionary:
	var st: Dictionary = _bed()
	Farming.plant(st["plots"][0], Content.get_def(&"crop", crop_id) as CropDef)
	st["water"] = water
	return st


## Ticks `days` of weather in 10-minute steps, topping the soil up first thing every morning when
## `keep_wet`.
func _days(st: Dictionary, days: float, env: Dictionary, keep_wet: bool) -> void:
	var minutes: float = days * Farming.DAY_MIN
	var t: float = 0.0
	while t < minutes - 0.001:
		if keep_wet and fmod(t, Farming.DAY_MIN) < 0.001:
			st["water"] = Farming.soil_capacity()
		var step: float = minf(10.0, minutes - t)
		Farming.tick_bed(st, step, env)
		t += step


func test_content_is_wired() -> void:
	assert_eq(Farming.plots_of(Content.structure(&"garden_bed")), 4)
	assert_eq(Farming.catcher_capacity(Content.structure(&"rain_catcher")), 24.0)
	assert_false(Farming.is_farm(Content.structure(&"campfire")))
	assert_eq(Farming.crop_for_seed(&"seed_potato").id, &"potato")
	assert_eq(Farming.crop_for_seed(&"potato").id, &"potato", "a potato is its own seed")
	assert_eq(Farming.crop_for_seed(&"carrot_seeds").id, &"carrot")
	assert_null(Farming.crop_for_seed(&"stick"))
	for c: CropDef in Content.all(&"crop"):
		for s: String in c.seeds:
			assert_true(Content.item(StringName(s)) != null, "%s seed %s is an item" % [c.id, s])
	assert_true(Content.get_def(&"blueprint", &"garden_bed") != null and Content.get_def(&"blueprint", &"rain_catcher") != null)
	assert_true(GameRules.options().has("crop_growth"), "a world setting scales growth")


func test_a_watered_crop_grows_through_its_stages_to_ripe() -> void:
	var st: Dictionary = _planted(&"potato")
	var plot: Dictionary = st["plots"][0]
	var c: CropDef = Farming.crop(&"potato")
	assert_eq(Farming.stage_of(plot), 0, "a seedling")
	var seen: Array[int] = [0]
	for d: int in int(c.grow_days) + 1:
		_days(st, 1.0, SPRING, true)
		if not seen.has(Farming.stage_of(plot)):
			seen.append(Farming.stage_of(plot))
	assert_true(Farming.is_ripe(plot), "ripe after its grow days of good growth")
	assert_eq(seen, [0, 1, 2, 3] as Array[int], "every stage in order, the last one ripe")
	assert_almost_eq(float(plot["health"]), 1.0, 0.01, "a watered plant stays healthy")


func test_growth_takes_the_grow_days_in_good_weather() -> void:
	var c: CropDef = Farming.crop(&"potato")
	var st: Dictionary = _planted(&"potato")
	_days(st, c.grow_days - 0.5, SPRING, true)
	assert_false(Farming.is_ripe(st["plots"][0]), "not before")
	_days(st, 0.6, SPRING, true)
	assert_true(Farming.is_ripe(st["plots"][0]), "and on time")


func test_season_temperature_and_the_world_setting_scale_growth() -> void:
	var c: CropDef = Farming.crop(&"potato")
	assert_eq(Farming.season_mult(c, "winter"), 0.0, "nothing grows in winter")
	assert_almost_eq(Farming.season_mult(c, "autumn"), 0.7, 0.001, "the crop's own season overrides the config's")
	assert_almost_eq(Farming.season_mult(Farming.crop(&"yarrow"), "summer"), float(Farming.cfg()["seasons"]["summer"]), 0.001)
	assert_eq(Farming.temp_factor(c, c.min_temp_c - 1.0), 0.0, "too cold to grow")
	assert_eq(Farming.temp_factor(c, 20.0), 1.0)
	assert_lt(Farming.temp_factor(c, 9.0), 1.0, "slower when cool")
	var slow: Dictionary = _planted(&"potato")
	var fast: Dictionary = _planted(&"potato")
	var winter: Dictionary = _planted(&"potato")
	_days(slow, 1.0, SPRING, true)
	_days(fast, 1.0, SPRING.merged({"growth": 2.0}, true), true)
	_days(winter, 1.0, SPRING.merged({"season": "winter"}, true), true)
	assert_almost_eq(float(fast["plots"][0]["grown"]), 2.0 * float(slow["plots"][0]["grown"]), 0.01, "crop_growth 2 doubles it")
	assert_eq(float(winter["plots"][0]["grown"]), 0.0)


func test_dry_soil_wilts_then_kills_and_nothing_grows() -> void:
	var c: CropDef = Farming.crop(&"potato")
	var st: Dictionary = _planted(&"potato", 0.0)
	var plot: Dictionary = st["plots"][0]
	_days(st, c.wilt_days * 0.6, SPRING, false)
	assert_true(Farming.is_wilted(plot), "wilting")
	assert_false(Farming.is_dead(plot))
	assert_eq(float(plot["grown"]), 0.0, "no water, no growth")
	# Watered in time it recovers.
	var saved: Dictionary = st.duplicate(true)
	_days(saved, 1.0, SPRING, true)
	assert_false(Farming.is_wilted(saved["plots"][0]), "watered, it perks up")
	_days(st, c.wilt_days * 0.5, SPRING, false)
	assert_true(Farming.is_dead(plot), "dead after its wilt days")
	assert_true(Farming.signature(st).contains("x"), "shows dead")


func test_a_soaked_bed_dries_over_days_faster_when_hot_and_planted() -> void:
	var bare: Dictionary = _bed()
	var planted: Dictionary = _planted(&"carrot")
	var hot: Dictionary = _planted(&"carrot")
	for st: Dictionary in [bare, planted, hot]:
		st["water"] = 1.0
	Farming.tick_bed(bare, 600.0, SPRING)
	Farming.tick_bed(planted, 600.0, SPRING)
	Farming.tick_bed(hot, 600.0, SPRING.merged({"ambient_c": 32.0}, true))
	assert_lt(float(bare["water"]), 1.0)
	assert_lt(float(planted["water"]), float(bare["water"]), "plants drink")
	assert_lt(float(hot["water"]), float(planted["water"]), "heat dries it")


func test_rain_soaks_a_bed_under_open_sky_only() -> void:
	var open: Dictionary = _planted(&"carrot", 0.0)
	var roofed: Dictionary = _planted(&"carrot", 0.0)
	Farming.tick_bed(open, 120.0, SPRING.merged({"rain": 1.0}, true))
	Farming.tick_bed(roofed, 120.0, SPRING)
	assert_gt(float(open["water"]), 0.8, "two hours of hard rain soak it")
	assert_eq(float(roofed["water"]), 0.0)
	assert_gt(float(open["plots"][0]["grown"]), 0.0, "and it grows while it rains")


func test_frost_kills_tender_crops_not_hardy_ones() -> void:
	var cold: Dictionary = SPRING.merged({"ambient_c": -3.0}, true)
	var beans: Dictionary = _planted(&"pole_beans")
	var berry: Dictionary = _planted(&"huckleberry")
	_days(beans, 1.2, cold, true)
	_days(berry, 1.2, cold, true)
	assert_true(Farming.is_dead(beans["plots"][0]), "beans die in a frost")
	assert_false(Farming.is_dead(berry["plots"][0]), "a huckleberry bush shrugs it off")


func test_a_catcher_fills_with_rain_up_to_its_capacity() -> void:
	var def: StructureDef = Content.structure(&"rain_catcher")
	var cap: float = Farming.catcher_capacity(def)
	var st: Dictionary = Farming.new_state(def)
	var per_hour: float = float(Farming.cfg()["catcher"]["fill_per_hour"])
	assert_false(Farming.tick_catcher(st, 60.0, {"rain": 0.0, "snow": 0.0}, cap), "dry weather: nothing")
	assert_eq(float(st["water"]), 0.0)
	assert_true(Farming.tick_catcher(st, 60.0, {"rain": 1.0}, cap), "a level changed")
	assert_almost_eq(float(st["water"]), per_hour, 0.001, "an hour of hard rain")
	Farming.tick_catcher(st, 120.0, {"rain": 0.5}, cap)
	assert_almost_eq(float(st["water"]), per_hour * 2.0, 0.001, "light rain fills it slower")
	var snowy: Dictionary = Farming.new_state(def)
	Farming.tick_catcher(snowy, 60.0, {"snow": 1.0}, cap)
	assert_between(float(snowy["water"]), 0.01, per_hour, "snow, a little")
	Farming.tick_catcher(st, 60.0 * 100.0, {"rain": 1.0}, cap)
	assert_eq(float(st["water"]), cap, "never over the brim")


func test_farms_save_and_older_saves_load_without_them() -> void:
	var s: GameSession = GameSession.create_new({"seed": 77, "game_mode": "slice"})
	var st: Dictionary = _planted(&"potato", 0.5)
	_days(st, 1.0, SPRING, false)
	s.world.farms["s:000009"] = st
	s.world.farms["s:000010"] = {"kind": "catcher", "water": 7.5}
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var back: GameSession = SaveSystem.load_session(SLOT)
	assert_not_null(back)
	assert_eq(JSON.stringify(back.world.farms, "", true), JSON.stringify(JSON.parse_string(JSON.stringify(s.world.farms)), "", true))
	var plot: Dictionary = back.world.farms["s:000009"]["plots"][0]
	assert_eq(str(plot["crop"]), "potato")
	assert_almost_eq(float(plot["grown"]), float(st["plots"][0]["grown"]), 0.0001)
	var old := WorldState.new()
	var d: Dictionary = s.world.to_dict()
	d.erase("farms")
	old.from_dict(d)
	assert_eq(old.farms, {}, "a save from before gardens loads with none")
