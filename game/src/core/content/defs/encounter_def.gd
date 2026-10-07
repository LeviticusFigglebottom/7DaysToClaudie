class_name EncounterDef
extends ContentDef
## A forest encounter (ADR-0054, data/encounters/*.json): something small to find between the
## towns, scattered deterministically per region by EncounterPlanner and built when its region
## attaches (Encounters). The planner reads only these fields, so the plan of a world never
## depends on which systems are loaded.
##
## `kind` says who builds it:
##  * "scene": Encounters itself, from `props` (a container prop is a LootProp), `loose` items,
##    a `notes` pickup and `sleepers` (an abandoned campsite, a wreck, a grave, a body-bag drop);
##  * "poi": a tiny building (`poi`, a POI def with zoning "encounter") that PoiManager builds and
##    frees like any other (a hermit's shack);
##  * anything else: a kind another system registers with Encounters.register_kind() (Bloom nests,
##    wolf dens, cave mouths). Its sites are planned from this data whether or not the system is
##    there; an unregistered kind is simply not built.
##
## Placement: `weight` among the defs, times `biomes[biome]` at the spot (0 or missing = never
## there); `slope_max` (degrees, over `radius`); `road` [min, max] metres from the nearest road's
## edge (of `road_surfaces`, any when empty); `min_building` metres from any building or lot,
## `min_water` from rivers and lakes; at most `max_per_region` a region (0 = no cap).
## `snap`: "road" moves the spot to the nearest road (within the cell) at a distance inside
## `road`, turned along it (a wreck in the ditch). `anchor`: "tree" stands it at the foot of the
## nearest standing tree (a ladder stand), which its clearing keeps.
## `clear` {trees, brush}: metres of trees and of undergrowth hidden around it at runtime (the
## vegetation's clearing mask; saves and the composer never see it).
## Prop entries: {prop | one_of: [prop ids], pos: [x, z] (m, site-local: +Z is the site's front),
## rot (deg), y (m above the ground), variant, chance (0..1), id (keys its container), container
## (overrides the prop's)}. Loose: {item, count, pos, y, chance, id}. Notes: {chance, items: [note
## items], pos, y}. Sleepers: {chance, count: [min, max], enemies: {id: weight}, poses: [pose],
## ring: [min, max] m from the centre}.

const BUILTIN_KINDS: PackedStringArray = ["scene", "poi"]
const PROP_KEYS: PackedStringArray = ["prop", "one_of", "pos", "rot", "y", "variant", "chance", "id", "container"]
const LOOSE_KEYS: PackedStringArray = ["item", "count", "pos", "y", "chance", "id"]
const NOTE_KEYS: PackedStringArray = ["chance", "items", "pos", "y"]
const SLEEPER_KEYS: PackedStringArray = ["chance", "count", "enemies", "poses", "ring"]
const POSES: PackedStringArray = ["lie", "sit", "stand", "kneel", "crouch"]

var ekind: StringName = &"scene"
var weight: float = 1.0
var biomes: Dictionary = {}
var radius: float = 4.0
var slope_max: float = 12.0
var road := Vector2(25.0, 1.0e9)
var road_surfaces: PackedStringArray = []
var snap: String = ""
var anchor: String = ""
var min_building: float = 60.0
var min_water: float = 12.0
var clear_trees: float = 4.0
var clear_brush: float = 5.0
var max_per_region: int = 0
## Loot tier of its containers and infected tier bonus of its sleepers (like a POI's tier).
var tier: int = 1
var props: Array[Dictionary] = []
var loose: Array[Dictionary] = []
var notes: Dictionary = {}
var sleepers: Dictionary = {}
var poi: StringName = &""


func _fields() -> PackedStringArray:
	return ["kind", "weight", "biomes", "radius", "slope_max", "road", "road_surfaces", "snap", "anchor", "min_building",
		"min_water", "clear", "max_per_region", "tier", "props", "loose", "notes", "sleepers", "poi"]


func _parse(r: DefReader) -> void:
	ekind = StringName(r.str_field("kind", "scene"))
	if not _is_valid_id(String(ekind)):
		r.err("kind '%s' must be lower_snake_case" % ekind)
	weight = r.num("weight", 1.0)
	biomes = r.dict("biomes")
	if biomes.is_empty():
		r.err("an encounter needs biomes {biome id: weight}")
	for b: Variant in biomes.keys():
		if not (biomes[b] is float or biomes[b] is int) or float(biomes[b]) < 0.0:
			r.err("biomes.%s must be a weight >= 0" % b)
	radius = r.num("radius", 4.0)
	slope_max = r.num("slope_max", 12.0)
	road = r.range2("road", Vector2(25.0, 1.0e9))
	if road.y < road.x:
		r.err("road must be [min, max] with max >= min")
	road_surfaces = r.strings("road_surfaces")
	snap = r.enum_str("snap", ["", "road"], "")
	anchor = r.enum_str("anchor", ["", "tree"], "")
	min_building = r.num("min_building", 60.0)
	min_water = r.num("min_water", 12.0)
	var cl: Dictionary = r.dict("clear")
	for k: Variant in cl.keys():
		if not str(k) in ["trees", "brush"]:
			r.err("clear has unknown key '%s' (trees, brush)" % k)
	clear_trees = float(cl.get("trees", radius))
	clear_brush = float(cl.get("brush", radius + 1.0))
	max_per_region = r.integer("max_per_region", 0)
	tier = clampi(r.integer("tier", 1), 1, 5)
	for p: Variant in r.arr("props"):
		if _entry_ok(r, p, "props", PROP_KEYS):
			var d: Dictionary = p
			if not d.has("prop") and not d.has("one_of"):
				r.err("props entry needs 'prop' or 'one_of'")
			props.append(d)
	for l: Variant in r.arr("loose"):
		if _entry_ok(r, l, "loose", LOOSE_KEYS):
			if not (l as Dictionary).has("item"):
				r.err("loose entry needs 'item'")
			loose.append(l as Dictionary)
	notes = r.dict("notes")
	_keys_ok(r, notes, "notes", NOTE_KEYS)
	sleepers = r.dict("sleepers")
	_keys_ok(r, sleepers, "sleepers", SLEEPER_KEYS)
	for pose: Variant in sleepers.get("poses", []):
		if not POSES.has(str(pose)):
			r.err("sleepers pose '%s' unknown (%s)" % [pose, ", ".join(POSES)])
	poi = r.sname("poi")
	if ekind == &"poi" and poi == &"":
		r.err("kind poi needs a poi")
	if ekind != &"poi" and poi != &"":
		r.err("poi is only for kind poi")
	if snap == "road" and road.y > 1.0e8:
		r.err("snap road needs a road [min, max] band")


func _entry_ok(r: DefReader, v: Variant, what: String, keys: PackedStringArray) -> bool:
	if not v is Dictionary:
		r.err("%s entries must be objects" % what)
		return false
	_keys_ok(r, v as Dictionary, what, keys)
	var pos: Variant = (v as Dictionary).get("pos", [0, 0])
	if not pos is Array or (pos as Array).size() != 2:
		r.err("%s pos must be [x, z]" % what)
		return false
	return true


func _keys_ok(r: DefReader, d: Dictionary, what: String, keys: PackedStringArray) -> void:
	for k: Variant in d.keys():
		if not str(k).begins_with("_") and not keys.has(str(k)):
			r.err("%s has unknown key '%s' (%s)" % [what, k, ", ".join(keys)])


## The weight of this def at a spot of `biome` (0 = never there).
func weight_in(biome: String) -> float:
	return weight * float(biomes.get(biome, 0.0))


## Every prop id an entry may show.
static func entry_props(p: Dictionary) -> PackedStringArray:
	if p.has("one_of"):
		return PackedStringArray(p["one_of"])
	return PackedStringArray([str(p.get("prop", ""))])


func _validate(db: Node, out: PackedStringArray) -> void:
	for b: Variant in biomes.keys():
		if not db.has_def(&"biome", StringName(str(b))):
			out.append("%s: biome '%s' unknown" % [ctx(), b])
	for p: Dictionary in props:
		for pid: String in entry_props(p):
			if not db.has_def(&"prop", StringName(pid)):
				out.append("%s: prop '%s' unknown" % [ctx(), pid])
		if p.has("container") and not db.has_def(&"container", StringName(str(p["container"]))):
			out.append("%s: container '%s' unknown" % [ctx(), p["container"]])
	for l: Dictionary in loose:
		if not db.has_def(&"item", StringName(str(l.get("item", "")))):
			out.append("%s: loose item '%s' unknown" % [ctx(), l.get("item")])
	for it: Variant in notes.get("items", []):
		if not db.has_def(&"item", StringName(str(it))):
			out.append("%s: note item '%s' unknown" % [ctx(), it])
	for e: Variant in (sleepers.get("enemies", {}) as Dictionary).keys():
		if not db.has_def(&"enemy", StringName(str(e))):
			out.append("%s: sleeper enemy '%s' unknown" % [ctx(), e])
	if not sleepers.is_empty() and (sleepers.get("enemies", {}) as Dictionary).is_empty():
		out.append("%s: sleepers need enemies {id: weight}" % ctx())
	if ekind == &"poi":
		var pd: PoiDef = db.call(&"get_def", &"poi", poi) as PoiDef
		if pd == null:
			out.append("%s: poi '%s' unknown" % [ctx(), poi])
		elif not pd.zoning.has("encounter"):
			out.append("%s: poi '%s' must have zoning [\"encounter\"] (no town lot may draw it)" % [ctx(), poi])
