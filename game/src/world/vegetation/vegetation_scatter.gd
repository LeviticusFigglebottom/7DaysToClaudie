class_name VegetationScatter
extends RefCounted
## Deterministic vegetation placement for a 64 m chunk from biome densities, the vegetation mask,
## slope and water. Same seed + chunk + data = same instances in the same order, so instances are
## addressed by (chunk, index) and saves only store differences (felled trees, harvested plants).
##
## Layers: "tree" (large, collidable, choppable), "medium" (bushes, saplings, boulders, deadfall
## piles, fallen logs), "ground" (ferns, grass, flowers, pebbles, mushrooms — dense, near only).

const CHUNK: float = 64.0
const LAYERS: Dictionary = {
	"tree": {"cell": 4.0, "kinds": ["tree"]},
	"medium": {"cell": 3.0, "kinds": ["bush", "rock", "deadfall"]},
	"ground": {"cell": 1.25, "kinds": ["fern", "grass", "flower", "mushroom"]},
}
const MAX_SLOPE: Dictionary = {"tree": 34.0, "bush": 38.0, "rock": 60.0, "deadfall": 30.0, "fern": 40.0, "grass": 30.0, "flower": 30.0, "mushroom": 35.0}


class Instance:
	var index: int
	var species: StringName
	var variant: int
	var pos: Vector3
	var yaw: float
	var scale: float
	var tilt: Vector2


## Returns {layer_name: Array[Instance]} for the chunk. height_fn(x, z) -> float.
## `layer_count` limits the work to the first N layers (1 = trees only, for far impostors); the
## layer order is fixed so instance indices are identical whichever count is requested.
static func scatter_chunk(chunk: Vector2i, rt: RegionTerrain, world_seed: int, height_fn: Callable, water_fn: Callable = Callable(), layer_count: int = 3) -> Dictionary:
	var out: Dictionary = {}
	var origin := Vector2(chunk.x * CHUNK, chunk.y * CHUNK)
	var biome_tables: Dictionary = _biome_tables()
	var index: int = 0
	for layer: String in (["tree", "medium", "ground"] as Array[String]).slice(0, layer_count):
		var spec: Dictionary = LAYERS[layer]
		var cell: float = spec["cell"]
		var kinds: Array = spec["kinds"]
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.derive_seed(world_seed, "veg:%s:%d_%d" % [layer, chunk.x, chunk.y])
		var list: Array[Instance] = []
		var steps: int = int(CHUNK / cell)
		for gz: int in steps:
			for gx: int in steps:
				# Always draw the same number of randoms per cell (stable sequences).
				var jx: float = rng.randf()
				var jz: float = rng.randf()
				var roll: float = rng.randf()
				var pick: float = rng.randf()
				var r_yaw: float = rng.randf()
				var r_scale: float = rng.randf()
				var r_var: int = rng.randi()
				var r_tilt: float = rng.randf()
				var x: float = origin.x + (gx + jx) * cell
				var z: float = origin.y + (gz + jz) * cell
				if not rt.rect.has_point(Vector2(x, z)):
					continue
				var veg: float = rt.veg_at(x, z)
				if veg <= 0.02:
					continue
				var biome: String = rt.biome_at(x, z)
				var table: Dictionary = (biome_tables.get(biome, {}) as Dictionary).get(layer, {})
				if table.is_empty():
					continue
				var total: float = float(table["_total"])
				var p_place: float = minf(1.0, total * cell * cell / 100.0) * veg
				if roll > p_place:
					continue
				var sp_id: StringName = _pick_species(table, pick)
				var sp: SpeciesDef = Content.get_def(&"species", sp_id) as SpeciesDef
				if sp == null:
					continue
				var y: float = height_fn.call(x, z)
				var e: float = 0.7
				var slope: float = rad_to_deg(atan(Vector2(height_fn.call(x + e, z) - height_fn.call(x - e, z), height_fn.call(x, z + e) - height_fn.call(x, z - e)).length() / (2.0 * e)))
				if slope > float(MAX_SLOPE.get(sp.veg_kind, 35.0)):
					continue
				if water_fn.is_valid() and float(water_fn.call(x, z)) > y - 0.15:
					continue
				var inst := Instance.new()
				inst.index = index
				inst.species = sp_id
				inst.variant = r_var % maxi(1, sp.models.size())
				# Trees sink a little so root flares meet sloped ground.
				inst.pos = Vector3(x, y - (0.15 if sp.veg_kind == "tree" else 0.03), z)
				inst.yaw = r_yaw * TAU
				var base_h: float = 20.0 if sp.veg_kind == "tree" else 1.0
				inst.scale = lerpf(sp.height_range.x, sp.height_range.y, r_scale) / base_h if sp.veg_kind == "tree" else lerpf(0.8, 1.25, r_scale)
				inst.tilt = Vector2(r_tilt - 0.5, fposmod(r_tilt * 7.13, 1.0) - 0.5) * (0.06 if sp.veg_kind == "tree" else 0.2)
				list.append(inst)
				index += 1
		out[layer] = list
	return out


static func _pick_species(table: Dictionary, r: float) -> StringName:
	var acc: float = 0.0
	var total: float = float(table["_total"])
	for k: Variant in table["_order"]:
		acc += float(table[k]) / total
		if r <= acc:
			return StringName(str(k))
	return StringName(str((table["_order"] as Array).back()))


static var _tables: Dictionary = {}


## Builds the shared species tables (call on the main thread before scattering on workers).
static func warm() -> void:
	_biome_tables()


## biome id -> layer -> {species: density, "_total", "_order"} (cached).
static func _biome_tables() -> Dictionary:
	if not _tables.is_empty():
		return _tables
	for b: BiomeDef in Content.all(&"biome"):
		var per_layer: Dictionary = {}
		var keys: Array = b.vegetation.keys()
		keys.sort()
		for k: Variant in keys:
			var sp: SpeciesDef = Content.get_def(&"species", StringName(str(k))) as SpeciesDef
			if sp == null:
				continue
			var layer: String = "ground"
			for ln: String in LAYERS:
				if (LAYERS[ln]["kinds"] as Array).has(sp.veg_kind):
					layer = ln
			if not per_layer.has(layer):
				per_layer[layer] = {"_total": 0.0, "_order": []}
			var t: Dictionary = per_layer[layer]
			t[str(k)] = float(b.vegetation[k])
			t["_total"] = float(t["_total"]) + float(b.vegetation[k])
			(t["_order"] as Array).append(str(k))
		_tables[String(b.id)] = per_layer
	return _tables


static func instance_id(chunk: Vector2i, index: int) -> StringName:
	return StringName("veg:%d_%d:%d" % [chunk.x, chunk.y, index])
