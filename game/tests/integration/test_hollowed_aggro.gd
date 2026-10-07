extends GutTest
## The Hollowed's detection band (docs/AI_TUNING.md), on a flat floor in the open: by day a Hollow
## sees a walking, upright player at 30 m; crouched at 30 m it doesn't, nor crouched behind a log
## (vegetation blocks sight) much closer; a torch is a beacon at night, not by day; side-on it only
## catches movement, at closer range; one that spots you draws the awake Hollowed near it (not
## sleepers, hounds or ones far off); and a POI sleeper's eyes are as short as they were.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const TICKS: int = 8  # two seconds of perception ticks (Enemy.PERCEPTION_INTERVAL)

var _prev: GameSession
var _ai: AIDirector
var _p: Player
var _root: Node3D


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 9157, "game_mode": "survival"})
	Game.session.clock.set_time(2, 12.0)
	_root = Node3D.new()
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


func after_each() -> void:
	Game.session = _prev


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


## The player upright walking across (3.4 m/s), or crouch-walking (1.7 m/s) with the eye down.
func _stance(crouched: bool) -> void:
	_p.call(&"_set_crouch", crouched)
	_p.head.position.y = 1.0 if crouched else 1.65
	_p.velocity = Vector3(1.7 if crouched else 3.4, 0.0, 0.0)


## A Hollow `dist` m down +Z, facing the player (or side-on, looking down +X), its brain driven
## by hand (_perceive) so the measurement doesn't depend on wandering.
func _hollow(dist: float, side: bool = false, id: StringName = &"hollow", tag: String = "h") -> Enemy:
	var e: Enemy = _ai.spawn(id, Vector3(0, 0.05, dist), {"tier": "normal", "authored": true, "yaw": PI * 0.5 if side else PI, "id": "aggro:" + tag})
	return e


func _settle(enemies: Array) -> void:
	await get_tree().physics_frame
	for e: Enemy in enemies:
		e.set_physics_process(false)


func _look(e: Enemy) -> bool:
	for i: int in TICKS:
		e._perceive(_p, e.global_position.distance_to(_p.global_position))
		if e.state != Enemy.State.IDLE:
			return true
	return false


func test_by_day_an_upright_walking_player_is_seen_at_30_m() -> void:
	var e: Enemy = _hollow(30.0)
	await _settle([e])
	_stance(false)
	assert_true(_look(e), "noticed within two seconds")
	assert_eq(e.state, Enemy.State.CHASE, "it saw them and commits")


func test_by_day_a_crouched_player_at_30_m_is_not_seen() -> void:
	var e: Enemy = _hollow(30.0)
	await _settle([e])
	_stance(true)
	assert_false(_look(e), "crouched at 30 m in daylight: unnoticed")
	assert_eq(e.state, Enemy.State.IDLE)


func test_a_log_hides_a_crouched_player_much_closer() -> void:
	var e: Enemy = _hollow(12.0)
	_box(Vector3(0, 0.65, 1.5), Vector3(8, 1.3, 0.6), 1 << 12)  # a fallen log on the vegetation layer
	await _settle([e])
	_stance(true)
	assert_false(_look(e), "behind the log: unseen")
	_stance(false)
	assert_true(_look(e), "standing, their head shows over it")


func test_a_torch_is_a_beacon_at_night_not_by_day() -> void:
	var e: Enemy = _hollow(55.0)
	await _settle([e])
	_stance(false)
	var eq: Node = _p.get_node(^"Equipment")
	eq.set(&"_light_on", true)
	assert_false(_look(e), "by day a torch at 55 m is just a man with a stick")
	Game.session.clock.set_time(2, 23.0)
	assert_true(_look(e), "at night it is seen from far off")
	eq.set(&"_light_on", false)


func test_a_dark_night_costs_a_hollow_little() -> void:
	Game.session.clock.set_time(2, 23.0)
	Stimuli.current.ambient_light = 0.05  # a moonless night (GameWorld feeds the sky's light)
	var e: Enemy = _hollow(28.0)
	await _settle([e])
	_stance(false)
	assert_true(_look(e), "it sees in the dark: a walking player at 28 m (dark_sight)")
	var e2: Enemy = _hollow(28.0, false, &"hollow", "crouched")
	e2.global_position = Vector3(0, 0.05, -28.0)
	e2.rotation.y = 0.0
	_stance(true)
	assert_false(_look(e2), "crouched at 28 m in the dark: unseen")


func test_side_on_it_catches_movement_closer_in() -> void:
	var near: Enemy = _hollow(12.0, true, &"hollow", "near")
	var far: Enemy = _hollow(25.0, true, &"hollow", "far")
	far.global_position = Vector3(0, 0.05, -25.0)
	await _settle([near, far])
	_stance(false)
	assert_true(_look(near), "movement at its shoulder, 12 m off")
	assert_false(_look(far), "side-on at 25 m it doesn't")
	_p.velocity = Vector3.ZERO
	var still: Enemy = _hollow(10.0, true, &"hollow", "still")
	still.global_position = Vector3(0, 0.05, 10.0)
	await _settle([still])
	assert_false(_look(still), "a player standing still at its side isn't noticed")


func test_one_that_sees_you_draws_the_hollowed_near_it() -> void:
	var spotter: Enemy = _hollow(25.0, false, &"hollow", "spotter")
	var buddy: Enemy = _hollow(40.0, false, &"hollow", "buddy")
	buddy.rotation.y = 0.0  # looking away
	var far: Enemy = _hollow(25.0, false, &"hollow", "far")
	far.global_position = Vector3(0, 0.05, 80.0)
	var sleeper: Enemy = _ai.spawn_sleeper(&"hollow", Vector3(6, 0.05, 30.0), 0.0, "lie", &"test_poi", &"s1")
	await _settle([spotter, buddy, far, sleeper])
	buddy.rotation.y = 0.0
	_stance(false)
	assert_true(_look(spotter))
	assert_eq(buddy.state, Enemy.State.INVESTIGATE, "the one behind it comes to look")
	assert_lt(Vector2(buddy.target_pos.x, buddy.target_pos.z).length(), 1.0, "where the player is")
	assert_eq(far.state, Enemy.State.IDLE, "55 m off: out of earshot of the cry")
	assert_eq(sleeper.state, Enemy.State.SLEEP, "a sleeper sleeps on")


func test_a_poi_sleeper_still_has_short_eyes() -> void:
	var sl: Enemy = _ai.spawn_sleeper(&"hollow", Vector3(0, 0.05, 8.0), PI, "stand", &"test_poi", &"s2")
	await _settle([sl])
	_stance(false)
	for i: int in TICKS:
		sl._perceive(_p, sl.global_position.distance_to(_p.global_position))
	assert_eq(sl.state, Enemy.State.SLEEP)
	assert_eq(sl.awareness, 0.0, "8 m off by day it doesn't see you (sleep_sight_day 12 x 0.35)")
