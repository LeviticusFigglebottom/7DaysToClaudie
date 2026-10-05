class_name ItemStack
extends RefCounted
## A stack of one item type. Per-instance state (quality, durability, extra data) lives here.

var item_id: StringName
var count: int = 1
## 0 = item has no quality; 1..6 otherwise.
var quality: int = 0
## Remaining durability; < 0 means "not tracked".
var durability: float = -1.0
## Extra per-instance data (e.g. loaded ammo). Must be JSON-serializable.
var data: Dictionary = {}


static func make(id: StringName, n: int = 1, q: int = 0) -> ItemStack:
	var s := ItemStack.new()
	s.item_id = id
	s.count = n
	var d: ItemDef = s.def()
	if d != null:
		if d.has_quality:
			s.quality = clampi(q if q > 0 else 1, 1, 6)
		if d.durability > 0.0:
			s.durability = d.durability * quality_durability_mult(s.quality)
	return s


static func quality_durability_mult(q: int) -> float:
	return 1.0 if q <= 0 else 0.75 + 0.15 * float(q)


## Weapon damage factor for a quality tier (Q1 0.95 ... Q6 1.45).
static func quality_damage_mult(q: int) -> float:
	return 1.0 if q <= 0 else 0.85 + 0.1 * float(q)


## Tier name and colour for quality 1..6 (data/config/loot.json "quality_tiers").
static func quality_name(q: int) -> String:
	var tiers: Array = Content.config(&"loot").get("quality_tiers", [])
	return str((tiers[q - 1] as Dictionary).get("name", "Q%d" % q)) if q >= 1 and q <= tiers.size() else "Q%d" % q


static func quality_color(q: int) -> Color:
	var tiers: Array = Content.config(&"loot").get("quality_tiers", [])
	return Color.html(str((tiers[q - 1] as Dictionary).get("color", "#ffffff"))) if q >= 1 and q <= tiers.size() else Color.WHITE


func def() -> ItemDef:
	return Content.item(item_id)


func max_stack() -> int:
	var d: ItemDef = def()
	return 1 if d == null else d.stack_max


func is_damaged() -> bool:
	var d: ItemDef = def()
	return d != null and d.durability > 0.0 and durability < d.durability * quality_durability_mult(quality) - 0.001


## Two stacks can merge when they are the same item, quality and carry no unique state.
func can_merge(other: ItemStack) -> bool:
	return other != null and other.item_id == item_id and other.quality == quality \
		and data.is_empty() and other.data.is_empty() and not is_damaged() and not other.is_damaged() \
		and max_stack() > 1


func duplicate_stack() -> ItemStack:
	var s := ItemStack.new()
	s.item_id = item_id
	s.count = count
	s.quality = quality
	s.durability = durability
	s.data = data.duplicate(true)
	return s


## Splits off `n` items into a new stack (n is clamped to count).
func split(n: int) -> ItemStack:
	var take: int = clampi(n, 0, count)
	var s: ItemStack = duplicate_stack()
	s.count = take
	count -= take
	return s


func to_dict() -> Dictionary:
	var d: Dictionary = {"id": String(item_id), "n": count}
	if quality > 0:
		d["q"] = quality
	if durability >= 0.0:
		d["dur"] = snappedf(durability, 0.01)
	if not data.is_empty():
		d["data"] = data
	return d


static func from_dict(d: Dictionary) -> ItemStack:
	var s := ItemStack.new()
	s.item_id = StringName(str(d.get("id", "")))
	s.count = int(d.get("n", 1))
	s.quality = int(d.get("q", 0))
	s.durability = float(d.get("dur", -1.0))
	s.data = d.get("data", {})
	return s


func _to_string() -> String:
	return "%s x%d%s" % [item_id, count, (" Q%d" % quality) if quality > 0 else ""]
