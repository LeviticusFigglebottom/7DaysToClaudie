class_name PerkDef
extends ContentDef
## A perk with ranks. Each rank requires an attribute level and grants effects (modifier keys
## consumed by systems through Progression.modifier(key)).

var attribute: StringName
## [{attr_level:int, effects:{key: value}, unlocks:[recipe ids]}]
var ranks: Array[Dictionary] = []


func _fields() -> PackedStringArray:
	return ["attribute", "ranks"]


func _parse(r: DefReader) -> void:
	attribute = StringName(r.req_str("attribute"))
	for rk: Variant in r.arr("ranks"):
		if not rk is Dictionary:
			r.err("ranks must be objects")
			continue
		var rr := DefReader.new(rk, "%s rank" % ctx())
		ranks.append({
			"attr_level": rr.integer("attr_level", 1),
			"effects": rr.dict("effects"),
			"unlocks": rr.strings("unlocks"),
			"text": rr.str_field("text", ""),
		})
		rr.check_unknown(["attr_level", "effects", "unlocks", "text"])
		r.errors.append_array(rr.errors)
	if ranks.is_empty():
		r.err("perk needs at least one rank")


func _validate(db: Node, out: PackedStringArray) -> void:
	if not db.has_def(&"attribute", attribute):
		out.append("%s: attribute '%s' unknown" % [ctx(), attribute])
	for rk: Dictionary in ranks:
		for u: String in rk["unlocks"]:
			if not db.has_def(&"recipe", StringName(u)) and not db.has_def(&"blueprint", StringName(u)):
				out.append("%s: rank unlocks unknown recipe/blueprint '%s'" % [ctx(), u])


func max_rank() -> int:
	return ranks.size()
