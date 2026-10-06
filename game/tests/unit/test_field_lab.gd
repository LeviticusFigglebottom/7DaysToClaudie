extends GutTest
## The Corvane Field Lab (DESIGN §11 "Tier 5", ADR-0046): the game's first tier-5 dungeon, a fenced compound random
## worlds stand far from the start. It is in the wilderness pool once, validates clean in every dressing (its route
## is completable in each), is the most layered dungeon in the game (held groups on every kind of trigger, traps,
## lock cues, keys and a keycard gating the deep rooms, the vault and its guardian, the shortcut out), opens its
## locked doors with keys it holds, rolls its loot from items that exist and pays out in the Program's quest items,
## tells its story in notes that resolve and name no town, backs its wall props onto walls, cuts its buried level
## under its own rooms, and its shell props match the kit rooms they wrap (tools/assetgen/blender_catalogs/props_lab.py
## SHELLS, mirrored below).

const ID: String = "corvane_field_lab"
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]
const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]
## The shells: [shell prop, prop id in the POI, rect [c0, r0, c1, r1], rotation, outside openings
## [side, index, kind] as the shell is cut in its own frame (props_lab.py SHELLS)].
const MODULE_OPENINGS: Array = [["E", 1, "door"], ["N", 2, "window"], ["N", 6, "window"], ["S", 2, "window"],
	["S", 6, "window"], ["W", 1, "window"]]
const SHELLS: Array = [
	["lab_module_shell", "shell_prep", [17, 23, 25, 26], 0],
	["lab_module_shell", "shell_micro", [17, 31, 25, 34], 0],
	["lab_module_shell", "shell_cold", [28, 23, 36, 26], 180],
	["lab_module_shell", "shell_admin", [28, 31, 36, 34], 180],
]
const DECON_OPENINGS: Array = [["S", 0, "door"], ["W", 1, "window"], ["E", 2, "window"]]

var _validator: PoiValidator = null


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validate() -> PoiValidator:
	if _validator == null:
		_validator = PoiValidator.validate(_def())
	return _validator


func _pool_entries() -> Array:
	var cfg: Dictionary = Content.config(&"world_gen")
	var out: Array = []
	for e: Variant in ((cfg.get("tuning", {}) as Dictionary).get("wilderness", {}) as Dictionary).get("pool", []):
		if str((e as Dictionary).get("poi", "")) == ID:
			out.append(e)
	return out


func test_tier_five_in_the_wilderness_pool_far_from_the_start() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "the field lab is content")
	if pd == null:
		return
	assert_eq(pd.tier, 5, "the field lab is tier 5")
	assert_true(pd.zoning.has("wilderness"), "zoned wilderness")
	assert_false(pd.zoning.has("residential") or pd.zoning.has("commercial") or pd.zoning.has("industrial"), "stays out of town lots")
	assert_true(pd.footprint.x >= 50 and pd.footprint.y >= 50, "a compound of 50 m and more a side")
	var entries: Array = _pool_entries()
	assert_eq(entries.size(), 1, "one wilderness pool entry")
	if entries.is_empty():
		return
	var pe: Dictionary = entries[0]
	assert_true(["remote", "forest"].has(str(pe.get("site", ""))), "a remote or forest site")
	assert_gte(int(pe.get("min_danger", 1)), 4, "far from the start (min_danger 4+)")
	assert_eq(int(pe.get("max", 0)), 1, "at most one per 16 km²")
	assert_eq(str(pe.get("access", "")), "track", "reached by a dirt track")
	# Drawn at least once in a 4 x 4 world at the default density: per_region x 16 >= 1.
	assert_gte(float(pe.get("per_region", 0.0)) * 16.0, 1.0, "a 4 x 4 world places one")
	assert_eq(WorldGenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json is valid with the entry")


func test_validates_clean_in_every_dressing() -> void:
	var v: PoiValidator = _validate()
	assert_eq(v.errors, PackedStringArray(), "the field lab validates in every option and combination")
	assert_eq(v.warnings, PackedStringArray(), "and without warnings")
	assert_gte(int(v.stats.get("variants", 0)), 16, "it varies between runs (alternatives)")


func test_route_is_reachable_end_to_end() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	assert_gte(l.route.size(), 20, "the longest route in the game")
	assert_eq(v.paths.size(), l.route.size(), "every leg of the route was walked")
	assert_eq(int(l.loot_room.get("level", 0)), -1, "the loot room is on the buried level")
	var deep: int = 0
	for wp: Dictionary in l.route:
		if int(wp["level"]) < 0:
			deep += 1
	assert_gt(deep, 4, "the route goes down into the buried level")


func test_is_a_full_tier_five_dungeon() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var shortcut_ok: bool = false
	for sc: Variant in l.shortcuts:
		shortcut_ok = shortcut_ok or str(l.opening(str((sc as Dictionary).get("opening", ""))).get("state", "")) == "locked_inside"
	assert_true(shortcut_ok, "a bolted shortcut out")
	var guardian: Dictionary = {}
	var groups: Dictionary = {}
	for s: Dictionary in l.sleepers:
		if bool(s["guardian"]):
			guardian = s
		elif str(s["group"]) != "":
			groups[str(s["group"])] = true
	assert_false(guardian.is_empty(), "a guardian on the vault")
	assert_true(["husk", "rammer", "blister"].has(str(guardian.get("enemy", ""))), "the guardian is a special Hollowed")
	assert_gte(groups.size(), 4, "four held groups or more")
	var kinds: Dictionary = {}
	var woken: Dictionary = {}
	for tg: Dictionary in l.triggers:
		if bool(tg["implicit"]):
			continue
		kinds[str(tg.get("on", ""))] = true
		woken[str(tg.get("group", ""))] = true
	for k: String in ["room", "opening", "pickup", "container", "trap"]:
		assert_true(kinds.has(k), "an ambush on a %s trigger" % k)
	for g: String in groups:
		assert_true(woken.has(g), "group %s has a trigger" % g)
	var trap_types: Dictionary = {}
	for t: Dictionary in l.traps:
		trap_types[str(t["type"])] = true
	assert_gte(trap_types.size(), 4, "traps of four kinds or more")
	var locks: Dictionary = {}
	for op: Dictionary in l.openings:
		if str(op.get("lock", "")) != "":
			locks[str(op["lock"])] = true
	assert_true(locks.has("vault"), "the specimen vault has a vault lock (ADR-0026)")
	assert_gte(locks.size(), 4, "lock cues of four kinds")
	var notes: int = 0
	for pk: Dictionary in l.pickups:
		if bool(pk.get("is_note", false)):
			notes += 1
	assert_gte(notes, 5, "the lab's last weeks in notes")


func test_keys_open_what_they_claim() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	var keyed: int = 0
	var card: bool = false
	for op: Dictionary in l.openings:
		if str(op.get("state", "")) != "locked":
			continue
		var key: String = str(op.get("key", ""))
		keyed += 1
		assert_true(key.begins_with("lab_"), "%s is locked with the lab's own key (%s)" % [op["id"], key])
		var it: ItemDef = Content.get_def(&"item", StringName(key)) as ItemDef
		assert_not_null(it, "key %s is an item" % key)
		if it != null:
			assert_eq(it.category, "key", "%s is a key" % key)
			card = card or it.model.contains("keycard")
		var held: int = 0
		for pk: Dictionary in l.pickups:
			if str(pk.get("item", "")) == key:
				held += 1
		assert_eq(held, 1, "the key to %s lies in the compound once" % op["id"])
		assert_true((v.stats.get("keys", []) as Array).has(key), "the route picks up %s before it needs it" % key)
	assert_gte(keyed, 4, "four locked doors on the way down")
	assert_true(card, "a keycard gates the containment suite")


func test_loot_items_and_notes_resolve() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var vault_tables: Array[String] = []
	for p: Dictionary in l.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		assert_not_null(pd, "prop %s exists" % p.get("prop"))
		if pd == null:
			continue
		var cid: String = str(p.get("container", pd.container))
		if cid == "":
			continue
		var cd: ContainerDef = Content.get_def(&"container", StringName(cid)) as ContainerDef
		assert_not_null(cd, "container %s exists" % cid)
		if cd != null:
			assert_not_null(Content.get_def(&"loot_table", cd.loot_table), "%s has its table" % cid)
			if int(p["level"]) == -1 and l.room_at(-1, p["cell"]) == "V":
				vault_tables.append(String(cd.loot_table))
	assert_true(vault_tables.has("lab_specimen_vault"), "the vault holds the specimen store")
	for pk: Dictionary in l.pickups:
		assert_not_null(Content.get_def(&"item", StringName(str(pk.get("item", "")))), "pickup %s is an item" % pk.get("item"))
		if bool(pk.get("is_note", false)):
			var nid: String = str(pk["item"]).trim_prefix("note_")
			var nd: ContentDef = Content.get_def(&"note", StringName(nid))
			assert_not_null(nd, "note %s exists" % nid)
			if nd != null:
				assert_gt(str(nd.get(&"body")).length(), 200, "note %s says something" % nid)
	for td: ContentDef in Content.all(&"loot_table"):
		if not String(td.id).begins_with("lab_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table: %s" % [td.id, ed.get("table")])
	# The trip pays: the vault always holds a sealed core, and the Program's items are worth the most in the game.
	var vt: LootTableDef = Content.loot_table(&"lab_specimen_vault")
	assert_not_null(vt, "the specimen vault table exists")
	if vt != null:
		var sure: bool = false
		for g: Dictionary in vt.guaranteed:
			sure = sure or g["item"] == &"bloom_core_canister"
		assert_true(sure, "the vault always holds a sealed Bloom core")
	var core: ItemDef = Content.item(&"bloom_core_canister")
	var drive: ItemDef = Content.item(&"lab_research_drive")
	assert_not_null(core, "the sealed core is an item")
	assert_not_null(drive, "the research drive is an item")
	if core != null and drive != null:
		assert_eq(core.category, "quest", "the core is a Program delivery")
		assert_true(core.has_tag("trade") and drive.has_tag("trade"), "both trade at the quartermaster")
		var best: int = 0
		for it: ContentDef in Content.all(&"item"):
			if String(it.id) != "bloom_core_canister":
				best = maxi(best, int((it as ItemDef).value))
		assert_gt(core.value, best, "a sealed core is worth more than anything else in the valley")
		assert_gt(drive.value, 120, "a research drive is worth more than a revolver")
	for e2: String in Content.errors():
		assert_false(e2.contains("lab_") or e2.contains("corvane"), e2)


func test_wall_props_back_onto_walls() -> void:
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
		assert_true(l.walls.has(key), "%s against %s at %s level %d backs onto a wall" % [p["prop"], side, p["cell"], p["level"]])
		if bool(p.get("rot_set", false)):
			assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
				"%s against %s at %s faces into the room" % [p["prop"], side, p["cell"]])
	assert_gt(against_walls, 40, "the rooms are dressed along their walls")


func test_buried_level_lies_under_the_block() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var cells: Array[Vector2i] = l.room_cells(-1)
	assert_gt(cells.size(), 200, "a buried level of 200 m² and more")
	for c: Vector2i in cells:
		assert_true(l.is_room(l.room_at(0, c)), "buried cell %s lies under a room of the block (ADR-0007)" % c)


func test_shells_match_the_rooms_they_wrap() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var shells: Array = SHELLS.duplicate()
	shells.append(["lab_decon_shell", "shell_decon", [26, 17, 31, 20], 0])
	for s: Array in shells:
		var rect: Array = s[2]
		var c0: int = rect[0]
		var r0: int = rect[1]
		var c1: int = rect[2]
		var r1: int = rect[3]
		var w: int = c1 - c0 + 1
		var d: int = r1 - r0 + 1
		for r: int in range(r0, r1 + 1):
			for c: int in range(c0, c1 + 1):
				assert_true(l.is_room(l.room_at(0, Vector2i(c, r))), "%s covers a built cell (%d, %d)" % [s[1], c, r])
		var found: bool = false
		for p: Dictionary in l.props:
			if str(p.get("pkey", "")) != str(s[1]):
				continue
			found = true
			assert_eq(str(p["prop"]), str(s[0]), "%s is a %s" % [s[1], s[0]])
			var pos: Vector2 = p["pos"]
			assert_almost_eq(pos.x, (c0 + c1 + 1) * 0.5, 0.01, "%s centred in x" % s[1])
			assert_almost_eq(pos.y, (r0 + r1 + 1) * 0.5, 0.01, "%s centred in z" % s[1])
			assert_almost_eq(float(p.get("y", 0.0)), -l.floor_height, 0.001, "%s stands on the pad" % s[1])
			assert_almost_eq(fposmod(float(p["rot"]), 360.0), float(s[3]), 0.01, "%s turned %d" % [s[1], s[3]])
		assert_true(found, "the POI places %s" % s[1])
		# The rectangle's outside openings, read in the shell's own frame (turned 180: sides swap, indices run back).
		var have: Array = []
		for op: Dictionary in l.openings:
			if int(op["level"]) != 0 or str(op["type"]) == "open":
				continue
			var cell: Vector2i = op["cell"]
			var side: String = SIDE_NAMES[int(op["side"])]
			if cell.x < c0 or cell.x > c1 or cell.y < r0 or cell.y > r1:
				continue
			var nb: Vector2i = cell + PoiLayout.DIRS[int(op["side"])]
			if nb.x >= c0 and nb.x <= c1 and nb.y >= r0 and nb.y <= r1:
				continue
			var idx: int = cell.x - c0 if side in ["N", "S"] else cell.y - r0
			if int(s[3]) == 180:
				side = SIDE_NAMES[(SIDE_NAMES.find(side) + 2) % 4]
				idx = (w - 1 - idx) if side in ["N", "S"] else (d - 1 - idx)
			have.append("%s%d:%s" % [side, idx, str(op["type"])])
		var want: Array = []
		for o: Array in (DECON_OPENINGS if str(s[0]) == "lab_decon_shell" else MODULE_OPENINGS):
			want.append("%s%d:%s" % [o[0], o[1], o[2]])
		# The decon unit's back (north) stands against the block: its airlock door there is the block's.
		if str(s[0]) == "lab_decon_shell":
			have = have.filter(func(x: String) -> bool: return not x.begins_with("N"))
		have.sort()
		want.sort()
		assert_eq(have, want, "%s is cut for exactly the outside openings of its rooms" % s[1])


func test_nothing_a_player_reads_names_a_town() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("lab_"):
			for t: String in TOWNS:
				assert_false(str(nd.get(&"body")).contains(t), "note %s names %s" % [nd.id, t])
