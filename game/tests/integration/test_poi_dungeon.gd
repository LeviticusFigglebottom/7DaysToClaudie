extends GutTest
## POI dungeon mechanics against real nodes (ADR-0018): a trigger wakes only its own sleeper group
## (and only once, persisted); a bear trap bites and holds a real player body; a shotgun wire fires
## into the doorway; a weak floor gives way under the player and stays a hole through a
## world-state save/load; a padlock beaten off frees its door; an alarm rouses every sleeper;
## disarming pays out the trap's parts.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

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
	var raw: Dictionary = {"id": "dungeon_test", "name": "Dungeon Test", "tier": 1, "footprint": [16, 16]}
	raw.merge(layout, true)
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


## Single storey: room A (west) and B (east) with a door between, slab floor at 0.15.
func _one_storey(extra: Dictionary) -> Dictionary:
	var lay: Dictionary = {
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAAABBBB", "AAAABBBB", "AAAABBBB"], "rooms": {"A": {}, "B": {}}}],
		"openings": [
			{"id": "front", "at": [1, 2], "side": "S", "type": "door"},
			{"id": "inner", "at": [4, 1], "side": "W", "type": "door", "state": "closed"}],
		"props": [{"id": "loot_shelf", "prop": "metal_shelf", "at": [7, 0], "against": "N"}],
		"route": [{"at": [1, 4]}, {"at": [2, 1]}, {"at": [6, 1]}],
		"loot_room": {"room": "B", "level": 0}}
	lay.merge(extra, true)
	return lay


func _build(lay: Dictionary, iid: StringName = &"test/dungeon") -> PoiInstance:
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


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().physics_frame


func test_trigger_wakes_only_its_group_once() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"sleepers": [
			{"id": "g1", "group": "back", "at": [6, 1], "enemy": "hollow"},
			{"id": "g2", "group": "back", "at": [5, 2], "enemy": "hollow", "pose": "lie"},
			{"id": "loner", "at": [2, 0], "enemy": "hollow"}],
		"triggers": [{"id": "inner_opened", "group": "back", "on": "opening", "opening": "inner", "delay": 0.1}]}))
	inst.spawn_sleepers(_ai)
	await _frames(2)
	var g1: Enemy = inst.sleeper("g1")
	var g2: Enemy = inst.sleeper("g2")
	var loner: Enemy = inst.sleeper("loner")
	assert_true(g1.held and g2.held, "grouped sleepers start held")
	assert_false(loner.held)
	# Ordinary alerts (a can chime, a scream) leave the ambush alone.
	inst.alert_sleepers(g1.global_position, 30.0)
	assert_eq(g1.state, Enemy.State.SLEEP)
	assert_eq(loner.state, Enemy.State.WAKING, "an ungrouped sleeper does wake to it")
	# Opening the door fires the trigger: the group wakes, staggered.
	inst.on_opening_event("inner", g1.global_position)
	assert_true(inst.is_trigger_fired("inner_opened"))
	assert_eq(g1.state, Enemy.State.SLEEP, "nobody is up the same frame")
	inst.flush_ambush()
	assert_eq(g1.state, Enemy.State.WAKING)
	assert_eq(g2.state, Enemy.State.WAKING)
	assert_false(inst.fire_trigger("inner_opened"), "a trigger fires once")
	assert_true((Game.session.world.poi_state(&"test/dungeon")["triggers"] as Dictionary).has("inner_opened"), "persisted")


func test_spent_ambush_respawns_unheld() -> void:
	var lay: Dictionary = _one_storey({
		"sleepers": [{"id": "g1", "group": "back", "at": [6, 1], "enemy": "hollow"}],
		"triggers": [{"id": "into_b", "group": "back", "on": "room", "room": "B"}]})
	var inst: PoiInstance = _build(lay)
	inst.spawn_sleepers(_ai)
	inst.check_player_at(inst.to_global(inst.layout.cell_center(0, Vector2i(5, 1)) + Vector3.UP * 0.1))
	assert_true(inst.is_trigger_fired("into_b"), "walking into the room fires it")
	inst.despawn_sleepers(_ai)
	await _frames(1)
	var again: PoiInstance = _build(lay, &"test/dungeon")
	again.spawn_sleepers(_ai)
	assert_false(again.sleeper("g1").held, "after a reload the ambush is spent, not re-armed")
	assert_false(again.fire_trigger("into_b"), "and does not fire again")


func test_bear_trap_bites_and_holds() -> void:
	var inst: PoiInstance = _build(_one_storey({"traps": [{"id": "snap", "type": "bear_trap", "pos": [2.5, 1.5], "rot": 0}]}))
	await _frames(2)
	var trap: PoiPieces.BearTrap = inst.traps["snap"]
	var p: Player = _player_at(trap.global_position + Vector3.UP * 0.05)
	var hp: float = p.state.stats.health
	await _frames(6)
	assert_eq(inst.trap_state("snap"), "sprung")
	var dmg: float = float(Content.config(&"traps")["bear_trap"]["damage"])
	assert_almost_eq(hp - p.state.stats.health, dmg, 0.5, "the jaws bite")
	assert_gt(p.state.stats.bleeding, 0.0, "and the leg bleeds")
	assert_true(trap.is_holding())
	var held_at: Vector3 = p.global_position
	p.velocity = Vector3(4.0, 0.0, 0.0)
	await _frames(20)
	assert_almost_eq(Vector2(p.global_position.x, p.global_position.z).distance_to(Vector2(held_at.x, held_at.z)), 0.0, 0.05,
		"held in place")
	await _frames(int(float(Content.config(&"traps")["bear_trap"]["root_seconds"]) * 60.0) + 10)
	assert_false(trap.is_holding(), "the hold runs out")


func test_shotgun_wire_fires_into_the_doorway() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"openings": [
			{"id": "front", "at": [1, 2], "side": "S", "type": "door"},
			{"id": "inner", "at": [4, 1], "side": "W", "type": "open"}],
		"traps": [{"id": "gun", "type": "shotgun", "at": [4, 1], "side": "W"}]}))
	await _frames(2)
	var start: Vector3 = inst.to_global(inst.layout.cell_center(0, Vector2i(2, 1)) + Vector3.UP * 0.05)
	var p: Player = _player_at(start)
	var hp: float = p.state.stats.health
	# Walk east through the doorway at a walking pace (3 m/s).
	for i: int in 50:
		p.global_position = Vector3(start.x + 0.05 * i, p.global_position.y, start.z)
		await get_tree().physics_frame
	assert_eq(inst.trap_state("gun"), "sprung", "the wire was caught")
	assert_lt(p.state.stats.health, hp - 30.0, "the charge hit the player in the doorway")
	assert_gt(p.state.stats.bleeding, 0.0)


func test_weak_floor_collapses_and_the_hole_survives_save_load() -> void:
	var lay: Dictionary = {
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [
			{"level": 0, "plan": ["AAAAAA", "AAAAAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBBBBB", "BBBBBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "door", "at": [5, 0], "side": "E", "type": "door"}],
		"ladders": [{"level": 0, "at": [5, 1], "side": "E", "hatch": true}],
		"props": [{"id": "loot", "prop": "metal_shelf", "at": [0, 0], "against": "W", "level": 1}],
		"traps": [{"id": "rotten", "type": "weak_floor", "at": [2, 1], "level": 1}],
		"route": [{"at": [7, 0]}, {"at": [5, 0]}, {"at": [0, 0], "level": 1}],
		"loot_room": {"room": "B", "level": 1}}
	var iid := &"test/attic"
	var inst: PoiInstance = _build(lay, iid)
	await _frames(2)
	var wf: PoiPieces.WeakFloor = inst.traps["rotten"]
	var top: Vector3 = inst.to_global(inst.layout.cell_center(1, Vector2i(2, 1)))
	var p: Player = _player_at(top + Vector3.UP * 0.05)
	await _frames(3)
	assert_almost_eq(p.global_position.y, top.y, 0.1, "the rotten boards hold for a moment")
	await _frames(90)
	assert_eq(inst.trap_state("rotten"), "sprung")
	assert_true(wf.is_collapsed())
	assert_lt(p.global_position.y, top.y - 2.0, "the player went through to the floor below")
	# Save the world ledger, load it into a fresh session and rebuild the building.
	var j := JSON.new()
	assert_eq(j.parse(JSON.stringify(Game.session.world.to_dict())), OK)
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	Game.session.world.from_dict(j.data)
	var again: PoiInstance = _build(lay, iid)
	await _frames(2)
	assert_eq(again.trap_state("rotten"), "sprung", "the collapse is remembered")
	assert_null((again.traps["rotten"] as PoiPieces.WeakFloor).shape, "built as a hole: no slab to stand on")
	var space: PhysicsDirectSpaceState3D = again.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(top + Vector3.UP * 0.6, top + Vector3.DOWN * 0.6, 1)
	assert_true(space.intersect_ray(q).is_empty(), "nothing to stand on where the floor fell")


func test_padlock_beaten_off_frees_the_door() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"openings": [
			{"id": "front", "at": [1, 2], "side": "S", "type": "door"},
			{"id": "inner", "at": [4, 1], "side": "W", "type": "door", "state": "locked", "key": "pharmacy_key"}],
		"pickups": [{"id": "key", "item": "pharmacy_key", "at": [1, 0]}]}))
	await _frames(1)
	var locks: Array[Node] = inst.find_children("LockBody_*", "", true, false)
	assert_eq(locks.size(), 1, "the locked door carries a breakable padlock")
	var lock: PoiPieces.LockBody = locks[0]
	var door: PoiPieces.Door = lock.door
	assert_eq(door.state, "locked")
	assert_not_null(door.lock_mesh, "and shows it")
	var hits: int = 0
	while not lock.is_broken() and hits < 10:
		lock.take_damage(DamageInfo.make(25.0, &"blunt", &"melee"))
		hits += 1
	assert_eq(hits, int(ceil(float(Content.config(&"traps")["padlock"]["hp"]) / 25.0)))
	assert_eq(door.state, "closed", "the lock is off: the door just opens")
	assert_eq(str((inst.state["doors"] as Dictionary).get("inner", "")), "closed", "persisted")


func test_alarm_rouses_every_sleeper() -> void:
	var inst: PoiInstance = _build(_one_storey({
		"sleepers": [
			{"id": "g1", "group": "back", "at": [6, 1], "enemy": "hollow"},
			{"id": "loner", "at": [2, 0], "enemy": "hollow"}],
		"traps": [{"id": "bell", "type": "alarm", "at": [4, 1], "side": "W"}],
		"triggers": [{"id": "into_b", "group": "back", "on": "room", "room": "B"}]}))
	inst.spawn_sleepers(_ai)
	await _frames(1)
	inst.on_opening_event("inner", Vector3.ZERO)
	var alarm: PoiPieces.AlarmTrap = inst.traps["bell"]
	assert_eq(inst.trap_state("bell"), "sprung", "opening its door set it off")
	assert_true(alarm.is_ringing())
	assert_eq(inst.sleeper("g1").state, Enemy.State.WAKING, "the held ambush too")
	assert_eq(inst.sleeper("loner").state, Enemy.State.WAKING)
	assert_true(inst.is_trigger_fired("into_b"), "every ambush is spent")


func test_disarming_pays_out_parts() -> void:
	var lay: Dictionary = _one_storey({"traps": [{"id": "snap", "type": "bear_trap", "pos": [2.5, 1.5]}]})
	var inst: PoiInstance = _build(lay)
	var res: Dictionary = inst.disarm_trap("snap")
	assert_true(bool(res["ok"]))
	assert_eq(res["items"], Content.config(&"traps")["bear_trap"]["disarm_yield"])
	assert_eq(inst.trap_state("snap"), "disarmed")
	assert_false(bool(inst.disarm_trap("snap")["ok"]), "only once")
	var again: PoiInstance = _build(lay, &"test/dungeon")
	assert_false(again.traps.has("snap"), "a disarmed trap is gone from the building")
