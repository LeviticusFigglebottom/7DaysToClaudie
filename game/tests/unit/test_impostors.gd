extends GutTest
## Far-tree impostors (TD-005): a species' atlas has a row per model variant and a frame as wide as
## its crown; each far tree carries its own variant in the MultiMesh custom data, so it shows the
## tree it becomes up close; a deciduous species' bare-branch atlas follows the winter.


func test_frame_width_follows_the_crown() -> void:
	assert_eq(ImpostorLibrary.frame_width(10.0, 20.0), 128, "a 1:2 crown keeps the old frame")
	assert_eq(ImpostorLibrary.frame_width(16.0, 18.0), 240, "a broad crown gets the texels its width needs")
	assert_eq(ImpostorLibrary.frame_width(30.0, 18.0), ImpostorLibrary.FRAME_W_MAX, "never past square")
	assert_eq(ImpostorLibrary.frame_width(1.0, 30.0), ImpostorLibrary.FRAME_W_MIN, "a bare snag keeps a usable frame")
	assert_eq(ImpostorLibrary.frame_width(7.3, 20.0) % 16, 0, "in steps of 16 pixels")


func test_far_trees_carry_their_variant() -> void:
	var a := VegetationScatter.Instance.new()
	a.species = &"grey_fir"
	a.variant = 2
	a.pos = Vector3(4, 1, 7)
	a.scale = 1.0
	var b := VegetationScatter.Instance.new()
	b.species = &"grey_fir"
	b.variant = 0
	b.pos = Vector3(9, 2, 3)
	b.scale = 1.1
	var out: Dictionary = VegetationManager._far_buffers([a, b], {&"grey_fir": Vector2(6.4, 21.0)})
	var buf: PackedFloat32Array = out[&"grey_fir"][1]
	assert_eq(int(out[&"grey_fir"][0]), 2)
	assert_eq(buf.size(), 32, "16 floats a tree: the transform, then its custom data")
	assert_eq(buf[12], 2.0, "the first tree's variant row")
	assert_eq(buf[28], 0.0, "the second tree's")
	assert_eq(buf[3], 4.0, "the transform is untouched (origin x)")


func test_material_knows_the_rows_and_the_winter() -> void:
	var vm := VegetationManager.new()
	var fir: SpeciesDef = Content.get_def(&"species", &"grey_fir") as SpeciesDef
	var mat: ShaderMaterial = vm._impostor_mat(fir)
	assert_eq(int(mat.get_shader_parameter("variants")), ImpostorLibrary.variants_for(fir))
	assert_false(bool(mat.get_shader_parameter("has_winter")), "an evergreen has no bare-branch atlas")
	var mm: MultiMesh = vm._impostor_mmi("t", mat, [0, PackedFloat32Array()]).multimesh
	assert_true(mm.use_custom_data, "far trees carry their variant")
	vm.free()
	# A baked atlas (when the assets are generated) has a row for every variant it found.
	if ImpostorLibrary.is_baked(fir):
		var tex: Texture2D = ImpostorLibrary.atlas_for(fir)
		var rows: int = ImpostorLibrary.variants_for(fir)
		assert_eq(tex.get_height(), ImpostorLibrary.FRAME_H * rows, "a row per variant")
		assert_lte(rows, fir.models.size())
