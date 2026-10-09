extends GutTest
## Waystation 9 in the Cordon wall (TD-369, region D7): the wall pieces (data/props/cordon.json) and
## the post (POI waystation_9_post).
## * The pieces tile at a 6 m pitch with flush ends, their collision boxes close the wall from the
##   ground to the wire (no gap a body fits through, the river bay's water opening included), the
##   generated models ship exactly those boxes, and before `make assets` they draw as their boxes.
## * The post validates clean, is a safe tier-1 place (no Hollowed, traps or triggers), keeps the wall
##   line through its footprint and opens nowhere onto the outside, its notes resolve and keep the
##   outbreak's cause back, and the trader's kiosk, board and quartermaster land in the room left for
##   them at the def's anchor (TraderDef.in_poi), where the post raises no ring of barriers.
## * The player's capsule walks it (TraversalAudit) and the walk bot stands in every room.

const ID: String = "waystation_9_post"
const PITCH: float = 6.0
const WALL_Z: float = 9.0
const PIECES: Array[String] = ["cordon_wall_panel", "cordon_wall_gate", "cordon_river_gate", "cordon_river_abutment"]
const WIDTHS: Dictionary = {"cordon_wall_panel": 6.0, "cordon_wall_gate": 12.0, "cordon_river_gate": 6.0, "cordon_river_abutment": 3.0}
## Height each piece must be closed to along its whole length (the panel's and gate's wire top, the
## river pieces' concrete).
const CLOSED_TO: Dictionary = {"cordon_wall_panel": 6.9, "cordon_wall_gate": 4.86, "cordon_river_gate": 8.0, "cordon_river_abutment": 8.0}
const NOTES: Array[String] = ["ws9_salvager_notice", "ws9_standing_orders"]
const CAUSE_WORDS: Array[String] = ["corvane", "bh-7", "fs-2", "drill", "fung", "spore", "mycel", "bloom", "cave", "core", "mine"]

const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")
const Bot := preload("res://src/tools/cli/poi_walk_bot.gd")

var _validated: PoiValidator = null


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validate() -> PoiValidator:
	if _validated == null:
		_validated = PoiValidator.validate(_def())
	return _validated


func _prop(id: String) -> PropDef:
	return Content.get_def(&"prop", StringName(id)) as PropDef


## [x0, x1, y0, y1, z0, z1] of a box entry in the prop's frame (yaw 0 boxes only).
func _extent(b: Array) -> Array:
	var sz: Vector3 = b[0]
	var c: Vector3 = (b[1] as Transform3D).origin
	return [c.x - sz.x / 2, c.x + sz.x / 2, c.y - sz.y / 2, c.y + sz.y / 2, c.z - sz.z / 2, c.z + sz.z / 2]


# --- the wall pieces ----------------------------------------------------------------------------

func test_pieces_tile_flush_at_the_pitch() -> void:
	for id: String in PIECES:
		var pd: PropDef = _prop(id)
		assert_not_null(pd, "%s is content" % id)
		if pd == null:
			continue
		assert_eq(pd.standin, "boxes", "%s draws as its boxes before make assets" % id)
		assert_false(pd.boxes.is_empty(), "%s has collision boxes" % id)
		assert_almost_eq(pd.size.x, float(WIDTHS[id]), 0.011, "%s is %.1f m along the wall" % [id, WIDTHS[id]])
		var lo: float = INF
		var hi: float = -INF
		for b: Array in pd.collision_boxes():
			if not is_zero_approx((b[1] as Transform3D).basis.get_euler().y):
				continue
			var e: Array = _extent(b)
			lo = minf(lo, e[0])
			hi = maxf(hi, e[1])
		assert_almost_eq(lo, -float(WIDTHS[id]) / 2.0, 0.001, "%s's boxes start at its west end" % id)
		assert_almost_eq(hi, float(WIDTHS[id]) / 2.0, 0.001, "%s's boxes end at its east end (flush)" % id)
		assert_almost_eq(fmod(float(WIDTHS[id]), PITCH / 2.0), 0.0, 0.001, "%s fits the 6 m pitch (whole or half panels)" % id)
	assert_eq(_prop("cordon_wall_gate").size.x, 2.0 * PITCH, "the gate takes two panels' place")


## Along the wall line every x is closed from the ground to the piece's height by boxes standing on
## the line: nobody walks, crawls or swims through, and the river bay's opening is its grate.
func test_pieces_close_the_line_from_ground_to_top() -> void:
	for id: String in PIECES:
		var pd: PropDef = _prop(id)
		if pd == null:
			continue
		var top: float = float(CLOSED_TO[id])
		var x: float = -float(WIDTHS[id]) / 2.0 + 0.05
		while x < float(WIDTHS[id]) / 2.0:
			var spans: Array[Vector2] = []
			for b: Array in pd.collision_boxes():
				if not is_zero_approx((b[1] as Transform3D).basis.get_euler().y):
					continue
				var e: Array = _extent(b)
				# boxes across the line (the grate stands 0.42 m upstream of it, still across the opening)
				if e[0] <= x and x <= e[1] and e[4] <= 0.5 and e[5] >= -0.5:
					spans.append(Vector2(e[2], e[3]))
			spans.sort_custom(func(a: Vector2, b2: Vector2) -> bool: return a.x < b2.x)
			var reach: float = 0.0
			for s: Vector2 in spans:
				if s.x > reach + 0.01:
					break
				reach = maxf(reach, s.y)
			assert_gte(reach + 0.01, top, "%s is closed up to %.2f m at x %.2f (reaches %.2f)" % [id, top, x, reach])
			x += 0.25


func test_generated_models_ship_the_def_boxes() -> void:
	var checked: int = 0
	for id: String in PIECES + ["cordon_notice_board"]:
		var pd: PropDef = _prop(id)
		if pd == null or pd.boxes.is_empty():
			continue
		for model: Variant in pd.variants.values():
			if not ModelLibrary.has_model(str(model)):
				continue
			var shapes: Array = ModelLibrary.shapes(str(model))
			if shapes.is_empty():
				continue
			checked += 1
			assert_eq(shapes.size(), pd.boxes.size(), "%s ships one collider per def box" % model)
			var have: Array[AABB] = []
			for s: Dictionary in shapes:
				have.append(_shape_aabb(s["shape"], s["transform"]))
			for b: Array in pd.collision_boxes():
				var want: AABB = _box_aabb(b[0], b[1])
				var found: bool = false
				for h: AABB in have:
					if h.position.distance_to(want.position) < 0.03 and h.size.distance_to(want.size) < 0.03:
						found = true
						break
				assert_true(found, "%s ships the def's box at %s size %s" % [model, want.get_center(), want.size])
	if checked == 0:
		pass_test("no generated Cordon models here (stand-in run): the boxes are the def's")


## The prop-frame AABB of a box of `size` placed by `xf` (a turned box: of its corners).
func _box_aabb(size: Vector3, xf: Transform3D) -> AABB:
	var pts := PackedVector3Array()
	for i: int in 8:
		pts.append(Vector3(size.x * (0.5 if i & 1 else -0.5), size.y * (0.5 if i & 2 else -0.5), size.z * (0.5 if i & 4 else -0.5)))
	return _points_aabb(pts, xf)


func _shape_aabb(sh: Shape3D, xf: Transform3D) -> AABB:
	if sh is BoxShape3D:
		return _box_aabb((sh as BoxShape3D).size, xf)
	if sh is ConvexPolygonShape3D:
		return _points_aabb((sh as ConvexPolygonShape3D).points, xf)
	return AABB()


func _points_aabb(pts: PackedVector3Array, xf: Transform3D) -> AABB:
	var a := AABB(xf * pts[0], Vector3.ZERO)
	for p: Vector3 in pts:
		a = a.expand(xf * p)
	return a


func test_stand_ins_draw_the_boxes() -> void:
	var pd: PropDef = _prop("cordon_wall_panel")
	if pd == null:
		return
	var m: Mesh = ModelLibrary.boxes_mesh(pd.collision_boxes(), Color.GRAY)
	assert_not_null(m, "a stand-in mesh")
	var aabb: AABB = m.get_aabb()
	assert_almost_eq(aabb.size.x, 6.0, 0.001, "as long as the panel")
	assert_almost_eq(aabb.end.y, 6.9, 0.001, "as tall as the wire")
	assert_not_null(ModelLibrary.prop_standin("props/cordon_wall_panel"), "the panel has a box stand-in")
	assert_null(ModelLibrary.prop_standin("props/waystation_tower"), "other props keep the generic placeholder")


# --- the post -----------------------------------------------------------------------------------

func test_a_safe_tier_one_post() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "the post is content")
	if pd == null:
		return
	assert_eq(pd.tier, 1, "tier 1")
	var l: PoiLayout = PoiLayout.compile(pd)
	assert_eq(l.sleepers.size(), 0, "no Hollowed at a trader post")
	assert_eq(l.traps.size(), 0, "no traps")
	assert_eq((pd.layout.get("triggers", []) as Array).size(), 0, "no ambush triggers")


func test_validates_clean() -> void:
	var v: PoiValidator = _validate()
	assert_eq(v.errors, PackedStringArray(), "validates")
	assert_eq(v.warnings, PackedStringArray(), "no warnings")
	assert_eq(v.paths.size(), v.layout.route.size(), "every leg of the route was walked")
	assert_eq(str(v.layout.loot_room.get("room", "")), "P", "the Program stores are the payoff")
	for e: String in Content.errors():
		assert_false(e.contains("waystation") or e.contains("cordon"), e)


func test_the_wall_line_runs_through_the_footprint() -> void:
	var pd: PoiDef = _def()
	var l: PoiLayout = PoiLayout.compile(pd)
	var xs: Array[float] = []
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) != "cordon_wall_panel":
			continue
		var pos: Vector2 = p["pos"]
		assert_almost_eq(pos.y, WALL_Z, 0.001, "panel %s on the wall line" % p.get("id"))
		assert_almost_eq(float(p.get("rot", 0.0)), 0.0, 0.001, "panel %s faces the valley (+Z)" % p.get("id"))
		xs.append(pos.x)
	xs.sort()
	assert_eq(xs, [3.0, 9.0, 27.0, 33.0] as Array[float], "two panels each side at the 6 m pitch")
	assert_almost_eq(xs[0] - PITCH / 2.0, 0.0, 0.001, "the wall comes in at the west edge")
	assert_almost_eq(xs[xs.size() - 1] + PITCH / 2.0, float(pd.footprint.x), 0.001, "and leaves at the east edge")
	# The block fills the line between the panels: its west and east walls stand where they end.
	for li: int in [0, 1]:
		for c: int in range(12, 24):
			assert_true(l.is_room(l.room_at(li, Vector2i(c, 8))) and l.is_room(l.room_at(li, Vector2i(c, 9))),
				"level %d: the block is built across the line at x %d" % [li, c])
		assert_false(l.is_room(l.room_at(li, Vector2i(11, 9))), "nothing built west of the block on the line")
		assert_false(l.is_room(l.room_at(li, Vector2i(24, 9))), "nothing built east of it")


func test_nothing_opens_outside_the_cordon() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	for op: Dictionary in l.openings:
		var cell: Vector2i = op["cell"]
		var side: int = int(op["side"])
		var out: Vector2i = cell + [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)][side]
		if l.is_room(l.room_at(int(op["level"]), out)):
			continue
		assert_gte(out.y, int(WALL_Z), "%s opens onto the valley side, not outside the wall (onto %s)" % [op.get("id", ""), out])


func test_the_trader_lands_at_the_hatch() -> void:
	var td: TraderDef = Content.get_def(&"trader", &"waystation_9") as TraderDef
	assert_not_null(td, "the trader def")
	if td == null:
		return
	assert_eq(str(td.in_poi.get("poi", "")), ID, "Waystation 9 is built into the post")
	var pd: PoiDef = _def()
	var l: PoiLayout = PoiLayout.compile(pd)
	var a: Array = td.in_poi["anchor"]
	var anchor := Vector2(float(a[0]), float(a[1]))
	assert_gt(anchor.y, 19.0, "the spawn stands in the forecourt, on the valley side")
	# The counter (the kiosk) stands in the hatch recess: yard cells boxed in by the building.
	var co: Array = td.counter["offset"]
	var counter := anchor + Vector2(float(co[0]), float(co[1]))
	var kiosk: PropDef = _prop(str(td.counter["prop"]))
	var half := Vector2(kiosk.size.x, kiosk.size.z) * 0.5
	var krect := Rect2(counter - half, half * 2.0)
	for cx: int in range(int(floor(krect.position.x)), int(ceil(krect.end.x))):
		for cz: int in range(int(floor(krect.position.y)), int(ceil(krect.end.y))):
			assert_false(l.is_room(l.room_at(0, Vector2i(cx, cz))), "the kiosk stands on the yard (cell %d, %d)" % [cx, cz])
	for side: Vector2i in [Vector2i(15, 17), Vector2i(20, 17), Vector2i(18, 15)]:
		assert_true(l.is_room(l.room_at(0, side)), "the recess is walled by the post (%s)" % side)
	# The quartermaster stands inside the kiosk; the board stands in the open forecourt.
	var qo: Array = td.quartermaster["offset"]
	assert_true(krect.has_point(anchor + Vector2(float(qo[0]), float(qo[2]))), "the quartermaster is behind the hatch")
	var bo: Array = td.board["offset"]
	var board := anchor + Vector2(float(bo[0]), float(bo[1]))
	assert_lt(board.y, float(pd.footprint.y), "the board stands inside the footprint")
	assert_false(l.is_room(l.room_at(0, Vector2i(int(board.x), int(board.y)))), "and outdoors")
	# No prop of the post stands in the kiosk's or the board's way.
	var brect := Rect2(board - Vector2(1.4, 1.4), Vector2(2.8, 2.8))
	for p: Dictionary in l.props:
		if int(p.get("level", 0)) != 0:
			continue
		var pp: PropDef = _prop(str(p.get("prop", "")))
		var pos: Vector2 = p["pos"]
		var pr := Rect2(pos - Vector2(pp.size.x, pp.size.z) * 0.5, Vector2(pp.size.x, pp.size.z))
		assert_false(pr.intersects(krect.grow(0.1)), "%s clear of the kiosk" % p.get("id", p.get("prop")))
		assert_false(pr.intersects(brect), "%s clear of the contracts board" % p.get("id", p.get("prop")))


func test_the_post_raises_no_ring_inside_its_building() -> void:
	var td: TraderDef = Content.get_def(&"trader", &"waystation_9") as TraderDef
	if td == null:
		return
	for rot: float in [0.0, 90.0, 180.0, -37.5]:
		var origin := Vector2(-410.0, 3020.0)
		var s: Dictionary = td.spawn_in(origin, rot)
		var at := Vector3((s["pos"] as Vector2).x, 12.0, (s["pos"] as Vector2).y)
		var pl: Array = [{"kind": "poi", "def": ID, "id": "ws9", "origin": [origin.x, 12.0, origin.y], "rotation": rot}]
		assert_true(TraderManager.in_building(pl, td, at), "the spawn from spawn_in lies in the building (rotation %.1f)" % rot)
		# The spawn's yaw turns the post's +Z (its counter's front) the way the building's front faces.
		var post_front: Vector3 = Basis(Vector3.UP, deg_to_rad(float(s["yaw"]))) * Vector3.BACK
		var poi_front: Vector3 = Basis(Vector3.UP, -deg_to_rad(rot)) * Vector3.BACK
		assert_almost_eq(post_front.dot(poi_front), 1.0, 0.0001, "the hatch faces the valley (rotation %.1f)" % rot)
		assert_false(TraderManager.in_building(pl, td, at + Vector3(200.0, 0.0, 0.0)), "a spawn elsewhere keeps its ring")
	assert_false(TraderManager.in_building([], td, Vector3.ZERO), "no building, the ring stands (the D6 stand-in)")


func test_notes_resolve_and_keep_the_cause_back() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var read: Array[String] = []
	for pk: Dictionary in l.pickups:
		if bool(pk.get("is_note", false)):
			read.append(str(pk["item"]).trim_prefix("note_"))
	for nid: String in NOTES:
		assert_true(read.has(nid), "note %s is at the post" % nid)
		var nd: ContentDef = Content.get_def(&"note", StringName(nid))
		assert_not_null(nd, "note %s exists" % nid)
		assert_not_null(Content.get_def(&"item", StringName("note_" + nid)), "note_%s is an item" % nid)
		if nd == null:
			continue
		var text: String = ("%s\n%s" % [str(nd.get(&"title")), str(nd.get(&"body"))]).to_lower()
		assert_gt(text.length(), 300, "note %s says something" % nid)
		for w: String in CAUSE_WORDS:
			assert_false(text.contains(w), "note %s hints at the cause (%s)" % [nid, w])
		assert_true(text.contains("seventh night"), "note %s keeps the Hum's rhythm" % nid)


func test_the_player_walks_it_without_a_blocked_doorway() -> void:
	var found: Array[Dictionary] = await Runner.audit_one(self, _def(), ID)
	var errors: Array[String] = []
	for f: Dictionary in found:
		if str(f.get("severity", "")) == "error":
			errors.append(TraversalAudit.line(ID, f))
	assert_eq(errors, [] as Array[String], "TraversalAudit finds nothing on the route")


func test_the_walk_bot_stands_in_every_room() -> void:
	var prev: GameSession = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	var bot: Node = Bot.new()
	add_child_autofree(bot)
	var rep: Dictionary = await bot.call(&"walk", _def(), "test/" + ID)
	Game.session = prev
	assert_eq(rep["blocked"], [], "no leg the body could not finish")
	assert_eq(rep["unreached"], [], "no room left unreached")
	assert_eq(int(rep["blocking"]), 0, "nothing blocking")
