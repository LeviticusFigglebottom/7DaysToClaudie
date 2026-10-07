extends GutTest
## Bloom nests (ADR-0055) against real nodes: the defs load and validate; a nest seeds its guards
## while the player is near and not when far; only fire hurts it; burning it wakes its guards, puts
## a smoke column over it and plays its own sounds (shriek, burn loop, collapse), pays the burn_nest
## XP, emits the directive event, marks it burned (and it stays so through a save round-trip), its
## pods become searchable remains holding its loot (a looted pod stays looted through a save), and
## its Bloom spot fades; its mat is a clearing in the vegetation; the placement check finds roads,
## water and pads; a region feature places one, and the main map has one.

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


class FakeVegetation:
	extends Node
	var clearings: Dictionary = {}

	func set_clearings(source: StringName, list: Array) -> void:
		clearings[source] = list.duplicate(true)


class FakeWorld:
	extends Node3D
	var ai: Node = null
	var player: Node3D = null
	var terrain: Node = null
	var vegetation: Node = null
	var world_def: WorldDef = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _world: FakeWorld
var _ai: AIDirector
var _nests: BloomNests
var _bloom: FakeBloom
var _veg: FakeVegetation
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
	_veg = FakeVegetation.new()
	_world.add_child(_veg)
	_world.vegetation = _veg
	# The container commands a pod's search runs with no UI (container.take_all).
	_world.add_child(PlayerActions.new())
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
	# The heart follows the root mass's scale (TD-255): the young knot's is 0.6 of the full nest's.
	var knot: NestDef = Content.get_def(&"nest", &"root_knot") as NestDef
	assert_almost_eq(knot.core_size, NestDef.HEART_SIZE * 0.6, Vector3.ONE * 0.001)
	assert_almost_eq(knot.core_offset, NestDef.HEART_OFFSET * 0.6, Vector3.ONE * 0.001)
	assert_eq((Content.get_def(&"nest", &"hollow_nest") as NestDef).core_size, NestDef.HEART_SIZE)
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


func test_burning_it_wakes_its_guards_pays_and_stays_burned() -> void:
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
	assert_eq(get_tree().get_nodes_in_group(&"item_drops").size(), drops0, "nothing dropped on the ground: the pods hold it")
	assert_eq(_nests.pods_of("n1").size(), def.pods().size(), "its pods are searchable remains")
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


func test_the_burn_smokes_and_sounds_like_a_nest() -> void:
	_nests.place("n1", &"hollow_nest", NEST, 0.0)
	var def: NestDef = Content.get_def(&"nest", &"hollow_nest") as NestDef
	_hit("n1", 9999.0, &"fire")
	var smoke: BloomNests.Smoke = _nests._smoke.get("n1")
	assert_not_null(smoke, "a smoke column rises while it burns")
	assert_false(smoke.smouldering)
	assert_almost_eq(smoke.global_position.y, NEST.y + def.core_offset.y + def.core_size.y, 0.01, "over its heart")
	assert_has(_nests.played, BloomNests.SND_SCREAM, "its own shriek")
	assert_does_not_have(_nests.played, &"voice/keener_scream", "not the Keener's")
	assert_has(_nests.played, BloomNests.SND_BURN, "its burn loop")
	var nest: Node = _nests._nodes["n1"]
	var loop: Node = nest.get_node_or_null("BurnLoop")
	assert_not_null(loop, "the loop plays on the nest")
	assert_eq(loop.get_meta(&"sound_id"), BloomNests.SND_BURN)
	assert_eq((nest as BloomNests.Nest).fires.size(), 1 + def.pods().size(), "flames on its heart and every pod")
	_nests._process(def.burn_seconds + 0.1)
	assert_true(_nests.is_burned("n1"))
	assert_has(_nests.played, BloomNests.SND_COLLAPSE, "it falls in with a thud")
	assert_true(is_instance_valid(smoke) and smoke.smouldering, "the smoke lingers after it is dead")
	await get_tree().process_frame
	assert_null((_nests._nodes["n1"] as Node).get_node_or_null("BurnLoop"), "the burn loop is out")
	_nests._process(BloomNests.SMOKE_LINGER * 0.5)
	assert_true(_nests._smoke.has("n1"), "still smouldering")
	_nests._process(BloomNests.SMOKE_LINGER * 0.5 + BloomNests.Smoke.LIFE + 0.1)
	assert_false(_nests._smoke.has("n1"), "gone once it has smouldered out")
	# Un-placing a burning nest takes its smoke too.
	_nests.place("n2", &"root_knot", NEST + Vector3(60, 0, 0), 0.0)
	_hit_at("n2", NEST + Vector3(60, 1, 0))
	assert_true(_nests._smoke.has("n2"))
	_nests.on_unplace("n2")
	assert_false(_nests._smoke.has("n2"))


func _hit_at(id: String, at: Vector3) -> void:
	var info := DamageInfo.make(9999.0, &"fire", &"melee", _p.state.id)
	info.hit_pos = at
	_nests.core_of(id).take_damage(info)


func test_its_pods_are_searchable_remains_that_stay_looted() -> void:
	_nests.place("n1", &"hollow_nest", NEST, 0.0)
	var def: NestDef = Content.get_def(&"nest", &"hollow_nest") as NestDef
	assert_eq(_nests.pods_of("n1").size(), 0, "a living nest's pods are not containers")
	_hit("n1", 9999.0, &"fire")
	_nests._process(def.burn_seconds + 0.1)
	var pods: Array[BloomNests.Pod] = _nests.pods_of("n1")
	assert_eq(pods.size(), def.pods().size())
	var pod: BloomNests.Pod = pods[0]
	assert_not_null(pod.cdef, "the nest_pod container def names it")
	assert_string_starts_with(pod.interact_text(_p), "Search")
	assert_gt(pod.interact_hold_time(_p), 0.0, "searching takes a moment")
	assert_eq(PlayerInteraction.find_interactable(pod), pod, "the interaction ray finds it")
	assert_ne(pod.collision_layer & PlayerInteraction.MASK, 0, "on a layer the ray hits")
	assert_gt(pod.get_child_count(), 1, "it has a body to aim at")
	# Rolled once, seeded by world, nest and pod: the same loot on any search order.
	var inv: Inventory = _nests.pod_inventory("n1", pod.index, _p.state)
	assert_false(inv.stacks.is_empty(), "it holds the nest's loot")
	var items: Array = (Game.session.world.nests["n1"]["pods"] as Dictionary)[str(pod.index)]
	assert_eq(items.size(), inv.stacks.size(), "kept in the nest's state")
	var has_mycelium: bool = false
	for s: ItemStack in inv.stacks:
		has_mycelium = has_mycelium or s.item_id == &"bloom_mycelium"
	assert_true(has_mycelium, "the guaranteed Bloom mycelium")
	# Searching it with no UI takes everything (container.take_all); it stays empty after.
	var had: int = _p.state.inventory.count_of(&"bloom_mycelium")
	pod.interact(_p)
	assert_gt(_p.state.inventory.count_of(&"bloom_mycelium"), had, "taken into the pack")
	assert_true(pod.inventory.stacks.is_empty())
	assert_eq(((Game.session.world.nests["n1"]["pods"] as Dictionary)[str(pod.index)] as Array).size(), 0, "saved empty")
	assert_string_ends_with(pod.interact_text(_p), "(empty)")
	assert_eq(pod.interact_hold_time(_p), 0.0, "no second search")
	pod.interact(_p)
	assert_true(pod.inventory.stacks.is_empty(), "it does not roll again")
	# Another pod, looked at but not emptied.
	var other: BloomNests.Pod = pods[1]
	var n_other: int = _nests.pod_inventory("n1", other.index, _p.state).stacks.size()
	# Through a save: a looted pod stays looted, a half-looted one keeps what it held, an unsearched one is unsearched.
	var w := WorldState.new()
	w.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	_nests.on_unplace("n1")
	Game.session.world.nests = w.nests
	_nests.place("n1", &"hollow_nest", NEST, 0.0)
	var again: Array[BloomNests.Pod] = _nests.pods_of("n1")
	assert_eq(again.size(), def.pods().size())
	for pd: BloomNests.Pod in again:
		if pd.index == pod.index:
			assert_true(pd.searched())
			assert_string_ends_with(pd.interact_text(_p), "(empty)", "a looted pod stays looted")
		elif pd.index == other.index:
			assert_true(pd.searched())
			assert_eq(pd.inventory.stacks.size(), n_other, "what it still holds")
		else:
			assert_false(pd.searched(), "the third was never opened")


func test_its_mat_is_a_clearing_in_the_vegetation() -> void:
	_nests.place("n1", &"hollow_nest", NEST, 0.0)
	var list: Array = _veg.clearings.get(BloomNests.SPOT_SOURCE, [])
	assert_eq(list.size(), 1, "its mat is cleared")
	var def: NestDef = Content.get_def(&"nest", &"hollow_nest") as NestDef
	var r: float = float(list[0]["r"])
	assert_almost_eq(r, BloomNests.mat_radius(def), 0.001)
	assert_gt(r, 4.0, "it covers the props round the heart")
	assert_lt(r, def.bloom_radius, "but not its whole Bloom ground")
	assert_eq(list[0]["pos"], Vector2(NEST.x, NEST.z))
	_nests.on_unplace("n1")
	assert_eq((_veg.clearings.get(BloomNests.SPOT_SOURCE, [-1]) as Array).size(), 0, "given back when it goes")


func test_the_vegetation_leaves_out_what_stands_in_a_clearing() -> void:
	var vm := VegetationManager.new()
	add_child_autofree(vm)
	var layers: Dictionary = {"tree": [], "ground": []}
	for i: int in 6:
		var inst := VegetationScatter.Instance.new()
		inst.index = i
		inst.pos = Vector3(10.0 + i * 4.0, 0.0, 10.0)
		(layers["tree" if i % 2 == 0 else "ground"] as Array).append(inst)
	vm._data[Vector2i(0, 0)] = layers
	vm.set_clearings(&"nests", [{"pos": Vector2(10, 10), "r": 9.0}])
	var hidden: Array = []
	for i: int in 6:
		if vm._is_removed(Vector2i(0, 0), i):
			hidden.append(i)
	assert_eq(hidden, [0, 1, 2], "the trees and plants within 9 m are hidden, indices unchanged")
	assert_false(vm._cleared.has(Vector2i(5, 5)), "far chunks untouched")
	vm.set_clearings(&"nests", [])
	assert_eq(vm.clearing_count(), 0, "given back")
	assert_false(vm._is_removed(Vector2i(0, 0), 0), "nothing hidden once the nest's mats go")


func test_the_placement_check_finds_roads_water_and_pads() -> void:
	var def: NestDef = Content.get_def(&"nest", &"root_knot") as NestDef
	var r: float = BloomNests.mat_radius(def)
	var region: Dictionary = {"id": "t", "features": [
		{"type": "road", "id": "lane", "width": 4.0, "shoulder": 1.0, "points": [[0, 0], [100, 0]]},
		{"type": "lake", "id": "pond", "ellipse": [0, 200, 30, 20, 0], "shore": 5.0},
		{"type": "poi", "id": "cabin", "poi": "trappers_cabin", "origin": [300, 300], "rotation": 0, "size": [20, 10], "skirt": 6}]}
	assert_eq(BloomNests.placement_problems(Vector2(50, 400), r, region, null).size(), 0, "open ground is fine")
	var on_road: PackedStringArray = BloomNests.placement_problems(Vector2(50, 2), r, region, null)
	assert_eq(on_road.size(), 1)
	assert_string_contains(on_road[0], "lane")
	assert_string_contains(BloomNests.placement_problems(Vector2(10, 200), r, region, null)[0], "pond")
	assert_string_contains(BloomNests.placement_problems(Vector2(310, 305), r, region, null)[0], "cabin")
	assert_eq(BloomNests.placement_problems(Vector2(50, 2 + 4.0 * 0.5 + 1.0 + r + 0.5), r, region, null).size(), 0, "just clear of the road")
	# The world's own roads and rivers count too; the main map's nest stands clear.
	assert_eq(BloomNests.placement_warnings("res://world/main_map").size(), 0, "the main map's nest is placed clear")
	var wdef: WorldDef = WorldDef.load_from("res://world/main_map")
	var route9: Polyline2 = wdef.roads[0]["line"]
	assert_gt(BloomNests.placement_problems(route9.points[2], r, {}, wdef).size(), 0, "a nest on Route 9 is reported")


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
