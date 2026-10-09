class_name PropDef
extends ContentDef
## A set-dressing prop (furniture, appliances, clutter, vehicles, debris).

## Model ids for condition variants: {"clean": id, "worn": id, "destroyed": id}
var variants: Dictionary = {}
## "box" | "convex" | "mesh" | "none". Every kind but "none" builds as boxes: the one size box
## (box_centre()), or `boxes` when the def has them.
var collision: String = "box"
## Compound collision (TD-270): boxes used instead of the one size box, for shells and structures
## whose size box would close a doorway or stand in the air. Each {size: Vector3, at: Vector3,
## yaw: degrees}: `at` is the centre of the box's base in the prop's own frame (origin = the
## model's origin, +X right, +Y up, +Z the prop's front: box_centre()'s frame), and `yaw` turns the
## box about its vertical axis through `at` (as a placement's rot turns a prop). The size box
## would be {size: size, at: [0, 0, size.z / 2 - back_depth()]}. A prop with boxes collides as a
## "box" prop: leave `collision` out or say "box"; any other kind with boxes is an error.
var boxes: Array[Dictionary] = []
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
## Metres from the model's origin back to its back face (prop-local −Z): what stands between a
## prop placed `against` a wall and that wall. Negative = the convention (docs/ASSET_PIPELINE.md):
## 0 for a wall-mounted prop (origin on the wall plane), half its depth for the rest (origin at
## the bottom centre). Set it only for a model that breaks the convention; test_prop_wall_depth
## checks it against the generated meshes.
var back: float = -1.0
## Room tags this prop suits (kitchen, bedroom, bathroom, living, office, store, garage, basement,
## diner, hallway, exterior, any). PoiBuilder.ROOM_TAGS maps POI room types onto these.
var rooms: PackedStringArray = []
## Seats and beds posed sleepers land on (ADR-0022, SleeperAnchors): [{kind: "seat" | "bed",
## pos: [x, z] prop-local m (under the pelvis), height: seat / mattress top above the prop's base,
## facing: degrees (0 = the prop's front, +Z; a sitter's view, head to feet on a bed),
## lean: "back" (against a backrest, default) | "forward" (hunched on a backless seat) | "low" (sat
## legs out on a low surface: in a bathtub, on a mattress; pos under the pelvis, facing the legs)}].
var anchors: Array[Dictionary] = []
## What draws before `make assets` (ModelLibrary.mesh's placeholder): "" the generic small box,
## "boxes" the prop's collision boxes (a 6 m wall panel or a culvert bay that must still read and
## line up as a wall). Needs `boxes`.
var standin: String = ""


func _fields() -> PackedStringArray:
	return ["variants", "collision", "physics", "hp", "size", "container", "light", "blocks_sight", "wall_mounted", "rooms",
		"anchors", "back", "boxes", "standin"]


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
	back = r.num("back", -1.0)
	if r.has("back") and (back < 0.0 or back > size.z):
		r.err("back must be between 0 and the prop's depth (size z, %.2f m)" % size.z)
	rooms = r.strings("rooms")
	for b: Variant in r.arr("boxes"):
		var bp: String = box_problem(b)
		if bp != "":
			r.err(bp)
			continue
		var bd: Dictionary = b
		boxes.append({"size": _v3(bd["size"]), "at": _v3(bd["at"]), "yaw": float(bd.get("yaw", 0.0))})
	if r.has("boxes") and collision != "box":
		r.err("boxes are a box collision: leave collision out or make it \"box\" (it is \"%s\")" % collision)
	standin = r.enum_str("standin", ["", "boxes"], "")
	if standin == "boxes" and boxes.is_empty():
		r.err("standin \"boxes\" draws the prop's boxes: give it boxes")
	if variants.is_empty():
		r.err("prop needs variants {clean|worn|destroyed: model}")
	for a: Variant in r.arr("anchors"):
		var problem: String = anchor_problem(a)
		if problem != "":
			r.err(problem)
		else:
			anchors.append(a as Dictionary)


## Keys of one `boxes` entry.
const BOX_KEYS: PackedStringArray = ["size", "at", "yaw"]


## What is wrong with one boxes entry ("" when it is fine).
static func box_problem(b: Variant) -> String:
	if not b is Dictionary:
		return "boxes entries must be objects {size: [x, y, z], at: [x, y, z], yaw}"
	var d: Dictionary = b
	for k: Variant in d.keys():
		if not str(k).begins_with("_") and not BOX_KEYS.has(str(k)):
			return "box has unknown key '%s' (%s)" % [k, ", ".join(BOX_KEYS)]
	if not _is_v3(d.get("size", null)):
		return "box size must be [x, y, z] (metres)"
	var sz: Vector3 = _v3(d["size"])
	if sz.x <= 0.0 or sz.y <= 0.0 or sz.z <= 0.0:
		return "box size must be positive each way (it is %s)" % sz
	if not _is_v3(d.get("at", null)):
		return "box at must be [x, y, z] (the centre of its base in the prop's frame)"
	if d.has("yaw") and not (d["yaw"] is float or d["yaw"] is int):
		return "box yaw must be degrees"
	return ""


static func _is_v3(v: Variant) -> bool:
	if not v is Array or (v as Array).size() != 3:
		return false
	for c: Variant in v as Array:
		if not (c is float or c is int):
			return false
	return true


static func _v3(v: Variant) -> Vector3:
	var a: Array = v
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


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


## Metres from the origin back to the back face (see `back`).
func back_depth() -> float:
	if back >= 0.0:
		return back
	return 0.0 if wall_mounted else size.z * 0.5


## Centre of the prop's collision box in its own frame: up half its height, and forward off a wall
## plane origin so the box covers the model rather than reaching into the wall behind it.
func box_centre() -> Vector3:
	return Vector3(0.0, size.y * 0.5, size.z * 0.5 - back_depth())


## The prop's collision boxes in its own frame: [[size: Vector3, centre: Transform3D]], one per
## `boxes` entry, else the one size box (grown to at least `min_size` each way). Empty for
## collision "none".
func collision_boxes(min_size: Vector3 = Vector3(0.05, 0.05, 0.05)) -> Array:
	if collision == "none":
		return []
	if boxes.is_empty():
		return [[size.max(min_size), Transform3D(Basis.IDENTITY, box_centre())]]
	var out: Array = []
	for b: Dictionary in boxes:
		var sz: Vector3 = b["size"]
		out.append([sz, Transform3D(Basis(Vector3.UP, deg_to_rad(float(b["yaw"]))), (b["at"] as Vector3) + Vector3.UP * sz.y * 0.5)])
	return out


## Whether a point in the prop's frame (its height ignored) lies within `margin` of the plan
## footprint of what the prop collides with: the size box centred on the origin (the footprint
## SleeperAnchors always used), or each of `boxes` whose base is lower than `below` (m).
func plan_hits(local: Vector3, margin: float, below: float = INF) -> bool:
	if boxes.is_empty():
		return absf(local.x) < size.x * 0.5 + margin and absf(local.z) < size.z * 0.5 + margin
	for b: Dictionary in boxes:
		var at: Vector3 = b["at"]
		if at.y >= below:
			continue
		var q: Vector3 = Basis(Vector3.UP, -deg_to_rad(float(b["yaw"]))) * (local - at)
		var sz: Vector3 = b["size"]
		if absf(q.x) < sz.x * 0.5 + margin and absf(q.z) < sz.z * 0.5 + margin:
			return true
	return false


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
