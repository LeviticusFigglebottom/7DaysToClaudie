extends GutTest
## The Ashen and the Hollowed fight each other (TD-186, ADR-0048 phase 2): FactionDef.relations is
## symmetric; an Ashen raider that sees a Hollow (the player out of sight behind a wall) goes for it
## and wounds it, and a Hollow turns on an Ashen; nobody turns on its own kind; the player, once
## seen, comes first; a spear wounds a Hollow and flies past the thrower's own; and an Ashen killed
## by a Hollowed is nobody's kill (no XP, no kill count, no hostility, no player source).

const PLAYER_SCENE: String = "res://src/player/player.tscn"


class FakeWorld:
	extends Node3D
	var ai: Node = null
	var pois: Node = null
	var player: Node3D = null
	var building: Node = null
	var traders: Node = null
	var ashen: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _world: FakeWorld
var _ai: AIDirector
var _dir: AshenDirector
var _p: Player


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "survival"})
	_world = FakeWorld.new()
	add_child_autofree(_world)
	_ai = AIDirector.new()
	_world.add_child(_ai)
	_world.ai = _ai
	_box(Vector3(0, -0.5, 0), Vector3(400, 1, 400))
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_world.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = Vector3.ZERO
	_world.player = _p
	_dir = AshenDirector.new()
	_world.add_child(_dir)
	_world.ashen = _dir
	_dir.setup_world(_world)


func after_each() -> void:
	Game.session = _prev


func _box(at: Vector3, size: Vector3) -> void:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	_world.add_child(b)
	b.global_position = at


## A wall between the player (at the origin) and z = 30, so nobody there can see them.
func _wall() -> void:
	_box(Vector3(0, 3, 15), Vector3(120, 6, 1))


func _spawn(id: StringName, at: Vector3, opts: Dictionary = {}) -> Enemy:
	var o: Dictionary = {"tier": "normal", "authored": true}
	o.merge(opts, true)
	return _ai.spawn(id, at, o)


func _pdist(e: Enemy) -> float:
	return e.global_position.distance_to(_p.global_position)


func test_the_ashen_and_the_hollowed_are_hostile_both_ways() -> void:
	assert_true(FactionDef.hostile("ashen", "hollowed"), "ashen.json says so")
	assert_true(FactionDef.hostile("hollowed", "ashen"), "symmetric: the Hollowed have no FactionDef")
	assert_false(FactionDef.hostile("ashen", "ashen"))
	assert_false(FactionDef.hostile("hollowed", "hollowed"))
	assert_false(FactionDef.hostile("ashen", "wildlife"), "neutral")


func test_a_raider_goes_for_a_hollow_and_wounds_it() -> void:
	_wall()
	var r: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 30))
	var h: Enemy = _spawn(&"hollow", Vector3(6, 0, 30))
	await get_tree().physics_frame
	r.scan_foes(_pdist(r))
	assert_eq(r.foe, h, "the nearest hostile body it can see")
	assert_eq(r.state, Enemy.State.CHASE)
	assert_true(r.fighting_foe(), "the player is out of sight")
	var hp: float = h.health
	var php: float = _p.state.stats.health
	for i: int in 600:
		await get_tree().physics_frame
		if h.health < hp:
			break
	assert_lt(h.health, hp, "it closed and struck (or speared) the Hollow")
	assert_eq(_p.state.stats.health, php, "the player untouched")


func test_a_hollow_turns_on_an_ashen() -> void:
	_wall()
	var h: Enemy = _spawn(&"hollow", Vector3(0, 0, 30))
	var r: Enemy = _spawn(&"ashen_raider", Vector3(5, 0, 30))
	await get_tree().physics_frame
	h.scan_foes(_pdist(h))
	assert_eq(h.foe, r)
	assert_true(h.fighting_foe())


func test_nobody_turns_on_its_own_kind() -> void:
	_wall()
	var r1: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 30))
	var r2: Enemy = _spawn(&"ashen_scout", Vector3(4, 0, 30))
	var h1: Enemy = _spawn(&"hollow", Vector3(0, 0, -30))
	var h2: Enemy = _spawn(&"lurcher", Vector3(4, 0, -30))
	_box(Vector3(0, 3, -15), Vector3(120, 6, 1))
	await get_tree().physics_frame
	for e: Enemy in [r1, r2, h1, h2]:
		e.scan_foes(_pdist(e))
		assert_null(e.foe, "%s: no foe among its own" % e.def.id)
	# A blow from one of its own doesn't make a foe either.
	var info := DamageInfo.make(1.0, &"slash", &"ashen", r2.entity_id)
	info.hit_pos = r1.global_position + Vector3.UP
	r1.take_damage(info)
	assert_null(r1.foe)


func test_the_player_seen_comes_first() -> void:
	var stimuli := Stimuli.new()
	add_child_autofree(stimuli)
	stimuli.recenter(Vector3.ZERO)
	var r: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 8))
	var h: Enemy = _spawn(&"hollow", Vector3(4, 0, 10))
	await get_tree().physics_frame
	r.global_position = Vector3(0, 0, 8)
	r.rotation.y = PI
	r.scan_foes(_pdist(r))
	assert_eq(r.foe, h)
	r._perceive(_p, _pdist(r))
	assert_lt(r._now() - r.last_seen_time, 0.5, "it sees the player")
	assert_false(r.fighting_foe(), "the player comes first")
	assert_eq(r.state, Enemy.State.CHASE)
	assert_almost_eq(r.target_pos, _p.global_position, Vector3.ONE * 0.1, "on the player, not the Hollow")


func test_a_spear_wounds_a_hollow_and_flies_past_an_ashen() -> void:
	_wall()
	var r: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 30))
	var mate: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 33))
	var h: Enemy = _spawn(&"hollow", Vector3(0, 0, 37))
	await get_tree().physics_frame
	for e: Enemy in [r, mate, h]:
		e.set_physics_process(false)
	r.global_position = Vector3(0, 0, 30)
	mate.global_position = Vector3(0, 0, 33)
	h.global_position = Vector3(0, 0, 37)
	var hp_mate: float = mate.health
	var hp: float = h.health
	ThrownSpear.launch(_world, r.global_position + Vector3(0, 1.7, 0.4), h.global_position + Vector3.UP * 1.1, 20.0, 16.0, 0.4, r.entity_id, r)
	for i: int in 120:
		await get_tree().physics_frame
		if h.health < hp:
			break
	assert_lt(h.health, hp, "the spear found the Hollow")
	assert_eq(mate.health, hp_mate, "and flew past the thrower's own")
	assert_eq(h.foe, r, "the wounded Hollow turns on the thrower")


func test_an_ashen_killed_by_a_hollowed_is_nobodys_kill() -> void:
	_wall()
	var r: Enemy = _spawn(&"ashen_raider", Vector3(0, 0, 30))
	var h: Enemy = _spawn(&"hollow", Vector3(0, 0, 31.2))
	await get_tree().physics_frame
	for e: Enemy in [r, h]:
		e.set_physics_process(false)
	r.global_position = Vector3(0, 0, 30)
	h.global_position = Vector3(0, 0, 31.2)
	h.rotation.y = PI
	h.scan_foes(_pdist(h))
	assert_eq(h.foe, r)
	var xp: int = _p.state.progression.xp
	var hostility: float = _dir.hostility()
	var killers: Array = []
	var on_kill := func(_eid: StringName, _id: StringName, _pos: Vector3, killer: Dictionary) -> void: killers.append(killer)
	Events.enemy_killed.connect(on_kill)
	r.health = 1.0
	h.hit_foe()
	Events.enemy_killed.disconnect(on_kill)
	assert_false(r.is_alive(), "the Hollow's blow killed it")
	assert_eq(killers.size(), 1)
	assert_eq(str(killers[0].get("source", "")), String(h.entity_id), "the killer is the Hollow")
	assert_false(Game.session.players.has(StringName(str(killers[0].get("source", "")))))
	assert_eq(_p.state.progression.xp, xp, "no XP for the player")
	assert_true(_p.state.kills.is_empty(), "no kill counted")
	assert_eq(_dir.hostility(), hostility, "the Ashen don't blame the player")


func test_a_scout_picks_no_fight() -> void:
	# Mid-game audit M11: a scout downed Ezra within seconds. Scouts watch and report (ADR-0048).
	_wall()
	var sc: Enemy = _spawn(&"ashen_scout", Vector3(0, 0, 30), {"job": "scout"})
	var h: Enemy = _spawn(&"hollow", Vector3(4, 0, 30))
	await get_tree().physics_frame
	sc.scan_foes(_pdist(sc))
	assert_null(sc.foe, "it doesn't go for a hostile body it sees")
	assert_ne(sc.state, Enemy.State.CHASE)
	assert_true(h.is_alive(), "the Hollow it saw")


func test_a_scout_struck_in_the_open_runs() -> void:
	_wall()
	var sc: Enemy = _spawn(&"ashen_scout", Vector3(0, 0, 30), {"job": "scout"})
	var h: Enemy = _spawn(&"hollow", Vector3(1.5, 0, 30))
	await get_tree().physics_frame
	var info := DamageInfo.make(5.0, &"zombie", &"zombie", h.entity_id)
	info.source_pos = h.global_position
	sc.take_damage(info)
	assert_null(sc.foe, "it doesn't trade blows")
	assert_eq(sc.state, Enemy.State.FLEE, "it runs, away from what struck it")
	var away: Vector3 = sc.tribe.flee_to - h.global_position
	assert_gt(away.length(), 100.0)
