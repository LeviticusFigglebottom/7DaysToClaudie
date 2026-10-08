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
## {radius: m round the ordered spot he gathers within, slots: his pack's slots (carry caps apply:
##  two logs on the shoulder), share: of the player's XP and directive credit for what he fells,
##  kinds: {kind: [item ids he gathers for it]}, max_tree_hp: the biggest tree he fells (species hp),
##  chop: tool power of his blows, reach: m, give_up: s walking at one target before he skips it,
##  settle: s he waits for a felled tree to land} (ADR-0058 phase 2).
var gather: Dictionary = {}
## {range: m from the player a fetch target may lie}
var fetch: Dictionary = {}
## {range: m from him the storage piece "Store at base" uses may stand}
var store: Dictionary = {}
## {event: [lines]}; events in BARKS.
var barks: Dictionary = {}
## His voice (ADR-0058 phase 3): {gap: s between voiced barks, repeat: s an event keeps quiet after
##  it was said, lines: {event: "sound id" | "sound id:N" (variant N, 1-based) | "sound id:line"
##  (the variant matching the bark line shown)}}. A missing sound is silent (the line still shows).
var voice: Dictionary = {}
## His perks (ADR-0058 phase 3, a lineman): [{id, name, text, after_days: days with the player
##  before it shows, effects: {key in PERK_EFFECTS: number}}].
var perks: Array = []

const BARKS: PackedStringArray = ["recruited", "follow", "stay", "guard", "spotted", "downed", "revived", "out", "back", "hurt",
	"gather", "fetch", "store", "full", "done", "fetched", "cant_reach", "stored", "store_full", "given"]
## What a perk may change: slots (+ his pack's slots), carry_log (+ logs on his shoulder),
## chop_speed (x his chop clip's speed), chop_power (x his blows' tool power), fuel_use (x a running
## generator's fuel burn while he is within tune_range m of it), tune_range (m).
const PERK_EFFECTS: PackedStringArray = ["slots", "carry_log", "chop_speed", "chop_power", "fuel_use", "tune_range"]


func _fields() -> PackedStringArray:
	return ["enemy", "camp", "recruit_items", "revive_items", "revive_hold", "revive_health", "recruit_health",
		"return_health", "follow", "guard", "downed", "lantern", "gather", "fetch", "store", "barks", "voice", "perks"]


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
	gather = r.dict("gather")
	fetch = r.dict("fetch")
	store = r.dict("store")
	barks = r.dict("barks")
	voice = r.dict("voice")
	perks = r.arr("perks")


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
	var kinds: Dictionary = gather.get("kinds", {})
	if kinds.is_empty():
		out.append("%s: gather.kinds must name at least one kind" % ctx())
	for k: Variant in kinds:
		for it: Variant in kinds[k]:
			if not db.has_def(&"item", StringName(str(it))):
				out.append("%s: gather kind '%s': item '%s' unknown" % [ctx(), k, it])
	for k2: Variant in (voice.get("lines", {}) as Dictionary).keys():
		if not BARKS.has(str(k2)):
			out.append("%s: voice line '%s' is not one of %s" % [ctx(), k2, BARKS])
	for v: Variant in perks:
		if not v is Dictionary or str((v as Dictionary).get("id", "")) == "":
			out.append("%s: a perk needs an id" % ctx())
			continue
		for e: Variant in ((v as Dictionary).get("effects", {}) as Dictionary).keys():
			if not PERK_EFFECTS.has(str(e)):
				out.append("%s: perk '%s': effect '%s' is not one of %s" % [ctx(), v["id"], e, PERK_EFFECTS])
	if fnum(gather, "slots", 12.0) < 1.0 or fnum(gather, "radius", 30.0) <= 0.0 or fnum(fetch, "range", 60.0) <= 0.0:
		out.append("%s: gather.slots, gather.radius and fetch.range must be > 0" % ctx())


## The share of the player's XP and directive credit a deed by `source_id` earns: 1 for anyone but
## a companion (`companion:<def id>`), whose gathering counts at his def's gather.share (half).
static func share_for(source_id: StringName) -> float:
	var s: String = String(source_id)
	if not s.begins_with("companion:"):
		return 1.0
	var db: Node = ContentDB.instance
	var cd: CompanionDef = db.call(&"get_def", &"companion", StringName(s.substr(10))) as CompanionDef if db != null else null
	return clampf(fnum(cd.gather, "share", 0.5), 0.0, 1.0) if cd != null else 0.5


## The items a gather kind brings in ([] for an unknown kind).
func gather_items(kind: String) -> PackedStringArray:
	var out: PackedStringArray = []
	for it: Variant in (gather.get("kinds", {}) as Dictionary).get(kind, []):
		out.append(str(it))
	return out


static func fnum(d: Dictionary, key: String, default: float) -> float:
	return float(d.get(key, default))


## The perks he has after `days` with the player (after_days <= days).
func perks_after(days: int) -> Array:
	return perks.filter(func(p: Variant) -> bool: return p is Dictionary and int((p as Dictionary).get("after_days", 0)) <= days)


## An effect summed (slots, carry_log, tune_range) or multiplied (chop_speed, chop_power, fuel_use)
## over `active` perks; `none` when no perk names it.
static func perk_effect(active: Array, key: String, none: float) -> float:
	var add: bool = key in ["slots", "carry_log", "tune_range"]
	var v: float = 0.0 if add else 1.0
	var found: bool = false
	for p: Variant in active:
		var fx: Dictionary = (p as Dictionary).get("effects", {})
		if fx.has(key):
			found = true
			v = v + float(fx[key]) if add else v * float(fx[key])
	return v if found else none


## A line for an event (deterministic by `n`), "" when it has none.
func bark(event: String, n: int = 0) -> String:
	var lines: Array = barks.get(event, [])
	return "" if lines.is_empty() else str(lines[posmod(n, lines.size())])
