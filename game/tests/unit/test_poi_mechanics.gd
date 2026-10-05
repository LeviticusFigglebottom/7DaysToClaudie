extends GutTest
## POI dungeon mechanics (ADR-0018) at the layout / validator / state level: sleeper groups and
## triggers, trap types and placement, weak floors that must not strand the player, guardians,
## lock kinds and their approach side, stable piece ids (TD-031), re-keying old saves, and nothing
## placed over the open well of a stair flight or ladder hatch.


## A def from a layout dictionary (asserts it parses cleanly).
func _def(layout: Dictionary, id: String = "t") -> PoiDef:
	var raw: Dictionary = {"id": id, "name": "T", "tier": 2, "footprint": [16, 16]}
	raw.merge(layout, true)
	var d := PoiDef.new()
	var errs: PackedStringArray = d.parse(raw, &"poi", "test")
	assert_eq(errs, PackedStringArray(), "def parses")
	return d


## Two rooms in a row with a door between them, a front door, a loot shelf and two sleepers.
func _base() -> Dictionary:
	return {
		"levels": [{"level": 0, "plan": ["AAAABBBB", "AAAABBBB", "AAAABBBB"], "rooms": {"A": {"type": "store"}, "B": {"type": "storage"}}}],
		"openings": [
			{"id": "front", "at": [1, 2], "side": "S", "type": "door"},
			{"id": "inner", "at": [4, 1], "side": "W", "type": "door", "state": "closed"}],
		"props": [{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}],
		"sleepers": [
			{"id": "a1", "group": "back", "at": [6, 1], "enemy": "hollow"},
			{"id": "a2", "group": "back", "at": [5, 2], "enemy": "hollow", "pose": "lie"},
			{"id": "front_one", "at": [2, 0], "enemy": "hollow"}],
		"triggers": [{"id": "inner_opened", "group": "back", "on": "opening", "opening": "inner", "delay": 0.2}],
		"route": [{"at": [1, 4]}, {"at": [2, 1]}, {"at": [6, 1]}],
		"loot_room": {"room": "B", "level": 0}}


func _errors_with(v: PoiValidator, needle: String) -> int:
	var n: int = 0
	for e: String in v.errors:
		if e.contains(needle):
			n += 1
	return n


func _warnings_with(v: PoiValidator, needle: String) -> int:
	var n: int = 0
	for w: String in v.warnings:
		if w.contains(needle):
			n += 1
	return n


func test_groups_and_triggers_compile_and_validate() -> void:
	var v: PoiValidator = PoiValidator.validate(_def(_base()))
	assert_eq(v.errors, PackedStringArray())
	var l: PoiLayout = v.layout
	assert_eq(l.triggers.size(), 1)
	assert_eq(str(l.trigger("inner_opened")["group"]), "back")
	assert_eq(str(l.sleepers[0]["group"]), "back")
	assert_eq(str(l.sleepers[2]["group"]), "", "an ungrouped sleeper")
	assert_eq(v.stats["groups"], ["back"])


func test_trigger_references_are_checked() -> void:
	var lay: Dictionary = _base()
	lay["triggers"] = [
		{"id": "t_room", "group": "back", "on": "room", "room": "Z"},
		{"id": "t_open", "group": "back", "on": "opening", "opening": "nope"},
		{"id": "t_pick", "group": "back", "on": "pickup", "pickup": "nope"},
		{"id": "t_box", "group": "back", "on": "container", "prop": "nope"},
		{"id": "t_trap", "group": "back", "on": "trap", "trap": "nope"},
		{"id": "t_ghost", "group": "nobody", "on": "room", "room": "B"},
		{"id": "t_kind", "group": "back", "on": "sneeze"},
		{"id": "t_typo", "group": "back", "on": "room", "room": "B", "rooom": "B"}]
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v, "room 'Z' does not exist"), 1)
	assert_eq(_errors_with(v, "opening 'nope' not found"), 1)
	assert_eq(_errors_with(v, "pickup 'nope' not found"), 1)
	assert_eq(_errors_with(v, "prop 'nope' not found"), 1)
	assert_eq(_errors_with(v, "trap 'nope' not found"), 1)
	assert_eq(_errors_with(v, "wakes group 'nobody', but no sleeper is in it"), 1)
	assert_eq(_errors_with(v, "on 'sneeze' unknown"), 1)
	assert_eq(_errors_with(v, "unknown key 'rooom'"), 1)


func test_group_without_trigger_and_open_opening_warn() -> void:
	var lay: Dictionary = _base()
	lay["triggers"] = [{"id": "t", "group": "back", "on": "opening", "opening": "inner"}]
	(lay["sleepers"] as Array).append({"id": "lonely", "group": "attic", "at": [3, 0], "enemy": "hollow"})
	(lay["openings"] as Array)[1]["state"] = "open"
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_warnings_with(v, "group 'attic' has no trigger"), 1)
	assert_eq(_warnings_with(v, "is already open, so it never fires"), 1)


func test_ids_are_required_and_unique() -> void:
	var lay: Dictionary = _base()
	(lay["sleepers"] as Array).append({"at": [3, 1], "enemy": "hollow"})
	(lay["sleepers"] as Array).append({"id": "a1", "at": [3, 2], "enemy": "hollow"})
	lay["traps"] = [{"type": "bear_trap", "at": [2, 2]}, {"id": "Bad Id", "type": "bear_trap", "at": [3, 2]}]
	(lay["triggers"] as Array).append({"group": "back", "on": "room", "room": "B"})
	(lay["props"] as Array).append({"prop": "metal_shelf", "at": [0, 0], "against": "N"})
	(lay["props"] as Array).append({"id": "12", "prop": "metal_shelf", "at": [1, 0], "against": "N"})
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v, "sleeper 3 has no id"), 1)
	assert_eq(_errors_with(v, "duplicate sleeper id 'a1'"), 1)
	assert_eq(_errors_with(v, "trap 0 (bear_trap) has no id"), 1)
	assert_eq(_errors_with(v, "trap id 'Bad Id' must be lower_snake_case"), 1)
	assert_eq(_errors_with(v, "a trigger has no id"), 1)
	assert_eq(_errors_with(v, "prop id '12' must be lower_snake_case and not a number"), 1)
	assert_eq(_warnings_with(v, "container props have no id"), 1)


func test_trap_types_and_placement() -> void:
	var lay: Dictionary = _base()
	lay["traps"] = [
		{"id": "ok_bear", "type": "bear_trap", "at": [2, 2]},
		{"id": "yard_bear", "type": "bear_trap", "at": [-1, 1]},
		{"id": "sky_bear", "type": "bear_trap", "at": [2, 2], "level": 3},
		{"id": "mystery", "type": "piano_wire", "at": [2, 2]},
		{"id": "chime_wall", "type": "can_chime", "at": [4, 0], "side": "W"},
		{"id": "chime_door", "type": "can_chime", "at": [4, 1], "side": "W"},
		{"id": "gun_door", "type": "shotgun", "at": [4, 1], "side": "W"},
		{"id": "alarm_open", "type": "alarm", "at": [1, 1], "side": "E"},
		{"id": "boards", "type": "creaky_floor", "at": [1, 0], "size": [2, 2]},
		{"id": "boards_out", "type": "creaky_floor", "at": [6, 1], "size": [3, 1]},
		{"id": "flat_floor", "type": "weak_floor", "at": [1, 1]},
		{"id": "typo", "type": "bear_trap", "at": [3, 1], "sise": [1, 1]}]
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v, "'ok_bear'"), 0, "a bear trap in a room is fine")
	assert_eq(_errors_with(v, "'yard_bear'"), 0, "a bear trap may sit in the yard")
	assert_eq(_errors_with(v, "trap 'sky_bear' is on missing level 3"), 1)
	assert_eq(_errors_with(v, "type 'piano_wire' unknown"), 1)
	assert_eq(_errors_with(v, "trap 'chime_wall' crosses a solid wall"), 1)
	assert_eq(_errors_with(v, "'chime_door'"), 0, "a trip line across a doorway is fine")
	assert_eq(_errors_with(v, "'gun_door'"), 0)
	assert_eq(_errors_with(v, "'alarm_open'"), 0, "an alarm cord across an open passage is fine")
	assert_eq(_errors_with(v, "'boards'"), 0)
	assert_eq(_errors_with(v, "trap 'boards_out' cell (8, 1) (level 0) is not inside a room"), 1)
	assert_eq(_errors_with(v, "weak floor 'flat_floor' at (1, 1) level 0 needs a room cell directly below"), 1)
	assert_eq(_errors_with(v, "unknown key 'sise'"), 1)


func test_weak_floor_must_not_break_the_route_or_strand_the_player() -> void:
	# Upper floor is a single row the ladder lands on: a weak floor on it cuts the way to the loot.
	var lay: Dictionary = {
		"levels": [
			{"level": 0, "plan": ["AAAAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBBBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "door", "at": [5, 0], "side": "E", "type": "door"}],
		"ladders": [{"level": 0, "at": [5, 0], "side": "E", "hatch": true}],
		"props": [{"id": "loot", "prop": "metal_shelf", "at": [0, 0], "against": "W", "level": 1}],
		"traps": [{"id": "rotten", "type": "weak_floor", "at": [2, 0], "level": 1}],
		"route": [{"at": [7, 0]}, {"at": [5, 0]}, {"at": [0, 0], "level": 1}],
		"loot_room": {"room": "B", "level": 1}}
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v, "unreachable once the weak floors give way"), 1, "the only way to the loot crosses it")
	# Two rows upstairs: the loot can be reached round it, and the fall lands in a room with a door.
	lay["levels"] = [
		{"level": 0, "plan": ["AAAAAA", "AAAAAA"], "rooms": {"A": {}}},
		{"level": 1, "plan": ["BBBBBB", "BBBBBB"], "rooms": {"B": {}}}]
	var v2: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(v2.errors, PackedStringArray(), "a detour round the rotten boards keeps the route")
	# The room below is sealed (its only door bolted from outside): falling in strands the player.
	lay["levels"] = [
		{"level": 0, "plan": ["CCAAAA", "CCAAAA"], "rooms": {"A": {}, "C": {}}},
		{"level": 1, "plan": ["BBBBBB", "BBBBBB"], "rooms": {"B": {}}}]
	lay["traps"] = [{"id": "rotten", "type": "weak_floor", "at": [1, 1], "level": 1}]
	var v3: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v3, "falling through weak floor 'rotten' traps the player"), 1)


func test_nothing_stands_over_a_stairwell_or_hatch() -> void:
	# Stairs from (0, 2) rising east leave cells (0..3, 2) open on level 1; a ladder hatch opens (5, 0).
	var lay: Dictionary = {
		"levels": [
			{"level": 0, "plan": ["AAAAAA", "AAAAAA", "AAAAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBBBB", "BBBBBB", "BBBBBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "door", "at": [5, 2], "side": "E", "type": "door"}],
		"stairs": [{"level": 0, "at": [0, 2], "dir": "E"}],
		"ladders": [{"level": 0, "at": [5, 0], "side": "E", "hatch": true}],
		"props": [
			{"id": "loot", "prop": "metal_shelf", "at": [0, 0], "against": "N", "level": 1},
			{"id": "floating_shelf", "prop": "metal_shelf", "at": [1, 2], "level": 1},
			{"id": "hatch_shelf", "prop": "metal_shelf", "at": [5, 0], "level": 1},
			{"id": "notices", "prop": "cork_board", "at": [2, 2], "against": "S", "level": 1},
			{"id": "raised_shelf", "prop": "metal_shelf", "at": [0, 2], "y": 2.6, "level": 1}],
		"sleepers": [
			{"id": "fine", "at": [1, 1], "level": 1, "enemy": "hollow"},
			{"id": "hovering", "at": [2, 2], "level": 1, "enemy": "hollow"}],
		"pickups": [{"id": "drifting_key", "item": "pharmacy_key", "at": [3, 2], "level": 1}],
		"traps": [
			{"id": "well_bear", "type": "bear_trap", "at": [1, 2], "level": 1},
			{"id": "well_boards", "type": "creaky_floor", "at": [3, 1], "size": [1, 2], "level": 1},
			{"id": "hatch_rot", "type": "weak_floor", "at": [5, 0], "level": 1},
			{"id": "good_boards", "type": "creaky_floor", "at": [1, 0], "size": [2, 1], "level": 1},
			{"id": "well_chime", "type": "can_chime", "at": [3, 2], "side": "E", "level": 1},
			{"id": "landing_chime", "type": "can_chime", "at": [4, 2], "side": "W", "level": 1}],
		"route": [{"at": [7, 2]}, {"at": [4, 1]}, {"at": [0, 0], "level": 1}],
		"loot_room": {"room": "B", "level": 1}}
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	assert_eq(_errors_with(v, "sleeper 'hovering' at (2, 2) (level 1) floats over a stairwell or hatch opening"), 1)
	assert_eq(_errors_with(v, "prop 'floating_shelf' at (1, 2) level 1 floats over"), 1)
	assert_eq(_errors_with(v, "prop 'hatch_shelf' at (5, 0) level 1 floats over"), 1, "a ladder hatch is an opening too")
	assert_eq(_errors_with(v, "pickup 'drifting_key' at (3, 2) level 1 floats over"), 1)
	assert_eq(_errors_with(v, "trap 'well_bear' cell (1, 2) (level 1) floats over"), 1)
	assert_eq(_errors_with(v, "trap 'well_boards' cell (3, 2) (level 1) floats over"), 1, "only the cell over the well")
	assert_eq(_errors_with(v, "trap 'hatch_rot' cell (5, 0) (level 1) floats over"), 1)
	assert_eq(_errors_with(v, "trap 'well_chime': its 'at' cell (3, 2) (level 1) is a stairwell or hatch opening"), 1)
	for ok: String in ["'fine'", "'loot'", "'notices'", "'raised_shelf'", "'good_boards'", "'landing_chime'"]:
		assert_eq(_errors_with(v, ok), 0, "%s stands on floor, hangs on a wall or under the ceiling" % ok)
	assert_eq(_errors_with(v, "floats over"), 7, "nothing else is flagged")
	assert_eq(v.layout.stairwell_cells(0), {}, "no cellar stairs rise into level 0: it has no well")


func test_guardian_gets_the_loot_room_trigger() -> void:
	var lay: Dictionary = _base()
	(lay["sleepers"] as Array).append({"id": "boss", "guardian": true, "at": [7, 2], "enemy": "hollow"})
	(lay["sleepers"] as Array).append({"id": "stray_boss", "guardian": true, "at": [1, 1], "enemy": "hollow"})
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	var l: PoiLayout = v.layout
	var g: Dictionary = l.trigger(PoiLayout.GUARDIAN_TRIGGER)
	assert_false(g.is_empty(), "implicit trigger added")
	assert_eq(str(g["room"]), "B")
	assert_eq(str(g["group"]), PoiLayout.GUARDIAN_GROUP)
	assert_eq(str(l.sleepers[3]["group"]), PoiLayout.GUARDIAN_GROUP)
	assert_eq(_warnings_with(v, "guardian 'stray_boss' is not in the loot room"), 1)
	assert_eq(_warnings_with(v, "guardian 'boss'"), 0)
	assert_eq(_errors_with(v, "_guardian"), 0, "the implicit trigger needs no authored id")


func test_guardian_steps_up_one_infected_tier() -> void:
	assert_eq(AIDirector.guardian_tier(&"normal"), &"seeded")
	assert_eq(AIDirector.guardian_tier(&"seeded"), &"bloomed")
	assert_eq(AIDirector.guardian_tier(&"bloomed"), &"bloomed")


func test_lock_kinds_and_approach_side() -> void:
	var lay: Dictionary = _base()
	lay["openings"] = [
		{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "locked", "key": "pharmacy_key"},
		{"id": "inner", "at": [4, 1], "side": "W", "type": "door", "state": "locked", "key": "pharmacy_key", "lock": "chain"},
		{"id": "back", "at": [7, 0], "side": "E", "type": "door", "state": "locked_inside"},
		{"id": "pane", "at": [0, 1], "side": "W", "type": "window", "lock": "padlock"},
		{"id": "silly", "at": [7, 2], "side": "E", "type": "door", "state": "closed", "lock": "deadbolt"}]
	lay["pickups"] = [{"id": "key", "item": "pharmacy_key", "pos": [-1.5, 1.5]}]
	lay["triggers"] = [{"id": "t", "group": "back", "on": "room", "room": "B"}]
	var v: PoiValidator = PoiValidator.validate(_def(lay))
	var l: PoiLayout = v.layout
	assert_eq(str(l.opening("front")["lock"]), "padlock", "locked doors default to a padlock")
	assert_eq(str(l.opening("inner")["lock"]), "chain")
	assert_eq(str(l.opening("back")["lock"]), "bolt", "bolted doors default to a sliding bolt")
	assert_eq(_errors_with(v, "opening 'pane' has a lock but is not a door"), 1)
	assert_eq(_warnings_with(v, "opening 'silly' lock 'deadbolt' on a door that is not locked"), 1)
	# The front door's (1, 2) S edge: room A above (-Z side), the yard below (+Z side, "a").
	assert_eq(float(v.lock_sides["front"]), 1.0, "the padlock hangs on the street side")
	# inner: W side of cell (4, 1); "a" (+Z local = east) is room B, reached only through it.
	assert_eq(float(v.lock_sides["inner"]), -1.0, "approached from room A (west)")


func test_stable_keys_and_legacy_keys() -> void:
	var lay: Dictionary = _base()
	lay["props"] = [
		{"prop": "metal_shelf", "at": [0, 0], "against": "N"},
		{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}]
	lay["pickups"] = [{"item": "pharmacy_key", "at": [1, 1]}, {"id": "named", "item": "nails", "at": [2, 1]}]
	lay["notes"] = [{"note": "merrow_fridge", "at": [3, 1]}]
	lay["traps"] = [{"id": "snap", "type": "bear_trap", "at": [2, 2]}]
	var l: PoiLayout = PoiLayout.compile(_def(lay))
	assert_eq(str(l.props[0]["pkey"]), "0", "an unnamed prop keeps its index key")
	assert_eq(str(l.props[1]["pkey"]), "loot_shelf")
	assert_eq(str(l.pickups[0]["pid"]), "pk0")
	assert_eq(str(l.pickups[1]["pid"]), "named")
	assert_eq(str(l.pickups[2]["pid"]), "note_merrow_fridge", "notes are keyed by their note id")
	assert_eq(str(l.pickups[2]["legacy_key"]), "pk2", "...and know their old position key")
	assert_eq(str(l.traps[0]["tid"]), "snap")
	assert_eq(str(l.sleepers[0]["sid"]), "a1")


func test_v2_saves_mark_poi_states_for_rekeying() -> void:
	var trees: Dictionary = {"3_4": {"12": {"state": "stump", "day": 2}, "301": {"state": "harvested", "day": 3, "regrow": 0.0}}}
	var data: Dictionary = {"save_version": 2, "session": {"world": {
		"pois": {"town/diner": {"visited": true, "dead": ["s0"]}}, "trees": trees}}}
	var out: Dictionary = SaveSystem.migrate(data)
	assert_eq(int(out["save_version"]), SaveSystem.CURRENT_VERSION)
	assert_eq(int(out["session"]["world"]["pois"]["town/diner"]["keys"]), 1)
	assert_eq((out["session"]["world"]["trees"]["3_4"] as Dictionary).keys(), ["12"],
		"the riverbank re-scatter drops harvested plants again; stumps stay")


func test_legacy_poi_state_is_rekeyed_from_its_layout() -> void:
	var prev: GameSession = Game.session
	Game.session = GameSession.create_new({"seed": 3, "game_mode": "survival"})
	var lay: Dictionary = _base()
	lay["props"] = [
		{"prop": "metal_shelf", "at": [0, 0], "against": "N"},
		{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}]
	lay["sleepers"] = [{"id": "a1", "at": [6, 1], "enemy": "hollow"}, {"at": [2, 0], "enemy": "hollow"}]
	lay["notes"] = [{"note": "merrow_fridge", "at": [3, 1]}]
	lay["traps"] = [{"type": "bear_trap", "at": [2, 2]}]
	lay.erase("triggers")
	var w: WorldState = Game.session.world
	var iid := &"town/t"
	w.pois[String(iid)] = {"visited": true, "cleared": false, "dead": ["s1"], "broken": ["pk0"], "doors": {}, "traps": {"trap0": "triggered"}, "keys": 1}
	w.containers["c:town/t:1"] = {"opened": true, "items": [], "rolled_day": 2, "gen": 0}
	w.containers["c:town/t:0"] = {"opened": true, "items": [], "rolled_day": 3, "gen": 0}
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(_def(lay)), iid)
	assert_true(w.containers.has("c:town/t:loot_shelf"), "named container moved to its id")
	assert_false(w.containers.has("c:town/t:1"))
	assert_true(w.containers.has("c:town/t:0"), "an unnamed container keeps its index key")
	assert_eq(inst.state["dead"], ["s1"], "an unnamed sleeper keeps s<i>")
	assert_eq(inst.state["broken"], ["note_merrow_fridge"], "the taken note moved to its note id")
	assert_eq(inst.trap_state("trap0"), "sprung", "an unnamed trap keeps trap<i>")
	assert_eq(int(inst.state["keys"]), WorldState.POI_KEYS)
	inst.free()
	Game.session = prev


func test_held_sleeper_ignores_ordinary_wakes() -> void:
	var e := Enemy.new()
	e.setup(&"t:held", Content.enemy(&"hollow"), null, {"sleeper": "s", "held": true, "group": "back"})
	add_child(e)
	assert_eq(e.state, Enemy.State.SLEEP)
	e.notice(Vector3.ZERO)
	assert_eq(e.state, Enemy.State.SLEEP, "a held ambusher keeps still through other wakes")
	e.release_hold()
	e.notice(Vector3.ZERO)
	assert_eq(e.state, Enemy.State.WAKING, "released, it wakes like any sleeper")
	e.free()


func test_ambush_wakes_a_held_sleeper_alerted() -> void:
	var e := Enemy.new()
	e.setup(&"t:amb", Content.enemy(&"hollow"), null, {"sleeper": "s", "held": true, "group": "back"})
	add_child(e)
	e.ambush(Vector3(4, 0, 0))
	assert_false(e.held)
	assert_eq(e.state, Enemy.State.WAKING)
	assert_almost_eq(e.target_pos.x, 4.0, 0.001, "it knows where the intruder is")
	assert_gt(e.last_seen_time, -50.0, "and goes straight into the chase once up")
	e.free()
