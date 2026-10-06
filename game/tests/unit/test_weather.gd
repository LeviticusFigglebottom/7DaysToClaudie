extends GutTest
## Weather logic (ADR-0033): wetness ramps and drying, standing water that lags the rain, snow,
## gusts, lightning that is a pure function of seed and clock, and thunder at the speed of sound.

const CFG: Dictionary = {
	"wetness": {"wet_minutes": 30.0, "dry_minutes": 170.0, "sun_dry": 1.6, "wind_dry": 0.8, "puddle_after": 0.55,
		"puddle_fill_minutes": 70.0, "puddle_dry_minutes": 420.0},
	"snow": {"build_minutes": 120.0, "melt_minutes": 300.0, "melt_minutes_winter": 2400.0, "rain_melt_minutes": 90.0},
}
const LCFG: Dictionary = {"slot_minutes": 0.5, "distance_m": [350.0, 9000.0], "strokes": [1, 4], "stroke_gap_s": [0.05, 0.18],
	"flash_s": 0.11, "speed_of_sound": 343.0}


func _state() -> WeatherState:
	var ws := WeatherState.new()
	ws.cfg = CFG
	return ws


func _run(ws: WeatherState, minutes: float, p: Dictionary, step: float = 1.0) -> void:
	var t: float = 0.0
	while t < minutes:
		ws.weather_minutes(step, "autumn", p)
		t += step


func test_wetness_ramps_in_rain_and_dries_slowly() -> void:
	var ws := _state()
	var rain: Dictionary = {"rain": 1.0, "wind": 0.3, "snow": 0.0}
	_run(ws, 10.0, rain)
	assert_almost_eq(ws.wetness, 10.0 / 30.0, 0.02, "soaks at rain / wet_minutes")
	_run(ws, 30.0, rain)
	assert_eq(ws.wetness, 1.0, "soaked after half an hour of heavy rain")
	var light := _state()
	_run(light, 20.0, {"rain": 0.3, "wind": 0.3, "snow": 0.0})
	assert_lt(light.wetness, 0.25, "light rain soaks slowly")
	# Drying takes hours, not minutes, and runs faster in sun than in grey still air.
	var grey := _state()
	grey.wetness = 1.0
	grey.daylight = 0.0
	_run(grey, 60.0, {"rain": 0.0, "wind": 0.0, "snow": 0.0})
	var sunny := _state()
	sunny.wetness = 1.0
	sunny.daylight = 1.0
	_run(sunny, 60.0, {"rain": 0.0, "wind": 0.0, "snow": 0.0})
	assert_gt(grey.wetness, 0.6, "an hour of still overcast air leaves things wet")
	assert_lt(sunny.wetness, grey.wetness - 0.15, "the sun dries faster")
	var windy := _state()
	windy.wetness = 1.0
	windy.daylight = 0.0
	_run(windy, 60.0, {"rain": 0.0, "wind": 1.0, "snow": 0.0})
	assert_lt(windy.wetness, grey.wetness, "and so does the wind")


func test_puddles_lag_the_rain_and_linger() -> void:
	var ws := _state()
	var rain: Dictionary = {"rain": 1.0, "wind": 0.3, "snow": 0.0}
	_run(ws, 15.0, rain)
	assert_eq(ws.puddles, 0.0, "no standing water until the ground is soaked")
	_run(ws, 60.0, rain)
	assert_gt(ws.puddles, 0.4, "puddles fill once it is")
	var level: float = ws.puddles
	var wet: float = ws.wetness
	ws.daylight = 0.3
	_run(ws, 120.0, {"rain": 0.0, "wind": 0.2, "snow": 0.0})
	assert_gt(ws.puddles, level * 0.4, "puddles outlast the rain by hours")
	assert_lt(ws.wetness, wet, "while surfaces dry")
	assert_gt(ws.puddles, ws.wetness * 0.5, "standing water dries slower than the surfaces round it")
	_run(ws, 1200.0, {"rain": 0.0, "wind": 0.2, "snow": 0.0}, 5.0)
	assert_eq(ws.puddles, 0.0, "and are gone within a dry day")


func test_snow_builds_and_rain_washes_it() -> void:
	var ws := _state()
	_run(ws, 60.0, {"rain": 0.0, "wind": 0.3, "snow": 1.0})
	assert_almost_eq(ws.snow_cover, 0.5, 0.02, "an hour of heavy snow")
	var winter: float = ws.snow_cover
	ws.weather_minutes(60.0, "winter", {"rain": 0.0, "wind": 0.3, "snow": 0.0})
	assert_gt(ws.snow_cover, winter - 0.03, "winter keeps it")
	ws.weather_minutes(30.0, "winter", {"rain": 1.0, "wind": 0.3, "snow": 0.0})
	assert_lt(ws.snow_cover, winter - 0.3, "rain washes it away")


func test_save_round_trip_keeps_puddles() -> void:
	var ws := _state()
	ws.wetness = 0.7
	ws.puddles = 0.45
	ws.snow_cover = 0.2
	var back := WeatherState.new()
	back.from_dict(ws.to_dict())
	assert_almost_eq(back.puddles, 0.45, 0.0001)
	assert_almost_eq(back.wetness, 0.7, 0.0001)
	var old := WeatherState.new()
	old.from_dict({"current": "rain", "wet": 0.5})
	assert_eq(old.puddles, 0.0, "a save from before standing water loads dry")


func test_gusts_swing_around_the_base_wind() -> void:
	var lo: float = INF
	var hi: float = -INF
	for i: int in 600:
		var g: float = WeatherState.gust_at(float(i) * 0.1, 0.6)
		lo = minf(lo, g)
		hi = maxf(hi, g)
	assert_gt(hi, 1.35, "gusts rise well above the base wind")
	assert_lt(lo, 0.8, "and lulls fall below it")
	assert_almost_eq(WeatherState.gust_at(12.3, 0.6), WeatherState.gust_at(12.3, 0.6), 0.0, "deterministic in time")
	assert_almost_eq(WeatherState.gust_at(5.0, 0.0), 1.0, 0.0001, "no gust depth, no gusts")


func test_lightning_is_deterministic_and_frame_rate_independent() -> void:
	var a: Array[Dictionary] = LightningModel.strikes_between(4471, 0.0, 600.0, 7.0, LCFG)
	var b: Array[Dictionary] = LightningModel.strikes_between(4471, 0.0, 600.0, 7.0, LCFG)
	assert_eq(a.size(), b.size(), "same seed and clock, same storm")
	for i: int in a.size():
		assert_eq(a[i]["slot"], b[i]["slot"])
		assert_almost_eq(float(a[i]["distance"]), float(b[i]["distance"]), 0.0001)
	# Ten game hours at 7 an hour: about 70 strikes.
	assert_between(a.size(), 45, 95, "the rate is strikes per game hour")
	# The same ten hours in uneven frames find exactly the same strikes.
	var stepped: Array[Dictionary] = []
	var t: float = 0.0
	var k: int = 0
	while t < 600.0:
		var dt: float = [0.01, 0.37, 0.006, 1.3, 0.09][k % 5]
		var t1: float = minf(600.0, t + dt)
		stepped.append_array(LightningModel.strikes_between(4471, t, t1, 7.0, LCFG))
		t = t1
		k += 1
	assert_eq(stepped.size(), a.size(), "frame rate doesn't change the storm")
	for i: int in mini(stepped.size(), a.size()):
		assert_almost_eq(float(stepped[i]["at_min"]), float(a[i]["at_min"]), 0.0001)
	var other: Array[Dictionary] = LightningModel.strikes_between(99, 0.0, 600.0, 7.0, LCFG)
	var same: bool = other.size() == a.size()
	if same:
		for i: int in a.size():
			same = same and is_equal_approx(float(other[i]["at_min"]), float(a[i]["at_min"]))
	assert_false(same, "another world has another storm")
	assert_eq(LightningModel.strikes_between(4471, 0.0, 600.0, 0.0, LCFG).size(), 0, "no lightning, no strikes")


func test_strikes_are_mostly_distant_with_few_strokes() -> void:
	var all: Array[Dictionary] = LightningModel.strikes_between(7, 0.0, 6000.0, 7.0, LCFG)
	var far: int = 0
	for s: Dictionary in all:
		var d: float = float(s["distance"])
		assert_between(d, 350.0, 9000.0)
		if d > 1000.0:
			far += 1
		var n: int = (s["strokes"] as PackedFloat32Array).size()
		assert_between(n, 1, 4)
		assert_between(float(s["bearing"]), 0.0, TAU)
	assert_gt(float(far) / float(all.size()), 0.6, "most strikes fall over a kilometre away")


func test_thunder_follows_at_the_speed_of_sound() -> void:
	assert_almost_eq(LightningModel.thunder_delay(343.0, LCFG), 1.0, 0.0001)
	assert_almost_eq(LightningModel.thunder_delay(3430.0, LCFG), 10.0, 0.0001, "three kilometres: ten seconds")
	assert_almost_eq(LightningModel.thunder_delay(1000.0, {"speed_of_sound": 330.0}), 1000.0 / 330.0, 0.0001, "from data")


func test_flash_envelope() -> void:
	var s: Dictionary = {"strokes": PackedFloat32Array([0.0, 0.1, 0.25]), "distance": 1000.0, "bearing": 0.0}
	assert_eq(LightningModel.flash(s, -0.1, LCFG), 0.0, "nothing before the strike")
	assert_gt(LightningModel.flash(s, 0.02, LCFG), 0.7, "the first stroke flashes bright")
	assert_lt(LightningModel.flash(s, 0.09, LCFG), LightningModel.flash(s, 0.02, LCFG), "and dies away")
	assert_gt(LightningModel.flash(s, 0.12, LCFG), LightningModel.flash(s, 0.09, LCFG), "a return stroke flashes again")
	assert_lt(LightningModel.flash(s, LightningModel.duration(s, LCFG), LCFG), 0.01, "over by its duration")
	var near: Vector3 = LightningModel.light_direction({"bearing": 0.0, "distance": 500.0})
	var far: Vector3 = LightningModel.light_direction({"bearing": 0.0, "distance": 8000.0})
	assert_gt(near.y, far.y, "a near strike lights from high, a far one from the horizon")


func test_ground_fog_gathers_at_dusk_and_burns_off_after_dawn() -> void:
	var fc: Dictionary = {"dawn": [-1.5, 3.2], "dusk_hours": 2.5, "dusk_strength": 0.55}
	assert_eq(EnvironmentController.ground_fog_at(13.0, 6.25, 19.25, fc), 0.0, "none at midday")
	assert_almost_eq(EnvironmentController.ground_fog_at(6.25, 6.25, 19.25, fc), 1.0, 0.001, "thickest at sunrise")
	assert_lt(EnvironmentController.ground_fog_at(8.5, 6.25, 19.25, fc), 0.5, "burning off through the morning")
	assert_almost_eq(EnvironmentController.ground_fog_at(22.0, 6.25, 19.25, fc), 0.55, 0.001, "settled by night")
	assert_gt(EnvironmentController.ground_fog_at(5.5, 6.25, 19.25, fc), 0.55, "deepening toward dawn")


func test_weather_map_blur_finds_hollows() -> void:
	var n: int = 32
	var g := PackedFloat32Array()
	g.resize(n * n)
	g.fill(10.0)
	g[16 * n + 16] = 9.6
	var s: PackedFloat32Array = WeatherMaps.box_blur(g, n, 3)
	assert_gt(s[16 * n + 16] - g[16 * n + 16], 0.3, "a pit lies below the smoothed ground: water collects there")
	assert_almost_eq(s[2 * n + 2], 10.0, 0.0001, "flat ground has no hollow")


func test_eaves_are_found_where_a_roof_stands_over_open_ground() -> void:
	var m := WeatherMaps.new()
	m.configure({"cells": 16, "cell_m": 1.0, "catch_cells": 16})
	m._next_origin = Vector2(100.0, 200.0)
	m._ground.resize(256)
	m._ground.fill(5.0)
	m._catch = m._ground.duplicate()
	# A 4 x 4 m roof 3 m up, and a low fence rail that is no roof.
	for j: int in range(6, 10):
		for i: int in range(6, 10):
			m._catch[j * 16 + i] = 8.0
	m._catch[2 * 16 + 2] = 6.0
	m._find_eaves()
	assert_eq(m.eaves.size(), 16, "one drip point per roof edge cell over open ground")
	for e: Array in m.eaves:
		var at: Vector3 = e[0]
		assert_almost_eq(at.y, 7.92, 0.001, "drips leave from just under the roof's edge")
		assert_almost_eq(float(e[2]), 2.92, 0.001, "and fall to the ground beside it")
		var on_edge: bool = is_equal_approx(at.x, 106.0) or is_equal_approx(at.x, 110.0) or is_equal_approx(at.z, 206.0) or is_equal_approx(at.z, 210.0)
		assert_true(on_edge, "on the roof's outline: %s" % at)


## Ground that slopes gently east, and no water: what the weather map's worker reads.
class SlopedGround:
	extends RefCounted

	func height_at(x: float, _z: float) -> float:
		return 12.3 + 0.01 * x

	func water_level_at(_x: float, _z: float) -> float:
		return -INF


## Polls the map round `at` until it publishes (the heights come from a worker thread).
func _publish(m: WeatherMaps, at: Vector3, g: Object) -> bool:
	for i: int in 3000:
		if m.update(at, g, g, null):
			return true
		OS.delay_msec(1)
	return false


func test_weather_map_is_published_round_the_camera_and_kept_until_the_next_is_done() -> void:
	var m := WeatherMaps.new()
	m.configure({"cells": 16, "cell_m": 1.5, "catch_cells": 0, "recentre_m": 8.0})
	var g := SlopedGround.new()
	var at := Vector3(100.0, 14.0, 200.0)
	assert_false(m.covers(at), "no map yet")
	assert_true(_publish(m, at, g), "a map is published")
	assert_true(m.covers(at), "round the camera")
	assert_almost_eq(m.catch_at(at.x, at.z), 12.3 + 0.01 * at.x, 0.02, "with nothing overhead, rain lands on the ground")
	var far := Vector3(160.0, 14.0, 200.0)
	assert_false(m.covers(far), "after a jump the old map stays in place")
	assert_eq(m.catch_at(far.x, far.z), -INF, "and the camera is off it")
	assert_true(_publish(m, far, g), "until the new one is complete")
	assert_true(m.covers(far), "round the camera again")
	assert_almost_eq(m.catch_at(far.x, far.z), 12.3 + 0.01 * far.x, 0.02)
	m.shutdown()
