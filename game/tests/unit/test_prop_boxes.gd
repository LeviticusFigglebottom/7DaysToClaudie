extends GutTest
## Compound prop collision (TD-270): a PropDef's `boxes` parse and validate (unknown keys, sizes
## that are not positive and a kind other than "box" are errors), stand in its own frame (`at` is
## the centre of a box's base, `yaw` turns it), replace the one size box when PoiBuilder builds the
## prop, and are tagged with the prop's id (TraversalAudit names blockers by it) on every box.


func _raw(extra: Dictionary) -> Dictionary:
	var d: Dictionary = {"id": "t_shell", "name": "T", "variants": {"clean": "props/x"}, "size": [4.0, 3.0, 2.0]}
	d.merge(extra, true)
	return d


func _parse(extra: Dictionary) -> Array:
	var pd := PropDef.new()
	var errs: PackedStringArray = pd.parse(_raw(extra), &"prop", "test")
	return [pd, errs]


func test_boxes_parse_in_the_props_frame() -> void:
	var got: Array = _parse({"boxes": [{"size": [0.2, 2.0, 0.2], "at": [1.5, 0, -0.8]},
		{"size": [1.0, 0.5, 2.0], "at": [0, 1, 0], "yaw": 90, "_doc": "a comment"}]})
	var pd: PropDef = got[0]
	assert_eq(got[1], PackedStringArray(), "parses")
	assert_eq(pd.collision, "box", "boxes are a box collision: the field implies it")
	assert_eq(pd.boxes.size(), 2)
	assert_eq(pd.boxes[0]["size"], Vector3(0.2, 2.0, 0.2))
	assert_eq(pd.boxes[0]["at"], Vector3(1.5, 0.0, -0.8))
	assert_eq(float(pd.boxes[0]["yaw"]), 0.0, "yaw defaults to 0")
	var cb: Array = pd.collision_boxes()
	assert_eq(cb.size(), 2, "one shape a box, no size box")
	# `at` is the base centre: the shape's centre is half its height above it.
	assert_eq(cb[0][0], Vector3(0.2, 2.0, 0.2))
	assert_almost_eq((cb[0][1] as Transform3D).origin, Vector3(1.5, 1.0, -0.8), Vector3.ONE * 0.0001)
	var turned: Transform3D = cb[1][1]
	assert_almost_eq(turned.origin, Vector3(0.0, 1.25, 0.0), Vector3.ONE * 0.0001)
	assert_almost_eq(turned.basis * Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3.ONE * 0.0001, "yaw 90 turns +Z to +X, as a placement's rot")
	# Footprints: a point inside the turned box (1 x 2 turned: 2 along x) and one between them.
	assert_true(pd.plan_hits(Vector3(0.9, 0.0, 0.0), 0.0), "inside the turned box")
	assert_true(pd.plan_hits(Vector3(1.55, 0.0, -0.8), 0.0), "inside a post")
	assert_false(pd.plan_hits(Vector3(1.2, 0.0, 0.6), 0.0), "the gap between them is clear")
	assert_false(pd.plan_hits(Vector3(1.55, 0.0, -0.8), 0.0, 0.0), "boxes based at or over `below` don't count")


func test_without_boxes_the_size_box_stands() -> void:
	var pd: PropDef = _parse({})[0]
	var cb: Array = pd.collision_boxes()
	assert_eq(cb.size(), 1)
	assert_eq(cb[0][0], pd.size)
	assert_eq((cb[0][1] as Transform3D).origin, pd.box_centre())
	var none: PropDef = _parse({"collision": "none"})[0]
	assert_eq(none.collision_boxes().size(), 0, "collision none: no shape")
	assert_true(pd.plan_hits(Vector3(1.9, 0, 0.9), 0.0) and not pd.plan_hits(Vector3(2.1, 0, 0), 0.0), "the size box's footprint")


func test_bad_boxes_are_errors() -> void:
	var cases: Dictionary = {
		"negative size": {"boxes": [{"size": [1, -1, 1], "at": [0, 0, 0]}]},
		"zero size": {"boxes": [{"size": [1, 1, 0], "at": [0, 0, 0]}]},
		"unknown key": {"boxes": [{"size": [1, 1, 1], "at": [0, 0, 0], "rot": 3}]},
		"no at": {"boxes": [{"size": [1, 1, 1]}]},
		"short size": {"boxes": [{"size": [1, 1], "at": [0, 0, 0]}]},
		"text yaw": {"boxes": [{"size": [1, 1, 1], "at": [0, 0, 0], "yaw": "left"}]},
		"not an object": {"boxes": [[1, 1, 1]]},
		"not box collision": {"collision": "none", "boxes": [{"size": [1, 1, 1], "at": [0, 0, 0]}]},
	}
	for k: String in cases:
		var errs: PackedStringArray = _parse(cases[k])[1]
		assert_gt(errs.size(), 0, "%s is an error" % k)
	assert_eq(_parse({"collision": "box", "boxes": [{"size": [1, 1, 1], "at": [0, 0, 0]}]})[1], PackedStringArray(),
		"an explicit box collision is fine")


## A one-room POI with `props` built by PoiBuilder: [instance, builder].
func _build(props: Array) -> Array:
	var raw: Dictionary = {"id": "t_boxes", "name": "T", "tier": 1, "footprint": [16, 16],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAAAAAAAA", "AAAAAAAAA", "AAAAAAAAA", "AAAAAAAAA", "AAAAAAAAA",
			"AAAAAAAAA", "AAAAAAAAA", "AAAAAAAAA", "AAAAAAAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [4, 8], "side": "S", "type": "door", "state": "open"}],
		"props": props}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	var b: PoiBuilder = PoiBuilder.start(PoiLayout.compile(d), &"test/boxes")
	while not b.step():
		pass
	return [b.root, b]


func _tagged(n: Node, tag: String, out: Array[CollisionShape3D]) -> void:
	for c: Node in n.get_children():
		if c is CollisionShape3D and c.has_meta(&"prop") and str(c.get_meta(&"prop")) == tag:
			out.append(c)
		_tagged(c, tag, out)


## `n`'s transform relative to `root` (the instance is not in the tree).
func _rel(n: Node3D, root: Node3D) -> Transform3D:
	var t: Transform3D = n.transform
	var p: Node = n.get_parent()
	while p != null and p != root:
		t = (p as Node3D).transform * t
		p = p.get_parent()
	return t


func test_the_builder_makes_one_tagged_shape_a_box() -> void:
	var pd: PropDef = Content.get_def(&"prop", &"w4_trestle_boxcar") as PropDef
	assert_gt(pd.boxes.size(), 1, "the boxcar has compound collision")
	var built: Array = _build([{"prop": "w4_trestle_boxcar", "id": "car", "pos": [4.5, 4.5], "rot": 90},
		{"prop": "w4_chapel_lych_gate", "id": "gate", "pos": [2.0, 2.0], "rot": 0, "route_ok": true}])
	var inst: PoiInstance = built[0]
	var b: PoiBuilder = built[1]
	var shapes: Array[CollisionShape3D] = []
	_tagged(inst, "w4_trestle_boxcar", shapes)
	assert_eq(shapes.size(), pd.boxes.size(), "one shape per box, no size box")
	var xf: Transform3D = b._prop_xf(b.layout.props[0], pd)
	var want: Array = pd.collision_boxes()
	for i: int in want.size():
		var w: Transform3D = xf * (want[i][1] as Transform3D)
		var found: bool = false
		for cs: CollisionShape3D in shapes:
			if _rel(cs, inst).origin.distance_to(w.origin) < 0.001 \
					and ((cs.shape as BoxShape3D).size - (want[i][0] as Vector3)).length() < 0.001:
				found = true
		assert_true(found, "box %d stands at %s, turned with the prop" % [i, w.origin])
	var gate: Array[CollisionShape3D] = []
	_tagged(inst, "w4_chapel_lych_gate+route_ok", gate)
	assert_eq(gate.size(), 4, "the lych gate's four posts, each tagged with the route_ok mark")
	inst.free()


func test_a_container_prop_collides_as_its_boxes() -> void:
	var truck: PropDef = Content.get_def(&"prop", &"w4_ranger_brush_truck") as PropDef
	assert_ne(truck.container, &"", "the brush truck is searched")
	var built: Array = _build([{"prop": "w4_ranger_brush_truck", "id": "truck", "pos": [4.5, 4.5], "rot": 0}])
	var inst: PoiInstance = built[0]
	var lp: PoiPieces.LootProp = null
	for c: Node in inst.get_children():
		if c is PoiPieces.LootProp:
			lp = c
	assert_not_null(lp, "a LootProp")
	if lp != null:
		var n: int = 0
		var low: int = 0
		for c: Node in lp.get_children():
			if c is CollisionShape3D:
				n += 1
				var top: float = (c as CollisionShape3D).position.y + ((c as CollisionShape3D).shape as BoxShape3D).size.y * 0.5
				if top <= TraversalAudit.VAULT_MAX:
					low += 1
		assert_eq(n, truck.boxes.size(), "the truck's boxes, not its size box")
		assert_gt(low, 0, "the bumpers are low enough to vault")
	inst.free()
