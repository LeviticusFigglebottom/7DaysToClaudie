extends GutTest
## Campfire fuel through the build commands: feeding takes kindling before logs, lighting needs a
## lighter and fuel, the fire burns down with game time and goes out at zero; repairs cost
## materials and dismantling refunds them; a placed blueprint ghost can be taken down for what
## was handed over.

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


func test_dismantling_a_can_chime_gives_it_back() -> void:
	var def: StructureDef = Content.structure(&"can_chime_trap")
	_bm._spawn_piece(&"s:test_chime", def, Transform3D.IDENTITY, def.hp)
	_p.inventory.add_item(&"claw_hammer", 1)
	_p.toolbelt[0] = &"claw_hammer"
	_p.equipped_slot = 0
	assert_true(bool(_bm._cmd_dismantle({"player": String(_p.id), "piece": "s:test_chime"})["ok"]))
	assert_eq(_p.inventory.count_of(&"can_chime"), 1, "the chime comes back (half of one rounded down was nothing)")


func _site(bp_id: StringName, delivered: Dictionary, placed: Array) -> BlueprintSite:
	var bp: BlueprintDef = Content.get_def(&"blueprint", bp_id) as BlueprintDef
	var site: BlueprintSite = _bm._spawn_site(&"bp:test", bp, Transform3D.IDENTITY, delivered, placed)
	Game.session.world.blueprints["bp:test"] = site.to_dict()
	return site


func test_a_placed_blueprint_can_be_taken_down_for_what_was_delivered() -> void:
	var site: BlueprintSite = _site(&"campfire", {"stone": 3, "stick": 2}, [])
	var hint: String = PlayerInteraction.alt_text(site, null)
	assert_string_contains(hint, "hold [%s]" % PlayerInteraction.key_label(&"cancel"), "the prompt names the key")
	assert_string_contains(hint, "take down the Campfire blueprint")
	assert_string_contains(hint, "3 Stone")
	var args: Dictionary = {"player": String(_p.id), "site": "bp:test"}
	_p.stats.alive = false
	assert_false(bool(_bm._cmd_demolish(args)["ok"]), "not while dead")
	_p.stats.alive = true
	var res: Dictionary = _bm._cmd_demolish(args)
	assert_true(bool(res["ok"]))
	assert_eq(res["refund"], {"stone": 3, "stick": 2})
	assert_eq(_p.inventory.count_of(&"stone"), 3, "the stones come back")
	assert_eq(_p.inventory.count_of(&"stick"), 2, "and the sticks")
	assert_false(_bm.sites.has(&"bp:test"), "the ghost is gone")
	assert_false(Game.session.world.blueprints.has("bp:test"), "and so is its saved state")
	assert_false(bool(_bm._cmd_demolish(args)["ok"]), "only once")


func test_taking_down_a_log_blueprint_leaves_its_logs() -> void:
	var site: BlueprintSite = _site(&"log_wall", {}, [0, 1])
	assert_string_contains(PlayerInteraction.alt_text(site, null), "the logs already set stay")
	var res: Dictionary = _bm._cmd_demolish({"player": String(_p.id), "site": "bp:test"})
	assert_true(bool(res["ok"]))
	assert_eq(res["refund"], {}, "logs set in its slots are ordinary logs now: nothing to hand back")
	assert_false(_bm.sites.has(&"bp:test"))


func test_holding_cancel_on_a_ghost_takes_it_down_but_a_tap_does_not() -> void:
	Game.register_command(&"build.demolish", _bm._cmd_demolish)
	var ground := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(20, 1, 20)
	cs.shape = box
	ground.add_child(cs)
	add_child_autofree(ground)
	ground.global_position = Vector3(0, -0.5, 0)
	var player: Player = (load("res://src/player/player.tscn") as PackedScene).instantiate() as Player
	player.input_enabled = false
	add_child_autofree(player)
	player.bind_state(_p)
	# The campfire ghost straight ahead at eye height (the player looks down -Z).
	var site: BlueprintSite = _site(&"campfire", {"stone": 3}, [])
	site.global_position = Vector3(0, 1.4, -1.5)
	for i: int in 4:
		await get_tree().physics_frame
	assert_string_contains(player.interaction.alt_prompt, "take down the Campfire blueprint", "the line under the prompt offers it")
	player.input_enabled = true
	# A tap (as when cancelling a placement or closing a page) takes nothing down.
	await get_tree().physics_frame
	Input.action_press(&"cancel")
	for i2: int in 6:
		await get_tree().physics_frame
	Input.action_release(&"cancel")
	for i3: int in 70:
		await get_tree().physics_frame
	assert_true(_bm.sites.has(&"bp:test"), "a tap leaves the ghost")
	# Held past ALT_HOLD, it comes down and the stones come back.
	await get_tree().physics_frame
	Input.action_press(&"cancel")
	for i4: int in int(PlayerInteraction.ALT_HOLD * Engine.physics_ticks_per_second) + 10:
		await get_tree().physics_frame
	Input.action_release(&"cancel")
	assert_false(_bm.sites.has(&"bp:test"), "held, it is taken down")
	assert_eq(_p.inventory.count_of(&"stone"), 3, "and what was delivered comes back")
	Game.unregister_command(&"build.demolish")
