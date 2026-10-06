extends GutTest
## Burnt forest and fen (ADR-0041): their content and data tables, the generator's fire scars and
## fens (deterministic, off towns, roads and the start, absent when their weights are 0), the fen's
## pools (wading depth, inside the fen and the region, clear of roads), the per-region splat palette
## that makes room for ash and peat, the composer's recipes, and the scatter's waders.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const TMP: String = "user://test_biomes_burn_fen"
const BURN: int = 4
const FEN: int = 5

var _g: RefCounted = null


func before_all() -> void:
	_g = Generator.generate(GenSettings.resolve(&"standard", {"burn": 0.8, "fen": 0.8}, 7))


func after_all() -> void:
	Worlds._remove(TMP)


func _centre(g: RefCounted, k: int) -> Vector2:
	var n: int = g.get(&"biome_cols")
	var st: float = g.get(&"biome_step")
	var half: float = int(g.get(&"size")) * 512.0
	return Vector2(-half + (k % n + 0.5) * st, -half + (k / n + 0.5) * st)


func _count(g: RefCounted, b: int) -> int:
	var c: int = 0
	for v: int in (g.get(&"biome_cells") as PackedByteArray):
		if v == b:
			c += 1
	return c


# --- Content ------------------------------------------------------------------------------------

func test_biomes_species_and_tables() -> void:
	assert_eq(Generator.BIOMES[BURN], "burnt_forest", "burnt forest is biome map value 4")
	assert_eq(Generator.BIOMES[FEN], "fen", "fen is biome map value 5")
	for b: String in ["burnt_forest", "fen"]:
		var bd: BiomeDef = Content.get_def(&"biome", StringName(b)) as BiomeDef
		assert_not_null(bd, "%s is a biome" % b)
		assert_false(bd.spawns.is_empty(), "%s has its own spawn table" % b)
	assert_gt((Content.get_def(&"biome", &"fen") as BiomeDef).spawn_density, (Content.get_def(&"biome", &"burnt_forest") as BiomeDef).spawn_density,
		"the Bloom pools in the fen: more of them there than in the open burn")
	for w: String in ["cattail", "bulrush", "drowned_snag"]:
		assert_gt((Content.get_def(&"species", StringName(w)) as SpeciesDef).wade_depth, 0.0, "%s wades" % w)
	assert_eq((Content.get_def(&"species", &"grey_fir") as SpeciesDef).wade_depth, 0.0, "everything else keeps to dry ground")
	var j := JSON.new()
	assert_eq(j.parse(FileAccess.get_file_as_string("res://data/materials/terrain_layers.json")), OK)
	var layers: Array = (j.data as Dictionary)["layers"]
	assert_true(layers.has("ash_char") and layers.has("peat"), "the new terrain layers are in the contract")
	assert_lte(layers.size(), 16, "the weather tables are mat4s: 16 layers at most")
	var sf: Dictionary = Content.config(&"weather").get("surfaces", {})
	for l: Variant in layers:
		assert_true((sf["puddle"] as Dictionary).has(l) and (sf["porosity"] as Dictionary).has(l), "%s has puddle and porosity" % l)
	assert_gt(float(sf["puddle"]["peat"]), float(sf["puddle"]["forest_floor"]), "peat holds water")
	assert_lt(float(sf["porosity"]["peat"]), float(sf["porosity"]["dirt"]), "peat is already near saturated")


# --- The generator --------------------------------------------------------------------------------

func test_both_biomes_appear_and_keep_off_towns_and_the_start() -> void:
	assert_gt(_count(_g, BURN), 40, "a fire scar")
	assert_gt(_count(_g, FEN), 20, "fens")
	var drop: Vector2 = (_g.get(&"drop") as Dictionary).get("pos", Vector2(1e9, 1e9))
	var cells: PackedByteArray = _g.get(&"biome_cells")
	for k: int in cells.size():
		if cells[k] != BURN and cells[k] != FEN:
			continue
		var p: Vector2 = _centre(_g, k)
		assert_gt(float(_g.call(&"_town_distance", p)), 0.0, "no %s inside a town's disc at %s" % [Generator.BIOMES[cells[k]], p])
		if cells[k] == BURN:
			assert_gt(drop.distance_to(p), 200.0, "no burn round the drop site")
			# The road network the fire met (tracks and drives to places come later and may cross a burn).
			assert_gt(float(_g.call(&"nearest_road", p, PackedStringArray(["highway", "county"]))[0]), 20.0, "fire stopped at the road (%s)" % p)


func test_weights_of_zero_give_neither() -> void:
	var g0: RefCounted = Generator.generate(GenSettings.resolve(&"standard", {"burn": 0.0, "fen": 0.0}, 7))
	assert_eq(_count(g0, BURN), 0, "no burns at burn 0")
	assert_eq(_count(g0, FEN), 0, "no fens at fen 0")
	for cell: Variant in (g0.call(&"region_ids") as Dictionary):
		var rj: Dictionary = g0.call(&"region_json", str(cell))
		assert_false(rj.has("palette"), "the default palette without the new biomes")
		for f: Variant in rj["features"]:
			assert_ne(str((f as Dictionary).get("type", "")), "lake", "no fen pools")


func test_deterministic() -> void:
	var again: RefCounted = Generator.generate(GenSettings.resolve(&"standard", {"burn": 0.8, "fen": 0.8}, 7))
	assert_eq(again.get(&"biome_cells"), _g.get(&"biome_cells"), "the same biome map")
	for cell: Variant in (_g.call(&"region_ids") as Dictionary):
		assert_eq(JSON.stringify(again.call(&"region_json", str(cell))), JSON.stringify(_g.call(&"region_json", str(cell))),
			"region %s the same" % cell)


func test_fen_pools_are_wadeable_and_placed_well() -> void:
	var total: int = 0
	var regions: Dictionary = _g.get(&"regions")
	for cell: String in regions:
		var inner: Rect2 = (regions[cell]["rect"] as Rect2).grow(-60.0)
		for f: Dictionary in _g.call(&"fen_pools", cell):
			total += 1
			assert_true(str(f["id"]).begins_with("fen_"), "a fen pool's id (WaterSystem tints it)")
			var el: Array = f["ellipse"]
			var c := Vector2(float(el[0]), float(el[1]))
			assert_true(inner.has_point(c), "%s keeps inside its region" % f["id"])
			assert_eq(str(_g.call(&"biome_at", c)), "fen", "%s lies in the fen" % f["id"])
			assert_gt(float(_g.call(&"nearest_road", c)[0]), float(el[2]) + 6.0, "%s keeps off the roads" % f["id"])
			# The bed: the edge drop plus the depth under the water (TerrainComposer._band_water).
			assert_lt(TerrainComposer.EDGE_DROP + float(f["depth"]), Player.SWIM_DEPTH - 0.1, "%s is waded, not swum" % f["id"])
	assert_gt(total, 3, "the fens have pools")


func test_palette_makes_room_for_ash_and_peat() -> void:
	var regions: Dictionary = _g.get(&"regions")
	var seen: int = 0
	for cell: String in regions:
		var pal: PackedStringArray = _g.call(&"region_palette", cell)
		if pal.is_empty():
			continue
		seen += 1
		assert_eq(pal.size(), 8, "eight splat channels")
		assert_true(pal.has("ash_char") or pal.has("peat"), "a new layer in %s" % cell)
		assert_false(pal.has("sand") and (pal.has("ash_char") or pal.has("peat")), "sand goes first")
		for i: int in 6:
			if TerrainComposer.DEFAULT_PALETTE[i] != "moss_ground":
				assert_eq(pal[i], TerrainComposer.DEFAULT_PALETTE[i], "the kept layers keep their channels")
	assert_gt(seen, 0, "some regions need the new layers")


func test_composer_paints_peat_and_lets_waders_into_the_pools() -> void:
	var dir: String = TMP.path_join(str(_g.get(&"world_id")))
	assert_eq(Worlds.write(_g, dir), OK)
	var fws: PackedStringArray = Worlds.register_frameworks(dir)
	assert_eq(fws, PackedStringArray())
	var world: WorldDef = WorldDef.load_from(dir)
	# The region with the most pools.
	var best: String = ""
	var most: int = 0
	var regions: Dictionary = _g.get(&"regions")
	for cell: String in regions:
		var k: int = (_g.call(&"fen_pools", cell) as Array).size()
		if k > most:
			most = k
			best = cell
	assert_ne(best, "", "a region with pools")
	var rid: String = str(world.cells[best])
	var rt: RegionTerrain = TerrainComposer.compose(world, rid, 4.0)
	assert_not_null(rt)
	assert_true(rt.biome_ids.has("fen"), "the fen is painted")
	assert_true(rt.palette.has("peat"), "with peat in the palette")
	var pool: Dictionary = (_g.call(&"fen_pools", best) as Array)[0]
	var el: Array = pool["ellipse"]
	var c := Vector2(float(el[0]), float(el[1]))
	assert_eq(rt.biome_at(c.x, c.y), "fen", "the pool is fen ground")
	assert_gt(rt.veg_at(c.x, c.y), 0.3, "waders may stand in the pool")
	var lake_found: bool = false
	for wb: Dictionary in rt.water:
		if str(wb["id"]) == str(pool["id"]):
			lake_found = true
			var ground: float = rt.height.sample(c.x, c.y)
			assert_between(float(wb["level"]) - ground, 0.3, 1.25, "a shallow pool, brim-full")
	assert_true(lake_found, "the pool is a water body")
	var w: PackedFloat32Array = rt.splat_at(c.x + float(el[2]) + 6.0, c.y)
	var peat: int = rt.palette.find("peat")
	assert_gt(w[peat], 0.05, "peat by the pool")
	for t: Dictionary in _g.get(&"towns"):
		Content.remove_runtime_def(&"framework", StringName(str(t["fw_id"])))


# --- The scatter ----------------------------------------------------------------------------------

func _fen_region() -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.spacing = 2.0
	rt.height = HeightField.create(Vector2.ZERO, 2.0, 65, 65, 10.0)
	rt.rect = Rect2(0, 0, 128, 128)
	rt.biome_ids = PackedStringArray(["fen"])
	var n: int = 65 * 65
	rt.biome.resize(n)
	rt.biome.fill(0)
	rt.vegmask.resize(n)
	rt.vegmask.fill(255)
	return rt


func _flat(_x: float, _z: float) -> float:
	return 10.0


func _flooded(_x: float, _z: float) -> float:
	return 10.3


func test_only_waders_stand_in_water() -> void:
	VegetationScatter.warm()
	var res: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), _fen_region(), 51, _flat, _flooded)
	var n: int = 0
	for layer: String in ["tree", "medium", "ground"]:
		for inst: VegetationScatter.Instance in res.get(layer, []):
			n += 1
			assert_gt((Content.get_def(&"species", inst.species) as SpeciesDef).wade_depth, 0.3, "%s stands in 30 cm of water" % inst.species)
	assert_gt(n, 5, "cattails, bulrush and drowned snags stand in the pools")
	var dry: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), _fen_region(), 51, _flat)
	assert_gt((dry["ground"] as Array).size(), n, "the dry fen grows more")
