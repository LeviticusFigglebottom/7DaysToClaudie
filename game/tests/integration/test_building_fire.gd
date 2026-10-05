extends GutTest
## Campfire fuel through the build commands: feeding takes kindling before logs, lighting needs a
## lighter and fuel, the fire burns down with game time and goes out at zero; repairs cost
## materials and dismantling refunds them.

var _prev: GameSession
var _bm: BuildingManager
var _p: PlayerState


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 11, "game_mode": "slice"})
	_p = Game.session.local_player()
	_bm = BuildingManager.new()
	add_child_autofree(_bm)
	# No world here: the manager's input/preview loop stays off.
	_bm.set_physics_process(false)


func after_each() -> void:
	Game.session = _prev


func _fire() -> StructurePiece:
	var def: StructureDef = Content.structure(&"campfire")
	return _bm._spawn_piece(&"s:test_fire", def, Transform3D.IDENTITY, def.hp)


func test_feeding_lighting_and_burning_out() -> void:
	var fire: StructurePiece = _fire()
	assert_true(fire.burns_fuel())
	assert_false(bool(_bm._cmd_light({"player": String(_p.id), "piece": "s:test_fire"})["ok"]), "no fuel, no fire")
	_p.inventory.add_item(&"log", 1)
	_p.inventory.add_item(&"stick", 2)
	var res: Dictionary = _bm._cmd_add_fuel({"player": String(_p.id), "piece": "s:test_fire"})
	assert_true(bool(res["ok"]))
	assert_eq(_p.inventory.count_of(&"stick"), 1, "kindling goes on first")
	assert_eq(_p.inventory.count_of(&"log"), 1, "the log is kept for building")
	assert_almost_eq(fire.fuel, BuildingManager.fuel_minutes(Content.item(&"stick")), 0.01)
	assert_false(bool(_bm._cmd_light({"player": String(_p.id), "piece": "s:test_fire"})["ok"]), "nothing to light it with")
	_p.inventory.add_item(&"lighter", 1)
	assert_true(bool(_bm._cmd_light({"player": String(_p.id), "piece": "s:test_fire"})["ok"]))
	assert_true(fire.lit)
	_bm._burn_fires(fire.fuel * 0.5)
	assert_true(fire.lit, "still burning halfway")
	_bm._burn_fires(fire.fuel + 1.0)
	assert_false(fire.lit, "out when the fuel is gone")
	assert_eq(fire.fuel, 0.0)


func test_repair_costs_and_dismantle_refunds() -> void:
	var fire: StructurePiece = _fire()
	fire.hp = fire.max_hp() * 0.5
	var args: Dictionary = {"player": String(_p.id), "piece": "s:test_fire"}
	assert_false(bool(_bm._cmd_repair(args)["ok"]), "repairs are not free")
	_p.inventory.add_item(&"stone", 2)
	_p.inventory.add_item(&"stick", 1)
	assert_true(bool(_bm._cmd_repair(args)["ok"]))
	assert_eq(_p.inventory.count_of(&"stone"), 0)
	assert_false(bool(_bm._cmd_dismantle(args)["ok"]), "dismantling needs a hammer in hand")
	_p.inventory.add_item(&"claw_hammer", 1)
	_p.toolbelt[0] = &"claw_hammer"
	_p.equipped_slot = 0
	fire.hp = fire.max_hp()
	assert_true(bool(_bm._cmd_dismantle(args)["ok"]))
	assert_false(_bm.pieces.has(&"s:test_fire"))
	assert_eq(_p.inventory.count_of(&"stone"), 3, "half the stones back")
	assert_eq(_p.inventory.count_of(&"stick"), 2, "and half the sticks")
