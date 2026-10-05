extends GutTest
## The Bloom field (ADR-0025): deterministic, shaped by authored zones with ragged edges, masked
## by the ground, queryable on the CPU exactly as the shaders sample it, and feeding the fungus
## scatter without moving any other vegetation index.

const COVER := Rect2(-256, -256, 512, 512)


func _zone(id: String, at: Vector2, radius: float, strength: float, edge: float = 0.6, seed: int = 77) -> BloomField.Zone:
	var z := BloomField.Zone.new()
	z.id = id
	z.points = PackedVector2Array([at])
	z.radius = radius
	z.strength = strength
	z.edge = edge
	z.seed = seed
	return z


func _field(zones: Array[BloomField.Zone]) -> BloomField:
	return BloomField.from_zones(zones, COVER, Content.config(&"bloom"))


func test_same_zones_give_the_same_field() -> void:
	var a: BloomField = _field([_zone("a", Vector2.ZERO, 60.0, 0.9)] as Array[BloomField.Zone])
	var b: BloomField = _field([_zone("a", Vector2.ZERO, 60.0, 0.9)] as Array[BloomField.Zone])
	assert_eq(a.base, b.base, "deterministic")
	var c: BloomField = _field([_zone("a", Vector2.ZERO, 60.0, 0.9, 0.6, 78)] as Array[BloomField.Zone])
	assert_ne(a.base, c.base, "another seed grows another shape")


func test_a_zone_holds_its_core_and_leaves_the_rest_clean() -> void:
	var f: BloomField = _field([_zone("a", Vector2(20, -10), 50.0, 0.8)] as Array[BloomField.Zone])
	assert_gt(f.at(20, -10), 0.45, "the core is colonised")
	assert_lt(f.at(20, -10), 0.81, "never past the zone's strength")
	assert_eq(f.at(-230, 230), 0.0, "far away is clean")
	assert_eq(f.at(5000, 0), 0.0, "off the grid is clean")
	var weak: BloomField = _field([_zone("a", Vector2(20, -10), 50.0, 0.3)] as Array[BloomField.Zone])
	assert_lt(weak.at(20, -10), f.at(20, -10), "strength scales it")


func test_the_edge_is_ragged_not_a_circle() -> void:
	var f: BloomField = _field([_zone("a", Vector2.ZERO, 70.0, 1.0, 0.8)] as Array[BloomField.Zone])
	# How far the colonised ground (> 0.3) reaches along 72 headings: a circle would be one number.
	var reach := PackedFloat32Array()
	for k: int in 72:
		var d := Vector2(cos(TAU * k / 72.0), sin(TAU * k / 72.0))
		var r: float = 0.0
		for step: int in 120:
			var p: Vector2 = d * (step * 2.0)
			if f.at(p.x, p.y) > 0.3:
				r = step * 2.0
		reach.append(r)
	var lo: float = INF
	var hi: float = 0.0
	for r: float in reach:
		lo = minf(lo, r)
		hi = maxf(hi, r)
	assert_gt(hi - lo, 35.0, "lobes and tongues: reach varies by more than half a radius (%.0f..%.0f m)" % [lo, hi])
	assert_gt(hi, 75.0, "tongues push out past the radius")


func test_the_cpu_query_reads_the_texels_bilinearly() -> void:
	var f: BloomField = _field([_zone("a", Vector2.ZERO, 60.0, 1.0)] as Array[BloomField.Zone])
	var i: int = f.width / 2
	var j: int = f.depth / 2
	var cx: float = f.rect.position.x + (i + 0.5) * f.texel
	var cz: float = f.rect.position.y + (j + 0.5) * f.texel
	assert_almost_eq(f.at(cx, cz), f.data[j * f.width + i] / 255.0, 1e-5, "a texel centre reads its texel")
	var mid: float = f.at(cx + f.texel * 0.5, cz)
	var expect: float = (f.data[j * f.width + i] + f.data[j * f.width + i + 1]) / 510.0
	assert_almost_eq(mid, expect, 1e-4, "half way between two texels reads their mean")
	var sr: Vector4 = f.shader_rect()
	assert_almost_eq(sr.z, 1.0 / (f.width * f.texel), 1e-9, "the shaders map the same extent")
	assert_eq(f.image().get_width(), f.width)
	assert_eq(BloomField.new().shader_rect(), Vector4.ZERO, "no field: the shaders switch the Bloom off")


func test_a_seep_runs_along_its_line() -> void:
	var z := BloomField.Zone.new()
	z.id = "seep"
	z.points = PackedVector2Array([Vector2(-150, 0), Vector2(0, 20), Vector2(150, 0)])
	z.radius = 14.0
	z.strength = 0.8
	z.edge = 0.4
	z.seed = 5
	var f: BloomField = _field([z] as Array[BloomField.Zone])
	var along: float = 0.0
	for x: int in range(-120, 121, 20):
		along += f.at(x, 20.0 * (1.0 - absf(x) / 150.0))
	assert_gt(along / 13.0, 0.35, "colonised along the whole line")
	assert_eq(f.at(0, 120), 0.0, "and not far to its side")


func test_region_features_and_poi_defaults() -> void:
	var rt := RegionTerrain.new()
	rt.region_id = "t"
	rt.placements = [
		{"kind": "poi", "def": "tamsin_clinic", "id": "clinic_a", "origin": [100.0, 0.0, 0.0], "rotation": 0.0, "size": [28, 26]},
		{"kind": "poi", "def": "tamsin_clinic", "id": "clinic_b", "origin": [-100.0, 0.0, 0.0], "rotation": 90.0, "size": [28, 26]},
		{"kind": "poi", "def": "merrow_house", "id": "house", "origin": [0.0, 0.0, 100.0], "rotation": 0.0, "size": [16, 18]},
	]
	var region: Dictionary = {"id": "t", "features": [
		{"type": "bloom", "id": "patch", "at": [10, 20], "radius": 30, "strength": 0.9},
		{"type": "bloom", "id": "seep", "points": [[0, 0], [40, 10]], "radius": 8},
		{"type": "bloom", "id": "anchored", "poi": "clinic_b", "offset": [0, -30], "radius": 12, "strength": 0.5},
		{"type": "road", "id": "r", "points": [[0, 0], [1, 1]]},
	]}
	var cfg: Dictionary = Content.config(&"bloom")
	var zones: Array[BloomField.Zone] = BloomField.region_zones(region, rt, cfg, 4471)
	var ids: PackedStringArray = []
	for z: BloomField.Zone in zones:
		ids.append(z.id)
	assert_eq(ids, PackedStringArray(["patch", "seep", "anchored", "t:poi:clinic_a"]),
		"features in order, then the clinic default only where no feature anchors to it")
	assert_eq(zones[0].points[0], Vector2(10, 20))
	assert_eq(zones[1].points.size(), 2, "a seep keeps its line")
	# clinic_b: origin (-100, 0), turned 90 degrees: footprint centre (14, 13) -> (-113, 14); the
	# offset (0, -30) toward its back -> (+30, 0) in the world.
	assert_almost_eq(zones[2].points[0].x, -83.0, 1e-3)
	assert_almost_eq(zones[2].points[0].y, 14.0, 1e-3)
	var d: Dictionary = (cfg.get("poi_defaults", {}) as Dictionary).get("tamsin_clinic", {})
	assert_almost_eq(zones[3].radius, float(d.get("radius", 0.0)), 1e-6, "the default's shape comes from data")
	assert_ne(zones[0].seed, zones[1].seed, "each zone has its own noise")


func test_the_ground_masks_the_field() -> void:
	var rt := RegionTerrain.new()
	rt.region_id = "t"
	rt.rect = COVER
	rt.spacing = 4.0
	var n: int = 129
	rt.height = HeightField.create(COVER.position, 4.0, n, n, 0.0)
	rt.vegmask.resize(n * n)
	rt.vegmask.fill(255)
	# A road along x = 0 (8 m wide): nothing grows there.
	for j: int in n:
		for i: int in range(62, 67):
			rt.vegmask[j * n + i] = 0
	var f: BloomField = _field([_zone("a", Vector2.ZERO, 80.0, 1.0)] as Array[BloomField.Zone])
	var before: float = f.at(1.0, 5.0)
	f.mask_ground({"t": rt})
	assert_gt(before, 0.4)
	assert_eq(f.at(1.0, 5.0), 0.0, "nothing on the road")
	assert_gt(f.at(30.0, 5.0), 0.3, "the wood beside it keeps it")


func test_spots_add_on_top_and_leave_the_authored_field() -> void:
	var f: BloomField = _field([_zone("a", Vector2(-150, -150), 30.0, 0.8)] as Array[BloomField.Zone])
	assert_eq(f.at(100, 100), 0.0)
	var dirty: Rect2i = f.set_spots([{"pos": Vector2(100, 100), "radius": 3.0, "strength": 0.9}])
	assert_ne(dirty.size, Vector2i.ZERO, "the texels around the spot changed")
	assert_gt(f.at(100, 100), 0.6, "a mound takes the ground around it")
	assert_eq(f.base_at(100, 100), 0.0, "the authored field (scatter) is untouched")
	f.set_spots([])
	assert_eq(f.at(100, 100), 0.0, "gone with the mound")


func test_the_glow_belongs_to_the_night() -> void:
	assert_eq(BloomWorld.night_level(30.0), 0.0, "never by day")
	assert_eq(BloomWorld.night_level(-25.0), 1.0, "full in the dark")
	assert_between(BloomWorld.night_level(-3.0), 0.05, 0.95, "fades in through dusk")


func test_larch_hollow_keeps_the_drop_site_clean() -> void:
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	var region: Dictionary = world.region_data("d6_larch_hollow")
	var zones: Array[BloomField.Zone] = BloomField.region_zones(region, null, Content.config(&"bloom"), world.seed)
	assert_gte(zones.size(), 4, "the authored zones (mill pond, deep wood, seep...)")
	var f: BloomField = BloomField.from_zones(zones, world.region_rect("d6_larch_hollow"), Content.config(&"bloom"))
	var drop := Vector2.ZERO
	for fv: Variant in region.get("features", []):
		if fv is Dictionary and str((fv as Dictionary).get("id", "")) == "drop_site":
			drop = Vector2(float(fv["pos"][0]), float(fv["pos"][1]))
	assert_ne(drop, Vector2.ZERO, "the region has a drop site")
	var worst: float = 0.0
	for k: int in 32:
		for r: float in [0.0, 50.0, 100.0, 150.0]:
			var p: Vector2 = drop + Vector2(cos(TAU * k / 32.0), sin(TAU * k / 32.0)) * r
			worst = maxf(worst, f.at(p.x, p.y))
	assert_eq(worst, 0.0, "the start area is clean for 150 m")
	for z: BloomField.Zone in zones:
		assert_gt(f.at(z.points[0].x, z.points[0].y), 0.2, "%s holds its core" % z.id)
	# Danger rises north and east: the strongest zone lies north-east of the start.
	var strongest: BloomField.Zone = zones[0]
	for z: BloomField.Zone in zones:
		if z.strength > strongest.strength:
			strongest = z
	assert_gt(strongest.points[0].x, drop.x, "east of the drop site")
	assert_lt(strongest.points[0].y, drop.y, "north of it")


func test_the_scatter_fruits_only_where_the_bloom_is() -> void:
	VegetationScatter.warm()
	var rt := RegionTerrain.new()
	rt.spacing = 2.0
	rt.height = HeightField.create(Vector2.ZERO, 2.0, 65, 65, 10.0)
	rt.rect = Rect2(0, 0, 128, 128)
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	rt.biome.resize(65 * 65)
	rt.biome.fill(0)
	rt.vegmask.resize(65 * 65)
	rt.vegmask.fill(255)
	var flat := func(_x: float, _z: float) -> float: return 10.0
	# Colonised on the west half of the chunk only.
	var west := func(x: float, _z: float) -> float: return 1.0 if x < 32.0 else 0.0
	var plain: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), rt, 4471, flat)
	var bloom: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), rt, 4471, flat, Callable(), 4, west)
	for layer: String in ["tree", "medium", "ground"]:
		var a: Array = (plain[layer] as Array).map(func(i: VegetationScatter.Instance) -> Array: return [i.index, i.species])
		var b: Array = (bloom[layer] as Array).map(func(i: VegetationScatter.Instance) -> Array: return [i.index, i.species])
		assert_eq(a, b, "%s layer indices don't move" % layer)
	assert_eq((plain["bloom"] as Array).size(), 0, "no field, no fruit")
	var bare := func(_x: float, _z: float) -> float: return 0.0
	var clean: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), rt, 4471, flat, Callable(), 4, bare)
	assert_eq((clean["bloom"] as Array).size(), 0, "a chunk the Bloom never reaches skips the layer")
	var caps: Array = bloom["bloom"]
	assert_gt(caps.size(), 20, "the colonised half fruits")
	for inst: VegetationScatter.Instance in caps:
		assert_lt(inst.pos.x, 32.0, "only where the field is")
		assert_eq((Content.get_def(&"species", inst.species) as SpeciesDef).veg_kind, "fungus")
	var last_ground: int = ((bloom["ground"] as Array).back() as VegetationScatter.Instance).index
	assert_gt((caps[0] as VegetationScatter.Instance).index, last_ground, "bloom indices come after every other layer's")
