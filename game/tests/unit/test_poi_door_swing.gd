extends GutTest
## Door leaves and furniture barricades keep halls and stairs clear (traversal bot poi_walk):
##  * PoiLayout.door_swing opens a leaf into the side with a metre to spare beside it: never across a
##    hall one cell deep, onto a stair flight or the cell it is climbed from, into the building
##    rather than out over the yard, away from a barricade; an authored "swing" wins.
##  * A furniture pile spills past a 1 m doorway only onto open floor (PoiLayout.barricade_pile,
##    PoiBuilder narrows it otherwise), and PoiValidator flags one across the only way onto a
##    flight's foot.


func _def(layout: Dictionary, id: String = "t") -> PoiDef:
	var raw: Dictionary = {"id": id, "name": "T", "tier": 2, "footprint": [16, 16]}
	raw.merge(layout, true)
	var d := PoiDef.new()
	var errs: PackedStringArray = d.parse(raw, &"poi", "test")
	assert_eq(errs, PackedStringArray(), "def parses")
	return d


## One storey: `plan` rows, rooms R (living), H (hallway), K (kitchen).
func _house(plan: Array, openings: Array) -> Dictionary:
	return {
		"levels": [{"level": 0, "plan": plan,
			"rooms": {"R": {"type": "living"}, "H": {"type": "hallway"}, "K": {"type": "kitchen"}}}],
		"openings": openings,
		"route": [{"at": [1, -2]}, {"at": [1, 0]}],
		"loot_room": {"room": "R", "level": 0}}


func _swing(d: Dictionary, op_id: String) -> float:
	var lay := PoiLayout.compile(_def(d))
	assert_eq(lay.errors, PackedStringArray(), "layout compiles")
	return lay.door_swing(lay.opening(op_id))


func test_a_leaf_opens_into_the_room_not_across_a_one_cell_hall() -> void:
	# The hall (row 2) is one cell deep: the default "a" (south) side would wall it off.
	var d: Dictionary = _house(["RRRR", "RRRR", "HHHH", "KKKK"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door"}])
	assert_eq(_swing(d, "d"), -1.0, "the leaf swings north, into the room")
	# Mirrored: the room is the "a" side, the default stands.
	d = _house(["KKKK", "HHHH", "RRRR", "RRRR"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door"}])
	assert_eq(_swing(d, "d"), 1.0, "the leaf swings south, into the room")
	# East / west walls: hall column 2 between two rooms.
	d = _house(["RRHK", "RRHK", "RRHK"], [{"id": "d", "at": [1, 1], "side": "E", "type": "door"}])
	assert_eq(_swing(d, "d"), -1.0, "the leaf swings west, into the room")
	# Through an "open" gap is still another room: the hall stays one cell deep (Larch Street).
	d = _house(["RRHK", "RRHK", "RRHK"], [{"id": "d", "at": [1, 1], "side": "E", "type": "door"},
		{"id": "gap", "at": [3, 1], "side": "W", "type": "open"}])
	assert_eq(_swing(d, "d"), -1.0, "a gap beyond the hall does not make it deeper")
	# Two rooms with room to spare: the default.
	d = _house(["RRRR", "RRRR", "KKKK", "KKKK"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door"}])
	assert_eq(_swing(d, "d"), 1.0, "both sides deep: the default")


func test_an_outside_door_opens_in_unless_the_inside_is_a_hall() -> void:
	var d: Dictionary = _house(["RRR", "RRR", "RRR"], [{"id": "front", "at": [1, 2], "side": "S", "type": "door"}])
	assert_eq(_swing(d, "front"), -1.0, "a front door on a south wall opens into the room")
	d = _house(["RRR", "RRR", "RRR"], [{"id": "back", "at": [1, 0], "side": "N", "type": "door"}])
	assert_eq(_swing(d, "back"), 1.0, "a back door on a north wall opens into the room")
	d = _house(["RRR", "HHH"], [{"id": "front", "at": [1, 1], "side": "S", "type": "door"}])
	assert_eq(_swing(d, "front"), 1.0, "into a one-cell hall it opens out over the yard")


func test_an_authored_swing_wins() -> void:
	var d: Dictionary = _house(["RRRR", "RRRR", "HHHH", "KKKK"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door", "swing": "S"}])
	assert_eq(_swing(d, "d"), 1.0, "swing S: over the hall, as authored")
	d = _house(["RRRR", "RRRR", "KKKK", "KKKK"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door", "swing": "N"}])
	assert_eq(_swing(d, "d"), -1.0, "swing N")
	d = _house(["RRRR", "RRRR", "KKKK", "KKKK"], [{"id": "d", "at": [1, 1], "side": "S", "type": "door", "swing": "E"}])
	var lay := PoiLayout.compile(_def(d))
	assert_eq(lay.errors.size(), 1, "a swing along the wall is an error")
	d = _house(["RRRR", "RRRR", "KKKK", "KKKK"], [{"id": "w", "at": [1, 1], "side": "S", "type": "window", "swing": "N"}])
	lay = PoiLayout.compile(_def(d))
	assert_eq(lay.errors.size(), 1, "only doors swing")


## Level 0: a stair house three cells wide (S) with a flight up its west column from (0, 4); the
## front door beside the flight's foot, a broken east window to climb in by.
func _stair_house(front: Dictionary) -> Dictionary:
	return {
		"levels": [
			{"level": 0, "plan": ["SSS", "SSS", "SSS", "SSS", "SSS"], "rooms": {"S": {"type": "hallway"}}},
			{"level": 1, "plan": ["LLL", "LLL", "LLL", "LLL", "LLL"], "rooms": {"L": {"type": "storage"}}}],
		"stairs": [{"level": 0, "at": [0, 4], "dir": "N"}],
		"openings": [front, {"id": "east_window", "at": [2, 2], "side": "E", "type": "window", "state": "broken"}],
		"props": [{"id": "crate", "prop": "metal_shelf", "at": [2, 0], "against": "N", "level": 1, "container": "toolbox"}],
		"route": [{"at": [4, 2]}, {"at": [1, 2]}, {"at": [2, 2], "level": 1}],
		"loot_room": {"room": "L", "level": 1}}


func test_a_leaf_keeps_off_a_flights_approach() -> void:
	# A flight up the west column from (0, 4), climbed from (0, 5); a side door on that cell's west
	# (outside) wall: its "a" side is the approach.
	var d: Dictionary = _stair_house({"id": "side", "at": [0, 5], "side": "W", "type": "door"})
	d["levels"][0]["plan"] = ["SSS", "SSS", "SSS", "SSS", "SSS", "SSS"]
	d["levels"][1]["plan"] = ["LLL", "LLL", "LLL", "LLL", "LLL", "LLL"]
	var lay := PoiLayout.compile(_def(d))
	assert_eq(lay.door_swing(lay.opening("side")), -1.0, "the leaf opens out, off the stair approach")
	d["stairs"] = []
	lay = PoiLayout.compile(_def(d))
	assert_eq(lay.door_swing(lay.opening("side")), 1.0, "with no stairs it opens in")


func test_a_barricaded_doors_leaf_opens_away_from_its_pile() -> void:
	# Interior furniture pile: on the "a" side; both sides deep, so the leaf opens to "b".
	var d: Dictionary = _house(["RRRR", "RRRR", "KKKK", "KKKK"], [
		{"id": "d", "at": [1, 1], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"}])
	assert_eq(_swing(d, "d"), -1.0, "away from the pile")
	# An exterior furniture pile stands inside: the leaf opens out.
	d = _house(["RRR", "RRR", "RRR"], [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"}])
	assert_eq(_swing(d, "front"), 1.0, "out, away from the pile inside")


func _bar(root: Node, id: String) -> PoiPieces.Breakable:
	for c: Node in root.get_children():
		if c is PoiPieces.Breakable and (c as PoiPieces.Breakable).piece_id == id:
			return c as PoiPieces.Breakable
	return null


func _bar_width(b: PoiPieces.Breakable) -> float:
	for c: Node in b.get_children():
		if c is CollisionShape3D:
			return ((c as CollisionShape3D).shape as BoxShape3D).size.x
	return 0.0


func test_a_furniture_pile_keeps_to_its_doorway_beside_a_stair_foot() -> void:
	var d: Dictionary = _stair_house({"id": "front", "at": [1, 4], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"})
	var lay := PoiLayout.compile(_def(d))
	var op: Dictionary = lay.opening("front")
	var pile: Dictionary = lay.barricade_pile(op, lay.barricade_face_hint(op))
	assert_eq(pile["cells"], [Vector2i(1, 4)] as Array[Vector2i], "the pile fills the cell inside the doorway")
	assert_false(bool(pile["wide"]), "the flight's foot beside it: no spill")
	var inst: PoiInstance = PoiBuilder.build(lay, &"test/pile_narrow")
	add_child_autofree(inst)
	var b: PoiPieces.Breakable = _bar(inst, "front_bar")
	assert_not_null(b)
	assert_lt(_bar_width(b), 1.0, "narrowed to the doorway's column")
	# The same door in an open room: full width.
	var d2: Dictionary = _house(["RRRRR", "RRRRR", "RRRRR"], [{"id": "front", "at": [2, 2], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"}])
	var lay2 := PoiLayout.compile(_def(d2))
	var op2: Dictionary = lay2.opening("front")
	assert_true(bool(lay2.barricade_pile(op2, lay2.barricade_face_hint(op2))["wide"]), "open floor either side")
	var inst2: PoiInstance = PoiBuilder.build(lay2, &"test/pile_wide")
	add_child_autofree(inst2)
	assert_almost_eq(_bar_width(_bar(inst2, "front_bar")), PoiLayout.PILE_W, 0.001, "full width")
	# Beside another doorway on the same wall: no spill.
	d2["openings"].append({"id": "next", "at": [3, 2], "side": "S", "type": "door"})
	lay2 = PoiLayout.compile(_def(d2))
	op2 = lay2.opening("front")
	assert_false(bool(lay2.barricade_pile(op2, lay2.barricade_face_hint(op2))["wide"]), "a doorway beside it")


func _errs(v: PoiValidator, needle: String) -> int:
	var n: int = 0
	for e: String in v.errors:
		if e.contains(needle):
			n += 1
	return n


func _warns(v: PoiValidator, needle: String) -> int:
	var n: int = 0
	for w: String in v.warnings:
		if w.contains(needle):
			n += 1
	return n


func test_the_validator_flags_a_pile_across_a_stair_foot() -> void:
	var d: Dictionary = _stair_house({"id": "front", "at": [1, 4], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"})
	var v: PoiValidator = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "the only way onto the foot of the stairs"), 1, "the climb starts behind the pile")
	# Boards nailed on the inside fill no cell.
	d = _stair_house({"id": "front", "at": [1, 4], "side": "S", "type": "door", "state": "barricaded", "barricade_on": "S"})
	v = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "the only way onto the foot of the stairs"), 0, "boards")
	assert_eq(_errs(v, "furniture barricade"), 0)
	# A pile on the flight itself.
	d = _stair_house({"id": "front", "at": [0, 2], "side": "W", "type": "door", "state": "barricaded", "barricade": "furniture"})
	v = PoiValidator.validate(_def(d))
	assert_gt(_errs(v, "stands on a stair flight"), 0, "a pile on the steps")


func test_a_route_through_a_pile_is_fine_while_it_can_be_broken() -> void:
	# A hall one cell deep, entered from its west end; a piled door off it stands in the hall.
	var d: Dictionary = _house(["RRRRR", "HHHHH"], [
		{"id": "west", "at": [0, 1], "side": "W", "type": "door"},
		{"id": "d", "at": [2, 0], "side": "S", "type": "door", "state": "barricaded", "barricade": "furniture"}])
	d["route"] = [{"at": [-2, 1]}, {"at": [0, 1]}, {"at": [4, 1]}]
	var v: PoiValidator = PoiValidator.validate(_def(d))
	assert_eq(_warns(v, "only reached through a furniture barricade (d)"), 1, "the player smashes the pile")
	assert_eq(_errs(v, "furniture barricade"), 0, "breakable: no error")
	# A way round through the room: the pile is not in the way.
	d["openings"].append({"id": "gap_w", "at": [0, 0], "side": "S", "type": "open"})
	d["openings"].append({"id": "gap_e", "at": [4, 0], "side": "S", "type": "open"})
	v = PoiValidator.validate(_def(d))
	assert_eq(_warns(v, "only reached through a furniture barricade"), 0, "a way round")
