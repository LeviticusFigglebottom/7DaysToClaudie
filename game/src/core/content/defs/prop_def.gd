class_name PropDef
extends ContentDef
## A set-dressing prop (furniture, appliances, clutter, vehicles, debris).

## Model ids for condition variants: {"clean": id, "worn": id, "destroyed": id}
var variants: Dictionary = {}
## "box" | "convex" | "mesh" | "none"
var collision: String = "box"
## "static" | "rigid" | "carry"
var physics: String = "static"
var hp: float = 0.0
var size: Vector3 = Vector3.ONE
## Container def id if this prop is lootable.
var container: StringName = &""
## {color, energy, range, flicker, offset:[x,y,z]} for light-emitting props, plus `power`,
## per-variant overrides (`variants`) and `fx`: see light_for() (ADR-0023).
var light: Dictionary = {}
var blocks_sight: bool = true
var wall_mounted: bool = false
## Room tags this prop suits (kitchen, bedroom, bathroom, living, office, store, garage, basement,
## diner, hallway, exterior, any). PoiBuilder.ROOM_TAGS maps POI room types onto these.
var rooms: PackedStringArray = []
## Seats and beds posed sleepers land on (ADR-0022, SleeperAnchors): [{kind: "seat" | "bed",
## pos: [x, z] prop-local m (under the pelvis), height: seat / mattress top above the prop's base,
## facing: degrees (0 = the prop's front, +Z; a sitter's view, head to feet on a bed),
## lean: "back" (against a backrest, default) | "forward" (hunched on a backless seat) | "low" (sat
## legs out on a low surface: in a bathtub, on a mattress; pos under the pelvis, facing the legs)}].
var anchors: Array[Dictionary] = []


func _fields() -> PackedStringArray:
	return ["variants", "collision", "physics", "hp", "size", "container", "light", "blocks_sight", "wall_mounted", "rooms",
		"anchors"]


func _parse(r: DefReader) -> void:
	variants = r.dict("variants")
	collision = r.enum_str("collision", ["box", "convex", "mesh", "none"], "box")
	physics = r.enum_str("physics", ["static", "rigid", "carry"], "static")
	hp = r.num("hp", 0.0)
	size = r.vec3("size", Vector3.ONE)
	container = r.sname("container")
	light = r.dict("light")
	blocks_sight = r.boolean("blocks_sight", true)
	wall_mounted = r.boolean("wall_mounted", false)
	rooms = r.strings("rooms")
	if variants.is_empty():
		r.err("prop needs variants {clean|worn|destroyed: model}")
	for a: Variant in r.arr("anchors"):
		var problem: String = anchor_problem(a)
		if problem != "":
			r.err(problem)
		else:
			anchors.append(a as Dictionary)


## Seat / bed anchor schema (ADR-0022). Kept here, free of game classes: Content parses props
## before anything else exists.
const ANCHOR_KINDS: PackedStringArray = ["seat", "bed"]
const ANCHOR_LEANS: PackedStringArray = ["back", "forward", "low"]
const ANCHOR_KEYS: PackedStringArray = ["kind", "pos", "height", "facing", "lean"]


## What is wrong with one anchors entry ("" when it is fine).
static func anchor_problem(a: Variant) -> String:
	if not a is Dictionary:
		return "anchors entries must be objects"
	var d: Dictionary = a
	for k: Variant in d.keys():
		if not str(k).begins_with("_") and not ANCHOR_KEYS.has(str(k)):
			return "anchor has unknown key '%s' (%s)" % [k, ", ".join(ANCHOR_KEYS)]
	if not ANCHOR_KINDS.has(str(d.get("kind", ""))):
		return "anchor kind must be one of %s" % ", ".join(ANCHOR_KINDS)
	var p: Variant = d.get("pos", null)
	if not p is Array or (p as Array).size() != 2 or not ((p as Array)[0] is float or (p as Array)[0] is int) \
			or not ((p as Array)[1] is float or (p as Array)[1] is int):
		return "anchor pos must be [x, z] (prop-local metres)"
	var h: Variant = d.get("height", null)
	if not (h is float or h is int) or float(h) < 0.0:
		return "anchor height must be a number >= 0 (seat or mattress top above the prop's base)"
	if d.has("facing") and not (d["facing"] is float or d["facing"] is int):
		return "anchor facing must be degrees"
	if d.has("lean") and (str(d.get("kind", "")) != "seat" or not ANCHOR_LEANS.has(str(d["lean"]))):
		return "anchor lean is for seats: %s" % ", ".join(ANCHOR_LEANS)
	return ""


func _validate(db: Node, out: PackedStringArray) -> void:
	if container != &"" and not db.has_def(&"container", container):
		out.append("%s: container '%s' unknown" % [ctx(), container])
	_validate_light(out)


func model_for(condition: String) -> String:
	if variants.has(condition):
		return str(variants[condition])
	for c: String in ["worn", "clean", "destroyed"]:
		if variants.has(c):
			return str(variants[c])
	return ""


# --- Lights (ADR-0023) -------------------------------------------------------------------------

## Keys a prop light may have. `power`: what feeds it (LIGHT_POWER). `variants`: per condition,
## a dictionary of overrides (a burnt-down candle is dimmer) or false for dark. `fx`: "fire" adds
## flames and a crackle (PropLights), sized by `fx_size` (m).
const LIGHT_KEYS: PackedStringArray = ["color", "energy", "range", "flicker", "offset", "shadow", "power", "variants", "fx", "fx_size"]
## The valley's grid has been down since the Cordon went up: "mains" lights never burn. Flames
## (candles, lamp oil, propane, wood) and batteries burn where a POI lights them; "generator" is
## for fixtures a POI powers itself.
const LIGHT_POWER: PackedStringArray = ["flame", "battery", "generator", "mains"]


## The condition variant a prop actually shows for `condition` (model_for's fallback order).
func variant_for(condition: String) -> String:
	if variants.has(condition):
		return condition
	for c: String in ["worn", "clean", "destroyed"]:
		if variants.has(c):
			return c
	return condition


## The light this prop gives when lit in `condition` ({} if it stays dark): the base light merged
## with the variant's override. A destroyed variant is dark unless it lists a light of its own (a
## smashed lantern doesn't burn), and mains lights are always dark.
func light_for(condition: String) -> Dictionary:
	if light.is_empty() or str(light.get("power", "flame")) == "mains":
		return {}
	var v: String = variant_for(condition)
	var per: Dictionary = light.get("variants", {}) if light.get("variants", {}) is Dictionary else {}
	var o: Variant = per.get(v, false if v == "destroyed" else true)
	if o is bool and not bool(o):
		return {}
	var out: Dictionary = light.duplicate(true)
	out.erase("variants")
	if o is Dictionary:
		out.merge(o, true)
	return out


func _validate_light(out: PackedStringArray) -> void:
	if light.is_empty():
		return
	for k: Variant in light.keys():
		if not LIGHT_KEYS.has(str(k)):
			out.append("%s: unknown light key '%s'" % [ctx(), k])
	if not LIGHT_POWER.has(str(light.get("power", "flame"))):
		out.append("%s: light power '%s' is not one of %s" % [ctx(), light.get("power"), ", ".join(LIGHT_POWER)])
	if not ["", "fire"].has(str(light.get("fx", ""))):
		out.append("%s: light fx '%s' unknown" % [ctx(), light.get("fx")])
	var per: Variant = light.get("variants", {})
	if not per is Dictionary:
		out.append("%s: light variants must be {condition: overrides | false}" % ctx())
		return
	for c: Variant in (per as Dictionary).keys():
		if not variants.has(str(c)):
			out.append("%s: light variant '%s' is not one of the prop's variants" % [ctx(), c])
		var o: Variant = (per as Dictionary)[c]
		if not (o is Dictionary or o is bool):
			out.append("%s: light variant '%s' must be overrides or false" % [ctx(), c])
		elif o is Dictionary:
			for k: Variant in (o as Dictionary).keys():
				if not LIGHT_KEYS.has(str(k)) or str(k) == "variants":
					out.append("%s: unknown light key '%s' in variant '%s'" % [ctx(), k, c])
