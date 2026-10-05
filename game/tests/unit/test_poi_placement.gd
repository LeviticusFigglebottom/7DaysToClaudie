extends GutTest
## PoiBuilder placement: free-standing level-0 props and pickups on yard cells stand on the pad
## (y = 0), on the porch deck and indoors on the floor (floor_height); boards on a barricaded
## interior door face the way in, never the room they seal, unless "barricade_on" names a room.


func _def(raw_layout: Dictionary) -> PoiDef:
	var raw: Dictionary = {"id": "t", "name": "T", "tier": 1, "footprint": [16, 16]}
	raw.merge(raw_layout, true)
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func _build(d: PoiDef) -> PoiInstance:
	return PoiBuilder.build(PoiLayout.compile(d), &"test/placement")


func _loot_y(inst: PoiInstance, key: String) -> float:
	for c: Node in inst.get_children():
		if c is PoiPieces.LootProp and (c as PoiPieces.LootProp).prop_key == key:
			return (c as Node3D).position.y
	fail_test("no loot prop '%s'" % key)
	return NAN


func _pickup_y(inst: PoiInstance, pid: String) -> float:
	for c: Node in inst.get_children():
		if c is PoiPieces.Pickup and (c as PoiPieces.Pickup).pickup_id == pid:
			return (c as Node3D).position.y
	fail_test("no pickup '%s'" % pid)
	return NAN


func _piece_x(inst: PoiInstance, piece_id: String) -> float:
	for c: Node in inst.get_children():
		if c is PoiPieces.Breakable and (c as PoiPieces.Breakable).piece_id == piece_id:
			return (c as Node3D).position.x
	fail_test("no piece '%s'" % piece_id)
	return NAN


func test_yard_items_stand_on_the_pad_and_porch_items_on_the_deck() -> void:
	var d: PoiDef = _def({
		"style": {"floor_height": 0.6, "porch": {"side": "S", "from": 0, "to": 1, "depth": 2}},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [0, 1], "side": "S", "type": "door"}],
		"props": [
			{"id": "inside", "prop": "crate_wood", "at": [1, 0]},
			{"id": "porch", "prop": "crate_wood", "at": [0, 2]},
			{"id": "yard", "prop": "crate_wood", "at": [3, 3]},
			{"id": "yard_lifted", "prop": "crate_wood", "at": [-2, 0], "y": 0.4}],
		"pickups": [{"id": "yard_key", "item": "pharmacy_key", "at": [3, 3], "y": 0.1},
			{"id": "porch_key", "item": "pharmacy_key", "at": [1, 3], "y": 0.1}]})
	var inst: PoiInstance = _build(d)
	assert_almost_eq(_loot_y(inst, "inside"), 0.6, 0.001, "indoors: on the floor")
	assert_almost_eq(_loot_y(inst, "porch"), 0.6, 0.001, "on the porch deck")
	assert_almost_eq(_loot_y(inst, "yard"), 0.0, 0.001, "in the yard: on the pad")
	assert_almost_eq(_loot_y(inst, "yard_lifted"), 0.4, 0.001, "yard y is measured from the pad")
	assert_almost_eq(_pickup_y(inst, "yard_key"), 0.1, 0.001)
	assert_almost_eq(_pickup_y(inst, "porch_key"), 0.7, 0.001)
	inst.free()


func _sealed(extra: Dictionary) -> PoiDef:
	# B (x 0) is sealed off: its only door, on the H|B edge at x = 1 (H on the wall's "a" side,
	# where the old rule never put boards), is boarded; the way in is through H.
	var seal: Dictionary = {"id": "seal", "at": [1, 0], "side": "W", "type": "door", "state": "barricaded"}
	seal.merge(extra, true)
	return _def({
		"levels": [{"level": 0, "plan": ["BHH"], "rooms": {"B": {}, "H": {}}}],
		"openings": [{"id": "front", "at": [2, 0], "side": "S", "type": "door"}, seal]})


func test_interior_boards_face_the_way_in() -> void:
	var inst: PoiInstance = _build(_sealed({}))
	assert_gt(_piece_x(inst, "seal_bar"), 1.0, "boards on the hall side, not inside the sealed room")
	inst.free()


func test_barricade_on_names_the_room() -> void:
	var inst: PoiInstance = _build(_sealed({"barricade_on": "B"}))
	assert_lt(_piece_x(inst, "seal_bar"), 1.0, "authored: inside B")
	inst.free()
