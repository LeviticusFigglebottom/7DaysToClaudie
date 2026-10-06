class_name FrameworkDef
extends ContentDef
## A reusable POI framework (town block, gas-station cluster, farmstead, ...): lots, roads and
## fixed props, with slots filled from POI pools by zoning/tags. Used by the handcrafted map
## (with authored picks) and by RWG (random picks) alike.
##
## An organic town of a random world (ADR-0040, `layout: "organic"`) is a framework too, placed at
## the world origin with no rotation: its lots carry `frame` (an oriented rectangle in world XZ)
## instead of `rect`, its roads are the town's own streets, and `authored` lists the authored
## buildings the generator let this town hold (a world-wide cap, LotPicker.assign_authored).

## [{id, rect:[x, z, w, d], zoning:[...], facing:"N|E|S|W", pick: optional poi id, tags:[...],
##   tier?: [lo, hi] | n, pool?: "any" | "authored" | "generated", templates?: [template ids],
##   reserved?: "what is planned here"}]. A lot without a pick holds what LotPicker chooses
## (ADR-0030); a reserved one stays empty. An organic town's lot has `frame: [cx, cz, w, d, yaw]`
## (centre, frontage, depth, yaw in degrees as PoiManager.lot_xf turns a building: its front,
## local +Z, along (sin yaw, cos yaw)) instead of rect and facing, plus `poly` (its parcel),
## `street` (the street it fronts), `ring` (core, inner, outer, edge) and `y` (its pad height).
var lots: Array = []
## [{points: [[x, z], ...], width, surface: "asphalt|gravel|dirt"}]
var roads: Array = []
## Fixed props (street lights, wrecks, barricades): [{prop, pos:[x, z], rot}]
var fixtures: Array = []
## Overall size [w, d] in meters.
var size: Vector2i = Vector2i(128, 128)
var tier_range: Vector2i = Vector2i(1, 3)
## "" (a block of rect lots) or "organic" (a random world's town, ADR-0040).
var layout: String = ""
## Organic towns: the size class (hamlet, village, town), the centre and radius (world XZ, m), the
## square ({frame: [cx, cz, w, d, yaw], y} or {}), and the authored buildings this town may hold.
var town_kind: String = ""
var center := Vector2.ZERO
var radius: float = 0.0
var plaza: Dictionary = {}
var authored: PackedStringArray = []

## Keys a lot may carry (LotPicker.LOT_KEYS; kept here so Content parses before the POI classes).
const LOT_KEYS: PackedStringArray = ["id", "rect", "zoning", "facing", "pick", "tags", "tier", "pool", "templates", "reserved",
	"frame", "poly", "street", "ring", "y"]
const POOLS: PackedStringArray = ["any", "authored", "generated"]
const LAYOUTS: PackedStringArray = ["", "organic"]


func _fields() -> PackedStringArray:
	return ["lots", "roads", "fixtures", "size", "tier_range", "layout", "center", "radius", "kind", "plaza", "authored"]


func _parse(r: DefReader) -> void:
	lots = r.arr("lots")
	roads = r.arr("roads")
	fixtures = r.arr("fixtures")
	var s: Array = r.arr("size")
	if s.size() == 2:
		size = Vector2i(int(s[0]), int(s[1]))
	var tr: Vector2 = r.range2("tier_range", Vector2(1, 3))
	tier_range = Vector2i(int(tr.x), int(tr.y))
	layout = r.enum_str("layout", LAYOUTS, "")
	town_kind = r.str_field("kind", "")
	var c: Array = r.arr("center")
	if c.size() == 2:
		center = Vector2(float(c[0]), float(c[1]))
	radius = r.num("radius", 0.0)
	plaza = r.dict("plaza")
	authored = r.strings("authored")
	var seen: Dictionary = {}
	for lot: Variant in lots:
		if not lot is Dictionary or not (lot as Dictionary).has("id") or not ((lot as Dictionary).has("rect") or (lot as Dictionary).has("frame")):
			r.err("each lot needs id and rect (or frame)")
			continue
		if seen.has(lot["id"]):
			r.err("duplicate lot id '%s'" % lot["id"])
		seen[lot["id"]] = true
		var l: Dictionary = lot
		for k: Variant in l.keys():
			if not str(k).begins_with("_") and not LOT_KEYS.has(str(k)):
				r.err("lot '%s' has unknown key '%s' (%s)" % [l["id"], k, ", ".join(LOT_KEYS)])
		if l.has("reserved") and str(l.get("pick", "")) != "":
			r.err("lot '%s' is reserved and picks '%s'" % [l["id"], l["pick"]])
		if l.has("pool") and not POOLS.has(str(l["pool"])):
			r.err("lot '%s' pool must be one of %s" % [l["id"], ", ".join(POOLS)])
		if not str(l.get("facing", "S")) in ["N", "E", "S", "W"]:
			r.err("lot '%s' facing must be N, E, S or W" % l["id"])
		if l.has("frame") and (not l["frame"] is Array or (l["frame"] as Array).size() != 5):
			r.err("lot '%s' frame must be [cx, cz, w, d, yaw]" % l["id"])
		if l.has("frame") and l.has("rect"):
			r.err("lot '%s' has both rect and frame" % l["id"])


func _validate(db: Node, out: PackedStringArray) -> void:
	for lot: Variant in lots:
		if lot is Dictionary and lot.has("pick") and not db.has_def(&"poi", StringName(lot["pick"])):
			out.append("%s: lot '%s' picks unknown poi '%s'" % [ctx(), lot.get("id"), lot["pick"]])
		if lot is Dictionary:
			for tid: Variant in (lot as Dictionary).get("templates", []):
				if not db.has_def(&"building_template", StringName(str(tid))):
					out.append("%s: lot '%s' names unknown building template '%s'" % [ctx(), lot.get("id"), tid])
	for f: Variant in fixtures:
		if f is Dictionary and f.has("prop") and not db.has_def(&"prop", StringName(f["prop"])):
			out.append("%s: fixture prop '%s' unknown" % [ctx(), f["prop"]])
	for pid: String in authored:
		if not db.has_def(&"poi", StringName(pid)):
			out.append("%s: authored names unknown poi '%s'" % [ctx(), pid])
