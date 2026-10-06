extends GutTest
## Hollowed hounds (ADR-0034) against real nodes: a pack spawned together knows itself and its
## spread; the low body lies along the ground and keeps its head; one hound's sighting rallies the
## pack, its howl spends the pack's howl; a hound breaks off after a bite; a held flame keeps the
## hounds in front of it off while one behind still closes; the world setting turns packs off.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _prev: GameSession
var _ai: AIDirector


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	_ai = AIDirector.new()
	add_child_autofree(_ai)
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(80, 1, 80)
	cs.shape = shape
	b.add_child(cs)
	add_child_autofree(b)
	b.global_position = Vector3(0, -0.5, 0)


func after_each() -> void:
	Game.session = _prev


func _pack(at := Vector3.ZERO) -> Array[Enemy]:
	var hounds: Array[Enemy] = _ai.spawn_pack(&"hollow_hound", at, {"id": "test:pack", "tier": "normal", "authored": true})
	return hounds


func _player_at(pos: Vector3) -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	p.input_enabled = false
	add_child_autofree(p)
	p.bind_state(PlayerState.new())
	p.global_position = pos
	return p


func test_a_pack_spawns_together_and_knows_itself() -> void:
	var hounds: Array[Enemy] = _pack()
	var size: Array = (Content.enemy(&"hollow_hound").beh("pack", {}) as Dictionary).get("size", [3, 5])
	assert_between(hounds.size(), int(size[0]), int(size[1]))
	var slots: Dictionary = {}
	for h: Enemy in hounds:
		assert_eq(h.pack.size(), hounds.size(), "every hound knows the whole pack")
		slots[h.pack_slot] = true
		assert_eq(h.def.archetype, "hound")
	assert_eq(slots.size(), hounds.size(), "each has its own place in the spread")


func test_the_hound_body_lies_low_along_the_ground_and_keeps_its_head() -> void:
	var h: Enemy = _pack()[0]
	await get_tree().physics_frame
	assert_almost_eq(h._shape.rotation.x, PI * 0.5, 0.001, "the capsule lies along the body")
	assert_lt(h._shape.position.y, 0.45, "low to the ground")
	assert_lt(h._eye().y - h.global_position.y, 0.8, "it sees from a dog's height")
	var info := DamageInfo.make(500.0, &"slash", &"melee", &"")
	info.hit_pos = h.global_position + Vector3.UP * 0.6
	info.dismember = 1.0
	h.take_damage(info)
	assert_false(h.severed.has("head"), "no humanoid gibs off a dog")
	assert_false(h.is_alive())


func test_one_sighting_rallies_the_pack_and_the_howl_is_spent_by_all() -> void:
	var hounds: Array[Enemy] = _pack()
	await get_tree().physics_frame
	var quarry := Vector3(20, 0, 0)
	hounds[0]._rally_pack(quarry)
	for i: int in range(1, hounds.size()):
		assert_eq(hounds[i].state, Enemy.State.CHASE, "mate %d takes up the chase" % i)
		assert_almost_eq(hounds[i].target_pos.x, quarry.x, 0.01)
	hounds[0]._howl()
	assert_eq(hounds[0].state, Enemy.State.SCREAM, "it stops to howl")
	for h: Enemy in hounds:
		assert_gt(h._howl_cd, 0.0, "one howl for the pack")


func test_a_hound_breaks_off_after_a_bite() -> void:
	var h: Enemy = _pack()[0]
	await get_tree().physics_frame
	assert_true(h._may_close(null))
	h._retreat_t = 1.2
	assert_false(h._may_close(null), "breaking off: no bite")


func test_a_held_flame_keeps_the_hounds_in_front_off() -> void:
	var p: Player = _player_at(Vector3.ZERO)
	await get_tree().physics_frame
	var eq: Node = p.get_node(^"Equipment")
	var flame := OmniLight3D.new()
	eq.add_child(flame)
	eq.set(&"_light", flame)
	eq.set(&"_light_on", true)
	assert_true(bool(eq.call(&"has_flame_on")))
	var fwd: Vector3 = -p.camera.global_transform.basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	var hounds: Array[Enemy] = _pack()
	await get_tree().physics_frame
	var front: Enemy = hounds[0]
	var behind: Enemy = hounds[1]
	front.global_position = fwd * 3.0
	behind.global_position = -fwd * 3.0
	assert_true(front._flame_shy(p), "in front of the flame it keeps off")
	assert_false(behind._flame_shy(p), "behind the player it still goes for the legs")
	assert_false(front._may_close(p))
	eq.set(&"_light_on", false)
	assert_false(front._flame_shy(p), "flame out: in it comes")


func test_the_world_setting_turns_packs_off() -> void:
	assert_true(_ai.hounds_allowed(99))
	assert_false(_ai.hounds_allowed(0), "below the hound's gamestage")
	Game.session.rules.values["hollowed_hounds"] = false
	assert_false(_ai.hounds_allowed(99))
	assert_eq(AIDirector.allowed_enemy(&"hollow_hound", 99, false), &"hollow")
