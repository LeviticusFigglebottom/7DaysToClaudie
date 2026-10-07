class_name ViewModelHolds
extends RefCounted
## How an item is held in first person (ADR-0029), read from data/config/viewmodel.json: its hold
## class (one_hand, club, spear, two_hand, light_left, pistol, held, food, bottle, blueprint,
## empty...), the baked arms actions that go with it, its attack style and use action, how it sits
## in the hand, and what its guard absorbs. Static and node-free, so tests can ask it directly.

const EMPTY: StringName = &"empty"


static func config() -> Dictionary:
	return Content.config(&"viewmodel")


## The hold class for an item (null = empty hands): equip.hold, else by equip.kind, then (melee)
## by damage_type, then by category, else the fallback.
static func hold_class(def: ItemDef, cfg: Dictionary = {}) -> StringName:
	if def == null:
		return EMPTY
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	var holds: Dictionary = c.get("holds", {})
	var explicit: String = str(def.equip.get("hold", ""))
	if explicit != "" and holds.has(explicit):
		return StringName(explicit)
	var dfl: Dictionary = c.get("defaults", {})
	var kind: String = str(def.equip.get("kind", ""))
	var by_kind: Dictionary = dfl.get("by_kind", {})
	if by_kind.has(kind):
		return StringName(str(by_kind[kind]))
	if kind == "melee":
		var by_dt: Dictionary = dfl.get("by_damage_type", {})
		var dt: String = str(def.equip.get("damage_type", ""))
		if by_dt.has(dt):
			return StringName(str(by_dt[dt]))
	var by_cat: Dictionary = dfl.get("by_category", {})
	if by_cat.has(def.category):
		return StringName(str(by_cat[def.category]))
	return StringName(str(dfl.get("fallback", "held")))


static func hold(cls: StringName, cfg: Dictionary = {}) -> Dictionary:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	return (c.get("holds", {}) as Dictionary).get(String(cls), {})


## The swing an item makes (equip.swing, else its hold's attack): an attacks key, or &"".
static func attack_style(def: ItemDef, cls: StringName, cfg: Dictionary = {}) -> StringName:
	if def != null and str(def.equip.get("swing", "")) != "":
		return StringName(str(def.equip["swing"]))
	return StringName(str(hold(cls, cfg).get("attack", "")))


## Fraction of attack_time at which the swing connects (the keyed contact frame).
static func impact_fraction(style: StringName, cfg: Dictionary = {}) -> float:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	var a: Dictionary = (c.get("attacks", {}) as Dictionary).get(String(style), {})
	return float(a.get("impact", 0.45))


## The use action for a consumable or placeable (eat, drink, apply, place...), or &"".
static func use_action(def: ItemDef, cls: StringName, cfg: Dictionary = {}) -> StringName:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	if def != null:
		var by_cat: Dictionary = (c.get("defaults", {}) as Dictionary).get("use_by_category", {})
		if by_cat.has(def.category):
			return StringName(str(by_cat[def.category]))
	return StringName(str(hold(cls, c).get("use", "")))


## The arms action names for a hold class: idle loop, guard, tether reading.
static func idle_action(cls: StringName) -> StringName:
	return StringName("fp_%s" % cls)


static func guard_action(cls: StringName) -> StringName:
	return StringName("fp_%s_guard" % cls)


static func tether_action(cls: StringName) -> StringName:
	return StringName("fp_%s_tether" % cls)


## Share of a blocked blow's damage the guard takes: equip.block, else the hold's. 0 = no guard.
static func block_share(def: ItemDef, cls: StringName, cfg: Dictionary = {}) -> float:
	if def != null and def.equip.has("block"):
		return clampf(float(def.equip["block"]), 0.0, 0.95)
	var h: Dictionary = hold(cls, cfg)
	if not h.has("guard"):
		return 0.0
	return clampf(float(h.get("block", 0.0)), 0.0, 0.95)


## Which hand holds the item: "R" or "L".
static func item_hand(cls: StringName, cfg: Dictionary = {}) -> String:
	return str(hold(cls, cfg).get("hand", "R"))


## The item's placement in its hand socket: the hold's rotation (degrees) and offset, combined
## with the item's own equip.grip_rot (which turns its model into the tool frame: handle +Y,
## edge or face +Z).
static func item_transform(def: ItemDef, cls: StringName, cfg: Dictionary = {}) -> Transform3D:
	var it: Dictionary = hold(cls, cfg).get("item", {})
	var r: Array = it.get("rot", [0, 0, 0])
	var p: Array = it.get("pos", [0, 0, 0])
	var cls_b := Basis.from_euler(Vector3(deg_to_rad(float(r[0])), deg_to_rad(float(r[1])), deg_to_rad(float(r[2]))))
	var g: Array = def.equip.get("grip_rot", []) if def != null else []
	var item_b := Basis.from_euler(Vector3(deg_to_rad(float(g[0])), deg_to_rad(float(g[1])), deg_to_rad(float(g[2])))) if g.size() == 3 else Basis()
	return Transform3D(cls_b * item_b, Vector3(float(p[0]), float(p[1]), float(p[2])))


## What a swing struck, for its feedback: wood (trees, wooden pieces), bark (loose logs), flesh,
## metal, stone, dirt or solid. `receiver` is what took the damage (or null).
static func surface_kind(collider: Object, receiver: Object, cfg: Dictionary = {}) -> StringName:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	var n: Node = collider as Node
	if receiver is Enemy or (n != null and n.is_in_group(&"enemies")):
		return &"flesh"
	if n is LogEntity or (n != null and n.is_in_group(&"logs")):
		return &"bark"
	if n != null and (n.is_in_group(&"tree_body") or n.has_meta(&"veg_id")):
		return &"wood"
	if n != null and n.has_meta(&"surface"):
		var by_meta: Dictionary = (c.get("impact", {}) as Dictionary).get("by_surface_meta", {})
		var s: String = str(n.get_meta(&"surface"))
		if by_meta.has(s):
			return StringName(str(by_meta[s]))
	if n != null and n.has_meta(&"terrain"):
		return &"dirt"
	return &"solid"


## Problems with the hold data (unknown classes, attacks on missing holds, bad item mappings),
## for validation and tests.
## The wrist range the arms generator keeps every baked hand inside (viewmodel.json `wrist`).
const WRIST_KEYS: PackedStringArray = ["flex", "extend", "radial", "ulnar", "roll"]


static func problems(cfg: Dictionary = {}) -> PackedStringArray:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	var out: PackedStringArray = []
	var holds: Dictionary = c.get("holds", {})
	for k: String in ["by_kind", "by_damage_type", "by_category"]:
		var m: Dictionary = (c.get("defaults", {}) as Dictionary).get(k, {})
		for key: Variant in m:
			if not holds.has(str(m[key])):
				out.append("viewmodel: defaults.%s.%s names unknown hold '%s'" % [k, key, m[key]])
	for cls: String in holds:
		if cls.begins_with("_"):
			continue
		var h: Dictionary = holds[cls]
		if not h.has("pose"):
			out.append("viewmodel: hold '%s' has no pose" % cls)
		var atk: String = str(h.get("attack", ""))
		if atk != "" and not (c.get("attacks", {}) as Dictionary).has(atk):
			out.append("viewmodel: hold '%s' attack '%s' is not an attack" % [cls, atk])
		var use: String = str(h.get("use", ""))
		if use != "" and not (c.get("uses", {}) as Dictionary).has(use):
			out.append("viewmodel: hold '%s' use '%s' is not a use" % [cls, use])
	var wrist: Dictionary = c.get("wrist", {})
	for k: String in WRIST_KEYS:
		var v: Variant = wrist.get(k, null)
		if not (v is float or v is int) or float(v) <= 0.0 or float(v) > 120.0:
			out.append("viewmodel: wrist.%s must be a number of degrees in (0, 120]" % k)
	for group: String in ["attacks", "uses"]:
		var g: Dictionary = c.get(group, {})
		for name: String in g:
			if name.begins_with("_"):
				continue
			if not holds.has(str((g[name] as Dictionary).get("hold", ""))):
				out.append("viewmodel: %s.%s keys on unknown hold '%s'" % [group, name, (g[name] as Dictionary).get("hold", "")])
	return out
