extends GutTest
## Hollowed through windows (TD-011, WindowLinks): a window's sill is above the nav bake's climb,
## so the mesh either side of a wall only joins through a window's link. A Hollow hunting someone
## behind a glazed window paths to it, breaks the glass and climbs over the sill (flat floor, two
## hand-made nav regions either side of the wall, the link between them).

const PLAYER_SCENE: String = "res://src/player/player.tscn"


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
var _rids: Array[RID] = []


func before_each() -> void:
	_prev = Game.session
	_prev_world = Game.world
	Game.session = GameSession.create_new({"seed": 9157, "game_mode": "survival"})
	Game.session.clock.set_time(2, 12.0)
	_root = FlatWorld.new()
	add_child_autofree(_root)
	_box(Vector3(0, -0.5, 0), Vector3(40, 1, 40), 1)
	var st := Stimuli.new()
	_root.add_child(st)
	st.recenter(Vector3.ZERO)
	_ai = AIDirector.new()
	_root.add_child(_ai)
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_root.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = Vector3(0, 0, 4)
	_p.set_physics_process(false)
	_p.head.position.y = 1.65
	_root.player = _p
	Game.world = _root


func after_each() -> void:
	WindowLinks.free_links(_rids)
	_rids.clear()
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


func _region(z0: float, z1: float) -> void:
	var nm := NavigationMesh.new()
	nm.vertices = PackedVector3Array([Vector3(-8, 0, z0), Vector3(8, 0, z0), Vector3(8, 0, z1), Vector3(-8, 0, z1)])
	nm.add_polygon(PackedInt32Array([3, 2, 1, 0]) if z1 < z0 else PackedInt32Array([0, 1, 2, 3]))
	var r: RID = NavigationServer3D.region_create()
	NavigationServer3D.region_set_map(r, _root.get_world_3d().navigation_map)
	NavigationServer3D.region_set_navigation_mesh(r, nm)
	_rids.append(r)


## A wall along x at z = 0 (10 m each side of a 1 m window, sill 0.9 m, lintel at 2 m) and the
## window's glass; the nav regions stop short of it either side, the link spans it.
func _wall_with_window() -> PoiPieces.Breakable:
	_box(Vector3(-5.5, 1.3, 0), Vector3(10, 2.6, 0.2), 1)
	_box(Vector3(5.5, 1.3, 0), Vector3(10, 2.6, 0.2), 1)
	_box(Vector3(0, 0.45, 0), Vector3(1, 0.9, 0.2), 1)
	_box(Vector3(0, 2.3, 0), Vector3(1, 0.6, 0.2), 1)
	var g := PoiPieces.Breakable.new()
	g.kind = "glass"
	g.hp = 1.0
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(1, 1.1, 0.03)
	cs.shape = shape
	g.add_child(cs)
	_root.add_child(g)
	g.global_position = Vector3(0, 1.45, 0)
	_region(-0.4, -12.0)
	_region(0.4, 12.0)
	var map: RID = _root.get_world_3d().navigation_map
	_rids.append(WindowLinks.make(map, Vector3(0, 0, -0.6), Vector3(0, 0, 0.6), {"sill": 0.9, "pieces": [g]}))
	# The regions join the map on one of the server's own syncs: wait until both answer.
	var until: int = Time.get_ticks_msec() + 5000
	while NavigationServer3D.map_get_iteration_id(map) == 0 and Time.get_ticks_msec() < until:
		await get_tree().physics_frame
	while Time.get_ticks_msec() < until and [Vector3(2, 0, -5), Vector3(2, 0, 5)].any(func(q: Vector3) -> bool:
			return NavigationServer3D.map_get_closest_point(map, q).distance_to(q) > 0.1):
		await get_tree().physics_frame
	return g


func test_a_hollow_breaks_the_glass_and_climbs_in_after_you() -> void:
	var glass: PoiPieces.Breakable = await _wall_with_window()
	var e: Enemy = _ai.spawn(&"hollow", Vector3(3, 0.05, -7), {"tier": "normal", "authored": true, "yaw": 0.0, "id": "vault:in"})
	await get_tree().physics_frame
	await get_tree().physics_frame
	e.last_seen_time = e._now() + 30.0  # it knows where you are: the hunt, not the noticing
	e.target_pos = _p.global_position
	e._set_state(Enemy.State.CHASE)
	var vaulted: bool = false
	var reached: bool = false
	for i: int in 60 * 25:
		await get_tree().physics_frame
		vaulted = vaulted or e.state == Enemy.State.VAULT
		var d: Vector3 = e.global_position - _p.global_position
		if e.global_position.z > 0.3 and Vector2(d.x, d.z).length() < 2.2:
			reached = true
			break
	assert_true(vaulted, "it climbed through the window")
	assert_true(glass.is_broken(), "breaking the glass first")
	assert_true(reached, "and came in to you (at %s, state %s)" % [e.global_position, Enemy.State.keys()[e.state]])
	assert_false(e.get(&"_shape").disabled, "collision back on once through")


func test_whole_glass_and_boards_cost_more_than_an_empty_window() -> void:
	var g := PoiPieces.Breakable.new()
	g.kind = "glass"
	g.hp = 1.0
	var b := PoiPieces.Breakable.new()
	b.kind = "boards"
	b.hp = 150.0
	autofree(g)
	autofree(b)
	assert_eq(WindowLinks.cost({"pieces": []}), WindowLinks.COST_OPEN)
	assert_eq(WindowLinks.cost({"pieces": [g]}), WindowLinks.COST_GLASS)
	assert_eq(WindowLinks.cost({"pieces": [g, b]}), WindowLinks.COST_BOARDS)
	assert_eq(WindowLinks.blocker({"pieces": [g, b]}), b, "the boards outside come off first")
	b.hp = 0.0
	assert_eq(WindowLinks.blocker({"pieces": [g, b]}), g)
	g.hp = 0.0
	assert_eq(WindowLinks.cost({"pieces": [g, b]}), WindowLinks.COST_OPEN, "smashed through: cheap again")
	assert_null(WindowLinks.blocker({"pieces": [g, b]}))


func test_a_built_house_links_its_ground_floor_window_across_the_wall() -> void:
	var raw: Dictionary = {"id": "window_links_test", "name": "Window Links Test", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "way_in", "at": [1, 2], "side": "S", "type": "window", "state": "closed"}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}],
		"loot_room": {"room": "A", "level": 0}}
	var pd := PoiDef.new()
	assert_eq(pd.parse(raw, &"poi", "test"), PackedStringArray())
	Game.world = null  # no ground to read: the link's ends stay at the floor
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), &"test/window_links")
	_root.add_child(inst)
	await get_tree().process_frame
	await get_tree().physics_frame
	var links: Array[RID] = (inst.get(&"_window_links") as Array[RID]).duplicate()
	assert_eq(links.size(), 1, "one window, one link")
	if links.size() != 1:
		return
	var info: Dictionary = WindowLinks.info(links[0])
	assert_eq(str(info["opening"]), "way_in")
	assert_eq((info["pieces"] as Array).size(), 1, "its glass is what is in the way")
	assert_eq(WindowLinks.cost(info), WindowLinks.COST_GLASS)
	# The window's wall: south side of cell (1, 2), world z = origin.y + 3 (outside is +z).
	var wz: float = inst.layout.origin.y + 3.0
	var a: Vector3 = NavigationServer3D.link_get_start_position(links[0])
	var b: Vector3 = NavigationServer3D.link_get_end_position(links[0])
	assert_almost_eq(a.z, wz + WindowLinks.REACH, 0.01, "starts outside the wall")
	assert_almost_eq(b.z, wz - WindowLinks.REACH, 0.01, "ends inside it")
	assert_almost_eq(a.x, inst.layout.origin.x + 1.5, 0.01, "on the window's centre line")
	assert_gt(float(info["sill"]), b.y + 0.7, "a sill to climb, above the floor")
	var glass: PoiPieces.Breakable = info["pieces"][0]
	glass.hp = 0.0  # as take_damage leaves it
	glass.smash()
	await get_tree().physics_frame  # the server applies link changes on its sync
	assert_eq(NavigationServer3D.link_get_enter_cost(links[0]), WindowLinks.COST_OPEN, "glass smashed: cheap to come through")
	_root.remove_child(inst)
	assert_eq(WindowLinks.info(links[0]), {}, "the links go with the building")
	inst.free()
