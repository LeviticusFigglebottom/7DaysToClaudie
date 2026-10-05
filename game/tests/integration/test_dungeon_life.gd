extends GutTest
## Dungeon life (ADR-0022): seated and lying sleepers land on seats and beds (deterministically,
## never two on one) and pose at the furniture's height, then get up off it; the Hollowed set traps
## off by weight class; a weak floor that gives way queues the nav tiles there for a rebake; shotgun
## pellets stop at walls and fall off with distance; a trigger fired while nobody is near is spent
## and rouses its group through a save and load; route cues go on the window the route climbs in by.

const PLAYER_SCENE: String = "res://src/player/player.tscn"


## A world with just an AI director (PoiManager asks it for the nav tiles).
class StubWorld:
	extends Node
	var ai: Node


var _prev: GameSession
var _ai: AIDirector


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	_ai = AIDirector.new()
	add_child_autofree(_ai)


func after_each() -> void:
	Game.session = _prev


func _def(layout: Dictionary) -> PoiDef:
	var raw: Dictionary = {"id": "dungeon_life_test", "name": "Dungeon Life Test", "tier": 1, "footprint": [16, 16]}
	raw.merge(layout, true)
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


const STYLE: Dictionary = {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}}


## One room 6 x 4 with a kitchen chair, a diner stool, a single bed, a four-seat pew (facing north)
## and a bathtub; the door is in the south wall.
func _furnished(sleepers: Array, extra_props: Array = []) -> Dictionary:
	var props: Array = [
		{"id": "chair", "prop": "kitchen_chair", "pos": [1.0, 1.0], "rot": 0},
		{"id": "stool", "prop": "diner_stool", "pos": [2.5, 1.0]},
		{"id": "bed", "prop": "bed_single", "pos": [4.6, 1.2], "rot": 0},
		{"id": "pew", "prop": "civic_pew", "pos": [2.0, 3.2], "rot": 180},
		{"id": "tub", "prop": "bathtub", "pos": [4.6, 3.4], "rot": 0}]
	props.append_array(extra_props)
	return {
		"style": STYLE,
		"levels": [{"level": 0, "plan": ["AAAAAA", "AAAAAA", "AAAAAA", "AAAAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 3], "side": "S", "type": "door"}],
		"props": props,
		"sleepers": sleepers,
		"route": [{"at": [1, 5]}, {"at": [1, 2]}],
		"loot_room": {"room": "A", "level": 0}}


## Single storey: room A (west) and B (east) with a door between (test_poi_dungeon's).
func _one_storey(extra: Dictionary) -> Dictionary:
	var lay: Dictionary = {
		"style": STYLE,
		"levels": [{"level": 0, "plan": ["AAAABBBB", "AAAABBBB", "AAAABBBB"], "rooms": {"A": {}, "B": {}}}],
		"openings": [
			{"id": "front", "at": [1, 2], "side": "S", "type": "door"},
			{"id": "inner", "at": [4, 1], "side": "W", "type": "door", "state": "closed"}],
		"props": [{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}],
		"route": [{"at": [1, 4]}, {"at": [2, 1]}, {"at": [6, 1]}],
		"loot_room": {"room": "B", "level": 0}}
	lay.merge(extra, true)
	return lay


## Two storeys, the upper one over rotten boards (test_poi_dungeon's attic).
func _attic(traps: Array) -> Dictionary:
	return {
		"style": STYLE,
		"levels": [
			{"level": 0, "plan": ["AAAAAA", "AAAAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBBBB", "BBBBBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "door", "at": [5, 0], "side": "E", "type": "door"}],
		"ladders": [{"level": 0, "at": [5, 1], "side": "E", "hatch": true}],
		"props": [{"id": "loot", "prop": "metal_shelf", "at": [0, 0], "against": "W", "level": 1}],
		"traps": traps,
		"route": [{"at": [7, 0]}, {"at": [5, 0]}, {"at": [0, 0], "level": 1}],
		"loot_room": {"room": "B", "level": 1}}


func _build(lay: Dictionary, iid: StringName = &"test/life") -> PoiInstance:
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(lay)), iid)
	add_child_autofree(inst)
	return inst


func _player_at(pos: Vector3) -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	p.input_enabled = false
	add_child_autofree(p)
	p.bind_state(PlayerState.new())
	p.global_position = pos
	return p


## An enemy body outside the tree, for the weight rules (they read its def and whether it lives).
func _body(id: StringName) -> Enemy:
	var e := Enemy.new()
	e.setup(StringName("test:" + String(id)), Content.enemy(id), null, {})
	autofree(e)
	return e


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().physics_frame


## "sid:prop/slot" for every landed sleeper, sorted: a plan's fingerprint.
func _fingerprint(res: Dictionary) -> String:
	var out: PackedStringArray = []
	for sid: String in res["by_sleeper"]:
		var a: Dictionary = res["by_sleeper"][sid]
		out.append("%s:%s/%d" % [sid, a["prop_key"], int(a["slot"])])
	out.sort()
	return ",".join(out) + "|" + ",".join(res["floor"])


# --- Seats and beds --------------------------------------------------------------------------------

func test_anchor_choice_is_deterministic_and_never_shared() -> void:
	var sleepers: Array = [
		{"id": "a", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "b", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "c", "pos": [1.7, 2.9], "enemy": "hollow", "pose": "sit", "rot": 180},
		{"id": "d", "pos": [1.9, 2.9], "enemy": "hollow", "pose": "sit", "rot": 180},
		{"id": "e", "pos": [4.5, 1.5], "enemy": "hollow", "pose": "lie"},
		{"id": "f", "pos": [1.0, 2.0], "enemy": "hollow", "pose": "lie"},
		{"id": "g", "pos": [3.0, 2.6], "enemy": "hollow", "pose": "sit", "anchor": "floor"},
		{"id": "h", "pos": [4.4, 3.4], "enemy": "hollow", "pose": "sit", "rot": 90}]
	var layout := PoiLayout.compile(_def(_furnished(sleepers)))
	var res: Dictionary = SleeperAnchors.assign(layout)
	var by: Dictionary = res["by_sleeper"]
	assert_eq(str(by["a"]["prop_key"]), "chair")
	assert_eq(str(by["b"]["prop_key"]), "stool", "the chair is taken: the next free seat in reach")
	assert_eq(str(by["c"]["prop_key"]), "pew")
	assert_eq(str(by["d"]["prop_key"]), "pew", "a pew seats several")
	assert_ne(int(by["c"]["slot"]), int(by["d"]["slot"]))
	assert_eq(str(by["e"]["prop_key"]), "bed")
	assert_eq(str(by["e"]["kind"]), "bed")
	assert_eq(str(by["h"]["prop_key"]), "tub", "sat in the bathtub")
	assert_eq(str(by["h"]["lean"]), "low")
	assert_eq(res["floor"], PackedStringArray(["f"]), "no bed in reach: it lies where it is")
	assert_false(by.has("g"), "opted out: stays on the floor")
	var used: Dictionary = {}
	for sid: String in by:
		var key: String = "%s/%d" % [by[sid]["prop_key"], int(by[sid]["slot"])]
		assert_false(used.has(key), "anchor %s taken twice" % key)
		used[key] = true
	# The plan is a pure function of the layout: the same again, and from a fresh compile.
	var fp: String = _fingerprint(res)
	assert_eq(_fingerprint(SleeperAnchors.assign(layout)), fp)
	assert_eq(_fingerprint(SleeperAnchors.assign(PoiLayout.compile(_def(_furnished(sleepers))))), fp)


func test_close_anchors_of_one_prop_exclude_each_other() -> void:
	# A mess bench seats both ways at the same spots: two sitters by its middle get the middle and
	# an end, never the middle twice back to back.
	var layout := PoiLayout.compile(_def(_furnished([
		{"id": "x", "pos": [3.0, 1.9], "enemy": "hollow", "pose": "sit", "rot": 180},
		{"id": "y", "pos": [3.0, 2.1], "enemy": "hollow", "pose": "sit", "rot": 0}],
		[{"id": "bench", "prop": "wild_mess_bench", "pos": [3.0, 2.0], "rot": 0}])))
	var by: Dictionary = SleeperAnchors.assign(layout)["by_sleeper"]
	assert_eq(str(by["x"]["prop_key"]), "bench")
	assert_eq(str(by["y"]["prop_key"]), "bench")
	var gap: float = (by["x"]["point"] as Vector3).distance_to(by["y"]["point"])
	assert_gt(gap, float(SleeperAnchors.cfg()["exclusive"]), "not on one spot")


func test_pins_and_validator_messages() -> void:
	var lay: Dictionary = _furnished([
		{"id": "p", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit", "anchor": "stool"},
		{"id": "q", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "r", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit", "anchor": "no_such_prop"},
		{"id": "s", "pos": [1.0, 2.2], "enemy": "hollow", "pose": "lie"},
		{"id": "t", "pos": [1.0, 2.2], "enemy": "dragger", "pose": "lie", "anchor": "floor"}])
	var layout := PoiLayout.compile(_def(lay))
	var res: Dictionary = SleeperAnchors.assign(layout)
	assert_eq(str(res["by_sleeper"]["p"]["prop_key"]), "stool", "a pinned anchor wins over a nearer seat")
	assert_eq(str(res["by_sleeper"]["q"]["prop_key"]), "chair")
	var check: Dictionary = SleeperAnchors.check(layout)
	assert_eq((check["errors"] as PackedStringArray).size(), 1)
	assert_string_contains(str(check["errors"][0]), "no_such_prop")
	var warned: String = "\n".join(check["warnings"])
	assert_string_contains(warned, "'s'", "a lying sleeper with no bed in reach is flagged")
	assert_false(warned.contains("'t'"), "an opted-out one is not")
	# And the POI validator reports them.
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_string_contains("\n".join(v.errors), "no_such_prop")
	assert_string_contains("\n".join(v.warnings), "sleeper 's'")


func test_stacked_walled_and_destroyed_seats_are_not_used() -> void:
	var layout := PoiLayout.compile(_def(_furnished([], [
		{"id": "crate_low", "prop": "crate_wood", "pos": [3.5, 2.2]},
		{"id": "crate_high", "prop": "crate_wood", "pos": [3.5, 2.2], "y": 0.43},
		{"id": "facing_in", "prop": "kitchen_chair", "pos": [5.6, 3.6], "rot": 180},
		{"id": "broken", "prop": "kitchen_chair", "pos": [0.6, 2.2], "variant": "destroyed"},
		{"id": "crate_free", "prop": "crate_wood", "pos": [1.0, 2.2]}])))
	var keys: Dictionary = {}
	for a: Dictionary in SleeperAnchors.collect(layout):
		keys[str(a["prop_key"])] = true
	assert_false(keys.has("crate_low"), "a crate with a crate on it is no seat")
	assert_false(keys.has("crate_high"), "nor is the crate on top")
	assert_true(keys.has("crate_free"), "a crate on its own is")
	assert_false(keys.has("broken"), "a smashed chair holds nobody")
	assert_true(keys.has("chair") and keys.has("pew") and keys.has("bed"))
	# rot 180 faces north: by the south wall that is into the room, a seat; pushed up against the
	# north wall the sitter's feet would be in it.
	assert_true(keys.has("facing_in"), "facing into the room it is a seat")
	var walled := PoiLayout.compile(_def(_furnished([], [
		{"id": "to_wall", "prop": "kitchen_chair", "pos": [5.6, 0.35], "rot": 180}])))
	for a2: Dictionary in SleeperAnchors.collect(walled):
		assert_ne(str(a2["prop_key"]), "to_wall", "a chair facing into the wall is not a seat")


func test_body_origin_sits_on_the_seat_and_lies_on_the_mattress() -> void:
	var c: Dictionary = SleeperAnchors.cfg()
	var sh: float = float(c["seat_height"])
	var sink: float = float(c["max_sink"])
	var floor_y: float = 0.15
	var chair: Dictionary = {"kind": "seat", "lean": "back", "point": Vector3(1.0, floor_y + sh, 2.0), "floor": floor_y, "yaw": 0.0}
	var o: Vector3 = SleeperAnchors.body_origin(chair, Vector3.ONE)["origin"]
	assert_almost_eq(o.y, floor_y, 0.001, "a chair seat_height high: feet on the floor")
	assert_almost_eq(o.z, 2.0 + float(c["seat_back"]), 0.001, "feet in front of the seat")
	var stool: Dictionary = chair.duplicate()
	stool["point"] = Vector3(1.0, floor_y + 0.8, 2.0)
	assert_almost_eq((SleeperAnchors.body_origin(stool, Vector3.ONE)["origin"] as Vector3).y, floor_y + 0.8 - sh, 0.001,
		"a stool lifts the body: the seat stays under it")
	assert_almost_eq((SleeperAnchors.body_origin(stool, Vector3(1.1, 1.1, 1.1))["origin"] as Vector3).y, floor_y + 0.8 - sh * 1.1, 0.001,
		"by the body's own seat height")
	var low: Dictionary = chair.duplicate()
	low["point"] = Vector3(1.0, floor_y + 0.3, 2.0)
	assert_almost_eq((SleeperAnchors.body_origin(low, Vector3.ONE)["origin"] as Vector3).y, floor_y - sink, 0.001,
		"a low seat sinks the feet no more than max_sink")
	var bed: Dictionary = {"kind": "bed", "lean": "back", "point": Vector3(0.0, floor_y + 0.64, 0.0), "floor": floor_y, "yaw": PI * 0.5}
	var ob: Vector3 = SleeperAnchors.body_origin(bed, Vector3.ONE)["origin"]
	assert_almost_eq(ob.y, floor_y + 0.64 - float(c["mattress_sink"]), 0.001, "on the mattress, pressed in a little")
	assert_almost_eq(ob.x, float(c["lie_back"]), 0.001, "the pelvis over the anchor: the origin toward the feet")
	var tub: Dictionary = {"kind": "seat", "lean": "low", "point": Vector3(0.0, floor_y + 0.08, 0.0), "floor": floor_y, "yaw": 0.0}
	var ot: Vector3 = SleeperAnchors.body_origin(tub, Vector3.ONE)["origin"]
	assert_almost_eq(ot.y, floor_y + 0.08, 0.001, "sat on the tub's floor")
	assert_almost_eq(ot.z, float(c["sit_back"]), 0.001)


func test_sleepers_pose_on_their_furniture_and_get_up_off_it() -> void:
	var inst: PoiInstance = _build(_furnished([
		{"id": "a", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "s", "pos": [2.5, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "e", "pos": [4.5, 1.5], "enemy": "hollow", "pose": "lie"},
		{"id": "h", "pos": [4.4, 3.4], "enemy": "hollow", "pose": "sit", "rot": 90}]))
	inst.spawn_sleepers(_ai)
	await _frames(2)
	var c: Dictionary = SleeperAnchors.cfg()
	var floor_y: float = inst.to_global(Vector3(0.0, inst.layout.level_y(0), 0.0)).y
	var heights: Dictionary = {"a": 0.46, "s": 0.8, "e": 0.64, "h": 0.08}
	for sid: String in heights:
		var e: Enemy = inst.sleeper(sid)
		assert_not_null(e, sid)
		assert_false(e.perch.is_empty(), "%s is perched" % sid)
		assert_eq(e.state, Enemy.State.SLEEP)
		var h: float = float(heights[sid])
		var want: float
		match sid:
			"e":
				want = floor_y + h - float(c["mattress_sink"])
			"h":
				want = floor_y + h
			_:
				want = floor_y + maxf(h - float(c["seat_height"]) * e.visual.scale.y, -float(c["max_sink"]))
		assert_almost_eq(e.global_position.y, want, 0.01, "%s at its furniture's height" % sid)
	# Woken, the sitter on the chair gets up where its feet were and is an ordinary body after.
	var a: Enemy = inst.sleeper("a")
	var exit: Vector3 = a.perch["exit"]
	inst.alert_sleepers(a.global_position, 3.0)
	assert_eq(a.state, Enemy.State.WAKING)
	var frames: int = 0
	while not a.perch.is_empty() and frames < 200:
		await get_tree().physics_frame
		frames += 1
	assert_true(a.perch.is_empty(), "off the chair")
	assert_almost_eq(Vector2(a.global_position.x, a.global_position.z).distance_to(Vector2(exit.x, exit.z)), 0.0, 0.05,
		"standing on its exit")
	assert_almost_eq(a.global_position.y, floor_y, 0.06)
	assert_almost_eq(float(frames) / float(Engine.physics_ticks_per_second), float(c["rise_seconds"]), 0.2, "over rise_seconds")
	# The one on the bed swings off it over the side.
	var e2: Enemy = inst.sleeper("e")
	var bed_exit: Vector3 = e2.perch["exit"]
	inst.alert_sleepers(e2.global_position, 3.0)
	frames = 0
	while not e2.perch.is_empty() and frames < 200:
		await get_tree().physics_frame
		frames += 1
	assert_almost_eq(Vector2(e2.global_position.x, e2.global_position.z).distance_to(Vector2(bed_exit.x, bed_exit.z)), 0.0, 0.05)
	var bed_xf: Transform3D = inst.global_transform * SleeperAnchors.collect(inst.layout).filter(
		func(an: Dictionary) -> bool: return str(an["prop_key"]) == "bed")[0]["xf"]
	var local: Vector3 = bed_xf.affine_inverse() * e2.global_position
	assert_true(absf(local.x) > 1.09 * 0.5 or absf(local.z) > 2.06 * 0.5, "standing clear of the bed")


func test_the_animated_hips_sit_on_the_seat_and_lie_on_the_bed() -> void:
	# The pose constants in traps.json "sleepers" must match char_anim's (SEAT_H, SEAT_Y, LIE_Y,
	# SIT_Y): with generated bodies, each pose's hips bone ends over its anchor, a hand's breadth above
	# the seat, the tub floor or the mattress. The procedural stand-in body has no bones to measure.
	var inst: PoiInstance = _build(_furnished([
		{"id": "a", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "s", "pos": [2.5, 1.1], "enemy": "hollow", "pose": "sit"},
		{"id": "e", "pos": [4.5, 1.5], "enemy": "hollow", "pose": "lie"},
		{"id": "h", "pos": [4.4, 3.4], "enemy": "hollow", "pose": "sit", "rot": 90}]))
	inst.spawn_sleepers(_ai)
	await _frames(20)
	var measured: int = 0
	for sid: String in ["a", "s", "e", "h"]:
		var sk: Skeleton3D = inst.sleeper(sid).visual.skeleton
		if sk == null or sk.find_bone("hips") < 0:
			continue
		var pt: Vector3 = inst.to_global(inst.seat_of(sid)["point"] as Vector3)
		var hips: Vector3 = sk.global_transform * sk.get_bone_global_pose(sk.find_bone("hips")).origin
		assert_lt(Vector2(hips.x - pt.x, hips.z - pt.z).length(), 0.08, "%s: hips over the anchor" % sid)
		assert_between(hips.y - pt.y, 0.04, 0.2, "%s: hips just above the seat or mattress" % sid)
		measured += 1
	if measured == 0:
		pass_test("stand-in bodies (no generated models yet): nothing to measure")


func test_a_seated_sleeper_killed_asleep_stays_in_its_pose() -> void:
	var inst: PoiInstance = _build(_furnished([{"id": "a", "pos": [1.0, 1.1], "enemy": "hollow", "pose": "sit"}]))
	inst.spawn_sleepers(_ai)
	await _frames(2)
	var a: Enemy = inst.sleeper("a")
	var at: Vector3 = a.global_position
	a.take_damage(DamageInfo.make(9999.0, &"blunt", &"melee"))
	await _frames(3)
	assert_false(a.is_alive())
	assert_almost_eq(a.global_position.distance_to(at), 0.0, 0.05, "dies where it sat")


# --- The Hollowed and traps ------------------------------------------------------------------------

func test_trap_rules_by_weight_class() -> void:
	var drag: Enemy = _body(&"dragger")
	var hol: Enemy = _body(&"hollow")
	var ram: Enemy = _body(&"rammer")
	var husk: Enemy = _body(&"husk")
	assert_lt(PoiPieces.weight_of(drag), PoiPieces.weight_of(hol), "a Dragger is light")
	assert_lt(PoiPieces.weight_of(hol), PoiPieces.weight_of(ram), "a Rammer is heavy")
	assert_eq(PoiPieces.weight_of(husk), PoiPieces.weight_of(ram), "so is a Husk")
	for t: String in ["can_chime", "bear_trap", "shotgun", "alarm", "creaky_floor"]:
		assert_true(PoiPieces.hollowed_sets_off(t, drag), "even a Dragger sets off the %s" % t)
	assert_false(PoiPieces.hollowed_sets_off("weak_floor", drag))
	assert_false(PoiPieces.hollowed_sets_off("weak_floor", hol), "a Hollow is too light for rotten boards")
	assert_true(PoiPieces.hollowed_sets_off("weak_floor", ram))
	assert_true(PoiPieces.hollowed_sets_off("weak_floor", husk))
	assert_false(PoiPieces.hollowed_fires("creaky_floor"), "a Hollowed's creak is a sound cue, not the ambush")
	for t2: String in ["can_chime", "bear_trap", "shotgun", "alarm", "weak_floor"]:
		assert_true(PoiPieces.hollowed_fires(t2), "%s set off by a Hollowed still fires its triggers" % t2)


func test_weak_floor_gives_way_under_the_heavy_ones_only() -> void:
	var inst: PoiInstance = _build(_attic([
		{"id": "rotten", "type": "weak_floor", "at": [2, 1], "level": 1},
		{"id": "rotten_2", "type": "weak_floor", "at": [4, 1], "level": 1}]))
	await _frames(2)
	var collapsed: Array = []
	inst.geometry_changed.connect(func(p: Vector3) -> void: collapsed.append(p))
	var top1: Vector3 = inst.to_global(inst.layout.cell_center(1, Vector2i(2, 1)))
	var top2: Vector3 = inst.to_global(inst.layout.cell_center(1, Vector2i(4, 1)))
	# Dormant bodies hold still where they are put (no player near to wake or move them).
	var ram: Enemy = _ai.spawn_sleeper(&"rammer", top1 + Vector3.UP * 0.05, 0.0, "stand", &"", &"ram", 1, {})
	var hol: Enemy = _ai.spawn_sleeper(&"hollow", top2 + Vector3.UP * 0.05, 0.0, "stand", &"", &"hol", 1, {})
	var hp: float = ram.health
	await _frames(60)
	assert_eq(inst.trap_state("rotten"), "sprung", "the Rammer went through the boards")
	assert_lt(ram.health, hp, "and took the fall")
	assert_eq(inst.trap_state("rotten_2"), "armed", "a Hollow is too light")
	assert_eq(hol.health, hol.max_health)
	assert_eq(collapsed.size(), 1, "the building reports its changed floor once")


func test_floor_collapse_queues_a_nav_rebake_there() -> void:
	var nav := NavTiles.new()
	autofree(nav)
	_ai.nav = nav
	var world := StubWorld.new()
	world.ai = _ai
	add_child_autofree(world)
	var pm := PoiManager.new()
	pm.world = world
	autofree(pm)
	var inst: PoiInstance = _build(_attic([{"id": "rotten", "type": "weak_floor", "at": [2, 1], "level": 1}]))
	inst.geometry_changed.connect(pm._on_poi_geometry_changed)
	await _frames(2)
	var wf: PoiPieces.WeakFloor = inst.traps["rotten"]
	var at: Vector3 = wf.global_position
	# The tiles around the building are loaded (baked once already).
	var k: Vector2i = NavTiles.tile_of(at)
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			nav._tiles[Vector2i(k.x + dx, k.y + dz)] = {"region": RID(), "baking": false}
	assert_false(nav.is_dirty(at))
	wf.collapse()
	assert_true(nav.is_dirty(at), "the tile under the hole is queued for a rebake")
	await _frames(2)
	assert_true(wf.shape == null or wf.shape.disabled, "and the slab the bake would parse is gone")


func test_creaky_floor_groans_under_a_hollow_but_keeps_its_ambush() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"sleepers": [{"id": "g1", "group": "back", "at": [6, 1], "enemy": "hollow"}],
		"traps": [{"id": "boards", "type": "creaky_floor", "at": [2, 1], "size": [1, 1]}],
		"triggers": [{"id": "creaked", "group": "back", "on": "trap", "trap": "boards"}]}))
	inst.spawn_sleepers(_ai)
	await _frames(2)
	var cf: PoiPieces.CreakyFloor = inst.traps["boards"]
	var at: Vector3 = inst.to_global(inst.layout.cell_center(0, Vector2i(2, 1)))
	var walker: Enemy = _ai.spawn_sleeper(&"hollow", at + Vector3(-0.4, 0.05, 0.0), 0.0, "stand", &"", &"walker", 1, {})
	await _frames(3)
	assert_true(cf._on.has(walker), "the boards feel a Hollow's weight")
	for i: int in 20:
		walker.global_position = at + Vector3(-0.4 + 0.05 * i, 0.05, 0.0)
		await get_tree().physics_frame
	assert_eq(inst.trap_state("boards"), "armed", "a Hollowed's creak does not spend the trap")
	assert_false(inst.is_trigger_fired("creaked"))
	assert_eq(inst.sleeper("g1").state, Enemy.State.SLEEP)
	walker.global_position = at + Vector3(0.0, 0.05, 6.0)
	await _frames(2)
	# The player's stride does.
	var p: Player = _player_at(at + Vector3(-0.4, 0.05, 0.0))
	for i2: int in 25:
		p.global_position = Vector3(at.x - 0.4 + 0.05 * i2, p.global_position.y, at.z)
		await get_tree().physics_frame
	assert_eq(inst.trap_state("boards"), "sprung")
	assert_true(inst.is_trigger_fired("creaked"))


func test_an_alarm_a_hollow_blunders_into_rings_but_spends_no_ambush() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"sleepers": [
			{"id": "g1", "group": "back", "at": [6, 1], "enemy": "hollow"},
			{"id": "loner", "at": [2, 0], "enemy": "hollow"}],
		"traps": [{"id": "bell", "type": "alarm", "at": [4, 1], "side": "W"}],
		"triggers": [{"id": "into_b", "group": "back", "on": "room", "room": "B"}]}))
	await _frames(1)
	var alarm: PoiPieces.AlarmTrap = inst.traps["bell"]
	alarm.on_body(_body(&"hollow"))
	assert_eq(inst.trap_state("bell"), "sprung")
	assert_true(alarm.is_ringing())
	assert_false(inst.is_trigger_fired("into_b"), "the player's alarm spends every ambush; a Hollow's does not")
	assert_true(inst.is_roused("loner"), "with nobody spawned, who hears the ringing is roused")
	assert_true(inst.is_roused("g1"), "an alarm is a sound that wakes a held ambush close by")


# --- Shotgun pellets -------------------------------------------------------------------------------

func _target(at: Vector3, size: Vector3, layer: int = 1, pellet_target: bool = true) -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = layer
	b.collision_mask = 0
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	b.add_child(cs)
	if pellet_target:
		b.set_meta(&"pellet_target", true)
	add_child_autofree(b)
	b.global_position = at
	return b


func test_pellets_spread_stop_at_walls_and_fall_off() -> void:
	var gun := PoiPieces.ShotgunTrap.new()
	gun.type = "shotgun"
	gun.trap_id = "gun"
	gun.aim = Vector3(0.0, 0.0, 1.0)
	add_child_autofree(gun)
	gun.global_position = Vector3(200.0, 60.0, 200.0)
	var t: Dictionary = PoiPieces.cfg("shotgun")
	var n: int = int(t["pellets"])
	var near: float = float(t["near"])
	var far: float = float(t["far"])
	var m: Vector3 = gun.to_global(gun.muzzle)
	var dir := Vector3(0.0, 0.0, 1.0)
	var dirs: Array[Vector3] = gun.pellet_dirs(dir)
	assert_eq(dirs.size(), n)
	assert_eq(gun.pellet_dirs(dir), dirs, "a fixed pattern per trap")
	var max_off: float = 0.0
	for d: Vector3 in dirs:
		max_off = maxf(max_off, rad_to_deg(d.angle_to(dir)))
	assert_lt(max_off, float(t["spread_deg"]) + 0.01, "within the spread")
	assert_gt(max_off, 0.5, "and spread")
	# Point blank: every pellet, full weight.
	var close: StaticBody3D = _target(m + dir * 1.0, Vector3(1.0, 1.0, 0.4))
	await _frames(2)
	var hits: Dictionary = gun.pellet_hits(m, dir)
	assert_eq(int(hits[close]["n"]), n)
	assert_almost_eq(float(hits[close]["share"]), float(n), 0.01)
	close.queue_free()
	await _frames(2)
	# Further off: weaker in proportion to the distance flown.
	var mid: StaticBody3D = _target(m + dir * 5.5, Vector3(3.0, 3.0, 0.4))
	await _frames(2)
	hits = gun.pellet_hits(m, dir)
	assert_eq(int(hits[mid]["n"]), n)
	var expect: float = 1.0 - (5.3 - near) / (far - near)
	assert_almost_eq(float(hits[mid]["share"]) / float(n), expect, 0.03)
	# A wall in between takes them all.
	var wall: StaticBody3D = _target(m + dir * 3.0, Vector3(3.0, 3.0, 0.2), 1, false)
	await _frames(2)
	hits = gun.pellet_hits(m, dir)
	assert_false(hits.has(mid), "nothing gets through the wall")
	wall.queue_free()
	# A door leaf (layer 2) does not shield the doorway.
	var door: StaticBody3D = _target(m + dir * 3.0, Vector3(3.0, 3.0, 0.05), 1 << 1, false)
	await _frames(2)
	hits = gun.pellet_hits(m, dir)
	assert_true(hits.has(mid), "pellets pass a door leaf")
	door.queue_free()
	mid.queue_free()
	# Out of range: nothing.
	var gone: StaticBody3D = _target(m + dir * (far + 1.0), Vector3(3.0, 3.0, 0.4))
	await _frames(2)
	assert_false(gun.pellet_hits(m, dir).has(gone))


# --- Triggers with nobody near ---------------------------------------------------------------------

func test_unspawned_trigger_is_spent_and_rouses_its_group_through_save_load() -> void:
	var lay: Dictionary = _one_storey({
		"props": [
			{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"},
			{"id": "cot", "prop": "civic_army_cot", "pos": [6.0, 1.2], "rot": 0}],
		"sleepers": [
			{"id": "g1", "group": "back", "pos": [6.0, 1.4], "enemy": "hollow", "pose": "lie"},
			{"id": "g2", "group": "back", "at": [5, 2], "enemy": "hollow"},
			{"id": "loner", "at": [2, 0], "enemy": "hollow"}],
		"triggers": [{"id": "into_b", "group": "back", "on": "room", "room": "B"}]})
	var iid := &"test/unspawned"
	var inst: PoiInstance = _build(lay, iid)
	await _frames(1)
	assert_false(inst.seat_of("g1").is_empty(), "g1 sleeps on the cot")
	# The Hum breaks in while the player is far away: the trigger fires with nobody spawned.
	var at: Vector3 = inst.to_global(inst.layout.cell_center(0, Vector2i(5, 1)))
	assert_true(inst.fire_trigger("into_b", at))
	assert_true(inst.is_trigger_fired("into_b"), "spent all the same")
	assert_true(inst.is_roused("g1") and inst.is_roused("g2"), "its group is roused")
	assert_false(inst.is_roused("loner"))
	assert_false(inst.fire_trigger("into_b"), "and it fires once")
	# Save the world ledger, load it into a fresh session and rebuild the building.
	var j := JSON.new()
	assert_eq(j.parse(JSON.stringify(Game.session.world.to_dict())), OK)
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	Game.session.world.from_dict(j.data)
	var again: PoiInstance = _build(lay, iid)
	await _frames(1)
	assert_true(again.is_trigger_fired("into_b"))
	assert_true(again.is_roused("g1"), "the rousing survives the save")
	again.spawn_sleepers(_ai)
	await _frames(2)
	var g1: Enemy = again.sleeper("g1")
	assert_false(g1.held)
	assert_ne(g1.state, Enemy.State.SLEEP, "it spawns up and about")
	assert_true(g1.perch.is_empty(), "off its cot")
	var exit: Vector3 = again.to_global(again.seat_of("g1")["exit"] as Vector3)
	assert_almost_eq(Vector2(g1.global_position.x, g1.global_position.z).distance_to(Vector2(exit.x, exit.z)), 0.0, 0.3,
		"standing beside it")
	assert_ne(again.sleeper("g2").state, Enemy.State.SLEEP)
	assert_eq(again.sleeper("loner").state, Enemy.State.SLEEP, "the rest of the building sleeps on")
	assert_false(again.is_roused("g1"), "the ledger entry is used up")
	assert_false(again.fire_trigger("into_b"), "the spent ambush does not fire again")


func test_a_trap_a_hollow_trips_with_nobody_near_rouses_who_would_hear_it() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"sleepers": [
			{"id": "near", "at": [2, 1], "enemy": "hollow"},
			{"id": "held", "group": "back", "at": [6, 1], "enemy": "hollow"}],
		"triggers": [{"id": "into_b", "group": "back", "on": "room", "room": "B"}]}))
	await _frames(1)
	var at: Vector3 = inst.to_global(inst.layout.cell_center(0, Vector2i(1, 1)))
	inst.on_trap_noise(at, 10.0, &"trap")
	assert_true(inst.is_roused("near"), "within earshot")
	assert_false(inst.is_roused("held"), "a rattle does not wake a held ambush")
	inst.on_trap_noise(at, 120.0, &"gunshot")
	assert_true(inst.is_roused("held"), "a gunshot within the wake radius does")


# --- Route cues ------------------------------------------------------------------------------------

func _window_house(entry_cue: Variant = null) -> Dictionary:
	var way_in: Dictionary = {"id": "way_in", "at": [1, 2], "side": "S", "type": "window", "state": "broken"}
	if entry_cue != null:
		way_in["cue"] = entry_cue
	return {
		"style": STYLE,
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}}],
		"openings": [
			way_in,
			{"id": "lit", "at": [3, 1], "side": "E", "type": "window", "state": "closed", "cue": "light"},
			{"id": "plain", "at": [0, 1], "side": "W", "type": "window", "state": "closed"}],
		"props": [{"id": "loot_shelf", "prop": "metal_shelf", "at": [3, 0], "against": "N"}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}],
		"loot_room": {"room": "A", "level": 0}}


func test_route_cues_mark_the_window_the_route_climbs_in_by() -> void:
	var layout := PoiLayout.compile(_def(_window_house()))
	var plan: Dictionary = RouteCues.plan(layout)
	assert_eq(PackedStringArray(plan.get("way_in", [])), PackedStringArray(Content.config(&"traps")["route_cues"]["default"]),
		"the entry window gets the default cues")
	assert_eq(PackedStringArray(plan.get("lit", [])), PackedStringArray(["light"]), "an authored cue")
	assert_false(plan.has("plain"))
	var inst: PoiInstance = _build(_window_house())
	await _frames(1)
	assert_not_null(inst.get_node_or_null(^"Cue_crate_way_in_0"), "a crate to climb on under it")
	assert_not_null(inst.get_node_or_null(^"Cue_lamp_lit"), "a lamp left burning")
	var none := PoiLayout.compile(_def(_window_house("none")))
	assert_false(RouteCues.plan(none).has("way_in"), "\"none\" turns the default off")
	var bad := PoiLayout.compile(_def(_window_house("neon_sign")))
	assert_eq((RouteCues.check(bad)["errors"] as PackedStringArray).size(), 1)
	var shut: Dictionary = _window_house()
	(shut["openings"] as Array)[1]["cue"] = ["curtain"]
	assert_eq((RouteCues.check(PoiLayout.compile(_def(shut)))["warnings"] as PackedStringArray).size(), 1,
		"a curtain needs an open window to hang out of")


func test_route_cues_find_the_shipped_entry_windows() -> void:
	# RouteCues' early-exit search walks the shipped routes the way the validator's full one does:
	# the diner is climbed into over a booth, the clinic by its waiting-room window, and a building
	# entered by a door gets no window cues.
	var want: Dictionary = {"mile9_diner": "booth_window_1", "merrow_house": "kitchen_window", "tamsin_clinic": "waiting_window_w"}
	for id: String in want:
		var layout := PoiLayout.compile(Content.get_def(&"poi", StringName(id)) as PoiDef)
		assert_eq(RouteCues.entry_windows(layout).keys(), [want[id]], "%s is climbed into by %s" % [id, want[id]])
	var by_door := PoiLayout.compile(Content.get_def(&"poi", &"pell_pharmacy") as PoiDef)
	assert_true(RouteCues.entry_windows(by_door).is_empty(), "the pharmacy is walked into by a door")
