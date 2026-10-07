extends GutTest
## PoiBuilder in steps (ADR-0038 §8, TD-107): a building raised in many small steps is the same
## building as one built at once. The phased builds use a 1 µs budget, so every resumable phase
## (walls, posts, floors, exterior, roof, props, scatter, probes, decals, batches) yields after
## each item, once with PoiManager's worker prework (prepare_check: barricade faces, roof plan,
## probe boxes, clutter, run decals) and once without. Each building is dressed per run, as the
## game dresses it. Compared: the root's children by class in order, node counts by class
## (collision shapes and probes among them), the batches with their instance counts, every
## collision shape (kind, size, place) and where both random streams ended. Headless MultiMesh
## instance transforms read back as identity, so batches are compared by name and count.
## Covers Merrow House, the sawmill, the campground, two buildings with cellars (the gas garage,
## the Okafor farmhouse), the Corvane field lab (buried levels, many roof stages) and a generated
## house; prints the step counts.

const Generator := preload("res://src/poi/building_generator.gd")
const Dressing := preload("res://src/poi/poi_dressing.gd")


func _defs() -> Array[PoiDef]:
	var out: Array[PoiDef] = []
	for id: StringName in [&"merrow_house", &"larch_hollow_sawmill", &"tamsin_campground", &"cordon_gas_garage",
			&"okafor_farmhouse", &"corvane_field_lab"]:
		var pd: PoiDef = Content.get_def(&"poi", id) as PoiDef
		assert_not_null(pd, "%s is content" % id)
		if pd != null:
			out.append(pd)
	for t: Variant in Content.all(&"building_template"):
		var g: PoiDef = Generator.generate(t, 4242)
		if g != null:
			out.append(g)
			break
	return out


func test_a_building_built_in_many_steps_is_the_same_building() -> void:
	var defs: Array[PoiDef] = _defs()
	assert_eq(defs.size(), 7, "content present")
	for raw: PoiDef in defs:
		# Dressed per run as the game dresses it (run decals, per-run scatter and wall damage).
		var ds: int = Dressing.dressing_seed(7, StringName("test/%s" % raw.id), Dressing.MODE_PER_RUN)
		var pd: PoiDef = Dressing.resolve(raw, Dressing.roll(raw, ds), {"mode": Dressing.MODE_PER_RUN, "seed": ds})
		var iid := StringName("test/%s" % pd.id)
		var whole: PoiBuilder = PoiBuilder.start(PoiLayout.compile(pd), iid)
		var whole_steps: int = 1
		while not whole.step():
			whole_steps += 1
		assert_eq(whole_steps, PoiBuilder.PHASES.size(), "%s: no budget, one phase a step" % pd.id)
		add_child_autofree(whole.root)
		var want: Dictionary = _signature(whole)
		for prepared: bool in [true, false]:
			var layout := PoiLayout.compile(pd)
			var v: PoiValidator = null
			if prepared:
				v = PoiValidator.new()
				v.layout = layout
				v._run()
				PoiBuilder.prepare_check(v)
			var b: PoiBuilder = PoiBuilder.start(layout, iid, v)
			var steps: int = 1
			while not b.step(0.001):
				steps += 1
			add_child_autofree(b.root)
			var what: String = "%s (%s)" % [pd.id, "prepared" if prepared else "unprepared"]
			gut.p("%s: %d steps at a 1 µs budget" % [what, steps])
			assert_gt(steps, PoiBuilder.PHASES.size() + 10, "%s: the phases yielded" % what)
			var got: Dictionary = _signature(b)
			for k: String in want:
				assert_eq(got[k], want[k], "%s: same %s" % [what, k])


## Everything compared between two builds of one building.
func _signature(b: PoiBuilder) -> Dictionary:
	var order: PackedStringArray = []
	for n: Node in b.root.get_children():
		order.append(n.get_class())
	return {"children in order": order, "node counts": _census(b.root), "batches": _batches(b.root),
		"collision shapes": _shapes(b.root), "rng state": [b._rng.state, b._rng2.state]}


## Node counts by class (CollisionShape3D and ReflectionProbe among them), and the total.
func _census(root: Node) -> Dictionary:
	var out: Dictionary = {}
	var all: Array[Node] = root.find_children("*", "", true, false)
	for n: Node in all:
		out[n.get_class()] = int(out.get(n.get_class(), 0)) + 1
	out["(total)"] = all.size()
	return out


## MultiMesh batch name -> instance count.
func _batches(root: Node) -> Dictionary:
	var out: Dictionary = {}
	for n: Node in root.find_children("MM_*", "MultiMeshInstance3D", true, false):
		var mm: MultiMesh = (n as MultiMeshInstance3D).multimesh
		out[String(n.name)] = mm.instance_count if mm != null else -1
	return out


## Every collision shape in tree order: its kind, size (boxes) or face count, and place.
func _shapes(root: Node) -> PackedStringArray:
	var out: PackedStringArray = []
	for n: Node in root.find_children("*", "CollisionShape3D", true, false):
		var cs := n as CollisionShape3D
		var detail: String = ""
		if cs.shape is BoxShape3D:
			detail = str((cs.shape as BoxShape3D).size.snappedf(0.001))
		elif cs.shape is ConcavePolygonShape3D:
			detail = str((cs.shape as ConcavePolygonShape3D).get_faces().size())
		out.append("%s %s %s" % [cs.shape.get_class() if cs.shape != null else "-", detail, cs.transform.origin.snappedf(0.001)])
	return out
