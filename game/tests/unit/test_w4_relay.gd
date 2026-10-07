extends GutTest
## Forest set pieces, round 4 (ADR-0053): the Ridge Relay Hut (w4_ridge_relay_hut), an unmanned microwave
## relay hut on a forested ridge. It validates clean in every dressing, its route (the chimed shelter door,
## the bunk room and generator room ambushes, out through the compound's open gate, up the guyed tower by
## four real ladders to the top platform's key, back down to the keyed battery room and out its bolted
## yard door) is walked end to end, it is a full dungeon, its key lies on the top platform before the
## battery room needs it, its loot and notes resolve and name no town, its wall props (the platform
## railings among them) back onto walls, the tower is climbed platform by platform with no climb
## interaction, and the player's capsule finds nothing blocking its route (TraversalAudit).

const ID: String = "w4_ridge_relay_hut"
const TIER: int = 1
const PREFIX: String = "w4_relay_"
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
	assert_not_null(pd, "the relay hut is content")
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
	var kinds: Dictionary = {}
	for t: Dictionary in l.traps:
		kinds[str(t.get("type", ""))] = true
	for k: String in ["can_chime", "bear_trap", "shotgun"]:
		assert_true(kinds.has(k), "a %s" % k)
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


func test_the_tower_is_climbed_by_ladders_platform_by_platform() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_true(l.stairs.is_empty(), "no stairs: ladders are the way up")
	assert_gt(l.ladders.size(), 1, "at least two ladder flights")
	var by_level: Dictionary = {}
	for ld: Dictionary in l.ladders:
		assert_true(bool(ld["hatch"]), "the ladder from level %d goes up through a hatch" % int(ld["level"]))
		by_level[int(ld["level"])] = ld
	# One flight from every level to the next, from the ground to the top platform.
	var top: int = 0
	while by_level.has(top):
		top += 1
	assert_eq(top, 4, "ladders from the ground to the top platform")
	for li: int in range(1, top + 1):
		var cells: int = 0
		var open_edges: int = 0
		for r: int in range(2, 4):
			for c: int in range(13, 15):
				if l.is_room(l.room_at(li, Vector2i(c, r))):
					cells += 1
		for op: Dictionary in l.openings:
			if int(op["level"]) == li and str(op["type"]) == "open":
				open_edges += 1
		assert_eq(cells, 4, "level %d is a 2 x 2 platform" % li)
		assert_eq(open_edges, 8, "level %d's platform is open on every edge (railings, not walls)" % li)
	var mid_dishes: int = 0
	var top_dishes: int = 0
	var radio: bool = false
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "w4_relay_dish":
			if int(p["level"]) == 4:
				top_dishes += 1
			elif int(p["level"]) > 0:
				mid_dishes += 1
		radio = radio or (str(p.get("prop", "")) == "w4_relay_field_radio" and int(p["level"]) == 4)
	assert_gt(top_dishes, 0, "dishes on the top platform")
	assert_gt(mid_dishes, 0, "a dish part-way up")
	assert_true(radio, "a radio on the top platform")
	for pk: Dictionary in l.pickups:
		if str(pk.get("item", "")) == "w4_relay_battery_key":
			assert_eq(int(pk["level"]), 4, "the key is on the top platform")


func test_keys_open_what_they_claim() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	var keyed: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("state", "")) != "locked":
			continue
		var key: String = str(op.get("key", ""))
		keyed += 1
		assert_true(key.begins_with(PREFIX), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)) as ItemDef, "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the hut once" % op["id"])
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
		if not String(td.id).begins_with(PREFIX):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w4_relay") or e2.contains("wild4_relay"), e2)


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
	assert_gt(against_walls, 5, "the rooms and platforms are dressed")


func test_nothing_a_player_reads_names_a_town() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with(PREFIX):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])
	for idf: ContentDef in Content.all(&"item"):
		if String(idf.id).contains(PREFIX):
			for t: String in TOWNS:
				assert_false(str(idf.get(&"description")).contains(t), "item %s names %s" % [idf.id, t])


func test_the_player_walks_it_without_a_blocked_doorway() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var errors: Array[String] = []
	for f: Dictionary in found:
		if str(f.get("severity", "")) == "error":
			errors.append(TraversalAudit.line(ID, f))
	assert_eq(errors, [] as Array[String], "TraversalAudit finds nothing on the route")
