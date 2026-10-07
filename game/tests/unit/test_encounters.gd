extends GutTest
## Forest encounters (ADR-0054): the planner is deterministic from the world seed and a region's
## data (same sites, same ids, same order; another seed gives others), keeps to its density and to
## every exclusion (region edge, vegetation mask, biome, slope, roads, buildings, water, spacing),
## and scales with the encounter_density world setting. Encounters builds a region's sites when it
## attaches (through its steps), takes them down when it detaches, opens and closes their
## vegetation clearings, hands a registered kind's sites to its callbacks (and catches up on sites
## already standing), and skips a kind nobody registered. What a player changes (a looted
## container, a dead sleeper, a taken note) is saved as differences and comes back.

const MAIN_MAP: String = "res://world/main_map"
const LARCH: String = "d6_larch_hollow"
const SEED: int = 4471

var _prev: GameSession
static var _larch: RegionTerrain = null


## What Encounters reads from its world.
class StubWorld:
	extends Node3D
	var terrain: TerrainManager
	var vegetation: Node
	var pois: Node = null
	var building: Node = null
	var ai: Node = null
	var player: Node3D = null


## Records the clearings Encounters asks the vegetation for.
class StubVegetation:
	extends Node
	var clearings: Dictionary = {}

	func add_clearing(id: StringName, at: Vector2, r_trees: float, r_brush: float) -> void:
		clearings[id] = [at, r_trees, r_brush]

	func remove_clearing(id: StringName) -> void:
		clearings.erase(id)


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": SEED, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev
	Encounters.unregister_kind(&"test_dummy")
	Content.remove_runtime_def(&"encounter", &"test_dummy_site")
	Content.remove_runtime_def(&"encounter", &"test_sleepers")


static func _region() -> RegionTerrain:
	if _larch == null:
		_larch = TerrainComposer.get_or_compose(WorldDef.load_from(MAIN_MAP), LARCH, 8.0)
	return _larch


func _cfg() -> Dictionary:
	return Content.config(&"encounters")


# --- The planner --------------------------------------------------------------------------------

func test_data_loads_and_every_kind_is_planned_from_data() -> void:
	var defs: Array = Content.all(&"encounter")
	assert_gte(defs.size(), 9, "the nine kinds of the owner's list")
	var ids: Array = defs.map(func(d: EncounterDef) -> String: return String(d.id))
	for want: String in ["abandoned_campsite", "hunting_stand", "wrecked_car", "logging_truck", "hermit_shack", "cordon_body_bags",
			"survivor_cache", "bloom_kill", "lone_grave", "broken_atv"]:
		assert_has(ids, want)
	var shack: EncounterDef = Content.get_def(&"encounter", &"hermit_shack") as EncounterDef
	assert_eq(shack.ekind, &"poi")
	assert_true((Content.get_def(&"poi", shack.poi) as PoiDef).zoning.has("encounter"), "no town lot draws the shack")
	assert_true(GameRules.options().has("encounter_density"), "a world setting")


func test_plan_is_deterministic() -> void:
	var rt: RegionTerrain = _region()
	var a: Array[Dictionary] = EncounterPlanner.plan_region(rt, SEED, 1.0, _cfg())
	var b: Array[Dictionary] = EncounterPlanner.plan_region(rt, SEED, 1.0, _cfg())
	assert_gt(a.size(), 0, "Larch Hollow's forest gets encounters")
	assert_eq(JSON.stringify(a.map(EncounterPlanner.public_site)), JSON.stringify(b.map(EncounterPlanner.public_site)), "same seed, same sites")
	var c: Array[Dictionary] = EncounterPlanner.plan_region(rt, SEED + 1, 1.0, _cfg())
	assert_ne(JSON.stringify(a.map(EncounterPlanner.public_site)), JSON.stringify(c.map(EncounterPlanner.public_site)), "another seed, other sites")
	var seen: Dictionary = {}
	var cell: float = float(_cfg().get("cell", 128.0))
	for s: Dictionary in a:
		assert_false(seen.has(s["id"]), "ids are unique")
		seen[s["id"]] = true
		# The id names the cell the site was drawn in, which the region owns.
		var k: PackedStringArray = String(s["id"]).trim_prefix("enc:").split("_")
		assert_true(rt.rect.has_point(Vector2((int(k[0]) + 0.5) * cell, (int(k[1]) + 0.5) * cell)), "%s: its cell is the region's" % s["id"])
		assert_eq(s["region"], StringName(LARCH))
		for key: String in ["id", "kind", "def", "pos", "yaw", "region", "seed"]:
			assert_true(s.has(key), "site has %s" % key)


func test_density_bounds_and_world_setting() -> void:
	var rt: RegionTerrain = _region()
	var km2: float = rt.rect.get_area() / 1.0e6
	var one: int = EncounterPlanner.plan_region(rt, SEED, 1.0, _cfg()).size()
	var per_km2: float = float(_cfg().get("per_km2", 10.0))
	assert_between(float(one) / km2, per_km2 * 0.25, per_km2 * 1.6, "about per_km2 on a forest region (%d sites)" % one)
	assert_eq(EncounterPlanner.plan_region(rt, SEED, 0.0, _cfg()).size(), 0, "encounter_density 0 turns them off")
	var two: int = EncounterPlanner.plan_region(rt, SEED, 2.0, _cfg()).size()
	assert_gt(two, one, "a denser setting places more")
	# Never more than one a cell.
	var cell: float = float(_cfg().get("cell", 128.0))
	assert_lte(two, int(rt.rect.get_area() / (cell * cell)))


func test_exclusion_rules_hold_for_every_site() -> void:
	var rt: RegionTerrain = _region()
	var cfg: Dictionary = EncounterPlanner.DEFAULTS.duplicate()
	cfg.merge(_cfg(), true)
	var ctx := EncounterPlanner._Ctx.new(rt, cfg, rt.height.sample, SEED)
	var sites: Array[Dictionary] = EncounterPlanner.plan_region(rt, SEED, 3.0, _cfg())
	assert_gt(sites.size(), 5)
	var spacing: float = float(cfg["spacing"])
	var inner: Rect2 = rt.rect.grow(-float(cfg["edge"]))
	for i: int in sites.size():
		var s: Dictionary = sites[i]
		var def: EncounterDef = Content.get_def(&"encounter", s["def"]) as EncounterDef
		var p := Vector2((s["pos"] as Vector3).x, (s["pos"] as Vector3).z)
		var what: String = "%s %s" % [s["id"], s["def"]]
		assert_true(inner.has_point(p), "%s: off the region's edge" % what)
		assert_gt(def.weight_in(rt.biome_at(p.x, p.y)), 0.0, "%s: a biome it belongs in" % what)
		assert_gt(float((cfg["biomes"] as Dictionary).get(rt.biome_at(p.x, p.y), 0.0)), 0.0, "%s: never in town or yard" % what)
		assert_lte(ctx.slope_over(p, def.radius), def.slope_max + 0.01, "%s: slope" % what)
		assert_gte(ctx.building_distance(p), def.min_building, "%s: clear of every building and lot" % what)
		var road_d: float = float(ctx.nearest(ctx.roads, p, 400.0, def.road_surfaces)[0])
		assert_true(road_d >= def.road.x - 0.01 and (road_d <= def.road.y + 0.01 or def.road.y > 1.0e8), "%s: road band (%.1f m)" % [what, road_d])
		if def.snap == "":
			assert_gte(rt.veg_at(p.x, p.y), float(cfg["min_veg"]), "%s: on forest floor (no road, water, pad)" % what)
		if def.min_water > 0.0:
			assert_gte(ctx.water_distance(p, def.min_water + 8.0), def.min_water, "%s: clear of water" % what)
		for j: int in i:
			var q: Vector3 = sites[j]["pos"]
			assert_gte(p.distance_to(Vector2(q.x, q.z)), spacing, "%s: spaced from %s" % [what, sites[j]["id"]])
	# A building dropped onto a site: the site is no longer planned there.
	var probe: RegionTerrain = RegionTerrain.new()
	probe.region_id = rt.region_id
	probe.rect = rt.rect
	probe.height = rt.height
	probe.biome = rt.biome
	probe.biome_ids = rt.biome_ids
	probe.vegmask = rt.vegmask
	probe.roads = rt.roads
	probe.water = rt.water
	probe.placements = rt.placements.duplicate()
	var victim: Vector3 = sites[0]["pos"]
	probe.placements.append({"kind": "lot", "def": "x", "id": "x/blocker", "origin": [victim.x, victim.y, victim.z], "rotation": 0.0, "size": [20, 20]})
	for s2: Dictionary in EncounterPlanner.plan_region(probe, SEED, 3.0, _cfg()):
		assert_gt((s2["pos"] as Vector3).distance_to(victim), 10.0, "nothing planned on the new lot")


func test_tree_anchored_sites_stand_at_a_trunk() -> void:
	var rt: RegionTerrain = _region()
	var anchored: int = 0
	for s: Dictionary in EncounterPlanner.plan_region(rt, SEED, 3.0, _cfg()):
		var def: EncounterDef = Content.get_def(&"encounter", s["def"]) as EncounterDef
		if def.anchor != "tree":
			continue
		anchored += 1
		assert_gt(float(s["trunk"]), 0.0, "%s knows its trunk" % s["id"])
		var p: Vector3 = s["pos"]
		var key := Vector2i(floori(p.x / VegetationScatter.CHUNK), floori(p.z / VegetationScatter.CHUNK))
		var found: bool = false
		for inst: VegetationScatter.Instance in VegetationScatter.scatter_chunk(key, rt, SEED, rt.height.sample, Callable(), 1).get("tree", []):
			if Vector2(inst.pos.x, inst.pos.z).distance_to(Vector2(p.x, p.z)) < 0.01:
				found = true
		assert_true(found, "%s stands on a tree of the scatter" % s["id"])
	if anchored == 0:
		pass_test("no ladder stand drawn in this region at this density")


# --- Building and streaming ---------------------------------------------------------------------

func _world(rt: RegionTerrain) -> StubWorld:
	var w := StubWorld.new()
	w.terrain = TerrainManager.new()
	w.terrain.regions = {rt.region_id: rt}
	autofree(w.terrain)
	w.vegetation = StubVegetation.new()
	w.add_child(w.vegetation)
	add_child_autofree(w)
	return w


func _encounters(w: StubWorld, sites: Array) -> Encounters:
	var e := Encounters.new()
	e.height_fn = func(_x: float, _z: float) -> float: return 10.0
	e.plan_fn = func(rid: String, _d: float, _c: Dictionary) -> Array:
		return sites.filter(func(s: Dictionary) -> bool: return String(s["region"]) == rid)
	w.add_child(e)
	e.setup_world(w)
	return e


static func _site(id: String, def: String, kind: String, pos: Vector3, rid: String = "r0") -> Dictionary:
	return {"id": StringName(id), "kind": StringName(kind), "def": StringName(def), "pos": pos, "yaw": 0.3,
		"region": StringName(rid), "seed": Ids.hash64(id), "trunk": 0.0}


static func _rt(rid: String) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = rid
	rt.rect = Rect2(0, 0, 1024, 1024)
	return rt


func _settle(e: Encounters) -> void:
	for i: int in 200:
		if e.steps.is_idle():
			return
		e.steps.run_frame()


func test_sites_build_on_attach_and_go_on_detach() -> void:
	var rt: RegionTerrain = _rt("r0")
	var w: StubWorld = _world(rt)
	var sites: Array = [_site("enc:1_1", "abandoned_campsite", "scene", Vector3(200, 10, 200)),
		_site("enc:2_2", "lone_grave", "scene", Vector3(330, 10, 330))]
	var e: Encounters = _encounters(w, sites)
	assert_true(e.placed.is_empty(), "built in steps, not in setup")
	_settle(e)
	assert_eq(e.placed.size(), 2, "both sites stand")
	var camp: EncounterSite = e.node_of(&"enc:1_1")
	assert_not_null(camp)
	assert_gt(camp.get_child_count(), 2, "props on the ground")
	assert_true(camp.container_ids.has(&"enc:1_1:cooler"), "the cooler is a container keyed by the site")
	var ids_before: Array[StringName] = camp.container_ids.duplicate()
	var veg: StubVegetation = w.vegetation
	assert_eq(veg.clearings.size(), 2, "a clearing round each")
	assert_eq(float(veg.clearings[&"enc:1_1"][1]), (Content.get_def(&"encounter", &"abandoned_campsite") as EncounterDef).clear_trees)
	w.terrain.region_detached.emit("r0")
	assert_true(e.placed.is_empty(), "taken down with the region")
	assert_true(veg.clearings.is_empty(), "the forest grows back")
	await get_tree().process_frame
	assert_false(is_instance_valid(camp), "the scene is freed")
	w.terrain.region_attached.emit("r0")
	_settle(e)
	assert_eq(e.placed.size(), 2, "back with the region (from the kept plan)")
	var again: EncounterSite = e.node_of(&"enc:1_1")
	assert_eq(again.container_ids, ids_before, "the same scene, the same containers")


func test_detach_before_the_build_step_drops_it() -> void:
	var rt: RegionTerrain = _rt("r0")
	var w: StubWorld = _world(rt)
	var e: Encounters = _encounters(w, [_site("enc:1_1", "survivor_cache", "scene", Vector3(200, 10, 200))])
	w.terrain.region_detached.emit("r0")
	_settle(e)
	assert_true(e.placed.is_empty(), "a site whose region left is not built")


func test_real_plan_runs_on_a_worker() -> void:
	var rt: RegionTerrain = _region()
	var w: StubWorld = _world(rt)
	var e := Encounters.new()
	e.height_fn = rt.height.sample
	w.add_child(e)
	e.setup_world(w)
	assert_true(e._jobs.has(LARCH), "planned on a worker")
	for i: int in 400:
		e._collect()
		if not e._jobs.has(LARCH):
			break
		await get_tree().process_frame
	assert_true(e.plans.has(LARCH))
	var want: Array[Dictionary] = EncounterPlanner.plan_region(rt, SEED, GameRules.current().num("encounter_density"), _cfg(), rt.height.sample)
	assert_eq((e.plans[LARCH] as Array).size(), want.size(), "the same plan as the planner's")
	_settle(e)
	var expect: int = 0
	for s: Dictionary in want:
		if StringName(str(s["kind"])) == &"scene":
			expect += 1
	assert_eq(e.placed.size(), expect, "every scene site built (the shack needs a PoiManager)")


func _dummy_def() -> void:
	var d := EncounterDef.new()
	assert_eq(d.parse({"id": "test_dummy_site", "kind": "test_dummy", "biomes": {"conifer_forest": 1.0}}, &"encounter", "test"), PackedStringArray())
	Content.add_runtime_def(d)


func test_registered_kind_gets_its_sites() -> void:
	_dummy_def()
	var placed: Array = []
	var removed: Array = []
	Encounters.register_kind(&"test_dummy", func(site: Dictionary) -> void: placed.append(site),
		func(id: StringName) -> void: removed.append(id))
	var rt: RegionTerrain = _rt("r0")
	var w: StubWorld = _world(rt)
	var e: Encounters = _encounters(w, [_site("enc:3_3", "test_dummy_site", "test_dummy", Vector3(400, 10, 400))])
	_settle(e)
	assert_eq(placed.size(), 1, "on_place ran")
	var got: Dictionary = placed[0]
	assert_eq(got.keys().size(), 7, "exactly the documented keys")
	for key: String in ["id", "kind", "def", "pos", "yaw", "region", "seed"]:
		assert_true(got.has(key), "on_place gets %s" % key)
	assert_eq(got["id"], &"enc:3_3")
	assert_eq(got["region"], &"r0")
	assert_true(w.vegetation.clearings.has(&"enc:3_3"), "its clearing too (from its data)")
	w.terrain.region_detached.emit("r0")
	assert_eq(removed, [&"enc:3_3"], "on_unplace on detach")


func test_unregistered_kind_waits_and_catches_up() -> void:
	_dummy_def()
	var rt: RegionTerrain = _rt("r0")
	var w: StubWorld = _world(rt)
	var e: Encounters = _encounters(w, [_site("enc:3_3", "test_dummy_site", "test_dummy", Vector3(400, 10, 400))])
	_settle(e)
	assert_true(e.placed.is_empty(), "nobody builds an unregistered kind")
	var placed: Array = []
	Encounters.register_kind(&"test_dummy", func(site: Dictionary) -> void: placed.append(site["id"]), func(_id: StringName) -> void: pass)
	assert_eq(placed, [&"enc:3_3"], "registering later places the sites already attached")
	Encounters.unregister_kind(&"test_dummy")
	assert_true(e.placed.is_empty(), "unregistering takes them down")


# --- State --------------------------------------------------------------------------------------

func test_state_round_trips_as_differences() -> void:
	var ws: WorldState = Game.session.world
	assert_true(ws.encounters.is_empty(), "nothing saved until something happens")
	var st: Dictionary = Encounters.state_of(&"enc:4_4", true)
	st["dead"] = ["s0"]
	st["taken"] = ["note"]
	ws.containers["enc:4_4:cooler"] = {"opened": true, "items": [], "rolled_day": 1, "gen": 0}
	var back := WorldState.new()
	back.from_dict(JSON.parse_string(JSON.stringify(ws.to_dict())))
	assert_eq(back.encounters, ws.encounters)
	assert_true(back.containers.has("enc:4_4:cooler"))
	var old := WorldState.new()
	var d: Dictionary = ws.to_dict()
	d.erase("encounters")
	old.from_dict(d)
	assert_eq(old.encounters, {}, "a save from before loads empty (no version bump)")


func test_looted_dead_and_taken_come_back() -> void:
	var d := EncounterDef.new()
	assert_eq(d.parse({"id": "test_sleepers", "biomes": {"conifer_forest": 1.0},
		"props": [{"prop": "enc_camp_cooler", "pos": [1, 0], "id": "cooler"}],
		"loose": [{"item": "cordage", "pos": [0, 1], "id": "rope"}],
		"notes": {"chance": 1.0, "items": ["note_enc_camp_list"], "pos": [0, -1]},
		"sleepers": {"chance": 1.0, "count": [3, 3], "enemies": {"hollow": 1}, "poses": ["lie"]}}, &"encounter", "test"), PackedStringArray())
	Content.add_runtime_def(d)
	var site: Dictionary = _site("enc:5_5", "test_sleepers", "scene", Vector3(10, 0, 10))
	var a := EncounterSite.new()
	a.build(site, d, Callable())
	add_child_autofree(a)
	assert_eq(a.sleeper_plan.size(), 3)
	assert_eq(a.pickup_ids, ["rope", "note"] as Array[String])
	# Loot the cooler, kill a sleeper, take the note.
	var lp: PoiPieces.LootProp = null
	for c: Node in a.get_children():
		if c is PoiPieces.LootProp:
			lp = c
	assert_not_null(lp)
	var inv := Inventory.new()
	Game.session.world.set_container_items(lp.container_id, inv, true, 1, 0)
	var e := Encounters.new()
	add_child_autofree(e)
	e._on_sleeper_died(null, &"enc:5_5", "s1")
	a.set_piece_state("note", "broken")
	# Saved and loaded.
	var ws := WorldState.new()
	ws.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	Game.session.world = ws
	var b := EncounterSite.new()
	b.build(site, d, Callable())
	add_child_autofree(b)
	assert_eq(b.sleeper_plan.map(func(s: Dictionary) -> String: return s["sid"]), ["s0", "s2"], "the dead stay dead")
	assert_eq(b.pickup_ids, ["rope"] as Array[String], "the taken note stays taken")
	var lp2: PoiPieces.LootProp = null
	for c2: Node in b.get_children():
		if c2 is PoiPieces.LootProp:
			lp2 = c2
	assert_true(lp2.opened, "the cooler stays looted")
	# The survivors stand where they stood before.
	assert_eq((b.sleeper_plan[0]["pos"] as Vector3), (a.sleeper_plan[0]["pos"] as Vector3))


# --- The vegetation's clearings ------------------------------------------------------------------

func test_vegetation_clearing_hides_instances_without_touching_saves() -> void:
	var vm := VegetationManager.new()
	autofree(vm)
	var key := Vector2i(0, 0)
	var layers: Dictionary = {"tree": [], "ground": []}
	for i: int in 4:
		var t := VegetationScatter.Instance.new()
		t.index = i
		t.pos = Vector3(10.0 + i * 3.0, 0.0, 10.0)
		(layers["tree"] as Array).append(t)
	var g := VegetationScatter.Instance.new()
	g.index = 4
	g.pos = Vector3(12.0, 0.0, 11.0)
	(layers["ground"] as Array).append(g)
	vm._data[key] = layers
	vm.add_clearing(&"c", Vector2(10.0, 10.0), 4.0, 2.5)
	assert_true(vm._is_removed(key, 0), "a tree inside the tree radius")
	assert_true(vm._is_removed(key, 1), "3 m away: inside 4 m")
	assert_false(vm._is_removed(key, 2), "6 m away: stands")
	assert_true(vm._is_removed(key, 4), "undergrowth inside its radius")
	assert_true(Game.session.world.trees.is_empty(), "nothing saved")
	vm.remove_clearing(&"c")
	assert_false(vm._is_removed(key, 0), "grows back")
	assert_eq(vm.clearing_count(), 0)


func test_registry_takes_an_extra_building() -> void:
	var reg := PoiRegistry.new()
	var xf := Transform3D(Basis(Vector3.UP, 0.4), Vector3(100, 5, 100))
	reg.add_extra(&"enc:9_9", "r0", &"hermit_shack", xf, Vector2(12, 10))
	assert_true(reg.entries.has(&"enc:9_9"))
	var c: Vector3 = xf * Vector3(6, 0, 5)
	assert_eq(reg.footprint_at(Vector2(c.x, c.z)), &"enc:9_9", "its footprint is known before it is built")
	assert_eq(PoiRegistry.building_xf(reg.entries[&"enc:9_9"], Content.get_def(&"poi", &"hermit_shack") as PoiDef), xf)
	var far: Vector3 = xf * Vector3(6, 0, 14)
	assert_eq(reg.footprint_at(Vector2(far.x, far.z)), &"", "outside its footprint")
