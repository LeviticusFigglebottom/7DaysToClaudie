class_name RecipeDef
extends ContentDef
## A crafting recipe. Hand recipes (station == "") are crafted on the salvage roll by laying the
## exact ingredients on the work slate; station recipes are picked from the station's list.

var result: StringName
var result_count: int = 1
## {item_id(StringName): count(int)}
var ingredients: Dictionary = {}
## Station id ("" = by hand on the salvage roll).
var station: StringName = &""
var time: float = 1.0
## "default" | "schematic" (learned via an item's teaches.recipe) | "perk:<perk_id>:<rank>" | "skill:<skill_id>:<points>"
var unlock: String = "default"
var category: String = "misc"
## Tools that must be present in the inventory (not consumed), e.g. ["knife"].
var tools_required: PackedStringArray = []


func _fields() -> PackedStringArray:
	return ["result", "count", "ingredients", "station", "time", "unlock", "category", "tools"]


func _parse(r: DefReader) -> void:
	result = StringName(r.req_str("result"))
	result_count = maxi(1, r.integer("count", 1))
	var ing: Dictionary = r.dict("ingredients")
	for k: Variant in ing.keys():
		var c: Variant = ing[k]
		if not (c is int or c is float) or int(c) <= 0:
			r.err("ingredient '%s' needs a positive count" % k)
			continue
		ingredients[StringName(k)] = int(c)
	if ingredients.is_empty():
		r.err("recipe needs at least one ingredient")
	station = r.sname("station")
	time = r.num("time", 1.0)
	unlock = r.str_field("unlock", "default")
	category = r.str_field("category", "misc")
	tools_required = r.strings("tools")


func _validate(db: Node, out: PackedStringArray) -> void:
	if not db.has_def(&"item", result):
		out.append("%s: result '%s' is not an item" % [ctx(), result])
	for k: StringName in ingredients:
		if not db.has_def(&"item", k):
			out.append("%s: ingredient '%s' is not an item" % [ctx(), k])
	if station != &"" and not db.has_def(&"station", station):
		out.append("%s: station '%s' unknown" % [ctx(), station])
	if unlock.begins_with("perk:"):
		var parts: PackedStringArray = unlock.split(":")
		if parts.size() != 3 or not db.has_def(&"perk", StringName(parts[1])):
			out.append("%s: unlock '%s' must be perk:<known_perk>:<rank>" % [ctx(), unlock])
	elif unlock not in ["default", "schematic"] and not unlock.begins_with("skill:"):
		out.append("%s: unlock '%s' invalid" % [ctx(), unlock])
	for t: String in tools_required:
		if not ItemDef.TOOL_KINDS.has(t):
			out.append("%s: unknown tool kind '%s'" % [ctx(), t])


func is_hand_recipe() -> bool:
	return station == &""
