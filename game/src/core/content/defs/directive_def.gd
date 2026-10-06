class_name DirectiveDef
extends ContentDef
## A Remand Program directive (our take on 7 Days to Die's challenges): one short goal inside a
## chapter. Chapters open in order; finishing every directive of one opens the next. Progress
## comes from gameplay events (DirectiveTracker), rewards are XP and items (ADR-0015).

const EVENTS: PackedStringArray = ["fell_tree", "craft", "place_log", "build", "loot", "kill", "enter_poi",
	"clear_poi", "survive_hum", "read_note", "level", "sleep", "supply_drop", "disarm_trap", "contract", "raid", "harvest"]
const TIERS: PackedStringArray = ["", "normal", "seeded", "bloomed"]
## Content kind each event's targets must name (build accepts a blueprint or a structure).
const TARGET_KIND: Dictionary = {"craft": &"item", "kill": &"enemy", "enter_poi": &"poi", "clear_poi": &"poi",
	"contract": &"quest", "harvest": &"crop"}

var chapter: int = 1
var chapter_name: String = ""
var order: int = 0
var event: String = "fell_tree"
## Ids that count: the item crafted, the enemy killed, the blueprint/structure built, the POI
## entered or cleared. Empty = any.
var targets: PackedStringArray = []
## kill only: the weakest infected tier that counts ("" = any).
var min_tier: String = ""
## How many times (for "level": the level to reach).
var count: int = 1
var reward_xp: int = 0
## item id -> count
var reward_items: Dictionary = {}


func _fields() -> PackedStringArray:
	return ["chapter", "chapter_name", "order", "event", "targets", "min_tier", "count", "reward"]


func _parse(r: DefReader) -> void:
	chapter = maxi(1, r.integer("chapter", 1))
	chapter_name = r.str_field("chapter_name", "")
	order = r.integer("order", 0)
	event = r.enum_str("event", EVENTS, "fell_tree")
	targets = r.strings("targets")
	min_tier = r.enum_str("min_tier", TIERS, "")
	count = maxi(1, r.integer("count", 1))
	var rw := DefReader.new(r.dict("reward"), "%s reward" % ctx())
	reward_xp = maxi(0, rw.integer("xp", 0))
	reward_items = rw.dict("items")
	rw.check_unknown(["xp", "items"])
	r.errors.append_array(rw.errors)


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: Variant in reward_items.keys():
		if not db.has_def(&"item", StringName(str(k))):
			out.append("%s: reward item '%s' unknown" % [ctx(), k])
	for t: String in targets:
		var id := StringName(t)
		if event == "build":
			if not db.has_def(&"blueprint", id) and not db.has_def(&"structure", id):
				out.append("%s: build target '%s' is neither a blueprint nor a structure" % [ctx(), t])
		elif TARGET_KIND.has(event):
			if not db.has_def(TARGET_KIND[event], id):
				out.append("%s: %s target '%s' unknown" % [ctx(), event, t])
		else:
			out.append("%s: event '%s' takes no targets" % [ctx(), event])
	if min_tier != "" and event != "kill":
		out.append("%s: min_tier only applies to kill" % ctx())


## "3 / 5"-style goal text for the tether and the Record tab.
func goal_text(progress: int) -> String:
	if event == "level":
		return "level %d" % count
	return "%d/%d" % [mini(progress, count), count] if count > 1 else ""
