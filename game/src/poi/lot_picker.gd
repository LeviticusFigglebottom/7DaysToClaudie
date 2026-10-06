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
##
## An organic town of a random world (ADR-0040) has frame lots (`frame: [cx, cz, w, d, yaw]`, world
## XZ): `lot_size` reads the frame and `lot_local_xf` stands the building in it. Its authored
## buildings are capped world-wide: the generator runs `assign_authored` over every town of the
## world and writes each town's share into its framework (`authored`), and an organic town's lots
## choose authored buildings from that list only (v1 towns, rect lots, are unchanged).

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Generator := preload("res://src/poi/building_generator.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")

const POOLS: PackedStringArray = ["any", "authored", "generated"]
## Lot keys (FrameworkDef checks them).
const LOT_KEYS: PackedStringArray = ["id", "rect", "zoning", "facing", "pick", "tags", "tier", "pool", "templates", "reserved",
	"frame", "poly", "street", "ring", "y"]
## An authored building weighs this much against a template of weight 1.
const AUTHORED_WEIGHT: float = 1.0


## The lot's size as the building sees it: x along the street, y depth (its front faces `facing`;
## a frame's front is its local +Z, so its frontage and depth are already the building's x and y).
static func lot_size(lot: Dictionary) -> Vector2i:
	if lot.has("frame"):
		var f: Array = lot["frame"]
		return Vector2i(int(f[2]), int(f[3]))
	var r: Array = lot.get("rect", [0, 0, 0, 0])
	var facing: String = str(lot.get("facing", "S"))
	return Vector2i(int(r[2]), int(r[3])) if facing in ["S", "N"] else Vector2i(int(r[3]), int(r[2]))


## A frame lot's building transform in the framework's frame (an organic town's is the world's):
## T(cx, y, cz) · Basis(UP, yaw) · T(-footprint / 2), the footprint centred in the frame, its front
## (+Z) towards the street. The same convention as PoiManager.lot_xf (facing S is yaw 0, E 90).
static func lot_local_xf(lot: Dictionary, footprint: Vector2i) -> Transform3D:
	var f: Array = lot["frame"]
	var b := Basis(Vector3.UP, deg_to_rad(float(f[4])))
	var c := Vector3(float(f[0]), float(lot.get("y", 0.0)), float(f[1]))
	return Transform3D(b, c - b * Vector3(footprint.x * 0.5, 0.0, footprint.y * 0.5))


## A lot's centre in its framework's plane (x, z): a frame's centre, or a rect's middle.
static func lot_center(lot: Dictionary) -> Vector2:
	if lot.has("frame"):
		return Vector2(float(lot["frame"][0]), float(lot["frame"][1]))
	var r: Array = lot.get("rect", [0, 0, 0, 0])
	return Vector2(float(r[0]) + float(r[2]) * 0.5, float(r[1]) + float(r[3]) * 0.5)


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
	# An organic town holds only the authored buildings the world gave it (assign_authored).
	var capped: bool = fw.layout == "organic"
	if pool != "generated":
		for pd: Variant in db.call(&"all", &"poi"):
			var p: PoiDef = pd
			if used.has(String(p.id)) or p.tier < tr.x or p.tier > tr.y or not _zoned(p.zoning, zon):
				continue
			if capped and not fw.authored.has(String(p.id)):
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


## World-wide caps on authored buildings (ADR-0040, random worlds v2; plan §3.11): which towns of a
## world may hold each authored building, at most `cap` towns per building, so 32 towns do not
## each get a Merrow House. `towns`: [{id, tier_range: [lo, hi], lots: [{frame | rect, zoning, ...}]}]
## (framework dictionaries). For each authored POI (by id) the towns with a lot it fits (zoning,
## tier, size) are listed in town-id order and `cap` of them drawn from a stream of `seed` and the
## POI's id. Returns {town id: PackedStringArray of POI ids, sorted}. Pure (content from ContentDB).
static func assign_authored(towns: Array, seed: int, cap: int) -> Dictionary:
	var out: Dictionary = {}
	var ids: PackedStringArray = []
	var by_id: Dictionary = {}
	for tv: Variant in towns:
		var t: Dictionary = tv
		ids.append(str(t.get("id", "")))
		by_id[str(t.get("id", ""))] = t
		out[str(t.get("id", ""))] = []
	ids.sort()
	var db: Node = ContentDB.instance
	if db == null or ids.is_empty() or cap <= 0:
		for tid0: String in ids:
			out[tid0] = PackedStringArray()
		return out
	# ContentDB.all is sorted by id.
	for pv: Variant in db.call(&"all", &"poi"):
		var p: PoiDef = pv
		var fits: PackedStringArray = []
		for tid: String in ids:
			var t: Dictionary = by_id[tid]
			var tr: Array = t.get("tier_range", [1, 3])
			if p.tier < int(tr[0]) or p.tier > int(tr[1]):
				continue
			for lv: Variant in t.get("lots", []):
				var l: Dictionary = lv
				var size: Vector2i = lot_size(l)
				if _zoned(p.zoning, PackedStringArray(l.get("zoning", []))) and p.footprint.x <= size.x and p.footprint.y <= size.y:
					fits.append(tid)
					break
		if fits.is_empty():
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.derive_seed(seed, "authored:%s" % p.id)
		# A seeded partial Fisher-Yates over the towns in id order: `cap` of them, each equally likely.
		var order: PackedStringArray = fits.duplicate()
		for k: int in mini(cap, order.size()):
			var j: int = k + rng.randi_range(0, order.size() - 1 - k)
			var tmp: String = order[k]
			order[k] = order[j]
			order[j] = tmp
			(out[order[k]] as Array).append(String(p.id))
	for tid2: String in ids:
		var lst := PackedStringArray(out[tid2])
		lst.sort()
		out[tid2] = lst
	return out


## The largest authored footprint (per axis: x along the street, y depth) that could stand on a lot,
## whatever the run's seed picks (Vector2i.ZERO: only generated buildings or nothing). The composer
## keeps a town yard's grass off it (TD-136): which building a lot holds is a run-seed choice, and
## the terrain is a function of the world's data alone. A generated building keeps its own yards
## (BuildingGenerator.SIDE_YARD, BACK_YARD) inside the frame, so it needs no clip. Same filter as
## _choose, less the `used` dedupe (any candidate may win).
static func max_authored_footprint(fw: FrameworkDef, l: Dictionary) -> Vector2i:
	var db: Node = ContentDB.instance
	if db == null or l.has("reserved"):
		return Vector2i.ZERO
	var pick: String = str(l.get("pick", ""))
	if pick != "":
		var pp: PoiDef = db.call(&"get_def", &"poi", StringName(pick)) as PoiDef
		return pp.footprint if pp != null else Vector2i.ZERO
	var pool: String = str(l.get("pool", "generated" if l.has("templates") else "any"))
	if pool == "generated":
		return Vector2i.ZERO
	var size: Vector2i = lot_size(l)
	var zon: PackedStringArray = PackedStringArray(l.get("zoning", []))
	var tr: Vector2i = fw.tier_range
	var lt: Variant = l.get("tier", null)
	if lt is Array and (lt as Array).size() == 2:
		tr = Vector2i(int(lt[0]), int(lt[1]))
	elif lt is float or lt is int:
		tr = Vector2i(int(lt), int(lt))
	var capped: bool = fw.layout == "organic"
	var out := Vector2i.ZERO
	for pd: Variant in db.call(&"all", &"poi"):
		var p: PoiDef = pd
		if p.tier < tr.x or p.tier > tr.y or not _zoned(p.zoning, zon):
			continue
		if capped and not fw.authored.has(String(p.id)):
			continue
		if p.footprint.x > size.x or p.footprint.y > size.y:
			continue
		out = Vector2i(maxi(out.x, p.footprint.x), maxi(out.y, p.footprint.y))
	return out


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
