class_name LotPicker
extends RefCounted
## What stands on each lot of a placed framework (ADR-0030). A lot with an authored "pick" holds
## that building. A lot without one chooses, deterministically from the world seed and its
## placement, by zoning and tier: an authored building from the pool (one not already standing in
## this framework, whose footprint fits), or a generated ordinary building from a
## BuildingTemplateDef whose zoning matches. "pool" narrows that to "authored" or "generated",
## "templates" names the templates a lot may generate, "tier" ([lo, hi] or a number) overrides the
## framework's tier_range (a lot that names templates generates unless its pool says otherwise),
## and "reserved" holds the lot empty for a building still to be authored
## (the school, the fire station, the bank).
## Pure function of the framework, the placement id and the world seed: PoiManager (which places
## the buildings) and TerrainHoles (which cuts their cellars) resolve the same lots the same way.
## Content comes from ContentDB.instance.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Generator := preload("res://src/poi/building_generator.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")

const POOLS: PackedStringArray = ["any", "authored", "generated"]
## Lot keys (FrameworkDef checks them).
const LOT_KEYS: PackedStringArray = ["id", "rect", "zoning", "facing", "pick", "tags", "tier", "pool", "templates", "reserved"]
## An authored building weighs this much against a template of weight 1.
const AUTHORED_WEIGHT: float = 1.0


## The lot's size as the building sees it: x along the street, y depth (its front faces `facing`).
static func lot_size(lot: Dictionary) -> Vector2i:
	var r: Array = lot.get("rect", [0, 0, 0, 0])
	var facing: String = str(lot.get("facing", "S"))
	return Vector2i(int(r[2]), int(r[3])) if facing in ["S", "N"] else Vector2i(int(r[3]), int(r[2]))


## One entry per lot, in order: {"lot": Dictionary, "kind": "authored" | "generated" | "reserved" |
## "empty", "def_id": StringName (authored), "template": StringName (generated), "seed": int,
## "size": Vector2i, "instance": "<placement>/<lot id>"}.
static func resolve(fw: FrameworkDef, placement_id: String, world_seed: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var db: Node = ContentDB.instance
	var used: Dictionary = {}
	for lot: Variant in fw.lots:
		if lot is Dictionary and str((lot as Dictionary).get("pick", "")) != "":
			used[str(lot["pick"])] = true
	for lot2: Variant in fw.lots:
		if not lot2 is Dictionary:
			continue
		var l: Dictionary = lot2
		var res: Dictionary = {"lot": l, "kind": "empty", "size": lot_size(l), "instance": "%s/%s" % [placement_id, l.get("id", "")],
			"seed": Ids.hash64("lot:%d:%s/%s" % [world_seed, placement_id, l.get("id", "")])}
		var pick: String = str(l.get("pick", ""))
		if pick != "":
			res["kind"] = "authored"
			res["def_id"] = StringName(pick)
		elif l.has("reserved"):
			res["kind"] = "reserved"
		elif db != null:
			_choose(fw, l, res, used, db)
		out.append(res)
	return out


static func _choose(fw: FrameworkDef, l: Dictionary, res: Dictionary, used: Dictionary, db: Node) -> void:
	var size: Vector2i = res["size"]
	var zon: PackedStringArray = PackedStringArray(l.get("zoning", []))
	var tr: Vector2i = fw.tier_range
	var lt: Variant = l.get("tier", null)
	if lt is Array and (lt as Array).size() == 2:
		tr = Vector2i(int(lt[0]), int(lt[1]))
	elif lt is float or lt is int:
		tr = Vector2i(int(lt), int(lt))
	# A lot that names its templates means generated buildings unless it says otherwise.
	var pool: String = str(l.get("pool", "generated" if l.has("templates") else "any"))
	var allowed: Array = l.get("templates", [])
	var cands: Array = []
	if pool != "generated":
		for pd: Variant in db.call(&"all", &"poi"):
			var p: PoiDef = pd
			if used.has(String(p.id)) or p.tier < tr.x or p.tier > tr.y or not _zoned(p.zoning, zon):
				continue
			# The footprint fits the lot's own frame (x along the street, y depth).
			if p.footprint.x > size.x or p.footprint.y > size.y:
				continue
			cands.append([AUTHORED_WEIGHT, "authored", p.id])
	if pool != "authored":
		for td: Variant in db.call(&"all", &"building_template"):
			var t: TemplateDef = td
			if not allowed.is_empty():
				if not allowed.has(String(t.id)):
					continue
			elif not _zoned(t.zoning, zon) or t.tier < tr.x or t.tier > tr.y:
				continue
			if t.weight <= 0.0 or not Generator.fits(t, size):
				continue
			cands.append([t.weight, "generated", t.id])
	if cands.is_empty():
		return
	var total: float = 0.0
	for c: Array in cands:
		total += float(c[0])
	var rng := RandomNumberGenerator.new()
	rng.seed = int(res["seed"])
	var x: float = rng.randf() * total
	var pick: Array = cands.back()
	for c2: Array in cands:
		x -= float(c2[0])
		if x < 0.0:
			pick = c2
			break
	res["kind"] = pick[1]
	if str(pick[1]) == "authored":
		res["def_id"] = pick[2]
		used[String(pick[2])] = true
	else:
		res["template"] = pick[2]


static func _zoned(have: PackedStringArray, want: PackedStringArray) -> bool:
	if want.is_empty():
		return true
	for z: String in have:
		if want.has(z):
			return true
	return false


## The PoiDef standing on a resolved lot (authored from content, generated from its template and
## seed; null for reserved and empty lots). Generated defs are named after the lot.
static func def_for(res: Dictionary) -> PoiDef:
	var db: Node = ContentDB.instance
	if db == null:
		return null
	match str(res.get("kind", "")):
		"authored":
			return db.call(&"get_def", &"poi", StringName(str(res["def_id"]))) as PoiDef
		"generated":
			var t: TemplateDef = db.call(&"get_def", &"building_template", StringName(str(res["template"]))) as TemplateDef
			if t == null:
				return null
			return Generator.generate(t, int(res["seed"]), res["size"], gen_id(res))
	return null


## The def id of a generated building: its template and the lot it stands on.
static func gen_id(res: Dictionary) -> String:
	var s: String = "%s_%s" % [res.get("template", "gen"), str(res.get("instance", "")).replace("/", "_")]
	var out: String = ""
	for ch: String in s.to_lower():
		out += ch if ((ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or ch == "_") else "_"
	return out


## The world seed of the running session (0 without one: previews, tests). Read through the scene
## tree, not the Game autoload, so worker-safe code that calls this compiles before autoloads exist.
static func session_seed() -> int:
	var ml: SceneTree = Engine.get_main_loop() as SceneTree
	var game: Node = ml.root.get_node_or_null(^"Game") if ml != null else null
	var session: Variant = game.get(&"session") if game != null else null
	return int((session as Object).get(&"world_seed")) if session != null else 0
