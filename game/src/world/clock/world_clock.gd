class_name WorldClock
extends RefCounted
## Game time model: day/hour, day-night phases, seasons and the Hum (horde night) schedule.
## Pure model — WorldClockDriver (node) advances it and forwards crossings to Events.
##
## Time is stored as total game minutes since Day 1 00:00 (float, saved). One game day lasts
## `day_length_minutes` real minutes (data/config/world_clock.json).

const MIN_PER_DAY: float = 1440.0

var total_minutes: float = 0.0
var day_length_real_minutes: float = 40.0
var sunrise_hour: float = 6.25
var sunset_hour: float = 19.25
var night_start_hour: float = 21.0
var night_end_hour: float = 5.0
var dusk_hour: float = 19.75
var season_order: PackedStringArray = ["spring", "summer", "autumn", "winter"]
var season_length_days: int = 12
var season_start_index: int = 2
## Horde ("the Hum") schedule.
var horde_first_day: int = 7
## 0 disables the Hum.
var horde_interval_days: int = 7
## Seeded ± jitter per Hum (game rule hum_variance_days), capped so Hums never reorder.
var horde_variance_days: int = 0
var horde_seed: int = 0
var horde_start_hour: float = 22.0
var horde_end_hour: float = 4.0
var horde_warning_hours: PackedFloat32Array = [24.0, 6.0, 1.0]
## Multiplier for time flow (sleeping fast-forwards; debug can change it).
var time_scale: float = 1.0


func configure(clock_cfg: Dictionary, horde_cfg: Dictionary) -> void:
	day_length_real_minutes = float(clock_cfg.get("day_length_minutes", day_length_real_minutes))
	sunrise_hour = float(clock_cfg.get("sunrise_hour", sunrise_hour))
	sunset_hour = float(clock_cfg.get("sunset_hour", sunset_hour))
	dusk_hour = float(clock_cfg.get("dusk_hour", dusk_hour))
	night_start_hour = float(clock_cfg.get("night_start_hour", night_start_hour))
	night_end_hour = float(clock_cfg.get("night_end_hour", night_end_hour))
	var seasons: Dictionary = clock_cfg.get("seasons", {})
	if seasons.has("order"):
		season_order = PackedStringArray(seasons["order"])
	season_length_days = int(seasons.get("length_days", season_length_days))
	season_start_index = maxi(0, season_order.find(str(seasons.get("start", "autumn"))))
	horde_first_day = maxi(1, int(horde_cfg.get("first_day", horde_first_day)))
	horde_interval_days = maxi(0, int(horde_cfg.get("interval_days", horde_interval_days)))
	horde_variance_days = maxi(0, int(horde_cfg.get("variance_days", 0)))
	horde_seed = int(horde_cfg.get("seed", 0))
	horde_start_hour = float(horde_cfg.get("start_hour", horde_start_hour))
	horde_end_hour = float(horde_cfg.get("end_hour", horde_end_hour))
	if horde_cfg.has("warning_hours"):
		horde_warning_hours = PackedFloat32Array(horde_cfg["warning_hours"])


func set_time(day_num: int, hour: float) -> void:
	total_minutes = float(day_num - 1) * MIN_PER_DAY + hour * 60.0


func day() -> int:
	return int(floor(total_minutes / MIN_PER_DAY)) + 1


func hour_f() -> float:
	return fposmod(total_minutes, MIN_PER_DAY) / 60.0


func hour() -> int:
	return int(floor(hour_f()))


func minute() -> int:
	return int(floor(fposmod(total_minutes, 60.0)))


## Game minutes that pass per real second at time_scale 1.
func minutes_per_real_second() -> float:
	return MIN_PER_DAY / (day_length_real_minutes * 60.0)


func is_night() -> bool:
	var h: float = hour_f()
	return h >= night_start_hour or h < night_end_hour


func is_daylight() -> bool:
	var h: float = hour_f()
	return h >= sunrise_hour and h < sunset_hour


## 0 at midnight .. 1 at noon (smooth), useful for lighting/temperature curves.
func daylight_factor() -> float:
	var h: float = hour_f()
	if h <= sunrise_hour - 0.75 or h >= sunset_hour + 0.75:
		return 0.0
	var mid: float = (sunrise_hour + sunset_hour) * 0.5
	var half: float = (sunset_hour - sunrise_hour) * 0.5 + 0.75
	return clampf(cos((h - mid) / half * PI * 0.5), 0.0, 1.0)


## Sun elevation in degrees (negative below the horizon), simple sinusoid over the day.
func sun_elevation_deg() -> float:
	var h: float = hour_f()
	var mid: float = (sunrise_hour + sunset_hour) * 0.5
	var day_len: float = sunset_hour - sunrise_hour
	var t: float = (h - mid) / day_len
	var max_elev: float = 52.0 + 14.0 * sin(season_phase() * TAU - PI * 0.5)
	return max_elev * cos(t * PI) - (max_elev * cos(0.5 * PI))


# --- Seasons -------------------------------------------------------------------------------

func season_index() -> int:
	var d: int = day() - 1
	return (season_start_index + d / season_length_days) % season_order.size()


func season() -> String:
	return season_order[season_index()]


## 0..1 through the current season.
func season_progress() -> float:
	return float((day() - 1) % season_length_days) / float(season_length_days)


## 0..1 through the year (spring start = 0).
func season_phase() -> float:
	return (float(season_index()) + season_progress()) / float(season_order.size())


# --- Hum schedule --------------------------------------------------------------------------

func hordes_enabled() -> bool:
	return horde_interval_days > 0


## Day of the k-th Hum (0-based): first + k * interval, shifted by a seeded ± variance.
func horde_day_of(k: int) -> int:
	var d: int = horde_first_day + k * horde_interval_days
	var v: int = mini(horde_variance_days, (horde_interval_days - 1) / 2)
	if v > 0 and k > 0:
		d += Ids.hash31("hum:%d:%d" % [horde_seed, k]) % (2 * v + 1) - v
	return d


func is_horde_day(d: int) -> bool:
	if not hordes_enabled() or d < horde_first_day:
		return false
	var k: int = int(round(float(d - horde_first_day) / float(horde_interval_days)))
	for kk: int in [k - 1, k, k + 1]:
		if kk >= 0 and horde_day_of(kk) == d:
			return true
	return false


## First Hum day on or after from_day; -1 when the Hum is disabled.
func next_horde_day(from_day: int = -1) -> int:
	if not hordes_enabled():
		return -1
	var d: int = day() if from_day < 0 else from_day
	var k: int = maxi(0, int(floor(float(d - horde_first_day) / float(horde_interval_days))) - 1)
	while horde_day_of(k) < d:
		k += 1
	return horde_day_of(k)


## True during the Hum window (start_hour on a horde day until end_hour the next morning).
func is_horde_active() -> bool:
	var h: float = hour_f()
	var d: int = day()
	return (is_horde_day(d) and h >= horde_start_hour) or (is_horde_day(d - 1) and h < horde_end_hour)


## Game hours until the next Hum starts (0 if active).
func hours_until_horde() -> float:
	if is_horde_active():
		return 0.0
	if not hordes_enabled():
		return INF
	var d: int = day()
	var hd: int = next_horde_day(d)
	if hd == d and hour_f() >= horde_start_hour:
		hd = next_horde_day(d + 1)
	var target: float = float(hd - 1) * MIN_PER_DAY + horde_start_hour * 60.0
	return maxf(0.0, (target - total_minutes) / 60.0)


# --- Advancing -----------------------------------------------------------------------------

## Advances by real seconds (scaled). Returns crossed events (see advance_minutes).
func advance_real(seconds: float) -> Array[Dictionary]:
	return advance_minutes(seconds * minutes_per_real_second() * time_scale)


## Advances game time and returns every boundary crossed, in order:
## {type: "hour"|"day"|"dawn"|"dusk"|"night"|"horde_warning"|"horde_start"|"horde_end", day, hour, ...}
func advance_minutes(minutes: float) -> Array[Dictionary]:
	var events: Array[Dictionary] = []
	if minutes <= 0.0:
		return events
	var before: float = total_minutes
	var after: float = total_minutes + minutes
	var was_horde: bool = is_horde_active()
	var hours_left_before: float = hours_until_horde()
	# Walk whole-hour boundaries so long skips (sleep) still emit every crossing, in order.
	# Ranges are half-open (cursor, mark] so a boundary is never reported twice.
	var cursor: float = before
	var next_hour_mark: float = (floor(before / 60.0) + 1.0) * 60.0
	while next_hour_mark <= after:
		_phase_crossings(events, cursor, next_hour_mark)
		total_minutes = next_hour_mark
		var d: int = day()
		var h: int = hour()
		events.append({"type": "hour", "day": d, "hour": h})
		if h == 0:
			events.append({"type": "day", "day": d, "hour": 0})
		cursor = next_hour_mark
		next_hour_mark += 60.0
	# Remaining partial hour (fractional-hour boundaries such as a 19:45 dusk).
	_phase_crossings(events, cursor, after)
	total_minutes = after
	var hours_left_after: float = hours_until_horde()
	for w: float in horde_warning_hours:
		if hours_left_before > w and hours_left_after <= w and hours_left_after > 0.0:
			events.append({"type": "horde_warning", "day": next_horde_day(), "hours_left": w})
	var is_horde: bool = is_horde_active()
	if is_horde and not was_horde:
		events.append({"type": "horde_start", "day": day() if hour_f() >= horde_start_hour else day() - 1})
	elif was_horde and not is_horde:
		events.append({"type": "horde_end", "day": day() - 1 if hour_f() >= horde_end_hour else day()})
	return events


func _phase_crossings(events: Array[Dictionary], from_min: float, to_min: float) -> void:
	for spec: Array in [["dawn", sunrise_hour], ["dusk", dusk_hour], ["night", night_start_hour]]:
		var h: float = spec[1]
		var day_start: float = floor(from_min / MIN_PER_DAY) * MIN_PER_DAY
		for base: float in [day_start, day_start + MIN_PER_DAY]:
			var mark: float = base + h * 60.0
			if mark > from_min and mark <= to_min:
				events.append({"type": spec[0], "day": int(floor(mark / MIN_PER_DAY)) + 1, "hour": h})


func to_dict() -> Dictionary:
	return {"total_minutes": total_minutes, "time_scale": time_scale}


func from_dict(d: Dictionary) -> void:
	total_minutes = float(d.get("total_minutes", total_minutes))
	time_scale = float(d.get("time_scale", 1.0))
