extends GutTest
## Town yards (player report 4): a yard grows grass, brush and trees right up to its house, and the
## house keeps its own ground clear at runtime. BuildingGenerator.plan_box predicts where a generated
## house stands on its lot without generating it (VegetationManager's footprints), and the footprint
## test hides what stands on the box, its margin and the walk in front.

const Generator := preload("res://src/poi/building_generator.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")


func test_plan_box_is_where_the_generated_house_stands() -> void:
	var lots: Array[Vector2i] = [Vector2i(20, 28), Vector2i(23, 32), Vector2i(26, 36), Vector2i(30, 40)]
	var total: int = 0
	var same: int = 0
	for t: TemplateDef in Content.all(&"building_template"):
		for i: int in 12:
			var lot: Vector2i = lots[i % lots.size()]
			if not Generator.fits(t, lot):
				continue
			var seed: int = Ids.hash64("yard_test:%s:%d" % [t.id, i])
			var box: Rect2i = Generator.plan_box(t, seed, lot)
			var pd: PoiDef = Generator.generate(t, seed, lot)
			if pd == null:
				continue
			total += 1
			assert_true(box.size.x > 0 and box.size.y > 0, "%s: a box for a lot it fits" % t.id)
			assert_true(Rect2i(Vector2i.ZERO, lot).encloses(box), "%s: the box lies on the lot" % t.id)
			var o: Array = pd.layout.get("origin", [0, 0])
			var plan: Array = (pd.layout.get("levels", [{}]) as Array)[0].get("plan", [])
			var w: int = 0
			for row: Variant in plan:
				w = maxi(w, str(row).length())
			if box == Rect2i(Vector2i(int(o[0]), int(o[1])), Vector2i(w, plan.size())):
				same += 1
	assert_gt(total, 20, "enough houses tried")
	# A house the validator sent to a retry stands elsewhere; that should be rare.
	assert_gt(float(same) / total, 0.9, "plan_box agrees with the house that stands (%d of %d)" % [same, total])


func test_footprints_hide_the_house_its_margin_and_the_walk() -> void:
	# A 10 x 8 house at (5, 6) on its lot, turned 90 degrees and moved to (100, 50).
	var xf := Transform2D(PI * 0.5, Vector2(100.0, 50.0))
	var fps: Array = [[xf.affine_inverse(), Rect2(5, 6, 10, 8), 0.0]]
	var inside: Vector2 = xf * Vector2(10.0, 10.0)
	assert_true(VegetationManager._in_footprint(fps, "ground", inside.x, inside.y), "grass under the house")
	var beside: Vector2 = xf * Vector2(15.0 + 1.0, 10.0)
	assert_true(VegetationManager._in_footprint(fps, "tree", beside.x, beside.y), "no tree a metre off its wall")
	assert_false(VegetationManager._in_footprint(fps, "ground", beside.x, beside.y), "grass a metre off its wall")
	var walk: Vector2 = xf * Vector2(10.0, 14.0 + 8.0)
	assert_true(VegetationManager._in_footprint(fps, "medium", walk.x, walk.y), "the walk to the street stays clear of brush")
	var side_yard: Vector2 = xf * Vector2(15.0 + 4.0, 10.0)
	assert_false(VegetationManager._in_footprint(fps, "tree", side_yard.x, side_yard.y), "a tree may grow in the side yard")
	assert_false(VegetationManager._in_footprint([], "tree", inside.x, inside.y), "no footprints, nothing hidden")
