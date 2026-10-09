class_name WorldClockDriver
extends Node
## Advances the session clock in real time (authority only) and fans out boundary crossings to
## Events. Also ticks game-time systems (weather, survival via `game_minutes_passed`).
## Sleeping fast-forwards in coarse steps so needs/weather/AI still progress consistently.

signal game_minutes_passed(minutes: float)

var session: GameSession
var weather: WeatherState
var paused: bool = false
## While > 0 the clock is fast-forwarding (sleep) at this many game minutes per real second.
var fast_forward_rate: float = 0.0
var _ff_remaining: float = 0.0
var _ff_done: Callable = Callable()
var _accum_minutes: float = 0.0


func _process(delta: float) -> void:
	if session == null or paused or not Game.is_authority():
		return
	var minutes: float
	if _ff_remaining > 0.0:
		minutes = minf(_ff_remaining, fast_forward_rate * delta)
		_ff_remaining -= minutes
	else:
		minutes = delta * session.clock.minutes_per_real_second() * session.clock.time_scale
	advance(minutes)
	if _ff_remaining <= 0.0 and fast_forward_rate > 0.0:
		fast_forward_rate = 0.0
		var cb: Callable = _ff_done
		_ff_done = Callable()
		if cb.is_valid():
			cb.call()


## Advances the clock and dispatches every crossed boundary.
func advance(minutes: float) -> void:
	if minutes <= 0.0:
		return
	var events: Array[Dictionary] = session.clock.advance_minutes(minutes)
	for e: Dictionary in events:
		_dispatch(e)
	if weather != null:
		var season: String = session.clock.season()
		if weather.tick(minutes, season, session.rng.stream("weather"), _barred_weather()):
			Events.weather_changed.emit(weather.target)
	game_minutes_passed.emit(minutes)


## The weather the gentle_start rule keeps away in the first days (data/config/weather.json).
func _barred_weather() -> PackedStringArray:
	if not GameRules.current().flag("gentle_start"):
		return PackedStringArray()
	var g: Dictionary = Content.config(&"weather").get("gentle_start", {})
	if session.clock.day() > int(g.get("days", 3)):
		return PackedStringArray()
	return PackedStringArray(g.get("barred", []))


## Fast-forwards `hours` of game time over ~real_seconds, then calls on_done.
func fast_forward(hours: float, real_seconds: float, on_done: Callable = Callable()) -> void:
	_ff_remaining = hours * 60.0
	fast_forward_rate = _ff_remaining / maxf(real_seconds, 0.1)
	_ff_done = on_done


func is_fast_forwarding() -> bool:
	return _ff_remaining > 0.0


func _dispatch(e: Dictionary) -> void:
	var d: int = int(e.get("day", 1))
	match str(e["type"]):
		"hour":
			Events.hour_changed.emit(d, int(e["hour"]))
		"day":
			Events.day_started.emit(d)
		"dawn":
			pass
		"dusk":
			Events.dusk_started.emit(d)
		"night":
			Events.night_started.emit(d)
		"horde_warning":
			Events.horde_night_warning.emit(d, float(e["hours_left"]))
		"horde_start":
			Events.horde_night_started.emit(d)
		"horde_end":
			Events.horde_night_ended.emit(d, {})
