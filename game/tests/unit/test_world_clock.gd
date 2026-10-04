extends GutTest


func _clock(first_horde: int = 7, interval: int = 7) -> WorldClock:
	var c := WorldClock.new()
	c.configure(Content.config(&"world_clock"), {"first_day": first_horde, "interval_days": interval, "start_hour": 22.0, "end_hour": 4.0, "warning_hours": [24, 6, 1]})
	return c


func test_day_and_hour_math() -> void:
	var c := _clock()
	c.set_time(3, 13.5)
	assert_eq(c.day(), 3)
	assert_eq(c.hour(), 13)
	assert_eq(c.minute(), 30)


func test_real_time_rate() -> void:
	var c := _clock()
	c.day_length_real_minutes = 40.0
	c.set_time(1, 0.0)
	c.advance_real(40.0 * 60.0)
	assert_eq(c.day(), 2)
	assert_almost_eq(c.hour_f(), 0.0, 0.001)


func test_night_flags() -> void:
	var c := _clock()
	c.set_time(1, 23.0)
	assert_true(c.is_night())
	c.set_time(1, 12.0)
	assert_false(c.is_night())
	assert_true(c.is_daylight())


func test_events_crossed_in_order_without_duplicates() -> void:
	var c := _clock()
	c.set_time(1, 19.9)  # after dusk (19:45)
	var ev: Array[Dictionary] = c.advance_minutes(90.0)  # to 21:24
	var types: Array = ev.map(func(e: Dictionary) -> String: return e["type"])
	assert_false(types.has("dusk"), "dusk already passed before this advance")
	assert_eq(types, ["hour", "night", "hour"])


func test_long_skip_emits_every_hour_and_day() -> void:
	var c := _clock()
	c.set_time(1, 22.0)
	var ev: Array[Dictionary] = c.advance_minutes(60.0 * 25.0)  # day1 22:00 -> day2 23:00
	var hours: int = ev.filter(func(e: Dictionary) -> bool: return e["type"] == "hour").size()
	var days: int = ev.filter(func(e: Dictionary) -> bool: return e["type"] == "day").size()
	assert_eq(hours, 25)
	assert_eq(days, 1)


func test_horde_schedule() -> void:
	var c := _clock(7, 7)
	assert_false(c.is_horde_day(6))
	assert_true(c.is_horde_day(7))
	assert_true(c.is_horde_day(14))
	assert_false(c.is_horde_day(15))
	c.set_time(3, 12.0)
	assert_eq(c.next_horde_day(), 7)
	c.set_time(8, 12.0)
	assert_eq(c.next_horde_day(), 14)


func test_horde_window_spans_midnight() -> void:
	var c := _clock(3, 7)
	c.set_time(3, 21.5)
	assert_false(c.is_horde_active())
	c.set_time(3, 23.0)
	assert_true(c.is_horde_active())
	c.set_time(4, 2.0)
	assert_true(c.is_horde_active())
	c.set_time(4, 5.0)
	assert_false(c.is_horde_active())


func test_horde_start_end_and_warnings() -> void:
	var c := _clock(2, 7)
	c.set_time(1, 20.0)
	var ev: Array[Dictionary] = c.advance_minutes(60.0 * 4.0)  # day1 20:00 -> day2 00:00
	assert_true(ev.any(func(e: Dictionary) -> bool: return e["type"] == "horde_warning" and int(e["hours_left"]) == 24))
	ev = c.advance_minutes(60.0 * 22.5)  # -> day2 22:30
	assert_true(ev.any(func(e: Dictionary) -> bool: return e["type"] == "horde_start" and int(e["day"]) == 2))
	ev = c.advance_minutes(60.0 * 6.0)  # -> day3 04:30
	assert_true(ev.any(func(e: Dictionary) -> bool: return e["type"] == "horde_end" and int(e["day"]) == 2))


func test_hours_until_horde() -> void:
	var c := _clock(3, 7)
	c.set_time(3, 20.0)
	assert_almost_eq(c.hours_until_horde(), 2.0, 0.001)
	c.set_time(3, 23.0)
	assert_eq(c.hours_until_horde(), 0.0)


func test_seasons_cycle() -> void:
	var c := _clock()
	c.set_time(1, 12.0)
	assert_eq(c.season(), "autumn")
	c.set_time(13, 12.0)
	assert_eq(c.season(), "winter")
	c.set_time(25, 12.0)
	assert_eq(c.season(), "spring")


func test_sun_elevation_day_vs_night() -> void:
	var c := _clock()
	c.set_time(1, 13.0)
	assert_gt(c.sun_elevation_deg(), 20.0)
	c.set_time(1, 1.0)
	assert_lt(c.sun_elevation_deg(), 0.0)
