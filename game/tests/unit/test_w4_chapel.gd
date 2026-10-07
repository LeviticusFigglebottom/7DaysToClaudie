extends GutTest
## Forest set pieces, round 4 (ADR-0053): Shiloh Chapel (w4_overgrown_chapel), a pioneer timber chapel half taken
## back by the forest, its undercroft and the Teague vault dug into the bank behind it. It validates clean in every
## dressing, its route (in by a window, up the narthex ladder to the loft, through the broken nave floor into the
## undercroft, up the ladder into the vestry for the key, the vault's chained iron door, down the switchback into the
## buried vault and back up the pastor's bolted passage) is walked end to end, it is a full tier-2 dungeon, its key lies
## in the vestry before the vault door needs it, its loot and notes resolve and name no town, its wall props back onto
## walls, its climbs are real (ladders with hatches, stairs, a drop hole; no climb interaction) and the player's
## capsule finds nothing blocking its route.

const ID: String = "w4_overgrown_chapel"
const TIER: int = 2
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]
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
	var loot: Dictionary = l.loot_room
	var li: int = int(loot.get("level", 0))
	var found: bool = false
	for c: Vector2i in l.room_cells(li):
		found = found or l.room_at(li, c) == str(loot.get("room", ""))
	assert_true(found, "has a loot room")


func test_the_climbs_are_real() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	# Two hatch ladders: the narthex up to the choir loft, the vestry cellar up into the vestry.
	var hatches: Dictionary = {}
	for ld: Dictionary in l.ladders:
		assert_true(bool(ld["hatch"]), "ladder at %s climbs through a hatch" % ld["cell"])
		hatches[int(ld["level"])] = int(hatches.get(int(ld["level"]), 0)) + 1
	assert_eq(int(hatches.get(0, 0)), 1, "a ladder up to the choir loft")
	assert_eq(int(hatches.get(-1, 0)), 1, "a ladder up out of the undercroft into the vestry")
	# Three flights: the vault's switchback (-1 -> 0, -2 -> -1) and the pastor's passage (-2 -> -1).
	var flights: Dictionary = {}
	for s: Dictionary in l.stairs:
		flights[int(s["level"])] = int(flights.get(int(s["level"]), 0)) + 1
	assert_eq(int(flights.get(-1, 0)), 1, "a flight from the vault porch down to the stair's turn")
	assert_eq(int(flights.get(-2, 0)), 2, "two flights up from the buried vault")
	assert_eq(l.holes.size(), 1, "the broken nave floor drops into the undercroft")
	assert_true(bool((l.levels[-2] as Dictionary).get("buried", false)), "the vault runs on under the churchyard")
	var raw: String = JSON.stringify(_def().layout)
	assert_false(raw.contains("\"climb\""), "no climb interact")
	var door: Dictionary = l.opening("vault_door")
	assert_eq(str(door.get("state", "")), "locked", "the vault's iron door is locked")
	assert_eq(str(door.get("lock", "")), "chain", "chained")
	assert_eq(str(door.get("model", "")), "door_metal", "an iron door")


func test_the_vault_shell_matches_its_room() -> void:
	# The vault front (w4_chapel_mausoleum_front) wraps the vault porch: plan cols 11..12, rows 1..6, one storey,
	# its iron door on S at index 1 (props_wild4_chapel.py VAULT mirrors this).
	const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]
	var l: PoiLayout = PoiLayout.compile(_def())
	for r: int in range(1, 7):
		for c: int in range(11, 13):
			assert_eq(l.room_at(0, Vector2i(c, r)), "M", "the shell covers the vault porch at (%d, %d)" % [c, r])
	var found: bool = false
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "w4_chapel_mausoleum_front":
			found = true
			var pos: Vector2 = p["pos"]
			assert_almost_eq(pos.x, 12.0, 0.01, "centred in x")
			assert_almost_eq(pos.y, 4.0, 0.01, "centred in z")
			assert_almost_eq(float(p.get("y", 0.0)), -l.floor_height, 0.001, "stands on the pad")
	assert_true(found, "places the vault front")
	var have: Array = []
	for op: Dictionary in l.openings:
		var cell: Vector2i = op["cell"]
		if int(op["level"]) != 0 or cell.x < 11 or cell.x > 12 or cell.y < 1 or cell.y > 6:
			continue
		var side: String = SIDE_NAMES[int(op["side"])]
		var on_edge: bool = (side == "N" and cell.y == 1) or (side == "S" and cell.y == 6) or (side == "W" and cell.x == 11) \
			or (side == "E" and cell.x == 12)
		if on_edge:
			have.append("%s%d:%s" % [side, cell.x - 11 if side in ["N", "S"] else cell.y - 1, str(op["type"])])
	assert_eq(have, ["S1:door"], "the shell is cut for exactly the porch's iron door")


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
	assert_gt(real_triggers, 2, "ambushes woken on triggers")
	if TIER >= 3:
		assert_gt(trap_triggers, 0, "tier 3 layers a trap that sets off an ambush")
	assert_gt(l.traps.size(), 1, "sets traps")
	var kinds: Dictionary = {}
	for t: Dictionary in l.traps:
		kinds[str(t.get("type", ""))] = true
	for k: String in ["can_chime", "creaky_floor", "bear_trap"]:
		assert_true(kinds.has(k), "sets a %s" % k)
	var locks: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("lock", "")) != "":
			locks += 1
	assert_gt(locks, 1, "lock cues")
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
		assert_true(key.begins_with("w4_chapel_"), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)), "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the building once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gt(keyed, 0, "locks its loot behind a key")


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
		if not String(td.id).begins_with("w4_chapel_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w4_chapel") or e2.contains("wild4_chapel") or e2.contains(ID), e2)


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
	assert_gt(against_walls, 5, "dresses its walls")


func test_nothing_a_player_reads_names_a_town() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("w4_chapel_"):
			for t: String in TOWNS:
				assert_false(str(nd.get(&"body")).contains(t), "note %s names %s" % [nd.id, t])
				assert_false(str(nd.get(&"title")).contains(t), "note %s's title names %s" % [nd.id, t])


func test_traversal_audit_finds_nothing_on_the_route() -> void:
	var bad: PackedStringArray = []
	for f: Dictionary in await Runner.audit_one(self, _def(), ID):
		if str(f["severity"]) == "error":
			bad.append(TraversalAudit.line(ID, f))
	assert_eq(bad, PackedStringArray(), "nothing blocks the route or a doorway on it")
