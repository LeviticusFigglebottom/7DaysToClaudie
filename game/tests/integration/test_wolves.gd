extends GutTest
## Wolf packs (ADR-0055) against real nodes on a flat floor: a pack spawns from a WildlifeSpawner
## plan as Enemies of faction wildlife the AI director neither counts nor despawns; a hungry pack
## runs down a deer, kills it and feeds, leaving the carcass eaten; a fed pack keeps off the player
## by day and watches; a pack not fed takes the player on at night, and its bite bleeds but never
## infects; a lit campfire keeps the pack outside its ring at night; a wolf's howl is no stimulus;
## the world setting turns them off. The wolves and deer are stepped by hand at 60 Hz (no waiting).

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const DT: float = 1.0 / 60.0


## Enough of a GameWorld for bodies that run their own brains: the player, a flat ground, and the
## player's building (for lit fires).
class FlatWorld:
	extends Node3D
	var player: Node3D = null
	var building: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0

	func ground_below(_p: Vector3) -> float:
		return 0.0


class FireBuilding:
	extends Node3D
	var fires: Array = []

	func pieces_in_radius(pos: Vector3, r: float) -> Array:
		var out: Array = []
		for f: Node3D in fires:
			if f.global_position.distance_to(pos) <= r:
				out.append(f)
		return out


class Campfire:
	extends Node3D
	var lit: bool = true

	func station_id() -> StringName:
		return &"campfire"


var _prev: GameSession
var _prev_world: Node
var _root: FlatWorld
var _ai: AIDirector
var _wm: WildlifeManager
var _p: Player
var _feed_seconds: float = 0.0


func before_each() -> void:
	_prev = Game.session
	_prev_world = Game.world
	Game.session = GameSession.create_new({"seed": 5501, "game_mode": "survival"})
	Game.session.clock.set_time(2, 12.0)
	_root = FlatWorld.new()
	add_child_autofree(_root)
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(600, 1, 600)
	cs.shape = shape
	b.add_child(cs)
	_root.add_child(b)
	b.global_position = Vector3(0, -0.5, 0)
	var st := Stimuli.new()
	_root.add_child(st)
	st.recenter(Vector3.ZERO)
	_ai = AIDirector.new()
	_root.add_child(_ai)
	_ai.set_process(false)
	_wm = WildlifeManager.new()
	_root.add_child(_wm)
	_wm.setup_world(null)
	_wm.set_process(false)
	_wm.wolves.ai = _ai
	_wm.wolves.set_physics_process(false)
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_root.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = Vector3.ZERO
	_p.set_physics_process(false)
	_p.head.position.y = 1.65
	_root.player = _p
	Game.world = _root
	_feed_seconds = float(WolfPack.section("feed").get("seconds", 75.0))


func after_each() -> void:
	WolfPack.section("feed")["seconds"] = _feed_seconds
	Game.session = _prev
	Game.world = _prev_world


func _pack(at: Vector3, n: int, hunger: float, tag: String = "a") -> WolfPack:
	var d := Content.get_def(&"wildlife", &"grey_wolf_pack") as WildlifeDef
	var pack: WolfPack = _wm.wolves.spawn_plan(d, {"id": StringName("w:test:%s" % tag), "def": d.id, "pos": Vector2(at.x, at.z),
		"count": n, "seed": 77})
	if pack != null:
		pack.hunger = hunger
		for m: Enemy in pack.members:
			m.set_physics_process(false)
	return pack


func _deer(n: int, at: Vector3) -> Array:
	var d := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	var herd: Array = _wm.spawn_band(d, {"id": &"w:test:deer", "def": d.id, "pos": Vector2(at.x, at.z), "count": n, "seed": 11})
	for a: Animal in herd:
		a.set_physics_process(false)
	return herd


## Steps the packs, the wolves and the deer by hand; stops early when `until` returns true.
func _run(seconds: float, herd: Array = [], until: Callable = Callable()) -> void:
	for i: int in int(seconds / DT):
		_wm.wolves._physics_process(DT)
		for pack: WolfPack in _wm.wolves.packs.values():
			for m: Enemy in pack.alive():
				m._physics_process(DT)
		for a: Variant in herd:
			if is_instance_valid(a):
				(a as Animal)._physics_process(DT)
		if until.is_valid() and bool(until.call()):
			return
		if i % 30 == 0:
			await get_tree().physics_frame


func _nearest(pack: WolfPack, to: Vector3) -> float:
	var d: float = INF
	for m: Enemy in pack.alive():
		d = minf(d, Vector2(m.global_position.x - to.x, m.global_position.z - to.z).length())
	return d


func test_a_pack_spawns_as_wildlife_the_director_leaves_alone() -> void:
	var pack: WolfPack = _pack(Vector3(0, 0, 60), 4, 0.2)
	assert_not_null(pack)
	assert_eq(pack.members.size(), 4)
	var slots: Dictionary = {}
	for m: Enemy in pack.members:
		assert_eq(m.def.faction, "wildlife")
		assert_eq(m.def.archetype, "hound", "the hound's body and brain")
		assert_eq(m.tier, &"normal", "no Seeded or Bloomed wolves")
		assert_not_null(m.wolf)
		assert_eq(m.pack.size(), 4, "each knows the pack")
		slots[m.pack_slot] = true
		assert_false(FactionDef.hostile("hollowed", m.def.faction), "the Hollowed and the wolves leave each other be")
	assert_eq(slots.size(), 4)
	assert_eq(_ai._roaming_count(), 0, "wolves are not roaming Hollowed")
	assert_true(_wm.wolves.has_plan(&"w:test:a"))
	Game.session.rules.values["hollowed_hounds"] = false
	assert_eq(AIDirector.allowed_enemy(&"grey_wolf", 0, false), &"grey_wolf", "the hound setting is not the wolves'")


func test_a_hungry_pack_runs_down_a_deer_and_feeds() -> void:
	WolfPack.section("feed")["seconds"] = 4.0
	_p.global_position = Vector3(-200, 0, 0)  # far off: this is between the wolves and the deer
	var herd: Array = _deer(2, Vector3(70, 0, 0))
	var pack: WolfPack = _pack(Vector3(0, 0, 0), 4, 0.9)
	await get_tree().physics_frame
	await _run(1.0, herd)
	assert_eq(pack.mode, WolfPack.Mode.HUNT, "hungry: it goes after the herd")
	assert_true(pack.alive()[0].wolf.unseen_by_prey(), "stalking: the deer don't see it")
	await _run(60.0, herd, func() -> bool: return pack.mode in [WolfPack.Mode.FEED, WolfPack.Mode.REST])
	assert_eq(pack.mode, WolfPack.Mode.FEED, "a deer down")
	var kill: Animal = pack.kill as Animal
	assert_not_null(kill)
	assert_false(kill.is_alive())
	assert_true(String(kill.killer).begins_with("w:test:a#"), "a wolf killed it (%s)" % kill.killer)
	await _run(40.0, herd, func() -> bool: return pack.mode == WolfPack.Mode.REST)
	assert_eq(pack.mode, WolfPack.Mode.REST, "fed, it beds down by the kill")
	assert_eq(pack.hunger, 0.0)
	assert_true(kill.butchered, "the carcass is left eaten")
	assert_lt(_nearest(pack, kill.global_position), 8.0, "the pack stays by its kill")
	assert_false(pack.engaged)


func test_a_fed_pack_keeps_off_the_player_by_day() -> void:
	var pack: WolfPack = _pack(Vector3(0, 0, 18), 3, 0.0)
	await get_tree().physics_frame
	var start: float = _nearest(pack, Vector3.ZERO)
	await _run(8.0)
	assert_false(pack.engaged, "fed, by day: no reason to come for you")
	for m: Enemy in pack.alive():
		assert_true(m.state in [Enemy.State.IDLE, Enemy.State.WANDER], "it never hunts you (%s)" % m.state)
	assert_gt(_nearest(pack, Vector3.ZERO), start + 12.0, "it backed off toward 40 m (%.1f)" % _nearest(pack, Vector3.ZERO))
	assert_eq(_p.state.stats.health, _p.state.stats.max_health)


func test_at_night_a_pack_not_fed_comes_and_its_bite_bleeds_but_never_infects() -> void:
	Game.session.clock.set_time(2, 23.0)
	var pack: WolfPack = _pack(Vector3(0, 0, 16), 3, 0.5)
	await get_tree().physics_frame
	await _run(10.0, [], func() -> bool: return _p.state.stats.health < _p.state.stats.max_health)
	assert_true(pack.engaged, "night, and not fed: the pack takes you on")
	assert_lt(_p.state.stats.health, _p.state.stats.max_health, "and bites")
	assert_gt(_p.state.stats.bleeding, 0.0, "a bleeding wound")
	assert_eq(_p.state.stats.infection, 0.0, "a wolf carries no Bloom")


func test_a_lit_campfire_keeps_the_pack_outside_its_ring_at_night() -> void:
	Game.session.clock.set_time(2, 23.0)
	var fb := FireBuilding.new()
	_root.add_child(fb)
	var fire := Campfire.new()
	fb.add_child(fire)
	fire.global_position = Vector3(1.5, 0, 0)
	fb.fires = [fire]
	_root.building = fb
	var r: float = float(WolfPack.section("fire").get("radius", 13.0))
	var pack: WolfPack = _pack(Vector3(0, 0, 30), 4, 0.9)
	await get_tree().physics_frame
	var closest: float = INF
	for k: int in 12:
		await _run(1.0)
		closest = minf(closest, _nearest(pack, fire.global_position))
	assert_true(pack.engaged, "hungry at night: it wants you")
	assert_gt(closest, r - 1.5, "but no wolf comes into the fire's ring (closest %.1f m)" % closest)
	assert_lt(closest, r + 12.0, "it circles close outside it")
	assert_eq(_p.state.stats.health, _p.state.stats.max_health, "untouched by the fire")


func test_a_wolf_howl_is_no_stimulus() -> void:
	var pack: WolfPack = _pack(Vector3(0, 0, 50), 3, 0.2)
	await get_tree().physics_frame
	var seq: int = Stimuli.current.last_seq()
	var heat: float = Game.session.heat.at(Vector3(0, 0, 50)) if Game.session.heat.has_method(&"at") else 0.0
	pack.alive()[0]._howl()
	pack.howl(_wm.wolves)
	assert_eq(Stimuli.current.last_seq(), seq, "nothing for the Hollowed to hear")
	if Game.session.heat.has_method(&"at"):
		assert_eq(Game.session.heat.at(Vector3(0, 0, 50)), heat, "and no heat")


func test_the_rule_to_take_the_player_on() -> void:
	var c: Dictionary = WolfPack.cfg()
	assert_false(WolfPack.wants_player(c, 0.0, false, 15.0, false, false, false), "fed, by day: leaves you be")
	assert_false(WolfPack.wants_player(c, 0.1, true, 15.0, false, false, false), "just fed, at night: too")
	assert_true(WolfPack.wants_player(c, 0.5, true, 30.0, false, false, false), "not fed, at night")
	assert_true(WolfPack.wants_player(c, 0.9, false, 15.0, false, false, false), "hungry and close by day")
	assert_false(WolfPack.wants_player(c, 0.9, false, 80.0, false, false, false), "hungry but far by day")
	assert_true(WolfPack.wants_player(c, 0.0, false, 60.0, true, false, false), "wounded")
	assert_true(WolfPack.wants_player(c, 0.0, false, 15.0, false, true, false), "by its kill")
	assert_true(WolfPack.wants_player(c, 0.4, false, 100.0, false, false, true), "on your blood trail")


func test_the_world_setting_turns_them_off() -> void:
	Game.session.rules.values["wolves"] = false
	assert_null(_pack(Vector3(0, 0, 60), 4, 0.5, "off"), "no packs")
	assert_eq(_ai.enemies.size(), 0)
	Game.session.rules.values["wolves"] = true
	var pack: WolfPack = _pack(Vector3(0, 0, 60), 4, 0.5, "on")
	assert_not_null(pack)
	Game.session.rules.values["wolves"] = false
	_wm.wolves._check()
	assert_true(_wm.wolves.packs.is_empty(), "turned off, the packs go")
