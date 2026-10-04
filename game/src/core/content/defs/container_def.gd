class_name ContainerDef
extends ContentDef
## A loot container type (kitchen cabinet != gun safe != medicine cabinet).

var loot_table: StringName
var slots: int = 8
## Seconds to search.
var search_time: float = 1.0
## Noise made when searched (stimulus loudness units, see docs/AI.md).
var noise: float = 4.0
## Prop id used to present it (props/*.json); "" = invisible volume (e.g. floor pile).
var prop: StringName = &""
var locked: bool = false
## Multiplier applied to loot quality/quantity by POI tier.
var tier_scaling: float = 1.0


func _fields() -> PackedStringArray:
	return ["loot_table", "slots", "search_time", "noise", "prop", "locked", "tier_scaling"]


func _parse(r: DefReader) -> void:
	loot_table = StringName(r.req_str("loot_table"))
	slots = r.integer("slots", 8)
	search_time = r.num("search_time", 1.0)
	noise = r.num("noise", 4.0)
	prop = r.sname("prop")
	locked = r.boolean("locked", false)
	tier_scaling = r.num("tier_scaling", 1.0)


func _validate(db: Node, out: PackedStringArray) -> void:
	if not db.has_def(&"loot_table", loot_table):
		out.append("%s: loot_table '%s' unknown" % [ctx(), loot_table])
	if prop != &"" and not db.has_def(&"prop", prop):
		out.append("%s: prop '%s' unknown" % [ctx(), prop])
