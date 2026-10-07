extends GutTest
## Climbable structures (ADR-0057) with the real Player climb (ADR-0051): walking into the hunting
## stand's ladder climbs it up through the hatch onto the deck, walking into the hatch climbs back
## down, and a climbing rope set at a ledge hangs to the ground and climbs the same way. The
## viewmodel's climbing arms take hold meanwhile. Real physics, real pieces, the real player.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _player: Player


func before_each() -> void:
	var ground := StaticBody3D.new()
	ground.collision_layer = 1
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(60, 1, 60)
	cs.shape = box
	cs.position = Vector3(0, -0.5, 0)
	ground.add_child(cs)
	add_child_autofree(ground)
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = false
	add_child_autofree(_player)
	_player.bind_state(PlayerState.new())
	_player.state.stats.stamina = 100.0


func after_each() -> void:
	Input.action_release(&"move_forward")


func _piece(id: StringName, xf: Transform3D) -> StructurePiece:
	var piece := StructurePiece.new()
	piece.setup(StringName("t_%s" % id), Content.structure(id), null)
	add_child_autofree(piece)
	piece.global_transform = xf
	return piece


func _ladder_in(n: Node) -> PoiPieces.Ladder:
	for c: Node in n.find_children("*", "", true, false):
		if c is PoiPieces.Ladder:
			return c
	return null


func _walk(frames: int, done: Callable) -> void:
	_player.input_enabled = true
	Input.action_press(&"move_forward")
	for i: int in frames:
		await get_tree().physics_frame
		if done.call():
			break
	Input.action_release(&"move_forward")
	_player.input_enabled = false
	for i: int in 3:
		await get_tree().physics_frame


func _face(dir: Vector3) -> void:
	_player.rotation.y = atan2(-dir.x, -dir.z)


func _vm() -> ViewModel:
	return _player.get_node_or_null("Head/Camera3D/ViewModel") as ViewModel


func test_up_the_hunting_stand_and_back_down() -> void:
	var piece: StructurePiece = _piece(&"hunting_stand", Transform3D(Basis(Vector3.UP, 0.4), Vector3(2, 0, 1)))
	for i: int in 3:
		await get_tree().physics_frame
	var lad: PoiPieces.Ladder = _ladder_in(piece)
	assert_not_null(lad)
	if lad == null:
		return
	var top: Vector3 = lad.ends()[0]
	_player.global_position = (lad.ends()[1] as Vector3) + lad.face() * 0.2
	_face(-lad.face())
	await get_tree().physics_frame
	var stowed: Array[bool] = [false]
	await _walk(400, func() -> bool:
		if _vm() != null and _vm().item_stowed():
			stowed[0] = true
		return _player.global_position.y > top.y - 0.05 and not _player.is_climbing() and not _player.is_vaulting())
	assert_almost_eq(_player.global_position.y, top.y, 0.15, "up on the deck")
	assert_true(stowed[0], "the arms took hold of the ladder")
	# Back down: walk into the hatch.
	_face(-lad.face())
	var held: Array[bool] = [false]
	await _walk(400, func() -> bool:
		held[0] = held[0] or _player.is_climbing()
		return held[0] and not _player.is_climbing())
	assert_true(held[0], "walking into the hatch takes hold of the ladder")
	assert_almost_eq(_player.global_position.y, lad.global_position.y, 0.2, "down on the ground")


func test_rope_hangs_from_a_ledge_and_climbs() -> void:
	# A 4 m block; the rope is set down 0.3 m from its edge, facing out over it (-Z).
	var block := StaticBody3D.new()
	block.collision_layer = 1
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(6, 4, 6)
	cs.shape = box
	block.add_child(cs)
	add_child_autofree(block)
	block.global_position = Vector3(0, 2, 3)
	var piece: StructurePiece = _piece(&"climbing_rope", Transform3D(Basis(), Vector3(0, 4, 0.3)))
	var lad: PoiPieces.Ladder = null
	for i: int in 20:
		await get_tree().physics_frame
		lad = _ladder_in(piece)
		if lad != null:
			break
	assert_not_null(lad, "the rope found the ledge")
	if lad == null:
		return
	assert_almost_eq(lad.height, 4.0, 0.05, "down to the ground")
	assert_almost_eq(lad.global_position.y, 0.0, 0.05)
	assert_almost_eq(lad.face().dot(Vector3.FORWARD), 1.0, 0.01, "out over the drop")
	var top: Vector3 = lad.ends()[0]
	_player.global_position = (lad.ends()[1] as Vector3) + lad.face() * 0.2
	_face(-lad.face())
	await get_tree().physics_frame
	var rope_hold: Array[bool] = [false]
	await _walk(500, func() -> bool:
		if _vm() != null and _vm().climb.hold == ViewModelClimb.ROPE and _vm().climb.busy():
			rope_hold[0] = true
		return _player.global_position.y > top.y - 0.05 and not _player.is_climbing() and not _player.is_vaulting())
	assert_almost_eq(_player.global_position.y, top.y, 0.15, "up on the ledge")
	assert_true(rope_hold[0], "hand over hand on the rope")
