class_name WeatherState
extends RefCounted
## Weather model: current state blends toward a target; when a state's duration runs out the next
## one is picked by season weights (WeatherDef.season_weights). Deterministic given its RNG.
## Wetness accumulates in rain and dries over time (drives hm_wetness); snow cover builds while it
## snows and melts slowly afterwards, very slowly in winter (drives hm_snow). Wind gusts around
## each state's base strength.

const BLEND_MINUTES: float = 45.0
const PARAM_KEYS: PackedStringArray = ["fog_density", "volumetric_density", "rain", "snow", "wind", "cloud_cover", "temperature_offset", "noise_mask"]

var current: StringName = &"clear"
var target: StringName = &"clear"
var blend: float = 1.0
var minutes_left: float = 240.0
var wind_angle: float = 0.7
var wetness: float = 0.0
var snow_cover: float = 0.0
## Game minutes elapsed, for the gust cycle (deterministic: no RNG draw per frame).
var _gust_t: float = 0.0
## Forced by debug tools / scripted events ("" = automatic).
var forced: StringName = &""


func params() -> Dictionary:
	var a: WeatherDef = Content.get_def(&"weather", current) as WeatherDef
	var b: WeatherDef = Content.get_def(&"weather", target) as WeatherDef
	var out: Dictionary = {}
	for k: String in PARAM_KEYS:
		var va: float = float(a.get(k)) if a != null else 0.0
		var vb: float = float(b.get(k)) if b != null else va
		out[k] = lerpf(va, vb, blend)
	out["wind_dir"] = Vector2(cos(wind_angle), sin(wind_angle))
	# Gusts: two slow beats around the state's wind, about +/-25%.
	var gust: float = 0.5 + 0.5 * sin(_gust_t * 0.13) * sin(_gust_t * 0.041 + 1.3)
	out["wind"] = clampf(float(out["wind"]) * lerpf(0.75, 1.25, gust), 0.0, 1.0)
	out["wetness"] = wetness
	out["snow_cover"] = snow_cover
	out["id"] = target if blend > 0.5 else current
	return out


func force(id: StringName) -> void:
	forced = id
	_start(id, 0.5)


func tick(game_minutes: float, season: String, rng: RandomNumberGenerator) -> bool:
	var changed: bool = false
	if blend < 1.0:
		blend = minf(1.0, blend + game_minutes / BLEND_MINUTES)
		if blend >= 1.0:
			current = target
			changed = true
	minutes_left -= game_minutes
	if minutes_left <= 0.0 and blend >= 1.0:
		var next: StringName = forced if forced != &"" else _pick(season, rng)
		_start(next, rng.randf())
		changed = true
	wind_angle += rng.randf_range(-0.002, 0.002) * game_minutes
	_gust_t += game_minutes
	var p: Dictionary = params()
	var rain: float = float(p["rain"])
	if rain > 0.05:
		wetness = minf(1.0, wetness + rain * game_minutes / 40.0)
	else:
		wetness = maxf(0.0, wetness - game_minutes / 180.0)
	var snow: float = float(p["snow"])
	if snow > 0.05:
		snow_cover = minf(1.0, snow_cover + snow * game_minutes / 120.0)
	else:
		# Rain washes it away fastest; winter keeps it for days.
		var melt: float = 1.0 / (2400.0 if season == "winter" else 300.0) + rain / 90.0
		snow_cover = maxf(0.0, snow_cover - melt * game_minutes)
	return changed


## Starts a state; `roll` (0..1) places its length inside the def's duration range (the length
## was always the midpoint, so every rain lasted exactly 4.5 hours).
func _start(id: StringName, roll: float) -> void:
	target = id
	blend = 0.0
	var d: WeatherDef = Content.get_def(&"weather", id) as WeatherDef
	var dur: Vector2 = d.duration_hours if d != null else Vector2(3, 6)
	minutes_left = lerpf(dur.x, dur.y, clampf(roll, 0.0, 1.0)) * 60.0


func _pick(season: String, rng: RandomNumberGenerator) -> StringName:
	var weights: Dictionary = {}
	for d: WeatherDef in Content.all(&"weather"):
		var w: float = float(d.season_weights.get(season, 1.0))
		# Avoid repeating the same state back to back.
		if d.id == target:
			w *= 0.35
		if w > 0.0:
			weights[String(d.id)] = w
	var pick: Variant = Weighted.pick_key(weights, rng)
	return StringName(str(pick)) if pick != null else &"clear"


func to_dict() -> Dictionary:
	return {"current": String(current), "target": String(target), "blend": blend, "left": minutes_left,
		"wind": wind_angle, "wet": wetness, "snow_cover": snow_cover, "gust_t": _gust_t, "forced": String(forced)}


func from_dict(d: Dictionary) -> void:
	current = StringName(str(d.get("current", "clear")))
	target = StringName(str(d.get("target", current)))
	blend = float(d.get("blend", 1.0))
	minutes_left = float(d.get("left", 240.0))
	wind_angle = float(d.get("wind", 0.7))
	wetness = float(d.get("wet", 0.0))
	snow_cover = float(d.get("snow_cover", 0.0))
	_gust_t = float(d.get("gust_t", 0.0))
	forced = StringName(str(d.get("forced", "")))
