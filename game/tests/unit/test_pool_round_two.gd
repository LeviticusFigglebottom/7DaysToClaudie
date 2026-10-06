extends GutTest
## Pool round 2 (DESIGN §11 "Pool buildings"): five more set pieces for random towns, filling the
## industrial gap - a pawn and gun shop, a cannery, a water works, a quarry office and a veterans'
## post. Each is zoned, tiered and sized for the random generator's lots (and the organic planner's,
## ADR-0040), a fitting lot picks it, it validates clean in every dressing, it is a full dungeon, its
## wall props face into the room, its loot rolls from items that exist, and nothing a player reads
## in it names a town.

const Lots := preload("res://src/poi/lot_picker.gd")

## id -> the lot it fits: [zoning, tier, lot width, lot depth] (world_gen.json tuning.towns.lot).
const ROUND_TWO: Dictionary = {
	"hollis_pawn_gun": ["commercial", 3, 28, 32],
	"northfork_cannery": ["industrial", 3, 26, 26],
	"water_works": ["industrial", 2, 26, 26],
	"ridgeline_quarry_office": ["industrial", 2, 26, 26],
	"vfw_post": ["civic", 2, 32, 32],
}

## Places a player could read a town's name in: the set pieces' notes.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]


func _fw(lots: Array) -> FrameworkDef:
	var fw := FrameworkDef.new()
	assert_eq(fw.parse({"id": "round_two_fw", "size": [400, 400], "tier_range": [1, 3], "lots": lots}, &"framework", "test"), PackedStringArray())
	return fw


func _def(id: String) -> PoiDef:
	return Content.get_def(&"poi", StringName(id)) as PoiDef


func test_zoned_tiered_and_sized_for_town_lots() -> void:
	for id: String in ROUND_TWO:
		var pd: PoiDef = _def(id)
		assert_not_null(pd, "%s is content" % id)
		if pd == null:
			continue
		var want: Array = ROUND_TWO[id]
		assert_true(pd.zoning.has(str(want[0])), "%s is zoned %s" % [id, want[0]])
		assert_eq(pd.tier, int(want[1]), "%s tier" % id)
		assert_true(pd.footprint.x <= int(want[2]) and pd.footprint.y <= int(want[3]),
			"%s footprint %s fits a %dx%d %s lot" % [id, pd.footprint, want[2], want[3], want[0]])
		assert_false(pd.zoning.has("residential"), "%s stays off residential streets" % id)


func test_a_fitting_lot_picks_each() -> void:
	for id: String in ROUND_TWO:
		var want: Array = ROUND_TWO[id]
		var t: int = int(want[1])
		var fw: FrameworkDef = _fw([{"id": "lot", "rect": [10, 10, int(want[2]), int(want[3])], "zoning": [want[0]], "facing": "S",
			"tier": [t, t], "pool": "authored"}])
		var picked: int = -1
		for ws: int in range(1, 1025):
			if String(Lots.resolve(fw, "town", ws)[0].get("def_id", "")) == id:
				picked = ws
				break
		assert_gt(picked, 0, "a %s tier-%d lot picks %s for some world seed" % [want[0], t, id])


func test_each_validates_clean_in_every_dressing() -> void:
	for id: String in ROUND_TWO:
		var v: PoiValidator = PoiValidator.validate(_def(id))
		assert_eq(v.errors, PackedStringArray(), "%s validates" % id)
		assert_eq(v.warnings, PackedStringArray(), "%s has no warnings" % id)
		assert_gt(int(v.stats.get("variants", 0)), 8, "%s varies between runs (alternatives)" % id)


func test_each_is_a_full_dungeon() -> void:
	for id: String in ROUND_TWO:
		var l: PoiLayout = PoiLayout.compile(_def(id))
		var shortcut_ok: bool = false
		for sc: Variant in l.shortcuts:
			shortcut_ok = shortcut_ok or str(l.opening(str((sc as Dictionary).get("opening", ""))).get("state", "")) == "locked_inside"
		assert_true(shortcut_ok, "%s has a bolted shortcut out" % id)
		var guardian: bool = false
		var groups: Dictionary = {}
		for s: Dictionary in l.sleepers:
			guardian = guardian or bool(s["guardian"])
			if str(s["group"]) != "" and not bool(s["guardian"]):
				groups[str(s["group"])] = true
		assert_true(guardian, "%s has a guardian on the loot" % id)
		assert_gt(groups.size(), 0, "%s holds an ambush group" % id)
		var real_triggers: int = 0
		for tg: Dictionary in l.triggers:
			if not bool(tg["implicit"]):
				real_triggers += 1
		assert_gt(real_triggers, 0, "%s wakes its ambush on a trigger" % id)
		assert_gt(l.traps.size(), 1, "%s sets traps" % id)
		var keyed: bool = false
		var locks: int = 0
		for op: Dictionary in l.openings:
			if str(op.get("lock", "")) != "":
				locks += 1
			keyed = keyed or str(op.get("key", "")).begins_with("town4_")
		assert_gt(locks, 1, "%s shows lock cues" % id)
		assert_true(keyed, "%s locks its loot room with its own key" % id)
		var notes: int = 0
		for pk: Dictionary in l.pickups:
			if bool(pk.get("is_note", false)):
				notes += 1
		assert_gt(notes, 1, "%s tells its story in notes" % id)


func test_wall_props_face_into_the_room() -> void:
	const FACING: Dictionary = {"N": 0.0, "E": -90.0, "S": 180.0, "W": 90.0}
	for id: String in ROUND_TWO:
		for p: Dictionary in PoiLayout.compile(_def(id)).props:
			var side: String = str(p.get("against", ""))
			if FACING.has(side):
				assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
					"%s: %s against %s at %s faces into the room" % [id, p["prop"], side, p["cell"]])


func test_their_containers_roll_real_items() -> void:
	for cd: ContentDef in Content.all(&"container"):
		if not String(cd.id).begins_with("town4_"):
			continue
		assert_not_null(Content.get_def(&"loot_table", StringName(str(cd.get(&"loot_table")))), "%s has its table" % cd.id)
	for e: String in Content.errors():
		assert_false(e.contains("town4"), e)


func test_nothing_a_player_reads_names_a_town() -> void:
	for id: String in ROUND_TWO:
		var pd: PoiDef = _def(id)
		for t: String in TOWNS:
			assert_false(pd.display_name.contains(t), "%s: its name says %s" % [id, t])
			assert_false(pd.story.contains(t), "%s: its story says %s" % [id, t])
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("town4_"):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])
