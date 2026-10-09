class_name WeatherState
extends RefCounted
## Weather model: current state blends toward a target; when a state's duration runs out the next
## one is picked by season weights (WeatherDef.season_weights). Deterministic given its RNG.
## What the weather leaves behind is state too (ADR-0033), with its rates in
## data/config/weather.json:
## * wetness: surfaces soak in rain and dry afterwards, faster in sun and wind (hm_wetness);
## * puddles: standing water, which only starts once the ground is soaked and lingers for hours
##   after the rain stops (hm_rain.y);
## * snow_cover: builds while it snows and melts slowly afterwards, very slowly in winter (hm_snow).
## Wind gusts around each state's base strength by its `gust` depth: slowly in game time here
## (saved), and in seconds through gust_at(), which the environment drives the foliage and the rain
## with. Lightning is a pure function of the seed and the clock (LightningModel).

const BLEND_MINUTES: float = 45.0
const PARAM_KEYS: PackedStringArray = ["fog_density", "volumetric_density", "rain", "snow", "wind", "cloud_cover", "temperature_offset", "noise_mask",
	"lightning", "gust", "ground_fog", "haze"]

var current: StringName = &"clear"
var target: StringName = &"clear"
var blend: float = 1.0
var minutes_left: float = 240.0
var wind_angle: float = 0.7
var wetness: float = 0.0
var puddles: float = 0.0
var snow_cover: float = 0.0
## How strongly the sun dries things now (0 night or heavy overcast .. 1 high sun): set by the
## environment every frame; drying runs on it.
var daylight: float = 0.5
## Game minutes elapsed, for the slow gust cycle (deterministic: no RNG draw per frame).
var _gust_t: float = 0.0
## Forced by debug tools / scripted events ("" = automatic).
var forced: StringName = &""
## data/config/weather.json (read once; tests may set their own).
var cfg: Dictionary = {}


func params() -> Dictionary:
	var a: WeatherDef = Content.get_def(&"weather", current) as WeatherDef
	var b: WeatherDef = Content.get_def(&"weather", target) as WeatherDef
	var out: Dictionary = {}
	for k: String in PARAM_KEYS:
		var va: float = float(a.get(k)) if a != null else 0.0
		var vb: float = float(b.get(k)) if b != null else va
		out[k] = lerpf(va, vb, blend)
	out["wind_dir"] = Vector2(cos(wind_angle), sin(wind_angle))
	# Slow swells: two beats around the state's wind, as deep as its gust allows.
	var swell: float = 0.5 + 0.5 * sin(_gust_t * 0.13) * sin(_gust_t * 0.041 + 1.3)
	var depth: float = float(out["gust"])
	out["wind"] = clampf(float(out["wind"]) * lerpf(1.0 - depth, 1.0 + depth, swell), 0.0, 1.0)
	out["wetness"] = wetness
	out["puddles"] = puddles
	out["snow_cover"] = snow_cover
	out["id"] = target if blend > 0.5 else current
	return out


## Wind strength multiplier from gusts at a moment in real seconds (deterministic in t): a few
## incommensurate beats, so gusts build over a couple of seconds, hold and die away. 1 = the base
## wind; `depth` (the state's gust) sets the swing.
static func gust_at(t: float, depth: float) -> float:
	var g: float = 0.5 * sin(t * 0.61 + 0.4) + 0.3 * sin(t * 1.37 + 2.1) + 0.2 * sin(t * 2.9 + 4.3)
	# Gusts are short and lulls long: skew the swing upward.
	g = g * 0.5 + 0.5
	g = g * g * (3.0 - 2.0 * g)
	return lerpf(1.0 - depth * 0.6, 1.0 + depth, g)


func force(id: StringName) -> void:
	forced = id
	_start(id, 0.5)


## `barred`: states the next pick may not turn to (the gentle_start rule's first days); one that is
## already blowing ends now rather than at its time.
func tick(game_minutes: float, season: String, rng: RandomNumberGenerator, barred: PackedStringArray = []) -> bool:
	var changed: bool = false
	if not barred.is_empty() and forced == &"" and barred.has(String(target)):
		minutes_left = minf(minutes_left, 0.0)
	if blend < 1.0:
		blend = minf(1.0, blend + game_minutes / BLEND_MINUTES)
		if blend >= 1.0:
			current = target
			changed = true
	minutes_left -= game_minutes
	if minutes_left <= 0.0 and blend >= 1.0:
		var next: StringName = forced if forced != &"" else _pick(season, rng, barred)
		_start(next, rng.randf())
		changed = true
	wind_angle += rng.randf_range(-0.002, 0.002) * game_minutes
	_gust_t += game_minutes
	weather_minutes(game_minutes, season, params())
	return changed


## Advances what the weather leaves behind by `game_minutes` under the weather `p` (params()).
func weather_minutes(game_minutes: float, season: String, p: Dictionary) -> void:
	var c: Dictionary = _section("wetness")
	var rain: float = float(p.get("rain", 0.0))
	var wind: float = float(p.get("wind", 0.0))
	if rain > 0.05:
		wetness = minf(1.0, wetness + rain * game_minutes / float(c.get("wet_minutes", 30.0)))
	else:
		# Still, grey air dries slowly; sun and wind take it off much faster.
		var rate: float = (1.0 + float(c.get("sun_dry", 1.6)) * daylight) * (1.0 + float(c.get("wind_dry", 0.8)) * wind)
		wetness = maxf(0.0, wetness - rate * game_minutes / float(c.get("dry_minutes", 170.0)))
	# Standing water: only once the ground can't drink any more, and it lingers.
	var after: float = float(c.get("puddle_after", 0.55))
	if rain > 0.05 and wetness >= after:
		puddles = minf(1.0, puddles + rain * game_minutes / float(c.get("puddle_fill_minutes", 70.0)))
	elif rain <= 0.05:
		var rate2: float = 1.0 + 0.5 * daylight + 0.3 * wind
		puddles = maxf(0.0, puddles - rate2 * game_minutes / float(c.get("puddle_dry_minutes", 420.0)))
	var s: Dictionary = _section("snow")
	var snow: float = float(p.get("snow", 0.0))
	if snow > 0.05:
		snow_cover = minf(1.0, snow_cover + snow * game_minutes / float(s.get("build_minutes", 120.0)))
	else:
		# Rain washes it away fastest; winter keeps it for days.
		var melt_m: float = float(s.get("melt_minutes_winter", 2400.0)) if season == "winter" else float(s.get("melt_minutes", 300.0))
		var melt: float = 1.0 / melt_m + rain / float(s.get("rain_melt_minutes", 90.0))
		snow_cover = maxf(0.0, snow_cover - melt * game_minutes)


func _section(key: String) -> Dictionary:
	if cfg.is_empty():
		cfg = Content.config(&"weather")
	return cfg.get(key, {}) as Dictionary


## Starts a state; `roll` (0..1) places its length inside the def's duration range (the length
## was always the midpoint, so every rain lasted exactly 4.5 hours).
func _start(id: StringName, roll: float) -> void:
	target = id
	blend = 0.0
	var d: WeatherDef = Content.get_def(&"weather", id) as WeatherDef
	var dur: Vector2 = d.duration_hours if d != null else Vector2(3, 6)
	minutes_left = lerpf(dur.x, dur.y, clampf(roll, 0.0, 1.0)) * 60.0


func _pick(season: String, rng: RandomNumberGenerator, barred: PackedStringArray = []) -> StringName:
	var weights: Dictionary = {}
	for d: WeatherDef in Content.all(&"weather"):
		var w: float = float(d.season_weights.get(season, 1.0)) if not barred.has(String(d.id)) else 0.0
		# Avoid repeating the same state back to back.
		if d.id == target:
			w *= 0.35
		if w > 0.0:
			weights[String(d.id)] = w
	var pick: Variant = Weighted.pick_key(weights, rng)
	return StringName(str(pick)) if pick != null else &"clear"


func to_dict() -> Dictionary:
	return {"current": String(current), "target": String(target), "blend": blend, "left": minutes_left,
		"wind": wind_angle, "wet": wetness, "puddles": puddles, "snow_cover": snow_cover, "gust_t": _gust_t, "forced": String(forced)}


func from_dict(d: Dictionary) -> void:
	current = StringName(str(d.get("current", "clear")))
	target = StringName(str(d.get("target", current)))
	blend = float(d.get("blend", 1.0))
	minutes_left = float(d.get("left", 240.0))
	wind_angle = float(d.get("wind", 0.7))
	wetness = float(d.get("wet", 0.0))
	# Saves from before ADR-0033 have no standing water: it builds again with the next rain.
	puddles = float(d.get("puddles", 0.0))
	snow_cover = float(d.get("snow_cover", 0.0))
	_gust_t = float(d.get("gust_t", 0.0))
	forced = StringName(str(d.get("forced", "")))
