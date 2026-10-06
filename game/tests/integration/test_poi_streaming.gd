extends GutTest
## Buildings streamed by distance (RWG v2 Phase 3, docs/RWG_V2_PLAN.md "Tests"): in a small
## synthetic streamed world (one region, one authored building from the PoiRegistry) the player's
## doings in a building survive PoiManager freeing it when the focus moves away and building it
## again when the focus comes back. Opened door stays open, the looted container stays looted, the
## killed sleeper stays dead, the per-run dressing picks (state["picks"]) come back the same and a
## pinned pick is honoured rather than re-rolled. Also: a building freed while its route check is
## still running leaves no worker task behind once the ring settles.
##
## Everything goes through the paths the game uses: PoiManager.setup_world and _update_ring (the
## ring PoiManager._process drives every RING_INTERVAL), the streamer's StepRunner for the plan and
## build steps, Door.interact / LootProp.interact (with the container.take_all command) and
## Enemy.take_damage for the kill.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
## A small one-storey house with closed inner doors, containers, ungrouped sleepers and per-run
## alternatives (ADR-0030).
const DEF: StringName = &"merrow_house"
const IID: StringName = &"test_stream/merrow"
## Far beyond streaming.json poi.free (560 m) from the building at the origin.
const FAR := Vector3(3000.0, 0.0, 0.0)
const NEAR := Vector3(-20.0, 0.0, 10.0)


## What PoiManager reads from its world (GameWorld's fields), nothing else.
class StubWorld:
	extends Node
	var terrain: TerrainManager
	var ai: Node
	var poi_registry: PoiRegistry
	var streaming: bool = true
	var boot_focus := Vector3.ZERO
	var player: Node = null
	## False: PoiManager._process leaves the ring and the sleepers alone; the test drives them.
	var is_ready: bool = false

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _world: StubWorld
var _pm: PoiManager
var _ai: AIDirector
var _steps: StepRunner


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 90210, "game_mode": "survival"})
	add_child_autofree(PlayerActions.new())
	_ai = AIDirector.new()
	add_child_autofree(_ai)
	var rt := RegionTerrain.new()
	rt.region_id = "r0"
	rt.placements = [{"kind": "poi", "def": String(DEF), "id": String(IID), "origin": [0.0, 0.0, 0.0], "rotation": 0.0, "size": [22, 24]}]
	_world = StubWorld.new()
	_world.ai = _ai
	_world.terrain = TerrainManager.new()
	_world.terrain.regions = {"r0": rt}
	# A streamer that is never set up (no compose threads): only its StepRunner, which is what
	# PoiManager queues its building steps into while the world plays.
	_world.terrain.streamer = RegionStreamer.new()
	_steps = _world.terrain.streamer.steps
	_world.poi_registry = PoiRegistry.build(null, {"r0": rt}, {}, Game.session.world_seed)
	_world.boot_focus = FAR
	add_child_autofree(_world)
	# Outside the tree, as in test_poi_ring: PoiManager only reads its regions and streamer.
	autofree(_world.terrain)
	_pm = PoiManager.new()
	add_child_autofree(_pm)
	_pm.setup_world(_world)


func after_each() -> void:
	# Joins whatever a failed test left on the worker pool before the manager goes.
	if is_instance_valid(_pm):
		for t: int in _pm._tasks + _pm._orphans:
			WorkerThreadPool.wait_for_task_completion(t)
		_pm._tasks.clear()
		_pm._orphans.clear()
		# Now, not at the end of the frame: its _exit_tree unregisters poi.disarm_trap before the
		# next test's manager registers it again.
		_pm.free()
	if is_instance_valid(_world) and _world.terrain != null and is_instance_valid(_world.terrain.streamer):
		_world.terrain.streamer.free()
	Game.session = _prev


## Runs the streaming steps (a frame's budget each) until the queue is empty.
func _settle(max_frames: int = 600) -> bool:
	for i: int in max_frames:
		if _steps.is_idle():
			return true
		_steps.run_frame()
		await get_tree().process_frame
	return _steps.is_idle()


func _ring(at: Vector3) -> void:
	_pm._update_ring(at, _pm._build_r)


func _player() -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	p.input_enabled = false
	add_child_autofree(p)
	p.bind_state(Game.local_player())
	p.global_position = Vector3(-30.0, 0.5, -30.0)
	return p


func _door(inst: PoiInstance, op_id: String) -> PoiPieces.Door:
	for n: Node in inst.find_children("*", "", true, false):
		if n is PoiPieces.Door and (n as PoiPieces.Door).op_id == op_id:
			return n
	return null


func _container(inst: PoiInstance, key: String) -> PoiPieces.LootProp:
	for n: Node in inst.find_children("*", "", true, false):
		if n is PoiPieces.LootProp and (n as PoiPieces.LootProp).prop_key == key:
			return n
	return null


## A closed, unlocked door no ambush trigger watches (opening a watched one would wake a group,
## which then roams instead of despawning: not what this test is about).
func _plain_closed_door(inst: PoiInstance) -> PoiPieces.Door:
	var watched: Dictionary = {}
	for t: Dictionary in inst.layout.triggers:
		if str(t["on"]) == "opening":
			watched[str(t["opening"])] = true
	for n: Node in inst.find_children("*", "", true, false):
		if n is PoiPieces.Door:
			var d: PoiPieces.Door = n
			if d.state == "closed" and d.partner == null and not watched.has(d.opening_id):
				return d
	return null


## A searchable container that isn't locked.
func _open_container(inst: PoiInstance) -> PoiPieces.LootProp:
	for n: Node in inst.find_children("*", "", true, false):
		if n is PoiPieces.LootProp:
			var c: PoiPieces.LootProp = n
			if c.cdef != null and not c.cdef.locked and c.prop_key != "":
				return c
	return null


## An ungrouped sleeper (no ambush hold) of the dressed layout.
func _plain_sleeper(inst: PoiInstance) -> String:
	for s: Dictionary in inst.layout.sleepers:
		if str(s["group"]) == "":
			return str(s["sid"])
	return ""


## The sleeper ids standing in the building now.
func _alive(inst: PoiInstance) -> Array:
	var out: Array = []
	for s: Dictionary in inst.layout.sleepers:
		var e: Enemy = inst.sleeper(str(s["sid"]))
		if e != null and e.is_alive() and not out.has(str(s["sid"])):
			out.append(str(s["sid"]))
	out.sort()
	return out


func _built() -> PoiInstance:
	var inst: Variant = _pm.instances.get(IID)
	return inst if is_instance_valid(inst) else null


## Brings the focus near and waits for the building to stand.
func _approach() -> PoiInstance:
	_ring(NEAR)
	assert_true(_pm._jobs.has(IID) or _pm.instances.has(IID), "queued once the focus is near")
	assert_true(await _settle(), "its plan and build steps ran out")
	return _built()


## Moves the focus away and lets the freed building leave the tree.
func _leave() -> void:
	_ring(FAR)
	assert_false(_pm.instances.has(IID), "freed beyond the free radius")
	assert_false(_pm._jobs.has(IID))
	await get_tree().process_frame
	await get_tree().process_frame


func test_state_survives_free_and_rebuild() -> void:
	assert_false(_pm.instances.has(IID), "the boot focus is far: nothing built")
	var inst: PoiInstance = await _approach()
	assert_not_null(inst, "built near the focus")
	if inst == null:
		return
	var st: Dictionary = Game.session.world.poi_state(IID)
	assert_true(st.has("picks"), "a per-run world pins the building's dressing picks")
	var picks: Dictionary = (st.get("picks", {}) as Dictionary).duplicate(true)
	assert_false(picks.is_empty(), "%s has alternatives: one pick per group" % DEF)

	var player: Player = _player()
	# Open a door.
	var door: PoiPieces.Door = _plain_closed_door(inst)
	assert_not_null(door, "a closed, unwatched door to open")
	var door_id: String = door.op_id if door != null else ""
	if door != null:
		door.interact(player)
		assert_eq(door.state, "open")
		assert_eq(inst.piece_state(door_id, "closed"), "open", "recorded in the building's state")

	# Loot a container (search it; with no UI the game takes everything: container.take_all).
	var box: PoiPieces.LootProp = _open_container(inst)
	assert_not_null(box, "a container to loot")
	var box_key: String = box.prop_key if box != null else ""
	var left: int = -1
	if box != null:
		box.interact(player)
		assert_true(box.opened, "searched")
		left = box.inventory.stacks.size()
		var cst: Dictionary = Game.session.world.container_state(box.container_id)
		assert_true(bool(cst.get("opened", false)), "recorded in the world's container state")

	# Kill a sleeper.
	inst.spawn_sleepers(_ai)
	await get_tree().physics_frame
	var sid: String = _plain_sleeper(inst)
	assert_ne(sid, "", "an ungrouped sleeper")
	var victim: Enemy = inst.sleeper(sid)
	assert_not_null(victim, "spawned")
	if victim != null:
		victim.take_damage(DamageInfo.make(9999.0, &"blunt", &"melee", Game.session.local_player_id))
		await get_tree().physics_frame
		assert_false(victim.is_alive())
	assert_true((st.get("dead", []) as Array).has(sid), "the kill is recorded")
	var alive_before: Array = _alive(inst)
	assert_false(alive_before.has(sid))

	# Away: the building is freed (sleepers put away first), its state stays in WorldState.
	await _leave()
	assert_false(is_instance_valid(inst), "the old building node is gone")
	assert_true(Game.session.world.pois.has(String(IID)), "its state stayed in WorldState")

	# Back: the same building, its state restored.
	var again: PoiInstance = await _approach()
	assert_not_null(again, "rebuilt when the focus came back")
	if again == null:
		return
	assert_eq(again.state, Game.session.world.poi_state(IID), "the same saved state")
	assert_eq(again.state.get("picks"), picks, "the same dressing picks")
	if door_id != "":
		var d2: PoiPieces.Door = _door(again, door_id)
		assert_not_null(d2, "the door is there again")
		if d2 != null:
			assert_eq(d2.state, "open", "the door opened before is still open")
	if box_key != "":
		var b2: PoiPieces.LootProp = _container(again, box_key)
		assert_not_null(b2, "the container is there again")
		if b2 != null:
			assert_true(b2.opened, "still searched")
			assert_eq(b2.inventory.stacks.size() if b2.inventory != null else 0, left, "still holds only what was left in it")
			assert_eq(b2.interact_hold_time(player), 0.0, "nothing to search again")
	again.spawn_sleepers(_ai)
	await get_tree().physics_frame
	assert_null(again.sleeper(sid), "the killed sleeper does not respawn")
	assert_eq(_alive(again), alive_before, "the others are back at their posts")

	# Settled: no worker task left behind.
	_ring(NEAR)
	assert_true(await _settle())
	assert_eq(_pm._tasks.size(), 0, "no route checks running")
	assert_eq(_pm._orphans.size(), 0, "no orphaned tasks")


func test_a_pinned_pick_is_kept_not_rerolled() -> void:
	var inst: PoiInstance = await _approach()
	assert_not_null(inst)
	if inst == null:
		return
	var st: Dictionary = Game.session.world.poi_state(IID)
	var picks: Dictionary = st.get("picks", {})
	# The "doors" group decides how the bath door stands: as_left (closed), shut (open), kicked_in
	# (broken). Pin another option than the roll, as a save made before content changed its weights
	# would carry (there is no public path to pin a pick: the saved state is what a load restores).
	var expected: Dictionary = {"as_left": "closed", "shut": "open", "kicked_in": "broken"}
	var rolled: String = str(picks.get("doors", ""))
	assert_true(expected.has(rolled), "%s rolls its doors group" % DEF)
	var other: String = "kicked_in" if rolled != "kicked_in" else "shut"
	picks["doors"] = other
	await _leave()
	var again: PoiInstance = await _approach()
	assert_not_null(again)
	if again == null:
		return
	assert_eq(str((again.state.get("picks", {}) as Dictionary).get("doors", "")), other, "the pinned pick, not a fresh roll")
	var bath: PoiPieces.Door = _door(again, "bath_door")
	assert_not_null(bath)
	if bath != null:
		assert_eq(bath.state, expected[other], "and the building is dressed by it")


func test_a_building_freed_mid_check_leaves_no_task() -> void:
	_ring(NEAR)
	assert_true(_pm._jobs.has(IID))
	# Only the plan step: it compiles the building and starts its route check on a worker.
	_steps.budget_ms = 0.0
	_steps.run_frame()
	var job: Dictionary = _pm._jobs.get(IID, {})
	assert_true(job.has("layout"), "planned")
	# Freed before its build step ran: its check is orphaned, not joined by a step.
	_ring(FAR)
	assert_true(_steps.is_idle(), "its build step was cancelled")
	assert_false(_pm._jobs.has(IID))
	assert_eq(_pm._tasks.size(), 0, "the check is no longer the build's")
	for i: int in 300:
		if _pm._orphans.is_empty():
			break
		await get_tree().process_frame
		_ring(FAR)
	assert_eq(_pm._orphans.size(), 0, "joined once done (_prune_tasks)")
	assert_eq(_pm.instances.size(), 0, "nothing built")
