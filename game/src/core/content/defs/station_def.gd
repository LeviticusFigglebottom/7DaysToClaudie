class_name StationDef
extends ContentDef
## A crafting station (campfire, workbench, forge, chemistry bench, grill).

## Structure def placed in the world that hosts this station.
var structure: StringName = &""
## Needs fuel to operate (campfire, forge).
var needs_fuel: bool = false
## Attention generated per minute while active (heat system).
var heat_per_minute: float = 0.0
## Light/warmth radius while lit (m); 0 = none.
var warmth_radius: float = 0.0


func _fields() -> PackedStringArray:
	return ["structure", "needs_fuel", "heat_per_minute", "warmth_radius"]


func _parse(r: DefReader) -> void:
	structure = r.sname("structure")
	needs_fuel = r.boolean("needs_fuel", false)
	heat_per_minute = r.num("heat_per_minute", 0.0)
	warmth_radius = r.num("warmth_radius", 0.0)


func _validate(db: Node, out: PackedStringArray) -> void:
	if structure != &"" and not db.has_def(&"structure", structure):
		out.append("%s: structure '%s' unknown" % [ctx(), structure])
