class_name StructureDef
extends ContentDef
## A placeable/destructible building piece (player-built or POI kit piece).
## Structural rules: see src/building/structure_graph.gd and docs/adr/0006-structural-integrity.md.

const KINDS: PackedStringArray = ["log", "foundation", "floor", "wall", "pillar", "beam", "stairs", "roof",
	"door", "window", "barricade", "defense", "station", "shelter", "storage", "decor", "assembly"]
const MATERIALS: PackedStringArray = ["log", "stick", "wood", "reinforced", "stone", "concrete", "metal", "glass"]

var piece_kind: String = "log"
var material: String = "wood"
var hp: float = 100.0
var mass: float = 50.0
## Can rest on terrain and act as a structural root.
var grounded: bool = true
## Horizontal steps of cantilever this material supports before failing.
var max_span: float = 4.0
## Stability lost per vertical step (load bearing). 0..1
var vertical_loss: float = 0.04
## Model id (assets/generated/models/<model>.glb).
var model: String = ""
## Fracture chunks model id ("" = generic debris).
var fracture: String = ""
## Local bounds size [x, y, z] in meters (used for placement + collision fallback).
var size: Vector3 = Vector3.ONE
## Snap profile handled by BuildSnapper ("log", "grid", "none").
var snap: String = "none"
## Items consumed to place: {item_id: count}
var cost: Dictionary = {}
## {"to": structure_id, "cost": {...}}
var upgrade: Dictionary = {}
## {"cost": {...}, "amount": hp}
var repair: Dictionary = {}
## Damage multipliers by damage type (blunt/slash/pierce/ballistic/fire/explosive/zombie).
var damage_mult: Dictionary = {}
var flammable: bool = false
## Contact damage dealt to enemies (spikes) per hit; 0 = none.
var contact_damage: float = 0.0
## Tags like "shelter", "sleep", "save_point", "light", "station:<id>".
var provides: PackedStringArray = []


func _fields() -> PackedStringArray:
	return ["kind", "material", "hp", "mass", "grounded", "max_span", "vertical_loss", "model", "fracture",
		"size", "snap", "cost", "upgrade", "repair", "damage_mult", "flammable", "contact_damage", "provides"]


func _parse(r: DefReader) -> void:
	piece_kind = r.enum_str("kind", KINDS, "log")
	material = r.enum_str("material", MATERIALS, "wood")
	hp = r.num("hp", 100.0)
	mass = r.num("mass", 50.0)
	grounded = r.boolean("grounded", true)
	max_span = r.num("max_span", 4.0)
	vertical_loss = r.num("vertical_loss", 0.04)
	model = r.str_field("model", "")
	fracture = r.str_field("fracture", "")
	size = r.vec3("size", Vector3.ONE)
	snap = r.enum_str("snap", ["log", "grid", "none"], "none")
	cost = r.dict("cost")
	upgrade = r.dict("upgrade")
	repair = r.dict("repair")
	damage_mult = r.dict("damage_mult")
	flammable = r.boolean("flammable", false)
	contact_damage = r.num("contact_damage", 0.0)
	provides = r.strings("provides")


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: Variant in cost.keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: cost item '%s' unknown" % [ctx(), k])
	if upgrade.has("to") and not db.has_def(&"structure", StringName(upgrade["to"])):
		out.append("%s: upgrade.to '%s' unknown" % [ctx(), upgrade["to"]])
	for k: Variant in (upgrade.get("cost", {}) as Dictionary).keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: upgrade cost item '%s' unknown" % [ctx(), k])
	for k: Variant in (repair.get("cost", {}) as Dictionary).keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: repair cost item '%s' unknown" % [ctx(), k])


func damage_multiplier(damage_type: StringName) -> float:
	return float(damage_mult.get(String(damage_type), 1.0))


func has_provide(tag: String) -> bool:
	return provides.has(tag)
