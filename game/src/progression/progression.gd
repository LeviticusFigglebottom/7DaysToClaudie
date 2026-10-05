class_name Progression
extends RefCounted
## Character progression: XP/levels, attributes (Sinew, Grit, Keen, Quiet, Wits), perks,
## learned schematics/blueprints and learn-by-reading skill tracks (field journals).
## Systems query effects through modifier(key) (sum of perk-rank effects + attribute per_level).

signal leveled_up(new_level: int)
signal learned(kind: StringName, id: StringName)
## Points went into an attribute or perk (derived player stats need recomputing).
signal spent()

var level: int = 1
var xp: int = 0
var skill_points: int = 0
## attribute id -> level (starts at 1)
var attributes: Dictionary = {}
## perk id -> rank (0 = not owned)
var perks: Dictionary = {}
var known_recipes: Dictionary = {}
var known_blueprints: Dictionary = {}
## learn-by-reading skill tracks: skill id -> points
var skills: Dictionary = {}

var _cfg: Dictionary = {}


func _init() -> void:
	_cfg = Content.config(&"progression")
	for a: AttributeDef in Content.all(&"attribute"):
		attributes[a.id] = 1
	skill_points = int(_cfg.get("starting_points", 0))


func xp_to_next() -> int:
	var base: float = float(_cfg.get("xp_base", 400.0))
	var growth: float = float(_cfg.get("xp_growth", 1.18))
	return int(base * pow(growth, level - 1))


## Adds XP; returns levels gained.
func add_xp(amount: int) -> int:
	amount = int(round(float(amount) * GameRules.current().num("xp_multiplier")))
	if amount <= 0:
		return 0
	xp += amount
	var gained: int = 0
	while xp >= xp_to_next():
		xp -= xp_to_next()
		level += 1
		skill_points += int(_cfg.get("points_per_level", 1))
		gained += 1
		leveled_up.emit(level)
	return gained


## XP for a named source from data/config/progression.json "xp" (kill, loot, build, survive the
## Hum...), times `times` (POI tier, container tier). Returns levels gained.
func award(source: String, times: float = 1.0) -> int:
	var table: Dictionary = _cfg.get("xp", {})
	if not table.has(source):
		push_warning("Progression: unknown XP source '%s'" % source)
		return 0
	return add_xp(int(round(float(table[source]) * times)))


func attr_level(id: StringName) -> int:
	return int(attributes.get(id, 1))


func perk_rank(id: StringName) -> int:
	return int(perks.get(id, 0))


func attribute_cost(id: StringName) -> int:
	var lvl: int = attr_level(id)
	return 1 + int(lvl / int(_cfg.get("attribute_cost_step", 3)))


func can_raise_attribute(id: StringName) -> bool:
	return attribute_block_reason(id) == ""


## Why an attribute can't be trained right now ("" = it can). Shown in the Record tab.
func attribute_block_reason(id: StringName) -> String:
	var a: AttributeDef = Content.get_def(&"attribute", id) as AttributeDef
	if a == null:
		return "unknown attribute"
	if attr_level(id) >= a.max_level:
		return "at its peak"
	var cost: int = attribute_cost(id)
	if skill_points < cost:
		return "needs %d point%s" % [cost, "" if cost == 1 else "s"]
	return ""


func raise_attribute(id: StringName) -> bool:
	if not can_raise_attribute(id):
		return false
	skill_points -= attribute_cost(id)
	attributes[id] = attr_level(id) + 1
	spent.emit()
	return true


func can_buy_perk(id: StringName) -> bool:
	return perk_block_reason(id) == ""


## Why a perk's next rank can't be learned right now ("" = it can).
func perk_block_reason(id: StringName) -> String:
	var p: PerkDef = Content.get_def(&"perk", id) as PerkDef
	if p == null:
		return "unknown perk"
	var next_rank: int = perk_rank(id) + 1
	if next_rank > p.max_rank():
		return "fully learned"
	var need: int = int(p.ranks[next_rank - 1]["attr_level"])
	if attr_level(p.attribute) < need:
		var a: AttributeDef = Content.get_def(&"attribute", p.attribute) as AttributeDef
		return "needs %s %d" % [a.display_name if a != null else String(p.attribute), need]
	if skill_points < 1:
		return "needs 1 point"
	return ""


func buy_perk(id: StringName) -> bool:
	if not can_buy_perk(id):
		return false
	skill_points -= 1
	perks[id] = perk_rank(id) + 1
	var p: PerkDef = Content.get_def(&"perk", id) as PerkDef
	for u: String in p.ranks[perk_rank(id) - 1]["unlocks"]:
		_learn(StringName(u))
	spent.emit()
	return true


## Sum of a named effect across owned perk ranks and attribute levels.
func modifier(key: String, default: float = 0.0) -> float:
	var total: float = default
	for pid: StringName in perks:
		var p: PerkDef = Content.get_def(&"perk", pid) as PerkDef
		if p == null:
			continue
		for i: int in mini(perk_rank(pid), p.max_rank()):
			total += float((p.ranks[i]["effects"] as Dictionary).get(key, 0.0))
	for aid: StringName in attributes:
		var a: AttributeDef = Content.get_def(&"attribute", aid) as AttributeDef
		if a != null and a.per_level.has(key):
			total += float(a.per_level[key]) * float(attr_level(aid) - 1)
	return total


func knows_recipe(r: RecipeDef) -> bool:
	if r == null:
		return false
	if r.unlock == "default":
		return true
	if known_recipes.has(r.id):
		return true
	if r.unlock.begins_with("perk:"):
		var parts: PackedStringArray = r.unlock.split(":")
		return perk_rank(StringName(parts[1])) >= int(parts[2])
	if r.unlock.begins_with("skill:"):
		var sp: PackedStringArray = r.unlock.split(":")
		return int(skills.get(StringName(sp[1]), 0)) >= int(sp[2])
	return false


func knows_blueprint(b: BlueprintDef) -> bool:
	return b != null and (b.unlock == "default" or known_blueprints.has(b.id))


## Reading a schematic/journal item. Returns {kind, id} learned ({} if nothing new).
func learn_from_item(def: ItemDef) -> Dictionary:
	if def == null or def.teaches.is_empty():
		return {}
	if def.teaches.has("recipe"):
		var rid := StringName(def.teaches["recipe"])
		if known_recipes.has(rid):
			return {}
		_learn(rid)
		return {"kind": &"recipe", "id": rid}
	if def.teaches.has("blueprint"):
		var bid := StringName(def.teaches["blueprint"])
		if known_blueprints.has(bid):
			return {}
		_learn(bid)
		return {"kind": &"blueprint", "id": bid}
	if def.teaches.has("skill"):
		var sid := StringName(def.teaches["skill"])
		skills[sid] = int(skills.get(sid, 0)) + int(def.teaches.get("points", 1))
		learned.emit(&"skill", sid)
		return {"kind": &"skill", "id": sid, "points": skills[sid]}
	return {}


func _learn(id: StringName) -> void:
	if Content.has_def(&"recipe", id):
		known_recipes[id] = true
		learned.emit(&"recipe", id)
	elif Content.has_def(&"blueprint", id):
		known_blueprints[id] = true
		learned.emit(&"blueprint", id)


func to_dict() -> Dictionary:
	return {
		"level": level, "xp": xp, "points": skill_points, "attributes": _sn_keys(attributes),
		"perks": _sn_keys(perks), "recipes": _sn_list(known_recipes), "blueprints": _sn_list(known_blueprints),
		"skills": _sn_keys(skills),
	}


func from_dict(d: Dictionary) -> void:
	level = int(d.get("level", 1))
	xp = int(d.get("xp", 0))
	skill_points = int(d.get("points", 0))
	for k: Variant in (d.get("attributes", {}) as Dictionary).keys():
		attributes[StringName(str(k))] = int(d["attributes"][k])
	perks.clear()
	for k: Variant in (d.get("perks", {}) as Dictionary).keys():
		perks[StringName(str(k))] = int(d["perks"][k])
	known_recipes.clear()
	for r: Variant in d.get("recipes", []):
		known_recipes[StringName(str(r))] = true
	known_blueprints.clear()
	for b: Variant in d.get("blueprints", []):
		known_blueprints[StringName(str(b))] = true
	skills.clear()
	for k: Variant in (d.get("skills", {}) as Dictionary).keys():
		skills[StringName(str(k))] = int(d["skills"][k])


static func _sn_keys(src: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in src.keys():
		out[String(k)] = src[k]
	return out


static func _sn_list(src: Dictionary) -> Array:
	var out: Array = []
	for k: Variant in src.keys():
		out.append(String(k))
	out.sort()
	return out
