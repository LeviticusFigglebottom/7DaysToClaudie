extends GutTest
## The pool buildings (DESIGN §11 "Pool buildings"): five authored set pieces random towns pick for their
## lots (LotPicker, ADR-0030). Each is zoned, tiered and sized for the random generator's lots, a lot that
## fits it can pick it, it validates clean in every dressing, it is a full dungeon (locked front, a
## shortcut out, an ambush on a trigger, traps, a guardian on the loot, notes), and Larch Street's
## residential lots never draw one.

const Lots := preload("res://src/poi/lot_picker.gd")

## id -> the lot it was sized for: [zoning, tier, lot width, lot depth] (data/config/world_gen.json
## tuning.towns.lot: commercial 28 x 32, civic 32 x 32, industrial 26 x 26 on the back street).
const POOL: Dictionary = {
	"suds_spin_laundromat": ["commercial", 1, 28, 32],
	"hollowmere_grocery": ["commercial", 2, 28, 32],
	"bracken_lumber_feed": ["industrial", 3, 26, 26],
	"pell_county_library": ["civic", 2, 32, 32],
	"khlw_valley_radio": ["civic", 2, 32, 32],
}


func _fw(lots: Array, tier_range: Array = [1, 3]) -> FrameworkDef:
	var fw := FrameworkDef.new()
	var errs: PackedStringArray = fw.parse({"id": "pool_test_fw", "size": [400, 400], "tier_range": tier_range, "lots": lots}, &"framework", "test")
	assert_eq(errs, PackedStringArray())
	return fw


func test_pool_buildings_exist_zoned_tiered_and_sized_for_town_lots() -> void:
	for id: String in POOL:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		assert_not_null(pd, "%s is content" % id)
		if pd == null:
			continue
		var want: Array = POOL[id]
		assert_true(pd.zoning.has(str(want[0])), "%s is zoned %s" % [id, want[0]])
		assert_eq(pd.tier, int(want[1]), "%s tier" % id)
		assert_true(pd.footprint.x <= int(want[2]) and pd.footprint.y <= int(want[3]),
			"%s footprint %s fits a %dx%d %s lot" % [id, pd.footprint, want[2], want[3], want[0]])
		assert_false(pd.zoning.has("residential"), "%s stays off residential streets (Larch Street)" % id)


func test_a_fitting_lot_picks_each_pool_building() -> void:
	for id: String in POOL:
		var want: Array = POOL[id]
		var t: int = int(want[1])
		var fw: FrameworkDef = _fw([{"id": "lot", "rect": [10, 10, int(want[2]), int(want[3])], "zoning": [want[0]], "facing": "S",
			"tier": [t, t], "pool": "authored"}])
		var picked: int = -1
		for ws: int in range(1, 257):
			var res: Array[Dictionary] = Lots.resolve(fw, "town", ws)
			assert_eq(str(res[0]["kind"]), "authored", "an authored-pool lot always holds a set piece")
			if String(res[0].get("def_id", "")) == id:
				picked = ws
				break
		assert_gt(picked, 0, "a %s tier-%d lot of %dx%d picks %s for some world seed" % [want[0], t, want[2], want[3], id])
		if picked > 0:
			var again: Array[Dictionary] = Lots.resolve(fw, "town", picked)
			assert_eq(String(again[0]["def_id"]), id, "the same world seed picks it again")
			var pd: PoiDef = Lots.def_for(again[0])
			assert_not_null(pd)


func test_a_lot_too_small_or_out_of_tier_never_picks_them() -> void:
	for id: String in POOL:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		var want: Array = POOL[id]
		var t: int = int(want[1])
		var other_tier: int = 3 if t < 3 else 1
		var fw: FrameworkDef = _fw([
			{"id": "narrow", "rect": [0, 0, pd.footprint.x - 1, pd.footprint.y], "zoning": [want[0]], "facing": "S", "tier": [t, t]},
			{"id": "shallow", "rect": [60, 0, pd.footprint.x, pd.footprint.y - 1], "zoning": [want[0]], "facing": "S", "tier": [t, t]},
			{"id": "tier", "rect": [120, 0, 40, 40], "zoning": [want[0]], "facing": "S", "tier": [other_tier, other_tier]},
			{"id": "zoning", "rect": [180, 0, 40, 40], "zoning": ["rural"], "facing": "S", "tier": [t, t]}])
		for ws: int in [1, 2, 3, 4, 5, 6, 7, 8]:
			for res: Dictionary in Lots.resolve(fw, "town", ws):
				assert_ne(String(res.get("def_id", "")), id, "%s stays off lot %s" % [id, res["lot"].get("id")])


func test_each_validates_clean_in_every_dressing() -> void:
	for id: String in POOL:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		var v: PoiValidator = PoiValidator.validate(pd)
		assert_eq(v.errors, PackedStringArray(), "%s validates" % id)
		assert_eq(v.warnings, PackedStringArray(), "%s has no warnings" % id)
		assert_gt(int(v.stats.get("variants", 0)), 8, "%s varies between runs (alternatives)" % id)


func test_each_is_a_full_dungeon() -> void:
	for id: String in POOL:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		var l: PoiLayout = PoiLayout.compile(pd)
		var locked_front: bool = false
		var shortcut_ok: bool = false
		for op: Dictionary in l.openings:
			if int(op["level"]) != 0 or not str(op["type"]).begins_with("door"):
				continue
			var w: Dictionary = l.walls.get(PoiLayout.edge_key(0, str(op["axis"]), op["edge"]), {})
			if bool(w.get("exterior", false)) and str(op["state"]) in ["locked", "locked_inside", "barricaded"]:
				locked_front = true
		for sc: Variant in l.shortcuts:
			var op2: Dictionary = l.opening(str((sc as Dictionary).get("opening", "")))
			shortcut_ok = shortcut_ok or str(op2.get("state", "")) == "locked_inside"
		assert_true(locked_front, "%s has a locked or barred front" % id)
		assert_true(shortcut_ok, "%s has a bolted shortcut out" % id)
		var groups: Dictionary = {}
		var guardian: bool = false
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
		var notes: int = 0
		var locks: int = 0
		for pk: Dictionary in l.pickups:
			if bool(pk.get("is_note", false)):
				notes += 1
		for op3: Dictionary in l.openings:
			if str(op3.get("lock", "")) != "":
				locks += 1
		assert_gt(notes, 1, "%s tells its story in notes" % id)
		assert_gt(locks, 1, "%s shows lock cues" % id)


func test_wall_props_face_into_the_room() -> void:
	# PoiLayout gives every compiled prop a "rot" (0 when none is authored), so PoiBuilder never applies
	# the facing "against" implies: a prop against a side wall needs its turn spelled out, or a dryer row
	# stands sideways and a cooler case pokes through the wall.
	const FACING: Dictionary = {"N": 0.0, "E": -90.0, "S": 180.0, "W": 90.0}
	for id: String in POOL:
		var l: PoiLayout = PoiLayout.compile(Content.get_def(&"poi", StringName(id)) as PoiDef)
		for p: Dictionary in l.props:
			var side: String = str(p.get("against", ""))
			if FACING.has(side):
				assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
					"%s: %s against %s at %s faces into the room" % [id, p["prop"], side, p["cell"]])


func test_larch_street_still_builds_its_own_houses() -> void:
	var fw: FrameworkDef = Content.get_def(&"framework", &"pell_crossing")
	for ws: int in [4471, 1, 90210, 7]:
		for res: Dictionary in Lots.resolve(fw, "pell_crossing", ws):
			assert_false(POOL.has(String(res.get("def_id", ""))), "Pell's Crossing never picks a pool building (lot %s)" % res["lot"].get("id"))
