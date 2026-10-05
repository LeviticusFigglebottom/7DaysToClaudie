extends GutTest
## Player traversal against real physics: walking up a door-threshold step, vaulting through a
## window opening (the diner and Merrow House routes depend on it), mantling onto a crate, and
## refusing to vault a full-height wall.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _player: Player


func _box(size: Vector3, center: Vector3) -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = 1
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	add_child_autofree(b)
	b.global_position = center
	return b


func before_each() -> void:
	_box(Vector3(40, 1, 40), Vector3(0, -0.5, 0))
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = false
	add_child_autofree(_player)
	_player.bind_state(PlayerState.new())
	_player.state.stats.stamina = 100.0


func _settle() -> void:
	for i: int in 3:
		await get_tree().physics_frame


## Places the player standing at `pos` facing `forward` (horizontal).
func _place(pos: Vector3, forward: Vector3) -> void:
	_player.global_position = pos
	_player.rotation.y = atan2(-forward.x, -forward.z)
	_player.velocity = Vector3.ZERO


func _finish_vault() -> void:
	for i: int in 240:
		if not _player.is_vaulting():
			return
		_player._vault_step(1.0 / 60.0)


func test_walks_up_a_threshold_step() -> void:
	_box(Vector3(2, 0.15, 2), Vector3(3, 0.075, 0))
	await _settle()
	_place(Vector3(1.0, 0.0, 0.0), Vector3.RIGHT)
	await _settle()
	# Walk forward for a second over real physics frames.
	_player.input_enabled = true
	Input.action_press(&"move_forward")
	for i: int in 60:
		await get_tree().physics_frame
	Input.action_release(&"move_forward")
	_player.input_enabled = false
	assert_gt(_player.global_position.x, 2.0 + Player.RADIUS, "walked onto the step")
	assert_almost_eq(_player.global_position.y, 0.15, 0.04, "standing on the step")


func test_does_not_step_up_a_wall() -> void:
	_box(Vector3(0.2, 2.5, 3), Vector3(2.1, 1.25, 0))
	await _settle()
	_place(Vector3(2.0 - Player.RADIUS - 0.05, 0.0, 0.0), Vector3.RIGHT)
	_player.velocity = Vector3(3.0, 0.0, 0.0)
	_player._try_step_up(1.0 / 60.0)
	assert_almost_eq(_player.global_position.y, 0.0, 0.01)


func test_vaults_through_a_window() -> void:
	# Wall along X at z = -5 (0.2 m thick) with a 1.0 m wide opening from 0.9 m to 2.1 m.
	_box(Vector3(4, 0.9, 0.2), Vector3(0, 0.45, -5))
	_box(Vector3(4, 0.9, 0.2), Vector3(0, 2.55, -5))
	_box(Vector3(1.5, 1.2, 0.2), Vector3(-1.25, 1.5, -5))
	_box(Vector3(1.5, 1.2, 0.2), Vector3(1.25, 1.5, -5))
	await _settle()
	_place(Vector3(0, 0, -4.9 + Player.RADIUS + 0.2), Vector3.FORWARD)
	assert_true(_player._try_vault(), "vault starts at a window sill")
	_finish_vault()
	assert_false(_player.is_vaulting())
	assert_lt(_player.global_position.z, -5.1 - Player.RADIUS + 0.01, "ends beyond the wall")
	assert_almost_eq(_player.global_position.y, 0.0, 0.1, "lands on the floor inside")


func test_mantles_onto_a_crate() -> void:
	_box(Vector3(1.2, 0.8, 1.6), Vector3(0, 0.4, -3.0))
	_box(Vector3(4, 3, 0.2), Vector3(0, 1.5, -3.9))
	await _settle()
	_place(Vector3(0, 0, -2.2 + Player.RADIUS + 0.15), Vector3.FORWARD)
	assert_true(_player._try_vault())
	_finish_vault()
	assert_almost_eq(_player.global_position.y, 0.8, 0.1, "standing on the crate")


func test_refuses_a_full_height_wall() -> void:
	_box(Vector3(4, 2.6, 0.2), Vector3(0, 1.3, -5))
	await _settle()
	_place(Vector3(0, 0, -4.9 + Player.RADIUS + 0.2), Vector3.FORWARD)
	assert_false(_player._try_vault())
	assert_false(_player.is_crouching(), "no crouch left behind by a refused vault")


func test_floats_instead_of_sinking() -> void:
	# Deep water off the edge of the floor box: the surface at y = 5.
	_place(Vector3(100.0, 0.0, 0.0), Vector3.FORWARD)
	for i: int in 240:
		_player.in_water_depth = maxf(0.0, 5.0 - _player.global_position.y)
		await get_tree().physics_frame
	assert_almost_eq(_player.global_position.y, 5.0 - Player.SWIM_DEPTH, 0.3, "floats at swimming depth, eyes above water")
