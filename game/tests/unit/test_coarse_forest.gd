extends GutTest
## The coarse far forest (TD-006): cluster impostors scattered over a 16 m region, a quad for every
## VegetationManager.COARSE_TREES trees the near scatter would place, deterministic per block.


## A flat 512 m conifer-forest region at the coarse spacing; `veg` is its vegetation allowance.
func _region(veg: int = 255) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.spacing = 16.0
	rt.height = HeightField.create(Vector2.ZERO, 16.0, 33, 33, 40.0)
	rt.rect = Rect2(0, 0, 512, 512)
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	var n: int = 33 * 33
	rt.biome.resize(n)
	rt.biome.fill(0)
	rt.vegmask.resize(n)
	rt.vegmask.fill(veg)
	return rt


func _dims() -> Array:
	var dims: Dictionary = {}
	var heights: Dictionary = {}
	for d: ContentDef in Content.all(&"species"):
		var sp := d as SpeciesDef
		if sp.veg_kind == "tree":
			dims[sp.id] = Vector2(6.4, 21.0)
			heights[sp.id] = sp.height_range
	return [dims, heights]


func _count(out: Dictionary) -> int:
	var n: int = 0
	for k: Variant in out:
		n += int(out[k][0])
		assert_eq((out[k][1] as PackedFloat32Array).size(), int(out[k][0]) * 12, "12 floats a quad")
	return n


func test_a_forest_block_is_deterministic_and_thinned() -> void:
	VegetationScatter.warm()
	var d: Array = _dims()
	var rt := _region()
	var block := Rect2(0, 0, 512, 512)
	var a: Dictionary = VegetationManager._coarse_block(rt, block, 4471, {}, null, d[0], d[1])
	var b: Dictionary = VegetationManager._coarse_block(rt, block, 4471, {}, null, d[0], d[1])
	assert_eq(a, b, "same seed and block, same clusters")
	# The near scatter's tree count over the block, divided by the trees a cluster stands for.
	var table: Dictionary = VegetationScatter._biome_tables()["conifer_forest"]["tree"]
	var per_cell: float = minf(1.0, float(table["_total"]) * 16.0 / 100.0)
	var expected: float = per_cell * (512.0 * 512.0 / 16.0) / VegetationManager.COARSE_TREES
	var n: int = _count(a)
	assert_between(float(n), expected * 0.85, expected * 1.15, "about one quad per %s trees (%d of %.0f)" % [VegetationManager.COARSE_TREES, n, expected])
	assert_true(a.has(&"grey_fir"), "the biome's main tree is there")


func test_no_clusters_where_the_mask_is_bare() -> void:
	VegetationScatter.warm()
	var d: Array = _dims()
	var out: Dictionary = VegetationManager._coarse_block(_region(0), Rect2(0, 0, 512, 512), 4471, {}, null, d[0], d[1])
	assert_eq(_count(out), 0)


func test_clusters_stand_on_the_ground_and_scale_up() -> void:
	VegetationScatter.warm()
	var d: Array = _dims()
	var out: Dictionary = VegetationManager._coarse_block(_region(), Rect2(0, 0, 256, 256), 7, {}, null, d[0], d[1])
	var buf: PackedFloat32Array = out[&"grey_fir"][1]
	assert_almost_eq(buf[7], 40.0 - 0.6, 0.01, "sunk a little into the 16 m ground")
	var width: float = Vector3(buf[0], buf[4], buf[8]).length()
	var height: float = Vector3(buf[1], buf[5], buf[9]).length()
	assert_gt(width / height, 6.4 / 21.0 * 1.2, "wider than a single tree's frame")
