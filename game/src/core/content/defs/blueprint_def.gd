class_name BlueprintDef
extends ContentDef
## A buildable plan from the guidebook. Two flavours:
##  - "pieces": a ghost of individual structure pieces (e.g. logs) the player fills one by one;
##  - "assembly": a single structure that completes once `cost` has been delivered.

var mode: String = "assembly"
var category: String = "misc"
## pieces mode: [{structure, pos:Vector3, rot:Vector3 (degrees)}]
var pieces: Array[Dictionary] = []
## assembly mode: resulting structure + total cost {item: count}
var result: StringName = &""
var cost: Dictionary = {}
## Ghost preview model id.
var preview: String = ""
## Max ground slope (degrees) at placement.
var max_slope: float = 25.0
var unlock: String = "default"
## Assemblies that may stand on a log floor or platform instead of the ground (furniture, racks,
## stairs: ADR-0035). They rest on the logs under them and fall with them.
var on_structures: bool = false


func _fields() -> PackedStringArray:
	return ["mode", "category", "pieces", "result", "cost", "preview", "max_slope", "unlock", "on_structures"]


func _parse(r: DefReader) -> void:
	mode = r.enum_str("mode", ["assembly", "pieces"], "assembly")
	category = r.str_field("category", "misc")
	result = r.sname("result")
	cost = r.dict("cost")
	preview = r.str_field("preview", "")
	max_slope = r.num("max_slope", 25.0)
	unlock = r.str_field("unlock", "default")
	on_structures = r.boolean("on_structures", false)
	for p: Variant in r.arr("pieces"):
		if not p is Dictionary:
			r.err("pieces must be objects")
			continue
		var pr := DefReader.new(p, "%s piece" % ctx())
		pieces.append({"structure": StringName(pr.req_str("structure")), "pos": pr.vec3("pos"), "rot": pr.vec3("rot")})
		r.errors.append_array(pr.errors)
	if mode == "pieces" and pieces.is_empty():
		r.err("pieces-mode blueprint needs pieces")
	if mode == "assembly" and (result == &"" or cost.is_empty()):
		r.err("assembly blueprint needs result and cost")


func _validate(db: Node, out: PackedStringArray) -> void:
	if result != &"" and not db.has_def(&"structure", result):
		out.append("%s: result structure '%s' unknown" % [ctx(), result])
	for k: Variant in cost.keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: cost item '%s' unknown" % [ctx(), k])
	for p: Dictionary in pieces:
		if not db.has_def(&"structure", p["structure"]):
			out.append("%s: piece structure '%s' unknown" % [ctx(), p["structure"]])


## Total materials needed, aggregated over pieces (pieces mode) or cost (assembly).
func total_cost(db: Node) -> Dictionary:
	if mode == "assembly":
		return cost.duplicate()
	var total: Dictionary = {}
	for p: Dictionary in pieces:
		var sd: StructureDef = db.get_def(&"structure", p["structure"]) as StructureDef
		if sd == null:
			continue
		for k: Variant in sd.cost.keys():
			total[k] = int(total.get(k, 0)) + int(sd.cost[k])
	return total
