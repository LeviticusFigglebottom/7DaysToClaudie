extends GutTest
## The Lift 3 crash site (lift3_crash_site, DESIGN §1 and §11): the Program lift the player came in on,
## down in the timber short of the drop. A tier-1 outdoor set piece: it validates clean in every dressing,
## its route is walked end to end, it holds no Hollowed and no traps (the crew are remains), its loot is
## early gear, its notes resolve, name no town and say nothing of the outbreak's cause, the forward
## fuselage shell it reuses from the Cordon transport wreck matches the kit rooms it wraps (the openings
## are cut in tools/assetgen/blender_catalogs/props_wild4_plane.py SHELLS, mirrored below), the flight
## deck is reached by a ladder, the main map stands it back along the approach from the drop site, and
## the player's capsule walks it without a blocked doorway (TraversalAudit).

const ID: String = "lift3_crash_site"

## Places a player could read a town's name in (random worlds place it too).
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]
## Words that would tell a tier-1 reader what started the outbreak (docs/LORE_TRAIL.md).
const CAUSE_WORDS: Array[String] = ["corvane", "bh-7", "fs-2", "drill", "fung", "spore", "mycel", "bloom", "cave", "core"]

## The shell: [prop, rect [c0, r0, c1, r1], storeys built over the whole rect, exterior openings
## [side, index, kind, level]] as the catalog cuts them (w4_cordon_plane_wreck's, shifted).
const SHELL: Array = ["w4_plane_fuselage_fwd", [12, 5, 15, 18], 1, [
	["S", 0, "half", 0], ["S", 1, "half", 0], ["S", 2, "half", 0], ["S", 3, "half", 0], ["W", 10, "door", 0],
	["N", 1, "window", 1], ["N", 2, "window", 1]]]
const SIDE_NAMES: Array[String] = ["N", "E", "S", "W"]
## The Lift 3 notes (notes/lift3.json).
const NOTES: Array[String] = ["lift3_manifest", "lift3_kneeboard", "lift3_seatback"]
## Loot tables a tier-1 early find may roll from, and the items it must not.
const TABLES: Array[String] = ["lift3_cargo", "lift3_canister", "lift3_flight_kit"]
const TOO_GOOD: Array[String] = ["revolver", "shotgun", "hunting_rifle", "ammo_38", "antifungal", "first_aid_kit", "bloom_sample"]
## How far from the main map's drop site it may stand (m): back along the approach, a walk, not a neighbour.
const MAIN_MAP_DIST: Vector2 = Vector2(500.0, 1800.0)

const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")

var _validated: PoiValidator = null


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validate() -> PoiValidator:
	if _validated == null:
		_validated = PoiValidator.validate(_def())
	return _validated


func test_tier_one_and_zoned_for_the_wilderness() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "the crash site is content")
	if pd == null:
		return
	assert_eq(pd.tier, 1, "tier 1: an early find")
	assert_true(pd.zoning.has("wilderness"), "zoned wilderness")
	assert_false(pd.zoning.has("residential") or pd.zoning.has("commercial"), "stays out of town lots")


func test_validates_clean_in_every_dressing() -> void:
	var v: PoiValidator = _validate()
	assert_eq(v.errors, PackedStringArray(), "validates")
	assert_eq(v.warnings, PackedStringArray(), "no warnings")
	assert_gt(int(v.stats.get("variants", 0)), 4, "varies between runs (alternatives)")


func test_route_is_reachable_end_to_end() -> void:
	var v: PoiValidator = _validate()
	var l: PoiLayout = v.layout
	assert_gt(l.route.size(), 6, "a route of beats")
	assert_eq(v.paths.size(), l.route.size(), "every leg of the route was walked")
	assert_eq(str(l.loot_room.get("room", "")), "C", "the flight deck is the payoff")


func test_no_hollowed_and_no_traps() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(l.sleepers.size(), 0, "no Hollowed: the crew are remains")
	assert_eq(l.traps.size(), 0, "nobody rigged a crash site")
	var remains: int = 0
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "corpse_remains":
			remains += 1
	assert_eq(remains, 2, "the two pilots (one per dressing for the first officer)")


func test_mostly_outdoors() -> void:
	var pd: PoiDef = _def()
	var l: PoiLayout = PoiLayout.compile(pd)
	var room_cells: int = 0
	for li: Variant in l.levels:
		var lv: Dictionary = l.levels[li]
		for r: int in int(lv.get("d", 0)):
			for c: int in int(lv.get("w", 0)):
				if l.is_room(l.room_at(int(li), Vector2i(c, r))):
					room_cells += 1
	assert_lt(float(room_cells) / float(pd.footprint.x * pd.footprint.y), 0.1, "the hull is a small part of the site")


func test_the_flight_deck_is_climbed_to_by_a_ladder() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(l.ladders.size(), 1, "one ladder")
	var ld: Dictionary = l.ladders[0]
	assert_eq(int(ld["level"]), 0, "it stands in the crew bay")
	assert_true(bool(ld["hatch"]), "up through a hatch")
	assert_eq(l.room_at(1, ld["cell"]), "C", "into the flight deck")


func test_loot_is_early_gear_and_notes_resolve() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var containers: int = 0
	for p: Dictionary in l.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		assert_not_null(pd, "prop %s exists" % p.get("prop"))
		if pd == null:
			continue
		var cid: String = str(p.get("container", pd.container))
		if cid == "":
			continue
		containers += 1
		var cd: ContentDef = Content.get_def(&"container", StringName(cid))
		assert_not_null(cd, "container %s exists" % cid)
		if cd != null:
			assert_not_null(Content.get_def(&"loot_table", StringName(str(cd.get(&"loot_table")))), "%s has its table" % cid)
	assert_gt(containers, 4, "cargo, canisters and the crew's kit to search")
	for tid: String in TABLES:
		var td: ContentDef = Content.get_def(&"loot_table", StringName(tid))
		assert_not_null(td, "table %s" % tid)
		if td == null:
			continue
		var rolled: Array = (td.get(&"entries") as Array).duplicate()
		rolled.append_array(td.get(&"guaranteed") as Array)
		for e: Variant in rolled:
			var item: String = str((e as Dictionary).get("item", ""))
			assert_ne(item, "", "%s rolls plain items, no nested tables" % tid)
			assert_not_null(Content.get_def(&"item", StringName(item)), "%s rolls an item that exists: %s" % [tid, item])
			assert_false(TOO_GOOD.has(item), "%s keeps to early gear (%s)" % [tid, item])
	var read: Array[String] = []
	for pk: Dictionary in l.pickups:
		if bool(pk.get("is_note", false)):
			read.append(str(pk["item"]).trim_prefix("note_"))
	for nid: String in NOTES:
		assert_true(read.has(nid), "note %s lies in the wreck" % nid)
		var nd: ContentDef = Content.get_def(&"note", StringName(nid))
		assert_not_null(nd, "note %s exists" % nid)
		if nd != null:
			assert_gt(str(nd.get(&"body")).length(), 120, "note %s says something" % nid)
		assert_not_null(Content.get_def(&"item", StringName("note_" + nid)), "note_%s is an item" % nid)
	for e2: String in Content.errors():
		assert_false(e2.contains("lift3"), e2)


func test_notes_name_no_town_and_keep_the_cause_back() -> void:
	var pd: PoiDef = _def()
	for t: String in TOWNS:
		assert_false(pd.display_name.contains(t), "its name says %s" % t)
		assert_false(pd.story.contains(t), "its story says %s" % t)
	for nid: String in NOTES:
		var nd: ContentDef = Content.get_def(&"note", StringName(nid))
		if nd == null:
			continue
		var text: String = "%s\n%s" % [str(nd.get(&"title")), str(nd.get(&"body"))]
		for t: String in TOWNS:
			assert_false(text.contains(t), "note %s names %s" % [nid, t])
		for w: String in CAUSE_WORDS:
			assert_false(text.to_lower().contains(w), "note %s hints at the cause (%s)" % [nid, w])
	var manifest: String = str(Content.get_def(&"note", &"lift3_manifest").get(&"body"))
	for no: String in ["4466", "4471", "4479"]:
		assert_true(manifest.contains("No. " + no), "the manifest lists salvager %s" % no)
	var board: String = str(Content.get_def(&"note", &"lift3_kneeboard").get(&"body"))
	assert_true(board.contains("0541") and board.to_lower().contains("firebreak"), "the kneeboard crosses the firebreak at 0541, as the intro's radio")
	assert_true(board.contains("No wind") and board.contains("No. 2"), "ground moving with no wind; number two lost")


func test_wall_props_back_onto_walls() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	for p: Dictionary in l.props:
		var side: String = str(p.get("against", ""))
		if side == "":
			continue
		var e: Array = PoiLayout.side_edge(p["cell"], int(PoiLayout.SIDES[side]))
		var key: String = PoiLayout.edge_key(int(p["level"]), str(e[0]), e[1])
		assert_true(l.walls.has(key), "%s against %s at %s level %d backs onto a wall" % [p["prop"], side, p["cell"], p["level"]])


func test_the_shell_matches_the_rooms_it_wraps() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var rect: Array = SHELL[1]
	var c0: int = rect[0]
	var r0: int = rect[1]
	var c1: int = rect[2]
	var r1: int = rect[3]
	for li: int in int(SHELL[2]):
		for r: int in range(r0, r1 + 1):
			for c: int in range(c0, c1 + 1):
				assert_true(l.is_room(l.room_at(li, Vector2i(c, r))), "the shell covers a built cell (%d, %d) level %d" % [c, r, li])
	var found: bool = false
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == str(SHELL[0]):
			found = true
			var pos: Vector2 = p["pos"]
			assert_almost_eq(pos.x, (c0 + c1 + 1) * 0.5, 0.01, "centred in x")
			assert_almost_eq(pos.y, (r0 + r1 + 1) * 0.5, 0.01, "centred in z")
			assert_almost_eq(float(p.get("y", 0.0)), -l.floor_height, 0.001, "stands on the pad")
	assert_true(found, "places the forward fuselage")
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
	for o: Array in SHELL[3]:
		want.append("%s%d:%s@%d" % [o[0], o[1], o[2], o[3]])
	have.sort()
	want.sort()
	assert_eq(have, want, "the shell is cut for exactly the rooms' outside openings")


func test_the_main_map_stands_it_back_along_the_approach() -> void:
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	assert_not_null(world, "the main map loads")
	if world == null:
		return
	var f: FileAccess = FileAccess.open("res://world/main_map/regions/d6_larch_hollow/region.json", FileAccess.READ)
	var j := JSON.new()
	assert_eq(j.parse(f.get_as_text()), OK, "region.json parses")
	var drop := Vector2.INF
	var placed: Dictionary = {}
	var others: Array[Vector2] = []
	for fe: Variant in (j.data as Dictionary).get("features", []):
		var d: Dictionary = fe
		if str(d.get("type", "")) == "spawn" and str(d.get("id", "")) == "drop_site":
			drop = Vector2(float(d["pos"][0]), float(d["pos"][1]))
		elif str(d.get("type", "")) == "poi" and str(d.get("poi", "")) == ID:
			placed = d
		elif str(d.get("type", "")) in ["poi", "framework"]:
			others.append(Vector2(float(d["origin"][0]), float(d["origin"][1])))
	assert_false(placed.is_empty(), "Larch Hollow places the crash site")
	if placed.is_empty() or drop == Vector2.INF:
		return
	# The origin is the pad's corner; its rotation turns the plan as the composer does (Vector2.rotated).
	var pd: PoiDef = _def()
	var o := Vector2(float(placed["origin"][0]), float(placed["origin"][1]))
	var ang: float = deg_to_rad(float(placed.get("rotation", 0.0)))
	var corners: Array[Vector2] = []
	for k: Vector2 in [Vector2.ZERO, Vector2(pd.footprint.x, 0), Vector2(0, pd.footprint.y), Vector2(pd.footprint)]:
		corners.append(o + k.rotated(ang))
	var centre: Vector2 = o + (Vector2(pd.footprint) * 0.5).rotated(ang)
	var dist: float = centre.distance_to(drop)
	assert_between(dist, MAIN_MAP_DIST.x, MAIN_MAP_DIST.y, "a walk back from the drop (%.0f m)" % dist)
	for oth: Vector2 in others:
		assert_gt(centre.distance_to(oth), 90.0, "clear of the POI at %s" % oth)
	# The nose (the plan's back, -Z) points along the approach, toward the drop.
	var heading: Vector2 = Vector2(0, -1).rotated(ang)
	assert_gt(heading.dot((drop - centre).normalized()), 0.9, "it came down heading for the drop")
	var rect: Rect2 = world.region_rect("d6_larch_hollow").grow(-48.0)
	for c: Vector2 in corners:
		assert_true(rect.has_point(c), "inside the region, clear of its fading border (%s)" % c)


func test_the_player_walks_it_without_a_blocked_doorway() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var errors: Array[String] = []
	for f: Dictionary in found:
		if str(f.get("severity", "")) == "error":
			errors.append(TraversalAudit.line(ID, f))
	assert_eq(errors, [] as Array[String], "TraversalAudit finds nothing on the route")
