class_name PoiDef
extends ContentDef
## A point of interest (a building or a wilderness site) authored with the POI spec DSL
## (docs/POI_AUTHORING.md) and/or a hand-authored scene. The layout blocks are kept raw here
## and compiled by PoiLayout (src/poi/poi_layout.gd) — content stays declarative. Dungeon
## mechanics (sleeper groups, triggers, traps, locks, guardians) are part of the layout and checked
## by PoiValidator (ADR-0018).

const ZONES: PackedStringArray = ["residential", "commercial", "civic", "industrial", "rural", "wilderness", "roadside"]

var tier: int = 1
var zoning: PackedStringArray = []
## Lot footprint in whole meters (x = width, y = depth), including yard.
var footprint: Vector2i = Vector2i(12, 12)
## One-paragraph environmental story — what happened here.
var story: String = ""
var author: String = ""
## Optional hand-authored scene (res://...tscn) with a PoiRoot. Overrides generated geometry.
var scene: String = ""
## Raw layout blocks (compiled by PoiLayout).
var layout: Dictionary = {}
## Performance budget overrides {draw_calls, triangles, lights, enemies}.
var budget: Dictionary = {}

## "triggers" wake sleeper groups as ambushes (ADR-0018, docs/POI_AUTHORING.md "Ambushes").
const LAYOUT_KEYS: PackedStringArray = ["style", "levels", "rooms", "openings", "stairs", "ladders", "props",
	"sleepers", "traps", "route", "loot_room", "shortcuts", "lights", "decals", "notes", "scatter", "exterior",
	"roof", "front", "origin", "quest_hooks", "pickups", "holes", "triggers"]


func _fields() -> PackedStringArray:
	var f: PackedStringArray = ["tier", "zoning", "footprint", "story", "author", "scene", "budget"]
	f.append_array(LAYOUT_KEYS)
	return f


func _parse(r: DefReader) -> void:
	tier = clampi(r.integer("tier", 1), 1, 5)
	zoning = r.strings("zoning")
	for z: String in zoning:
		if not ZONES.has(z):
			r.err("unknown zoning '%s'" % z)
	var fp: Array = r.arr("footprint")
	if fp.size() == 2:
		footprint = Vector2i(int(fp[0]), int(fp[1]))
	else:
		r.err("footprint must be [width, depth]")
	story = r.str_field("story", "")
	author = r.str_field("author", "")
	scene = r.str_field("scene", "")
	budget = r.dict("budget")
	for k: String in LAYOUT_KEYS:
		if r.has(k):
			layout[k] = r.raw(k)
	if scene == "" and not layout.has("levels"):
		r.err("POI needs either 'scene' or 'levels'")


func _validate(db: Node, out: PackedStringArray) -> void:
	for p: Variant in layout.get("props", []):
		if p is Dictionary and p.has("prop") and not db.has_def(&"prop", StringName(p["prop"])):
			out.append("%s: prop '%s' unknown" % [ctx(), p["prop"]])
	for s: Variant in layout.get("sleepers", []):
		if s is Dictionary:
			for e: Variant in (s.get("enemies", {}) as Dictionary).keys():
				if not db.has_def(&"enemy", StringName(e)):
					out.append("%s: sleeper enemy '%s' unknown" % [ctx(), e])
	for n: Variant in layout.get("notes", []):
		if n is Dictionary and n.has("note") and not db.has_def(&"note", StringName(n["note"])):
			out.append("%s: note '%s' unknown" % [ctx(), n["note"]])


func level_count() -> int:
	return (layout.get("levels", []) as Array).size()
