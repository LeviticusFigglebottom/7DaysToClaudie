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
## Game minutes of fuel a newly built one holds (its kindling), and the most it takes.
var start_fuel: float = 0.0
var max_fuel: float = 720.0


func _fields() -> PackedStringArray:
	return ["structure", "needs_fuel", "heat_per_minute", "warmth_radius", "start_fuel", "max_fuel"]


func _parse(r: DefReader) -> void:
	structure = r.sname("structure")
	needs_fuel = r.boolean("needs_fuel", false)
	heat_per_minute = r.num("heat_per_minute", 0.0)
	warmth_radius = r.num("warmth_radius", 0.0)
	start_fuel = r.num("start_fuel", 0.0)
	max_fuel = r.num("max_fuel", 720.0)


func _validate(db: Node, out: PackedStringArray) -> void:
	if structure != &"" and not db.has_def(&"structure", structure):
		out.append("%s: structure '%s' unknown" % [ctx(), structure])
