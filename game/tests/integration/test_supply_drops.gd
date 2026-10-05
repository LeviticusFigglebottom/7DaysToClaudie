extends GutTest
## Remand supply drops: the schedule, a deterministic landing spot in range, one drop per day, the
## canister falling and landing, the tether marker, and loot that improves with the drop tier.


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

	func height_at(_x: float, _z: float) -> float:
		return 0.0


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
