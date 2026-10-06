extends GutTest
## Base building (ADR-0035) through the build commands: a rack holds only its own resource, up to
## its capacity, shows how full it is and keeps its contents; a door swings open and shut (leaf and
## collider) and stays as it was left; stairs are a ramp you can stand on; furniture finds the log
## floor under it.

var _prev: GameSession
var _bm: BuildingManager
var _p: PlayerState


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 11, "game_mode": "slice"})
	_p = Game.session.local_player()
	_bm = BuildingManager.new()
	add_child_autofree(_bm)
	_bm.set_physics_process(false)


func after_each() -> void:
	Game.session = _prev


func _spawn(def_id: StringName, id: StringName, xf := Transform3D.IDENTITY) -> StructurePiece:
	var def: StructureDef = Content.structure(def_id)
	return _bm._spawn_piece(id, def, xf, def.hp)


func _args(id: String) -> Dictionary:
	return {"player": String(_p.id), "piece": id}


func _shown(rack: StructurePiece) -> int:
	var n: int = 0
	for f: Node3D in rack._fills:
		if f.visible:
			n += 1
	return n


func test_a_log_rack_holds_only_logs_up_to_its_capacity_and_shows_it() -> void:
	var rack: StructurePiece = _spawn(&"log_rack", &"s:rack")
	assert_eq(rack.rack_item(), &"log")
	assert_eq(rack.rack_capacity(), 12)
	assert_eq(_shown(rack), 0, "empty")
	_p.inventory.add_item(&"stick", 5)
	assert_false(bool(_bm._cmd_rack_store(_args("s:rack"))["ok"]), "sticks don't go on a log rack")
	# logs are carried a couple at a time: trips to the rack until it is full
	var trips: int = 0
	while rack.rack_count() < rack.rack_capacity() and trips < 20:
		trips += 1
		_p.inventory.add_item(&"log", 2)
		var r: Dictionary = _bm._cmd_rack_store(_args("s:rack"))
		assert_true(bool(r["ok"]))
		assert_eq(_p.inventory.count_of(&"log"), 0, "everything carried goes on")
		assert_eq(_shown(rack), int(ceil(float(rack.rack_count()) * rack._fills.size() / 12.0)), "fills as it goes")
	assert_eq(rack.rack_count(), 12, "up to its capacity")
	assert_eq(_p.inventory.count_of(&"stick"), 5)
	_p.inventory.add_item(&"log", 1)
	assert_false(bool(_bm._cmd_rack_store(_args("s:rack"))["ok"]), "no room left")
	assert_eq(_p.inventory.count_of(&"log"), 1, "it stays carried")
	_p.inventory.remove(&"log", 1)
	assert_true(bool(_bm._cmd_rack_take(_args("s:rack"))["ok"]))
	assert_eq(rack.rack_count(), 11, "one at a time")
	assert_eq(_p.inventory.count_of(&"log"), 1)
	# what a rack holds is saved with it
	rack.free()
	var again: StructurePiece = _spawn(&"log_rack", &"s:rack")
	assert_eq(again.rack_count(), 11, "it keeps its logs")
	assert_gt(_shown(again), 0)


func test_a_door_swings_and_stays_as_it_was_left() -> void:
	var door: StructurePiece = _spawn(&"stick_door", &"s:door")
	await get_tree().process_frame
	assert_false(door.door_open)
	var shut: Transform3D = door._leaf_shape.transform
	var r: Dictionary = _bm._cmd_toggle_door(_args("s:door"))
	assert_true(bool(r["ok"]) and bool(r["open"]))
	assert_true(bool(Game.session.world.flags.get("open:s:door", false)), "remembered")
	assert_gt(door._leaf_shape.transform.origin.distance_to(shut.origin), 0.3, "the leaf's collider swings out of the doorway")
	door.free()
	var again: StructurePiece = _spawn(&"stick_door", &"s:door")
	assert_true(again.door_open, "loads open")
	assert_true(bool(_bm._cmd_toggle_door(_args("s:door"))["ok"]))
	assert_false(again.door_open)
	assert_false(Game.session.world.flags.has("open:s:door"))


func test_stairs_are_a_ramp_you_can_stand_on() -> void:
	_spawn(&"log_stairs", &"s:stairs")
	for i: int in 3:
		await get_tree().physics_frame
	var space: PhysicsDirectSpaceState3D = _bm.get_world_3d().direct_space_state
	var mid := Vector3(0, 5, StructurePiece.STAIR_RUN * 0.5)
	var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(mid, mid + Vector3.DOWN * 10.0, StructurePiece.LAYER))
	assert_false(hit.is_empty(), "something to stand on half way up")
	if not hit.is_empty():
		assert_almost_eq((hit["position"] as Vector3).y, StructurePiece.STAIR_RISE * 0.5, 0.15, "half the rise half way along")


func test_furniture_finds_the_log_floor_under_it() -> void:
	var floor_y: float = 1.5
	_bm._add_piece(&"s:floor", Content.structure(&"log_piece"), Transform3D(Basis(), Vector3(0, floor_y, 0)), 400.0, true)
	for i: int in 3:
		await get_tree().physics_frame
	var bed: BlueprintDef = Content.get_def(&"blueprint", &"bough_bed") as BlueprintDef
	var fire: BlueprintDef = Content.get_def(&"blueprint", &"campfire") as BlueprintDef
	assert_true(bed.on_structures)
	assert_false(fire.on_structures, "no campfire on a wooden floor")
	var on: Vector3 = Vector3(0.5, floor_y + 0.1, 0.0)
	assert_almost_eq(_bm._structure_floor(bed, on), floor_y + LogSnapper.RADIUS, 0.01, "stands on the log's top")
	assert_eq(_bm._structure_floor(fire, on), -INF)
	assert_eq(_bm._structure_floor(bed, Vector3(9, floor_y, 9)), -INF, "no log there: the ground")
	assert_not_null(_bm.support_under(on))
