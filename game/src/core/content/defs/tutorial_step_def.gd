class_name TutorialStepDef
extends ContentDef
## One step of the optional "first days" tutorial (ADR-0062): a Remand Program card on the tether's
## journal that says how to make or do one essential early thing. Steps are listed by `order`;
## progress comes from the same gameplay events the directives count (TutorialTracker), plus
## `gather` (an item picked up or harvested). `body` names keys with `{key:<action>}` placeholders,
## shown as the key the action is bound to now (TutorialTracker.render_body).

## The events a step can wait for: DirectiveDef's names where they mean the same thing, plus
## gather. Each has a hook in TutorialTracker.setup_world.
const EVENTS: PackedStringArray = ["gather", "craft", "build", "fell_tree", "place_log", "sleep", "loot", "enter_poi",
	"read_note", "kill", "recruit"]
## Content kind each event's targets must name (build accepts a blueprint or a structure).
const TARGET_KIND: Dictionary = {"gather": &"item", "craft": &"item", "kill": &"enemy", "enter_poi": &"poi",
	"recruit": &"poi"}
## `{key:interact}` -> the key interact is bound to.
const KEY_PATTERN: String = "\\{key:([a-z0-9_]+)\\}"

## Where the step stands in the list (ascending; unique).
var order: int = 0
var body: String = ""
var event: String = "craft"
## Ids that count (the item gathered or crafted, the blueprint or structure built...). Empty = any.
var targets: PackedStringArray = []
## How many (for gather: items picked up, summed over the targets).
var count: int = 1


func _fields() -> PackedStringArray:
	return ["order", "title", "body", "event", "targets", "count"]


func _parse(r: DefReader) -> void:
	order = r.integer("order", 0)
	display_name = r.req_str("title")
	body = r.req_str("body")
	event = r.enum_str("event", EVENTS, "craft")
	targets = r.strings("targets")
	count = maxi(1, r.integer("count", 1))


func _validate(db: Node, out: PackedStringArray) -> void:
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
	var actions: Dictionary = (db.call(&"config", &"input_bindings") as Dictionary).get("actions", {})
	for action: String in key_actions(body):
		if not actions.has(action):
			out.append("%s: body names key '{key:%s}', which is not an input action" % [ctx(), action])
	for other: ContentDef in db.call(&"all", &"tutorial_step"):
		if other != self and (other as TutorialStepDef).order == order and String(other.id) < String(id):
			out.append("%s: order %d is also %s's" % [ctx(), order, other.id])


## The input actions a text's `{key:...}` placeholders name.
static func key_actions(text: String) -> PackedStringArray:
	var out: PackedStringArray = []
	var re := RegEx.create_from_string(KEY_PATTERN)
	for m: RegExMatch in re.search_all(text):
		out.append(m.get_string(1))
	return out
