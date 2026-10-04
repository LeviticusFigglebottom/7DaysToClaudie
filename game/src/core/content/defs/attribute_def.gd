class_name AttributeDef
extends ContentDef
## A core attribute (Sinew, Grit, Keen, Quiet, Wits). Perks hang off attributes.

var max_level: int = 10
var color: Color = Color.WHITE
## Passive effects per attribute level: {stat_key: per_level_amount}
var per_level: Dictionary = {}


func _fields() -> PackedStringArray:
	return ["max_level", "color", "per_level"]


func _parse(r: DefReader) -> void:
	max_level = r.integer("max_level", 10)
	color = r.color("color", Color.WHITE)
	per_level = r.dict("per_level")
