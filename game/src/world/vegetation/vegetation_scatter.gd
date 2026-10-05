class_name VegetationScatter
extends RefCounted
## Deterministic vegetation placement for a 64 m chunk from biome densities, the vegetation mask,
## slope and water. Same seed + chunk + data = same instances in the same order, so instances are
## addressed by (chunk, index) and saves only store differences (felled trees, harvested plants).
##
## Layers: "tree" (large, collidable, choppable), "medium" (bushes, saplings, boulders, deadfall
## piles, fallen logs), "ground" (ferns, grass, flowers, mushrooms, moss, litter, herb carpets — dense,
## near only), "bloom" (the Bloom's fruiting bodies, only where its field is strong; ADR-0025).
##
## The medium and ground layers grow in patches: a low-frequency noise field scales the chance of
## placing anything (dense thickets and bare stretches instead of an even sprinkle), and each
## species reads the field at its own offset, so ferns, moss and litter dominate different
## patches. The tree layer stays uniform: its instance indices address felled trees in saves.
##
## The bloom layer comes last, so it never moves another layer's indices: its chance follows the
## Bloom's authored field (`bloom_fn`, deterministic per world) instead of a patch field.

const CHUNK: float = 64.0
## patch = how strongly the patch field scales placement (0 = uniform; 0.5 = x0.5 .. x1.5);
## patch_size = typical patch spacing in metres.
const LAYERS: Dictionary = {
	"tree": {"cell": 4.0, "kinds": ["tree"]},
	"medium": {"cell": 3.0, "kinds": ["bush", "rock", "deadfall"], "patch": 0.6, "patch_size": 36.0},
	"ground": {"cell": 1.25, "kinds": ["fern", "grass", "flower", "mushroom", "moss", "litter", "herb"], "patch": 0.5, "patch_size": 18.0},
	# field: the Bloom field (0..1) is raised to this power to scale the chance, so caps crowd the
	# heart of a zone and only straggle out along its edges; below `field_min` nothing fruits.
	# near_tree: the chance rises up to this many times around a trunk's foot (the mycelium feeds
	# on the roots), within `near_tree_m` metres.
	"bloom": {"cell": 2.0, "kinds": ["fungus"], "field": 1.6, "field_min": 0.12, "near_tree": 2.5, "near_tree_m": 2.6},
}
## Layer order: instance indices run through the layers in this order (saves address them).
const ORDER: Array[String] = ["tree", "medium", "ground", "bloom"]
const MAX_SLOPE: Dictionary = {"tree": 34.0, "bush": 38.0, "rock": 60.0, "deadfall": 30.0, "fern": 40.0, "grass": 30.0, "flower": 30.0,
	"mushroom": 35.0, "moss": 45.0, "litter": 32.0, "herb": 38.0, "fungus": 40.0}
## Kinds that lie on the ground follow its slope instead of standing upright.
const HUGS_GROUND: PackedStringArray = ["moss", "litter"]


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
## bloom_fn(x, z) -> 0..1 is the Bloom's authored field (TerrainManager.bloom_base_at); without it
## the bloom layer is empty.
static func scatter_chunk(chunk: Vector2i, rt: RegionTerrain, world_seed: int, height_fn: Callable, water_fn: Callable = Callable(), layer_count: int = 4, bloom_fn: Callable = Callable()) -> Dictionary:
	var out: Dictionary = {}
	var origin := Vector2(chunk.x * CHUNK, chunk.y * CHUNK)
	var biome_tables: Dictionary = _biome_tables()
	var index: int = 0
	for layer: String in ORDER.slice(0, layer_count):
		var spec: Dictionary = LAYERS[layer]
		var cell: float = spec["cell"]
		var kinds: Array = spec["kinds"]
		var by_field: bool = spec.has("field")
		var field_min: float = float(spec.get("field_min", 0.1))
		# Most chunks hold no Bloom at all: skip the layer's thousand cells there.
		if by_field and not (bloom_fn.is_valid() and _reaches(bloom_fn, origin, field_min * 0.75)):
			var none: Array[Instance] = []
			out[layer] = none
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.derive_seed(world_seed, "veg:%s:%d_%d" % [layer, chunk.x, chunk.y])
		var patchy: float = float(spec.get("patch", 0.0))
		var field: FastNoiseLite = _patch_field(world_seed, layer, float(spec.get("patch_size", 30.0))) if patchy > 0.0 else null
		# Trunks of this chunk on a 4 m grid, for layers that gather around them.
		var trunks: Dictionary = _trunk_grid(out.get("tree", []), 4.0) if spec.has("near_tree") else {}
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
				var bloom: float = 1.0
				if by_field:
					bloom = float(bloom_fn.call(x, z))
					if bloom < field_min:
						continue
				var veg: float = rt.veg_at(x, z)
				if veg <= 0.02:
					continue
				var biome: String = rt.biome_at(x, z)
				var table: Dictionary = (biome_tables.get(biome, {}) as Dictionary).get(layer, {})
				if table.is_empty():
					continue
				var total: float = float(table["_total"])
				var p_place: float = total * cell * cell / 100.0
				if field != null:
					p_place *= 1.0 - patchy + 2.0 * patchy * smoothstep(0.3, 0.7, _field01(field, x, z))
				if by_field:
					p_place *= pow(bloom, float(spec["field"]))
				if spec.has("near_tree"):
					# Never inside a trunk or its root flare.
					var near: Vector2 = _nearest_trunk(trunks, x, z, 4.0)
					if near.x < near.y * 1.6 + 0.1:
						continue
					p_place *= 1.0 + float(spec["near_tree"]) * (1.0 - smoothstep(near.y * 1.6 + 0.3, float(spec["near_tree_m"]), near.x))
				p_place = minf(1.0, p_place) * veg
				if roll > p_place:
					continue
				var sp_id: StringName = _pick_species(table, pick) if field == null else _pick_species_patchy(table, pick, field, x, z)
				var sp: SpeciesDef = Content.get_def(&"species", sp_id) as SpeciesDef
				if sp == null:
					continue
				var y: float = height_fn.call(x, z)
				var e: float = 0.7
				var grad := Vector2(height_fn.call(x + e, z) - height_fn.call(x - e, z), height_fn.call(x, z + e) - height_fn.call(x, z - e)) / (2.0 * e)
				var slope: float = rad_to_deg(atan(grad.length()))
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
				if HUGS_GROUND.has(sp.veg_kind):
					inst.tilt = ground_tilt(grad, inst.yaw)
				list.append(inst)
				index += 1
		out[layer] = list
	return out


## True if `fn` (a field, 0..1) reaches `level` anywhere on a 4 m grid over the chunk at `origin`.
## The Bloom field is smooth on that scale (2 m texels, metres-wide edge bands), so sampling a little
## below the fruiting threshold only drops chunks where nothing could fruit.
static func _reaches(fn: Callable, origin: Vector2, level: float) -> bool:
	var n: int = int(CHUNK / 4.0)
	for iz: int in n + 1:
		for ix: int in n + 1:
			if float(fn.call(origin.x + ix * 4.0, origin.y + iz * 4.0)) >= level:
				return true
	return false


## Trunk positions and radii of a tree list, bucketed on a `cell` m grid: {Vector2i: [Vector3(x, z, r)]}.
static func _trunk_grid(trees: Array, cell: float) -> Dictionary:
	var grid: Dictionary = {}
	for inst: Instance in trees:
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		var r: float = (sp.trunk_radius if sp != null else 0.3) * inst.scale
		var k := Vector2i(int(floor(inst.pos.x / cell)), int(floor(inst.pos.z / cell)))
		if not grid.has(k):
			grid[k] = []
		(grid[k] as Array).append(Vector3(inst.pos.x, inst.pos.z, r))
	return grid


## (distance to the nearest trunk's centre, its radius), or (INF, 0) with none within a cell.
static func _nearest_trunk(grid: Dictionary, x: float, z: float, cell: float) -> Vector2:
	var best := Vector2(INF, 0.0)
	var c := Vector2i(int(floor(x / cell)), int(floor(z / cell)))
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			for t: Vector3 in grid.get(Vector2i(c.x + dx, c.y + dz), []):
				var d: float = Vector2(t.x - x, t.y - z).length()
				if d < best.x:
					best = Vector2(d, t.z)
	return best


## Euler X/Z tilt (Basis.from_euler(Vector3(x, yaw, z)), YXZ order) that turns the model's up
## axis onto the terrain normal for a height gradient (dh/dx, dh/dz).
static func ground_tilt(grad: Vector2, yaw: float) -> Vector2:
	var n := Vector3(-grad.x, 1.0, -grad.y).normalized()
	var u: Vector3 = n.rotated(Vector3.UP, -yaw)
	return Vector2(atan2(u.z, u.y), -asin(clampf(u.x, -1.0, 1.0)))


static func _patch_field(world_seed: int, layer: String, size: float) -> FastNoiseLite:
	var f := FastNoiseLite.new()
	f.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	f.seed = Ids.derive_seed(world_seed, "veg_patch:" + layer) & 0x7fffffff
	f.frequency = 1.0 / size
	f.fractal_octaves = 2
	return f


## The patch field mapped to roughly 0..1.
static func _field01(f: FastNoiseLite, x: float, z: float) -> float:
	return clampf(f.get_noise_2d(x, z) * 0.8 + 0.5, 0.0, 1.0)


## Weighted pick where each species' weight swells or shrinks with the patch field read at that
## species' own offset (so different species dominate different patches).
static func _pick_species_patchy(table: Dictionary, r: float, field: FastNoiseLite, x: float, z: float) -> StringName:
	var order: Array = table["_order"]
	var offsets: Dictionary = table["_offset"]
	var weights: PackedFloat32Array = []
	var total: float = 0.0
	for k: Variant in order:
		var off: float = float(offsets[k])
		var w: float = float(table[k]) * (0.2 + 1.6 * _field01(field, x * 1.3 + off, z * 1.3 - off * 0.7))
		weights.append(w)
		total += w
	var acc: float = 0.0
	for i: int in order.size():
		acc += weights[i] / total
		if r <= acc:
			return StringName(str(order[i]))
	return StringName(str(order.back()))


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
				per_layer[layer] = {"_total": 0.0, "_order": [], "_offset": {}}
			var t: Dictionary = per_layer[layer]
			t[str(k)] = float(b.vegetation[k])
			t["_total"] = float(t["_total"]) + float(b.vegetation[k])
			(t["_order"] as Array).append(str(k))
			# Far apart in the patch field so species patches are unrelated.
			(t["_offset"] as Dictionary)[str(k)] = float(Ids.hash31(str(k)) % 4096) * 7.3
		_tables[String(b.id)] = per_layer
	return _tables


static func instance_id(chunk: Vector2i, index: int) -> StringName:
	return StringName("veg:%d_%d:%d" % [chunk.x, chunk.y, index])
