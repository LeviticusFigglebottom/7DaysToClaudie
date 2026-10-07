extends GutTest
## Forest set pieces, round 4: the Cordon transport wreck (w4_cordon_plane_wreck). It validates clean in
## every dressing, its route is walked end to end, it is a full tier-3 dungeon, its sample key lies on the
## flight deck before the hatch it opens, its loot and notes resolve and name no town, its wall props back
## onto walls, its two fuselage shells match the kit rooms they wrap (the openings are cut in
## tools/assetgen/blender_catalogs/props_wild4_plane.py SHELLS, mirrored below), the flight deck is
## reached by a real ladder, and the player's capsule walks it without a blocked doorway (TraversalAudit).

const ID: String = "w4_cordon_plane_wreck"
const TIER: int = 3

## Places a player could read a town's name in.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]

## The shells: [shell prop, rect [c0, r0, c1, r1], storeys built over the whole rect, exterior openings
## [side, index, kind, level]] as the catalog cuts them.
const SHELLS: Array = [
	["w4_plane_fuselage_fwd", [15, 4, 18, 17], 1, [
		["S", 0, "half", 0], ["S", 1, "half", 0], ["S", 2, "half", 0], ["S", 3, "half", 0], ["W", 10, "door", 0],
		["N", 1, "window", 1], ["N", 2, "window", 1]]],
	["w4_plane_fuselage_tail", [6, 30, 12, 32], 1, [["S", 4, "door", 0]]],
]
const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]

const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")

var _validated: PoiValidator = null


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validate() -> PoiValidator:
	if _validated == null:
		_validated = PoiValidator.validate(_def())
	return _validated


func test_tiered_and_zoned_for_the_wilderness() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "the wreck is content")
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
	var loot: Dictionary = l.loot_room
	assert_true(l.is_room(l.room_at(int(loot.get("level", 0)), _any_cell(l, str(loot.get("room", "")), int(loot.get("level", 0))))),
		"a loot room")


func _any_cell(l: PoiLayout, ch: String, li: int) -> Vector2i:
	var lv: Dictionary = l.levels.get(li, {})
	for r: int in int(lv.get("d", 0)):
		for c: int in int(lv.get("w", 0)):
			if l.room_at(li, Vector2i(c, r)) == ch:
				return Vector2i(c, r)
	return Vector2i(-1, -1)


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
	assert_gt(real_triggers, 2, "ambushes wake on triggers")
	if TIER >= 3:
		assert_gt(trap_triggers, 0, "(tier 3) a trap sets off an ambush")
	assert_gt(l.traps.size(), 1, "traps")
	var locks: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("lock", "")) != "":
			locks += 1
	assert_gt(locks, 1, "lock cues")
	var notes: int = 0
	for pk: Dictionary in l.pickups:
		if bool(pk.get("is_note", false)):
			notes += 1
	assert_gt(notes, 2, "the story in notes")


func test_the_flight_deck_is_climbed_to_by_a_ladder() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(l.ladders.size(), 1, "one ladder")
	var ld: Dictionary = l.ladders[0]
	assert_eq(int(ld["level"]), 0, "it stands in the crew bay")
	assert_true(bool(ld["hatch"]), "up through a hatch")
	assert_eq(l.room_at(1, ld["cell"]), "C", "into the flight deck")
	assert_true(l.stairs.is_empty(), "no stairs: the ladder is the way up")


func test_keys_open_what_they_claim() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	var keyed: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("state", "")) != "locked":
			continue
		var key: String = str(op.get("key", ""))
		keyed += 1
		assert_true(key.begins_with("w4_plane_"), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)) as ItemDef, "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the wreck once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gt(keyed, 0, "the loot is behind a key")


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
		if not String(td.id).begins_with("w4_plane_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w4_plane") or e2.contains("wild4_plane"), e2)


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
		assert_true(l.walls.has(key) or l.galleries.has(key),
			"%s against %s at %s level %d backs onto a wall" % [p["prop"], side, p["cell"], p["level"]])
		if bool(p.get("rot_set", false)):
			assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
				"%s against %s at %s faces into the room" % [p["prop"], side, p["cell"]])
	assert_gt(against_walls, 5, "the cabins' walls are dressed")


func test_shells_match_the_rooms_they_wrap() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	for s: Array in SHELLS:
		var rect: Array = s[1]
		var c0: int = rect[0]
		var r0: int = rect[1]
		var c1: int = rect[2]
		var r1: int = rect[3]
		for li: int in int(s[2]):
			for r: int in range(r0, r1 + 1):
				for c: int in range(c0, c1 + 1):
					assert_true(l.is_room(l.room_at(li, Vector2i(c, r))), "%s covers a built cell (%d, %d) level %d" % [s[0], c, r, li])
		var found: bool = false
		for p: Dictionary in l.props:
			if str(p.get("prop", "")) == str(s[0]):
				found = true
				var pos: Vector2 = p["pos"]
				assert_almost_eq(pos.x, (c0 + c1 + 1) * 0.5, 0.01, "%s centred in x" % s[0])
				assert_almost_eq(pos.y, (r0 + r1 + 1) * 0.5, 0.01, "%s centred in z" % s[0])
				assert_almost_eq(float(p.get("y", 0.0)), -l.floor_height, 0.001, "%s stands on the pad" % s[0])
		assert_true(found, "places %s" % s[0])
		var have: Array = []
		for op: Dictionary in l.openings:
			var cell: Vector2i = op["cell"]
			var side: String = SIDE_NAMES[int(op["side"])]
			if cell.x < c0 or cell.x > c1 or cell.y < r0 or cell.y > r1:
				continue
			var on_edge: bool = (side == "N" and cell.y == r0) or (side == "S" and cell.y == r1) or (side == "W" and cell.x == c0) \
				or (side == "E" and cell.x == c1)
			if not on_edge:
				continue
			var idx: int = cell.x - c0 if side in ["N", "S"] else cell.y - r0
			have.append("%s%d:%s@%d" % [side, idx, str(op["type"]), int(op["level"])])
		var want: Array = []
		for o: Array in s[3]:
			want.append("%s%d:%s@%d" % [o[0], o[1], o[2], o[3]])
		have.sort()
		want.sort()
		assert_eq(have, want, "%s is cut for exactly the rooms' outside openings" % s[0])


func test_nothing_a_player_reads_names_a_town() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("w4_plane_"):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])


func test_the_player_walks_it_without_a_blocked_doorway() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var errors: Array[String] = []
	for f: Dictionary in found:
		if str(f.get("severity", "")) == "error":
			errors.append(TraversalAudit.line(ID, f))
	assert_eq(errors, [] as Array[String], "TraversalAudit finds nothing on the route")
