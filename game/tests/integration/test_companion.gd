extends GutTest
## Ezra Vane, the companion (ADR-0058 phase 1): recruited at his camp with a first aid kit or
## painkillers; follows at 3-6 m; stays; guarding, engages a hostile near his spot; never targets
## the player and shrugs the player's blows; the Hollowed pick him as a foe once he is recruited
## (not while he sits at his camp); downed at 0 hp (out of play), revived with a kit (consumed);
## bled out he is gone until the next dawn and comes back at the player's spawn point (never under
## permadeath); his state round-trips through the save; the quick order toggles follow / stay; the
## AI director neither counts nor culls him.
## Phase 2: gathering fills his own pack (stones; a small tree he fells with his own blows, its logs
## on his shoulder) and stops when it is full; fetch brings what the player looked at back (into
## their pack, or at their feet); give and store empty his pack; his pack and errand round-trip
## through the save; his trees count half for the player's XP and directives.
## Phase 3: his barks are voiced from his body (the variant matching the line), rate-limited and
## silent without the sounds; his perks come with the days (a bigger pack, a third log, faster
## felling, a generator near him burns less); placed beside the player or at their bed he lands
## on the floor, out of water, walls and furniture, on the player's side of a wall; downed, the
## Hollowed keep at him a while (mauling him shortens his bleed-out); companion_strength scales him.

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
	var vegetation: Node = null
	var loose: Node = null
	var water: Node = null

	## Terrain for a test (x, z) -> height; flat when unset.
	var terrain: Callable = Callable()

	func height_at(x: float, z: float) -> float:
		return float(terrain.call(x, z)) if terrain.is_valid() else 0.0

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


## Stands in for BuildingManager: the pieces by id (CompanionDirector.nearest_storage reads them).
class FakeBuilding:
	extends Node3D
	var pieces: Dictionary = {}


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
	var acts := PlayerActions.new()
	acts.world = _world
	_world.add_child(acts)
	var loose := LooseItems.new()
	_world.add_child(loose)
	_world.loose = loose
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
	assert_true(e.is_alive(), "the Hollowed keep at him a while (downed.linger)")
	e.ally._linger_until = e._now() - 0.1
	assert_false(e.is_alive(), "then out of play: the Hollowed lose interest")
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
	# Under load the director's own tick may already have taken the body out in those frames.
	if is_instance_valid(e):
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


# --- Phase 2: gather, fetch, give, store ------------------------------------------------------------

## A vegetation manager with these instances ([species, position]) in chunk (0, 0): trees get their
## collision bodies (as near the player) unless `bodies` is false (as far from them), the rest are
## harvestable.
func _veg(list: Array, bodies: bool = true) -> VegetationManager:
	var vm := VegetationManager.new()
	_world.add_child(vm)
	_world.vegetation = vm
	var key := Vector2i(0, 0)
	var layers: Dictionary = {"tree": [], "medium": [], "ground": []}
	for i: int in list.size():
		var inst := VegetationScatter.Instance.new()
		inst.index = i
		inst.species = StringName(str(list[i][0]))
		inst.pos = list[i][1]
		inst.scale = 1.0
		inst.tilt = Vector2.ZERO
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		(layers["tree" if sp.veg_kind == "tree" else "ground"] as Array).append(inst)
	vm._data[key] = layers
	vm._pickable[key] = vm._bin_pickables(vm._harvestables(layers))
	for inst2: VegetationScatter.Instance in layers["tree"] if bodies else []:
		var id: StringName = VegetationScatter.instance_id(key, inst2.index)
		vm._bodies[id] = vm._make_body(id, key, inst2, Content.get_def(&"species", inst2.species) as SpeciesDef)
	return vm


## Turns the player (yaw) and their head (pitch) to look at `at`.
func _aim(at: Vector3) -> void:
	var d: Vector3 = at - _p.camera.global_position
	_p.rotation.y = atan2(-d.x, -d.z)
	_p.head.rotation.x = atan2(d.y, Vector2(d.x, d.z).length())


## Runs physics frames until `done` holds (or `limit` frames).
func _until(done: Callable, limit: int) -> void:
	for i: int in limit:
		await get_tree().physics_frame
		if bool(done.call()):
			return


func test_gathering_stone_fills_his_pack_and_stops_when_full() -> void:
	var e: Enemy = await _recruited()
	var spot := Vector3(20, 0, 10)
	var list: Array = []
	for i: int in 8:
		list.append(["loose_stone", spot + Vector3(float(i % 4) * 0.7, 0.0, float(i / 4) * 0.7)])
	var vm: VegetationManager = _veg(list)
	# Most of a pack's worth already: a few stones more and he is full (15 is the carry cap).
	_dir.inventory.add_item(&"stone", 11)
	var lines: Array = []
	var on_msg := func(t: String, _k: StringName) -> void: lines.append(t)
	Events.player_status_message.connect(on_msg)
	var r: Dictionary = Game.execute(&"companion.order", {"order": "gather", "kind": "stone", "spot": [spot.x, 0.0, spot.z]})
	assert_true(bool(r.get("ok", false)), str(r))
	assert_eq(e.ally.order, "gather")
	await _until(func() -> bool: return e.ally.order == "follow", 1500)
	Events.player_status_message.disconnect(on_msg)
	assert_eq(e.ally.order, "follow", "full, he came back to follow")
	assert_eq(_dir.inventory.count_of(&"stone"), 15, "a full pack: the stone carry cap")
	assert_eq(_p.state.inventory.count_of(&"stone"), 0, "into his own pack, not the player's")
	var harvested: int = 0
	for inst: VegetationScatter.Instance in vm._data[Vector2i(0, 0)]["ground"]:
		if vm._is_removed(Vector2i(0, 0), inst.index):
			harvested += 1
	assert_between(harvested, 2, 4, "he stopped when full (%d of 8 picked)" % harvested)
	assert_lt(e.global_position.distance_to(_p.global_position), 7.0, "back with the player")
	assert_true(lines.any(func(l: String) -> bool: return l in _dir.cdef.barks["full"]), "and says so: %s" % [lines])
	assert_false(bool(Game.execute(&"companion.order", {"order": "gather", "kind": "stone"}).get("ok", true)), "no room: refused")
	assert_false(bool(Game.execute(&"companion.order", {"order": "gather", "kind": "gold"}).get("ok", true)), "unknown kind")


func test_gathering_wood_he_fells_a_small_tree_for_half_the_credit() -> void:
	var e: Enemy = await _recruited()
	var tracker := DirectiveTracker.new()
	tracker.world = _world
	_world.add_child(tracker)
	tracker.setup_world(_world)
	# Recruited in chapter 1: the tracker credits his directive on setup (deferred; ADR-0062).
	await _frames(1)
	assert_true(_p.state.directives.done.has(&"find_lineman"), "recruited before his chapter: Find the lineman counts")
	var tree_at := Vector3(22, 0, 14)
	var vm: VegetationManager = _veg([["paper_birch", tree_at], ["hollow_larch", tree_at + Vector3(4, 0, 0)]])
	_p.global_position = Vector3(0, 0, -6)
	var felled: Array = []
	var on_fell := func(_id: StringName, _pos: Vector3, by: StringName) -> void: felled.append(by)
	Events.tree_felled.connect(on_fell)
	var xp0: int = _p.state.progression.xp
	var r: Dictionary = Game.execute(&"companion.order", {"order": "gather", "kind": "wood", "spot": [tree_at.x, 0.0, tree_at.z]})
	assert_true(bool(r.get("ok", false)), str(r))
	await _until(func() -> bool: return e.ally.order == "follow", 3000)
	Events.tree_felled.disconnect(on_fell)
	assert_eq(felled, [CompanionDirector.BODY_ID], "he felled the birch with his own blows")
	assert_true(vm._is_removed(Vector2i(0, 0), 0), "a stump")
	assert_false(vm._is_removed(Vector2i(0, 0), 1), "the larch is too big a tree for him")
	assert_between(_dir.inventory.count_of(&"log"), 1, 2, "its logs on his shoulder (two at most)")
	assert_eq(_p.state.inventory.count_of(&"log"), 0)
	assert_eq(_p.state.progression.xp - xp0, 5, "half a felled tree's XP")
	assert_eq(_p.state.directives.count_of(&"arrival_fell"), 0, "half a directive tree")
	Events.tree_felled.emit(&"veg:0_0:9", Vector3.ZERO, CompanionDirector.BODY_ID)
	assert_eq(_p.state.directives.count_of(&"arrival_fell"), 1, "two of his make one")
	Events.tree_felled.emit(&"veg:0_0:8", Vector3.ZERO, _p.state.id)
	assert_eq(_p.state.directives.count_of(&"arrival_fell"), 2, "the player's own count whole")
	tracker.free()


func test_fetch_brings_back_what_the_player_looked_at() -> void:
	var e: Enemy = await _recruited()
	await _until(func() -> bool: return e.velocity.length() < 0.05, 240)
	var drop: ItemDrop = ItemDrop.spawn(_world, ItemStack.make(&"cloth_bandage", 3), _p.global_position + Vector3(14, 0.3, 6))
	await _frames(30)
	assert_false(bool(Game.execute(&"companion.order", {"order": "fetch"}).get("ok", true)), "nothing looked at yet")
	_aim(drop.global_position)
	await get_tree().physics_frame
	_dir.tick()
	assert_eq(_dir.looked, {"entity": String(drop.entity_id)}, "the look ray found it")
	_aim(e.global_position + Vector3.UP)
	await get_tree().physics_frame
	_dir.tick()
	assert_eq(_dir.looked, {"entity": String(drop.entity_id)}, "looking at him to give the order keeps it")
	var r: Dictionary = Game.execute(&"companion.order", {"order": "fetch"})
	assert_true(bool(r.get("ok", false)), str(r))
	await _until(func() -> bool: return e.ally.order == "follow", 1500)
	assert_eq(e.ally.order, "follow")
	assert_false(is_instance_valid(drop) and not drop.is_queued_for_deletion(), "taken off the ground")
	assert_eq(_p.state.inventory.count_of(&"cloth_bandage"), 3, "handed over")
	assert_true(_dir.inventory.is_empty(), "nothing kept back")
	var far: ItemDrop = ItemDrop.spawn(_world, ItemStack.make(&"stone", 1), _p.global_position + Vector3(80, 0.3, 0))
	await get_tree().physics_frame
	assert_false(bool(Game.execute(&"companion.order", {"order": "fetch", "target": {"entity": String(far.entity_id)}}).get("ok", true)),
		"past fetch.range")


func test_a_fetched_log_lands_at_the_feet_of_a_full_shoulder() -> void:
	var e: Enemy = await _recruited()
	_give(&"log", 2)
	var lg: LogEntity = _world.loose.spawn_log(_p.global_position + Vector3(12, 0.3, 4), Basis(), &"")
	await _frames(20)
	var r: Dictionary = Game.execute(&"companion.order", {"order": "fetch", "target": {"entity": String(lg.entity_id)}})
	assert_true(bool(r.get("ok", false)), str(r))
	await _until(func() -> bool: return e.ally.order == "follow", 1500)
	assert_false(is_instance_valid(lg) and not lg.is_queued_for_deletion(), "he picked it up")
	assert_eq(_p.state.inventory.count_of(&"log"), 2, "the player's shoulder was full")
	var near: int = 0
	for n: Node in get_tree().get_nodes_in_group(&"logs"):
		if not n.is_queued_for_deletion() and (n as Node3D).global_position.distance_to(_p.global_position) < 4.0:
			near += 1
	assert_eq(near, 1, "dropped at the player's feet")
	assert_eq(_dir.inventory.count_of(&"log"), 0)


func test_give_me_what_you_carry() -> void:
	var e: Enemy = await _recruited()
	assert_false(bool(Game.execute(&"companion.give", {}).get("ok", true)), "he carries nothing")
	_dir.inventory.add_item(&"log", 2)
	_dir.inventory.add_item(&"stick", 7)
	_give(&"log", 1)
	e.global_position = _p.global_position + Vector3(2, 0, 0)
	var logs0: int = get_tree().get_nodes_in_group(&"logs").size()
	var r: Dictionary = Game.execute(&"companion.give", {})
	assert_true(bool(r.get("ok", false)), str(r))
	assert_eq(_p.state.inventory.count_of(&"stick"), 7)
	assert_eq(_p.state.inventory.count_of(&"log"), 2, "what fits on the player's shoulder")
	assert_eq(get_tree().get_nodes_in_group(&"logs").size(), logs0 + 1, "the rest at their feet")
	assert_true(_dir.inventory.is_empty())
	_dir.inventory.add_item(&"stone", 2)
	e.global_position = _p.global_position + Vector3(20, 0, 0)
	assert_false(bool(Game.execute(&"companion.give", {}).get("ok", true)), "too far to hand over")


func test_store_at_base_fills_the_nearest_crate() -> void:
	var e: Enemy = await _recruited()
	var b := FakeBuilding.new()
	_world.add_child(b)
	_world.building = b
	assert_false(bool(Game.execute(&"companion.store", {}).get("ok", true)), "he carries nothing")
	_dir.inventory.add_item(&"stone", 5)
	_dir.inventory.add_item(&"stick", 3)
	assert_false(bool(Game.execute(&"companion.store", {}).get("ok", true)), "no storage")
	var crate := StructurePiece.new()
	crate.setup(&"p:crate", Content.structure(&"storage_crate"), b)
	b.add_child(crate)
	crate.global_position = e.global_position + Vector3(-10, 0, 6)
	b.pieces[&"p:crate"] = crate
	var r: Dictionary = Game.execute(&"companion.store", {})
	assert_true(bool(r.get("ok", false)), str(r))
	assert_eq(e.ally.order, "store")
	await _until(func() -> bool: return e.ally.order == "follow", 1200)
	assert_eq(e.ally.order, "follow", "stored, back to following")
	assert_eq(crate.inventory.count_of(&"stone"), 5)
	assert_eq(crate.inventory.count_of(&"stick"), 3)
	assert_true(_dir.inventory.is_empty())
	assert_eq((Game.session.world.container_state(&"p:crate").get("items", []) as Array).size(), 2, "the crate's contents persist")


func test_his_pack_and_errand_round_trip_through_the_save() -> void:
	var e: Enemy = await _recruited()
	_dir.inventory.add_item(&"log", 2)
	_dir.inventory.add_item(&"plant_fiber", 9)
	Game.execute(&"companion.order", {"order": "gather", "kind": "fibre", "spot": [30.0, 0.0, 12.0]})
	Events.game_saving.emit("test")
	var ws := WorldState.new()
	ws.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	_ai.despawn(e)
	_dir.free()
	await get_tree().physics_frame
	Game.session.world.companion = ws.companion
	_dir = CompanionDirector.new()
	_world.add_child(_dir)
	_world.companion = _dir
	_dir.setup_world(_world)
	assert_eq(_dir.inventory.count_of(&"log"), 2, "his pack loads")
	assert_eq(_dir.inventory.count_of(&"plant_fiber"), 9)
	assert_eq(_dir.inventory.max_slots, 16, "12 and the Pack mule perk's 4")
	_dir.tick()
	var b: Enemy = _dir.body
	assert_not_null(b)
	assert_eq(b.ally.order, "gather", "the errand loads")
	assert_eq(b.ally.work.kind, "fibre")
	assert_almost_eq(b.ally.work.spot, Vector3(30, 0, 12), Vector3.ONE * 0.01)
	assert_eq(b.ally.inventory, _dir.inventory)
	# Bled out, he loses what he carried.
	b.ally.go_down(null, 0.05)
	await _frames(10)
	_dir.tick()
	assert_true(_dir.inventory.is_empty(), "lost with him")


# --- Phase 3: voice, perks, placement, downed, strength ------------------------------------------

## Stands in for WaterSystem: water deeper than wading everywhere `wet` says so.
class FakeWater:
	extends Node
	var wet: Callable

	func depth_at(pos: Vector3) -> float:
		return 1.2 if bool(wet.call(pos)) else 0.0


func test_his_barks_are_voiced_and_rate_limited() -> void:
	var e: Enemy = await _recruited()
	var m: CompanionMind = e.ally
	assert_eq(m.last_voice, "voice/ezra_recruited", "recruited: his voice too")
	var lines: Array = []
	var on_msg := func(t: String, _k: StringName) -> void: lines.append(t)
	Events.player_status_message.connect(on_msg)
	m._voice_t = -1000.0
	m.bark("spotted")
	assert_eq(lines.size(), 1, "the status-bar line still shows")
	assert_eq(m.last_voice, "voice/ezra_spotted")
	var shown: int = (m.cdef.barks["spotted"] as Array).find(lines[0])
	assert_eq(m.last_voice_variant, shown + 1, "the variant matching the line shown")
	m.bark("spotted")
	assert_eq(lines.size(), 1, "said on his own: not again within voice.repeat")
	m.bark("follow")
	assert_eq(lines.size(), 2, "an order's answer always shows")
	assert_eq(m.last_voice, "voice/ezra_spotted", "but not voiced within voice.gap of the last")
	m._voice_t = -1000.0
	m.bark("stay")
	assert_eq(m.last_voice, "voice/ezra_stay", "every order answer has its own line (TD-309)")
	var stay_shown: int = (m.cdef.barks["stay"] as Array).find(lines[2])
	assert_eq(m.last_voice_variant, stay_shown + 1, "spoken as shown")
	m.bark("downed")
	assert_eq(m.last_voice, "voice/ezra_downed", "urgent barks cut in")
	Events.player_status_message.disconnect(on_msg)
	var voice: Node = e.get_node_or_null(^"Voice")
	if Audio.variants(&"voice/ezra_stay").is_empty():
		assert_null(voice, "no sounds generated: silent, no player made")
	else:
		assert_true(voice is Sound3D and (voice as Sound3D).playing, "played from his body")


func test_downed_the_hollowed_keep_at_him_a_while() -> void:
	var e: Enemy = await _recruited()
	var h: Enemy = _spawn(&"hollow", e.global_position + Vector3(1.2, 0, 0))
	await get_tree().physics_frame
	h.set_physics_process(false)
	var info := DamageInfo.make(e.health + 50.0, &"zombie", &"zombie", h.entity_id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)
	assert_true(e.ally.downed)
	h.foe = e
	h._foe_seen = h._now()
	h._set_state(Enemy.State.ATTACK)
	assert_true(EnemyFoes.fighting(h), "still at him just after he went down")
	var t0: float = e.ally.downed_t
	e.take_damage(info)
	assert_almost_eq(e.ally.downed_t, t0 - 6.0, 0.01, "mauled where he lies: he bleeds out the faster")
	assert_eq(e.health, 0.0, "no health to lose")
	var pinfo := DamageInfo.make(30.0, &"slash", &"melee", _p.state.id)
	e.take_damage(pinfo)
	assert_almost_eq(e.ally.downed_t, t0 - 6.0, 0.01, "the player's blows never count")
	e.ally._linger_until = e._now() - 0.1
	assert_false(EnemyFoes.fighting(h), "after downed.linger they lose interest")
	# A downed body loaded from a save is out of play at once.
	e.ally.get_up(0.5)
	e.ally.go_down(null, 60.0)
	assert_false(e.is_alive())


func test_downed_only_those_already_on_him_keep_him() -> void:
	var e: Enemy = await _recruited()
	var a: Enemy = _spawn(&"hollow", e.global_position + Vector3(1.2, 0, 0))
	await get_tree().physics_frame
	a.set_physics_process(false)
	a.foe = e
	a._foe_seen = a._now()
	assert_true(e.ally.open_to(a), "standing, anyone may take him up")
	var info := DamageInfo.make(e.health + 50.0, &"zombie", &"zombie", a.entity_id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)
	assert_true(e.ally.downed)
	assert_true(e.ally.open_to(a), "the one on him when he fell keeps him")
	var b: Enemy = _spawn(&"hollow", e.global_position + Vector3(-3.0, 0, 0))
	await get_tree().physics_frame
	b.set_physics_process(false)
	assert_false(e.ally.open_to(b), "a newcomer doesn't join in")
	EnemyFoes.scan(b, 5.0)
	assert_ne(b.foe, e, "its scan passes him by while he lies there")
	e.ally.get_up(0.5)
	assert_true(e.ally.open_to(b), "on his feet again, he is anyone's foe")


func test_his_blows_and_hurts_have_his_own_voice() -> void:
	var own: bool = not Audio.variants(&"voice/ezra_grunt").is_empty()
	assert_eq(CompanionMind.voice(&"voice/zombie_attack"), &"voice/ezra_grunt" if own else &"voice/ashen_grunt",
		"his own grunt when it is generated (TD-303)")
	var pain: bool = not Audio.variants(&"voice/ezra_pain").is_empty()
	assert_eq(CompanionMind.voice(&"voice/zombie_pain"), &"voice/ezra_pain" if pain else &"voice/ashen_pain")
	assert_eq(CompanionMind.voice(&"voice/zombie_death"), &"voice/ashen_death", "he has no death cry of his own")


func test_the_logs_ride_his_shoulder_bone() -> void:
	var e: Enemy = await _recruited()
	_dir.inventory.add_item(&"log", 2)
	e.ally._shoulder_logs()
	var node: Node3D = e.ally._shoulder
	assert_not_null(node, "logs on his shoulder")
	assert_eq(node.get_child_count(), 2, "one per log")
	if e.visual.skeleton != null:
		assert_true(node.get_parent() is BoneAttachment3D, "on a bone, so they follow his clips (TD-305)")
	await _frames(2)
	var want: Vector3 = e.global_transform * CompanionMind.SHOULDER_AT
	assert_lt(node.global_position.distance_to(want), 0.4, "over his right shoulder (%s vs %s)" % [node.global_position, want])


func test_the_card_marks_what_fetch_would_bring() -> void:
	await _recruited()
	var lg: LogEntity = _world.loose.spawn_log(_p.global_position + Vector3(6, 0.3, 2), Basis(), &"")
	await _frames(10)
	_dir.looked = {"entity": String(lg.entity_id)}
	var card := CompanionScreen.new()
	card.director = _dir
	add_child_autofree(card)
	card.open()
	var mk: Node3D = card._marker
	assert_not_null(mk, "a marker in the world (TD-307)")
	assert_true(mk.visible)
	assert_lt(mk.global_position.distance_to(lg.global_position), 0.05, "on the log")
	card.close_screen()
	assert_false(mk.visible, "gone with the card")
	card.open()
	_dir.looked = {}
	card._refresh()
	assert_false(mk.visible, "nothing looked at, nothing marked")
	card.close_screen()


func test_he_fells_a_tree_away_from_the_player_with_no_collision_body() -> void:
	var e: Enemy = await _recruited()
	var tree_at := Vector3(22, 0, 14)
	var vm: VegetationManager = _veg([["paper_birch", tree_at]], false)
	assert_null(vm.body_for(Vector2i(0, 0), vm._data[Vector2i(0, 0)]["tree"][0]), "no body, as far from the player")
	_p.global_position = Vector3(0, 0, -6)
	var r: Dictionary = Game.execute(&"companion.order", {"order": "gather", "kind": "wood", "spot": [tree_at.x, 0.0, tree_at.z]})
	assert_true(bool(r.get("ok", false)), str(r))
	await _until(func() -> bool: return e.ally.order == "follow", 3000)
	assert_true(vm._is_removed(Vector2i(0, 0), 0), "felled all the same (TD-304)")
	assert_between(_dir.inventory.count_of(&"log"), 1, 2, "and its logs brought in")


func test_a_far_target_is_reached_round_a_cliff_not_through_it() -> void:
	await _recruited()
	# A 30 m high wall of rock across x = 60 from z = -200 to z = 40, with open ground round its
	# north end (z > 40): from (0, 0) to (120, 0) the straight line runs into it.
	_world.terrain = func(x: float, z: float) -> float:
		return 30.0 if absf(x - 60.0) < 8.0 and z > -200.0 and z < 40.0 else 0.0
	var f: FlowField = CompanionWork.route(Vector3(0, 0, 0), Vector3(120, 0, 0))
	assert_not_null(f, "a route is built")
	var dir: Vector3 = f.direction_at(Vector3(0, 0, 0))
	assert_gt(dir.z, 0.3, "it heads round the open end, not at the cliff (%s)" % dir)
	# Walk the route: it gets there without crossing the rock.
	var at := Vector3(0, 0, 0)
	var crossed: bool = false
	for i: int in 400:
		var d: Vector3 = f.direction_at(at)
		if d == Vector3.ZERO:
			break
		at += d * 3.0
		if absf(at.x - 60.0) < 8.0 and at.z > -200.0 and at.z < 40.0:
			crossed = true
	assert_false(crossed, "never across the rock")
	assert_lt(Vector2(at.x - 120.0, at.z).length(), 8.0, "and arrives (%s)" % at)
	_world.terrain = Callable()


func test_his_gear_shows_as_he_uses_it() -> void:
	var e: Enemy = await _seated()
	if not e.visual.has_part("prop_splint"):
		pending("no generated body with the props (make assets)")
		return
	var shown := func(part: String) -> bool: return (e.visual._segments[part] as MeshInstance3D).visible
	await _frames(2)
	assert_true(shown.call("prop_splint"), "splinted at his camp")
	assert_true(shown.call("prop_hatchet_belt") and not shown.call("prop_hatchet_hand"), "the hatchet on his belt while he sits")
	_p.global_position = CAMP_AT + Vector3(0, 0, 2.5)
	_give(&"first_aid_kit")
	Game.execute(&"companion.recruit", {})
	await _frames(int(e.ally.rising_t * 60.0) + 4)
	assert_false(shown.call("prop_splint"), "off once he is up and with the player")
	assert_false(shown.call("prop_lantern"), "no lantern by day")
	var h: Enemy = _spawn(&"hollow", e.global_position + Vector3(2.0, 0, 0))
	e.foe = h
	await _frames(2)
	assert_true(shown.call("prop_hatchet_hand") and not shown.call("prop_hatchet_belt"), "in his fist to fight")
	e.foe = null
	e._set_state(Enemy.State.IDLE)
	Game.session.clock.set_time(Game.session.clock.day(), 23.0)
	await _frames(3)
	assert_true(e.ally.lantern_on(), "his light at night, following")
	assert_true(shown.call("prop_lantern"), "the lantern in his hand while its light is on")
	assert_true(e.ally.lantern.get_parent() is BoneAttachment3D, "the light rides his hand")


func test_companion_strength_scales_him() -> void:
	var e: Enemy = await _recruited()
	assert_almost_eq(e.max_health, e.def.health, 0.01, "1 by default: the enemy settings never apply")
	after_each()
	_start({"seed": 5803, "game_mode": "survival", "rules": {"companion_strength": 1.5, "enemy_health": 2.0}})
	var e2: Enemy = await _recruited()
	assert_almost_eq(e2.max_health, e2.def.health * 1.5, 0.01, "health x companion_strength")
	assert_almost_eq(e2.damage_mult, 1.5, 0.001, "his blows too")
	var preset: GameRules = GameRules.resolve({}, &"hollowed", {})
	assert_lt(preset.num("companion_strength"), 1.0, "the hard presets weaken him")


func test_his_perks_come_with_the_days() -> void:
	var e: Enemy = await _recruited()
	assert_eq(_dir.days_with(), 0)
	var names: Array = _dir.active_perks().map(func(p: Dictionary) -> String: return str(p["id"]))
	assert_eq(names, ["pack_mule"], "the first from the start")
	assert_eq(_dir.inventory.max_slots, 16, "four more slots")
	assert_eq(_dir.inventory.add_item(&"log", 4), 1, "a third log on his shoulder, not a fourth")
	assert_eq(_dir.inventory.count_of(&"log"), 3)
	assert_almost_eq(e.ally.perk("chop_speed", 1.0), 1.0, 0.001, "not a faller yet")
	var gen_at: Vector3 = e.global_position + Vector3(10, 0, 0)
	assert_eq(_dir.fuel_factor(gen_at), 1.0, "nor a lineman")
	Game.session.clock.set_time(4, 12.0)
	_dir.tick()
	assert_eq(_dir.active_perks().size(), 3, "two days on: all three")
	assert_almost_eq(e.ally.perk("chop_speed", 1.0), 1.3, 0.001)
	assert_almost_eq(e.ally.perk("chop_power", 1.0), 1.25, 0.001)
	assert_almost_eq(_dir.fuel_factor(gen_at), 0.75, 0.001, "a generator near him burns a quarter less")
	assert_eq(_dir.fuel_factor(e.global_position + Vector3(80, 0, 0)), 1.0, "not one far off")
	# The generator's prompt says so where the fuel is read (TD-310).
	var btm := BaseTechManager.new()
	btm.world = _world
	var prev_btm: BaseTechManager = BaseTechManager.current
	BaseTechManager.current = btm
	assert_string_contains(BaseTechManager._tuned_text(gen_at), "Ezra keeps it tuned")
	assert_eq(BaseTechManager._tuned_text(e.global_position + Vector3(80, 0, 0)), "", "not one far off")
	BaseTechManager.current = prev_btm
	btm.free()
	e.ally.go_down(null, 60.0)
	assert_eq(_dir.fuel_factor(gen_at), 1.0, "nor while he is down")
	# The card lists his knacks.
	var cd: CompanionDef = _dir.cdef
	assert_true(cd.perks_after(0).size() < cd.perks_after(9).size())


func test_placed_beside_the_player_he_keeps_out_of_walls_and_water() -> void:
	var e: Enemy = await _recruited()
	_p.global_position = Vector3(0, 0, 0)
	_p.rotation = Vector3.ZERO
	_p.head.rotation = Vector3.ZERO
	# A wall right behind the player, across the spot he would be put at.
	_box(Vector3(0, 1.5, 3.0), Vector3(30, 3, 0.4))
	await get_tree().physics_frame
	_dir.place_beside(_p)
	var at: Vector3 = e.global_position
	assert_lt(at.z, 3.0 - 0.2 - CompanionDirector.BODY_RADIUS + 0.01, "on the player's side of the wall (%s)" % at)
	assert_lt(Vector2(at.x, at.z).length(), 10.0, "still beside the player")
	assert_almost_eq(at.y, 0.1, 0.2, "on the floor")
	# Water everywhere off a dry strip in front of the player.
	var water := FakeWater.new()
	water.wet = func(pos: Vector3) -> bool: return pos.z > -1.5 or absf(pos.x) > 1.0
	_world.add_child(water)
	_world.water = water
	_dir.place_beside(_p)
	at = e.global_position
	assert_lte(at.z, -1.5, "not in the water (%s)" % at)
	assert_lte(absf(at.x), 1.0)
	_world.water = null
	water.free()


func test_a_crest_below_head_height_doesnt_block_a_spot_but_a_wall_does() -> void:
	await _recruited()
	await get_tree().physics_frame
	var anchor := Vector3(40, 0, 40)
	# A 1.4 m crest across the line to the spot 4 m off: above chest height, below the head.
	_box(anchor + Vector3(0, 0.7, 2.0), Vector3(30, 1.4, 0.4))
	await get_tree().physics_frame
	var spot: Vector3 = anchor + Vector3(0, 0, 4.0)
	var at: Vector3 = _dir.safe_spot(anchor, spot)
	assert_almost_eq(at.z, spot.z, 0.3, "over the crest, where it was wanted (%s)" % at)
	# A full wall: the spot behind it is refused.
	_box(anchor + Vector3(0, 1.5, -2.0), Vector3(30, 3.0, 0.4))
	await get_tree().physics_frame
	var at2: Vector3 = _dir.safe_spot(anchor, anchor + Vector3(0, 0, -4.0))
	assert_gt(at2.z, anchor.z - 2.0, "not behind the wall (%s)" % at2)


func test_a_saved_spot_inside_a_wall_is_moved_out() -> void:
	await _recruited()
	var inside := Vector3(-40, 0, 40)
	_box(inside + Vector3.UP * 1.5, Vector3(2.0, 3.0, 2.0))
	await get_tree().physics_frame
	var at: Vector3 = _dir.safe_spot(inside, inside)
	assert_gt(maxf(absf(at.x - inside.x), absf(at.z - inside.z)), 1.0 + CompanionDirector.BODY_RADIUS - 0.01,
		"out of the block it was saved in (%s)" % at)


func test_at_dawn_he_comes_back_inside_the_room_with_the_bed() -> void:
	var e: Enemy = await _recruited()
	var bed := Vector3(30, 0, 30)
	_p.state.spawn_point = bed
	_p.state.has_spawn_point = true
	# A hut round the bed: four walls, the bed itself where he would be put.
	for side: Vector3 in [Vector3(2.6, 0, 0), Vector3(-2.6, 0, 0), Vector3(0, 0, 2.6), Vector3(0, 0, -2.6)]:
		var sz := Vector3(0.3, 3.0, 5.5) if side.x != 0.0 else Vector3(5.5, 3.0, 0.3)
		_box(bed + side + Vector3.UP * 1.5, sz)
	_box(bed + Vector3(1.5, 0.3, 1.0), Vector3(1.2, 0.6, 2.2))
	await get_tree().physics_frame
	e.ally.go_down(null, 0.05)
	await _frames(10)
	_dir.tick()
	Game.session.clock.set_time(3, 8.0)
	_dir.tick()
	var b: Enemy = _dir.body
	assert_not_null(b, "back at dawn")
	var d: Vector3 = b.global_position - bed
	assert_lt(maxf(absf(d.x), absf(d.z)), 2.45 - CompanionDirector.BODY_RADIUS + 0.01, "inside the hut (%s)" % d)
	var in_bed: bool = absf(d.x - 1.5) < 0.6 + CompanionDirector.BODY_RADIUS and absf(d.z - 1.0) < 1.1 + CompanionDirector.BODY_RADIUS
	assert_false(in_bed, "not in the bed (%s)" % d)
