extends GutTest
## First contact with an awake Hollow (TD-191, docs/AI_TUNING.md): a sighting is not instant; it
## stops, turns to look and commits after a short build-up (longer far off, a single beat up close),
## the suspicion drains when you drop out of sight, and a Hollow that has seen you over a fallen log
## goes round it instead of pushing into it (flat floor, no navmesh).

const PLAYER_SCENE: String = "res://src/player/player.tscn"


## Enough of a GameWorld for a body that runs its own brain: the player, a flat ground.
class FlatWorld:
	extends Node3D
	var player: Node3D = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0

	func ground_below(_p: Vector3) -> float:
		return 0.0


var _prev: GameSession
var _prev_world: Node
var _ai: AIDirector
var _p: Player
var _root: FlatWorld


func before_each() -> void:
	_prev = Game.session
	_prev_world = Game.world
	Game.session = GameSession.create_new({"seed": 9157, "game_mode": "survival"})
	Game.session.clock.set_time(2, 12.0)
	_root = FlatWorld.new()
	add_child_autofree(_root)
	_box(Vector3(0, -0.5, 0), Vector3(300, 1, 300), 1)
	var st := Stimuli.new()
	_root.add_child(st)
	st.recenter(Vector3.ZERO)
	_ai = AIDirector.new()
	_root.add_child(_ai)
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_root.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = Vector3.ZERO
	_p.set_physics_process(false)
	_p.head.position.y = 1.65


func after_each() -> void:
	Game.session = _prev
	Game.world = _prev_world


func _box(at: Vector3, size: Vector3, layer: int) -> void:
	var b := StaticBody3D.new()
	b.collision_layer = layer
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	_root.add_child(b)
	b.global_position = at


func _hollow(dist: float, tag: String) -> Enemy:
	return _ai.spawn(&"hollow", Vector3(0, 0.05, dist), {"tier": "normal", "authored": true, "yaw": PI, "id": "contact:" + tag})


func _settle(enemies: Array) -> void:
	await get_tree().physics_frame
	for e: Enemy in enemies:
		e.set_physics_process(false)


## Perception ticks (0.25 s each) until it leaves IDLE; -1 if it doesn't within `limit`.
func _ticks_to_notice(e: Enemy, limit: int = 12) -> int:
	for i: int in limit:
		e._perceive(_p, e.global_position.distance_to(_p.global_position))
		if e.state != Enemy.State.IDLE:
			return i + 1
	return -1


func test_far_off_it_takes_a_moment_up_close_it_is_at_once() -> void:
	var far: Enemy = _hollow(30.0, "far")
	var near: Enemy = _hollow(4.0, "near")
	near.global_position = Vector3(0, 0.05, -4.0)
	near.rotation.y = 0.0
	await _settle([far, near])
	_p.velocity = Vector3(3.4, 0, 0)
	far._perceive(_p, 30.0)
	assert_eq(far.state, Enemy.State.IDLE, "at 30 m one glimpse isn't enough")
	assert_between(far._notice, 0.01, 0.99, "but it has started to make you out")
	var n: int = _ticks_to_notice(far)
	assert_between(n, 3, 7, "it commits within ~1-2 s at 30 m (%d more ticks)" % n)
	assert_eq(far.state, Enemy.State.CHASE)
	assert_eq(_ticks_to_notice(near), 1, "4 m off: at once")


func test_while_it_looks_it_stops_and_turns_toward_you() -> void:
	var e: Enemy = _hollow(25.0, "look")
	e.rotation.y = PI * 0.75  # 45 degrees off: still in its eye
	e.set(&"_yaw_target", e.rotation.y)
	await _settle([e])
	e.target_pos = Vector3(30, 0, 25)
	e._set_state(Enemy.State.WANDER)
	_p.velocity = Vector3(3.4, 0, 0)
	e._perceive(_p, 25.0)
	assert_eq(e.state, Enemy.State.WANDER)
	e._physics_process(1.0 / 60.0)
	assert_lt(Vector2(e.velocity.x, e.velocity.z).length(), 0.05, "it stands still to look")
	assert_almost_eq(float(e.get(&"_yaw_target")), PI, 0.05, "and turns to face the player (-Z)")


func test_out_of_sight_the_suspicion_drains() -> void:
	var e: Enemy = _hollow(30.0, "drain")
	await _settle([e])
	_p.velocity = Vector3(3.4, 0, 0)
	e._perceive(_p, 30.0)
	e._perceive(_p, 30.0)
	var built: float = e._notice
	assert_gt(built, 0.0)
	_p.global_position = Vector3(0, 0, -200.0)  # gone
	for i: int in 12:
		e._perceive(_p, e.global_position.distance_to(_p.global_position))
	assert_eq(e._notice, 0.0, "a glimpse forgotten")
	assert_eq(e.state, Enemy.State.IDLE)


func test_a_hunting_body_and_a_hound_commit_at_once() -> void:
	var e: Enemy = _hollow(30.0, "hunt")
	var h: Enemy = _ai.spawn(&"hollow_hound", Vector3(5, 0.05, 15.0), {"tier": "normal", "authored": true, "yaw": PI, "id": "contact:hound"})
	await _settle([e, h])
	_p.velocity = Vector3(3.4, 0, 0)
	e.last_seen_time = Stimuli.current.now() - 2.0  # lost sight of you a moment ago
	e._perceive(_p, 30.0)
	assert_eq(e.state, Enemy.State.CHASE, "it had you a moment ago: no second look")
	h._perceive(_p, h.global_position.distance_to(_p.global_position))
	assert_ne(h.state, Enemy.State.IDLE, "a hound howls or runs at once (pack logic)")


func test_it_goes_round_a_log_it_saw_you_over() -> void:
	# The player stands upright 3 m behind an 8 m log (1.3 m tall, vegetation layer), head showing over it;
	# the Hollow comes from 6 m beyond it. Pushing straight in, it never arrived (aggro_probe "log").
	_box(Vector3(0, 0.65, 3.0), Vector3(8, 1.3, 0.6), 1 << 12)
	_root.player = _p
	Game.world = _root
	var e: Enemy = _hollow(9.0, "log")
	await get_tree().physics_frame
	var reached: bool = false
	var detoured: bool = false
	for i: int in 60 * 14:
		await get_tree().physics_frame
		detoured = detoured or float(e.get(&"_detour_t")) > 0.0
		var d: Vector3 = e.global_position - _p.global_position
		if Vector2(d.x, d.z).length() < 1.9:
			reached = true
			break
	assert_true(detoured, "it slid along the log")
	assert_true(reached, "and came round it to the player (at %s)" % e.global_position)
