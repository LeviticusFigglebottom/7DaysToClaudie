class_name FrameworkDef
extends ContentDef
## A reusable POI framework (town block, gas-station cluster, farmstead, ...): lots, roads and
## fixed props, with slots filled from POI pools by zoning/tags. Used by the handcrafted map
## (with authored picks) and by RWG (random picks) alike.

## [{id, rect:[x, z, w, d], zoning:[...], facing:"N|E|S|W", pick: optional poi id, tags:[...]}]
var lots: Array = []
## [{points: [[x, z], ...], width, surface: "asphalt|gravel|dirt"}]
var roads: Array = []
## Fixed props (street lights, wrecks, barricades): [{prop, pos:[x, z], rot}]
var fixtures: Array = []
## Overall size [w, d] in meters.
var size: Vector2i = Vector2i(128, 128)
var tier_range: Vector2i = Vector2i(1, 3)


func _fields() -> PackedStringArray:
	return ["lots", "roads", "fixtures", "size", "tier_range"]


func _parse(r: DefReader) -> void:
	lots = r.arr("lots")
	roads = r.arr("roads")
	fixtures = r.arr("fixtures")
	var s: Array = r.arr("size")
	if s.size() == 2:
		size = Vector2i(int(s[0]), int(s[1]))
	var tr: Vector2 = r.range2("tier_range", Vector2(1, 3))
	tier_range = Vector2i(int(tr.x), int(tr.y))
	var seen: Dictionary = {}
	for lot: Variant in lots:
		if not lot is Dictionary or not (lot as Dictionary).has("id") or not (lot as Dictionary).has("rect"):
			r.err("each lot needs id and rect")
			continue
		if seen.has(lot["id"]):
			r.err("duplicate lot id '%s'" % lot["id"])
		seen[lot["id"]] = true


func _validate(db: Node, out: PackedStringArray) -> void:
	for lot: Variant in lots:
		if lot is Dictionary and lot.has("pick") and not db.has_def(&"poi", StringName(lot["pick"])):
			out.append("%s: lot '%s' picks unknown poi '%s'" % [ctx(), lot.get("id"), lot["pick"]])
	for f: Variant in fixtures:
		if f is Dictionary and f.has("prop") and not db.has_def(&"prop", StringName(f["prop"])):
			out.append("%s: fixture prop '%s' unknown" % [ctx(), f["prop"]])
