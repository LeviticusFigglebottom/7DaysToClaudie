class_name ItemDef
extends ContentDef
## An item type. Instances are ItemStack (count/quality/durability live there, not here).

const CATEGORIES: PackedStringArray = [
	"resource", "tool", "weapon", "ammo", "food", "drink", "medical", "clothing",
	"light", "throwable", "trap", "schematic", "magazine", "note", "quest", "key", "junk", "placeable",
]
## Tool abilities an equipped item can provide (see equip.tools).
const TOOL_KINDS: PackedStringArray = ["axe", "shovel", "pickaxe", "hammer", "knife", "lighter", "saw"]

var category: String = "resource"
## Max items per stack.
var stack_max: int = 1
## Max of this item the player can carry in the salvage roll (0 = unlimited, bulk still applies).
var carry_max: int = 0
## Encumbrance units per item.
var bulk: float = 0.1
## Trade value (Waystation scrip).
var value: int = 0
## Model id under res://assets/generated/models/ (e.g. "items/stick"); "" = placeholder.
var model: String = ""
var icon: String = ""
## Items with quality roll Q1..Q6 (tools, weapons, clothing).
var has_quality: bool = false
## Max durability (0 = indestructible / not degrading).
var durability: float = 0.0
## Seconds of fire fuel when burned (0 = not fuel).
var fuel: float = 0.0
## Equip block (slot, kind, damage, tools...) — see docs/CONTENT.md#items.
var equip: Dictionary = {}
## Consume block (hunger, thirst, health, ...) applied by SurvivalStats.consume().
var consume: Dictionary = {}
## Learn-by-reading: {"recipe": id} | {"skill": id, "points": n} | {"blueprint": id}
var teaches: Dictionary = {}
## Item produced when this one is scrapped/broken down: {item_id: count}
var scrap: Dictionary = {}
## Note id for readable items.
var note: StringName = &""


func _fields() -> PackedStringArray:
	return ["category", "stack_max", "carry_max", "bulk", "value", "model", "icon", "quality",
		"durability", "fuel", "equip", "consume", "teaches", "scrap", "note"]


func _parse(r: DefReader) -> void:
	category = r.enum_str("category", CATEGORIES, "resource")
	stack_max = maxi(1, r.integer("stack_max", 1))
	carry_max = maxi(0, r.integer("carry_max", 0))
	bulk = r.num("bulk", 0.1)
	value = r.integer("value", 0)
	# Convention: models/icons are generated per item id unless overridden.
	model = r.str_field("model", "items/%s" % id)
	icon = r.str_field("icon", "icons/%s" % id)
	has_quality = r.boolean("quality", false)
	durability = r.num("durability", 0.0)
	fuel = r.num("fuel", 0.0)
	equip = r.dict("equip")
	consume = r.dict("consume")
	teaches = r.dict("teaches")
	scrap = r.dict("scrap")
	note = r.sname("note")
	if has_quality and stack_max > 1:
		r.err("quality items must have stack_max 1")
	for t: Variant in equip.get("tools", []):
		if not TOOL_KINDS.has(str(t)):
			r.err("equip.tools has unknown tool kind '%s'" % t)


func _validate(db: Node, out: PackedStringArray) -> void:
	var ammo: String = str(equip.get("ammo", ""))
	if ammo != "" and not db.has_def(&"item", StringName(ammo)):
		out.append("%s: equip.ammo '%s' is not an item" % [ctx(), ammo])
	var returns: String = str(consume.get("returns", ""))
	if returns != "" and not db.has_def(&"item", StringName(returns)):
		out.append("%s: consume.returns '%s' is not an item" % [ctx(), returns])
	for k: Variant in scrap.keys():
		if not db.has_def(&"item", StringName(k)):
			out.append("%s: scrap item '%s' unknown" % [ctx(), k])
	if teaches.has("recipe") and not db.has_def(&"recipe", StringName(teaches["recipe"])):
		out.append("%s: teaches unknown recipe '%s'" % [ctx(), teaches["recipe"]])
	if teaches.has("blueprint") and not db.has_def(&"blueprint", StringName(teaches["blueprint"])):
		out.append("%s: teaches unknown blueprint '%s'" % [ctx(), teaches["blueprint"]])
	if note != &"" and not db.has_def(&"note", note):
		out.append("%s: note '%s' unknown" % [ctx(), note])


func is_equippable() -> bool:
	return not equip.is_empty()


func is_consumable() -> bool:
	return not consume.is_empty()


func provides_tool(tool_kind: String) -> bool:
	return (equip.get("tools", []) as Array).has(tool_kind)


func equip_num(key: String, default: float = 0.0) -> float:
	return float(equip.get(key, default))
