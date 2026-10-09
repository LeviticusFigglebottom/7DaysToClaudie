extends GutTest
## Base traps and electricity (ADR-0052) on real pieces: a generator is fuelled, started and wired
## to a work light that then shines; wire runs cost spools by length and are refunded when cut; the
## generator burns its fuel down and the light goes out with it; a sentry is loaded and shoots a
## Hollow, a kill credited to the trap directive; a spike pit stakes, holds and slows a Hollow and
## wears; a deadfall drops on what walks under it and is lifted again; a tripwire bell rings; the
## traps are walked through; a destroyed piece takes its state and wires along; none of it touches
## the companion (mid-game audit M1, TD-300).

var _prev: GameSession
var _bm: BuildingManager
var _tm: BaseTechManager
var _p: PlayerState
var _kills: Array = []


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 41, "game_mode": "slice"})
	_p = Game.session.local_player()
	_bm = BuildingManager.new()
	add_child_autofree(_bm)
	_bm.set_physics_process(false)
	_tm = BaseTechManager.new()
	_tm.building = _bm
	add_child_autofree(_tm)
	_tm.register_commands()
	_kills.clear()
	Events.trap_killed.connect(_on_kill)


func after_each() -> void:
	Events.trap_killed.disconnect(_on_kill)
	for c: StringName in BaseTechManager.COMMANDS:
		Game.unregister_command(c)
	Game.session = _prev


func _on_kill(piece: StringName, def_id: StringName, enemy_id: StringName) -> void:
	_kills.append([piece, def_id, enemy_id])


func _spawn(def_id: StringName, id: StringName, at: Vector3 = Vector3.ZERO) -> StructurePiece:
	var def: StructureDef = Content.structure(def_id)
	var piece: StructurePiece = _bm._spawn_piece(id, def, Transform3D(Basis(), at), def.hp)
	Events.structure_placed.emit(id, def_id, at)
	return piece


func _args(id: String, extra: Dictionary = {}) -> Dictionary:
	return {"player": String(_p.id), "piece": id}.merged(extra)


func _enemy(at: Vector3) -> Enemy:
	var e := Enemy.new()
	e.setup(&"test:hollow", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = at
	e.set_physics_process(false)
	return e


## Ezra's body (ADR-0058), recruited: in the "enemies" group like any Hollow, but an ally.
func _ezra(at: Vector3) -> Enemy:
	var e := Enemy.new()
	e.setup(&"test:ezra", Content.enemy(&"ezra_vane"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = at
	e.set_physics_process(false)
	assert_not_null(e.ally, "the companion's body carries its mind")
	e.ally.recruited = true
	assert_true(e.is_alive(), "recruited and up: in play")
	return e


func _lit_generator(at: Vector3 = Vector3.ZERO) -> StructurePiece:
	var gen: StructurePiece = _spawn(&"generator", &"s:gen", at)
	_p.inventory.add_item(&"gas_can", 1)
	assert_true(bool(Game.execute(&"power.fuel", _args("s:gen"))["ok"]))
	assert_true(bool(Game.execute(&"power.toggle", _args("s:gen"))["ok"]))
	return gen


func test_fuel_start_wire_and_light_a_base() -> void:
	var gen: StructurePiece = _spawn(&"generator", &"s:gen")
	var light: StructurePiece = _spawn(&"work_light", &"s:light", Vector3(6, 0, 0))
	assert_not_null(gen.tech, "a generator gets its tech node")
	assert_not_null(light.tech)
	assert_false(bool(Game.execute(&"power.toggle", _args("s:gen"))["ok"]), "no fuel, no start")
	assert_false(bool(Game.execute(&"power.fuel", _args("s:gen"))["ok"]), "no gas can carried")
	_p.inventory.add_item(&"gas_can", 3)
	var f: Dictionary = Game.execute(&"power.fuel", _args("s:gen"))
	assert_true(bool(f["ok"]))
	assert_eq(float(f["fuel"]), BaseTech.can_hours())
	assert_true(bool(Game.execute(&"power.fuel", _args("s:gen"))["ok"]))
	assert_false(bool(Game.execute(&"power.fuel", _args("s:gen"))["ok"]), "the tank is full")
	assert_eq(_p.inventory.count_of(&"gas_can"), 1)
	assert_true(bool(Game.execute(&"power.toggle", _args("s:gen"))["ok"]))
	assert_true(_tm.has_power(gen), "it runs")
	assert_false(_tm.has_power(light), "not wired yet")
	assert_false(light.tech.is_lit())
	# Wire them: one spool for six metres.
	var wire: Dictionary = {"player": String(_p.id), "from": "s:gen", "to": "s:light"}
	assert_false(bool(Game.execute(&"power.wire", wire)["ok"]), "no wire carried")
	_p.inventory.add_item(&"copper_wire", 2)
	var xp0: int = _p.progression.xp
	var w: Dictionary = Game.execute(&"power.wire", wire)
	assert_true(bool(w["ok"]))
	assert_eq(int(w["spools"]), 1)
	assert_eq(_p.inventory.count_of(&"copper_wire"), 1, "the spool is spent")
	assert_gt(_p.progression.xp, xp0, "wiring teaches a little")
	assert_false(bool(Game.execute(&"power.wire", wire)["ok"]), "already wired")
	assert_true(_tm.has_power(light), "wired to a running generator")
	assert_true(light.tech.is_lit(), "and it shines")
	assert_not_null(_tm._wires.mesh, "the wire is drawn")
	# Switching the light off and on.
	assert_false(bool(Game.execute(&"power.toggle", _args("s:light"))["on"]))
	assert_false(light.tech.is_lit())
	Game.execute(&"power.toggle", _args("s:light"))
	assert_true(light.tech.is_lit())
	# Stopping the generator darkens it.
	Game.execute(&"power.toggle", _args("s:gen"))
	assert_false(light.tech.is_lit(), "no power, no light")
	Game.execute(&"power.toggle", _args("s:gen"))
	# Cutting the wires gives the spool back.
	var cut: Dictionary = Game.execute(&"power.unwire", _args("s:light"))
	assert_true(bool(cut["ok"]))
	assert_eq(int(cut["spools"]), 1)
	assert_eq(_p.inventory.count_of(&"copper_wire"), 2)
	assert_false(light.tech.is_lit())
	assert_false(bool(Game.execute(&"power.unwire", _args("s:light"))["ok"]), "nothing left to cut")


func test_a_run_too_long_is_refused_and_takes_more_spools_when_long() -> void:
	_spawn(&"generator", &"s:gen")
	_spawn(&"work_light", &"s:near", Vector3(12, 0, 0))
	_spawn(&"work_light", &"s:far", Vector3(30, 0, 0))
	_p.inventory.add_item(&"copper_wire", 5)
	var far: Dictionary = Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:far"})
	assert_false(bool(far["ok"]))
	assert_eq(str(far["error"]), "too long")
	var near: Dictionary = Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:near"})
	assert_true(bool(near["ok"]))
	assert_eq(int(near["spools"]), 2, "twelve metres take two ten-metre spools")
	assert_false(bool(Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:near", "to": "s:near"})["ok"]), "not to itself")


func test_the_generator_burns_dry_and_the_lights_go_out() -> void:
	var gen: StructurePiece = _lit_generator()
	var light: StructurePiece = _spawn(&"work_light", &"s:light", Vector3(3, 0, 0))
	_p.inventory.add_item(&"copper_wire", 1)
	Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:light"})
	assert_true(light.tech.is_lit())
	var st: Dictionary = Game.session.world.base_tech["power"]["s:gen"]
	_tm.tick(60.0)
	assert_lt(float(st["fuel"]), BaseTech.can_hours(), "an hour burns fuel")
	assert_gt(float(st["fuel"]), BaseTech.can_hours() - 1.0, "less than an hour's worth at a light load")
	_tm.tick(60.0 * 24.0)
	assert_eq(float(st["fuel"]), 0.0, "run dry")
	assert_false(_tm.has_power(gen))
	assert_false(light.tech.is_lit(), "and the light is out")
	# The world setting: double fuel use burns twice as fast.
	st["fuel"] = 2.0
	_tm.refresh_grid()
	Game.session.rules.values["power_fuel_use"] = 2.0
	_tm.tick(30.0)
	var load: float = float(_tm.loads.get("s:gen", 0.0))
	assert_almost_eq(float(st["fuel"]), 2.0 - BaseTech.fuel_burn(30.0, load, 2.0), 0.0001)


func test_a_sentry_is_loaded_and_shoots_a_hollow() -> void:
	_lit_generator()
	var sentry: StructurePiece = _spawn(&"nail_sentry", &"s:sentry", Vector3(2, 0, 0))
	_p.inventory.add_item(&"copper_wire", 1)
	Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:sentry"})
	assert_true(_tm.has_power(sentry))
	assert_false(bool(Game.execute(&"power.load", _args("s:sentry"))["ok"]), "no nails")
	_p.inventory.add_item(&"nails", 30)
	var l: Dictionary = Game.execute(&"power.load", _args("s:sentry"))
	assert_true(bool(l["ok"]))
	assert_eq(int(l["ammo"]), 30)
	assert_eq(_p.inventory.count_of(&"nails"), 0)
	var e: Enemy = _enemy(Vector3(8, 0, 0))
	var hp: float = e.health
	sentry.tech._turret_step(1.0)
	assert_lt(e.health, hp, "it fires at the Hollow in range")
	assert_eq(int(Game.session.world.base_tech["power"]["s:sentry"]["ammo"]), 29, "a nail a shot")
	# A Hollow out of range is left alone.
	var far: Enemy = _enemy(Vector3(60, 0, 0))
	e.health = 0.5
	sentry.tech.fire_at(e)
	assert_false(e.is_alive(), "shot dead")
	assert_eq(_kills.size(), 1, "a sentry kill is a trap kill")
	assert_eq(_kills[0][1], &"nail_sentry")
	var hp_far: float = far.health
	sentry.tech._fire_t = 0.0
	sentry.tech._turret_step(1.0)
	assert_eq(far.health, hp_far, "too far to shoot")


func test_a_spike_pit_stakes_holds_and_slows() -> void:
	var pit: StructurePiece = _spawn(&"spike_pit", &"s:pit")
	assert_eq(pit.collision_layer, BaseTechNode.INTERACT_LAYER, "walked into, not over")
	var e: Enemy = _enemy(Vector3(0.2, 0, 0))
	var hp: float = e.health
	var pit_hp: float = pit.hp
	pit.tech._on_body_entered(e)
	assert_lt(e.health, hp, "staked on the way in")
	assert_lt(pit.hp, pit_hp, "the stakes wear")
	# Held: whatever it tries, it stays where it fell in.
	e.global_position = Vector3(1.0, 0, 0)
	pit.tech._pit_step(0.1)
	assert_almost_eq(e.global_position.x, 0.2, 0.001, "held while it claws out")
	# Then slowed: it keeps only part of each step.
	pit.tech._inside[e]["stuck"] = 0.0
	var from: Vector3 = e.global_position
	e.global_position = from + Vector3(1.0, 0, 0)
	pit.tech._pit_step(0.1)
	var slow: float = float(BaseTech.trap_cfg("spike_pit").get("slow", 0.3))
	assert_almost_eq(e.global_position.x - from.x, slow, 0.001, "slowed in the pit")
	var hp2: float = e.health
	pit.tech._pit_step(2.0)
	assert_lt(e.health, hp2, "staked again while inside")
	pit.tech._on_body_exited(e)
	assert_true(pit.tech._inside.is_empty())


func test_a_deadfall_drops_and_is_lifted_again() -> void:
	var df: StructurePiece = _spawn(&"deadfall", &"s:df")
	assert_eq(df.collision_layer, BaseTechNode.INTERACT_LAYER, "walked under, not into")
	var e: Enemy = _enemy(Vector3(0, 0, 0))
	var hp: float = e.health
	# A Hollow walking under it sets it off through the trigger (the physics overlap).
	await wait_physics_frames(4)
	assert_lt(e.health, hp, "the log comes down on it")
	assert_false(e.is_alive(), "hard enough to kill a plain Hollow")
	assert_eq(_kills.size(), 1, "a trap kill")
	if not _kills.is_empty():
		assert_eq(_kills[0][1], &"deadfall")
	assert_false(bool(Game.session.world.base_tech["traps"]["s:df"]["armed"]), "sprung")
	assert_lt(df.hp, df.max_hp(), "it wears")
	var e2: Enemy = _enemy(Vector3(0, 0, 0.2))
	var hp2: float = e2.health
	df.tech._on_body_entered(e2)
	assert_eq(e2.health, hp2, "a sprung deadfall does nothing")
	assert_true(bool(Game.execute(&"trap.rearm", _args("s:df"))["ok"]))
	assert_true(bool(Game.session.world.base_tech["traps"]["s:df"]["armed"]), "set again")
	assert_false(bool(Game.execute(&"trap.rearm", _args("s:df"))["ok"]), "already set")
	# Still standing under it: the next physics step (or its own walk in) brings it down again.
	await wait_physics_frames(3)
	df.tech._on_body_entered(e2)
	assert_lt(e2.health, hp2, "and it drops again")


func test_a_loaded_sprung_deadfall_shows_its_log_down() -> void:
	BaseTech.world_state()["traps"]["s:df"] = {"armed": false}
	var df: StructurePiece = _spawn(&"deadfall", &"s:df")
	assert_almost_eq(df.tech._log.position.y, 0.18, 0.001, "the log lies where it fell")
	assert_false(bool(Game.session.world.base_tech["traps"]["s:df"]["armed"]), "placing it didn't reset the saved state")


func test_a_tripwire_rings_once_per_cooldown() -> void:
	var tw: StructurePiece = _spawn(&"tripwire_bell", &"s:tw")
	var e: Enemy = _enemy(Vector3(0, 0, 0))
	var st := Stimuli.new()
	add_child_autofree(st)
	var seq0: int = st.last_seq()
	tw.tech._on_body_entered(e)
	assert_gt(st.last_seq(), seq0, "the bell is heard")
	var seq1: int = st.last_seq()
	tw.tech._on_body_entered(e)
	assert_eq(st.last_seq(), seq1, "not again until the cooldown")


func test_a_destroyed_piece_takes_its_state_and_wires() -> void:
	_lit_generator()
	var light: StructurePiece = _spawn(&"work_light", &"s:light", Vector3(3, 0, 0))
	_p.inventory.add_item(&"copper_wire", 1)
	Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:light"})
	assert_true(light.tech.is_lit())
	_bm.destroy_piece(&"s:gen")
	await wait_process_frames(2)
	assert_false(Game.session.world.base_tech["power"].has("s:gen"), "its state is gone")
	assert_true((Game.session.world.base_tech["wires"] as Array).is_empty(), "and its wires")
	assert_false(light.tech.is_lit(), "the light lost its power")


func test_prompts_follow_the_state() -> void:
	var gen: StructurePiece = _spawn(&"generator", &"s:gen")
	var pl := Player.new()
	pl.state = _p
	autofree(pl)
	assert_string_contains(BaseTechManager.prompt(gen, pl), "empty")
	_p.inventory.add_item(&"gas_can", 1)
	assert_eq(BaseTechManager.action(gen, pl)[0], &"power.fuel")
	Game.execute(&"power.fuel", _args("s:gen"))
	assert_eq(BaseTechManager.action(gen, pl)[0], &"power.toggle")
	assert_string_contains(BaseTechManager.prompt(gen, pl), "Start")
	_p.inventory.add_item(&"copper_wire", 1)
	assert_eq(BaseTechManager.alt_action(gen, pl)[0], &"wire_start", "with a spool, run a wire")
	BaseTechManager.alt_act(gen, pl)
	var light: StructurePiece = _spawn(&"work_light", &"s:light", Vector3(4, 0, 0))
	assert_eq(BaseTechManager.alt_action(light, pl)[0], &"power.wire", "then connect it")
	BaseTechManager.alt_act(light, pl)
	assert_eq((Game.session.world.base_tech["wires"] as Array).size(), 1)
	assert_eq(BaseTechManager.alt_action(light, pl)[0], &"power.unwire", "no spool left: cut it")
	var df: StructurePiece = _spawn(&"deadfall", &"s:df")
	Game.session.world.base_tech["traps"]["s:df"]["armed"] = false
	assert_eq(BaseTechManager.action(df, pl)[0], &"trap.rearm")


## M1: the sentry and the floodlight walk the "enemies" group, which holds Ezra too. Neither
## aims at him; both still take the Hollow beside him.
func test_a_powered_sentry_and_floodlight_ignore_the_companion() -> void:
	_lit_generator()
	var sentry: StructurePiece = _spawn(&"nail_sentry", &"s:sentry", Vector3(2, 0, 0))
	var flood: StructurePiece = _spawn(&"floodlight", &"s:flood", Vector3(-2, 0, 0))
	_p.inventory.add_item(&"copper_wire", 2)
	Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:sentry"})
	Game.execute(&"power.wire", {"player": String(_p.id), "from": "s:gen", "to": "s:flood"})
	assert_true(_tm.has_power(sentry) and _tm.has_power(flood), "both powered")
	_p.inventory.add_item(&"nails", 30)
	Game.execute(&"power.load", _args("s:sentry"))
	var ezra: Enemy = _ezra(Vector3(5, 0, 0))
	var hp: float = ezra.health
	sentry.tech._turret_step(1.0)
	sentry.tech.fire_at(ezra)
	assert_eq(ezra.health, hp, "the sentry never shoots him")
	assert_eq(int(Game.session.world.base_tech["power"]["s:sentry"]["ammo"]), 30, "not a nail spent on him")
	flood.tech._scan_t = 0.0
	flood.tech._flood_step(0.5)
	assert_false(flood.tech.is_lit(), "his moving about the base doesn't trip the floodlight")
	assert_eq(flood.tech._hold_t, 0.0)
	# A Hollow further off than him: both take it.
	var e: Enemy = _enemy(Vector3(9, 0, 0))
	var ehp: float = e.health
	sentry.tech._fire_t = 0.0
	sentry.tech._turret_step(1.0)
	assert_lt(e.health, ehp, "the sentry fires at the Hollow")
	assert_eq(ezra.health, hp, "and still not at him, though he is nearer")
	flood.tech._scan_t = 0.0
	flood.tech._flood_step(0.5)
	assert_true(flood.tech.is_lit(), "the floodlight catches the Hollow")


## M1, the traps: a spike pit, a deadfall and a tripwire bell neither trigger on nor hurt him.
func test_traps_never_trigger_on_the_companion() -> void:
	var pit: StructurePiece = _spawn(&"spike_pit", &"s:pit", Vector3(20, 0, 0))
	var ezra: Enemy = _ezra(Vector3(20.2, 0, 0))
	var hp: float = ezra.health
	var pit_hp: float = pit.hp
	pit.tech._on_body_entered(ezra)
	assert_eq(ezra.health, hp, "no stake for him")
	assert_eq(pit.hp, pit_hp, "and no wear")
	assert_true(pit.tech._inside.is_empty(), "nor held or slowed")
	var df: StructurePiece = _spawn(&"deadfall", &"s:df", Vector3(-20, 0, 0))
	df.tech._on_body_entered(ezra)
	assert_true(bool(Game.session.world.base_tech["traps"]["s:df"]["armed"]), "he doesn't spring the deadfall")
	var tw: StructurePiece = _spawn(&"tripwire_bell", &"s:tw", Vector3(0, 0, 20))
	var st := Stimuli.new()
	add_child_autofree(st)
	var seq0: int = st.last_seq()
	tw.tech._on_body_entered(ezra)
	assert_eq(st.last_seq(), seq0, "he steps over the tripwire")
	# Under a deadfall a Hollow springs, the log spares him.
	ezra.global_position = Vector3(-20, 0, 0)
	var e: Enemy = _enemy(Vector3(-20, 0, 0.2))
	await wait_physics_frames(4)
	assert_false(bool(Game.session.world.base_tech["traps"]["s:df"]["armed"]), "the Hollow sprang it")
	assert_false(e.is_alive(), "the log killed the Hollow")
	assert_eq(ezra.health, hp, "and missed him")
