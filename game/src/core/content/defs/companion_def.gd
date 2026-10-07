class_name CompanionDef
extends ContentDef
## A companion (ADR-0058): Ezra Vane. His body is an EnemyDef of archetype `companion` (`enemy`:
## navigation, hit zones, damage, the living animation set and EnemyFoes all apply); this def
## holds what makes him a companion: where he waits to be found (`camp`: a POI def), what recruits
## and revives him, how he follows, guards and lights the way, how long he lasts downed, and his
## barks. CompanionDirector and CompanionMind run it.

## The EnemyDef his body is (archetype `companion`).
var enemy: StringName = &""
## {poi: def id of his camp, offset: [x, z] building-local where he sits, yaw: deg (building-local),
##  wake_range: m (he is placed when the player comes this close), sleep_range: m}
var camp: Dictionary = {}
## Items any one of which, given to him at his camp, recruits him (consumed).
var recruit_items: PackedStringArray = []
## Items any one of which revives him while downed (consumed), and the hold time (s).
var revive_items: PackedStringArray = []
var revive_hold: float = 4.0
## Health fraction he gets up with: revived, recruited, back the next dawn.
var revive_health: float = 0.35
var recruit_health: float = 0.6
var return_health: float = 0.5
## {min, max: m behind the player he keeps, run_beyond: m (runs to catch up), teleport_beyond: m
##  (placed beside the player out of sight), leash: m (a fight is dropped past this from the player),
##  engage: m (he takes on hostiles hunting within this of the player)}
var follow: Dictionary = {}
## {radius: m round the spot he engages within, leash: m}
var guard: Dictionary = {}
## {seconds: bleed-out}
var downed: Dictionary = {}
## {range, energy, color: [r, g, b]}: the lantern he carries at night while following.
var lantern: Dictionary = {}
## {event: [lines]}; events in BARKS.
var barks: Dictionary = {}

const BARKS: PackedStringArray = ["recruited", "follow", "stay", "guard", "spotted", "downed", "revived", "out", "back", "hurt"]


func _fields() -> PackedStringArray:
	return ["enemy", "camp", "recruit_items", "revive_items", "revive_hold", "revive_health", "recruit_health",
		"return_health", "follow", "guard", "downed", "lantern", "barks"]


func _parse(r: DefReader) -> void:
	enemy = r.sname("enemy")
	camp = r.dict("camp")
	recruit_items = r.strings("recruit_items")
	revive_items = r.strings("revive_items")
	revive_hold = r.num("revive_hold", 4.0)
	revive_health = clampf(r.num("revive_health", 0.35), 0.05, 1.0)
	recruit_health = clampf(r.num("recruit_health", 0.6), 0.05, 1.0)
	return_health = clampf(r.num("return_health", 0.5), 0.05, 1.0)
	follow = r.dict("follow")
	guard = r.dict("guard")
	downed = r.dict("downed")
	lantern = r.dict("lantern")
	barks = r.dict("barks")


func _validate(db: Node, out: PackedStringArray) -> void:
	var ed: EnemyDef = db.get_def(&"enemy", enemy) as EnemyDef
	if ed == null:
		out.append("%s: enemy '%s' unknown" % [ctx(), enemy])
	elif ed.archetype != "companion":
		out.append("%s: enemy '%s' is archetype %s, not companion" % [ctx(), enemy, ed.archetype])
	if not db.has_def(&"poi", StringName(str(camp.get("poi", "")))):
		out.append("%s: camp poi '%s' unknown" % [ctx(), camp.get("poi", "")])
	for list: PackedStringArray in [recruit_items, revive_items]:
		if list.is_empty():
			out.append("%s: recruit_items and revive_items must not be empty" % ctx())
		for it: String in list:
			if not db.has_def(&"item", StringName(it)):
				out.append("%s: item '%s' unknown" % [ctx(), it])
	for k: Variant in barks.keys():
		if not BARKS.has(str(k)):
			out.append("%s: bark '%s' is not one of %s" % [ctx(), k, BARKS])
	if fnum(follow, "min", 3.0) >= fnum(follow, "max", 6.0) or fnum(follow, "teleport_beyond", 120.0) <= fnum(follow, "max", 6.0):
		out.append("%s: follow needs min < max < teleport_beyond" % ctx())
	if fnum(camp, "sleep_range", 180.0) <= fnum(camp, "wake_range", 150.0):
		out.append("%s: camp sleep_range must be past wake_range" % ctx())
	if fnum(downed, "seconds", 180.0) <= 0.0 or revive_hold <= 0.0:
		out.append("%s: downed.seconds and revive_hold must be > 0" % ctx())


static func fnum(d: Dictionary, key: String, default: float) -> float:
	return float(d.get(key, default))


## A line for an event (deterministic by `n`), "" when it has none.
func bark(event: String, n: int = 0) -> String:
	var lines: Array = barks.get(event, [])
	return "" if lines.is_empty() else str(lines[posmod(n, lines.size())])
