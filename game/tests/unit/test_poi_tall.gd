extends GutTest
## Tall rooms, the roof planner and per-room probes (ADR-0021): a room's "storeys" and the '^' void
## it rises through compile into one volume (no floor, no ceiling between; walls rise through;
## galleries look over it); the validator keeps everything off the void and lets an authored gap in
## a gallery be a one-way drop that must not strand the player; two-storey openings need a wall
## above; RoofPlanner splits massing into wings (L legs, lean-to annexes, towers, overrides) whose
## roofs RoofBuilder joins without overlapping faces; probe boxes cover rooms, not yards.


func _def(layout: Dictionary, footprint: Array = [16, 16]) -> PoiDef:
	var raw: Dictionary = {"id": "t", "name": "T", "tier": 2, "footprint": footprint}
	raw.merge(layout, true)
	var d := PoiDef.new()
	var errs: PackedStringArray = d.parse(raw, &"poi", "test")
	assert_eq(errs, PackedStringArray(), "def parses")
	return d


func _count(list: PackedStringArray, needle: String) -> int:
	var n: int = 0
	for e: String in list:
		if e.contains(needle):
			n += 1
	return n


## A hall two storeys tall (columns 0-3) with a loft (columns 4-5) on its east side upstairs, a
## stair up to the loft from a lobby, and a door in from the yard.
func _hall(extra: Dictionary = {}) -> Dictionary:
	var lay: Dictionary = {
		"style": {"floor_height": 0.6, "roof": {"type": "gable", "axis": "x", "pitch": 30}},
		"levels": [
			{"level": 0, "plan": ["HHHHLL", "HHHHLL", "HHHHLL", "HHHHLL", "HHHHLL"],
				"rooms": {"H": {"name": "Hall", "type": "hall", "storeys": 2}, "L": {"name": "Lobby", "type": "hallway"}}},
			{"level": 1, "plan": ["^^^^GG", "^^^^GG", "^^^^GG", "^^^^GG", "^^^^GG"],
				"rooms": {"G": {"name": "Gallery", "type": "hallway"}}}],
		"openings": [
			{"id": "front", "at": [1, 4], "side": "S", "type": "door"},
			{"id": "lobby_door", "at": [4, 2], "side": "W", "type": "door", "state": "open"}],
		"stairs": [{"level": 0, "at": [5, 4], "dir": "N"}],
		"props": [{"id": "shelf", "prop": "metal_shelf", "at": [0, 0], "against": "N"}],
		"route": [{"at": [1, 6]}, {"at": [2, 2]}, {"at": [5, 0], "level": 1}],
		"loot_room": {"room": "H", "level": 0}}
	lay.merge(extra, true)
	return lay


func test_tall_room_compiles_into_one_volume() -> void:
	var v: PoiValidator = PoiValidator.validate(_def(_hall()))
	assert_eq(v.errors, PackedStringArray())
	var l: PoiLayout = v.layout
	assert_true(l.is_void(1, Vector2i(2, 2)))
	assert_false(l.is_room(l.room_at(1, Vector2i(2, 2))), "a void cell has no floor of its own")
	assert_eq(l.volume_of(1, Vector2i(2, 2)), [0, "H"], "the void belongs to the hall below")
	assert_eq(l.floor_cell(1, Vector2i(2, 2)), [0, Vector2i(2, 2)])
	assert_eq(l.column_top(0, Vector2i(2, 2)), 1)
	assert_eq(l.column_top(0, Vector2i(4, 2)), 0, "the lobby is one storey")
	assert_almost_eq(l.ceiling_height(0, Vector2i(2, 2)), 5.8, 1e-4)
	# Walls rise through the void to the outside; none inside it; a gallery edge toward the loft.
	assert_true(l.walls.has(PoiLayout.edge_key(1, "v", Vector2i(0, 2))), "west wall continues up")
	assert_true(bool(l.walls[PoiLayout.edge_key(1, "v", Vector2i(0, 2))]["exterior"]))
	assert_false(l.walls.has(PoiLayout.edge_key(1, "v", Vector2i(2, 2))), "no wall inside the void")
	assert_false(l.walls.has(PoiLayout.edge_key(1, "v", Vector2i(4, 2))), "the loft looks over the hall")
	assert_true(l.galleries.has(PoiLayout.edge_key(1, "v", Vector2i(4, 2))))
	assert_eq(str(l.galleries[PoiLayout.edge_key(1, "v", Vector2i(4, 2))]["style"]), "balustrade")
	assert_eq(v.stats["levels"], 2)


func test_void_needs_a_tall_room_under_it() -> void:
	var lay: Dictionary = _hall()
	lay["levels"][0]["rooms"]["H"].erase("storeys")
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_gt(_count(v.errors, "give it \"storeys\": 2"), 0, "a room rising through a storey must say so")
	var lay2: Dictionary = _hall()
	lay2["levels"][1]["plan"] = ["^^^^GG", "^^^^GG", "^^^^GG", "^^^^GG", "^^^^GG", "^^^^GG"]
	var v2: PoiValidator = PoiValidator.validate(_def(lay2))
	assert_gt(_count(v2.errors, "no room rises from below it"), 0, "a void over the yard")
	var lay3: Dictionary = _hall()
	lay3["levels"][0]["rooms"]["H"]["storeys"] = 4
	lay3["levels"][0]["rooms"]["H"]["stories"] = 2
	var v3: PoiValidator = PoiValidator.validate(_def(lay3))
	assert_eq(_count(v3.errors, "storeys must be 1..3"), 1)
	assert_eq(_count(v3.errors, "unknown key 'stories'"), 1, "room keys are checked")
	var lay4: Dictionary = _hall()
	lay4["levels"][0]["rooms"]["L"]["storeys"] = 2
	var v4: PoiValidator = PoiValidator.validate(_def(lay4))
	assert_eq(_count(v4.warnings, "no '^' above it"), 1, "a tall room that never rises warns")


func test_nothing_stands_in_the_void() -> void:
	var lay: Dictionary = _hall({
		"sleepers": [{"id": "floater", "at": [1, 1], "level": 1}],
		"pickups": [{"id": "key_up", "item": "pharmacy_key", "at": [2, 1], "level": 1}],
		"traps": [{"id": "boards", "type": "creaky_floor", "at": [3, 1], "level": 1}],
		"holes": [{"level": 1, "at": [3, 3]}]})
	lay["props"].append({"prop": "chair_wood", "at": [1, 3], "level": 1})
	lay["props"].append({"prop": "civic_hymn_board", "at": [0, 3], "against": "W", "level": 1, "height": 1.0})
	lay["route"].append({"at": [2, 3], "level": 1})
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_count(v.errors, "sleeper 'floater'"), 1)
	assert_eq(_count(v.errors, "pickup 'key_up'"), 1)
	assert_eq(_count(v.errors, "trap 'boards'"), 1)
	assert_eq(_count(v.errors, "hole at (3, 3)"), 1)
	assert_eq(_count(v.errors, "prop 'chair_wood'"), 1, "a chair floats in the open space")
	assert_eq(_count(v.errors, "civic_hymn_board"), 0, "a wall-mounted board hangs on the tall wall")
	assert_eq(_count(v.errors, "open space; put it on its floor"), 1, "a route waypoint up in the void")


func test_gallery_gap_is_a_one_way_drop() -> void:
	# Without a gap the hall floor is only reached by the door; with one, from the gallery too.
	var lay: Dictionary = _hall()
	lay["route"] = [{"at": [1, 6]}, {"at": [5, 0], "level": 1}, {"at": [2, 2]}]
	lay["openings"][1]["state"] = "locked"
	lay["openings"][1]["key"] = "pharmacy_key"
	lay["openings"][0]["at"] = [5, 4]
	lay["stairs"] = [{"level": 0, "at": [4, 4], "dir": "N"}]
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_gt(_count(v.errors, "unreachable from the previous one"), 0, "the railing holds")
	lay["openings"].append({"id": "loft_gap", "at": [4, 1], "side": "W", "type": "open", "level": 1})
	var v2: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_count(v2.errors, "unreachable"), 0, "over the gap and down into the hall")
	assert_eq(_count(v2.errors, "strands the player"), 1, "but the hall's only door is locked")
	# At the stair's foot: a door onto the flight above it would meet the steps a metre up.
	lay["openings"][1] = {"id": "lobby_door", "at": [3, 4], "side": "E", "type": "door", "state": "locked_inside"}
	var v3: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(v3.errors, PackedStringArray(), "the bolt opens from the hall side")


func test_gallery_takes_only_gaps_and_can_be_a_wall() -> void:
	var lay: Dictionary = _hall()
	lay["openings"].append({"id": "gal_window", "at": [4, 1], "side": "W", "type": "window", "level": 1})
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_count(v.errors, "is on a gallery edge"), 1)
	lay["levels"][1]["rooms"]["G"]["gallery"] = false
	var v2: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(v2.errors, PackedStringArray(), "a wall with a window over the hall")
	assert_true(v2.layout.walls.has(PoiLayout.edge_key(1, "v", Vector2i(4, 1))))
	lay["levels"][1]["rooms"]["G"]["gallery"] = "rail"
	lay["openings"].pop_back()
	var v3: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(str(v3.layout.galleries[PoiLayout.edge_key(1, "v", Vector2i(4, 2))]["style"]), "rail")


func test_tall_openings_span_two_storeys() -> void:
	var lay: Dictionary = _hall()
	lay["openings"].append({"id": "lancet_w", "at": [0, 2], "side": "W", "type": "lancet", "state": "closed"})
	lay["openings"].append({"id": "bad_tall", "at": [5, 1], "side": "E", "type": "window_tall"})
	lay["openings"].append({"id": "doors_tall", "at": [1, 4], "side": "S", "type": "door2_tall"})
	lay["openings"].remove_at(0)
	lay["route"][1] = {"at": [2, 2]}
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	var l: PoiLayout = v.layout
	assert_eq(int(l.opening("lancet_w")["storeys"]), 2)
	assert_true(l.walls[PoiLayout.edge_key(1, "v", Vector2i(0, 2))].has("covered"), "the lancet fills the wall above too")
	assert_eq(_count(v.errors, "tall opening 'bad_tall'"), 0, "the lobby's east wall rises to the loft's")
	assert_true(l.walls[PoiLayout.edge_key(1, "v", Vector2i(6, 1))].has("covered"))
	assert_eq(_count(v.errors, "unreachable"), 0, "tall double doors are a way in")
	# A lancet does not let anyone through while its glass is whole.
	assert_false(v._opening_passable(l.opening("lancet_w"), Vector2i(0, 2), {}))
	var lay2: Dictionary = _hall()
	lay2["levels"][1]["plan"] = ["^^^^  ", "^^^^  ", "^^^^  ", "^^^^  ", "^^^^  "]
	lay2["levels"][1]["rooms"] = {}
	lay2["stairs"] = []
	lay2["route"] = [{"at": [1, 6]}, {"at": [2, 2]}]
	lay2["openings"].append({"id": "lobby_tall", "at": [5, 1], "side": "E", "type": "window_tall"})
	var v2: PoiValidator = PoiValidator.validate(_def(lay2))
	assert_eq(_count(v2.errors, "tall opening 'lobby_tall'"), 1, "no wall above the one-storey lobby")


func test_tall_door_pair_is_mirrored() -> void:
	# The barn door is dressed on one face (battens, braces, strap hinges): the right leaf is the
	# left one mirrored, not turned half round, so both show their dressed face outside.
	var lay: Dictionary = _hall()
	lay["openings"][0] = {"id": "doors_tall", "at": [1, 4], "side": "S", "type": "door2_tall", "state": "closed"}
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(lay)), &"test/tall_doors")
	add_child_autofree(inst)
	var dets: Dictionary = {}
	for n: Node in inst.get_children():
		if not n is PoiPieces.Door:
			continue
		var d: PoiPieces.Door = n
		for c: Node in d.pivot.get_children():
			if c is MeshInstance3D:
				dets[d.op_id] = (d.pivot.transform.basis * (c as MeshInstance3D).transform.basis).determinant()
				break
	assert_gt(float(dets.get("doors_tall_l", 0.0)), 0.0, "the left leaf as modelled")
	assert_lt(float(dets.get("doors_tall_r", 0.0)), 0.0, "the right leaf is the left one mirrored")
	assert_gt(float(dets.get("lobby_door", 0.0)), 0.0, "single leaves are not mirrored")


func test_locate_answers_for_the_whole_volume() -> void:
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(_hall())), &"test/tall")
	add_child_autofree(inst)
	var l: PoiLayout = inst.layout
	var high: Vector3 = inst.to_global(l.cell_center(1, Vector2i(2, 2)) + Vector3.UP * 1.0)
	assert_eq(inst.locate(high), [0, Vector2i(2, 2)], "up in the hall's open space is the hall")
	assert_true(inst.is_indoors(high))
	assert_eq(inst.room_type_at(high), "hall")
	var gal: Vector3 = inst.to_global(l.cell_center(1, Vector2i(5, 2)) + Vector3.UP * 1.0)
	assert_eq(inst.locate(gal), [1, Vector2i(5, 2)])


## The builder's kit batches (key -> {xf: [Transform3D], c: [Color]}): a headless MultiMesh does
## not keep its instances, so tests read what the builder put in.
func _batches(lay: Dictionary, id: StringName) -> Array:
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def(lay))
	var inst: PoiInstance = b._build(id)
	add_child_autofree(inst)
	return [inst, b._batches]


func test_tall_room_builds_without_floor_or_ceiling_between() -> void:
	var built: Array = _batches(_hall(), &"test/tall_build")
	var l: PoiLayout = (built[0] as PoiInstance).layout
	var batches: Dictionary = built[1]
	var slab_at: Dictionary = {}
	var bands: int = 0
	var rails: int = 0
	var codes: Array = []
	for key: String in batches:
		var xfs: Array = batches[key]["xf"]
		var cs: Array = batches[key]["c"]
		for i: int in xfs.size():
			var o: Vector3 = (xfs[i] as Transform3D).origin
			if key.begins_with("floor_1m"):
				slab_at["%.1f:%.1f:%.1f" % [o.x, o.y, o.z]] = true
			elif key.begins_with("wall_band_1m"):
				bands += 1
			elif key.begins_with("gallery_balustrade_1m"):
				rails += 1
			elif key.begins_with("wall_1m"):
				codes.append(int(floor((cs[i] as Color).a)))
	var mid: Vector3 = l.cell_center(1, Vector2i(2, 2))
	assert_false(slab_at.has("%.1f:%.1f:%.1f" % [mid.x, mid.y, mid.z]), "no floor across the hall at the storey line")
	var top: Vector3 = mid + Vector3.UP * PoiLayout.STOREY
	assert_true(slab_at.has("%.1f:%.1f:%.1f" % [top.x, top.y, top.z]), "its ceiling is a storey up")
	assert_gt(bands, 0, "storey bands close the gap between stacked pieces")
	assert_eq(rails, 5, "a railing along the loft's edge")
	assert_true(codes.has(4) or codes.has(5) or codes.has(4 * 16) or codes.has(5 * 16), "tall-room pieces carry height codes")


func test_roof_plan_follows_the_massing() -> void:
	# An L: main block 10 x 6 with a 4 x 4 leg off its back, one storey.
	var l_shape: Dictionary = {
		"style": {"roof": {"type": "gable", "pitch": 35}},
		"levels": [{"level": 0, "plan": ["AAAA      ", "AAAA      ", "AAAA      ", "AAAA      ", "BBBBBBBBBB", "BBBBBBBBBB",
			"BBBBBBBBBB", "BBBBBBBBBB", "BBBBBBBBBB", "BBBBBBBBBB"], "rooms": {"A": {}, "B": {"open_to": "A"}}}]}
	var wings: Array = RoofPlanner.plan(PoiLayout.compile(_def(l_shape)))
	assert_eq(wings.size(), 2)
	var main: RoofPlanner.Wing = wings[0]
	var leg: RoofPlanner.Wing = wings[1]
	assert_eq(main.cells, Rect2i(0, 4, 10, 6))
	assert_eq(main.axis, "x", "the main ridge runs along its long side")
	assert_eq(leg.role, "leg")
	assert_eq(leg.axis, "z", "the leg's ridge runs into the main roof")
	assert_eq(leg.span, Rect2i(0, 0, 4, 7), "and on to the main ridge")
	assert_eq(leg.ends, [true, false] as Array[bool], "its end inside the main roof has no gable wall")
	# A two-storey block with a one-storey annex on its south side: a lean-to sloping south.
	var annex: Dictionary = {
		"style": {"roof": {"type": "gable", "pitch": 40}},
		"levels": [
			{"level": 0, "plan": ["AAAAAA", "AAAAAA", "AAAAAA", "AAAAAA", "BBBBBB", "BBBBBB", "BBBBBB"], "rooms": {"A": {}, "B": {}}},
			{"level": 1, "plan": ["CCCCCC", "CCCCCC", "CCCCCC", "CCCCCC"], "rooms": {"C": {}}}],
		"openings": [{"id": "up_win", "at": [2, 3], "side": "S", "type": "window", "level": 1}]}
	var w2: Array = RoofPlanner.plan(PoiLayout.compile(_def(annex)))
	var lean: RoofPlanner.Wing = null
	for w: RoofPlanner.Wing in w2:
		if w.level == 0:
			lean = w
	assert_not_null(lean)
	assert_eq(lean.type, "shed")
	assert_eq(lean.slope, 2, "away from the taller wall")
	assert_lt(lean.rise(), 0.85 - RoofPlanner.FLASHING + 0.01, "under the window sill upstairs")
	# A small top two storeys up beside nothing of its level: a tower with a hip.
	var tower: Dictionary = {
		"style": {"roof": {"type": "gable"}},
		"levels": [
			{"level": 0, "plan": ["AAAAAAAA", "AAAAAAAA", "AAAAAAAA", "AAAAAAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["   TTT  ", "   TTT  ", "   TTT  "], "rooms": {"T": {}}}]}
	var w3: Array = RoofPlanner.plan(PoiLayout.compile(_def(tower)))
	var top: RoofPlanner.Wing = null
	for w: RoofPlanner.Wing in w3:
		if w.level == 1:
			top = w
	assert_eq(top.role, "tower")
	assert_eq(top.type, "hip")
	# Overrides name a wing by a cell; a bad one is reported.
	tower["style"]["roof"]["roofs"] = [{"level": 1, "at": [4, 1], "type": "spire"}, {"level": 1, "at": [0, 3], "type": "hip"}]
	var roof_errors: Array = []
	var w4: Array = RoofPlanner.plan(PoiLayout.compile(_def(tower)), roof_errors)
	var spire: bool = false
	for w: RoofPlanner.Wing in w4:
		spire = spire or (w.level == 1 and w.type == "spire")
	assert_true(spire)
	assert_eq(roof_errors.size(), 1, "no roof at level 1 over (0, 3)")
	var v: PoiValidator = PoiValidator.validate(_def(tower))
	assert_eq(_count(v.errors, "roof override"), 1, "and the validator reports it")


func test_roof_faces_never_overlap() -> void:
	# Cross gables, a lean-to and a tower through the main roof: after clipping, every point of the
	# plan is under at most one face.
	var lay: Dictionary = {
		"style": {"roof": {"type": "gable", "pitch": 38, "overhang": 0.5}},
		"levels": [
			{"level": 0, "plan": ["  AAAA    ", "  AAAA    ", "BBBBBBBBBB", "BBBBBBBBBB", "BBBBBBBBBB", "BBBBBBBBBB", "CCCCCC    ", "CCCCCC    "],
				"rooms": {"A": {}, "B": {}, "C": {}}},
			{"level": 1, "plan": ["  DDDD    ", "  DDDD    ", "DDDDDDDDDD", "DDDDDDDDDD", "DDDDDDDDDD", "DDDDDDDDDD"], "rooms": {"D": {}}},
			{"level": 2, "plan": ["          ", "          ", "    TT    ", "    TT    "], "rooms": {"T": {}}}]}
	var layout: PoiLayout = PoiLayout.compile(_def(lay))
	var wings: Array = RoofPlanner.plan(layout)
	var faces: Array = []
	for w: RoofPlanner.Wing in wings:
		match w.type:
			"gable":
				faces.append_array(RoofBuilder._gable_faces(w, layout.origin, w.index))
			"hip", "pyramid":
				faces.append_array(RoofBuilder._hip_faces(w, layout.origin, w.index))
			"shed":
				faces.append_array(RoofBuilder._shed_faces(w, layout.origin, w.index))
	var feet: Array[Rect2] = []
	for w2: RoofPlanner.Wing in wings:
		feet.append(w2.rect_m(layout.origin, w2.span))
	var typed: Array[RoofBuilder.Face] = []
	typed.assign(faces)
	RoofBuilder._clip(typed, feet)
	# Inside a wing's walls nothing of another wing's roof shows below its own (it would poke
	# through as a sheet in the attic, or cut the valley wrong); out under an eave it may.
	var buried: int = 0
	var x: float = -1.13
	while x < 11.0:
		var z: float = -1.07
		while z < 9.0:
			var p := Vector2(x, z)
			for f: RoofBuilder.Face in typed:
				var h_f: float = -INF
				for piece: PackedVector2Array in f.pieces:
					if RoofBuilder.point_in(piece, p):
						h_f = f.h(p)
				if h_f == -INF:
					continue
				for g: RoofBuilder.Face in typed:
					if g.wing == f.wing or not feet[g.wing].has_point(p):
						continue
					for piece2: PackedVector2Array in g.pieces:
						if RoofBuilder.point_in(piece2, p) and g.h(p) > h_f + 0.01:
							buried += 1
			z += 0.37
		x += 0.41
	assert_eq(buried, 0, "no roof face left under another wing's roof inside its walls")


func test_polygon_subtract_conserves_area() -> void:
	var sq := PackedVector2Array([Vector2(0, 0), Vector2(4, 0), Vector2(4, 4), Vector2(0, 4)])
	var cut := PackedVector2Array([Vector2(1, 1), Vector2(3, 1), Vector2(3, 5), Vector2(1, 5)])
	var pieces: Array = RoofBuilder.subtract(sq, cut)
	var total: float = 0.0
	for p: PackedVector2Array in pieces:
		total += RoofBuilder.area(p)
	assert_almost_eq(total, 16.0 - 6.0, 1e-4)
	assert_eq(RoofBuilder.subtract(sq, PackedVector2Array([Vector2(5, 5), Vector2(6, 5), Vector2(6, 6)])).size(), 1, "a cut beside it")


func test_probe_boxes_cover_rooms_not_yards() -> void:
	# An L: the yard in its inner corner gets no probe.
	var lay: Dictionary = {
		"levels": [{"level": 0, "plan": ["AAAA....", "AAAA....", "AAAAAAAA", "AAAAAAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "d", "at": [5, 3], "side": "S", "type": "door"}],
		"route": [{"at": [5, 5]}, {"at": [5, 3]}]}
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def(lay))
	var boxes: Array[AABB] = b.probe_boxes()
	assert_eq(boxes.size(), 2)
	var yard: Vector3 = b.layout.cell_center(0, Vector2i(6, 0)) + Vector3.UP
	var room: Vector3 = b.layout.cell_center(0, Vector2i(1, 0)) + Vector3.UP
	var in_yard: bool = false
	var in_room: bool = false
	for box: AABB in boxes:
		in_yard = in_yard or box.has_point(yard)
		in_room = in_room or box.has_point(room)
	assert_false(in_yard, "the yard in the L keeps the outdoor light")
	assert_true(in_room)
	# The tall hall's box spans both storeys; the lobby and the loft over it stack into one.
	var b2 := PoiBuilder.new()
	b2.layout = PoiLayout.compile(_def(_hall()))
	var hall_top: float = 0.0
	for box2: AABB in b2.probe_boxes():
		if box2.has_point(b2.layout.cell_center(0, Vector2i(1, 1)) + Vector3.UP):
			hall_top = box2.end.y
	assert_almost_eq(hall_top, b2.layout.level_y(1) + PoiLayout.STOREY, 1e-3)
	assert_eq(b2.probe_boxes().size(), 2)


func test_probe_count_is_capped() -> void:
	var rows: Array = []
	for r: int in 9:
		var row: String = ""
		for c: int in 18:
			row += "A" if (r % 2 == 0 or c % 3 == 0) else "."
		rows.append(row)
	var lay: Dictionary = {"levels": [{"level": 0, "plan": rows, "rooms": {"A": {}}}]}
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def(lay, [20, 12]))
	assert_lte(b.probe_boxes().size(), PoiBuilder.MAX_PROBES)


func test_stairs_stand_off_the_walls() -> void:
	# TD-023: a flight along the west wall moves 8 cm east and keeps its banister on the open side.
	var lay: Dictionary = {
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA", "AAA", "AAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBB", "BBB", "BBB", "BBB", "BBB"], "rooms": {"B": {}}}],
		"stairs": [{"level": 0, "at": [0, 4], "dir": "N"}]}
	var built: Array = _batches(lay, &"test/stairs")
	var inst: PoiInstance = built[0]
	var batches: Dictionary = built[1]
	var flight: Vector3 = (batches["stairs_straight"]["xf"][0] as Transform3D).origin
	var rails: Array[Vector3] = []
	for xf: Transform3D in batches["stairs_railing"]["xf"]:
		rails.append(xf.origin)
	var cx: float = inst.layout.cell_center(0, Vector2i(0, 4)).x
	assert_almost_eq(flight.x, cx + PoiBuilder.WALL_T * 0.5, 1e-4, "off the west wall")
	assert_almost_eq(flight.z, inst.layout.cell_center(0, Vector2i(0, 4)).z + 0.5 - PoiBuilder.WALL_T * 0.5, 1e-4, "off the wall at its foot")
	assert_eq(rails.size(), 1, "one banister")
	assert_gt(rails[0].x, flight.x, "on the open east side")


func test_farmhouse_ell_is_an_annex_gable_with_its_own_probe() -> void:
	# The showcase L: the Okafor farmhouse's one-storey summer-kitchen ell against the two-storey
	# house's east gable end. Its east windows moved to the back wall, so nothing lowers its pitch.
	var pd: PoiDef = Content.get_def(&"poi", &"okafor_farmhouse") as PoiDef
	if pd == null:
		pending("farm content missing")
		return
	var l: PoiLayout = PoiLayout.compile(pd)
	var ell: RoofPlanner.Wing = null
	for w: RoofPlanner.Wing in RoofPlanner.plan(l):
		if w.level == 0 and w.cells.has_point(Vector2i(14, 1)):
			ell = w
	assert_not_null(ell, "the ell has a roof of its own")
	if ell == null:
		return
	assert_eq(ell.cells, Rect2i(12, 0, 5, 4))
	assert_eq([ell.role, ell.type, ell.axis], ["annex", "gable", "x"], "an abutting gable, its ridge running away from the house")
	assert_almost_eq(ell.pitch, 38.0, 0.01, "the house's pitch")
	assert_false(ell.ends[0], "closed against the house")
	assert_true(ell.ends[1], "a gable end outside")
	var b := PoiBuilder.new()
	b.layout = l
	var yard: Vector3 = l.cell_center(0, Vector2i(14, 6)) + Vector3.UP
	var kitchen: Vector3 = l.cell_center(0, Vector2i(14, 1)) + Vector3.UP
	var in_yard: bool = false
	var in_kitchen: bool = false
	for box: AABB in b.probe_boxes():
		in_yard = in_yard or box.has_point(yard)
		in_kitchen = in_kitchen or box.has_point(kitchen)
	assert_false(in_yard, "the yard in the L's corner stays outdoors")
	assert_true(in_kitchen, "the summer kitchen is lit as a room")


func test_chimney_clears_the_roof() -> void:
	# A chimney at a two-storey gable end used to stop at 4.5 m, under the eaves. It stands on whole
	# metres of shaft until it clears the ridge 2.5 m away.
	var lay: Dictionary = {
		"style": {"floor_height": 0.6, "chimney": [-1, 2], "roof": {"type": "gable", "axis": "x", "pitch": 38}},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBB", "BBBB", "BBBB", "BBBB", "BBBB"], "rooms": {"B": {}}}]}
	var built: Array = _batches(lay, &"test/chimney")
	var batches: Dictionary = built[1]
	var shafts: Array = batches["chimney_shaft_1m"]["xf"] if batches.has("chimney_shaft_1m") else []
	var top: Transform3D = batches["chimney_brick"]["xf"][0]
	var ridge: float = 0.6 + 2.0 * PoiLayout.STOREY + 2.5 * tan(deg_to_rad(38.0))
	assert_eq(top.origin.y, float(shafts.size()), "the chimney stands on its shaft")
	assert_gt(top.origin.y + 4.5, ridge + 0.3, "it clears the ridge")
	assert_lt(top.origin.y + 4.5, ridge + 1.5, "and stops there")
	for k: int in shafts.size():
		assert_almost_eq((shafts[k] as Transform3D).origin.y, float(k), 1e-4, "whole metres, so the brick courses run on")
