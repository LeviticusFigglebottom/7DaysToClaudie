extends GutTest
## The main map builds by distance (GameWorld.poi_ring, owner report 4): every building it built
## whole at load is in its PoiRegistry under the same instance id and def, so a save made while it
## built whole keeps every building's state (WorldState.pois is keyed by instance id), and a building
## outside the boot ring takes its saved state when the ring builds it later. Run on the main map's
## own regions (WorldLoader, as GameWorld loads them; composed regions come from the disk cache).

const MAIN_MAP: String = "res://world/main_map"
## A lot of Pell's Crossing's west end in C6, ~420 m from the drop site: past the boot ring.
const FAR_LOT: StringName = &"pell_outskirts/lot_0"


## What PoiManager reads from its world (GameWorld's fields), nothing else.
class StubWorld:
	extends Node
	var terrain: TerrainManager
	var ai: Node = null
	var poi_registry: PoiRegistry = null
	var poi_lots: Dictionary = {}
	var streaming: bool = false
	var poi_ring: bool = false
	var boot_focus := Vector3(1.0e5, 0.0, 1.0e5)
	var player: Node = null
	## False: PoiManager._process leaves the ring alone; the test drives it.
	var is_ready: bool = false
	var booting: bool = true

	func is_booting() -> bool:
		return booting

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _loader: WorldLoader


func before_all() -> void:
	_loader = WorldLoader.new()
	_loader.resolve_lots = true
	_loader.world_seed = 4471
	# Built whole (every lot's building generated), as before the ring: the registry comes too.
	_loader.load_world(MAIN_MAP)


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev


func _manager(ring: bool) -> Array:
	var w := StubWorld.new()
	w.terrain = TerrainManager.new()
	w.terrain.regions = _loader.detailed
	w.poi_lots = _loader.lots
	if ring:
		w.poi_registry = _loader.registry
		w.poi_ring = true
	add_child_autofree(w)
	autofree(w.terrain)
	var pm := PoiManager.new()
	add_child(pm)
	pm.setup_world(w)
	w.booting = false
	return [pm, w]


func _free(pm: PoiManager) -> void:
	for t: int in pm._tasks + pm._orphans:
		WorkerThreadPool.wait_for_task_completion(t)
	pm._tasks.clear()
	pm._orphans.clear()
	# Now: its _exit_tree unregisters its commands before the next manager registers them.
	pm.free()


func _listing(pm: PoiManager) -> Dictionary:
	var out: Dictionary = {}
	for b: Dictionary in pm.all_buildings():
		out[StringName(str(b["id"]))] = StringName(str(b["def"]))
	return out


func test_the_ring_lists_every_building_built_whole_by_the_same_id() -> void:
	assert_true(_loader.error == "", "the main map loads: %s" % _loader.error)
	var whole: Array = _manager(false)
	var built: Dictionary = _listing(whole[0])
	(whole[0] as PoiManager).boot_steps()
	_free(whole[0])
	var ring: Array = _manager(true)
	var listed: Dictionary = _listing(ring[0])
	assert_eq((ring[0] as PoiManager).instances.size(), 0, "nothing built: the boot focus is far off")
	_free(ring[0])
	assert_gt(built.size(), 60, "the main map's buildings (C6's west end included)")
	assert_true(built.has(FAR_LOT), "the west end's lot is a building")
	for id: StringName in built:
		assert_true(listed.has(id), "%s is in the registry" % id)
		if listed.has(id):
			assert_eq(listed[id], built[id], "%s keeps its def" % id)
	for id2: StringName in listed:
		assert_true(built.has(id2), "%s was built whole too" % id2)


func test_a_building_past_the_boot_ring_takes_its_saved_state_when_built() -> void:
	var st: Dictionary = Game.session.world.poi_state(FAR_LOT)
	st["visited"] = true
	st["test_marker"] = "kept"
	var ring: Array = _manager(true)
	var pm: PoiManager = ring[0]
	assert_false(pm.instances.has(FAR_LOT), "not built at boot")
	var e: Dictionary = pm.registry.entries[FAR_LOT]
	var c: Vector2 = e["center"]
	pm._update_ring(Vector3(c.x, 0.0, c.y), 60.0)
	var steps: StepRunner = pm._own_steps
	assert_not_null(steps, "a world built whole runs the ring's steps itself")
	for i: int in 3000:
		if steps == null or steps.is_idle():
			break
		steps.run_frame()
		await get_tree().process_frame
	var inst: PoiInstance = pm.instances.get(FAR_LOT)
	assert_not_null(inst, "the ring built it")
	if inst != null:
		assert_true(bool(inst.state.get("visited", false)), "its saved state: visited")
		assert_eq(str(inst.state.get("test_marker", "")), "kept", "its saved state: every key")
	_free(pm)
