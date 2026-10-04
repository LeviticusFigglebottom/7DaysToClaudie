class_name BiomeDef
extends ContentDef
## A biome: ground layers, vegetation mix, ambience, temperature and spawn groups.

## {species_id: density per 100 m^2}
var vegetation: Dictionary = {}
## Ground material layer ids used by the terrain splat (grass, forest_floor, rock, snow, ...).
var ground: PackedStringArray = []
var ambience: String = ""
var temperature_offset: float = 0.0
## {enemy_id: weight} for wandering spawns.
var spawns: Dictionary = {}
var spawn_density: float = 1.0
var fog_tint: Color = Color(0.7, 0.75, 0.8)


func _fields() -> PackedStringArray:
	return ["vegetation", "ground", "ambience", "temperature_offset", "spawns", "spawn_density", "fog_tint"]


func _parse(r: DefReader) -> void:
	vegetation = r.dict("vegetation")
	ground = r.strings("ground")
	ambience = r.str_field("ambience", "")
	temperature_offset = r.num("temperature_offset", 0.0)
	spawns = r.dict("spawns")
	spawn_density = r.num("spawn_density", 1.0)
	fog_tint = r.color("fog_tint", Color(0.7, 0.75, 0.8))


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: Variant in vegetation.keys():
		if not db.has_def(&"species", StringName(k)):
			out.append("%s: vegetation species '%s' unknown" % [ctx(), k])
	for k: Variant in spawns.keys():
		if not db.has_def(&"enemy", StringName(k)):
			out.append("%s: spawn enemy '%s' unknown" % [ctx(), k])
