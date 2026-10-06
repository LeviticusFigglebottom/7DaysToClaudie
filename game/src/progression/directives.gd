class_name Directives
extends RefCounted
## A player's Remand Program directives: progress per directive, which are done, and the open
## chapter. Only the open chapter's directives advance, so the chain teaches the loop in order
## (gather and build, then search and fight, then hold through the Hum...). Serializable.

## Infected tier strength for DirectiveDef.min_tier.
const TIER_RANK: Dictionary = {"": 0, "normal": 1, "seeded": 2, "bloomed": 3}
## Events whose targets are buildings (POI defs): those directives are fitted to each world.
const BUILDING_EVENTS: PackedStringArray = ["enter_poi", "clear_poi"]

var progress: Dictionary = {}
var done: Dictionary = {}
var chapter: int = 1
## How this world plays the directives aimed at particular buildings (DirectiveTracker sets them
## from for_world(); not saved: the same world always fits the same way). stand_ins: directive id
## -> {"targets": PackedStringArray of POI def ids that count instead, "name": the building's name}
## for one whose own buildings this world lacks; spent: directive id -> true for one it can't
## offer at all, which no longer holds up its chapter.
var stand_ins: Dictionary = {}
var spent: Dictionary = {}


static func chapters() -> PackedInt32Array:
	var out := PackedInt32Array()
	for d: DirectiveDef in Content.all(&"directive"):
		if not out.has(d.chapter):
			out.append(d.chapter)
	out.sort()
	return out


static func chapter_defs(ch: int) -> Array[DirectiveDef]:
	var out: Array[DirectiveDef] = []
	for d: DirectiveDef in Content.all(&"directive"):
		if d.chapter == ch:
			out.append(d)
	out.sort_custom(func(a: DirectiveDef, b: DirectiveDef) -> bool: return a.order < b.order if a.order != b.order else String(a.id) < String(b.id))
	return out


static func chapter_name(ch: int) -> String:
	for d: DirectiveDef in chapter_defs(ch):
		if d.chapter_name != "":
			return d.chapter_name
	return "Chapter %d" % ch


## The open chapter's directives not done yet (and not spent in this world).
func open() -> Array[DirectiveDef]:
	return chapter_defs(chapter).filter(func(d: DirectiveDef) -> bool: return not done.has(d.id) and not spent.has(d.id))


## The ids that count for a directive in this world: its own targets, or its stand-in's.
func targets_of(d: DirectiveDef) -> PackedStringArray:
	return (stand_ins[d.id] as Dictionary)["targets"] if stand_ins.has(d.id) else d.targets


## A directive's name on the tether and in the Record: a stand-in names its building.
func label(d: DirectiveDef) -> String:
	if not stand_ins.has(d.id):
		return d.display_name
	var where: String = str((stand_ins[d.id] as Dictionary).get("name", ""))
	match d.event:
		"clear_poi":
			return "Clear %s" % where
		"enter_poi":
			return "Go inside %s" % where
	return d.display_name


## Applies how this world plays the building directives (for_world()); a chapter left with only
## spent directives opens the next.
func set_world(fit: Dictionary) -> void:
	stand_ins = fit.get("stand_ins", {})
	spent = fit.get("spent", {})
	_advance()


## How a world plays the directives aimed at particular buildings. `buildings`: every building it
## places, as PoiManager.all_buildings() lists them ({id, def, name, tier, kind, pos}). A directive
## whose own targets stand somewhere in it is unchanged. Otherwise the building of the same tier and
## kind nearest the drop site stands in, ties broken by the world seed; with none, the directive is
## spent, so its chapter can't stall. Returns {"stand_ins": {...}, "spent": {...}} for set_world().
static func for_world(buildings: Array, drop_site: Vector3, world_seed: int) -> Dictionary:
	var present: Dictionary = {}
	for b: Dictionary in buildings:
		present[str(b.get("def", ""))] = true
	var stand_ins_: Dictionary = {}
	var spent_: Dictionary = {}
	for d: DirectiveDef in Content.all(&"directive"):
		if not BUILDING_EVENTS.has(d.event) or d.targets.is_empty():
			continue
		var tiers: Dictionary = {}
		var kinds: Dictionary = {}
		var here: bool = false
		for t: String in d.targets:
			if present.has(t):
				here = true
				break
			var pd: PoiDef = Content.get_def(&"poi", StringName(t)) as PoiDef
			if pd != null:
				tiers[pd.tier] = true
				kinds[building_kind(pd)] = true
		if here:
			continue
		var best: Dictionary = {}
		var best_key: Array = []
		for b: Dictionary in buildings:
			if not tiers.has(int(b.get("tier", 0))) or not kinds.has(str(b.get("kind", ""))):
				continue
			var at: Vector3 = b.get("pos", Vector3.ZERO)
			var key: Array = [snappedf(Vector2(at.x - drop_site.x, at.z - drop_site.z).length(), 0.01),
				Ids.hash64("directive:%d:%s:%s" % [world_seed, d.id, b.get("id", "")])]
			if best.is_empty() or float(key[0]) < float(best_key[0]) or (float(key[0]) == float(best_key[0]) and int(key[1]) < int(best_key[1])):
				best = b
				best_key = key
		if best.is_empty():
			spent_[d.id] = true
		else:
			stand_ins_[d.id] = {"targets": PackedStringArray([str(best["def"])]), "name": str(best.get("name", best["def"]))}
	return {"stand_ins": stand_ins_, "spent": spent_}


## "authored" for a building from content, "generated" for one made from a template (ADR-0030).
static func building_kind(pd: PoiDef) -> String:
	return "generated" if pd.template != &"" else "authored"


## Every chapter's directives finished.
func all_done() -> bool:
	var chs: PackedInt32Array = chapters()
	return chs.is_empty() or (chapter >= chs[chs.size() - 1] and open().is_empty())


func count_of(id: StringName) -> int:
	return int(progress.get(id, 0))


## Feeds one gameplay event. `amount` adds to counts (for "level" it is the level reached).
## Returns the directives this completed (the caller pays their rewards).
func record(event: String, target: StringName = &"", amount: int = 1, tier: StringName = &"") -> Array[DirectiveDef]:
	var out: Array[DirectiveDef] = []
	for d: DirectiveDef in chapter_defs(chapter):
		if done.has(d.id) or spent.has(d.id) or d.event != event:
			continue
		var targets: PackedStringArray = targets_of(d)
		if not targets.is_empty() and not targets.has(String(target)):
			continue
		if d.min_tier != "" and int(TIER_RANK.get(String(tier), 0)) < int(TIER_RANK.get(d.min_tier, 0)):
			continue
		progress[d.id] = maxi(count_of(d.id), amount) if event == "level" else count_of(d.id) + amount
		if count_of(d.id) >= d.count:
			done[d.id] = true
			out.append(d)
	if not out.is_empty():
		_advance()
	return out


## Opens the next chapter once the current one is finished.
func _advance() -> void:
	var chs: PackedInt32Array = chapters()
	while open().is_empty():
		var nxt: int = -1
		for c: int in chs:
			if c > chapter:
				nxt = c
				break
		if nxt < 0:
			return
		chapter = nxt


func to_dict() -> Dictionary:
	var p: Dictionary = {}
	for k: Variant in progress.keys():
		p[String(k)] = progress[k]
	var d: Array = []
	for k: Variant in done.keys():
		d.append(String(k))
	d.sort()
	return {"chapter": chapter, "progress": p, "done": d}


func from_dict(d: Dictionary) -> void:
	chapter = maxi(1, int(d.get("chapter", 1)))
	progress.clear()
	for k: Variant in (d.get("progress", {}) as Dictionary).keys():
		progress[StringName(str(k))] = int(d["progress"][k])
	done.clear()
	for k: Variant in d.get("done", []):
		done[StringName(str(k))] = true
	# Directives added to an older chapter after this save: carry on rather than stall.
	_advance()
