extends GutTest
## Ezra Vane, the companion (ADR-0058 phase 1): recruited at his camp with a first aid kit or
## painkillers; follows at 3-6 m; stays; guarding, engages a hostile near his spot; never targets
## the player and shrugs the player's blows; the Hollowed pick him as a foe once he is recruited
## (not while he sits at his camp); downed at 0 hp (out of play), revived with a kit (consumed);
## bled out he is gone until the next dawn and comes back at the player's spawn point (never under
## permadeath); his state round-trips through the save; the quick order toggles follow / stay; the
## AI director neither counts nor culls him.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const CAMP_AT := Vector3(12, 0, 0)


class FakeWorld:
	extends Node3D
	var ai: Node = null
	var pois: Node = null
	var player: Node3D = null
	var building: Node = null
	var traders: Node = null
	var companion: Node = null
	var ui: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0

	func ground_below(_p: Vector3) -> float:
		return 0.0

	func drop_site() -> Vector3:
		return Vector3(-40, 0, -40)


var _prev: GameSession
var _prev_world: Node
var _world: FakeWorld
var _ai: AIDirector
var _dir: CompanionDirector
var _p: Player


func before_each() -> void:
	_start({"seed": 5801, "game_mode": "survival"})


func _start(opts: Dictionary) -> void:
	_prev = Game.session
	_prev_world = Game.world
	Game.session = GameSession.create_new(opts)
	Game.session.clock.set_time(2, 12.0)
	_world = FakeWorld.new()
	add_child_autofree(_world)
	Game.world = _world
	_ai = AIDirector.new()
	_world.add_child(_ai)
	_world.ai = _ai
	_box(Vector3(0, -0.5, 0), Vector3(400, 1, 400))
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_world.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = Vector3.ZERO
	_p.set_physics_process(false)
	_world.player = _p
	_dir = CompanionDirector.new()
	_world.add_child(_dir)
	_world.companion = _dir
	_dir.buildings_source = func() -> Array:
		return [{"id": "camp1", "def": "ezra_camp", "xf": Transform3D(Basis(), CAMP_AT)}]
	_dir.setup_world(_world)


func after_each() -> void:
	if _dir != null and is_instance_valid(_dir):
		_dir.free()
	Game.session = _prev
	Game.world = _prev_world


func _box(at: Vector3, size: Vector3) -> void:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	_world.add_child(b)
	b.global_position = at


func _give(item: StringName, n: int = 1) -> void:
	_p.state.inventory.add(ItemStack.make(item, n))


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().physics_frame


## Ezra seated at his camp (the player within its wake range).
func _seated() -> Enemy:
	_dir.tick()
	await get_tree().physics_frame
	return _dir.body


## Ezra recruited and following, the player beside his camp.
func _recruited() -> Enemy:
	var e: Enemy = await _seated()
	_p.global_position = CAMP_AT + Vector3(0, 0, 2.5)
	_give(&"first_aid_kit")
	var r: Dictionary = Game.execute(&"companion.recruit", {})
	assert_true(bool(r.get("ok", false)), "recruited: %s" % r)
	await _frames(int(e.ally.rising_t * 60.0) + 4)
	return e


func _spawn(id: StringName, at: Vector3) -> Enemy:
	return _ai.spawn(id, at, {"tier": "normal", "authored": true})


func test_the_remand_fight_the_hollowed_and_the_ashen() -> void:
	assert_true(FactionDef.hostile("remand", "hollowed"))
	assert_true(FactionDef.hostile("hollowed", "remand"), "symmetric")
	assert_true(FactionDef.hostile("ashen", "remand"))
	assert_false(FactionDef.hostile("remand", "wildlife"))
	var cd: CompanionDef = Content.get_def(&"companion", &"ezra") as CompanionDef
	assert_not_null(cd)
	assert_eq(Content.enemy(cd.enemy).archetype, "companion")
	assert_eq(Content.enemy(cd.enemy).faction, "remand")


func test_he_waits_at_his_camp_out_of_play_and_a_kit_recruits_him() -> void:
	var e: Enemy = await _seated()
	assert_not_null(e, "seated at the camp while the player is near")
	assert_eq(e.entity_id, CompanionDirector.BODY_ID)
	assert_almost_eq(e.global_position.x, CAMP_AT.x, 0.5)
	assert_false(e.is_alive(), "out of play before he is recruited: nobody's foe")
	assert_eq(_ai.alive_count(), 0, "the AI director doesn't count him")
	assert_eq(e.interact_text(_p), "Talk to the lineman")
	assert_false(bool(Game.execute(&"companion.recruit", {}).get("ok", true)), "too far, and no kit")
	_p.global_position = CAMP_AT + Vector3(0, 0, 2.5)
	assert_false(bool(Game.execute(&"companion.recruit", {}).get("ok", true)), "no kit")
	_give(&"painkillers")
	var got: Array = []
	var on_rec := func(cid: StringName) -> void: got.append(cid)
	Events.companion_recruited.connect(on_rec)
	var r: Dictionary = Game.execute(&"companion.recruit", {})
	Events.companion_recruited.disconnect(on_rec)
	assert_true(bool(r.get("ok", false)), str(r))
	assert_eq(_p.state.inventory.count_of(&"painkillers"), 0, "consumed")
	assert_eq(got, [&"ezra"])
	assert_true(_dir.recruited())
	assert_true(e.ally.recruited)
	assert_eq(e.ally.order, "follow")
	assert_true(e.is_alive(), "in play now")
	assert_eq(e.interact_text(_p), "", "getting up")


func test_he_follows_at_three_to_six_metres() -> void:
	var e: Enemy = await _recruited()
	_p.global_position = CAMP_AT + Vector3(0, 0, 25)
	var d: float = INF
	for i: int in 600:
		await get_tree().physics_frame
		d = Vector2(e.global_position.x - _p.global_position.x, e.global_position.z - _p.global_position.z).length()
		if i > 60 and d <= 6.0 and e.velocity.length() < 0.05:
			break
	assert_between(d, 1.8, 6.5, "he caught up and keeps his distance (%.1f m)" % d)
	_dir.tick()
	assert_eq(_dir.body, e, "the same body")


func test_far_off_he_is_placed_beside_the_player() -> void:
	var e: Enemy = await _recruited()
	_dir.tick()
	_p.global_position = Vector3(200, 0, 0)
	_dir.tick()
	assert_lt(e.global_position.distance_to(_p.global_position), 10.0, "past teleport_beyond: beside the player")
	_p.global_position = Vector3(170, 0, 0)
	e.global_position = Vector3(200, 0.3, 0)
	Events.player_spawned.emit(_p.state.id)
	_dir.tick()
	assert_lt(e.global_position.distance_to(_p.global_position), 10.0, "after a respawn (or sleep) further than 20 m")


func test_stay_holds_the_spot() -> void:
	var e: Enemy = await _recruited()
	var spot: Vector3 = e.global_position
	assert_true(bool(Game.execute(&"companion.order", {"order": "stay"}).get("ok", false)))
	_p.global_position = spot + Vector3(30, 0, 0)
	await _frames(180)
	assert_lt(Vector2(e.global_position.x - spot.x, e.global_position.z - spot.z).length(), 1.6, "he stayed")
	assert_false(bool(Game.execute(&"companion.order", {"order": "dance"}).get("ok", true)), "unknown order")


func test_guarding_he_engages_a_hostile_near_the_spot() -> void:
	var e: Enemy = await _recruited()
	assert_true(bool(Game.execute(&"companion.order", {"order": "guard"}).get("ok", false)))
	_p.global_position = e.global_position + Vector3(-35, 0, 0)
	var h: Enemy = _spawn(&"hollow", e.global_position + Vector3(8, 0, 0))
	var hp: float = h.health
	for i: int in 600:
		await get_tree().physics_frame
		if h.health < hp:
			break
	assert_eq(e.foe, h, "the hostile inside his guard radius")
	assert_lt(h.health, hp, "he closed and struck it")
	assert_lt(e.ally.spot.distance_to(e.global_position), 26.0, "within his leash")


func test_he_never_targets_the_player_and_shrugs_their_blows() -> void:
	var e: Enemy = await _recruited()
	e._perceive(_p, e.global_position.distance_to(_p.global_position))
	assert_lt(e.last_seen_time, -50.0, "he never 'sees' the player as quarry")
	EnemyFoes.scan(e, 1.0)
	assert_null(e.foe, "no foe: the player is no Enemy and nothing hostile is near")
	var hp: float = e.health
	var info := DamageInfo.make(30.0, &"slash", &"melee", _p.state.id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)
	assert_eq(e.health, hp, "no friendly fire")
	var php: float = _p.state.stats.health
	await _frames(60)
	assert_eq(_p.state.stats.health, php, "the player untouched")


func test_the_hollowed_pick_him_as_a_foe_once_recruited() -> void:
	var e: Enemy = await _seated()
	var h: Enemy = _spawn(&"hollow", CAMP_AT + Vector3(5, 0, 0))
	await get_tree().physics_frame
	h.set_physics_process(false)
	h.scan_foes(1.0)
	assert_null(h.foe, "not while he sits at his camp")
	_p.global_position = CAMP_AT + Vector3(0, 0, 2.5)
	_give(&"first_aid_kit")
	Game.execute(&"companion.recruit", {})
	await _frames(int(e.ally.rising_t * 60.0) + 4)
	h.global_position = e.global_position + Vector3(5, 0, 0)
	h.scan_foes(1.0)
	assert_eq(h.foe, e, "a Remand body: a foe for the Hollowed")


func test_downed_then_revived_with_a_kit() -> void:
	var e: Enemy = await _recruited()
	var h: Enemy = _spawn(&"hollow", e.global_position + Vector3(30, 0, 0))
	await get_tree().physics_frame
	h.set_physics_process(false)
	var info := DamageInfo.make(e.health + 50.0, &"zombie", &"zombie", h.entity_id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)
	assert_true(e.ally.downed, "downed, not dead")
	assert_ne(e.state, Enemy.State.DEAD)
	assert_false(e.is_alive(), "out of play: the Hollowed lose interest")
	h.foe = e
	assert_false(EnemyFoes.fighting(h), "a downed companion is dropped as a foe")
	assert_false(bool(Game.execute(&"companion.order", {"order": "stay"}).get("ok", true)), "no orders while down")
	_p.global_position = e.global_position + Vector3(1.5, 0, 0)
	assert_eq(e.interact_hold_time(_p), 0.0, "no kit: nothing to hold for")
	_give(&"cloth_bandage")
	assert_almost_eq(e.interact_hold_time(_p), 4.0, 0.01, "hold E 4 s with a bandage")
	var r: Dictionary = Game.execute(&"companion.revive", {})
	assert_true(bool(r.get("ok", false)), str(r))
	assert_eq(_p.state.inventory.count_of(&"cloth_bandage"), 0, "consumed")
	assert_false(e.ally.downed)
	assert_almost_eq(e.health / e.max_health, 0.35, 0.02)
	await _frames(int(e.ally.rising_t * 60.0) + 4)
	assert_true(e.is_alive())


func test_bled_out_he_is_back_at_the_spawn_point_next_dawn() -> void:
	var e: Enemy = await _recruited()
	_p.state.spawn_point = Vector3(30, 0, 30)
	_p.state.has_spawn_point = true
	e.ally.go_down(null, 0.05)
	await _frames(10)
	assert_true(e.ally.gone)
	_dir.tick()
	assert_null(_dir.body, "taken out of the world")
	assert_true(_dir.is_out())
	assert_eq(int(CompanionDirector.state()["out_until_day"]), 3)
	_dir.tick()
	assert_null(_dir.body, "not before the next dawn")
	Game.session.clock.set_time(3, 8.0)
	_dir.tick()
	assert_not_null(_dir.body, "back at dawn")
	assert_lt(Vector2(_dir.body.global_position.x - 30.0, _dir.body.global_position.z - 30.0).length(), 3.0, "at the player's bed")
	assert_eq(_dir.body.ally.order, "stay")
	assert_almost_eq(_dir.body.health / _dir.body.max_health, 0.5, 0.02, "wounded")


func test_under_permadeath_he_does_not_come_back() -> void:
	after_each()
	_start({"seed": 5802, "game_mode": "survival", "rules": {"death_penalty": "permadeath"}})
	var e: Enemy = await _recruited()
	e.ally.go_down(null, 0.05)
	await _frames(10)
	_dir.tick()
	assert_true(bool(CompanionDirector.state().get("dead", false)))
	Game.session.clock.set_time(5, 9.0)
	_dir.tick()
	assert_null(_dir.body, "gone for good")


func test_his_state_round_trips_through_the_save() -> void:
	var e: Enemy = await _recruited()
	Game.execute(&"companion.order", {"order": "guard", "spot": [14.0, 0.0, 6.0]})
	e.health = e.max_health * 0.4
	Events.game_saving.emit("test")
	var saved: Dictionary = Game.session.world.to_dict()
	assert_true(saved.has("companion"))
	var ws := WorldState.new()
	ws.from_dict(JSON.parse_string(JSON.stringify(saved)))
	assert_eq(str(ws.companion.get("order", "")), "guard")
	# A load: a fresh director, the body gone, the state as saved.
	_ai.despawn(e)
	_dir.free()
	await get_tree().physics_frame
	Game.session.world.companion = ws.companion
	_dir = CompanionDirector.new()
	_world.add_child(_dir)
	_world.companion = _dir
	_dir.setup_world(_world)
	_p.global_position = Vector3(14, 0, 8)
	_dir.tick()
	var b: Enemy = _dir.body
	assert_not_null(b, "respawned on load")
	assert_eq(b.entity_id, CompanionDirector.BODY_ID, "the fixed id")
	assert_true(b.ally.recruited)
	assert_eq(b.ally.order, "guard")
	assert_almost_eq(b.ally.spot, Vector3(14, 0, 6), Vector3.ONE * 0.01)
	assert_almost_eq(b.health / b.max_health, 0.4, 0.02)
	var empty := WorldState.new()
	empty.from_dict({})
	assert_true(empty.companion.is_empty(), "older saves load without him")


func test_the_quick_order_toggles_follow_and_stay() -> void:
	var e: Enemy = await _recruited()
	assert_eq(e.ally.order, "follow")
	assert_true(bool(_dir.quick_order().get("ok", false)))
	assert_eq(e.ally.order, "stay")
	_dir.quick_order()
	assert_eq(e.ally.order, "follow")
	Game.execute(&"companion.order", {"order": "guard"})
	_dir.quick_order()
	assert_eq(e.ally.order, "follow", "from guard, back to follow")
	assert_true(InputMap.has_action(&"companion_order"), "a rebindable action")


func test_the_lantern_is_lit_at_night_while_following() -> void:
	var e: Enemy = await _recruited()
	Game.session.clock.set_time(2, 23.0)
	await _frames(3)
	assert_true(e.ally.lantern_on(), "lit at night")
	Game.execute(&"companion.order", {"order": "stay"})
	await _frames(3)
	assert_false(e.ally.lantern_on(), "out while he holds a spot")


func test_the_ai_director_never_culls_him() -> void:
	var e: Enemy = await _recruited()
	_p.global_position = Vector3(0, 0, 0)
	e.global_position = Vector3(0, 0, AIDirector.DESPAWN_RANGE + 50.0)
	e.set_physics_process(false)
	assert_eq(_ai.hostiles_near(e.global_position, 5.0), 0, "never keeps the player from sleeping")
	assert_eq(_ai._roaming_count(), 0)
	assert_true(is_instance_valid(e) and _ai.enemies.has(CompanionDirector.BODY_ID))
