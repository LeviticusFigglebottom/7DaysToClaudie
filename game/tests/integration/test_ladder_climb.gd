extends GutTest
## Ladders are climbed, not used (ADR-0051): walking into one at its foot climbs it, up through its
## hatch and off onto the landing upstairs; walking into the hatch from the landing climbs back
## down; Jump lets go. Real physics, a real built POI and the real player.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _player: Player
var _inst: PoiInstance


func before_each() -> void:
	var raw: Dictionary = {"id": "t_ladder", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBB", "BBB", "BBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"ladders": [{"level": 0, "at": [1, 0], "side": "N", "hatch": true}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}, {"at": [1, 1], "level": 1}]}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	_inst = PoiBuilder.build(PoiLayout.compile(d), &"t_ladder")
	add_child_autofree(_inst)
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = false
	add_child_autofree(_player)
	_player.bind_state(PlayerState.new())
	_player.state.stats.stamina = 100.0
	for i: int in 3:
		await get_tree().physics_frame


func after_each() -> void:
	Input.action_release(&"move_forward")
	Input.action_release(&"move_back")


func _ladder() -> PoiPieces.Ladder:
	for n: Node in get_tree().get_nodes_in_group(&"ladder"):
		if _inst.is_ancestor_of(n):
			return n as PoiPieces.Ladder
	return null


## Walks forward (real input, real physics) for up to `frames` frames or until `done` is true.
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


func test_walk_up_the_ladder_and_off_onto_the_landing() -> void:
	var lad: PoiPieces.Ladder = _ladder()
	assert_not_null(lad, "the ladder is built and climbable")
	if lad == null:
		return
	assert_false(lad.has_method(&"interact"), "no interaction: it is climbed")
	var top: Vector3 = lad.ends()[0]
	_player.global_position = (lad.ends()[1] as Vector3) + lad.face() * 0.3
	_face(-lad.face())
	await get_tree().physics_frame
	await _walk(360, func() -> bool: return _player.global_position.y > top.y - 0.05 and not _player.is_climbing() and not _player.is_vaulting())
	assert_almost_eq(_player.global_position.y, top.y, 0.15, "upstairs")
	var flat := Vector2(_player.global_position.x - top.x, _player.global_position.z - top.z)
	assert_lt(flat.length(), 0.6, "on the landing beside the hatch")
	assert_false(_player.is_climbing())


func test_walk_into_the_hatch_and_down() -> void:
	var lad: PoiPieces.Ladder = _ladder()
	if lad == null:
		fail_test("no ladder")
		return
	var top: Vector3 = lad.ends()[0]
	var foot: Vector3 = lad.ends()[1]
	_player.global_position = top + Vector3.UP * 0.05
	_face(-lad.face())
	await get_tree().physics_frame
	# One walk forward: into the hatch, onto the ladder, and (forward means down until it is let go)
	# down to the foot.
	var held: Array[bool] = [false]
	await _walk(400, func() -> bool:
		held[0] = held[0] or _player.is_climbing()
		return held[0] and not _player.is_climbing())
	assert_true(held[0], "walking into the hatch takes hold of the ladder")
	assert_false(_player.is_climbing(), "off at the foot")
	assert_almost_eq(_player.global_position.y, foot.y, 0.15, "down on the floor")


func test_jump_lets_go() -> void:
	var lad: PoiPieces.Ladder = _ladder()
	if lad == null:
		fail_test("no ladder")
		return
	_player.global_position = (lad.ends()[1] as Vector3) + lad.face() * 0.3
	_face(-lad.face())
	await get_tree().physics_frame
	await _walk(40, func() -> bool: return _player.global_position.y > lad.global_position.y + 0.8)
	assert_true(_player.is_climbing(), "on the ladder")
	_player.input_enabled = true
	Input.action_press(&"jump")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(&"jump")
	_player.input_enabled = false
	assert_false(_player.is_climbing(), "let go")
