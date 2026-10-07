extends GutTest
## Wilderness set pieces, round 5: the Silver Run fish hatchery (w5_fish_hatchery), a state trout hatchery on a forest
## creek the Cordon used as a water-testing post. It validates clean in every dressing, its route (round by the creek, over
## a pony wall into the raceway shed, out again to the intake dam, up the ladder onto the catwalk for the lab key, the
## manager's cottage for the house key, the hatch house's deadbolt, the Cordon's field lab, the chiller's padlock and the
## bolted back door) is walked end to end, it is a full tier-2 dungeon, its keys are found before the doors need them, its
## loot and notes resolve and name no town, its wall props back onto walls, its climbs are real (a hatch ladder, vaults
## over pony walls; no climb interaction) and the player's capsule finds nothing blocking its route.

const ID: String = "w5_fish_hatchery"
const TIER: int = 2
const PREFIX: String = "w5_hatchery_"
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
	# One hatch ladder up the dam's abutment onto the intake catwalk (level 1, no room under it).
	assert_eq(l.ladders.size(), 1, "one ladder")
	for ld: Dictionary in l.ladders:
		assert_true(bool(ld["hatch"]), "the ladder at %s climbs through a hatch" % ld["cell"])
		assert_eq(int(ld["level"]), 0, "from the creek bank")
		assert_eq(l.room_at(1, ld["cell"]), "W", "up onto the catwalk")
	var on_route: int = 0
	for wp: Dictionary in l.route:
		if int(wp.get("level", 0)) == 1:
			on_route += 1
	assert_gt(on_route, 1, "the route walks the catwalk")
	# The raceway shed's creek side is pony walls the route vaults (sill 1.0 m over a 0.15 m slab).
	var halves: int = 0
	for op: Dictionary in l.openings:
		if str(op["type"]) == "half":
			halves += 1
	assert_gt(halves, 10, "an open-sided shed")
	assert_eq(l.stairs.size(), 0, "no stairs")
	var raw: String = JSON.stringify(_def().layout)
	assert_false(raw.contains("\"climb\""), "no climb interact")
	var door: Dictionary = l.opening("chiller_door")
	assert_eq(str(door.get("state", "")), "locked", "the chiller is locked")
	assert_eq(str(door.get("lock", "")), "padlock", "padlocked")
	assert_eq(str(l.opening("house_door").get("lock", "")), "deadbolt", "the hatch house door is deadbolted")
	assert_eq(str(l.opening("shed_lab_door").get("state", "")), "barricaded", "the lab is boarded against the shed")


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
		assert_true(key.begins_with(PREFIX), "%s is locked with its own key (%s)" % [op["id"], key])
		assert_not_null(Content.get_def(&"item", StringName(key)), "key %s is an item" % key)
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the building once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gt(keyed, 1, "locks the hatch house and the loot behind keys")


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
		assert_false(e2.contains("w5_hatchery") or e2.contains("wild5_hatchery") or e2.contains(ID), e2)


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
		if String(nd.id).begins_with(PREFIX):
			for t: String in TOWNS:
				assert_false(str(nd.get(&"body")).contains(t), "note %s names %s" % [nd.id, t])
				assert_false(str(nd.get(&"title")).contains(t), "note %s's title names %s" % [nd.id, t])
	for idef: ContentDef in Content.all(&"item"):
		if String(idef.id).begins_with(PREFIX) or String(idef.id).begins_with("note_" + PREFIX):
			for t: String in TOWNS:
				assert_false(str(idef.get(&"description")).contains(t), "item %s names %s" % [idef.id, t])


func test_traversal_audit_finds_nothing_on_the_route() -> void:
	var bad: PackedStringArray = []
	for f: Dictionary in await Runner.audit_one(self, _def(), ID):
		if str(f["severity"]) == "error":
			bad.append(TraversalAudit.line(ID, f))
	assert_eq(bad, PackedStringArray(), "nothing blocks the route or a doorway on it")
