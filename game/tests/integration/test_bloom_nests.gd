extends GutTest
## Bloom nests (ADR-0055) against real nodes: the defs load and validate; a nest seeds its guards
## while the player is near and not when far; only fire hurts it; burning it wakes its guards, drops
## its loot, pays the burn_nest XP, emits the directive event, marks it burned (and it stays so
## through a save round-trip), and its Bloom spot fades; a region feature places one, and the
## main map has one.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const NEST := Vector3(40, 0, 40)


class FakeBloom:
	extends Node
	var sources: Dictionary = {}

	func set_spot_source(source: StringName, spots: Array) -> void:
		if spots.is_empty():
			sources.erase(source)
		else:
			sources[source] = spots.duplicate(true)


class FakeTerrain:
	extends Node
	signal region_attached(rid: String)
	signal region_detached(rid: String)
	var bloom: Node = null
	var regions: Dictionary = {}


class FakeWorld:
	extends Node3D
	var ai: Node = null
	var player: Node3D = null
	var terrain: Node = null
	var world_def: WorldDef = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _world: FakeWorld
var _ai: AIDirector
var _nests: BloomNests
var _bloom: FakeBloom
var _p: Player


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "survival"})
	_world = FakeWorld.new()
	add_child_autofree(_world)
	_ai = AIDirector.new()
	_world.add_child(_ai)
	_world.ai = _ai
	var t := FakeTerrain.new()
	_bloom = FakeBloom.new()
	t.add_child(_bloom)
	t.bloom = _bloom
	_world.add_child(t)
	_world.terrain = t
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
	_p.global_position = Vector3(0, 0, -200)
	_world.player = _p
	_nests = BloomNests.new()
	_world.add_child(_nests)
	_nests.setup_world(_world)


func after_each() -> void:
	Game.session = _prev


func _hit(id: String, amount: float, type: StringName) -> void:
	var info := DamageInfo.make(amount, type, &"melee", _p.state.id)
	info.hit_pos = NEST + Vector3.UP
	_nests.core_of(id).take_damage(info)


func test_defs_load_and_validate() -> void:
	assert_eq(Content.errors().size(), 0, "content loads clean: %s" % ", ".join(Content.errors()))
	for id: StringName in [&"root_knot", &"hollow_nest"]:
		var d: NestDef = Content.get_def(&"nest", id) as NestDef
		assert_not_null(d, "nest %s" % id)
		assert_false(d.props.is_empty())
		assert_false(d.pods().is_empty(), "%s has a pod" % id)
		assert_gt(d.hp, 0.0)
	assert_not_null(Content.loot_table(&"nest_loot"))
	assert_true(DirectiveDef.EVENTS.has("burn_nest"))
	var bad := NestDef.new()
	var errs: PackedStringArray = bad.parse({"id": "bad", "props": [], "seed": {"count": 2, "nonsense": 1}}, &"nest", "test")
	assert_gt(errs.size(), 1, "no props and an unknown seed key are errors")


func test_a_nest_seeds_its_guards_near_the_player_not_far() -> void:
	assert_true(_nests.place("n1", &"hollow_nest", NEST, 0.0))
	_nests.tick()
	assert_eq(_nests.guards("n1").size(), 0, "nobody while the player is 240 m off")
	_p.global_position = NEST + Vector3(0, 0, 60)
	_nests.tick()
	var g: Array[Enemy] = _nests.guards("n1")
	var def: NestDef = Content.get_def(&"nest", &"hollow_nest") as NestDef
	assert_eq(g.size(), def.seed_count)
	var asleep: int = 0
	for e: Enemy in g:
		assert_lt(Vector2(e.global_position.x - NEST.x, e.global_position.z - NEST.z).length(), def.seed_ring.y + 0.5, "round the nest")
		if e.state == Enemy.State.SLEEP:
			asleep += 1
	assert_eq(asleep, def.seed_sleepers, "some sleep in its roots")
	_p.global_position = NEST + Vector3(0, 0, 300)
	_nests.tick()
	assert_eq(_nests.guards("n1").size(), 0, "taken away once the player is gone")


func test_a_killed_guard_stays_dead_until_its_respawn() -> void:
	_nests.place("n1", &"root_knot", NEST, 0.0)
	_p.global_position = NEST + Vector3(0, 0, 30)
	_nests.tick()
	var g: Array[Enemy] = _nests.guards("n1")
	var n: int = g.size()
	var info := DamageInfo.make(9999.0, &"pierce", &"melee", _p.state.id)
	info.hit_pos = g[0].global_position + Vector3.UP
	g[0].take_damage(info)
	assert_eq((_nests.state("n1")["seeded_dead"] as Array).size(), 1)
	_nests.tick()
	assert_eq(_nests.guards("n1").size(), n - 1, "not back yet")
	Game.session.clock.total_minutes += 13.0 * 60.0
	_nests.tick()
	assert_eq(_nests.guards("n1").size(), n, "back from the pods after its respawn hours")


func test_only_fire_hurts_it() -> void:
	_nests.place("n1", &"root_knot", NEST, 0.0)
	var hp: float = float(_nests.state("n1")["hp"])
	_hit("n1", 50.0, &"slash")
	_hit("n1", 50.0, &"blunt")
	_hit("n1", 50.0, &"ballistic")
	assert_eq(float(_nests.state("n1")["hp"]), hp, "blades, clubs and bullets do nothing")
	_hit("n1", 9.0, &"fire")
	assert_almost_eq(float(_nests.state("n1")["hp"]), hp - 9.0, 0.01, "a torch blow burns it")


func test_burning_it_wakes_its_guards_drops_loot_pays_and_stays_burned() -> void:
	watch_signals(Events)
	_nests.place("n1", &"root_knot", NEST, 0.0)
	_p.global_position = NEST + Vector3(0, 0, 20)
	_nests.tick()
	var sleepers: Array[Enemy] = []
	for e: Enemy in _nests.guards("n1"):
		if e.state == Enemy.State.SLEEP:
			sleepers.append(e)
	assert_gt(sleepers.size(), 0)
	var spot0: Array = _bloom.sources.get(BloomNests.SPOT_SOURCE, [])
	assert_eq(spot0.size(), 1, "its Bloom is on the ground")
	var prog: Progression = _p.state.progression
	var xp0: int = prog.level * 1000000 + prog.xp
	var drops0: int = get_tree().get_nodes_in_group(&"item_drops").size()
	_hit("n1", 9999.0, &"fire")
	assert_true(_nests.is_burning("n1"))
	for e: Enemy in sleepers:
		assert_ne(e.state, Enemy.State.SLEEP, "its guards wake to the scream")
	var def: NestDef = Content.get_def(&"nest", &"root_knot") as NestDef
	_nests._process(def.burn_seconds + 0.1)
	assert_true(_nests.is_burned("n1"))
	assert_null(_nests.core_of("n1"), "nothing left to burn")
	assert_gt(prog.level * 1000000 + prog.xp, xp0, "burn_nest XP")
	await get_tree().process_frame
	assert_gt(get_tree().get_nodes_in_group(&"item_drops").size(), drops0, "its pods drop loot")
	assert_signal_emitted(Events, "nest_burned")
	# The Bloom fades over the def's fade hours.
	var s_full: float = _nests.spot_strength("n1")
	Game.session.clock.total_minutes += def.burn_fade_hours * 30.0
	assert_lt(_nests.spot_strength("n1"), s_full, "fading")
	Game.session.clock.total_minutes += def.burn_fade_hours * 60.0
	_nests.tick()
	assert_eq(_bloom.sources.get(BloomNests.SPOT_SOURCE, []).size(), 0, "gone once faded")
	# Hits on the dead nest do nothing; it survives a save round-trip burned.
	var w := WorldState.new()
	w.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	assert_true(bool(w.nests["n1"]["burned"]))
	var old := WorldState.new()
	old.from_dict({})
	assert_eq(old.nests, {}, "older saves load with no nests")
	# Re-placed after the load (its region streamed back): burned props, no guards come back.
	_nests.on_unplace("n1")
	Game.session.world.nests = w.nests
	_nests.place("n1", &"root_knot", NEST, 0.0)
	assert_true(_nests.is_burned("n1"))
	assert_null(_nests.core_of("n1"))


func test_unplacing_frees_it_and_keeps_its_state() -> void:
	_nests.on_place({"id": &"enc:1", "kind": &"nest", "def": &"root_knot", "pos": NEST, "yaw": 0.5, "region": &"r", "seed": 1})
	_p.global_position = NEST
	_nests.tick()
	assert_gt(_nests.guards("enc:1").size(), 0)
	_hit("enc:1", 9.0, &"fire")
	_nests.on_unplace(&"enc:1")
	assert_false(_nests.placements.has("enc:1"))
	assert_eq(_nests.guards("enc:1").size(), 0, "its guards go with it")
	assert_true(Game.session.world.nests.has("enc:1"), "its state stays")
	_nests.on_place({"id": &"enc:1", "kind": &"nest", "def": &"root_knot", "pos": NEST, "yaw": 0.5, "region": &"r", "seed": 1})
	var def: NestDef = Content.get_def(&"nest", &"root_knot") as NestDef
	assert_almost_eq(float(_nests.state("enc:1")["hp"]), def.hp - 9.0, 0.01, "its wound stays")


func test_a_region_feature_places_it() -> void:
	var feats: Array[Dictionary] = BloomNests.region_features({"id": "r1", "features": [
		{"type": "nest", "id": "deep", "def": "root_knot", "at": [12, 34], "yaw": 90},
		{"type": "bloom", "at": [0, 0], "radius": 10}]})
	assert_eq(feats.size(), 1)
	assert_eq(feats[0]["id"], "r1:deep")
	assert_eq(feats[0]["at"], Vector2(12, 34))
	assert_almost_eq(float(feats[0]["yaw"]), PI / 2.0, 0.001)
	# The main map's nest, placed when its region attaches.
	_world.world_def = WorldDef.load_from("res://world/main_map")
	var main: Array[Dictionary] = BloomNests.region_features(_world.world_def.region_data("d6_larch_hollow"))
	assert_eq(main.size(), 1, "Larch Hollow has a nest in its deep woods")
	(_world.terrain as FakeTerrain).region_attached.emit("d6_larch_hollow")
	var id: String = main[0]["id"]
	assert_true(_nests.placements.has(id))
	assert_not_null(_nests.core_of(id))
	(_world.terrain as FakeTerrain).region_detached.emit("d6_larch_hollow")
	assert_false(_nests.placements.has(id), "streamed out with its region")
