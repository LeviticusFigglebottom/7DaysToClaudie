extends GutTest
## The trestle tunnel (w4_trestle_tunnel, forest set pieces round 4, ADR-0053): an abandoned logging line's
## trestle over a dry ravine into a tunnel the Cordon blew. It validates clean in every dressing, its route is
## walked end to end (the ladder up a bent is climbed, the stair gate is the bolted way out), it is a full
## dungeon, its keys are found before the doors they open, its loot and notes resolve and name no town, its wall
## props back onto walls, and the player's own capsule gets along its route (TraversalAudit, ADR-0051).

const ID: String = "w4_trestle_tunnel"
const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")
## Places a player could read a town's name in.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]

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
	assert_eq(pd.tier, 2, "tier")
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
	assert_eq(str(l.loot_room.get("room", "")), "A", "the refuge niche is the loot room")


func test_the_deck_is_climbed_to_by_a_ladder_without_a_hatch() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(l.ladders.size(), 1, "one ladder")
	if l.ladders.size() != 1:
		return
	var lad: Dictionary = l.ladders[0]
	assert_false(bool(lad["hatch"]), "the bent's ladder has no hatch")
	assert_eq(l.room_at(int(lad["level"]) + 1, lad["landing"]), "D", "it lands on the trestle deck")
	assert_false(l.is_room(l.room_at(int(lad["level"]) + 1, lad["cell"])), "nothing is built over the ladder")
	for op: Dictionary in l.openings:
		assert_false(str(op.get("type", "")) == "climb", "no climb interact")


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
	for tg: Dictionary in l.triggers:
		if not bool(tg["implicit"]):
			real_triggers += 1
	assert_gt(real_triggers, 2, "ambushes wake on triggers")
	assert_gt(l.traps.size(), 1, "traps are set")
	var kinds: Dictionary = {}
	for t: Dictionary in l.traps:
		kinds[str(t["type"])] = true
	for k: String in ["weak_floor", "can_chime", "bear_trap"]:
		assert_true(kinds.has(k), "a %s trap" % k)
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


func test_keys_open_what_they_claim() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	var keyed: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("state", "")) != "locked":
			continue
		var key: String = str(op.get("key", ""))
		keyed += 1
		assert_true(key.begins_with("w4_trestle_"), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)), "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the building once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gt(keyed, 1, "the bulkhead and the niche are locked")


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
		if not String(td.id).begins_with("w4_trestle_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w4_trestle") or e2.contains("wild4_trestle"), e2)


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
		if String(nd.id).begins_with("w4_trestle_"):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])


func test_the_player_gets_along_the_route() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var bad: PackedStringArray = []
	for f: Dictionary in found:
		if str(f["severity"]) == "error":
			bad.append(TraversalAudit.line(ID, f))
		else:
			gut.p("traversal warning: " + TraversalAudit.line(ID, f))
	assert_eq(bad, PackedStringArray(), "nothing blocks the route or a doorway on it")
