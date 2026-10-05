extends GutTest
## Remand supply drops: the schedule, a deterministic landing spot in range, one drop per day, the
## drone flying the canister in and away (ADR-0023), the canister falling and landing, a landing
## check that keeps clear of trees and player structures, the tether's list of every drop, and
## loot that improves with the drop tier.


class StubTerrain:
	extends Node

	func region_terrain_at(_x: float, _z: float) -> Object:
		return self


class StubWorld:
	extends Node3D
	var player: Node3D
	var terrain: Node
	var water: Node = null
	var pois: Node = null
	var building: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


## Player structures (only their positions matter to the landing check).
class StubBuilding:
	extends Node3D

	func add_piece(at: Vector3) -> void:
		var n := Node3D.new()
		add_child(n)
		n.global_position = at

	func pieces_in_radius(pos: Vector3, r: float) -> Array:
		var out: Array = []
		for n: Node3D in get_children():
			if n.global_position.distance_to(pos) <= r + 2.5:
				out.append(n)
		return out


var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4242, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev


func _world() -> StubWorld:
	var w := StubWorld.new()
	w.terrain = StubTerrain.new()
	w.add_child(w.terrain)
	w.player = Node3D.new()
	w.add_child(w.player)
	add_child_autofree(w)
	return w


func _drops(w: StubWorld) -> SupplyDrops:
	var sd := SupplyDrops.new()
	add_child_autofree(sd)
	sd.world = w
	return sd


func test_schedule_and_tier() -> void:
	assert_eq(SupplyDrops.interval_days("weekly"), 7)
	assert_eq(SupplyDrops.interval_days("every_3_days"), 3)
	assert_eq(SupplyDrops.interval_days("after_hum"), 0)
	assert_eq(SupplyDrops.interval_days("off"), 0)
	assert_eq(SupplyDrops.tier_for(1), 2)
	assert_eq(SupplyDrops.tier_for(50), 4)
	assert_eq(SupplyDrops.tier_for(500), 5)


func test_drop_falls_lands_and_is_marked() -> void:
	var w: StubWorld = _world()
	var sd: SupplyDrops = _drops(w)
	var id: StringName = sd.dispatch(3)
	assert_ne(id, &"")
	assert_eq(sd.dispatch(3), &"", "one drop a day")
	assert_true(Game.session.world.drops.has(String(id)), "persisted for saves")
	var d: SupplyDrops.Drop = sd.drops[id]
	var dist: float = Vector2(d.ground.x, d.ground.z).length()
	assert_between(dist, SupplyDrops.MIN_DIST * 0.4, SupplyDrops.MAX_DIST + 0.1)
	assert_eq(sd.pick_spot(Vector3.ZERO, String(id)), d.ground, "the spot is deterministic")
	assert_false(d.landed)
	assert_gt(d.global_position.y, d.ground.y + 50.0, "released high above the spot")
	d._process(60.0)
	assert_true(d.landed)
	assert_almost_eq(d.global_position.y, d.ground.y, 0.01)
	assert_false(d.emptied())
	assert_eq(sd.markers().size(), 1)
	Game.session.rules.values["supply_drop_markers"] = false
	assert_eq(sd.markers().size(), 0, "the world setting hides the marker")


func test_restored_drop_is_already_on_the_ground() -> void:
	var w: StubWorld = _world()
	Game.session.world.drops["drop_9"] = {"pos": [40.0, 0.0, 130.0], "day": 9, "tier": 3}
	var sd := SupplyDrops.new()
	add_child_autofree(sd)
	sd.setup_world(w)
	var d: SupplyDrops.Drop = sd.drops[&"drop_9"]
	assert_true(d.landed)
	assert_eq(d.tier, 3)
	assert_almost_eq(d.global_position.distance_to(Vector3(40.0, 0.0, 130.0)), 0.0, 0.01)


func _count_rare(tier: int) -> int:
	var n: int = 0
	for i: int in 200:
		var rng := RandomNumberGenerator.new()
		rng.seed = 900 + i
		for st: ItemStack in LootRoller.roll(&"supply_drop", LootRoller.Context.new(tier, 10, rng)):
			if st.item_id in [&"revolver", &"antifungal", &"repair_kit", &"machete"]:
				n += 1
	return n


func test_drop_loot_improves_with_tier() -> void:
	assert_eq(_count_rare(2), 0, "no rare gear at tier 2")
	assert_gt(_count_rare(4), 10)


func test_landing_keeps_clear_of_trees_and_structures() -> void:
	var w: StubWorld = _world()
	var b := StubBuilding.new()
	w.building = b
	w.add_child(b)
	b.add_piece(Vector3(100.0, 0.0, 0.0))
	var sd: SupplyDrops = _drops(w)
	var trees: Array = [{"pos": Vector3(0.0, 0.0, 150.0), "radius": 0.4}]
	sd.tree_source = func(p: Vector3, r: float) -> Array:
		return trees.filter(func(t: Dictionary) -> bool: return Vector2(t["pos"].x - p.x, t["pos"].z - p.z).length() <= r + 1.0)
	assert_true(sd.spot_ok(Vector3(-150.0, 0.0, 0.0)), "open ground is fine")
	assert_false(sd.spot_ok(Vector3(101.5, 0.0, 0.0)), "not on the player's base")
	assert_false(sd.spot_ok(Vector3(2.0, 0.0, 152.0)), "not under a tree: its crown would snag the chute")
	assert_true(sd.spot_ok(Vector3(9.0, 0.0, 150.0)), "a few metres off the trunk is open sky")
	# Anything else solid (a wreck, a rock) is found by its collider.
	var body := StaticBody3D.new()
	body.collision_layer = 1 << 2
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(2.0, 1.5, 4.0)
	cs.shape = box
	body.add_child(cs)
	w.add_child(body)
	body.global_position = Vector3(-60.0, 0.75, 60.0)
	await wait_physics_frames(3)
	assert_false(sd.spot_ok(Vector3(-59.0, 0.0, 61.0)), "not onto a solid prop")
	# Every spot it picks is clear of all of them.
	for i: int in 30:
		var p: Vector3 = sd.pick_spot(Vector3.ZERO, "t%d" % i)
		assert_true(sd.spot_ok(p), "picked spot %d is clear" % i)


func test_the_drone_flies_the_lift_in_and_away() -> void:
	var w: StubWorld = _world()
	var sd: SupplyDrops = _drops(w)
	var id: StringName = sd.dispatch(4)
	var d: SupplyDrops.Drop = sd.drops[id]
	assert_not_null(d.drone, "a drone brings it")
	var f: ProgramDrone.Flight = d.flight
	assert_almost_eq(Vector2(f.start.x - d.ground.x, f.start.z - d.ground.z).length(), float(Content.config(&"program_drone")["approach_m"]), 0.5)
	assert_almost_eq(f.position(f.release_time()).distance_to(d.ground + Vector3.UP * SupplyDrops.RELEASE_HEIGHT), 0.0, 0.01, "it hovers over the spot to let go")
	assert_eq(sd.entries()[0]["state"], "inbound")
	# Carried until the release: the canister rides under the drone.
	d._process(f.release_time() * 0.5)
	assert_false(d.landed)
	assert_almost_eq(d.global_position.distance_to(f.position(d._t) + ProgramDrone.HANG), 0.0, 0.01, "carried on the sling")
	assert_almost_eq(d.drone.global_position.distance_to(f.position(d._t)), 0.0, 0.3)
	# Speed falls to a hover, then it climbs away.
	assert_almost_eq(f.velocity(f.t_arrive + 0.5).length(), 0.0, 0.01)
	assert_gt(f.velocity(f.t_arrive * 0.3).length(), float(Content.config(&"program_drone")["cruise_speed"]) * 0.95)
	assert_gt(f.position(f.t_end).y, f.hover.y + 40.0)
	d._process(f.release_time() * 0.5 + 0.5)
	assert_eq(sd.entries()[0]["state"], "falling")
	var t_fall: float = (SupplyDrops.RELEASE_HEIGHT - 1.9) / SupplyDrops.FALL_SPEED
	d._process(t_fall + 1.0)
	assert_true(d.landed, "lands about %.0f s after the release" % t_fall)
	assert_almost_eq(d.global_position.distance_to(d.ground), 0.0, 0.01, "on the spot")
	assert_eq(sd.entries()[0]["state"], "landed")
	# Doppler: higher approaching, lower going away.
	var lis := Vector3(0.0, 0.0, 0.0)
	assert_gt(ProgramDrone.doppler(Vector3(0, 0, -300), Vector3(0, 0, 30), lis, Vector3.ZERO), 1.05)
	assert_lt(ProgramDrone.doppler(Vector3(0, 0, 300), Vector3(0, 0, 30), lis, Vector3.ZERO), 0.95)
	# The drone is gone once its flight is over.
	d._process(f.t_end)
	await wait_frames(2)
	assert_false(is_instance_valid(d.drone) and d.drone != null and d.drone.is_inside_tree(), "the drone leaves")


func test_the_tether_lists_every_drop() -> void:
	var w: StubWorld = _world()
	var sd: SupplyDrops = _drops(w)
	for day: int in [9, 2, 5]:
		Game.session.world.drops["drop_%d" % day] = {"pos": [40.0 * day, 0.0, 0.0], "day": day, "tier": 2}
		sd._spawn(StringName("drop_%d" % day), Vector3(40.0 * day, 0.0, 0.0), 2, true)
	var list: Array[Dictionary] = sd.entries()
	assert_eq(list.size(), 3, "every drop, not just the nearest")
	assert_eq(list.map(func(e: Dictionary) -> int: return int(e["day"])), [2, 5, 9], "in the order they came")
	var text: String = Tether.drops_lines(list, Vector3.ZERO)
	assert_eq(text.split("\n").size(), 3, "one line each")
	assert_string_contains(text, "80 m")
	assert_string_contains(text, "LANDED")
	var many: Array = []
	for i: int in 7:
		many.append({"pos": Vector3(0.0, 0.0, -100.0 * (i + 1)), "state": "landed"})
	var packed: PackedStringArray = Tether.drops_lines(many, Vector3.ZERO).split("\n")
	assert_lte(packed.size(), 4, "seven drops still fit")
	assert_string_contains("\n".join(packed), "700 m")
