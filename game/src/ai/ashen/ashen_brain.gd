class_name AshenBrain
extends RefCounted
## The Ashen's arithmetic (ADR-0048), pure and deterministic so it can be tested without a world:
## hostility and the escalation level it gives, the daily scout and raid rolls, raid sizes, morale
## and how frightening a fire is. AshenDirector and AshenMind call it; nothing here touches the
## scene tree.

const AGGRESSION: Dictionary = {"calm": 0.5, "normal": 1.0, "fierce": 1.6}


## The faction def (the one in data/factions/ashen.json).
static func def() -> FactionDef:
	return Content.get_def(&"faction", &"ashen") as FactionDef


## Escalation level for a hostility score at a gamestage: the highest level whose `at` and
## `gamestage` are both met.
static func level_for(fd: FactionDef, hostility: float, gamestage: int) -> int:
	var lv: int = 0
	for i: int in fd.levels.size():
		var l: Dictionary = fd.levels[i]
		if hostility >= float(l.get("at", 0.0)) and gamestage >= int(l.get("gamestage", 0)):
			lv = i
	return lv


## Hostility after an event (`FactionDef.GAIN_EVENTS`), `times` over, scaled by the aggression
## setting, capped at hostility.max.
static func gain(fd: FactionDef, hostility: float, event: String, times: float = 1.0, aggression: String = "normal") -> float:
	var g: float = float((fd.hostility.get("gain", {}) as Dictionary).get(event, 0.0)) * times * float(AGGRESSION.get(aggression, 1.0))
	return clampf(hostility + g, 0.0, float(fd.hostility.get("max", 150.0)))


## Hostility at the next dawn: below the raid level it creeps up (curiosity), at or above it fades.
static func dawn(fd: FactionDef, hostility: float) -> float:
	var raid_at: float = float((fd.levels[mini(2, fd.levels.size() - 1)] as Dictionary).get("at", 35.0))
	if hostility < raid_at:
		return minf(raid_at - 0.01, hostility + float(fd.hostility.get("daily_rise", 0.0)))
	return maxf(0.0, hostility - float(fd.hostility.get("decay_per_day", 0.0)))


## The day's scout visit, or {}: {hour: float} when one comes. Deterministic per world and day.
static func scout_roll(fd: FactionDef, world_seed: int, day: int, level: int, aggression: String = "normal") -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:scout:%d:%d" % [world_seed, day])
	var chance: float = float(FactionDef.per_level(fd.scouts.get("chance", []), level, 0.0)) * float(AGGRESSION.get(aggression, 1.0))
	if rng.randf() >= chance:
		return {}
	var h: Array = fd.scouts.get("hour", [8, 17])
	return {"hour": rng.randf_range(float(h[0]), float(h[1]))}


## The day's raid, or {}: {hour, size, members: [enemy ids]}. Never in the grace days, never on a
## Hum day (`hum_day`). Deterministic per world and day.
static func raid_roll(fd: FactionDef, world_seed: int, day: int, level: int, gamestage: int, hum_day: bool,
		aggression: String = "normal") -> Dictionary:
	if hum_day or day <= int(fd.raids.get("grace_days", 4)):
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:raid:%d:%d" % [world_seed, day])
	var chance: float = float(FactionDef.per_level(fd.raids.get("chance", []), level, 0.0)) * float(AGGRESSION.get(aggression, 1.0))
	if rng.randf() >= chance:
		return {}
	var n: int = raid_size(fd, level, gamestage, rng)
	if n <= 0:
		return {}
	var h: Array = fd.raids.get("hour", [18, 20])
	var table: Dictionary = FactionDef.per_level(fd.raids.get("enemies", []), level, {})
	if table.is_empty():
		return {}
	var members: Array[String] = []
	for i: int in n:
		members.append(String(Weighted.pick_key(table, rng)))
	return {"hour": rng.randf_range(float(h[0]), float(h[1])), "size": n, "members": members}


## How many come: the level's band size plus `per_gamestage` per gamestage point, capped.
static func raid_size(fd: FactionDef, level: int, gamestage: int, rng: RandomNumberGenerator) -> int:
	var s: Array = FactionDef.per_level(fd.raids.get("size", []), level, [0, 0])
	var n: int = rng.randi_range(int(s[0]), int(s[s.size() - 1]))
	if n <= 0:
		return 0
	n += int(floor(float(gamestage) * float(fd.raids.get("per_gamestage", 0.0))))
	return mini(n, int(fd.raids.get("max_size", 9)))


# --- Morale -------------------------------------------------------------------------------------

## Morale after a band mate falls.
static func mate_down(fd: FactionDef, morale: float, home: bool) -> float:
	return _floor(fd, morale - float(fd.morale.get("mate_down", 0.2)), home)


## Morale after losing `fraction` of full health in one blow.
static func hurt(fd: FactionDef, morale: float, fraction: float, home: bool) -> float:
	return _floor(fd, morale - float(fd.morale.get("hurt", 0.5)) * clampf(fraction, 0.0, 1.0), home)


## Morale after `dt` seconds near a fire of `fear` (0-1), recovering when there is none.
static func near_fire(fd: FactionDef, morale: float, fear: float, dt: float, home: bool) -> float:
	if fear <= 0.0:
		return minf(1.0, morale + float(fd.morale.get("recover_per_s", 0.01)) * dt)
	return _floor(fd, morale - float(fd.fire.get("morale_per_s", 0.06)) * fear * dt, home)


static func breaks(fd: FactionDef, morale: float) -> bool:
	return morale < float(fd.morale.get("break", 0.3))


## Inside their own camp's territory they never fall below home_floor: they defend home to the end.
static func _floor(fd: FactionDef, m: float, home: bool) -> float:
	return clampf(m, float(fd.morale.get("home_floor", 0.6)) if home else 0.0, 1.0)


# --- Fire ---------------------------------------------------------------------------------------

## How much a fire frightens a fighter at `pos` (0-1). `flame` is the player's held flame (its
## position, or Vector3.INF when none), `facing` the player's flat look direction, `fires` the
## player's lit fires and stations. A held flame only counts in front of the player: one behind
## them still comes on.
static func fire_fear(fd: FactionDef, pos: Vector3, flame: Vector3, facing: Vector3, fires: Array) -> float:
	var fear: float = 0.0
	var r: float = float(fd.fire.get("radius", 9.0))
	if flame != Vector3.INF:
		var to_me := Vector3(pos.x - flame.x, 0.0, pos.z - flame.z)
		var d: float = to_me.length()
		if d < r:
			var ang: float = rad_to_deg(Vector3(facing.x, 0.0, facing.z).angle_to(to_me)) if to_me.length() > 0.01 and facing.length() > 0.01 else 0.0
			if ang < float(fd.fire.get("behind_angle", 100.0)):
				fear = maxf(fear, 1.0 - d / r)
	var sr: float = float(fd.fire.get("station_radius", 7.0))
	for f: Variant in fires:
		var fp: Vector3 = f
		var d2: float = Vector2(pos.x - fp.x, pos.z - fp.z).length()
		if d2 < sr:
			fear = maxf(fear, (1.0 - d2 / sr) * 0.8)
	return fear


## The nearest fire point a fighter must keep off (`keep_off` m), or Vector3.INF.
static func fire_to_avoid(fd: FactionDef, pos: Vector3, flame: Vector3, fires: Array) -> Vector3:
	var keep: float = float(fd.fire.get("keep_off", 4.0))
	var best := Vector3.INF
	var best_d: float = keep
	var pts: Array = fires.duplicate()
	if flame != Vector3.INF:
		pts.append(flame)
	for f: Variant in pts:
		var fp: Vector3 = f
		var d: float = Vector2(pos.x - fp.x, pos.z - fp.z).length()
		if d < best_d:
			best = fp
			best_d = d
	return best
