extends GutTest
## The Ashen (ADR-0048) against real nodes: a fighter is a living Enemy with an AshenMind (no
## infection in its blows); a scout watches from its vantage and slips away to report, or breaks off
## when the player comes at it; a band breaks when its mates fall, but not at home; a camp is
## peopled when the player comes near and its dead stay dead; a raid comes, is turned back for XP
## and the directive event, and the Hum sends them running; the faction's state survives a save.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const CAMP := Vector3(60, 0, 60)


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
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(400, 1, 400)
	cs.shape = shape
	b.add_child(cs)
	_world.add_child(b)
	b.global_position = Vector3(0, -0.5, 0)
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
	_dir.buildings_source = func() -> Array:
		return [{"id": "poi:camp", "def": "ashen_highcamp", "name": "the high camp", "tier": 3, "pos": CAMP}]


func after_each() -> void:
	Game.session = _prev


func _spawn(id: StringName, at: Vector3, opts: Dictionary = {}) -> Enemy:
	var o: Dictionary = {"tier": "normal", "authored": true}
	o.merge(opts, true)
	return _ai.spawn(id, at, o)


func _kill(e: Enemy) -> void:
	var info := DamageInfo.make(9999.0, &"pierce", &"melee", _p.state.id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)


func test_an_ashen_fighter_is_a_living_enemy() -> void:
	var e: Enemy = _spawn(&"ashen_raider", Vector3(1.5, 0, 0))
	await get_tree().physics_frame
	assert_not_null(e.tribe)
	assert_eq(e.tier, &"normal", "never Seeded or Bloomed")
	e.global_position = _p.global_position + Vector3(0, 0, 1.2)
	e.rotation.y = PI
	var infection: float = _p.state.stats.infection
	e._deliver_hit(_p)
	assert_eq(_p.state.stats.infection, infection, "an axe, not a bite: no Bloom")
	assert_eq(AshenMind.voice(&"voice/zombie_alert"), &"voice/ashen_warcry")
	assert_eq(e._vid(&"voice/hollow_groan_idle", &"voice/hound_growl"), &"", "no groans")


func test_a_scout_watches_then_slips_away_to_report() -> void:
	var e: Enemy = _spawn(&"ashen_scout", Vector3(0, 0, 45), {"job": "scout"})
	await get_tree().physics_frame
	e._set_state(Enemy.State.OBSERVE)
	var observe: float = float(_dir.fd.scouts["observe"])
	var t: float = 0.0
	while t < observe + 1.0 and e.state == Enemy.State.OBSERVE:
		e.tribe.move(_p, e.global_position.distance_to(_p.global_position), 1.0)
		t += 1.0
	assert_true(e.tribe.reported, "watched long enough")
	assert_eq(e.state, Enemy.State.FLEE)
	assert_gt((e.tribe.flee_to - _p.global_position).length(), 100.0, "away from the player")


func test_a_scout_comes_at_breaks_off_without_reporting() -> void:
	var e: Enemy = _spawn(&"ashen_scout", Vector3(0, 0, 10), {"job": "scout"})
	await get_tree().physics_frame
	e._set_state(Enemy.State.OBSERVE)
	e.tribe.move(_p, 10.0, 0.5)
	assert_eq(e.state, Enemy.State.FLEE)
	assert_false(e.tribe.reported)


func test_a_band_breaks_when_its_mates_fall_but_not_at_home() -> void:
	var band: Array = []
	for i: int in 5:
		band.append(_spawn(&"ashen_raider", Vector3(30 + i * 2, 0, 0), {"job": "raid", "goal": Vector3.ZERO}))
	for e: Variant in band:
		(e as Enemy).tribe.band = band
	await get_tree().physics_frame
	for i2: int in 3:
		_kill(band[i2])
	assert_eq((band[4] as Enemy).state, Enemy.State.FLEE, "three of five down: the rest run")
	var home: Array = []
	for j: int in 5:
		home.append(_spawn(&"ashen_raider", CAMP + Vector3(j * 2, 0, 0), {"job": "camp", "camp": "poi:camp", "camp_pos": CAMP, "territory": 160.0}))
	for e2: Variant in home:
		(e2 as Enemy).tribe.band = home
	await get_tree().physics_frame
	for j2: int in 4:
		_kill(home[j2])
	assert_ne((home[4] as Enemy).state, Enemy.State.FLEE, "at home they fight to the last")


func test_a_camp_is_peopled_near_and_its_dead_stay_dead() -> void:
	_p.global_position = CAMP + Vector3(0, 0, 100)
	_dir._follow_camps(_p)
	var cfg: Dictionary = _dir.fd.camp_for(&"ashen_highcamp")
	var n: int = _dir.residents_of("poi:camp", cfg).size()
	assert_eq((_dir._residents["poi:camp"] as Array).size(), n, "everyone at home")
	assert_eq(_dir.residents_of("poi:camp", cfg), _dir.residents_of("poi:camp", cfg), "the same people every time")
	assert_gt(_dir.hostility(), float(_dir.fd.hostility["start"]), "walking into their territory is trespass")
	_kill(_dir._residents["poi:camp"][0])
	_p.global_position = CAMP + Vector3(0, 0, 400)
	_dir._follow_camps(_p)
	assert_false(_dir._residents.has("poi:camp"), "emptied past its sleep range")
	_p.global_position = CAMP + Vector3(0, 0, 100)
	_dir._follow_camps(_p)
	assert_eq((_dir._residents["poi:camp"] as Array).size(), n - 1, "the dead stay dead")
	for e: Variant in (_dir._residents["poi:camp"] as Array).duplicate():
		_kill(e)
	assert_true(bool(_dir.camp_state("poi:camp").get("wiped", false)), "a camp can be wiped out")


func test_a_raid_is_turned_back_for_xp() -> void:
	var ended: Array = []
	Events.ashen_raid_ended.connect(func(_rid: String, repelled: bool) -> void: ended.append(repelled), CONNECT_ONE_SHOT)
	var r: Dictionary = _dir.debug_raid(4)
	assert_false(r.is_empty())
	assert_eq((r["members"] as Array).size(), 4)
	await get_tree().physics_frame
	var xp: int = _p.state.progression.xp
	var lvl: int = _p.state.progression.level
	for e: Variant in (r["members"] as Array).duplicate():
		if (e as Enemy).is_alive():
			_kill(e)
	_dir._follow_raid(_p, 1.0)
	assert_true(_dir.raid.is_empty())
	assert_eq(ended, [true], "repelled")
	assert_true(_p.state.progression.xp > xp or _p.state.progression.level > lvl, "and paid in XP")


func test_the_hum_sends_them_running() -> void:
	var r: Dictionary = _dir.debug_raid(3)
	await get_tree().physics_frame
	_dir._on_hum(7)
	for e: Variant in r["members"]:
		assert_eq((e as Enemy).state, Enemy.State.FLEE)
	assert_true(_dir.raid.is_empty(), "the raid is off")


func test_the_faction_survives_a_save() -> void:
	_dir.provoke("kill", 3.0)
	_dir.camp_state("poi:camp")["dead"] = [1, 2]
	var w := WorldState.new()
	w.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	assert_almost_eq(float(w.ashen["hostility"]), _dir.hostility(), 0.001)
	assert_eq((w.ashen["camps"]["poi:camp"]["dead"] as Array).size(), 2)
	var old := WorldState.new()
	old.from_dict({})
	assert_eq(old.ashen, {}, "older saves load with no Ashen state")
