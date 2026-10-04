extends GutTest


func _graph_column(levels: int, vloss: float = 0.04) -> StructureGraph:
	var g := StructureGraph.new()
	for i: int in levels:
		g.add_piece(StringName("c%d" % i), &"log_piece", 4.0, vloss, i == 0)
		if i > 0:
			g.link(StringName("c%d" % i), StringName("c%d" % (i - 1)), StructureGraph.Link.ON)
	g.recompute()
	return g


func test_grounded_piece_is_fully_stable() -> void:
	var g := _graph_column(1)
	assert_eq(g.stability(&"c0"), 1.0)


func test_vertical_stack_loses_a_little_per_level() -> void:
	var g := _graph_column(5, 0.05)
	assert_almost_eq(g.stability(&"c4"), 0.8, 0.0001)


func test_cantilever_beyond_span_fails() -> void:
	var g := StructureGraph.new()
	g.add_piece(&"base", &"log_piece", 4.0, 0.04, true)
	var prev: StringName = &"base"
	for i: int in 6:
		var id := StringName("arm%d" % i)
		g.add_piece(id, &"log_piece", 4.0, 0.04, false)
		g.link(id, prev, StructureGraph.Link.SIDE)
		prev = id
	var failed: Array[StringName] = g.recompute()
	# span 4 -> each sideways step costs 0.25: arm0 .75, arm1 .5, arm2 .25, arm3 0 (fails), arm4, arm5 fail.
	assert_eq(failed, [&"arm3", &"arm4", &"arm5"] as Array[StringName])
	assert_almost_eq(g.stability(&"arm2"), 0.25, 0.0001)


func test_removing_support_collapses_dependents() -> void:
	var g := _graph_column(4)
	var collapsed: Array[StringName] = g.remove_and_cascade(&"c0")
	collapsed.sort_custom(func(a: StringName, b: StringName) -> bool: return String(a) < String(b))
	assert_eq(collapsed, [&"c1", &"c2", &"c3"] as Array[StringName])
	assert_eq(g.size(), 0)


func test_redundant_support_survives_removal() -> void:
	# Two pillars holding one beam: removing one pillar keeps the beam up.
	var g := StructureGraph.new()
	g.add_piece(&"p1", &"log_piece", 4.0, 0.04, true)
	g.add_piece(&"p2", &"log_piece", 4.0, 0.04, true)
	g.add_piece(&"beam", &"log_piece", 4.0, 0.04, false)
	g.link(&"beam", &"p1", StructureGraph.Link.ON)
	g.link(&"beam", &"p2", StructureGraph.Link.ON)
	g.recompute()
	assert_eq(g.remove_and_cascade(&"p1").size(), 0)
	assert_gt(g.stability(&"beam"), 0.9)


func test_removal_only_touches_its_component() -> void:
	var g := _graph_column(2)
	g.add_piece(&"other", &"log_piece", 4.0, 0.04, true)
	g.recompute()
	g.remove_and_cascade(&"c0")
	assert_true(g.has_piece(&"other"))
	assert_eq(g.stability(&"other"), 1.0)


func test_serialization_round_trip() -> void:
	var g := _graph_column(3)
	var h := StructureGraph.new()
	h.from_dict(JSON.parse_string(JSON.stringify(g.to_dict())))
	assert_eq(h.size(), 3)
	assert_almost_eq(h.stability(&"c2"), g.stability(&"c2"), 0.0001)
	assert_eq(h.remove_and_cascade(&"c0").size(), 2)
