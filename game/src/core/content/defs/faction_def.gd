class_name FactionDef
extends ContentDef
## A human faction (ADR-0048): the Ashen. Where it lives (`camps`: POI defs whose placed buildings
## are its camps, with their residents and territory), how it escalates against the player
## (`hostility` gains and decay, `levels` with the gamestage each needs), and how its scouts, raids,
## morale and fear of fire are tuned. AshenDirector runs it; AshenBrain holds the arithmetic.

## [{poi: def id, residents: {enemy id: [lo, hi]}, territory: m, wake_range: m, sleep_range: m}]
var camps: Array = []
## [{name, at: hostility, gamestage: min gamestage}], rising; index = level (0 = unaware).
var levels: Array = []
## {gain: {event: points}, decay_per_day: points, max: points}
var hostility: Dictionary = {}
## {chance: [per level], ring: [min, max] m, observe: s, spotted_range: m, flee_range: m,
##  vantage: [min, max] m, enemy: id}
var scouts: Dictionary = {}
## {chance: [per level], grace_days, hour: [from, to], ring: [min, max] m, size: [[lo, hi] per level],
##  per_gamestage: extra fighters per gamestage point, max_size, enemies: [{enemy: weight} per level],
##  give_up: s, base_range: m, dark_side: deg, flow: {radius, cell, structure_cost_per_hp, fire_cost,
##  slope_max_deg}, sack_pieces, gardens: {loot_crops, trample, trample_damage 0-1, looters, reach: m}}
var raids: Dictionary = {}
## {mate_down, hurt (per fraction of health lost), break, home_floor, recover_per_s}
var morale: Dictionary = {}
## {radius, keep_off, morale_per_s, behind_angle}
var fire: Dictionary = {}
## {other faction (EnemyDef.FACTIONS): "hostile" | "neutral"} (ADR-0048 phase 2, TD-186). Unlisted
## factions are neutral. Hostility is symmetric: one side saying "hostile" is enough (the Hollowed
## have no FactionDef, so the Ashen's `hollowed: hostile` is what turns the Hollowed on them too).
var relations: Dictionary = {}

const RELATIONS: PackedStringArray = ["hostile", "neutral"]
const GAIN_EVENTS: PackedStringArray = ["kill", "trespass", "scout_report", "scout_killed", "camp_wiped", "heat", "raid_repelled"]


func _fields() -> PackedStringArray:
	return ["camps", "levels", "hostility", "scouts", "raids", "morale", "fire", "relations"]


func _parse(r: DefReader) -> void:
	camps = r.arr("camps")
	levels = r.arr("levels")
	hostility = r.dict("hostility")
	scouts = r.dict("scouts")
	raids = r.dict("raids")
	morale = r.dict("morale")
	fire = r.dict("fire")
	relations = r.dict("relations")


func _validate(db: Node, out: PackedStringArray) -> void:
	for f: Variant in relations.keys():
		if not EnemyDef.FACTIONS.has(str(f)) or str(f) == String(id):
			out.append("%s: relation to '%s' (not another of %s)" % [ctx(), f, EnemyDef.FACTIONS])
		elif not RELATIONS.has(str(relations[f])):
			out.append("%s: relation '%s' to %s is not one of %s" % [ctx(), relations[f], f, RELATIONS])
	for c: Variant in camps:
		var cd: Dictionary = c
		if not db.has_def(&"poi", StringName(str(cd.get("poi", "")))):
			out.append("%s: camp poi '%s' unknown" % [ctx(), cd.get("poi", "")])
		var res: Dictionary = cd.get("residents", {})
		if res.is_empty():
			out.append("%s: camp '%s' has no residents" % [ctx(), cd.get("poi", "")])
		for e: Variant in res.keys():
			_check_member(db, str(e), out)
		if float(cd.get("sleep_range", 180.0)) <= float(cd.get("wake_range", 150.0)):
			out.append("%s: camp '%s' sleep_range must be past wake_range" % [ctx(), cd.get("poi", "")])
	var prev: float = -1.0
	for l: Variant in levels:
		var at: float = float((l as Dictionary).get("at", 0.0))
		if at <= prev:
			out.append("%s: levels must rise" % ctx())
		prev = at
	if levels.is_empty():
		out.append("%s: no levels" % ctx())
	for k: Variant in (hostility.get("gain", {}) as Dictionary).keys():
		if not str(k) in GAIN_EVENTS:
			out.append("%s: hostility gain '%s' is not one of %s" % [ctx(), k, GAIN_EVENTS])
	if scouts.has("enemy"):
		_check_member(db, str(scouts["enemy"]), out)
	for tbl: Variant in raids.get("enemies", []):
		for e2: Variant in (tbl as Dictionary).keys():
			_check_member(db, str(e2), out)
	var g: Dictionary = raids.get("gardens", {})
	if float(g.get("trample_damage", 0.0)) < 0.0 or float(g.get("trample_damage", 0.0)) > 1.0 or int(g.get("looters", 0)) < 0:
		out.append("%s: raids.gardens trample_damage must be 0-1 and looters 0 or more" % ctx())
	for key: String in ["chance"]:
		for src: Dictionary in [scouts, raids]:
			if src.has(key) and (src[key] as Array).size() != levels.size():
				out.append("%s: %s needs one value per level" % [ctx(), key])


func _check_member(db: Node, enemy_id: String, out: PackedStringArray) -> void:
	var ed: EnemyDef = db.get_def(&"enemy", StringName(enemy_id)) as EnemyDef
	if ed == null:
		out.append("%s: enemy '%s' unknown" % [ctx(), enemy_id])
	elif ed.faction != String(id):
		out.append("%s: enemy '%s' is faction %s, not %s" % [ctx(), enemy_id, ed.faction, id])


## Whether bodies of factions `a` and `b` fight each other: never within a faction; otherwise when
## either side's FactionDef lists the other as hostile (symmetric). Safe from any thread.
static func hostile(a: String, b: String) -> bool:
	if a == b:
		return false
	return _says_hostile(a, b) or _says_hostile(b, a)


static func _says_hostile(a: String, b: String) -> bool:
	var db: Node = ContentDB.instance
	var fd: FactionDef = db.call(&"get_def", &"faction", StringName(a)) as FactionDef if db != null else null
	return fd != null and str(fd.relations.get(b, "neutral")) == "hostile"


## The camp entry for a POI def ({} when the def is not one of this faction's camps).
func camp_for(poi_def: StringName) -> Dictionary:
	for c: Variant in camps:
		if str((c as Dictionary).get("poi", "")) == String(poi_def):
			return c
	return {}


## Per-level value of a list in scouts/raids (clamped to the last entry).
static func per_level(list: Array, level: int, default: Variant) -> Variant:
	if list.is_empty():
		return default
	return list[clampi(level, 0, list.size() - 1)]
