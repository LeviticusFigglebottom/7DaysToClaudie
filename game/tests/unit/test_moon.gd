extends GutTest
## The moon (ADR-0023): phase and position follow the world clock deterministically, moonrise
## drifts later through the cycle, full and new moon light the night differently, and the night's
## darkness range comes from data.


func _clock() -> WorldClock:
	var c := WorldClock.new()
	c.configure(Content.config(&"world_clock"), {"first_day": 7, "interval_days": 7})
	return c


func _moon() -> MoonModel:
	return MoonModel.new().configure(Content.config(&"world_clock").get("moon", {}))


## Day number and hour at which the phase is `target` (first time on or after day 1).
func _when(m: MoonModel, target: float) -> float:
	var days: float = fposmod(target - m.phase_at_start, 1.0) * m.synodic_days
	return days * WorldClock.MIN_PER_DAY


func test_phase_follows_the_clock() -> void:
	var m: MoonModel = _moon()
	var c: WorldClock = _clock()
	c.set_time(1, 0.0)
	assert_almost_eq(m.phase_at(c.total_minutes), m.phase_at_start, 1e-5)
	var cycle: float = m.synodic_days * WorldClock.MIN_PER_DAY
	assert_almost_eq(m.phase_at(c.total_minutes + cycle), m.phase_at_start, 1e-4, "one synodic month later")
	assert_almost_eq(m.phase_at(_when(m, 0.5)), 0.5, 1e-4)
	# Continuous: no step at midnight.
	c.set_time(3, 23.99)
	var before: float = m.phase_at(c.total_minutes)
	c.set_time(4, 0.01)
	assert_almost_eq(m.phase_at(c.total_minutes), before, 0.001)
	assert_eq(MoonModel.phase_name(0.5), "FULL MOON")
	assert_eq(MoonModel.phase_name(0.0), "NEW MOON")
	assert_eq(MoonModel.phase_name(0.25), "FIRST QUARTER")
	assert_eq(MoonModel.phase_name(0.76), "LAST QUARTER")
	assert_eq(MoonModel.phase_name(0.88), "WANING CRESCENT")


func test_light_by_phase() -> void:
	var m: MoonModel = _moon()
	assert_almost_eq(MoonModel.illuminated(0.0), 0.0, 1e-5)
	assert_almost_eq(MoonModel.illuminated(0.5), 1.0, 1e-5)
	assert_almost_eq(MoonModel.illuminated(0.25), 0.5, 1e-5)
	assert_almost_eq(m.brightness(0.5), 1.0, 1e-5)
	assert_lt(m.brightness(0.25), 0.5, "a half moon gives less than half a full moon's light")
	var prev: float = -1.0
	for i: int in 11:
		var b: float = m.brightness(0.05 * i)
		assert_gt(b, prev, "waxing brightens")
		prev = b


func test_full_moon_rules_the_night_and_new_moon_the_day() -> void:
	var m: MoonModel = _moon()
	var c: WorldClock = _clock()
	var noon: float = MoonModel.noon_hour(c)
	# Midnight nearest the full moon.
	var full_t: float = round(_when(m, 0.5) / WorldClock.MIN_PER_DAY) * WorldClock.MIN_PER_DAY
	c.total_minutes = full_t
	var yr: float = MoonModel.year_phase(c)
	assert_gt(m.altitude_at(full_t, noon, yr), 15.0, "a full moon is high at midnight")
	assert_lt(m.altitude_at(full_t + 12.0 * 60.0, noon, yr), 0.0, "and down at noon")
	var dir: Vector3 = m.direction_at(full_t, noon, yr)
	assert_almost_eq(dir.length(), 1.0, 1e-4)
	assert_gt(dir.z, 0.0, "it crosses the sky to the south")
	var new_t: float = round(_when(m, 0.0) / WorldClock.MIN_PER_DAY) * WorldClock.MIN_PER_DAY
	assert_lt(m.altitude_at(new_t, noon, yr), 0.0, "a new moon is down at midnight")
	assert_gt(m.altitude_at(new_t + 12.75 * 60.0, noon, yr), 0.0, "and up with the sun")


func test_moonrise_drifts_later_each_day() -> void:
	var m: MoonModel = _moon()
	var c: WorldClock = _clock()
	var rises: Array[float] = []
	var day: int = 1
	while rises.size() < int(m.synodic_days) and day < 40:
		var rs: Vector2 = m.rise_set(c, day)
		if rs.x >= 0.0:
			rises.append(float(day - 1) * 24.0 + rs.x)
		day += 1
	assert_gt(rises.size(), 6, "the moon rises on most days")
	var drift: float = (rises[-1] - rises[0]) / float(rises.size() - 1) - 24.0
	# The moon falls back 360 / synodic_days degrees a day against the sun: 24 / (P - 1) hours.
	var expected: float = 24.0 / (m.synodic_days - 1.0)
	assert_almost_eq(drift, expected, 0.6, "moonrise comes ~%.1f h later each day (got %.2f)" % [expected, drift])
	# Over one cycle moonrise visits every part of the clock.
	var hours: Array[float] = []
	for r: float in rises:
		hours.append(fposmod(r, 24.0))
	hours.sort()
	var widest: float = 24.0 - (hours[-1] - hours[0])
	for i: int in range(1, hours.size()):
		widest = maxf(widest, hours[i] - hours[i - 1])
	assert_lt(widest, 7.0, "no part of the day is skipped by moonrise")


func test_disc_shading_matches_the_phase() -> void:
	var moon_dir := Vector3(0.0, 0.6, 0.8)
	var sun_dir := Vector3(-0.9, -0.3, 0.3).normalized()
	for phase: float in [0.1, 0.25, 0.5, 0.8]:
		var s: Vector3 = MoonModel.sunlight_at_moon(moon_dir, sun_dir, phase)
		assert_almost_eq(rad_to_deg(moon_dir.angle_to(s)), rad_to_deg(MoonModel.elongation(phase)), 0.01)
		if phase < 0.5:
			# The lit limb faces the sun the player sees.
			assert_gt((s - moon_dir * s.dot(moon_dir)).dot(sun_dir), 0.0)


func test_darkness_range_is_data() -> void:
	var cfg: Dictionary = Content.config(&"world_clock").get("moon", {})
	assert_true(cfg.has("night_ambient_new") and cfg.has("night_ambient_full"))
	assert_lt(float(cfg["night_ambient_new"]), float(cfg["night_ambient_full"]), "a new moon is darker than a full one")
	assert_lt(Color.html(str(cfg["night_zenith_new"])).get_luminance(), Color.html(str(cfg["night_zenith_full"])).get_luminance())


func test_full_and_new_moon_nights_differ() -> void:
	var m: MoonModel = _moon()
	var c: WorldClock = _clock()
	var env := EnvironmentController.new()
	env.clock = c
	add_child_autofree(env)
	c.total_minutes = round(_when(m, 0.5) / WorldClock.MIN_PER_DAY) * WorldClock.MIN_PER_DAY
	env.update_now()
	var full_light: float = env.moon.light_energy
	var full_ambient: float = env.env.ambient_light_energy
	assert_eq(str(env.moon_state["name"]), "FULL MOON")
	assert_gt(full_light, 0.05, "a full moon lights the night")
	c.total_minutes = round(_when(m, 0.0) / WorldClock.MIN_PER_DAY) * WorldClock.MIN_PER_DAY
	env.update_now()
	assert_lt(env.moon.light_energy, 0.002, "no moonlight at new moon")
	assert_lt(env.env.ambient_light_energy, full_ambient * 0.5, "a new-moon night is much darker")
	assert_gt(env.env.ambient_light_energy, 0.0, "but not black: the darkness has a floor")
