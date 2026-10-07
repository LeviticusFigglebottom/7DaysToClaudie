extends GutTest
## The POI traversal bot (src/tools/cli/poi_walk_bot.gd, `poi_walk.gd`) walks a small known-good
## building with the real Player body: in from the yard through the front door, through two more
## doors, and stands in every room without a blocked leg. Guards the bot's calibration (a bot that
## reports problems in a good building is noise) as much as the building pieces it walks through.

const Bot := preload("res://src/tools/cli/poi_walk_bot.gd")

var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev


## Three rooms on a slab 15 cm up: C (front, the way in), A behind it, B (the loot room) beside
## both, a closed door between each; no scatter.
func _def() -> PoiDef:
	var raw: Dictionary = {"id": "walk_test", "name": "Walk Test", "tier": 1, "footprint": [16, 16],
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAAABBBB", "AAAABBBB", "CCCCBBBB", "CCCCBBBB"], "rooms": {"A": {}, "B": {}, "C": {}}}],
		"openings": [
			{"id": "front", "at": [1, 3], "side": "S", "type": "door"},
			{"id": "c_to_a", "at": [1, 2], "side": "N", "type": "door"},
			{"id": "a_to_b", "at": [4, 0], "side": "W", "type": "door"}],
		"props": [{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}],
		"route": [{"at": [1, 5]}, {"at": [1, 1]}, {"at": [6, 1]}],
		"loot_room": {"room": "B", "level": 0}}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func test_walks_into_every_room_of_a_good_building() -> void:
	var bot: Node = Bot.new()
	add_child_autofree(bot)
	var rep: Dictionary = await bot.call(&"walk", _def(), "test/walk")
	assert_eq(rep["validator"], [], "the test building validates")
	assert_eq(rep["blocked"], [], "no leg the body could not finish")
	assert_eq(rep["unreached"], [], "no room left unreached")
	assert_eq(rep["visited"], ["0:A", "0:B", "0:C"], "stood in every room")
	assert_eq(rep["assisted"], [], "no jump or vault on a plain floor or doorway")
	assert_eq(int(rep["blocking"]), 0)


## The bot with the validator's plan (every step costs the same: no going round props), so the
## route runs straight into the cells a bathtub fills, as the validator's BFS path does.
class BfsBot:
	extends "res://src/tools/cli/poi_walk_bot.gd"

	func _step_cost(_a: Array, _b: Array) -> float:
		return 1.0


## One room three cells wide, in by a door on the south; a bathtub turned along the room fills the
## middle column's cells (1, 1) and (1, 2) (the capsule fits nowhere in them), with a free lane down
## either side of it.
func _tub_def() -> PoiDef:
	var raw: Dictionary = {"id": "walk_tub_test", "name": "Walk Tub Test", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 3], "side": "S", "type": "door"}],
		"props": [{"id": "tub", "prop": "bathtub", "at": [1, 1], "offset": [0.0, 0.5], "rot": 90}],
		"route": [{"at": [1, 5]}, {"at": [1, 0]}],
		"loot_room": {"room": "A", "level": 0}}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func test_detours_round_props_that_fill_the_planned_cells() -> void:
	var bot: BfsBot = BfsBot.new()
	add_child_autofree(bot)
	var rep: Dictionary = await bot.walk(_tub_def(), "test/walk_tub")
	var detours: Array = (rep["assisted"] as Array).filter(func(l: Dictionary) -> bool: return str(l.get("assist", "")) == "detour")
	gut.p("detour legs: %s" % [detours])
	assert_eq(rep["blocked"], [], "no leg blocked: the lane beside the tub is the way")
	assert_false(detours.is_empty(), "a leg went round the tub")
	if detours.is_empty():
		return
	assert_has(detours[0]["needed"], "detour")
	assert_true(str(detours[0].get("past", "")).contains("L0(1,2)"), "past the cells the tub fills")
	assert_has(rep["visited"], "0:A")
	assert_eq(int(rep["blocking"]), 0)


## Two rooms stacked: in by a door on the east, up a ladder leaning on the east wall of (3, 0) to the
## room above (the loot).
func _ladder_def() -> PoiDef:
	var raw: Dictionary = {"id": "walk_ladder_test", "name": "Walk Ladder Test", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [
			{"level": 0, "plan": ["AAAA", "AAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBB", "BBBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "door", "at": [3, 1], "side": "E", "type": "door"}],
		"ladders": [{"level": 0, "at": [3, 0], "side": "E", "hatch": true}],
		"props": [{"id": "loot", "prop": "metal_shelf", "at": [0, 0], "against": "W", "level": 1}],
		"route": [{"at": [5, 1]}, {"at": [1, 1]}, {"at": [0, 1], "level": 1}],
		"loot_room": {"room": "B", "level": 1}}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func test_climbs_a_ladder() -> void:
	var bot: Node = Bot.new()
	add_child_autofree(bot)
	var rep: Dictionary = await bot.call(&"walk", _ladder_def(), "test/walk_ladder")
	gut.p("climbs: %s" % [rep["climbs"]])
	assert_eq(rep["validator"], [], "the test building validates")
	assert_false((rep["climbs"] as Array).is_empty(), "the route takes the ladder")
	for c: Dictionary in rep["climbs"]:
		assert_true(bool(c["ok"]), "climbed %s" % c)
	assert_eq(rep["blocked"], [], "no leg blocked")
	assert_has(rep["visited"], "1:B", "stood in the room above")


## Where the player climbs by walking into a ladder (Player.is_climbing), the bot's walk-in path
## climbs it; on a branch whose player has no climbing yet there is nothing to walk into.
func test_walks_into_a_ladder_to_climb_it() -> void:
	var probe: Player = (load(Bot.PLAYER_SCENE) as PackedScene).instantiate() as Player
	var can_climb: bool = probe.has_method(&"is_climbing")
	probe.free()
	if not can_climb:
		pending("the player has no is_climbing here: ladders climb by their interact")
		return
	var bot: Node = Bot.new()
	bot.set(&"force_walk_in", true)
	add_child_autofree(bot)
	var rep: Dictionary = await bot.call(&"walk", _ladder_def(), "test/walk_ladder_in")
	gut.p("climbs: %s" % [rep["climbs"]])
	assert_false((rep["climbs"] as Array).is_empty(), "the route takes the ladder")
	for c: Dictionary in rep["climbs"]:
		assert_true(bool(c["ok"]), "climbed %s" % c)
		assert_eq(str(c["how"]), "walk_in")
	assert_has(rep["visited"], "1:B", "stood in the room above")
