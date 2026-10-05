extends GutTest
## Dawn rooting leaves a mark (ADR-0025): a Hum survivor that roots into the soil leaves a fungal
## mound, kept in WorldState.mounds (saved, save v4). It swells, then shrinks and is gone after its
## lifetime; while it stands the Bloom field takes the ground around it; it can be torn open once.


class StubWorld:
	extends Node3D
	var terrain: TerrainManager


var _prev: GameSession
var _picked: Array = []


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4242, "game_mode": "survival"})
	_picked.clear()
	Game.register_command(&"world.pickup_item", func(args: Dictionary) -> Dictionary:
		_picked.append(args)
		return {"ok": true, "left": 0})


func after_each() -> void:
	Game.unregister_command(&"world.pickup_item")
	Game.session = _prev


## A flat 256 m region at 5 m with no authored Bloom, a terrain manager over it and the mounds.
func _mounds() -> BloomMounds:
	var w := WorldDef.new()
	w.id = "mound_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var rt := RegionTerrain.new()
	rt.region_id = "t"
	rt.rect = w.region_rect("t")
	rt.spacing = 2.0
	var n: int = 129
	rt.height = HeightField.create(rt.rect.position, 2.0, n, n, 5.0)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.vegmask.fill(255)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["conifer_forest"])
	var sw := StubWorld.new()
	add_child_autofree(sw)
	var tm := TerrainManager.new()
	sw.add_child(tm)
	tm.setup(w, {"t": rt}, {})
	sw.terrain = tm
	var m := BloomMounds.new()
	sw.add_child(m)
	m.setup_world(sw)
	return m


func test_a_mound_swells_then_shrinks_and_goes() -> void:
	assert_eq(BloomMounds.growth(-0.1, 6.0, 6.0), 0.0, "not before it rooted")
	assert_lt(BloomMounds.growth(0.05, 6.0, 6.0), 0.5, "still swelling an hour in")
	assert_gt(BloomMounds.growth(0.5, 6.0, 6.0), 0.9, "full by midday")
	assert_lt(BloomMounds.growth(5.5, 6.0, 6.0), BloomMounds.growth(2.0, 6.0, 6.0), "shrinking with the days")
	assert_gt(BloomMounds.growth(5.9, 6.0, 6.0), 0.3, "sunk low but still there")
	assert_eq(BloomMounds.growth(6.0, 6.0, 6.0), 0.0, "gone after its lifetime")


func test_a_rooted_hollow_leaves_a_saved_mound_that_takes_the_ground() -> void:
	var m: BloomMounds = _mounds()
	var at := Vector3(10.0, 0.0, 12.0)
	assert_eq(m.terrain.bloom_at(at.x, at.z), 0.0, "clean ground before")
	Events.hollowed_rooted.emit(&"z:000101", &"hollow", at)
	var mounds: Dictionary = Game.session.world.mounds
	assert_true(mounds.has("mound:z:000101"), "recorded in the world state")
	var st: Dictionary = mounds["mound:z:000101"]
	assert_almost_eq(float(st["pos"][1]), 5.0, 1e-4, "on the ground")
	assert_true(BloomMounds.MODELS.has(str(st["model"])))
	assert_false(bool(st["harvested"]))
	# Half a day later it has swollen to full size and the Bloom has taken the ground around it.
	Game.session.clock.advance_minutes(720.0)
	m._sync(false)
	assert_gt(m.terrain.bloom_at(at.x, at.z), 0.5, "the web spreads around it")
	assert_eq(m.terrain.bloom_base_at(at.x, at.z), 0.0, "the authored field (scatter) is untouched")
	assert_eq(m.get_child_count(), 1, "one mound body")
	# Rooting twice changes nothing.
	Events.hollowed_rooted.emit(&"z:000101", &"hollow", at)
	assert_eq(mounds.size(), 1)
	# After its lifetime it is gone, and so is its mark on the ground.
	Game.session.clock.advance_minutes(float(Content.config(&"bloom")["mounds"]["lifetime_days"]) * 1440.0)
	m._sync(false)
	assert_false(mounds.has("mound:z:000101"), "dropped from the world state")
	assert_eq(m.terrain.bloom_at(at.x, at.z), 0.0, "the ground is clean again")


func test_a_mound_is_torn_open_once_within_reach() -> void:
	var m: BloomMounds = _mounds()
	Events.hollowed_rooted.emit(&"z:000102", &"hollow", Vector3(-20.0, 0.0, 30.0))
	var ps: PlayerState = Game.local_player()
	ps.position = Vector3(-60.0, 5.0, 30.0)
	var far: Dictionary = Game.execute(&"bloom.harvest_mound", {"player": String(ps.id), "mound": "mound:z:000102"})
	assert_false(bool(far["ok"]), "too far away")
	ps.position = Vector3(-21.0, 5.0, 30.5)
	var res: Dictionary = Game.execute(&"bloom.harvest_mound", {"player": String(ps.id), "mound": "mound:z:000102"})
	assert_true(bool(res["ok"]), str(res))
	assert_gte(int((res["items"] as Dictionary).get("bloom_mycelium", 0)), 2, "mycelium from its felt")
	assert_false(_picked.is_empty(), "handed to the player through world.pickup_item")
	assert_true(bool(Game.session.world.mounds["mound:z:000102"]["harvested"]))
	var again: Dictionary = Game.execute(&"bloom.harvest_mound", {"player": String(ps.id), "mound": "mound:z:000102"})
	assert_false(bool(again["ok"]), "only once")
	var none: Dictionary = Game.execute(&"bloom.harvest_mound", {"player": String(ps.id), "mound": "mound:nope"})
	assert_false(bool(none["ok"]))
	assert_not_null(m)


func test_mounds_survive_a_save_and_old_saves_gain_none() -> void:
	var ws := WorldState.new()
	ws.mounds = {"mound:z:1": {"pos": [1.0, 2.0, 3.0], "yaw": 0.5, "model": BloomMounds.MODELS[0], "day": 7.25, "harvested": false}}
	var back := WorldState.new()
	back.from_dict(JSON.parse_string(JSON.stringify(ws.to_dict())))
	assert_eq(back.mounds.size(), 1)
	assert_almost_eq(float(back.mounds["mound:z:1"]["day"]), 7.25, 1e-6)
	var old: Dictionary = SaveSystem.migrate({"save_version": 3, "session": {"world": {"trees": {}}}})
	assert_eq(int(old["save_version"]), SaveSystem.CURRENT_VERSION)
	assert_eq(old["session"]["world"]["mounds"], {}, "v3 -> v4 adds the (empty) mound ledger")
