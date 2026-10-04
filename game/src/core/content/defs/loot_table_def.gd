class_name LootTableDef
extends ContentDef
## Weighted loot table. Entries reference items or nested tables. See LootRoller.

## [min, max] number of rolls.
var rolls: Vector2i = Vector2i(1, 1)
## Chance the whole container is empty (before tier adjustment).
var empty_chance: float = 0.0
## Each: {item|table, weight, count:Vector2i, tier_min, tier_max, quality_bias}
var entries: Array[Dictionary] = []
## Always added: {item, count:Vector2i}
var guaranteed: Array[Dictionary] = []


func _fields() -> PackedStringArray:
	return ["rolls", "empty_chance", "entries", "guaranteed"]


func _parse(r: DefReader) -> void:
	var rr: Vector2 = r.range2("rolls", Vector2(1, 1))
	rolls = Vector2i(int(rr.x), int(rr.y))
	empty_chance = clampf(r.num("empty_chance", 0.0), 0.0, 1.0)
	for e: Variant in r.arr("entries"):
		if not e is Dictionary:
			r.err("entries must be objects")
			continue
		var er := DefReader.new(e, "%s entry" % ctx())
		var entry: Dictionary = {
			"item": er.sname("item"),
			"table": er.sname("table"),
			"weight": er.num("weight", 1.0),
			"count": _vi(er.range2("count", Vector2(1, 1))),
			"tier_min": er.integer("tier_min", 0),
			"tier_max": er.integer("tier_max", 99),
			"quality_bias": er.integer("quality_bias", 0),
		}
		er.check_unknown(["item", "table", "weight", "count", "tier_min", "tier_max", "quality_bias"])
		if entry["item"] == &"" and entry["table"] == &"":
			er.err("entry needs 'item' or 'table'")
		r.errors.append_array(er.errors)
		entries.append(entry)
	for g: Variant in r.arr("guaranteed"):
		if g is Dictionary:
			var gr := DefReader.new(g, "%s guaranteed" % ctx())
			guaranteed.append({"item": StringName(gr.req_str("item")), "count": _vi(gr.range2("count", Vector2(1, 1)))})
			r.errors.append_array(gr.errors)


func _validate(db: Node, out: PackedStringArray) -> void:
	for e: Dictionary in entries:
		if e["item"] != &"" and not db.has_def(&"item", e["item"]):
			out.append("%s: entry item '%s' unknown" % [ctx(), e["item"]])
		if e["table"] != &"":
			if not db.has_def(&"loot_table", e["table"]):
				out.append("%s: nested table '%s' unknown" % [ctx(), e["table"]])
			elif e["table"] == id:
				out.append("%s: table references itself" % ctx())
	for g: Dictionary in guaranteed:
		if not db.has_def(&"item", g["item"]):
			out.append("%s: guaranteed item '%s' unknown" % [ctx(), g["item"]])


static func _vi(v: Vector2) -> Vector2i:
	return Vector2i(int(v.x), int(v.y))
