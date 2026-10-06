extends GutTest
## PoiBuilder in phases (ADR-0038, RWG v2 Phase 3): a building raised one phase per frame is the
## same building as one built at once: the same nodes by class, the same kit and prop batches with
## the same instance counts, the same probes and collision shapes. Covers an ordinary house, a
## building with a cellar, the two largest (the sawmill and the campground) and a generated house.
## Prints the slowest phase of each (TD-102).

const Generator := preload("res://src/poi/building_generator.gd")


func _defs() -> Array[PoiDef]:
	var out: Array[PoiDef] = []
	for id: StringName in [&"merrow_house", &"okafor_farmhouse", &"larch_hollow_sawmill", &"tamsin_campground"]:
		var pd: PoiDef = Content.get_def(&"poi", id) as PoiDef
		if pd != null:
			out.append(pd)
	for t: Variant in Content.all(&"building_template"):
		var g: PoiDef = Generator.generate(t, 4242)
		if g != null:
			out.append(g)
			break
	return out


func test_a_phased_build_is_the_same_building() -> void:
	var defs: Array[PoiDef] = _defs()
	assert_gt(defs.size(), 3, "content present")
	for pd: PoiDef in defs:
		var layout := PoiLayout.compile(pd)
		# The same instance id: legacy dressing seeds scatter and wall damage from it.
		var whole: PoiInstance = PoiBuilder.build(layout, StringName("test/%s" % pd.id))
		add_child_autofree(whole)
		var b: PoiBuilder = PoiBuilder.start(PoiLayout.compile(pd), StringName("test/%s" % pd.id))
		var slowest: String = ""
		var slowest_ms: float = 0.0
		var steps: int = 0
		while true:
			var phase: String = b.next_phase()
			var t0: int = Time.get_ticks_usec()
			var done: bool = b.step()
			var ms: float = float(Time.get_ticks_usec() - t0) / 1000.0
			# The route check runs on a worker in the game (PoiManager): leave it out of the report.
			if ms > slowest_ms and phase != "route":
				slowest_ms = ms
				slowest = phase
			steps += 1
			if done:
				break
			await get_tree().process_frame
		assert_eq(steps, PoiBuilder.PHASES.size(), "%s: one phase a step" % pd.id)
		add_child_autofree(b.root)
		gut.p("%s: slowest phase after the route check: %s %.1f ms" % [pd.id, slowest, slowest_ms])
		assert_eq(_census(b.root), _census(whole), "%s: same nodes" % pd.id)
		assert_eq(_batches(b.root), _batches(whole), "%s: same batches" % pd.id)


## Node counts by class, plus collision shapes and probes by count.
func _census(root: Node) -> Dictionary:
	var out: Dictionary = {}
	for n: Node in root.find_children("*", "", true, false):
		out[n.get_class()] = int(out.get(n.get_class(), 0)) + 1
	return out


## MultiMesh batch name -> instance count.
func _batches(root: Node) -> Dictionary:
	var out: Dictionary = {}
	for n: Node in root.find_children("MM_*", "MultiMeshInstance3D", true, false):
		var mm: MultiMesh = (n as MultiMeshInstance3D).multimesh
		out[String(n.name)] = mm.instance_count if mm != null else -1
	return out
