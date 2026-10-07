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
