class_name Farming
extends RefCounted
## The rules of gardens and rain catchers (ADR-0049), as pure functions over their saved state
## (WorldState.farms entries) so they can be tested without a world. FarmManager feeds them game
## time and the weather and runs the farm.* commands.
##
## A bed (`garden:<plots>`) has one soil moisture for all its plots: rain soaks it, a bottle or a
## bucket tops it up, the soil and every living plant drink it down (faster when it's hot). A plot
## grows only while there is water, by the season and the air temperature (data/config/
## farming.json, the crop's own seasons) and the crop_growth world setting. In dry soil a plant
## wilts and, after its wilt_days, dies; frost below its frost_c hurts it too. A ripe plot waits to
## be harvested; a perennial (regrow_stage) goes back a few stages instead of emptying.
## A rain catcher (`rain_catcher:<units>`) fills from rain (and a little from snow) under open sky.

const DAY_MIN: float = 1440.0


static func cfg() -> Dictionary:
	return Content.config(&"farming")


static func _section(key: String) -> Dictionary:
	return cfg().get(key, {}) as Dictionary


## Plots of a garden bed (`garden:<n>`), 0 when it is not one.
static func plots_of(def: StructureDef) -> int:
	if def == null:
		return 0
	for p: String in def.provides:
		if p.begins_with("garden:"):
			return int(p.get_slice(":", 1))
	return 0


## Water a rain catcher holds when full (`rain_catcher:<units>`), 0 when it is not one.
static func catcher_capacity(def: StructureDef) -> float:
	if def == null:
		return 0.0
	for p: String in def.provides:
		if p.begins_with("rain_catcher:"):
			return float(p.get_slice(":", 1))
	return 0.0


static func is_farm(def: StructureDef) -> bool:
	return plots_of(def) > 0 or catcher_capacity(def) > 0.0


static func new_state(def: StructureDef) -> Dictionary:
	var n: int = plots_of(def)
	if n > 0:
		var plots: Array = []
		for i: int in n:
			plots.append({})
		return {"kind": "bed", "water": 0.0, "plots": plots}
	return {"kind": "catcher", "water": 0.0}


static func crop(id: Variant) -> CropDef:
	return Content.get_def(&"crop", StringName(str(id))) as CropDef if id != null else null


## The crop an item plants, or null.
static func crop_for_seed(item: StringName) -> CropDef:
	for c: CropDef in Content.all(&"crop"):
		if c.seeds.has(String(item)):
			return c
	return null


static func soil_capacity() -> float:
	return float(_section("soil").get("capacity", 1.0))


# --- Plots ---------------------------------------------------------------------------------------

static func is_empty_plot(plot: Dictionary) -> bool:
	return not plot.has("crop")


static func is_dead(plot: Dictionary) -> bool:
	return bool(plot.get("dead", false))


static func is_ripe(plot: Dictionary) -> bool:
	var c: CropDef = crop(plot.get("crop"))
	return c != null and not is_dead(plot) and float(plot.get("grown", 0.0)) >= c.grow_days - 0.0001


## 0..1 of the way to ripe.
static func progress(plot: Dictionary) -> float:
	var c: CropDef = crop(plot.get("crop"))
	return clampf(float(plot.get("grown", 0.0)) / c.grow_days, 0.0, 1.0) if c != null else 0.0


## Visual stage (0-based): the last one only when ripe.
static func stage_of(plot: Dictionary) -> int:
	var c: CropDef = crop(plot.get("crop"))
	if c == null:
		return 0
	if is_ripe(plot):
		return c.stages - 1
	return mini(c.stages - 2, int(floor(progress(plot) * float(c.stages - 1))))


static func is_wilted(plot: Dictionary) -> bool:
	return not is_empty_plot(plot) and not is_dead(plot) and float(plot.get("health", 1.0)) < float(_section("plants").get("wilted_below", 0.6))


static func plant(plot: Dictionary, c: CropDef) -> void:
	plot.clear()
	plot["crop"] = String(c.id)
	plot["grown"] = 0.0
	plot["health"] = 1.0


## Growth stage a perennial goes back to after a harvest, in grown days.
static func regrow_days(c: CropDef) -> float:
	return c.grow_days * float(c.regrow_stage) / float(c.stages - 1)


# --- Growth --------------------------------------------------------------------------------------

## The season's growth multiplier for a crop (its own, else the config's).
static func season_mult(c: CropDef, season: String) -> float:
	if c.seasons.has(season):
		return float(c.seasons[season])
	return float((cfg().get("seasons", {}) as Dictionary).get(season, 1.0))


## 0..1 by the air temperature: nothing at the crop's min_temp_c, full from best_c to hot_c, less
## past it.
static func temp_factor(c: CropDef, ambient_c: float) -> float:
	var t: Dictionary = _section("temperature")
	var best: float = maxf(float(t.get("best_c", 16.0)), c.min_temp_c + 1.0)
	var hot: float = float(t.get("hot_c", 30.0))
	if ambient_c <= c.min_temp_c:
		return 0.0
	if ambient_c < best:
		return (ambient_c - c.min_temp_c) / (best - c.min_temp_c)
	if ambient_c <= hot:
		return 1.0
	return clampf(1.0 - (ambient_c - hot) / 12.0, 0.25, 1.0)


## Days of good growth a day of this weather gives (before water and health).
static func growth_rate(c: CropDef, env: Dictionary) -> float:
	return season_mult(c, str(env.get("season", "spring"))) * temp_factor(c, float(env.get("ambient_c", 15.0))) \
		* maxf(0.0, float(env.get("growth", 1.0)))


## Advances a bed by `minutes` of game time. env: {ambient_c, rain (0..1, 0 when sheltered), season,
## growth (the crop_growth world setting)}. Returns true when anything a player would see changed
## (a stage, wilting, a death, the soil going dry or wet).
static func tick_bed(st: Dictionary, minutes: float, env: Dictionary) -> bool:
	if minutes <= 0.0:
		return false
	var soil: Dictionary = _section("soil")
	var pl: Dictionary = _section("plants")
	var before: String = signature(st)
	var days: float = minutes / DAY_MIN
	var cap: float = soil_capacity()
	var ambient: float = float(env.get("ambient_c", 15.0))
	var plots: Array = st.get("plots", [])
	var live: int = 0
	for plot: Dictionary in plots:
		if not is_empty_plot(plot) and not is_dead(plot):
			live += 1
	var water: float = float(st.get("water", 0.0))
	water = minf(cap, water + float(env.get("rain", 0.0)) * minutes / maxf(1.0, float(soil.get("rain_fill_minutes", 90.0))))
	var heat: float = maxf(0.0, ambient - float(soil.get("hot_from_c", 18.0))) * float(soil.get("hot_dry_per_c", 0.04))
	var use: float = (float(soil.get("dry_per_day", 0.3)) + float(soil.get("crop_use_per_day", 0.06)) * live) * (1.0 + heat) * days
	# The share of this tick the soil still had water in it: plants grow through that part and
	# wilt through the rest.
	var wet: float = 1.0 if use <= 0.0 or water >= use else clampf(water / use, 0.0, 1.0)
	if water <= 0.0:
		wet = 0.0
	st["water"] = clampf(water - use, 0.0, cap)
	for plot: Dictionary in plots:
		if is_empty_plot(plot) or is_dead(plot):
			continue
		var c: CropDef = crop(plot["crop"])
		if c == null:
			continue
		var health: float = float(plot.get("health", 1.0))
		health -= days * (1.0 - wet) / c.wilt_days
		if ambient < c.frost_c:
			# Frost: water doesn't save it, and nothing mends while it lasts.
			health -= days / maxf(0.05, float(pl.get("frost_kill_days", 1.0)))
		else:
			health += days * wet * float(pl.get("recover_per_day", 0.6))
		if not is_ripe(plot):
			var g: float = days * wet * growth_rate(c, env) * lerpf(0.5, 1.0, clampf(health, 0.0, 1.0))
			plot["grown"] = minf(c.grow_days, float(plot.get("grown", 0.0)) + g)
		plot["health"] = clampf(health, 0.0, 1.0)
		if health <= 0.0:
			plot["dead"] = true
	return signature(st) != before


## Fills a rain catcher by `minutes` of the weather in env {rain, snow} (both 0 under a roof).
static func tick_catcher(st: Dictionary, minutes: float, env: Dictionary, capacity: float) -> bool:
	var c: Dictionary = _section("catcher")
	var before: int = int(float(st.get("water", 0.0)))
	var add: float = (float(env.get("rain", 0.0)) * float(c.get("fill_per_hour", 2.0))
		+ float(env.get("snow", 0.0)) * float(c.get("snow_fill_per_hour", 0.4))) * minutes / 60.0
	st["water"] = clampf(float(st.get("water", 0.0)) + add, 0.0, capacity)
	return int(float(st["water"])) != before


## What a player sees of a bed: per plot its crop, stage and condition, and the soil wet or dry
## (changes in it mean the visual needs a refresh).
static func signature(st: Dictionary) -> String:
	var parts: PackedStringArray = ["wet" if float(st.get("water", 0.0)) > 0.01 else "dry"]
	for plot: Dictionary in st.get("plots", []):
		if is_empty_plot(plot):
			parts.append("-")
		else:
			parts.append("%s%d%s%s" % [plot["crop"], stage_of(plot), "x" if is_dead(plot) else "", "w" if is_wilted(plot) else ""])
	return ",".join(parts)


# --- Water ---------------------------------------------------------------------------------------

## How much soil moisture one of `item` gives a bed (0 = it doesn't water), and what it leaves.
static func water_source(item: StringName) -> Dictionary:
	var ws: Dictionary = _section("water_sources")
	var e: Variant = ws.get(String(item))
	return e if e is Dictionary else {}


## The water item a player would pour on a bed: the held one if it waters, else the configured order.
static func water_choice(p: PlayerState) -> StringName:
	var held: StringName = p.equipped_item()
	if held != &"" and not water_source(held).is_empty() and p.inventory.has(held):
		return held
	for id: Variant in _section("water_sources").get("order", []):
		if p.inventory.has(StringName(str(id))):
			return StringName(str(id))
	return &""


## The seed item a player would plant: the held one if it plants something, else the first carried
## (crops in id order, each crop's seeds in their order).
static func seed_choice(p: PlayerState) -> StringName:
	var held: StringName = p.equipped_item()
	if held != &"" and crop_for_seed(held) != null and p.inventory.has(held):
		return held
	for c: CropDef in Content.all(&"crop"):
		for s: String in c.seeds:
			if p.inventory.has(StringName(s)):
				return StringName(s)
	return &""


## Empty containers a player carries that a catcher can fill: [[empty, full, units]], in config order.
static func fillable(p: PlayerState) -> Array:
	var out: Array = []
	var cont: Dictionary = _section("catcher").get("containers", {})
	for k: Variant in cont.keys():
		if p.inventory.has(StringName(str(k))):
			var v: Array = cont[k]
			out.append([StringName(str(k)), StringName(str(v[0])), int(v[1])])
	return out
