extends GutTest
## Base traps and electricity (ADR-0052), the rules alone (BaseTech): pieces' roles from their
## defs, fresh states, wire spools, who gets power on a network, fuel burn by load and the world
## setting, heat, trap damage by the setting and wear, warnings' bearings, the content wiring, and
## the state's save round trip (an older save without it loads empty).

const SLOT: String = "unit_test_base_tech"

var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 31, "game_mode": "slice"})


func after_each() -> void:
	Game.session = _prev
	SaveSystem.delete_slot(SLOT)


func _def(id: StringName) -> StructureDef:
	return Content.structure(id)


func _node(id: StringName, st: Dictionary = {}) -> Dictionary:
	return {"def": _def(id), "st": BaseTech.new_state(_def(id)).merged(st, true)}


func test_roles_come_from_the_defs() -> void:
	assert_eq(BaseTech.trap_kind(_def(&"spike_pit")), "spike_pit")
	assert_eq(BaseTech.trap_kind(_def(&"deadfall")), "deadfall")
	assert_eq(BaseTech.trap_kind(_def(&"tripwire_bell")), "tripwire")
	assert_eq(BaseTech.power_kind(_def(&"generator")), "generator")
	assert_eq(BaseTech.power_kind(_def(&"work_light")), "work_light")
	assert_eq(BaseTech.power_kind(_def(&"floodlight")), "floodlight")
	assert_eq(BaseTech.power_kind(_def(&"nail_sentry")), "turret")
	assert_eq(BaseTech.source_watts(_def(&"generator")), 400.0)
	assert_eq(BaseTech.draw_watts(_def(&"work_light")), 60.0)
	for plain: StringName in [&"log_piece", &"campfire", &"spike_barrier", &"garden_bed"]:
		assert_false(BaseTech.handles(_def(plain)), "%s is no base tech" % plain)
	assert_true(BaseTech.walk_through(_def(&"spike_pit")), "the Hollowed walk into a pit")
	assert_false(BaseTech.walk_through(_def(&"generator")), "but bump into a generator")


func test_content_is_wired() -> void:
	for bp: StringName in [&"spike_pit", &"deadfall", &"tripwire_bell", &"generator", &"work_light", &"floodlight", &"nail_sentry"]:
		var b: BlueprintDef = Content.get_def(&"blueprint", bp) as BlueprintDef
		assert_not_null(b, "a blueprint for %s" % bp)
		assert_eq(b.result, bp)
	for s: StringName in [&"schematic_generator", &"schematic_floodlight", &"schematic_nail_sentry"]:
		var it: ItemDef = Content.item(s)
		assert_true(it != null and it.teaches.has("blueprint"), "%s teaches its blueprint" % s)
		var taught: BlueprintDef = Content.get_def(&"blueprint", StringName(str(it.teaches["blueprint"]))) as BlueprintDef
		assert_eq(taught.unlock, "schematic", "the blueprint %s needs it" % taught.id)
	assert_not_null(Content.get_def(&"recipe", &"strip_wire"), "wire is stripped from parts at the workbench")
	assert_not_null(Content.get_def(&"loot_table", &"electrical_salvage"))
	assert_not_null(Content.item(StringName(str(BaseTech.power_cfg("generator").get("fuel_item", "")))), "the fuel is an item")
	assert_not_null(Content.item(StringName(str(BaseTech.power_cfg("wire").get("item", "")))), "the wire is an item")
	var d: DirectiveDef = Content.get_def(&"directive", &"hold_trap_kill") as DirectiveDef
	assert_eq(d.event, "trap_kill")
	var rules := GameRules.current()
	assert_true(rules.values.has("trap_damage") and rules.values.has("power_fuel_use"), "two world settings")


func test_fresh_states() -> void:
	assert_eq(BaseTech.new_state(_def(&"deadfall")), {"armed": true}, "a deadfall comes set")
	assert_eq(BaseTech.new_state(_def(&"spike_pit")), {})
	assert_eq(BaseTech.new_state(_def(&"generator")), {"on": false, "fuel": 0.0}, "off and empty")
	assert_eq(BaseTech.new_state(_def(&"work_light")), {"on": true}, "a light is switched on")
	assert_eq(BaseTech.new_state(_def(&"nail_sentry")), {"on": true, "ammo": 0})


func test_wire_spools_by_length() -> void:
	assert_eq(BaseTech.wire_spools(0.5), 1, "any run takes a spool")
	assert_eq(BaseTech.wire_spools(10.0), 1)
	assert_eq(BaseTech.wire_spools(10.5), 2)
	assert_eq(BaseTech.wire_spools(14.5), 0, "past the longest run")
	var wires: Array = [["a", "b", 1]]
	assert_true(BaseTech.has_wire(wires, "b", "a"), "either way round")
	assert_false(BaseTech.has_wire(wires, "a", "c"))
	assert_eq(BaseTech.wires_of(wires, "b").size(), 1)


func test_a_running_generator_powers_its_network_in_order() -> void:
	var nodes: Dictionary = {
		"g": _node(&"generator", {"on": true, "fuel": 2.0}),
		"l1": _node(&"work_light"), "l2": _node(&"work_light"),
		"s": _node(&"nail_sentry"), "f": _node(&"floodlight"),
		"lone": _node(&"work_light"),
	}
	# A chain through consumers counts: g - l1 - s - l2 - f; "lone" is wired to nothing.
	var wires: Array = [["g", "l1", 1], ["l1", "s", 1], ["s", "l2", 1], ["l2", "f", 1]]
	var res: Dictionary = BaseTech.solve(nodes, wires)
	var p: Dictionary = res["powered"]
	# 400 W: f (150) first by id, then l1 (60), l2 (60) = 270; the sentry's 200 no longer fits.
	assert_true(p.has("f") and p.has("l1") and p.has("l2"), "served in id order")
	assert_false(p.has("s"), "the sentry doesn't fit in what is left")
	assert_false(p.has("lone"), "not wired, not powered")
	assert_false(p.has("g"), "the generator is no consumer")
	assert_almost_eq(float(res["load"]["g"]), 270.0 / 400.0, 0.001)
	assert_eq((res["networks"] as Array).size(), 2)
	# Switching the floodlight off frees its watts for the sentry.
	nodes["f"]["st"]["on"] = false
	p = BaseTech.solve(nodes, wires)["powered"]
	assert_true(p.has("s") and not p.has("f"))
	# Off or out of fuel, nothing runs.
	nodes["g"]["st"]["fuel"] = 0.0
	assert_true((BaseTech.solve(nodes, wires)["powered"] as Dictionary).is_empty(), "no fuel, no power")
	nodes["g"]["st"]["fuel"] = 2.0
	nodes["g"]["st"]["on"] = false
	assert_true((BaseTech.solve(nodes, wires)["powered"] as Dictionary).is_empty(), "switched off, no power")
	# A second generator on the network adds its watts.
	nodes["g"]["st"]["on"] = true
	nodes["g2"] = _node(&"generator", {"on": true, "fuel": 1.0})
	wires.append(["g2", "lone", 1])
	wires.append(["lone", "g", 1])
	nodes["f"]["st"]["on"] = true
	p = BaseTech.solve(nodes, wires)["powered"]
	for id: String in ["f", "l1", "l2", "lone", "s"]:
		assert_true(p.has(id), "800 W serve %s" % id)
	assert_eq(BaseTech.solve(nodes, [["g", "ghost", 1]])["powered"].size(), 0, "a wire to a missing piece is ignored")


func test_fuel_burns_by_load_and_setting() -> void:
	var idle: float = float(BaseTech.power_cfg("generator").get("idle_burn", 0.35))
	assert_almost_eq(BaseTech.fuel_burn(60.0, 1.0), 1.0, 0.0001, "an hour at full load is an hour of fuel")
	assert_almost_eq(BaseTech.fuel_burn(60.0, 0.0), idle, 0.0001, "idling burns less")
	assert_almost_eq(BaseTech.fuel_burn(60.0, 1.0, 2.0), 2.0, 0.0001, "the setting scales it")
	var st: Dictionary = {"on": true, "fuel": 1.5}
	assert_false(BaseTech.burn(st, 60.0, 1.0))
	assert_almost_eq(float(st["fuel"]), 0.5, 0.0001)
	assert_true(BaseTech.burn(st, 60.0, 1.0), "runs dry")
	assert_eq(float(st["fuel"]), 0.0, "never below empty")
	var off: Dictionary = {"on": false, "fuel": 3.0}
	BaseTech.burn(off, 600.0, 1.0)
	assert_eq(float(off["fuel"]), 3.0, "a stopped generator burns nothing")
	assert_gt(BaseTech.heat(60.0, 1.0), BaseTech.heat(60.0, 0.0), "a loaded engine draws more attention")
	assert_gt(BaseTech.heat(60.0, 0.0), 0.0, "even idling")
	assert_eq(BaseTech.hours_text(3.34), "3h 20m")
	assert_eq(BaseTech.hours_text(0.5), "30m")


func test_trap_damage_follows_the_setting_and_dull_stakes() -> void:
	assert_eq(BaseTech.trap_damage(20.0), 20.0)
	assert_eq(BaseTech.trap_damage(20.0, 0.2, 0.35), 10.0, "dull stakes do half")
	assert_eq(BaseTech.trap_damage(20.0, 0.5, 0.35), 20.0)
	Game.session.rules.values["trap_damage"] = 2.0
	assert_eq(BaseTech.trap_damage(20.0), 40.0, "the world setting scales it")


func test_bearing_text() -> void:
	assert_eq(BaseTech.bearing_text(Vector3.ZERO, Vector3(0, 0, -40)), "north, 40 m", "-Z is north")
	assert_eq(BaseTech.bearing_text(Vector3.ZERO, Vector3(30, 0, 30)), "south-east, 42 m")
	assert_eq(BaseTech.bearing_text(Vector3.ZERO, Vector3(1, 0, 1)), "right by you")


func test_state_saves_and_older_saves_load_without_it() -> void:
	var s: GameSession = Game.session
	var ws: Dictionary = BaseTech.world_state()
	ws["power"]["s:000004"] = {"on": true, "fuel": 3.25}
	ws["power"]["s:000005"] = {"on": true, "ammo": 37}
	ws["traps"]["s:000006"] = {"armed": false}
	(ws["wires"] as Array).append(["s:000004", "s:000005", 1])
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var back: GameSession = SaveSystem.load_session(SLOT)
	assert_not_null(back)
	assert_almost_eq(float(back.world.base_tech["power"]["s:000004"]["fuel"]), 3.25, 0.0001)
	assert_eq(int(back.world.base_tech["power"]["s:000005"]["ammo"]), 37)
	assert_false(bool(back.world.base_tech["traps"]["s:000006"]["armed"]))
	assert_eq((back.world.base_tech["wires"] as Array).size(), 1)
	var old := WorldState.new()
	var d: Dictionary = s.world.to_dict()
	d.erase("base_tech")
	old.from_dict(d)
	assert_eq(old.base_tech, {}, "a save from before base tech loads with none")


func test_a_wire_being_run_shows_where_it_goes_and_what_it_takes() -> void:
	# TD-246: the free end follows the aim; the line under the prompt reads it live.
	var cam := Vector3(0, 1.6, 0)
	var fwd := Vector3(0, 0, -1)
	assert_eq(BaseTechManager.run_end(Vector3(3, 1, 3), Vector3(9, 0, 9), cam, fwd), Vector3(3, 1, 3), "on the power piece aimed at")
	assert_eq(BaseTechManager.run_end(null, Vector3(1, 0, -2), cam, fwd), Vector3(1, 0, -2), "where the look ray hits")
	var hand: Vector3 = BaseTechManager.run_end(null, null, cam, fwd)
	assert_lt(hand.z, -0.5, "else in the hand, ahead")
	assert_lt(hand.y, cam.y, "and a little low")
	assert_eq(BaseTechManager.run_label(7.6, 1, 14.0), "Wire 8 m · 1 spool")
	assert_eq(BaseTechManager.run_label(12.0, 2, 14.0), "Wire 12 m · 2 spools")
	assert_eq(BaseTechManager.run_label(16.2, 0, 14.0), "Wire 16 m · too long (14 m at most)")
