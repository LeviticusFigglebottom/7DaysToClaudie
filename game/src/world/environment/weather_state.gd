class_name WeatherState
extends RefCounted
## Weather model: current state blends toward a target; when a state's duration runs out the next
## one is picked by season weights (WeatherDef.season_weights). Deterministic given its RNG.
## Wetness accumulates in rain and dries over time (drives hm_wetness).

const BLEND_MINUTES: float = 45.0
const PARAM_KEYS: PackedStringArray = ["fog_density", "volumetric_density", "rain", "snow", "wind", "cloud_cover", "temperature_offset", "noise_mask"]

var current: StringName = &"clear"
var target: StringName = &"clear"
var blend: float = 1.0
var minutes_left: float = 240.0
var wind_angle: float = 0.7
var wetness: float = 0.0
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
	out["wetness"] = wetness
	out["id"] = target if blend > 0.5 else current
	return out


func force(id: StringName) -> void:
	forced = id
	_start(id, 120.0)


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
		_start(next, 0.0)
		changed = true
	wind_angle += rng.randf_range(-0.002, 0.002) * game_minutes
	var p: Dictionary = params()
	var rain: float = float(p["rain"])
	if rain > 0.05:
		wetness = minf(1.0, wetness + rain * game_minutes / 40.0)
	else:
		wetness = maxf(0.0, wetness - game_minutes / 180.0)
	return changed


func _start(id: StringName, _unused: float) -> void:
	target = id
	blend = 0.0
	var d: WeatherDef = Content.get_def(&"weather", id) as WeatherDef
	var dur: Vector2 = d.duration_hours if d != null else Vector2(3, 6)
	minutes_left = lerpf(dur.x, dur.y, 0.5) * 60.0


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
		"wind": wind_angle, "wet": wetness, "forced": String(forced)}


func from_dict(d: Dictionary) -> void:
	current = StringName(str(d.get("current", "clear")))
	target = StringName(str(d.get("target", current)))
	blend = float(d.get("blend", 1.0))
	minutes_left = float(d.get("left", 240.0))
	wind_angle = float(d.get("wind", 0.7))
	wetness = float(d.get("wet", 0.0))
	forced = StringName(str(d.get("forced", "")))
