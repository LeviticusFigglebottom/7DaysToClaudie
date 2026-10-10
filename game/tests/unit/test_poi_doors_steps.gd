extends GutTest
## Player report 3 (Build #67): broken doors hang open, raised doorways get steps, and stairs keep
## clear of doors and walls.
##  * A broken door's leaf hangs open off its top hinge (Door.broken_open, from its id), visible and
##    with no collision; a door smashed in play swings there.
##  * Every exterior doorway of every authored building, and of a sample of generated ones, whose
##    sill stands more than PoiBuilder.STOOP_MIN_RISE above the yard has steps (PoiBuilder.stoops),
##    and the builder lays them.
##  * PoiValidator: no doorway onto a flight past its foot or onto the well above it (other than at
##    its head), no wall across a climb, no door leaf swung into the steps (PoiLayout.door_swing
##    turns it away); the route never walks over a flight's upper steps.

const Generator := preload("res://src/poi/building_generator.gd")

## Generated buildings per template the stoop and stair checks sample.
const GEN_SAMPLE: int = 6


func _def(layout: Dictionary, id: String = "t") -> PoiDef:
	var raw: Dictionary = {"id": id, "name": "T", "tier": 2, "footprint": [16, 16]}
	raw.merge(layout, true)
	var d := PoiDef.new()
	var errs: PackedStringArray = d.parse(raw, &"poi", "test")
	assert_eq(errs, PackedStringArray(), "def parses")
	return d


## One room on a 0.6 m foundation with a back door and a front door (the cottage of the report).
func _cottage(back_state: String = "broken", floor_height: float = 0.6) -> Dictionary:
	return {
		"style": {"floor_height": floor_height},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {"type": "living"}}}],
		"openings": [
			{"id": "front_door", "at": [1, 2], "side": "S", "type": "door", "state": "closed"},
			{"id": "back_door", "at": [2, 0], "side": "N", "type": "door", "state": back_state}],
		"props": [{"id": "shelf", "prop": "metal_shelf", "at": [3, 1], "against": "E"}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}],
		"loot_room": {"room": "A", "level": 0}}


func _doors(root: Node) -> Array[PoiPieces.Door]:
	var out: Array[PoiPieces.Door] = []
	for c: Node in root.get_children():
		if c is PoiPieces.Door:
			out.append(c as PoiPieces.Door)
	return out


func _door(root: Node, id: String) -> PoiPieces.Door:
	for d: PoiPieces.Door in _doors(root):
		if d.op_id == id:
			return d
	return null


## Angle (radians) the leaf stands off the wall's plane.
func _leaf_angle(d: PoiPieces.Door) -> float:
	var along: Vector3 = d.pivot.transform.basis * Vector3.RIGHT
	return absf(atan2(along.z, absf(along.x)))


func _leaf_mesh(d: PoiPieces.Door) -> MeshInstance3D:
	for c: Node in d.pivot.get_children():
		if c is MeshInstance3D and c != d.lock_mesh:
			return c as MeshInstance3D
	return null


# --- broken doors ----------------------------------------------------------------------------------

func test_a_broken_door_hangs_open_and_visible() -> void:
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(_cottage())), &"test/cottage")
	add_child_autofree(inst)
	var d: PoiPieces.Door = _door(inst, "back_door")
	assert_not_null(d, "the back door is built")
	if d == null:
		return
	assert_true(d.is_broken())
	assert_between(d.broken_open, PoiBuilder.BROKEN_OPEN.x, PoiBuilder.BROKEN_OPEN.y)
	assert_gt(_leaf_angle(d), deg_to_rad(65.0), "the leaf hangs well open, out of the doorway")
	assert_true(d.leaf_shape.disabled, "nothing to bump into")
	var mi: MeshInstance3D = _leaf_mesh(d)
	assert_not_null(mi)
	assert_true(mi != null and mi.visible, "the leaf is drawn (hanging), not hidden")
	# It sags off its top hinge: the latch end lower than the hinge, the corner on the floor.
	var latch: Vector3 = d.pivot.transform * Vector3(d.leaf_local.origin.x * 2.0, 0.0, 0.0)
	assert_almost_eq(latch.y, 0.0, 0.01, "latch corner rests on the floor")
	assert_gt(d.pivot.position.y, 0.02, "hinge foot lifted off it")
	assert_eq(d.interact_text(null), "", "a broken door has no open/close")
	var shut: PoiPieces.Door = _door(inst, "front_door")
	assert_almost_eq(_leaf_angle(shut), 0.0, 0.001, "a closed door is shut")


func test_the_pose_is_fixed_per_door_and_needs_no_save() -> void:
	var a: float = PoiBuilder.broken_open_for(&"pell/lot3", "back_door")
	assert_eq(a, PoiBuilder.broken_open_for(&"pell/lot3", "back_door"), "same door, same pose")
	var spread: Dictionary = {}
	for i: int in 20:
		spread[snappedf(PoiBuilder.broken_open_for(StringName("pell/lot%d" % i), "back_door"), 0.01)] = true
	assert_gt(spread.size(), 5, "doors hang at different angles")


func test_a_door_smashed_in_play_swings_open() -> void:
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(_cottage("closed"))), &"test/cottage2")
	add_child_autofree(inst)
	var d: PoiPieces.Door = _door(inst, "back_door")
	assert_almost_eq(_leaf_angle(d), 0.0, 0.001)
	d.smash()
	for i: int in 60:
		d._process(0.05)
	assert_true(d.is_broken())
	assert_gt(_leaf_angle(d), deg_to_rad(65.0), "it swung in and hangs open")
	assert_true(_leaf_mesh(d).visible)
	assert_eq(str(inst.piece_state("back_door", "")), "broken", "saved as broken (its pose follows from its id)")


func test_every_broken_door_of_every_building_is_posed_open() -> void:
	var n: int = 0
	for id: StringName in [&"haldane_place", &"pell_ranger_station", &"timberline_motel"]:
		var pd: PoiDef = Content.get_def(&"poi", id) as PoiDef
		if pd == null:
			continue
		var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), StringName("test/" + String(id)))
		add_child_autofree(inst)
		for d: PoiPieces.Door in _doors(inst):
			if d.is_broken():
				n += 1
				assert_gt(_leaf_angle(d), deg_to_rad(65.0), "%s %s hangs open" % [id, d.op_id])
				assert_true(_leaf_mesh(d).visible, "%s %s is drawn" % [id, d.op_id])
	assert_gt(n, 3, "broken doors found")


# --- steps up to raised doorways -------------------------------------------------------------------

## Exterior ground-floor doorways (per metre) whose sill is above the yard, as [op id, outside cell].
func _raised_doorways(lay: PoiLayout) -> Array:
	var out: Array = []
	var li0: int = 0 if lay.levels.has(0) else lay.level_ids.front()
	var deck: Dictionary = PoiBuilder.porch_cells(lay)
	for op: Dictionary in lay.openings:
		var t: String = str(op["type"])
		if int(op["level"]) != li0 or not (t.begins_with("door") or t == "open"):
			continue
		for pair: Array in PoiLayout.opening_edges(op):
			var a_in: bool = lay.is_room(lay.room_at(li0, pair[0]))
			if a_in == lay.is_room(lay.room_at(li0, pair[1])):
				continue
			var outside: Vector2i = pair[1] if a_in else pair[0]
			if lay.level_y(li0) - (lay.level_y(li0) if deck.has(outside) else 0.0) > PoiBuilder.STOOP_MIN_RISE:
				out.append([str(op["id"]), outside])
	return out


func _assert_steps(pd: PoiDef, what: String) -> int:
	var lay := PoiLayout.compile(pd)
	var have: Dictionary = {}
	for st: Dictionary in PoiBuilder.stoops(lay):
		have["%s@%s" % [st["op"], st["outside"]]] = st
		assert_almost_eq(float(st["rise"]), lay.level_y(0 if lay.levels.has(0) else lay.level_ids.front()), 0.001, "%s: sized to the rise" % what)
		assert_true(float(st["run"]) >= 1.0 and float(st["rise"]) / float(st["run"]) <= PoiBuilder.STEP_UNIT_RISE + 0.001,
			"%s: no steeper than the porch step" % what)
	var raised: Array = _raised_doorways(lay)
	for r: Array in raised:
		assert_true(have.has("%s@%s" % [r[0], r[1]]), "%s: doorway '%s' (out to %s) has steps up to it" % [what, r[0], r[1]])
	return raised.size()


func test_every_raised_exterior_doorway_has_steps() -> void:
	var raised: int = 0
	for pd: PoiDef in Content.all(&"poi"):
		raised += _assert_steps(pd, String(pd.id))
	for t: Variant in Content.all(&"building_template"):
		for i: int in GEN_SAMPLE:
			var g: PoiDef = Generator.generate(t, Ids.hash64("steps:%s:%d" % [(t as Resource).get("id"), i]))
			if g != null:
				raised += _assert_steps(g, "%s seed %d" % [g.id, i])
	gut.p("%d raised doorways checked" % raised)
	assert_gt(raised, 50, "plenty of raised doorways in the sample")


func test_low_sills_get_no_steps_and_the_builder_lays_them() -> void:
	assert_eq(PoiBuilder.stoops(PoiLayout.compile(_def(_cottage("closed", 0.15)))).size(), 0, "a 0.15 m sill is stepped over")
	var lay := PoiLayout.compile(_def(_cottage("closed", 0.6)))
	var st: Array = PoiBuilder.stoops(lay)
	assert_eq(st.size(), 2, "front and back doors")
	var b: PoiBuilder = PoiBuilder.start(lay, &"test/stoops")
	while b.next_phase() != "roof":
		b.step()
	var sp: Dictionary = PoiBuilder.stoop_piece(str(lay.style.get("exterior", "siding_white")), 0.6, 1)
	assert_eq(str(sp["piece"]), "stoop_wood_3_1m", "a sided cottage's 0.6 m sill: three wooden steps")
	assert_eq(((b._batches.get(sp["piece"], {}) as Dictionary).get("xf", []) as Array).size(), 2, "both laid")
	var back: Dictionary = st[0] if st[0]["op"] == "back_door" else st[1]
	assert_eq(int(back["side"]), 0, "the back door's steps run out north")
	while not b.step():
		pass
	add_child_autofree(b.root)


# --- stairs, doors and walls -----------------------------------------------------------------------

## Two storeys: a hall (H, two columns) with a flight in its west column rising north from row 4,
## rooms either side; upstairs a landing over the hall.
func _two_storey(openings: Array, stair_at: Array = [2, 4]) -> Dictionary:
	return {
		"levels": [
			{"level": 0, "plan": ["AAHHBB", "AAHHBB", "AAHHBB", "AAHHBB", "AAHHBB", "AAHHBB"],
				"rooms": {"A": {"type": "living"}, "B": {"type": "kitchen"}, "H": {"type": "hallway"}}},
			{"level": 1, "plan": ["CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD"],
				"rooms": {"C": {"type": "bedroom"}, "D": {"type": "bedroom"}, "L": {"type": "hallway"}}}],
		"stairs": [{"level": 0, "at": stair_at, "dir": "N"}],
		"openings": [{"id": "front", "at": [3, 5], "side": "S", "type": "door"}] + openings,
		"props": [{"id": "shelf", "prop": "metal_shelf", "at": [0, 0], "against": "N", "level": 1}],
		"route": [{"at": [3, 7]}, {"at": [3, 3]}, {"at": [3, 0], "level": 1}, {"at": [1, 1], "level": 1}],
		"loot_room": {"room": "C", "level": 1}}


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


func test_a_clean_two_storey_validates() -> void:
	var v: PoiValidator = PoiValidator.validate(_def(_two_storey([
		{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"},
		{"id": "c_door", "at": [2, 0], "side": "W", "type": "door", "level": 1}])))
	assert_eq(v.errors, PackedStringArray())


func test_doorways_onto_a_flight() -> void:
	# Past the foot (the flight is (2,4) .. (2,1)): an error, at any of a 2 m opening's metres.
	var v: PoiValidator = PoiValidator.validate(_def(_two_storey([{"id": "a_door", "at": [1, 2], "side": "E", "type": "door"}])))
	assert_eq(_errs(v, "'a_door'"), 1, "a door beside the flight's third step")
	v = PoiValidator.validate(_def(_two_storey([{"id": "wide", "at": [1, 0], "side": "E", "type": "door2"}])))
	assert_eq(_errs(v, "'wide'"), 1, "a double door's second metre meets the second step")
	# Beside the first step: a warning (passable along the foot jamb).
	v = PoiValidator.validate(_def(_two_storey([{"id": "a_door", "at": [1, 4], "side": "E", "type": "door"},
		{"id": "a_door2", "at": [1, 5], "side": "E", "type": "door"}])))
	assert_eq(_errs(v, "'a_door'"), 0)
	assert_eq(_warns(v, "'a_door'"), 1, "beside the first step")
	# Upstairs onto the well, but not at the head (the landing (2,0) to the head (2,1)).
	v = PoiValidator.validate(_def(_two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"},
		{"id": "c_door", "at": [1, 2], "side": "E", "type": "door", "level": 1}])))
	assert_eq(_errs(v, "'c_door'"), 1, "a door onto the well drops the player onto the flight")
	v = PoiValidator.validate(_def(_two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"},
		{"id": "c_door", "at": [1, 0], "side": "E", "type": "door", "level": 1}])))
	assert_eq(_errs(v, "'c_door'"), 0, "a door off the landing")


func test_walls_across_a_climb() -> void:
	# The upstairs hall split between the landing (2,0) and the head (2,1).
	var d: Dictionary = _two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"}])
	d["levels"][1]["plan"] = ["CCMMDD", "CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD"]
	d["levels"][1]["rooms"]["M"] = {"type": "hallway"}
	var v: PoiValidator = PoiValidator.validate(_def(d))
	assert_gt(_errs(v, "stands across the climb"), 0, "a wall between the head and the landing")
	# A door there is the way off the top: fine.
	d["openings"].append({"id": "top", "at": [2, 1], "side": "N", "type": "door", "level": 1})
	v = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "stands across the climb"), 0, "a door at the head")
	# Upstairs over the first step a wall leaves 2.25 m of headroom: fine.
	d = _two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"}])
	d["levels"][1]["plan"] = ["CCLLDD", "CCLLDD", "CCLLDD", "CCLLDD", "CCMMDD", "CCMMDD"]
	d["levels"][1]["rooms"]["M"] = {"type": "hallway"}
	v = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "stands across the climb"), 0, "headroom over the first step")


func test_a_door_swings_away_from_a_flight() -> void:
	# A door at the foot of a flight rising south from (2,1), from the cell behind it (2,0): an edge's
	# leaf swings south / east by default, into "a" = the foot.
	var d: Dictionary = _two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"},
		{"id": "foot_door", "at": [2, 1], "side": "N", "type": "door"}], [2, 1])
	d["stairs"][0]["dir"] = "S"
	d["levels"][0]["plan"] = ["AAKHBB", "AAHHBB", "AAHHBB", "AAHHBB", "AAHHBB", "AAHHBB"]
	d["levels"][0]["rooms"]["K"] = {"type": "storage"}
	d["route"] = [{"at": [3, 7]}, {"at": [3, 3]}]
	var lay := PoiLayout.compile(_def(d))
	var op: Dictionary = lay.opening("foot_door")
	assert_eq(lay.door_swing(op), -1.0, "the leaf swings north, off the flight's foot")
	assert_eq(lay.door_swing(lay.opening("a_door")), 1.0, "others keep the default")
	var v: PoiValidator = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "swings open into the stair flight"), 0)
	var inst: PoiInstance = PoiBuilder.build(lay, &"test/swing")
	add_child_autofree(inst)
	var door: PoiPieces.Door = _door(inst, "foot_door")
	door._target = 1.0
	for i: int in 40:
		door._process(0.05)
	var far: Vector3 = door.pivot.transform * Vector3(door.leaf_local.origin.x * 2.0, 0.0, 0.0)
	assert_lt(far.z, -0.5, "opened, the leaf stands north of its wall, off the steps")


func test_the_route_never_walks_over_the_steps() -> void:
	# The upstairs bedroom D is only reachable over the well: no floor there.
	var d: Dictionary = _two_storey([{"id": "a_door", "at": [1, 5], "side": "E", "type": "door"},
		{"id": "c_door", "at": [1, 0], "side": "E", "type": "door", "level": 1}])
	d["route"] = [{"at": [3, 7]}, {"at": [2, 3]}]
	var v: PoiValidator = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "on a stair flight"), 1, "a waypoint on the steps")
	d["route"] = [{"at": [3, 7]}, {"at": [3, 3]}, {"at": [2, 3], "level": 1}]
	v = PoiValidator.validate(_def(d))
	assert_eq(_errs(v, "over a stairwell"), 1, "a waypoint over the well")


func test_generated_buildings_keep_stairs_clear() -> void:
	var bad: PackedStringArray = []
	var needles: Array[String] = ["opens onto the stair flight", "opens onto the well", "stands across the climb",
		"swings open into the stair flight", "on a stair flight", "over a stairwell"]
	# Authored buildings fail test_poi's test_every_poi_validates on any of these errors (with every
	# alternative); generated ones retry until clean, so this catches one that ran out of retries.
	var defs: Array = []
	for t: Variant in Content.all(&"building_template"):
		for i: int in GEN_SAMPLE:
			var g: PoiDef = Generator.generate(t, Ids.hash64("stairs:%s:%d" % [(t as Resource).get("id"), i]))
			if g != null:
				defs.append(g)
	for pd: PoiDef in defs:
		var v: PoiValidator = PoiValidator.validate(pd)
		for e: String in v.errors:
			for n: String in needles:
				if e.contains(n):
					bad.append("%s: %s" % [pd.id, e])
	assert_eq(bad, PackedStringArray(), "no stair problems")


func test_stoop_piece_by_finish_rise_and_width() -> void:
	var c: Dictionary = PoiBuilder.stoop_piece("brick_red", 0.45, 2)
	assert_eq(str(c["piece"]), "stoop_concrete_2_2m", "brick: a concrete stoop, 0.45 m = two steps, 2 m wide")
	assert_almost_eq(float(c["sy"]) * PoiBuilder.STOOP_RISE * 2.0, 0.45, 0.001, "scaled to the rise")
	assert_almost_eq(float(c["depth"]), (PoiBuilder.STOOP_LANDING + PoiBuilder.STOOP_TREAD) * float(c["sz"]), 0.001, "landing + a step")
	assert_eq(str(PoiBuilder.stoop_piece("log_chinked", 0.25, 1)["piece"]), "stoop_wood_1_1m", "a log wall: one wooden step")
	var tall: Dictionary = PoiBuilder.stoop_piece("siding_white", 0.9, 1)
	assert_eq(int(tall["steps"]), 3, "never more than three steps")
	assert_almost_eq(float(tall["sz"]), float(tall["sy"]), 0.001, "a taller rise lengthens the run as much")
	for k: String in ["wood", "concrete"]:
		for n: int in [1, 2, 3]:
			for w: int in [1, 2]:
				var m: Mesh = PoiParts.kit_mesh("stoop_%s_%d_%dm" % [k, n, w])
				assert_not_null(m, "stoop_%s_%d_%dm has a mesh (model or stand-in)" % [k, n, w])
				if m != null:
					var aabb: AABB = m.get_aabb()
					assert_almost_eq(aabb.size.x, float(w), 0.12, "%s %d %dm: width" % [k, n, w])
					assert_true(aabb.position.z > -0.06 and aabb.end.z > 0.25, "%s %d %dm: runs out along +Z from the wall" % [k, n, w])


## Owner report 4, item 8: a flight whose foot stood off a wall reached the landing's height 8 cm
## past its head, 6 cm under the slab's edge there, and the capsule stopped dead a step short of
## the top (four buildings needed a jump). Every flight of every authored building, and of a sample
## of generated ones, meets its landing's floor at the head.
func test_every_flight_meets_its_landing() -> void:
	var defs: Array = []
	for v: Variant in Content.all(&"poi"):
		defs.append(v)
	for t: Variant in Content.all(&"building_template"):
		for i: int in 2:
			var g: PoiDef = Generator.generate(t, Ids.hash64("ramp:%s:%d" % [(t as Resource).get("id"), i]))
			if g != null:
				defs.append(g)
	var bad: PackedStringArray = []
	var flights: int = 0
	for pd: PoiDef in defs:
		var lay: PoiLayout = PoiLayout.compile(pd)
		if not lay.errors.is_empty() or lay.stairs.is_empty():
			continue
		var inst: PoiInstance = PoiBuilder.build(lay, StringName("test/ramp/" + String(pd.id)))
		add_child(inst)
		await get_tree().physics_frame
		await get_tree().physics_frame
		var space: PhysicsDirectSpaceState3D = inst.get_world_3d().direct_space_state
		for s: Dictionary in lay.stairs:
			flights += 1
			var li: int = int(s["level"])
			var cells: Array = s["cells"]
			var d := Vector3(PoiLayout.DIRS[int(s["dir"])].x, 0, PoiLayout.DIRS[int(s["dir"])].y)
			var head_edge: Vector3 = lay.cell_center(li, cells.back()) + d * 0.5
			var top: float = lay.level_y(li + 1)
			for back: float in [0.04, 0.12]:
				var at: Vector3 = inst.global_transform * (head_edge - d * back)
				var q := PhysicsRayQueryParameters3D.create(at + Vector3.UP * (top + 1.0 - at.y), at + Vector3.UP * (top - 0.5 - at.y))
				var hit: Dictionary = space.intersect_ray(q)
				var y: float = (inst.global_transform.affine_inverse() * (hit["position"] as Vector3)).y if not hit.is_empty() else -INF
				# The ramp's slope (3 m over 4) a little short of the edge, never a lip under it.
				if absf(y - (top - back * 0.75)) > 0.03:
					bad.append("%s flight from %s (level %d): %.2f m short of its head the ramp is at %.3f, %.3f expected" % [
						pd.id, s["cell"], li, back, y, top - back * 0.75])
		remove_child(inst)
		inst.free()
	assert_gt(flights, 10, "flights checked")
	assert_eq(bad, PackedStringArray(), "every flight reaches its landing's height at its head")
