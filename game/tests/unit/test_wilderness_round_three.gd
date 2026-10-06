extends GutTest
## Wilderness set pieces, round 3 (DESIGN §11 "Wilderness set pieces (random worlds)"): four dungeons random
## worlds place outside towns from the wilderness pool - Camp Tamarack, Elk Ridge Lodge, the Cordon
## quarantine camp and the Haldane Place. Each is in the pool on the sites the brief gives it, validates clean
## in every dressing (its route is completable in every one), is a full dungeon, opens its locked doors with
## keys it holds, rolls its loot from items that exist, tells its story in notes that resolve and name no
## town, backs its wall props onto walls facing into the room, and its shell props match the kit rooms
## they wrap (their openings are cut in tools/assetgen/blender_catalogs/props_wild3.py SHELLS, mirrored
## below).

const ROUND_THREE: Dictionary = {
	"camp_tamarack": {"tier": 2, "sites": ["lake_shore", "waterside"]},
	"elk_ridge_lodge": {"tier": 3, "sites": ["forest", "remote"]},
	"cordon_quarantine_camp": {"tier": 3, "sites": ["roadside", "remote"]},
	"haldane_place": {"tier": 2, "sites": ["forest"]},
}

## Places a player could read a town's name in.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]

## The shells: poi -> [shell prop, rect [c0, r0, c1, r1], storeys, exterior openings [side, index, kind, level]]
## as the catalog cuts them (props_wild3.py SHELLS / LODGE_OPENINGS).
const SHELLS: Array = [
	["elk_ridge_lodge", "w3_lodge_shell", [4, 4, 19, 13], 2, [
		["S", 3, "door2", 0], ["S", 1, "window_tall", 0], ["S", 6, "window_tall", 0],
		["W", 1, "window_tall", 0], ["W", 8, "window_tall", 0], ["N", 2, "window_tall", 0], ["N", 6, "window_tall", 0],
		["N", 12, "door", 0], ["N", 10, "window", 0], ["N", 14, "window", 0], ["E", 2, "window", 0], ["E", 5, "door", 0],
		["S", 14, "door", 0], ["S", 13, "window", 0], ["S", 9, "window", 0],
		["N", 10, "window", 1], ["N", 14, "window", 1], ["E", 2, "window", 1], ["E", 6, "window", 1], ["E", 9, "window", 1],
		["S", 14, "window", 1], ["S", 10, "window", 1], ["S", 8, "window", 1]]],
	["cordon_quarantine_camp", "w3_reefer_shell", [34, 4, 36, 11], 1, [["S", 1, "door", 0], ["E", 5, "door", 0]]],
	["cordon_quarantine_camp", "w3_command_trailer_shell", [5, 8, 8, 16], 1, [
		["E", 6, "door", 0], ["E", 2, "window", 0], ["W", 2, "window", 0], ["W", 6, "window", 0], ["N", 1, "window", 0]]],
]
const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]


## One validation per building, shared by the tests below (Camp Tamarack's 25 dressings take most of a minute).
var _validated: Dictionary = {}


func _def(id: String) -> PoiDef:
	return Content.get_def(&"poi", StringName(id)) as PoiDef


func _validate(id: String) -> PoiValidator:
	if not _validated.has(id):
		_validated[id] = PoiValidator.validate(_def(id))
	return _validated[id]


func _pool() -> Array:
	var cfg: Dictionary = Content.config(&"world_gen")
	return ((cfg.get("tuning", {}) as Dictionary).get("wilderness", {}) as Dictionary).get("pool", [])


func test_tiered_zoned_and_in_the_wilderness_pool() -> void:
	var pool: Array = _pool()
	for id: String in ROUND_THREE:
		var pd: PoiDef = _def(id)
		assert_not_null(pd, "%s is content" % id)
		if pd == null:
			continue
		var want: Dictionary = ROUND_THREE[id]
		assert_eq(pd.tier, int(want["tier"]), "%s tier" % id)
		assert_true(pd.zoning.has("wilderness"), "%s is zoned wilderness" % id)
		assert_false(pd.zoning.has("residential") or pd.zoning.has("commercial"), "%s stays out of town lots" % id)
		var entries: int = 0
		for e: Variant in pool:
			var pe: Dictionary = e
			if str(pe.get("poi", "")) != id:
				continue
			entries += 1
			assert_true((want["sites"] as Array).has(str(pe.get("site", ""))), "%s sits on a %s site" % [id, want["sites"]])
			assert_gt(float(pe.get("per_region", 0.0)), 0.0, "%s is drawn" % id)
			assert_true(int(pe.get("min_danger", 1)) <= 5, "%s can appear" % id)
		assert_eq(entries, 1, "%s has one wilderness pool entry" % id)


func test_each_validates_clean_in_every_dressing() -> void:
	for id: String in ROUND_THREE:
		var v: PoiValidator = _validate(id)
		assert_eq(v.errors, PackedStringArray(), "%s validates" % id)
		assert_eq(v.warnings, PackedStringArray(), "%s has no warnings" % id)
		assert_gt(int(v.stats.get("variants", 0)), 8, "%s varies between runs (alternatives)" % id)


func test_each_route_is_reachable_end_to_end() -> void:
	for id: String in ROUND_THREE:
		var v: PoiValidator = _validate(id)
		var l: PoiLayout = v.layout
		assert_gt(l.route.size(), 6, "%s has a route of beats" % id)
		assert_eq(v.paths.size(), l.route.size(), "%s: every leg of its route was walked" % id)
		var loot: Dictionary = l.loot_room
		assert_true(l.is_room(l.room_at(int(loot.get("level", 0)), _any_cell(l, str(loot.get("room", "")), int(loot.get("level", 0))))),
			"%s has a loot room" % id)


func _any_cell(l: PoiLayout, ch: String, li: int) -> Vector2i:
	var lv: Dictionary = l.levels.get(li, {})
	for r: int in int(lv.get("d", 0)):
		for c: int in int(lv.get("w", 0)):
			if l.room_at(li, Vector2i(c, r)) == ch:
				return Vector2i(c, r)
	return Vector2i(-1, -1)


func test_each_is_a_full_dungeon() -> void:
	for id: String in ROUND_THREE:
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
		assert_gt(groups.size(), 1, "%s holds more than one ambush group" % id)
		var real_triggers: int = 0
		var trap_triggers: int = 0
		for tg: Dictionary in l.triggers:
			if not bool(tg["implicit"]):
				real_triggers += 1
				if str(tg.get("on", "")) == "trap":
					trap_triggers += 1
		assert_gt(real_triggers, 2, "%s wakes its ambushes on triggers" % id)
		if int(ROUND_THREE[id]["tier"]) >= 3:
			assert_gt(trap_triggers, 0, "%s (tier 3) layers a trap that sets off an ambush" % id)
		assert_gt(l.traps.size(), 1, "%s sets traps" % id)
		var locks: int = 0
		for op: Dictionary in l.openings:
			if str(op.get("lock", "")) != "":
				locks += 1
		assert_gt(locks, 1, "%s shows lock cues" % id)
		var notes: int = 0
		for pk: Dictionary in l.pickups:
			if bool(pk.get("is_note", false)):
				notes += 1
		assert_gt(notes, 2, "%s tells its story in notes" % id)


func test_keys_open_what_they_claim() -> void:
	for id: String in ROUND_THREE:
		var v: PoiValidator = _validate(id)
		var l: PoiLayout = v.layout
		var keyed: int = 0
		for op: Dictionary in l.openings:
			if str(op.get("state", "")) != "locked":
				continue
			var key: String = str(op.get("key", ""))
			keyed += 1
			assert_true(key.begins_with("w3_"), "%s: %s is locked with its own key (%s)" % [id, op["id"], key])
			var it: ItemDef = Content.get_def(&"item", StringName(key)) as ItemDef
			assert_not_null(it, "%s: key %s is an item" % [id, key])
			var held: int = 0
			for pk: Dictionary in l.pickups:
				if str(pk.get("item", "")) == key:
					held += 1
			assert_eq(held, 1, "%s: the key to %s lies in the building once" % [id, op["id"]])
			assert_true((v.stats.get("keys", []) as Array).has(key), "%s: the route picks up %s before it needs it" % [id, key])
		assert_gt(keyed, 0, "%s locks its loot behind a key" % id)


func test_loot_and_notes_resolve() -> void:
	for id: String in ROUND_THREE:
		var l: PoiLayout = PoiLayout.compile(_def(id))
		for p: Dictionary in l.props:
			var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
			assert_not_null(pd, "%s: prop %s exists" % [id, p.get("prop")])
			if pd == null:
				continue
			var cid: String = str(p.get("container", pd.container))
			if cid == "":
				continue
			var cd: ContentDef = Content.get_def(&"container", StringName(cid))
			assert_not_null(cd, "%s: container %s exists" % [id, cid])
			if cd != null:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(cd.get(&"loot_table")))), "%s: %s has its table" % [id, cid])
		for pk: Dictionary in l.pickups:
			assert_not_null(Content.get_def(&"item", StringName(str(pk.get("item", "")))), "%s: pickup %s is an item" % [id, pk.get("item")])
			if bool(pk.get("is_note", false)):
				var nid: String = str(pk["item"]).trim_prefix("note_")
				var nd: ContentDef = Content.get_def(&"note", StringName(nid))
				assert_not_null(nd, "%s: note %s exists" % [id, nid])
				if nd != null:
					assert_gt(str(nd.get(&"body")).length(), 120, "%s: note %s says something" % [id, nid])
	for td: ContentDef in Content.all(&"loot_table"):
		if not String(td.id).begins_with("w3_"):
			continue
		for e: Variant in td.get(&"entries"):
			var ed: Dictionary = e
			if str(ed.get("item", "")) != "":
				assert_not_null(Content.get_def(&"item", StringName(str(ed["item"]))), "%s rolls an item that exists: %s" % [td.id, ed["item"]])
			else:
				assert_not_null(Content.get_def(&"loot_table", StringName(str(ed.get("table", "")))), "%s nests a table that exists: %s" % [td.id, ed.get("table")])
	for e2: String in Content.errors():
		assert_false(e2.contains("w3_") or e2.contains("wild3"), e2)


func test_wall_props_face_into_the_room() -> void:
	const FACING: Dictionary = {"N": 0.0, "E": -90.0, "S": 180.0, "W": 90.0}
	for id: String in ROUND_THREE:
		var l: PoiLayout = PoiLayout.compile(_def(id))
		var against_walls: int = 0
		for p: Dictionary in l.props:
			var side: String = str(p.get("against", ""))
			if not FACING.has(side):
				continue
			against_walls += 1
			# The builder backs it onto that side of its cell: a wall (or a balcony rail) must be there.
			var e: Array = PoiLayout.side_edge(p["cell"], int(PoiLayout.SIDES[side]))
			var key: String = PoiLayout.edge_key(int(p["level"]), str(e[0]), e[1])
			assert_true(l.walls.has(key) or l.galleries.has(key),
				"%s: %s against %s at %s level %d backs onto a wall" % [id, p["prop"], side, p["cell"], p["level"]])
			# Without an authored rot the builder turns it to face away from its wall; an authored one must agree.
			if bool(p.get("rot_set", false)):
				assert_almost_eq(fposmod(float(p["rot"]) - float(FACING[side]), 360.0), 0.0, 0.01,
					"%s: %s against %s at %s faces into the room" % [id, p["prop"], side, p["cell"]])
		# The quarantine camp is mostly outdoors: its trailer, hut and reefer hold about ten.
		assert_gt(against_walls, 5, "%s dresses its walls" % id)


func test_shells_match_the_rooms_they_wrap() -> void:
	for s: Array in SHELLS:
		var id: String = s[0]
		var l: PoiLayout = PoiLayout.compile(_def(id))
		var rect: Array = s[2]
		var c0: int = rect[0]
		var r0: int = rect[1]
		var c1: int = rect[2]
		var r1: int = rect[3]
		var storeys: int = s[3]
		# Every cell of the rectangle is built on every storey the shell covers, and nothing just outside it.
		for li: int in storeys:
			for r: int in range(r0, r1 + 1):
				for c: int in range(c0, c1 + 1):
					var ch: String = l.room_at(li, Vector2i(c, r))
					assert_true(l.is_room(ch) or l.is_void(li, Vector2i(c, r)), "%s: %s covers a built cell (%d, %d) level %d" % [id, s[1], c, r, li])
		# Its prop sits at the rectangle's centre, sunk to the pad.
		var found: bool = false
		for p: Dictionary in l.props:
			if str(p.get("prop", "")) == str(s[1]):
				found = true
				# Compiled props carry their position as a Vector2 (PoiLayout._placed).
				var pos: Vector2 = p["pos"]
				assert_almost_eq(pos.x, (c0 + c1 + 1) * 0.5, 0.01, "%s: %s centred in x" % [id, s[1]])
				assert_almost_eq(pos.y, (r0 + r1 + 1) * 0.5, 0.01, "%s: %s centred in z" % [id, s[1]])
				assert_almost_eq(float(p.get("y", 0.0)), -l.floor_height, 0.001, "%s: %s stands on the pad" % [id, s[1]])
		assert_true(found, "%s places %s" % [id, s[1]])
		# The exterior openings on the rectangle's outline are exactly the ones the shell is cut for.
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
		for o: Array in s[4]:
			want.append("%s%d:%s@%d" % [o[0], o[1], o[2], o[3]])
		have.sort()
		want.sort()
		assert_eq(have, want, "%s: %s is cut for exactly the rooms' outside openings" % [id, s[1]])


func test_nothing_a_player_reads_names_a_town() -> void:
	for id: String in ROUND_THREE:
		var pd: PoiDef = _def(id)
		for t: String in TOWNS:
			assert_false(pd.display_name.contains(t), "%s: its name says %s" % [id, t])
			assert_false(pd.story.contains(t), "%s: its story says %s" % [id, t])
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("w3_"):
			var body: String = str(nd.get(&"body"))
			for t: String in TOWNS:
				assert_false(body.contains(t), "note %s names %s" % [nd.id, t])
