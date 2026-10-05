class_name BuildingTemplateDef
extends ContentDef
## A template for generated ordinary buildings ("filler" houses, shops and workshops; ADR-0030):
## BuildingGenerator turns a template plus a seed into a complete PoiDef (plan, rooms, openings,
## stairs, props, loot, a few sleepers, a dungeon-lite route with a locked front and a way in).
## Framework lots without an authored pick draw from these by zoning (LotPicker). Everything a
## template varies is a range or a weighted list here, so a street of twelve reads as twelve
## different buildings; the archetype names the plan builder in code.

## Plan builders in BuildingGenerator.
const ARCHETYPES: PackedStringArray = ["house", "duplex", "store", "workshop"]
## How the upper floor of a two-storey house covers the ground floor: the whole of it, or a
## "cape" storey-and-a-half set back from the front (the front rooms get a lean-to roof).
const UPPER: PackedStringArray = ["full", "cape"]
## Roof types a template may draw (RoofPlanner.TYPES without the church shapes). Kept here: Content
## parses defs before the POI classes it would otherwise reach for exist.
const ROOF_TYPES: PackedStringArray = ["gable", "hip", "shed", "flat"]

var archetype: String = "house"
var zoning: PackedStringArray = []
var tier: int = 1
## Relative chance among the candidates of a lot (LotPicker).
var weight: float = 1.0
## Plan size ranges in cells (x = width along the street, y = depth), inclusive.
var width: Vector2i = Vector2i(9, 12)
var depth: Vector2i = Vector2i(8, 10)
var storeys: int = 1
var upper: String = "full"
## Chance of a front porch (houses).
var porch: float = 0.0
var floor_height: float = 0.6
## Front yard depth range (m) between the lot's street edge and the front wall.
var setback: Vector2i = Vector2i(4, 7)
var decay: Vector2 = Vector2(0.25, 0.5)
var sleepers: Vector2i = Vector2i(2, 4)
## Wall finishes of the outside, one per building.
var exteriors: PackedStringArray = ["siding_white"]
## [{type, axis?, pitch: [lo, hi], weight?, parapet?}] - one is drawn per building.
var roofs: Array = []
var roof_materials: PackedStringArray = ["roof_shingle"]
## Room type -> {"wall": [finishes], "floor": [finishes]} drawn per room.
var finishes: Dictionary = {}
## Name patterns ("The {family} House"); {family} draws from data/config/building_generator.json.
var names: PackedStringArray = []
## One-line stories, one drawn per building ({family} as above).
var stories: PackedStringArray = []
## Chance the house has a chimney on a gable end.
var chimney: float = 0.0


func _fields() -> PackedStringArray:
	return ["archetype", "zoning", "tier", "weight", "width", "depth", "storeys", "upper", "porch", "floor_height", "setback",
		"decay", "sleepers", "exteriors", "roofs", "roof_materials", "finishes", "names", "stories", "chimney"]


func _parse(r: DefReader) -> void:
	archetype = r.enum_str("archetype", ARCHETYPES, "house")
	zoning = r.strings("zoning")
	for z: String in zoning:
		if not PoiDef.ZONES.has(z):
			r.err("unknown zoning '%s'" % z)
	tier = clampi(r.integer("tier", 1), 1, 5)
	weight = maxf(0.0, r.num("weight", 1.0))
	width = _irange(r, "width", width)
	depth = _irange(r, "depth", depth)
	storeys = clampi(r.integer("storeys", 1), 1, 2)
	upper = r.enum_str("upper", UPPER, "full")
	porch = clampf(r.num("porch", 0.0), 0.0, 1.0)
	floor_height = r.num("floor_height", 0.6)
	setback = _irange(r, "setback", setback)
	var dr: Vector2 = r.range2("decay", decay)
	decay = Vector2(clampf(dr.x, 0.0, 1.0), clampf(dr.y, 0.0, 1.0))
	sleepers = _irange(r, "sleepers", sleepers)
	exteriors = r.strings("exteriors")
	if exteriors.is_empty():
		exteriors = ["siding_white"]
	roofs = r.arr("roofs")
	roof_materials = r.strings("roof_materials")
	if roof_materials.is_empty():
		roof_materials = ["roof_shingle"]
	finishes = r.dict("finishes")
	names = r.strings("names")
	stories = r.strings("stories")
	chimney = clampf(r.num("chimney", 0.0), 0.0, 1.0)
	if width.x < 6 or depth.x < 6 or width.y < width.x or depth.y < depth.x:
		r.err("width and depth must be [lo, hi] ranges of at least 6 cells")
	if storeys == 2 and depth.x < 8:
		r.err("a two-storey template needs a depth of at least 8 (the stair flight runs 4 cells from the back)")
	for rf: Variant in roofs:
		if not rf is Dictionary or not ROOF_TYPES.has(str((rf as Dictionary).get("type", ""))):
			r.err("roofs entries need a type (%s)" % ", ".join(ROOF_TYPES))


## [lo, hi] integer range (a single number means lo = hi).
func _irange(r: DefReader, key: String, def_v: Vector2i) -> Vector2i:
	if not r.has(key):
		return def_v
	var v: Variant = r.raw(key)
	if v is Array and (v as Array).size() == 2:
		return Vector2i(int(v[0]), int(v[1]))
	if v is float or v is int:
		return Vector2i(int(v), int(v))
	r.err("%s must be [lo, hi]" % key)
	return def_v


func _validate(db: Node, out: PackedStringArray) -> void:
	var cfg: Dictionary = db.call(&"config", &"building_generator") if db.has_method(&"config") else {}
	if (cfg.get("families", []) as Array).is_empty():
		out.append("%s: data/config/building_generator.json needs a 'families' list" % ctx())
	var kit: Dictionary = _json("res://data/materials/kit_finishes.json")
	var mats: Dictionary = _json("res://data/materials/roofs.json").get("materials", {})
	for mat: String in roof_materials:
		if not mats.has(mat):
			out.append("%s: roof material '%s' unknown (data/materials/roofs.json)" % [ctx(), mat])
	for e: String in exteriors:
		if not (kit.get("wall", []) as Array).has(e):
			out.append("%s: exterior finish '%s' unknown" % [ctx(), e])
	for rt: Variant in finishes.keys():
		var f: Variant = finishes[rt]
		if not f is Dictionary:
			out.append("%s: finishes.%s must be {wall: [...], floor: [...]}" % [ctx(), rt])
			continue
		for k: String in ["wall", "floor"]:
			for v: Variant in (f as Dictionary).get(k, []):
				if not (kit.get(k, []) as Array).has(str(v)):
					out.append("%s: finishes.%s %s '%s' unknown (data/materials/kit_finishes.json)" % [ctx(), rt, k, v])


static func _json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var j := JSON.new()
	return j.data if j.parse(FileAccess.get_file_as_string(path)) == OK and j.data is Dictionary else {}
