class_name HeatMap
extends RefCounted
## Attention ("heat") accumulated by noisy player activity — forges, gunfire, chopping, mining,
## fires — on a coarse world grid. When a cell crosses thresholds the director sends scouts,
## a Keener (screamer) or a wandering pack toward it. Pure model; WanderDirector acts on triggers.
## Tuning: data/config/heat.json.

var cell_size: float = 64.0
## Vector2i -> float heat
var cells: Dictionary = {}
## Vector2i -> game minutes remaining before the cell can trigger again
var cooldowns: Dictionary = {}
var decay_per_hour: float = 12.0
## [{at: heat, kind: "scout"|"keener"|"pack", cooldown_hours}] ascending
var thresholds: Array = []


func configure(cfg: Dictionary) -> void:
	cell_size = float(cfg.get("cell_size", cell_size))
	decay_per_hour = float(cfg.get("decay_per_hour", decay_per_hour))
	thresholds = cfg.get("thresholds", [
		{"at": 30.0, "kind": "scout", "cooldown_hours": 2.0},
		{"at": 70.0, "kind": "keener", "cooldown_hours": 6.0},
		{"at": 110.0, "kind": "pack", "cooldown_hours": 8.0},
	])
	thresholds.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["at"]) < float(b["at"]))


func cell_of(pos: Vector3) -> Vector2i:
	return Vector2i(int(floor(pos.x / cell_size)), int(floor(pos.z / cell_size)))


func cell_center(c: Vector2i) -> Vector3:
	return Vector3((float(c.x) + 0.5) * cell_size, 0.0, (float(c.y) + 0.5) * cell_size)


func add(pos: Vector3, amount: float) -> void:
	var c: Vector2i = cell_of(pos)
	cells[c] = float(cells.get(c, 0.0)) + amount


func heat_at(pos: Vector3) -> float:
	return float(cells.get(cell_of(pos), 0.0))


## Decays heat and returns triggers [{cell: Vector2i, pos: Vector3, heat: float, kind: String}].
func tick(game_minutes: float) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var decay: float = decay_per_hour * game_minutes / 60.0
	for c: Vector2i in cells.keys():
		var h: float = float(cells[c])
		var cd: float = float(cooldowns.get(c, 0.0))
		if cd > 0.0:
			cooldowns[c] = cd - game_minutes
		elif not thresholds.is_empty():
			var best: Dictionary = {}
			for t: Dictionary in thresholds:
				if h >= float(t["at"]):
					best = t
			if not best.is_empty():
				out.append({"cell": c, "pos": cell_center(c), "heat": h, "kind": str(best["kind"])})
				cooldowns[c] = float(best.get("cooldown_hours", 4.0)) * 60.0
				h *= 0.5
		h -= decay
		if h <= 0.0:
			cells.erase(c)
			if float(cooldowns.get(c, 0.0)) <= 0.0:
				cooldowns.erase(c)
		else:
			cells[c] = h
	return out


func to_dict() -> Dictionary:
	var c: Dictionary = {}
	for k: Vector2i in cells:
		c["%d,%d" % [k.x, k.y]] = cells[k]
	var cd: Dictionary = {}
	for k: Vector2i in cooldowns:
		cd["%d,%d" % [k.x, k.y]] = cooldowns[k]
	return {"cells": c, "cooldowns": cd}


func from_dict(d: Dictionary) -> void:
	cells.clear()
	cooldowns.clear()
	for k: Variant in (d.get("cells", {}) as Dictionary).keys():
		cells[_parse(str(k))] = float(d["cells"][k])
	for k: Variant in (d.get("cooldowns", {}) as Dictionary).keys():
		cooldowns[_parse(str(k))] = float(d["cooldowns"][k])


static func _parse(s: String) -> Vector2i:
	var p: PackedStringArray = s.split(",")
	return Vector2i(int(p[0]), int(p[1])) if p.size() == 2 else Vector2i.ZERO
