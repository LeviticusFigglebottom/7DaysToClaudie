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
## `anger` is the leading camp's effective anger (lead_anger): an angry camp near the player sends
## them more often (standing.chance_per_anger).
static func scout_roll(fd: FactionDef, world_seed: int, day: int, level: int, aggression: String = "normal",
		anger: float = 0.0) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:scout:%d:%d" % [world_seed, day])
	var chance: float = float(FactionDef.per_level(fd.scouts.get("chance", []), level, 0.0)) * float(AGGRESSION.get(aggression, 1.0)) \
		* anger_chance(fd, anger)
	if rng.randf() >= chance:
		return {}
	var h: Array = fd.scouts.get("hour", [8, 17])
	return {"hour": rng.randf_range(float(h[0]), float(h[1]))}


## The day's raid, or {}: {hour, size, members: [enemy ids]}. Never in the grace days, never on a
## Hum day (`hum_day`). Deterministic per world and day.
## `anger` (the leading camp's effective anger) raises the chance (standing.chance_per_anger) and
## adds a raider per standing.size_per_anger.
static func raid_roll(fd: FactionDef, world_seed: int, day: int, level: int, gamestage: int, hum_day: bool,
		aggression: String = "normal", anger: float = 0.0) -> Dictionary:
	if hum_day or day <= int(fd.raids.get("grace_days", 4)):
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:raid:%d:%d" % [world_seed, day])
	var chance: float = float(FactionDef.per_level(fd.raids.get("chance", []), level, 0.0)) * float(AGGRESSION.get(aggression, 1.0)) \
		* anger_chance(fd, anger)
	if rng.randf() >= chance:
		return {}
	var n: int = raid_size(fd, level, gamestage, rng)
	if n <= 0:
		return {}
	n = mini(n + anger_size(fd, anger), int(fd.raids.get("max_size", 9)))
	var h: Array = fd.raids.get("hour", [18, 20])
	var table: Dictionary = FactionDef.per_level(fd.raids.get("enemies", []), level, {})
	if table.is_empty():
		return {}
	var members: Array[String] = []
	# The level's `with` fighters come first (a war party's firebrand), then the rest are rolled.
	var musts: Dictionary = FactionDef.per_level(fd.raids.get("with", []), level, {})
	var must_ids: Array = musts.keys()
	must_ids.sort()
	for k: Variant in must_ids:
		for j: int in int(musts[k]):
			if members.size() < n:
				members.append(str(k))
	while members.size() < n:
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


# --- Per-camp standing (TD-190) ---------------------------------------------------------------------

## A camp's anger after an event tied to it (`FactionDef.STANDING_EVENTS`), `times` over, scaled
## by the aggression setting, capped at standing.max.
static func anger(fd: FactionDef, current: float, event: String, times: float = 1.0, aggression: String = "normal") -> float:
	var g: float = float((fd.standing.get("anger", {}) as Dictionary).get(event, 0.0)) * times * float(AGGRESSION.get(aggression, 1.0))
	return clampf(current + g, 0.0, float(fd.standing.get("max", 100.0)))


## A camp's anger at the next dawn: it fades by decay_per_day.
static func anger_at_dawn(fd: FactionDef, current: float) -> float:
	return maxf(0.0, current - float(fd.standing.get("decay_per_day", 0.0)))


## How much a camp `dist` m from the player counts (standing.reach {near, far, floor}): fully
## within `near`, falling to `floor` at `far` and beyond. A camp across the map is a rumour; the
## one over the ridge is a threat.
static func reach(fd: FactionDef, dist: float) -> float:
	var r: Dictionary = fd.standing.get("reach", {})
	if r.is_empty() or dist < 0.0:
		return 1.0
	var near: float = float(r.get("near", 300.0))
	var far: float = maxf(near + 1.0, float(r.get("far", 1500.0)))
	return lerpf(1.0, float(r.get("floor", 0.25)), clampf((dist - near) / (far - near), 0.0, 1.0))


## The raid and scout chance multiplier for a leading camp's effective anger: 1 + anger x
## standing.chance_per_anger, at most standing.chance_max.
static func anger_chance(fd: FactionDef, anger: float) -> float:
	return minf(1.0 + maxf(0.0, anger) * float(fd.standing.get("chance_per_anger", 0.0)), float(fd.standing.get("chance_max", 1.0)))


## Extra raiders for a leading camp's effective anger: one per standing.size_per_anger (0: none).
static func anger_size(fd: FactionDef, anger: float) -> int:
	var per: float = float(fd.standing.get("size_per_anger", 0.0))
	return int(floor(maxf(0.0, anger) / per)) if per > 0.0 else 0


## The camp a band comes from: of `ids` (the placed camps), the living one (not wiped) with the
## most effective anger (its anger x reach of its distance in `dists`, id -> m; missing = near) in
## `camp_states` (WorldState.ashen.camps), at least standing.lead; ties by id. "" for none.
static func angriest(fd: FactionDef, camp_states: Dictionary, ids: Array, dists: Dictionary = {}) -> String:
	var lead: float = float(fd.standing.get("lead", 5.0))
	var best: String = ""
	var best_a: float = -1.0
	var sorted: Array = ids.duplicate()
	sorted.sort()
	for id: Variant in sorted:
		var cs: Dictionary = camp_states.get(str(id), {})
		var a: float = float(cs.get("anger", 0.0)) * reach(fd, float(dists.get(str(id), -1.0)))
		if bool(cs.get("wiped", false)) or a < lead:
			continue
		if a > best_a:
			best = str(id)
			best_a = a
	return best


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
