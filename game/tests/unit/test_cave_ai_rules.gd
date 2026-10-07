extends GutTest
## The Hollowed and loose things in a cave (CAVES_PLAN WS-C, ADR-0056), on the real grotto of
## helpers/cave_hill.gd carved by the real volume: ground_below reads the chamber floor (and the
## floor from the rock under it, or the plan's floor before the volume is built), so the
## fell-through rescues (Enemy._move, LooseItems) and GameWorld's spawn drop never lift a body out
## of a chamber onto the hillside; a far body glides on the cave floor, not the hill; and an enemy
## in the chamber counts as underground (always night for it).

const Hill := preload("res://tests/unit/helpers/cave_hill.gd")

var _hw: Node3D
var _tm: TerrainManager
var _plan: CavePlan
var _floor := Vector3.ZERO
var _saved_world: Node


func before_all() -> void:
	_hw = Hill.make()
	add_child(_hw)
	Hill.setup(_hw)
	_tm = _hw.get(&"terrain")
	_plan = Hill.place_grotto(_tm)
	if _plan != null and _plan.ok:
		_floor = Hill.chamber_floor(_plan)


func after_all() -> void:
	_hw.free()


func before_each() -> void:
	_saved_world = Game.world
	Game.world = _hw


func after_each() -> void:
	Game.world = _saved_world


func _ok() -> bool:
	if _plan == null or not _plan.ok:
		fail_test("the grotto didn't plan: %s" % (_plan.reason if _plan != null else "null"))
		return false
	return true


func _built() -> bool:
	if not _ok():
		return false
	assert_true(Hill.drain(_tm), "the cave's volume jobs came back")
	_tm.volume.flush()
	return true


func _enemy() -> Enemy:
	var e := Enemy.new()
	e.setup(&"test:cave", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	# Driven by hand: no brain ticking between the steps.
	e.set_physics_process(false)
	return e


func test_a_plan_floor_before_the_volume_is_built() -> void:
	if not _ok():
		return
	# What ground_below falls back on where the volume isn't built yet (a cave streaming in).
	var caves: CaveSet = _tm.caves as CaveSet
	assert_not_null(caves, "the grotto is published")
	assert_almost_eq(caves.floor_below(_floor + Vector3.UP * 1.0), _floor.y, 0.3, "the plan's chamber floor")
	var h: float = _tm.height_at(_floor.x, _floor.z)
	assert_true(is_nan(caves.floor_below(Vector3(_floor.x, h + 0.5, _floor.z))), "up on the hill: no cave floor")
	assert_true(caves.is_inside(_floor + Vector3.UP * 1.0, h), "the chamber is inside the cave")


func test_b_ground_below_in_the_built_cave() -> void:
	if not _built():
		return
	var h: float = _tm.height_at(_floor.x, _floor.z)
	assert_lt(_floor.y, h - 3.0, "the chamber is under the hill")
	assert_almost_eq(_tm.ground_below(_floor + Vector3.UP * 1.0), _floor.y, 0.4, "standing in the chamber: its floor")
	assert_almost_eq(_tm.ground_below(_floor - Vector3.UP * 2.0), _floor.y, 0.4, "sunk into the rock under it: back up to its floor")
	assert_almost_eq(_tm.ground_below(Vector3(_floor.x, h + 0.5, _floor.z)), h, 0.4, "on the hillside above: the hillside")


func test_c_enemy_in_the_chamber_is_underground_and_not_rescued() -> void:
	if not _built():
		return
	var e: Enemy = _enemy()
	e.global_position = _floor + Vector3.UP * 0.05
	assert_true(e.is_underground(), "in the chamber it is underground (always night)")
	e._move(Vector3.ZERO, 1.0 / 60.0, 20.0)
	assert_lt(e.global_position.y, _floor.y + 1.0, "the rescue leaves it in the chamber")
	# Fallen through the chamber floor: back onto it, not onto the hillside.
	e.global_position = _floor - Vector3.UP * 5.0
	e.velocity = Vector3.ZERO
	e._move(Vector3.ZERO, 1.0 / 60.0, 20.0)
	assert_almost_eq(e.global_position.y, _floor.y + 0.5, 0.5, "rescued onto the chamber floor")
	# Up on the hill it is not underground.
	var e2: Enemy = _enemy()
	e2.global_position = Vector3(_floor.x, _tm.height_at(_floor.x, _floor.z) + 0.1, _floor.z)
	assert_false(e2.is_underground(), "on the hillside above: daylight rules")


func test_d_a_far_body_glides_on_the_cave_floor() -> void:
	if not _built():
		return
	var e: Enemy = _enemy()
	e.global_position = _floor + Vector3.UP * 0.05
	# Past KINEMATIC_BEYOND: no collision, it glides on the ground under it.
	e._move(Vector3(0.5, 0.0, 0.0), 1.0 / 60.0, Enemy.KINEMATIC_BEYOND + 50.0)
	assert_almost_eq(e.global_position.y, _floor.y, 0.5, "on the chamber floor, not the hillside")
	var h: float = _tm.height_at(_floor.x, _floor.z)
	assert_almost_eq(Enemy.far_ground(_hw, Vector3(_floor.x, h + 0.2, _floor.z)), h, 0.3, "a far body on the hill stays on it")


func test_e_loose_items_stay_in_the_cave() -> void:
	if not _built():
		return
	var li := LooseItems.new()
	add_child_autofree(li)
	li.set_physics_process(false)
	li.world = _hw
	var player := Node3D.new()
	add_child_autofree(player)
	player.global_position = _floor
	_hw.set(&"player", player)
	var b := RigidBody3D.new()
	b.add_to_group(&"item_drops")
	b.freeze = true
	add_child_autofree(b)
	b.global_position = _floor + Vector3.UP * 0.2
	li._physics_process(LooseItems.CHECK_INTERVAL)
	assert_lt(b.global_position.y, _floor.y + 1.0, "a drop on the chamber floor stays there")
	b.global_position = _floor - Vector3.UP * 4.0
	li._physics_process(LooseItems.CHECK_INTERVAL)
	assert_almost_eq(b.global_position.y, _floor.y + 0.6, 0.5, "one fallen through it comes back to the floor")
	_hw.set(&"player", null)
