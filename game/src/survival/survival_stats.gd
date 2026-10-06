class_name SurvivalStats
extends RefCounted
## Player survival model: health, stamina, fullness, hydration, rest, body temperature,
## wetness, bleeding and infection (the Bloom; see DESIGN.md "Novel systems").
##
## Two clocks drive it:
##  - tick_realtime(seconds): stamina use/regen (action-level);
##  - tick_game(game_minutes, env): needs, temperature, bleeding, infection (world clock).
## All tuning comes from data/config/survival.json (via Content.config).

signal changed()
signal died(cause: String)
signal status_added(status: StringName)
signal status_removed(status: StringName)

var health: float = 100.0
var max_health: float = 100.0
var stamina: float = 100.0
var max_stamina: float = 100.0
var fullness: float = 80.0
var hydration: float = 80.0
var rest: float = 85.0
var body_temp: float = 37.0
var wetness: float = 0.0
## Bleed intensity 0..1 (each wound adds; bandages clear).
var bleeding: float = 0.0
## Bloom infection 0..100 (100 = turned). M1: accumulates from bites, slowly grows; cure items lower it.
var infection: float = 0.0
var alive: bool = true
## Insulation from worn clothing in "degrees" of comfort.
var insulation: float = 4.0

## Progression bonuses (PlayerState.refresh_derived): Grit's extra health, Second Wind's regen.
var max_health_bonus: float = 0.0
var stamina_regen_mult: float = 1.0

var _stamina_regen_block: float = 0.0
var _statuses: Dictionary = {}
var _cfg: Dictionary = {}


func _init() -> void:
	reload_config()


func reload_config() -> void:
	_cfg = Content.config(&"survival")
	max_health = _c("health", "max", 100.0) + max_health_bonus
	max_stamina = _c("stamina", "max", 100.0)


## Applies progression bonuses. `grow` (points just spent) also fills the newly added health, as
## raising Grit should feel immediate; on load the saved health is kept as is.
func set_bonuses(health_bonus: float, regen_mult: float, grow: bool = false) -> void:
	var before: float = max_health
	max_health_bonus = maxf(0.0, health_bonus)
	stamina_regen_mult = maxf(0.1, regen_mult)
	max_health = _c("health", "max", 100.0) + max_health_bonus
	if grow and alive and max_health > before:
		health += max_health - before
	health = minf(health, max_health)
	changed.emit()


func _c(section: String, key: String, default: float) -> float:
	return float((_cfg.get(section, {}) as Dictionary).get(key, default))


# --- Derived values ------------------------------------------------------------------------

## Stamina ceiling after hunger/fatigue penalties (The Forest-style shrinking bar).
func stamina_cap() -> float:
	var cap: float = max_stamina
	var hunger_pen: float = _c("stamina", "max_penalty_hunger", 0.4) * clampf(1.0 - fullness / 50.0, 0.0, 1.0)
	var rest_pen: float = _c("stamina", "max_penalty_fatigue", 0.35) * clampf(1.0 - rest / 40.0, 0.0, 1.0)
	cap *= 1.0 - hunger_pen - rest_pen
	return maxf(cap, max_stamina * 0.2)


func has_status(s: StringName) -> bool:
	return _statuses.has(s)


func statuses() -> Array[StringName]:
	var out: Array[StringName] = []
	for k: StringName in _statuses.keys():
		out.append(k)
	out.sort()
	return out


# --- Real-time (stamina) ------------------------------------------------------------------

## exertion: stamina/sec currently being spent continuously (e.g. sprinting); 0 = resting.
func tick_realtime(dt: float, exertion: float = 0.0) -> void:
	if not alive:
		return
	if exertion > 0.0:
		stamina = maxf(0.0, stamina - exertion * dt)
		_stamina_regen_block = _c("stamina", "regen_delay", 0.8)
	else:
		var t: float = dt
		if _stamina_regen_block > 0.0:
			var used: float = minf(t, _stamina_regen_block)
			_stamina_regen_block -= used
			t -= used
		if t > 0.0:
			var rate: float = _c("stamina", "regen_per_sec", 14.0) * stamina_regen_mult
			if hydration < 15.0:
				rate *= 0.5
			stamina = minf(stamina_cap(), stamina + rate * t)
	stamina = minf(stamina, stamina_cap())


## Spend a burst of stamina (swing, jump). Returns false (and spends nothing) if not enough.
func spend_stamina(amount: float) -> bool:
	if stamina < amount * 0.5:
		return false
	stamina = maxf(0.0, stamina - amount)
	_stamina_regen_block = _c("stamina", "regen_delay", 0.8)
	changed.emit()
	return true


# --- Game-time (needs) --------------------------------------------------------------------

## env keys: ambient_c (float), wind (0..1), raining (bool), sheltered (bool), fire_warmth (deg C
## added by nearby fires), sleeping (bool), exertion (0..1 average activity).
func tick_game(minutes: float, env: Dictionary) -> void:
	if not alive or minutes <= 0.0:
		return
	var hours: float = minutes / 60.0
	var exertion: float = float(env.get("exertion", 0.0))
	var sleeping: bool = bool(env.get("sleeping", false))
	var sleep_mult: float = _c("rest", "sleep_needs_mult", 0.45) if sleeping else 1.0
	# World settings: hunger/thirst and Bloom infection pace.
	var needs: float = GameRules.current().num("needs_rate")

	fullness = maxf(0.0, fullness - _c("fullness", "decay_per_hour", 4.0) * needs * hours * (1.0 + exertion * 0.6) * sleep_mult)
	var hot: float = clampf((body_temp - 37.5) / 1.5, 0.0, 1.0)
	hydration = maxf(0.0, hydration - _c("hydration", "decay_per_hour", 6.0) * needs * hours * (1.0 + exertion * 0.5 + hot * 0.5) * sleep_mult)
	if sleeping:
		rest = minf(100.0, rest + _c("rest", "sleep_restore_per_hour", 14.0) * hours)
	else:
		rest = maxf(0.0, rest - _c("rest", "decay_per_hour", 3.0) * hours * (1.0 + exertion * 0.3))

	_tick_temperature(hours, env)
	_tick_bleeding(minutes)
	_tick_infection(hours)

	# Starvation / dehydration / exposure damage.
	if fullness <= 0.0:
		apply_damage(_c("fullness", "starving_damage_per_hour", 6.0) * hours, &"starvation")
	if hydration <= 0.0:
		apply_damage(_c("hydration", "dehydrated_damage_per_hour", 10.0) * hours, &"dehydration")
	if body_temp < _c("temperature", "hypothermia", 35.0):
		apply_damage(_c("temperature", "cold_damage_per_hour", 8.0) * hours, &"cold")
	if body_temp > _c("temperature", "hyperthermia", 39.5):
		apply_damage(_c("temperature", "heat_damage_per_hour", 6.0) * hours, &"heat")

	# Natural regeneration when well fed and watered.
	if alive and fullness >= _c("health", "regen_min_fullness", 50.0) and hydration >= _c("health", "regen_min_hydration", 40.0) and bleeding <= 0.0:
		var regen: float = _c("health", "regen_per_hour", 6.0) * (2.0 if sleeping else 1.0)
		health = minf(max_health, health + regen * hours)

	_update_statuses()
	changed.emit()


func _tick_temperature(hours: float, env: Dictionary) -> void:
	var ambient: float = float(env.get("ambient_c", 12.0))
	var wind: float = float(env.get("wind", 0.2))
	var raining: bool = bool(env.get("raining", false))
	var sheltered: bool = bool(env.get("sheltered", false))
	var fire: float = float(env.get("fire_warmth", 0.0))
	if raining and not sheltered:
		wetness = minf(1.0, wetness + hours * _c("temperature", "wetting_per_hour", 0.8))
	else:
		var dry_rate: float = _c("temperature", "drying_per_hour", 0.35) * (3.0 if fire > 0.0 else 1.0)
		wetness = maxf(0.0, wetness - hours * dry_rate)
	var felt: float = ambient + insulation + fire
	felt -= wind * _c("temperature", "wind_chill", 6.0) * (0.3 if sheltered else 1.0)
	felt -= wetness * _c("temperature", "wet_chill", 8.0)
	if sheltered:
		felt += _c("temperature", "shelter_bonus", 3.0)
	# Comfortable band keeps the body at 37; outside it the body drifts.
	var comfort_lo: float = _c("temperature", "comfort_low", 14.0)
	var comfort_hi: float = _c("temperature", "comfort_high", 30.0)
	var target: float = 37.0
	if felt < comfort_lo:
		target = 37.0 - (comfort_lo - felt) * 0.18
	elif felt > comfort_hi:
		target = 37.0 + (felt - comfort_hi) * 0.12
	target = clampf(target, 30.0, 42.0)
	var rate: float = _c("temperature", "adapt_per_hour", 1.4)
	body_temp = move_toward(body_temp, target, rate * hours)


func _tick_bleeding(minutes: float) -> void:
	if bleeding <= 0.0:
		return
	apply_damage(_c("bleeding", "damage_per_min", 1.5) * bleeding * minutes, &"bleeding")
	bleeding = maxf(0.0, bleeding - _c("bleeding", "clot_per_min", 0.02) * minutes)


func _tick_infection(hours: float) -> void:
	if infection <= 0.0:
		return
	if infection < _c("infection", "dormant_below", 5.0):
		infection = maxf(0.0, infection - _c("infection", "fight_off_per_hour", 0.5) * hours)
	else:
		infection = minf(100.0, infection + _c("infection", "growth_per_hour", 0.35) * GameRules.current().num("infection_rate") * hours)
	if infection >= 100.0:
		_die("turned")


# --- Events --------------------------------------------------------------------------------

## Applies damage (already reduced by armor). Returns damage actually taken.
func apply_damage(amount: float, cause: StringName = &"generic") -> float:
	if not alive or amount <= 0.0:
		return 0.0
	var taken: float = minf(health, amount)
	health -= taken
	if health <= 0.0:
		_die(String(cause))
	changed.emit()
	return taken


func add_wound(bleed: float, infection_amount: float = 0.0) -> void:
	bleeding = clampf(bleeding + bleed, 0.0, 1.0)
	if infection_amount > 0.0:
		infection = minf(100.0, infection + infection_amount * GameRules.current().num("infection_rate"))
	_update_statuses()
	changed.emit()


func heal(amount: float) -> void:
	if alive:
		health = minf(max_health, health + amount)
		changed.emit()


## Applies an item's consume block. Returns the effects applied (for UI feedback).
func consume(def: ItemDef) -> Dictionary:
	var fx: Dictionary = def.consume
	if not alive or fx.is_empty():
		return {}
	fullness = clampf(fullness + float(fx.get("fullness", 0.0)), 0.0, 100.0)
	hydration = clampf(hydration + float(fx.get("hydration", 0.0)), 0.0, 100.0)
	rest = clampf(rest + float(fx.get("rest", 0.0)), 0.0, 100.0)
	stamina = clampf(stamina + float(fx.get("stamina", 0.0)), 0.0, stamina_cap())
	body_temp = clampf(body_temp + float(fx.get("warmth", 0.0)), 30.0, 42.0)
	infection = clampf(infection + float(fx.get("infection", 0.0)), 0.0, 100.0)
	if fx.has("bleeding"):
		bleeding = clampf(bleeding + float(fx["bleeding"]), 0.0, 1.0)
	var hp: float = float(fx.get("health", 0.0))
	if hp > 0.0:
		heal(hp)
	elif hp < 0.0:
		apply_damage(-hp, &"poison")
	_update_statuses()
	changed.emit()
	return fx


func revive(at_health: float = 50.0) -> void:
	alive = true
	health = at_health
	bleeding = 0.0
	stamina = stamina_cap()
	# Turning ends the Bloom in that body. Without this reset the first infection tick after
	# waking found 100 again and killed the player once more: a death loop with the death penalty
	# applied every time. Any other death keeps the infection, because waking from a fall doesn't
	# cure it.
	if infection >= 100.0:
		infection = 0.0
	_update_statuses()
	changed.emit()


func _die(cause: String) -> void:
	if not alive:
		return
	alive = false
	health = 0.0
	died.emit(cause)


func _update_statuses() -> void:
	_set_status(&"starving", fullness <= 10.0)
	_set_status(&"dehydrated", hydration <= 10.0)
	_set_status(&"exhausted", rest <= _c("rest", "exhausted_threshold", 15.0))
	_set_status(&"hypothermic", body_temp < _c("temperature", "hypothermia", 35.0))
	_set_status(&"cold", body_temp < 36.3)
	_set_status(&"overheated", body_temp > 38.6)
	_set_status(&"wet", wetness > 0.35)
	_set_status(&"bleeding", bleeding > 0.0)
	_set_status(&"infected", infection >= _c("infection", "dormant_below", 5.0))


func _set_status(s: StringName, on: bool) -> void:
	if on and not _statuses.has(s):
		_statuses[s] = true
		status_added.emit(s)
	elif not on and _statuses.has(s):
		_statuses.erase(s)
		status_removed.emit(s)


func to_dict() -> Dictionary:
	return {
		"health": health, "stamina": stamina, "fullness": fullness, "hydration": hydration, "rest": rest,
		"body_temp": body_temp, "wetness": wetness, "bleeding": bleeding, "infection": infection,
		"alive": alive, "insulation": insulation,
	}


func from_dict(d: Dictionary) -> void:
	health = float(d.get("health", health))
	stamina = float(d.get("stamina", stamina))
	fullness = float(d.get("fullness", fullness))
	hydration = float(d.get("hydration", hydration))
	rest = float(d.get("rest", rest))
	body_temp = float(d.get("body_temp", body_temp))
	wetness = float(d.get("wetness", wetness))
	bleeding = float(d.get("bleeding", bleeding))
	infection = float(d.get("infection", infection))
	alive = bool(d.get("alive", true))
	insulation = float(d.get("insulation", insulation))
	_update_statuses()
	changed.emit()
