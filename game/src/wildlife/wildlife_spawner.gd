class_name WildlifeSpawner
extends RefCounted
## Where the valley's animals are (ADR-0027): a pure, deterministic plan per 128 m cell, day and
## time of day. The same world seed puts the same herd in the same meadow at the same dawn on
## every machine; WildlifeManager spawns the plans that fall in the ring round the player and
## forgets those that leave it. Nothing here is saved: a herd you walk away from is re-rolled
## the same when you come back (minus the ones you took, which the manager remembers).
##
## A plan: {id, def (StringName), pos (Vector2, XZ), count, seed}. `sample(pos: Vector2)` is the
## world: it returns {biome: String ("" = not land), edge: bool (another biome within ~40 m),
## ok: bool (dry, not a building, not a cliff)}.

const CELL: float = 128.0
## dawn and dusk last this long either side of sunrise and sunset (hours)
const TWILIGHT: float = 1.5


static func period_of(hour: float, sunrise: float, sunset: float) -> String:
	if absf(hour - sunrise) <= TWILIGHT:
		return "dawn"
	if absf(hour - sunset) <= TWILIGHT:
		return "dusk"
	if hour > sunrise and hour < sunset:
		return "day"
	return "night"


static func cell_of(pos: Vector2) -> Vector2i:
	return Vector2i(floori(pos.x / CELL), floori(pos.y / CELL))


## The plans for one cell. `density_mult` is the world setting (wildlife_density).
static func plan_cell(world_seed: int, cell: Vector2i, day: int, period: String, defs: Array, sample: Callable,
		density_mult: float = 1.0) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var area_km2: float = CELL * CELL / 1.0e6
	for d: WildlifeDef in defs:
		var act: float = float(d.activity.get(period, 1.0))
		if act <= 0.0:
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("wildlife:%d:%s:%d:%d:%d:%s" % [world_seed, d.id, cell.x, cell.y, day, period])
		# Expected groups in this cell; up to two tries (a dense biome can hold two bands).
		var expect: float = d.density * area_km2 * act * density_mult
		for k: int in 2:
			var roll: float = rng.randf()
			var px: float = (float(cell.x) + rng.randf()) * CELL
			var pz: float = (float(cell.y) + rng.randf()) * CELL
			var count: int = rng.randi_range(d.group.x, d.group.y)
			var pseed: int = int(rng.randi())
			var pos := Vector2(px, pz)
			var s: Dictionary = sample.call(pos)
			if not bool(s.get("ok", false)):
				continue
			var w: float = float(d.biomes.get(str(s.get("biome", "")), 0.0))
			if w <= 0.0:
				continue
			if bool(s.get("edge", false)):
				w *= d.edge
			if roll >= expect * w - float(k):
				continue
			out.append({"id": StringName("w:%s:%d:%d:%d:%s:%d" % [d.id, cell.x, cell.y, day, period, k]), "def": d.id,
				"pos": pos, "count": count, "seed": pseed})
	return out


## Every plan in the cells overlapping a circle round `center`.
static func plans_near(world_seed: int, center: Vector2, radius: float, day: int, period: String, defs: Array,
		sample: Callable, density_mult: float = 1.0) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var c0: Vector2i = cell_of(center - Vector2(radius, radius))
	var c1: Vector2i = cell_of(center + Vector2(radius, radius))
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			for p: Dictionary in plan_cell(world_seed, Vector2i(cx, cz), day, period, defs, sample, density_mult):
				if (p["pos"] as Vector2).distance_to(center) <= radius:
					out.append(p)
	return out
