class_name GameRules
extends RefCounted
## World settings for one playthrough (the 7 Days to Die "game options" idea): every tunable from
## data/config/game_rules.json resolved once at new-game time from
##   option defaults <- game mode "rules" (game_modes.json) <- difficulty preset <- player overrides
## and saved with the session. Systems read them through GameRules.current() so nothing caches a
## stale value; unknown or out-of-range values are clamped to the schema (ADR-0014).

var preset: StringName = &"survivor"
var values: Dictionary = {}

static var _fallback: GameRules = null


static func schema() -> Dictionary:
	return Content.config(&"game_rules")


static func options() -> Dictionary:
	return schema().get("options", {})


## The rules of the running session, or schema defaults when there is none (menus, unit tests).
static func current() -> GameRules:
	if Game.session != null and Game.session.rules != null:
		return Game.session.rules
	if _fallback == null:
		_fallback = resolve({}, &"survivor", {})
	return _fallback


static func resolve(mode_rules: Dictionary, preset_id: StringName, overrides: Dictionary) -> GameRules:
	var r := GameRules.new()
	var opts: Dictionary = options()
	for k: String in opts:
		r.values[k] = coerce(opts[k], (opts[k] as Dictionary).get("default"))
	r._apply(mode_rules)
	var presets: Dictionary = schema().get("presets", {})
	if not presets.has(String(preset_id)):
		preset_id = &"survivor"
	r.preset = preset_id
	r._apply((presets[String(preset_id)] as Dictionary).get("values", {}))
	r._apply(overrides)
	return r


## Sets known options, coercing and clamping to the schema; ignores unknown keys.
func _apply(d: Dictionary) -> void:
	var opts: Dictionary = options()
	for k: Variant in d.keys():
		var key: String = str(k)
		if key.begins_with("_") or not opts.has(key):
			continue
		values[key] = coerce(opts[key], d[k])


static func coerce(spec: Dictionary, v: Variant) -> Variant:
	match str(spec.get("type", "float")):
		"int":
			return clampi(int(v), int(spec.get("min", -2147483647)), int(spec.get("max", 2147483647)))
		"float":
			return clampf(float(v), float(spec.get("min", -1e9)), float(spec.get("max", 1e9)))
		"bool":
			return bool(v) if not v is String else str(v) in ["true", "1", "yes", "on"]
		"enum":
			var vals: Array = spec.get("values", [])
			return str(v) if vals.has(str(v)) else str(spec.get("default", vals[0] if not vals.is_empty() else ""))
	return v


func num(key: String) -> float:
	return float(values.get(key, 0.0))


func integer(key: String) -> int:
	return int(values.get(key, 0))


func flag(key: String) -> bool:
	return bool(values.get(key, false))


func choice(key: String) -> String:
	return str(values.get(key, ""))


## Hollowed speed for a period ("day", "night", "hum") relative to the designed default for that
## period, so each type keeps its own pace (a Lurcher is still faster than a Hollow).
func speed_scale(period: String) -> float:
	var f: Dictionary = schema().get("speed_factors", {})
	var key: String = "enemy_speed_" + period
	var default_speed: String = str((options().get(key, {}) as Dictionary).get("default", "run"))
	return float(f.get(choice(key), 1.0)) / maxf(0.01, float(f.get(default_speed, 1.0)))


func sleeper_wake_factor() -> float:
	return float((schema().get("sleeper_wake_factors", {}) as Dictionary).get(choice("sleeper_alertness"), 1.0))


## Options that differ from the preset (what the player customised), for summaries.
func customised() -> Dictionary:
	var base: GameRules = resolve({}, preset, {})
	var out: Dictionary = {}
	for k: String in values:
		if base.values.get(k) != values[k]:
			out[k] = values[k]
	return out


func to_dict() -> Dictionary:
	return {"preset": String(preset), "values": values.duplicate()}


## Saved values win; options added since the save get their defaults.
static func from_dict(d: Dictionary, mode_rules: Dictionary = {}) -> GameRules:
	var r: GameRules = resolve(mode_rules, StringName(str(d.get("preset", "survivor"))), {})
	r._apply(d.get("values", {}))
	return r
