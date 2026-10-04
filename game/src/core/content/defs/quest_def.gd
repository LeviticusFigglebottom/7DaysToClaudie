class_name QuestDef
extends ContentDef
## A Waystation contract / story quest (M2: full quest runtime; M1: data + hooks only).

var quest_type: String = "clear"
var tier: int = 1
## [{type: "clear_poi"|"fetch"|"defend"|"kill"|"deliver", target: id, count: n}]
var objectives: Array = []
## {item_id: count, "scrip": n, "reputation": n, "xp": n}
var rewards: Dictionary = {}
var giver: String = "waystation"
var requires: PackedStringArray = []


func _fields() -> PackedStringArray:
	return ["type", "tier", "objectives", "rewards", "giver", "requires"]


func _parse(r: DefReader) -> void:
	quest_type = r.enum_str("type", ["clear", "fetch", "defend", "kill", "deliver", "story"], "clear")
	tier = r.integer("tier", 1)
	objectives = r.arr("objectives")
	rewards = r.dict("rewards")
	giver = r.str_field("giver", "waystation")
	requires = r.strings("requires")
