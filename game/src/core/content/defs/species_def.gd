class_name SpeciesDef
extends ContentDef
## A vegetation species (tree, bush, fern, grass, deadfall, moss, litter...) used by scatter +
## chopping. The kind picks the scatter layer (VegetationScatter.LAYERS).

const VEG_KINDS: PackedStringArray = ["tree", "bush", "fern", "grass", "deadfall", "rock", "flower", "mushroom", "moss", "litter", "herb", "fungus"]

var veg_kind: String = "tree"
## Model ids for variants; LOD models follow "<id>_lod1", "<id>_lod2", impostor "<id>_imp".
var models: PackedStringArray = []
var stump_model: String = ""
var log_model: String = ""
var hp: float = 100.0
## {item_id: [min, max]} harvested when felled/gathered.
var yields: Dictionary = {}
## Tool kind needed ("" = by hand).
var tool: String = ""
var height_range: Vector2 = Vector2(10, 20)
## Trunk collision radius at scale 1.
var trunk_radius: float = 0.3
## Distances (m) for LOD switching: [lod0_end, lod1_end, lod2_end, impostor_end]
var lod_distances: PackedFloat32Array = [40.0, 110.0, 260.0, 1200.0]
var collides: bool = true
var regrow_days: float = 0.0
## Leaves turn and fall with the seasons (trees): the far-terrain canopy tints by it.
var deciduous: bool = false


func _fields() -> PackedStringArray:
	return ["kind", "models", "stump_model", "log_model", "hp", "yields", "tool", "height", "trunk_radius",
		"lod_distances", "collides", "regrow_days", "deciduous"]


func _parse(r: DefReader) -> void:
	veg_kind = r.enum_str("kind", VEG_KINDS, "tree")
	models = r.strings("models")
	stump_model = r.str_field("stump_model", "")
	log_model = r.str_field("log_model", "")
	hp = r.num("hp", 100.0)
	yields = r.dict("yields")
	tool = r.str_field("tool", "")
	height_range = r.range2("height", Vector2(10, 20))
	trunk_radius = r.num("trunk_radius", 0.3)
	var ld: Array = r.arr("lod_distances")
	if not ld.is_empty():
		lod_distances = PackedFloat32Array(ld)
	collides = r.boolean("collides", veg_kind in ["tree", "rock", "deadfall"])
	regrow_days = r.num("regrow_days", 0.0)
	deciduous = r.boolean("deciduous", false)
	if models.is_empty():
		r.err("species needs at least one model")


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: Variant in yields.keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: yield item '%s' unknown" % [ctx(), k])
