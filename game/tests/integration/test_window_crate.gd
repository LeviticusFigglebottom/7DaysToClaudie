extends GutTest
## A window whose sill is past the vault's reach from the yard (1.6 m up: a 0.9 m kit sill on a
## floor 0.7 m up) is the way in only with something to climb on under it, a route cue (ADR-0022).
## The traversal bot (poi_walk) walks to a 0.8 m box stood in front of it, jumps onto it with the
## player's own moves and vaults in from its top, and reports the leg as assisted by a crate; with
## nothing under the window the leg stays blocked, as before.

const Bot := preload("res://src/tools/cli/poi_walk_bot.gd")

## The bot with a box stood in front of the window once the building is up, before it indexes the
## solid things round it (a stand-in for a route-cue crate or a prop the content puts there).
class BoxBot:
	extends "res://src/tools/cli/poi_walk_bot.gd"
	var box_size: Vector3 = Vector3.ZERO

	func _build(instance_id: String) -> void:
		super._build(instance_id)
		if box_size == Vector3.ZERO:
			return
		var body := StaticBody3D.new()
		body.name = "Step_box"
		body.collision_layer = 1
		body.collision_mask = 0
		var cs := CollisionShape3D.new()
		var b := BoxShape3D.new()
		b.size = box_size
		cs.shape = b
		cs.position = Vector3(0, box_size.y * 0.5, 0)
		body.add_child(cs)
		# The window is the south side of cell (1, 2): its wall line is z = origin.y + 3.
		body.position = Vector3(layout.origin.x + 1.5, 0.0, layout.origin.y + 3.0 + RouteCues.WALL_T * 0.5 + box_size.z * 0.5 + 0.02)
		inst.add_child(body)


var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev


## One room 0.7 m up, its only way in a broken 1 m window on the south wall (no route cues: the
## test stands its own box).
func _def() -> PoiDef:
	var raw: Dictionary = {"id": "crate_window_test", "name": "Crate Window Test", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.7, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "way_in", "at": [1, 2], "side": "S", "type": "window", "state": "broken", "cue": "none"}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}],
		"loot_room": {"room": "A", "level": 0}}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func _window_leg(rep: Dictionary) -> Dictionary:
	for leg: Dictionary in rep["legs"]:
		if str(leg.get("opening", "")) == "way_in" and str(leg["from"]) == "L0(1,3)":
			return leg
	return {}


func test_climbs_a_box_under_a_high_window_and_vaults_in() -> void:
	var bot: BoxBot = BoxBot.new()
	# About a crate's footprint (crate_wood is 0.6 x 0.42), 0.8 m tall.
	bot.box_size = Vector3(0.5, 0.8, 0.4)
	add_child_autofree(bot)
	var rep: Dictionary = await bot.walk(_def(), "test/crate_window")
	var leg: Dictionary = _window_leg(rep)
	gut.p("window leg: %s" % leg)
	assert_false(leg.is_empty(), "the route goes in through the window")
	assert_true(bool(leg.get("ok", false)), "the body got in")
	assert_eq(str(leg.get("assist", "")), "crate", "climbed from the box")
	assert_eq(str(leg.get("assist_prop", "")), "Step_box", "the box is named")
	assert_almost_eq(float(leg.get("sill_m", 0.0)), 1.6, 0.05, "the sill is 1.6 m over the yard")
	assert_has(leg["needed"], "crate")
	assert_has(leg["needed"], "vault")
	assert_true((rep["assisted"] as Array).has(leg), "listed as assisted")
	assert_eq(rep["blocked"], [], "nothing blocked")
	assert_has(rep["visited"], "0:A", "stood in the room")


func test_without_a_prop_the_high_window_stays_blocked() -> void:
	var bot: BoxBot = BoxBot.new()
	add_child_autofree(bot)
	var rep: Dictionary = await bot.walk(_def(), "test/crate_window_bare")
	var leg: Dictionary = _window_leg(rep)
	gut.p("window leg: %s" % leg)
	assert_false(leg.is_empty(), "the route goes in through the window")
	assert_false(bool(leg.get("ok", true)), "no way up to the sill")
	assert_false(leg.has("assist"), "not assisted")
	assert_true(leg.has("needed"), "keeps what it tried")
	assert_eq(str(leg.get("category", "")), "window")
	assert_true((rep["blocked"] as Array).has(leg), "listed as blocked")
