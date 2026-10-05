extends GutTest
## VegetationScatter: deterministic placement, patchy medium/ground layers, a uniform tree layer
## (its indices address felled trees in saves) and ground-hugging kinds tilted onto the slope.


## A flat 128 m conifer-forest region with full vegetation allowance.
func _region() -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.spacing = 2.0
	rt.height = HeightField.create(Vector2.ZERO, 2.0, 65, 65, 10.0)
	rt.rect = Rect2(0, 0, 128, 128)
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	var n: int = 65 * 65
	rt.biome.resize(n)
	rt.biome.fill(0)
	rt.vegmask.resize(n)
	rt.vegmask.fill(255)
	return rt


func _flat(_x: float, _z: float) -> float:
	return 10.0


func _layer_species(res: Dictionary, layer: String) -> Array:
	var out: Array = []
	for inst: VegetationScatter.Instance in res.get(layer, []):
		out.append([inst.index, String(inst.species), inst.pos])
	return out


func test_same_inputs_give_the_same_instances() -> void:
	VegetationScatter.warm()
	var rt := _region()
	var a: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), rt, 4471, _flat)
	var b: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), rt, 4471, _flat)
	for layer: String in ["tree", "medium", "ground"]:
		assert_eq(_layer_species(a, layer), _layer_species(b, layer), "%s layer is deterministic" % layer)
	assert_gt((a["ground"] as Array).size(), 400, "a conifer chunk has a dense floor")


func test_tree_layer_ignores_the_patch_field() -> void:
	# The patch field only exists for layers that declare "patch"; the tree layer's draws and
	# placement must not depend on it (saved stumps address trees by index).
	assert_false((VegetationScatter.LAYERS["tree"] as Dictionary).has("patch"))
	VegetationScatter.warm()
	var res: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), _region(), 4471, _flat, Callable(), 1)
	var trees: Array = res["tree"]
	assert_gt(trees.size(), 20)
	assert_eq((trees[0] as VegetationScatter.Instance).index, 0, "tree indices start the chunk")


func test_ground_cover_is_patchy() -> void:
	VegetationScatter.warm()
	var res: Dictionary = VegetationScatter.scatter_chunk(Vector2i(0, 0), _region(), 4471, _flat)
	# Count ground plants per 16 m block: patches make some blocks clearly denser than others.
	var counts: Dictionary = {}
	for inst: VegetationScatter.Instance in res["ground"]:
		var k := Vector2i(int(inst.pos.x / 16.0), int(inst.pos.z / 16.0))
		counts[k] = int(counts.get(k, 0)) + 1
	var lo: int = 1 << 30
	var hi: int = 0
	for k: Vector2i in counts:
		lo = mini(lo, counts[k])
		hi = maxi(hi, counts[k])
	assert_gt(hi, lo * 1.5, "dense and sparse patches (%d..%d per block)" % [lo, hi])


func test_ground_tilt_turns_up_onto_the_terrain_normal() -> void:
	for grad: Vector2 in [Vector2(0.5, 0.0), Vector2(0.0, -0.4), Vector2(0.3, 0.6)]:
		for yaw: float in [0.0, 1.3, PI * 0.5, 4.0]:
			var t: Vector2 = VegetationScatter.ground_tilt(grad, yaw)
			var up: Vector3 = Basis.from_euler(Vector3(t.x, yaw, t.y)) * Vector3.UP
			var n := Vector3(-grad.x, 1.0, -grad.y).normalized()
			assert_almost_eq(up.dot(n), 1.0, 1e-4, "grad %s yaw %.2f" % [grad, yaw])
