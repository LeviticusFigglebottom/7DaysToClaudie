extends GutTest
## Wilderness set pieces, round 4 (ADR-0053): the Kettle Creek backcountry ranger station
## (w4_backcountry_ranger_station), a tier-2 forest dungeon with a 15 m steel fire-weather tower in its
## compound. It validates clean in every dressing, its route is walked end to end, it is a full dungeon
## (bolted shortcut, guardian, two ambush groups on triggers, traps, lock cues, notes), its keys lie in
## the building before the doors that need them, its loot and notes resolve and name no town, its wall
## props back onto walls, the tower is climbed by real ladders landing on kit landings up to the cab,
## the cab shell matches the kit room it wraps (props_wild4_ranger.py SHELLS, mirrored below), the way
## into the compound is an open gap, and TraversalAudit finds nothing in the way on the route.

const ID: String = "w4_backcountry_ranger_station"
const TIER: int = 2
const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")

## Places a player could read a town's name in.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]
const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]
## The cab shell: [prop, rect [c0, r0, c1, r1], level, exterior openings [side, index, kind]].
const CAB: Array = ["w4_ranger_tower_cab", [26, 6, 27, 7], 4, [["N", 0, "window2"], ["S", 0, "window2"], ["W", 0, "window2"], ["E", 0, "window2"]]]

var _validated: PoiValidator = null


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validate() -> PoiValidator:
	if _validated == null:
		_validated = PoiValidator.validate(_def())
	return _validated


func test_tiered_and_zoned_for_the_wilderness() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "%s is content" % ID)
	if pd == null:
		return
	assert_eq(pd.tier, TIER, "tier")
	assert_true(pd.zoning.has("wilderness"), "zoned wilderness")
	assert_false(pd.zoning.has("residential") or pd.zoning.has("commercial"), "stays out of town lots")


func test_validates_clean_in_every_dressing() -> void:
	var v: PoiValidator = _validate()
	assert_eq(v.errors, PackedStringArray(), "validates")
	assert_eq(v.warnings, PackedStringArray(), "no warnings")
	assert_gt(int(v.stats.get("variants", 0)), 8, "varies between runs (alternatives)")


func test_route_is_reachable_end_to_end() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	assert_gt(l.route.size(), 6, "a route of beats")
	assert_eq(v.paths.size(), l.route.size(), "every leg of the route was walked")
	assert_eq(str(l.loot_room.get("room", "")), "T", "the loot is in the tower cab")
	assert_eq(int(l.loot_room.get("level", 0)), 4, "on top of the tower")


func test_is_a_full_dungeon() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var shortcut_ok: bool = false
	for sc: Variant in l.shortcuts:
		shortcut_ok = shortcut_ok or str(l.opening(str((sc as Dictionary).get("opening", ""))).get("state", "")) == "locked_inside"
	assert_true(shortcut_ok, "a bolted shortcut out")
	var guardian: bool = false
	var groups: Dictionary = {}
	for s: Dictionary in l.sleepers:
		guardian = guardian or bool(s["guardian"])
		if str(s["group"]) != "" and not bool(s["guardian"]):
			groups[str(s["group"])] = true
	assert_true(guardian, "a guardian on the loot")
	assert_gt(groups.size(), 1, "more than one ambush group")
	var real_triggers: int = 0
	var trap_triggers: int = 0
	for tg: Dictionary in l.triggers:
		if not bool(tg["implicit"]):
			real_triggers += 1
			if str(tg.get("on", "")) == "trap":
				trap_triggers += 1
	assert_gt(real_triggers, 2, "ambushes woken by triggers")
	if TIER >= 3:
		assert_gt(trap_triggers, 0, "a trap that sets off an ambush")
	assert_gt(l.traps.size(), 1, "sets traps")
	var kinds: Dictionary = {}
	for t: Dictionary in l.traps:
		kinds[str(t["type"])] = true
	for k: String in ["can_chime", "bear_trap", "creaky_floor"]:
		assert_true(kinds.has(k), "sets a %s" % k)
	var locks: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("lock", "")) != "":
			locks += 1
	assert_gt(locks, 1, "shows lock cues")
	var notes: int = 0
	for pk: Dictionary in l.pickups:
		if bool(pk.get("is_note", false)):
			notes += 1
	assert_gt(notes, 2, "tells its story in notes")


func test_keys_open_what_they_claim() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	var keyed: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("state", "")) != "locked":
			continue
		var key: String = str(op.get("key", ""))
		keyed += 1
		assert_true(key.begins_with("w4_ranger_"), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)), "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the building once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gt(keyed, 0, "locks the way to its loot behind a key")
	# The district key from the cab opens the gun safe in the office.
	var safe_key: String = ""
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "w4_ranger_gun_safe":
			safe_key = str(p.get("key", ""))
	assert_eq(safe_key, "w4_ranger_district_key", "the gun safe takes the district key")


func test_loot_and_notes_resolve() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	for p: Dictionary in l.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		assert_not_null(pd, "prop %s exists" % p.get("prop"))
		if pd == null:
			continue
		var cid: String = str(p.get("container", pd.container))
		if cid == "":
			continue
		var cd: ContentDef = Content.get_def(&"container", StringName(cid))
		assert_not_null(cd, "container %s exists" % cid)
		if cd != null:
			assert_not_null(Content.get_def(&"loot_table", StringName(str(cd.get(&"loot_table")))), "%s has its table" % cid)
	for pk: Dictionary in l.pickups:
		assert_not_null(Content.get_def(&"item", StringName(str(pk.get("item", "")))), "pickup %s is an item" % pk.get("item"))
		if bool(pk.get("is_note", false)):
			var nid: String = str(pk["item"]).trim_prefix("note_")
			var nd: ContentDef = Content.get_def(&"note", StringName(nid))
			assert_not_null(nd, "note %s exists" % nid)
			if nd != null:
				assert_gt(str(nd.get(&"body")).length(), 120, "note %s says something" % nid)
	for td: ContentDef in Content.all(&"loot_table"):
		if not String(td.id).begins_with("w4_ranger_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w4_ranger") or e2.contains("wild4_ranger"), e2)


func test_wall_props_face_into_the_room() -> void:
	const FACING: Dictionary = {"N": 0.0, "E": -90.0, "S": 180.0, "W": 90.0}
	var l: PoiLayout = PoiLayout.compile(_def())
	var against_walls: int = 0
	for p: Dictionary in l.props:
		var side: String = str(p.get("against", ""))
		if not FACING.has(side):
			continue
		against_walls += 1
		var e: Array = PoiLayout.side_edge(p["cell"], int(PoiLayout.SIDES[side]))
		var key: String = PoiLayout.edge_key(int(p["level"]), str(e[0]), e[1])
		# The tower's rails stand on the landings' open edges (an opening, not a wall).
		if str(p.get("prop", "")) == "town3_mast_rail":
			assert_true(l.openings.any(func(op: Dictionary) -> bool: return int(op["level"]) == int(p["level"]) \
				and PoiLayout.edge_key(int(op["level"]), str(PoiLayout.side_edge(op["cell"], int(op["side"]))[0]), PoiLayout.side_edge(op["cell"], int(op["side"]))[1]) == key),
				"rail at %s level %d stands on a landing's edge" % [p["cell"], p["level"]])
		else:
			assert_true(l.walls.has(key) or l.galleries.has(key),
				"%s against %s at %s level %d backs onto a wall" % [p["prop"], side, p["cell"], p["level"]])
		if bool(p.get("rot_set", false)):
			assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
				"%s against %s at %s faces into the room" % [p["prop"], side, p["cell"]])
	assert_gt(against_walls, 5, "dresses its walls")


func test_the_tower_is_climbed_by_ladders_to_the_cab() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var raw: Array = (_def().layout.get("ladders", []) as Array)
	assert_eq(raw.size(), 4, "four flights of ladders up the tower")
	for lad: Variant in raw:
		var ld: Dictionary = lad
		var li: int = int(ld.get("level", 0))
		var c: Vector2i = Vector2i(int(ld["at"][0]), int(ld["at"][1]))
		assert_true(bool(ld.get("hatch", false)), "the ladder at level %d goes up through a hatch" % li)
		assert_true(l.is_room(l.room_at(li, c)), "the ladder at level %d stands in a room" % li)
		assert_true(l.is_room(l.room_at(li + 1, c)), "the ladder at level %d lands on a room (a landing) above" % li)
	assert_true(l.is_room(l.room_at(4, Vector2i(26, 6))), "the cab is on level 4")
	# No climbing interacts anywhere: every climb is a ladder.
	for p: Dictionary in l.props:
		assert_false(str(p.get("interact", "")).contains("climb"), "no climb interact on %s" % p.get("prop"))


func test_the_cab_shell_matches_its_room() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var rect: Array = CAB[1]
	var li: int = CAB[2]
	for r: int in range(int(rect[1]), int(rect[3]) + 1):
		for c: int in range(int(rect[0]), int(rect[2]) + 1):
			assert_true(l.is_room(l.room_at(li, Vector2i(c, r))), "the cab covers a built cell (%d, %d)" % [c, r])
	var found: bool = false
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == str(CAB[0]):
			found = true
			var pos: Vector2 = p["pos"]
			assert_almost_eq(pos.x, (int(rect[0]) + int(rect[2]) + 1) * 0.5, 0.01, "centred in x")
			assert_almost_eq(pos.y, (int(rect[1]) + int(rect[3]) + 1) * 0.5, 0.01, "centred in z")
			assert_eq(int(p["level"]), li, "on the cab's level")
			assert_almost_eq(float(p.get("y", 0.0)), 0.0, 0.001, "on the cab's floor")
	assert_true(found, "places the cab shell")
	var have: Array = []
	for op: Dictionary in l.openings:
		if int(op["level"]) != li:
			continue
		have.append("%s%d:%s" % [SIDE_NAMES[int(op["side"])], (op["cell"] as Vector2i).x - int(rect[0]) if SIDE_NAMES[int(op["side"])] in ["N", "S"] else (op["cell"] as Vector2i).y - int(rect[1]), str(op["type"])])
	var want: Array = []
	for o: Array in CAB[3]:
		want.append("%s%d:%s" % [o[0], o[1], o[2]])
	have.sort()
	want.sort()
	assert_eq(have, want, "the shell is cut for exactly the cab's windows")


func test_the_compound_gate_is_an_open_way_in() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var gate: Dictionary = {}
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "w4_ranger_compound_gate":
			gate = p
	assert_false(gate.is_empty(), "the compound has its gate")
	assert_true(bool(gate.get("route_ok", false)), "the open gate is marked route_ok")
	var gp: Vector2 = gate.get("pos", Vector2.ZERO)
	# No fence panel stands in the gate's 4 m gap.
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) != "fence_chainlink_2m":
			continue
		var fp: Vector2 = p["pos"]
		assert_false(absf(fp.y - gp.y) < 0.5 and absf(fp.x - gp.x) < 2.9, "a fence panel at %s closes the gate" % fp)


func test_traversal_audit_finds_nothing_on_the_route() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var errors: Array = found.filter(func(f: Dictionary) -> bool: return str(f["severity"]) == "error")
	assert_eq(errors.size(), 0, "nothing in the way on the route: %s" % [errors.map(func(f: Dictionary) -> String: return TraversalAudit.line(ID, f))])


func test_nothing_a_player_reads_names_a_town() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("w4_ranger_"):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])
