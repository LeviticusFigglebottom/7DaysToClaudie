class_name PoiManager
extends Node3D
## Places frameworks and POIs from the composed regions' placements (region.json features ->
## RegionTerrain.placements), builds each building with PoiBuilder, spawns/despawns sleepers as
## you approach, tracks visits, and answers indoor / room queries for survival, audio and nav.
##
## Placement frames: a placement origin is the pad corner; its rotation (degrees) turns the
## framework/POI plane the same way the composer did (Vector2.rotated), i.e. node yaw = -angle.
## Inside a framework, a lot's POI is centred in its rect with its front (+Z) toward `facing`.
## Owns the poi.* commands (ADR-0003): poi.disarm_trap takes a POI trap apart for its parts.
## A building whose weak floor gives way gets its nav tiles rebaked (ADR-0022).
## ADR-0030: every building is dressed for its run before it is built (dress_for: alternatives
## picked from the world seed and pinned in its saved state, per-run wear), and lots without an
## authored pick hold what LotPicker chooses: an authored building from the pool or a generated one.
## Its ProbeBudget keeps the buildings' interior reflection probes within the renderer's atlas.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Dressing := preload("res://src/poi/poi_dressing.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const ProbeBudget := preload("res://src/poi/interior_probe_budget.gd")

const SLEEPER_SPAWN: float = 46.0
const SLEEPER_DESPAWN: float = 95.0

var world: Node
var instances: Dictionary = {}
var _t: float = 0.0
var _inside: Dictionary = {}
## Shows only the interior probes nearest the camera (interior_probe_budget.gd).
var probes: Node


## While set (during setup_world in a GameWorld that is booting), _place_poi queues each building
## here instead of building it: GameWorld runs them as boot steps, a few per frame (ADR-0036). A
## 22-building town used to build in one frame of several seconds, and the OS called the game not
## responding.
var _queue: Array = []
var _queue_builds: Array = []
var _queueing: bool = false
## Route checks still running on worker threads (joined in _exit_tree).
var _tasks: Array[int] = []
## Every building placed in this world, built yet or not (all_buildings()): instance id -> entry.
var _placed: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	# Before any building enters the tree, so the probe cap holds from the first one built.
	probes = ProbeBudget.new()
	probes.name = "ProbeBudget"
	add_child(probes)
	Game.register_command(&"poi.disarm_trap", _cmd_disarm_trap)
	Settings.graphics_changed.connect(_on_graphics_changed)
	# A streamed world (RWG v2 Phase 3) builds its buildings by distance from the PoiRegistry:
	# its regions bring only their fixtures, and the boot builds the buildings around the spawn.
	if bool(w.get(&"streaming")) and w.get(&"poi_registry") is PoiRegistry:
		registry = w.get(&"poi_registry")
		var cfg: Dictionary = (Content.config(&"streaming") as Dictionary).get("poi", {})
		_build_r = float(cfg.get("build", 450.0))
		_free_r = float(cfg.get("free", 560.0))
		_max_built = int(cfg.get("max_built", 90))
		# Cellars are cut per built building (TD-107), not for every lot of an attached region.
		var tm0: TerrainManager = w.get(&"terrain") as TerrainManager
		if tm0 != null:
			tm0.start_gating_holes()
	# Tools and tests that set up a bare world still get every building built here and now.
	_queueing = w.has_method(&"is_booting") and bool(w.call(&"is_booting"))
	_place_all(w)
	if registry != null:
		var focus: Vector3 = w.get(&"boot_focus") if w.get(&"boot_focus") is Vector3 else Vector3.ZERO
		_update_ring(focus, BOOT_RADIUS)
	_queueing = false
	# Streamed worlds (ADR-0038): a region's buildings come and go with its 1 m terrain.
	var tm: TerrainManager = w.get(&"terrain") as TerrainManager
	if tm != null:
		tm.region_attached.connect(_on_region_attached)
		tm.region_detached.connect(_on_region_detached)


## The buildings queued by setup_world as [label, Callable, name] boot steps (empties the queue):
## every building's plan first, then every build.
func boot_steps() -> Array:
	var out: Array = _queue + _queue_builds
	_queue = []
	_queue_builds = []
	return out


func _place_all(w: Node) -> void:
	for rid: String in (w.terrain as TerrainManager).regions:
		_place_region(w.terrain.regions[rid])


## Places (or queues, see _queueing) a region's buildings and framework fixtures, remembering
## which region each belongs to. With a registry (a streamed world) only the fixtures: the
## buildings come from the ring (_update_ring).
func _place_region(rt: RegionTerrain) -> void:
	var buildings: bool = registry == null
	_region_now = rt.region_id
	_placed_regions[rt.region_id] = true
	for pl: Dictionary in rt.placements:
		match str(pl.get("kind", "")):
			"framework", "town":
				_place_framework(pl, buildings)
			"poi":
				if buildings:
					_place_poi(StringName(str(pl["def"])), StringName(str(pl["id"])), _placement_xf(pl), Vector2(pl.get("size", [0, 0])[0], pl.get("size", [0, 0])[1]))
	_region_now = ""


# --- Regions in and out (ADR-0038, RWG v2 Phase 2: buildings by region until Phase 3's rings) ---

## Fixtures of one framework placed per streaming step.
const FIXTURE_STEP: int = 48

## Region id -> true once its buildings are placed or queued.
var _placed_regions: Dictionary = {}
## Instance id -> the region it stands in; fixture bodies by region.
var _region_of: Dictionary = {}
var _fixtures: Dictionary = {}
var _region_now: String = ""


## A region attached at runtime: resolve its towns' lots (and generate their houses) on a worker,
## then queue its buildings as streaming steps, plan first and build after, a few phases a frame.
func _on_region_attached(rid: String) -> void:
	if _placed_regions.has(rid):
		return
	var tm: TerrainManager = world.terrain
	var rt: RegionTerrain = tm.regions.get(rid)
	if rt == null:
		return
	var steps: StepRunner = tm.streamer.steps if tm.streamer != null else null
	if steps == null:
		_place_region(rt)
		return
	_placed_regions[rid] = true
	if registry != null:
		# Its pads at 1 m heights; its fixtures in a step of their own (the buildings: _update_ring).
		registry.refresh_region(rid, rt)
		# A step per FIXTURE_STEP fixtures of each framework (a town's in one region were up to
		# ~70 ms in one step). Fixtures outside the region's rect are skipped inside.
		for pl: Dictionary in rt.placements:
			if not str(pl.get("kind", "")) in ["framework", "town"]:
				continue
			var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(pl["def"]))) as FrameworkDef
			var n: int = fw.fixtures.size() if fw != null else 0
			for from: int in range(0, maxi(n, 1), FIXTURE_STEP):
				steps.add(["", func() -> void:
					if _placed_regions.has(rid) and tm.regions.has(rid):
						_region_now = rid
						_place_framework(pl, false, Vector2i(from, from + FIXTURE_STEP))
						_region_now = "", "poi region %s" % rid])
		return
	var lots: Dictionary = world.get(&"poi_lots") if world.get(&"poi_lots") is Dictionary else {}
	var seed: int = Game.session.world_seed if Game.session != null else 0
	var todo: Array = []
	for pl: Dictionary in rt.placements:
		if str(pl.get("kind", "")) in ["framework", "town"] and not lots.has(str(pl["id"])):
			var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(pl["def"]))) as FrameworkDef
			if fw != null:
				todo.append([str(pl["id"]), fw])
	var out: Array = [{}]
	var task: int = WorkerThreadPool.add_task(func() -> void:
		var res: Dictionary = {}
		for t: Array in todo:
			var pairs: Array = []
			for r: Dictionary in Lots.resolve(t[1], t[0], seed):
				pairs.append([r, null if str(r["kind"]) in ["reserved", "empty"] else Lots.def_for(r)])
			res[t[0]] = pairs
		out[0] = res, false, "poi lots %s" % rid)
	_tasks.append(task)
	steps.add(["Raising the town…", func() -> bool:
		if not WorkerThreadPool.is_task_completed(task):
			return false
		WorkerThreadPool.wait_for_task_completion(task)
		_tasks.erase(task)
		if not _placed_regions.has(rid) or not tm.regions.has(rid):
			return true
		lots.merge(out[0])
		_queueing = true
		_place_region(rt)
		_queueing = false
		steps.insert_next(boot_steps())
		return true, "poi region %s" % rid], 10.0)


## A region detached: its queued building steps are dropped and its buildings and fixtures freed
## (their state lives in WorldState; sleepers despawn first).
func _on_region_detached(rid: String) -> void:
	if not _placed_regions.has(rid):
		return
	_placed_regions.erase(rid)
	var steps: StepRunner = world.terrain.streamer.steps if world.terrain.streamer != null else null
	if steps != null:
		steps.cancel("poi region %s" % rid, true)
	var ai: Node = world.get(&"ai")
	for id: StringName in _region_of.keys():
		if _region_of[id] != rid:
			continue
		_region_of.erase(id)
		_free_building(id, steps, ai)
	for body: Node in _fixtures.get(rid, []):
		if is_instance_valid(body):
			body.queue_free()
	_fixtures.erase(rid)


# --- Buildings by distance (RWG v2 Phase 3, streamed worlds) -----------------------------------

## Every building of the world as data (GameWorld.poi_registry); null builds everything at load.
var registry: PoiRegistry = null
## streaming.json "poi": build the nearest within _build_r (at most _max_built built or on the
## way), free beyond _free_r. The gap between the two keeps a building at the edge from flickering.
var _build_r: float = 450.0
var _free_r: float = 560.0
var _max_built: int = 90
## Built during the boot around the spawn, so the player doesn't arrive in a town of empty lots.
const BOOT_RADIUS: float = 200.0
const RING_INTERVAL: float = 0.5
var _ring_t: float = 0.0
## Instance id -> a building on its way (resolving, planning or building in steps).
var _jobs: Dictionary = {}
## Worker tasks of buildings freed before they were built (_prune_tasks, _exit_tree).
var _orphans: Array[int] = []


## Frees what fell out of the ring and queues the nearest wanted buildings whose regions are
## attached (a building's ground is its region's 1 m terrain), nearest first.
func _update_ring(pos: Vector3, radius: float) -> void:
	var tm: TerrainManager = world.get(&"terrain") as TerrainManager
	if tm == null:
		return
	var p := Vector2(pos.x, pos.z)
	var steps: StepRunner = tm.streamer.steps if tm.streamer != null else null
	var ai: Node = world.get(&"ai")
	for id: StringName in instances.keys() + _jobs.keys():
		if registry.entries.has(id) and registry.distance_to(id, p) > _free_r:
			_free_building(id, steps, ai)
	_prune_tasks()
	var count: int = instances.size() + _jobs.size()
	for hit: Array in registry.near(p, radius):
		if count >= _max_built:
			break
		var id2: StringName = hit[0]
		if instances.has(id2) or _jobs.has(id2):
			continue
		var e: Dictionary = registry.entries[id2]
		if not tm.regions.has(str(e["region"])):
			continue
		_queue_stream_build(id2, e, float(hit[1]), steps)
		count += 1


## A building's steps: resolve its def (a generated one on a worker), compile it and start its
## route check (_prepare_poi), then build it in slices (_finish_poi). Boot steps while the world
## boots, else streaming steps at its distance as priority.
func _queue_stream_build(id: StringName, e: Dictionary, dist: float, steps: StepRunner) -> void:
	var job: Dictionary = {"id": id, "e": e}
	_jobs[id] = job
	_region_of[id] = str(e["region"])
	var resolve := func() -> bool:
		if not job.has("pd"):
			var did: StringName = e["def"]
			if did != &"":
				job["pd"] = Content.get_def(&"poi", did) as PoiDef
			else:
				if not job.has("rtask"):
					var out: Array = [null]
					var res: Dictionary = e["res"]
					job["rout"] = out
					job["rtask"] = WorkerThreadPool.add_task(func() -> void: out[0] = Lots.def_for(res), false, "poi gen %s" % id)
					_tasks.append(job["rtask"])
					return false
				if not WorkerThreadPool.is_task_completed(job["rtask"]):
					return false
				WorkerThreadPool.wait_for_task_completion(job["rtask"])
				_tasks.erase(job["rtask"])
				job["pd"] = (job["rout"] as Array)[0]
		var pd: PoiDef = job["pd"]
		if pd == null:
			Log.warn("poi", "%s: nothing to place" % id)
			_jobs.erase(id)
			return true
		var xf: Transform3D = PoiRegistry.building_xf(e, pd)
		job["xf"] = xf
		_placed[id] = {"id": id, "def": pd.id, "name": pd.display_name, "tier": pd.tier,
			"kind": "generated" if pd.template != &"" else "authored", "pos": xf * Vector3(pd.footprint.x * 0.5, 0.0, pd.footprint.y * 0.5)}
		_prepare_poi(job)
		return true
	var build := func() -> bool:
		if not job.has("layout") or not _jobs.has(id):
			return true
		if not _finish_poi(job):
			return false
		_jobs.erase(id)
		return true
	var label: String = "Raising the town…"
	if _queueing or steps == null:
		_queue.append([label, resolve, "poi plan %s" % id])
		_queue_builds.append([label, build, "poi %s" % id])
	else:
		steps.add(["", resolve, "poi plan %s" % id], 100.0 + dist)
		steps.add(["", build, "poi %s" % id], 100.0 + dist)


## Takes a building out of the world (built or on its way): its steps dropped, sleepers despawned,
## its node freed. Its state stays in WorldState for when it comes back.
func _free_building(id: StringName, steps: StepRunner, ai: Node) -> void:
	if steps != null:
		steps.cancel("poi plan %s" % id, true)
		steps.cancel("poi %s" % id, true)
	# Its worker tasks still finish; they are joined once done (_prune_tasks), not by its steps.
	var job: Dictionary = _jobs.get(id, {})
	for k: String in ["task", "rtask"]:
		if job.has(k) and _tasks.has(job[k]):
			_tasks.erase(job[k])
			_orphans.append(job[k])
	# Half built: its root never entered the tree.
	if job.has("builder"):
		(job["builder"] as PoiBuilder).discard()
	_jobs.erase(id)
	_region_of.erase(id)
	_inside.erase(id)
	var inst: PoiInstance = instances.get(id)
	if inst != null and is_instance_valid(inst):
		if ai != null:
			inst.despawn_sleepers(ai)
		_keep_roamers(id, inst)
		inst.queue_free()
	instances.erase(id)
	_grid_remove(id)
	_set_hole(id, false)


## Instance id -> {sleeper id: Enemy}: awake sleepers that followed the player out of a building
## the ring then freed. Their died hook went with the building's node, so the manager keeps it.
var _roamers: Dictionary = {}
## Instance ids whose roamer died while the building was freed (cleared is checked on rebuild).
var _died_away: Dictionary = {}


func _keep_roamers(id: StringName, inst: PoiInstance) -> void:
	var out: Dictionary = {}
	for sid: StringName in inst._roaming:
		var e: Variant = inst._roaming[sid]
		if is_instance_valid(e) and (e as Enemy).is_alive():
			out[sid] = e
			var hook: Callable = _on_roamer_died.bind(id, String(sid))
			if not (e as Enemy).died.is_connected(hook):
				(e as Enemy).died.connect(hook)
	if not out.is_empty():
		_roamers[id] = out


func _on_roamer_died(e: Enemy, id: StringName, sid: String) -> void:
	var inst: PoiInstance = instances.get(id)
	if inst != null and is_instance_valid(inst):
		inst._on_sleeper_died(e, sid)
		inst._roaming.erase(StringName(sid))
		return
	(_roamers.get(id, {}) as Dictionary).erase(StringName(sid))
	if Game.session == null:
		return
	var st: Dictionary = Game.session.world.poi_state(id)
	var dead: Array = st.get("dead", [])
	if not dead.has(sid):
		dead.append(sid)
	st["dead"] = dead
	_died_away[id] = true


## Joins the finished tasks of buildings freed on their way (a route check or a generation keeps
## running after its building is dropped; the steps that would have joined it are gone).
func _prune_tasks() -> void:
	for i: int in range(_orphans.size() - 1, -1, -1):
		if WorkerThreadPool.is_task_completed(_orphans[i]):
			WorkerThreadPool.wait_for_task_completion(_orphans[i])
			_orphans.remove_at(i)


static func _placement_xf(pl: Dictionary) -> Transform3D:
	var o: Array = pl["origin"]
	return Transform3D(Basis(Vector3.UP, -deg_to_rad(float(pl.get("rotation", 0.0)))), Vector3(float(o[0]), float(o[1]), float(o[2])))


## `fx`: the range of the framework's fixtures to place ([from, to), to -1 = all), so a streamed
## region can place a big town's fixtures over several steps.
func _place_framework(pl: Dictionary, buildings: bool = true, fx: Vector2i = Vector2i(0, -1)) -> void:
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(pl["def"]))) as FrameworkDef
	if fw == null:
		Log.warn("poi", "framework %s not found" % pl["def"])
		return
	var fxf: Transform3D = _placement_xf(pl)
	var seed: int = Game.session.world_seed if Game.session != null else 0
	# An organic town of a random world (ADR-0040) comes once per region it touches ("town", with
	# that region's rect): only its lots whose frames centre there and the fixtures standing there.
	var only := Rect2()
	if pl.has("rect"):
		only = Rect2(float(pl["rect"][0]), float(pl["rect"][1]), float(pl["rect"][2]), float(pl["rect"][3]))
	# The world loader may have resolved the lots (and generated their buildings) already.
	var cache: Dictionary = world.get(&"poi_lots") if world.get(&"poi_lots") is Dictionary else {}
	var resolved: Array = cache.get(str(pl["id"]), [])
	if resolved.is_empty():
		for r: Dictionary in Lots.resolve(fw, str(pl["id"]), seed):
			var away: bool = only.has_area() and not only.has_point(Lots.lot_center(r["lot"]))
			resolved.append([r, null if away or str(r["kind"]) in ["reserved", "empty"] else Lots.def_for(r)])
	for pair: Array in (resolved if buildings else []):
		var res: Dictionary = pair[0]
		var l: Dictionary = res["lot"]
		if str(res["kind"]) in ["reserved", "empty"] or (only.has_area() and not only.has_point(Lots.lot_center(l))):
			continue
		var pd: PoiDef = pair[1]
		if pd == null:
			Log.warn("poi", "lot %s: nothing to place (%s %s)" % [l.get("id"), res["kind"], res.get("def_id", res.get("template", ""))])
			continue
		var xf: Transform3D = fxf * (Lots.lot_local_xf(l, pd.footprint) if l.has("frame") else lot_xf(l, pd.footprint))
		_place_poi(pd.id, StringName(str(res["instance"])), xf, Vector2(pd.footprint), pd)
	# Plain fixtures (lamp posts, hydrants, benches) are batched per 64 m cell: one MultiMesh per
	# model and one body holding every box (TD-107). An organic town has hundreds of them, and a
	# body and a mesh instance each cost a node, a draw call and a physics object apiece.
	var cells: Dictionary = {}
	for fi: int in range(fx.x, fw.fixtures.size() if fx.y < 0 else mini(fx.y, fw.fixtures.size())):
		var f: Dictionary = fw.fixtures[fi]
		var pdef: PropDef = Content.get_def(&"prop", StringName(str(f.get("prop", "")))) as PropDef
		if pdef == null:
			continue
		var p: Array = f.get("pos", [0, 0])
		var lp: Vector3 = fxf * Vector3(float(p[0]), 0.0, float(p[1]))
		if only.has_area() and not only.has_point(Vector2(lp.x, lp.z)):
			continue
		lp.y = world.height_at(lp.x, lp.z)
		var xf := Transform3D(fxf.basis * Basis(Vector3.UP, deg_to_rad(float(f.get("rot", 0.0)))), lp)
		var model: String = pdef.model_for(str(f.get("variant", "worn")))
		# Street fixtures with a container (dumpster, wrecks, mailbox) are searchable like any
		# prop indoors: same LootProp, tier 1, its id from the framework and the fixture's own id.
		var cdef: ContainerDef = Content.get_def(&"container", pdef.container) as ContainerDef if pdef.container != &"" else null
		if cdef == null:
			var k := Vector2i(floori(lp.x / GRID_CELL), floori(lp.z / GRID_CELL))
			if not cells.has(k):
				cells[k] = {"models": {}, "boxes": []}
			var models: Dictionary = cells[k]["models"]
			if not models.has(model):
				models[model] = []
			(models[model] as Array).append(xf)
			if pdef.collision != "none":
				(cells[k]["boxes"] as Array).append([xf * Transform3D(Basis(), Vector3(0, pdef.size.y * 0.5, 0)), pdef.size])
			continue
		var lpr := PoiPieces.LootProp.new()
		lpr.prop = pdef
		lpr.cdef = cdef
		lpr.container_id = StringName("c:%s:%s" % [pl["id"], str(f.get("id", "fx%d" % fi))])
		lpr.tier = 1
		lpr.name = "Fixture_%s_%d" % [pdef.id, fi]
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(model, "box")
		lpr.add_child(mi)
		if pdef.collision != "none":
			var cs := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = pdef.size
			cs.shape = box
			cs.position = Vector3(0, pdef.size.y * 0.5, 0)
			lpr.add_child(cs)
		add_child(lpr)
		lpr.global_transform = xf
		_keep_fixture(lpr)
	for k2: Vector2i in cells:
		_keep_fixture(fixture_cell(cells[k2], "Fixtures_%s_%d_%d" % [str(pl["id"]).replace("/", "_"), k2.x, k2.y]))


## One cell's batched fixtures ({models: {model id: [Transform3D]}, boxes: [[Transform3D, size]]},
## world transforms) as a body at the origin: a MultiMesh per model, a box shape per solid one.
func fixture_cell(cell: Dictionary, node_name: String) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	var models: Dictionary = cell["models"]
	for model: String in models:
		var xfs: Array = models[model]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = ModelLibrary.mesh(model, "box")
		mm.instance_count = xfs.size()
		for i: int in xfs.size():
			mm.set_instance_transform(i, xfs[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = model.get_file()
		mmi.multimesh = mm
		body.add_child(mmi)
	for b: Array in cell["boxes"]:
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = b[1]
		cs.shape = box
		cs.transform = b[0]
		body.add_child(cs)
	add_child(body)
	body.global_transform = Transform3D.IDENTITY
	return body


func _keep_fixture(body: Node) -> void:
	if _region_now == "":
		return
	if not _fixtures.has(_region_now):
		_fixtures[_region_now] = []
	(_fixtures[_region_now] as Array).append(body)


## A lot's POI frame in its framework: the footprint centred in the rect, its front (+Z) toward
## the lot's `facing`.
static func lot_xf(l: Dictionary, footprint: Vector2i) -> Transform3D:
	return PoiRegistry.rect_lot_xf(l, footprint)


## The def as this run builds it at this placement (ADR-0030): per-run picks and wear for a world
## dressed per run, the authored defaults and the old scatter for a legacy save. A run keeps the
## picks it made the first time (pinned in the POI's saved state), even if content gains options.
static func dress_for(pd: PoiDef, instance_id: StringName, session: GameSession) -> PoiDef:
	var a: Array = dress_args(pd, instance_id, session)
	return Dressing.resolve(pd, a[0], a[1])


## dress_for's half that reads and pins the run's saved state (main thread): [picks, resolve
## options]. Dressing.resolve with them is pure and may run on a worker.
static func dress_args(pd: PoiDef, instance_id: StringName, session: GameSession) -> Array:
	var mode: int = Dressing.MODE_LEGACY
	var world_seed: int = 0
	var st: Dictionary = {}
	if session != null:
		mode = session.world.poi_dressing
		world_seed = session.world_seed
		st = session.world.poi_state(instance_id)
	var seed: int = Dressing.dressing_seed(world_seed, instance_id, mode)
	var picks: Dictionary = {}
	if mode == Dressing.MODE_PER_RUN and Dressing.has_alternatives(pd):
		picks = Dressing.roll(pd, seed)
		var pinned: Dictionary = st.get("picks", {})
		for g: Dictionary in Dressing.groups(pd):
			var gid: String = str(g.get("id", ""))
			if pinned.has(gid) and Dressing.option_ids(g).has(str(pinned[gid])):
				picks[gid] = str(pinned[gid])
		if session != null:
			st["picks"] = picks.duplicate()
	return [picks, {"mode": mode, "seed": seed}]


func _place_poi(def_id: StringName, instance_id: StringName, xf: Transform3D, _pad: Vector2, def: PoiDef = null) -> PoiInstance:
	var pd: PoiDef = def if def != null else Content.get_def(&"poi", def_id) as PoiDef
	if pd == null:
		Log.warn("poi", "poi %s not found" % def_id)
		return null
	_placed[instance_id] = {"id": instance_id, "def": pd.id, "name": pd.display_name, "tier": pd.tier,
		"kind": "generated" if pd.template != &"" else "authored", "pos": xf * Vector3(pd.footprint.x * 0.5, 0.0, pd.footprint.y * 0.5)}
	if _region_now != "":
		_region_of[instance_id] = _region_now
	if _queueing:
		# Two steps a building: compile it (and start its route check on a worker thread), then,
		# once every compile has started its check, build it as soon as its check is done.
		var job: Dictionary = {"pd": pd, "id": instance_id, "xf": xf}
		var label: String = "Raising %s…" % pd.display_name if pd.display_name != "" else "Raising the town…"
		_queue.append(["Surveying the town…", _prepare_poi.bind(job), "poi plan %s" % instance_id])
		_queue_builds.append([label, _finish_poi.bind(job), "poi %s" % instance_id])
		return null
	return _build_poi(pd, instance_id, xf)


## Boot step: compiles a queued building's layout (main thread: the per-run picks are pinned in
## the session) and starts its PoiValidator on a worker thread.
func _prepare_poi(job: Dictionary) -> void:
	# The picks are pinned here (session state); dressing, compiling and the route check run on a
	# worker (a big building's compile was ~40 ms of a streaming step). The worker fills `out`
	# only: a dictionary written from two threads at once can corrupt itself.
	var a: Array = dress_args(job["pd"], job["id"], Game.session)
	var pd: PoiDef = job["pd"]
	var out: Array = [null, null, null]
	job["out"] = out
	job["layout"] = null
	job["task"] = WorkerThreadPool.add_task(func() -> void:
		var layout := PoiLayout.compile(Dressing.resolve(pd, a[0], a[1]))
		var v := PoiValidator.new()
		v.layout = layout
		out[0] = layout
		out[1] = v
		v._run()
		PoiBuilder.prepare_check(v)
		# The route-cue windows walk the route's outdoor legs: ~350 ms for the quarantine camp's
		# 44 m yard, which PoiInstance._ready (RouteCues.build) paid in one streaming frame.
		out[2] = RouteCues.entry_windows(layout), false, "poi check %s" % job["id"])
	_tasks.append(job["task"])


## Main-thread time a building's build takes per call before it yields to the next frame.
const BUILD_SLICE_MS: float = 8.0
## A single PoiBuilder phase longer than this is logged by name.
const SLOW_PHASE_MS: float = 20.0


## Boot step: builds a prepared building once its check is done, a few PoiBuilder steps per call
## (ADR-0038: no single frame pays for a whole sawmill); false = not done, ask again next frame.
func _finish_poi(job: Dictionary) -> bool:
	var task: int = int(job.get("task", -1))
	if task >= 0:
		if not WorkerThreadPool.is_task_completed(task):
			return false
		WorkerThreadPool.wait_for_task_completion(task)
		_tasks.erase(task)
		job.erase("task")
		if job.has("out"):
			job["layout"] = job["out"][0]
			job["checked"] = job["out"][1]
			RouteCues.plan(job["layout"], job["out"][2])
			job.erase("out")
			for e: String in (job["layout"] as PoiLayout).errors:
				Log.warn("poi", e)
	if not job.has("builder"):
		job["builder"] = PoiBuilder.start(job["layout"], job["id"], job.get("checked"))
	var b: PoiBuilder = job["builder"]
	var t0: int = Time.get_ticks_usec()
	while true:
		var phase: String = b.next_phase()
		var tp: int = Time.get_ticks_usec()
		# What is left of the slice: a resumable phase (walls, floors, roof, props...) stops there.
		var done: bool = b.step(maxf(BUILD_SLICE_MS - float(tp - t0) / 1000.0, 0.5))
		var ms: float = float(Time.get_ticks_usec() - tp) / 1000.0
		# A step still over the slice is one item too big to split: name it (StreamMeter only sees
		# the step).
		if ms > SLOW_PHASE_MS:
			Log.info("poi", "%s: phase %s took %.0f ms" % [job["id"], phase, ms])
		if done:
			break
		if float(Time.get_ticks_usec() - t0) / 1000.0 >= BUILD_SLICE_MS:
			return false
	_place_built(b.root, job["id"], job["xf"])
	return true


func _build_poi(pd: PoiDef, instance_id: StringName, xf: Transform3D, layout: PoiLayout = null, checked: PoiValidator = null) -> PoiInstance:
	if layout == null:
		layout = PoiLayout.compile(dress_for(pd, instance_id, Game.session))
		for e: String in layout.errors:
			Log.warn("poi", e)
	return _place_built(PoiBuilder.build(layout, instance_id, checked), instance_id, xf)


func _place_built(inst: PoiInstance, instance_id: StringName, xf: Transform3D) -> PoiInstance:
	add_child(inst)
	inst.global_transform = xf
	instances[instance_id] = inst
	_grid_add(instance_id, inst)
	# Its sleepers still out hunting from before it was freed: not spawned again at their posts.
	if _roamers.has(instance_id):
		inst._roaming = _roamers[instance_id]
		_roamers.erase(instance_id)
	if _died_away.has(instance_id):
		_died_away.erase(instance_id)
		inst.check_cleared()
	_limit_draw_distance(inst)
	inst.geometry_changed.connect(_on_poi_geometry_changed)
	_set_hole(instance_id, true)
	return inst


## A streamed world's cellar of this building opens with it and closes when it is freed.
func _set_hole(id: StringName, open: bool) -> void:
	if registry == null or world == null:
		return
	var tm: TerrainManager = world.get(&"terrain") as TerrainManager
	if tm != null:
		tm.set_poi_hole(id, open)


## Draw distances for a building's props, doors, pieces and prop batches (the kit batches keep the
## building's shape at any range). They had none: every prop of every building in the valley was
## drawn, shadow passes included, about 2.4 M triangles in 2,400 instances from any view (TD-003,
## ADR-0037). Small things stop at the graphics setting object_distance, door-sized ones at 2.5x,
## anything over 8 m (a steeple, a silo) is never cut.
func _limit_draw_distance(root: Node) -> void:
	var near: float = float(Settings.gfx("object_distance", 140.0))
	for n: Node in root.find_children("*", "GeometryInstance3D", true, false):
		var mi: GeometryInstance3D = n
		var mesh: Mesh = null
		if mi is MeshInstance3D:
			mesh = (mi as MeshInstance3D).mesh
		elif mi is MultiMeshInstance3D and _is_model_batch(mi as MultiMeshInstance3D):
			mesh = (mi as MultiMeshInstance3D).multimesh.mesh
		if mesh == null:
			continue
		if not mi.has_meta(&"hm_extent"):
			var b: Basis = mi.global_transform.basis
			mi.set_meta(&"hm_extent", (mesh.get_aabb().size * b.get_scale()).length())
		var extent: float = float(mi.get_meta(&"hm_extent"))
		var end: float = 0.0 if extent > 8.0 else (near * 2.5 if extent > 2.5 else near)
		mi.visibility_range_end = end
		# Hysteresis, no fade: a dithered fade would make every prop draw as transparency.
		mi.visibility_range_end_margin = 0.0 if end == 0.0 else end * 0.08
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED


## PoiBuilder batches props and other models ("@family/id" pieces, named MM_<family>_...) beside
## the kit pieces (walls, floors, roofs: the building's shape, never cut).
const MODEL_FAMILIES: PackedStringArray = ["props", "items", "trees", "plants", "rocks", "structures", "animals", "characters"]


static func _is_model_batch(mmi: MultiMeshInstance3D) -> bool:
	if mmi.multimesh == null or mmi.multimesh.mesh == null:
		return false
	var n: String = String(mmi.name)
	for f: String in MODEL_FAMILIES:
		if n.begins_with("MM_%s_" % f):
			return true
	return false


func _on_graphics_changed() -> void:
	for inst: Node in instances.values():
		if is_instance_valid(inst):
			_limit_draw_distance(inst)


## A building's walkable geometry changed (a weak floor gave way, ADR-0022): rebake the nav tiles
## there so the Hollowed stop pathing over the hole.
func _on_poi_geometry_changed(pos: Vector3) -> void:
	var ai: Node = world.get(&"ai") if world != null else null
	var nav: NavTiles = ai.get(&"nav") as NavTiles if ai != null else null
	if nav != null:
		nav.mark_dirty(pos)


func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_process_body(delta)
	StreamMeter.note("pois", t0)


func _process_body(delta: float) -> void:
	_ring_t += delta
	if registry != null and _ring_t >= RING_INTERVAL and world != null and world.player != null and world.is_ready:
		_ring_t = 0.0
		_update_ring(world.player.global_position, _build_r)
	_t += delta
	if _t < 1.0 or world == null or world.player == null or not world.is_ready:
		return
	_t = 0.0
	var ppos: Vector3 = world.player.global_position
	var ai: Node = world.get(&"ai")
	for id: StringName in instances:
		var inst: PoiInstance = instances[id]
		var b: AABB = inst.world_bounds()
		var d: float = b.get_center().distance_to(ppos) - b.size.length() * 0.4
		if d < SLEEPER_SPAWN and not inst.sleepers_spawned:
			inst.spawn_sleepers(ai)
		elif d > SLEEPER_DESPAWN and inst.sleepers_spawned:
			inst.despawn_sleepers(ai)
		var inside: bool = b.has_point(ppos)
		if inside != bool(_inside.get(id, false)):
			_inside[id] = inside
			if inside:
				var first: bool = not bool(inst.state.get("visited", false))
				if first:
					var p: PlayerState = Game.local_player()
					if p != null:
						p.progression.award("discover_poi", inst.tier)
				inst.state["visited"] = true
				Events.poi_entered.emit(id)
				if first:
					Events.poi_discovered.emit(id)
			else:
				Events.poi_exited.emit(id)


# --- Queries ---------------------------------------------------------------------------------

## Every building this world places, whether built yet or not: {id: instance id, def: def id,
## name, tier, kind: "authored" | "generated", pos: its centre}. The one lookup for "what buildings
## does this world have" (the directives use it): when buildings stream by distance, `instances`
## holds only the nearby ones, so this switches to the PoiRegistry of every placement
## (docs/RWG_V2_PLAN.md §1.7) instead.
func all_buildings() -> Array:
	if registry == null:
		return _placed.values()
	var out: Array = []
	for id: StringName in registry.entries:
		out.append(_placed[id] if _placed.has(id) else _registry_listing(registry.entries[id]))
	return out


## A building not resolved yet, as all_buildings() lists it, without generating it: an authored
## one from its def, a generated one from its template (its def id is the one the generator will
## give it, LotPicker.gen_id; its name the template's until a building is made).
func _registry_listing(e: Dictionary) -> Dictionary:
	var c: Vector2 = e["center"]
	var out: Dictionary = {"id": e["id"], "def": e["def"], "name": "", "tier": 1, "kind": "authored", "pos": Vector3(c.x, 0.0, c.y)}
	if e["def"] != &"":
		var pd: PoiDef = Content.get_def(&"poi", e["def"]) as PoiDef
		if pd != null:
			out["name"] = pd.display_name
			out["tier"] = pd.tier
			out["kind"] = "generated" if pd.template != &"" else "authored"
		return out
	var res: Dictionary = e["res"]
	var t: ContentDef = Content.get_def(&"building_template", StringName(str(res.get("template", ""))))
	out["def"] = StringName(Lots.gen_id(res))
	out["kind"] = "generated"
	if t != null:
		out["name"] = t.display_name
		out["tier"] = int(t.get(&"tier"))
	return out


## Map markers for every building, built or not: [{pos: Vector3, visited: bool, cleared: bool}].
## Read from the saved state without creating any (WorldState.poi_state would add an entry for
## every building in the world just by drawing the map).
func markers() -> Array:
	var saved: Dictionary = Game.session.world.pois if Game.session != null else {}
	var out: Array = []
	if registry == null:
		for id: StringName in instances:
			out.append(_marker((instances[id] as PoiInstance).global_position, saved.get(String(id), {})))
		return out
	for id2: StringName in registry.entries:
		var inst: PoiInstance = instances.get(id2)
		var c: Vector2 = registry.entries[id2]["center"]
		out.append(_marker(inst.global_position if inst != null and is_instance_valid(inst) else Vector3(c.x, 0.0, c.y), saved.get(String(id2), {})))
	return out


static func _marker(pos: Vector3, st: Dictionary) -> Dictionary:
	return {"pos": pos, "visited": bool(st.get("visited", false)), "cleared": bool(st.get("cleared", false))}


## The building whose footprint lies within `margin` m of pos, built or not ("" when none, or in a
## world without a registry, where every building is built: poi_at answers there). Wanderer
## spawns and supply drops use it so nothing lands where a building is about to stand.
func footprint_at(pos: Vector3, margin: float = 0.0) -> StringName:
	if registry == null:
		return &""
	var p := Vector2(pos.x, pos.z)
	if margin <= 0.0:
		return registry.footprint_at(p)
	var hits: Array = registry.near(p, margin)
	return hits[0][0] if not hits.is_empty() else &""


## The built building whose box holds pos, tested in the building's own frame (a turned building's
## world AABB would claim its neighbour's yard), found through a 64 m grid of the built ones: it is
## asked every frame by the player's survival and audio, and by AI.
func poi_at(pos: Vector3) -> PoiInstance:
	for id: StringName in _grid.get(Vector2i(floori(pos.x / GRID_CELL), floori(pos.z / GRID_CELL)), []):
		var e: Array = _boxes[id]
		if (e[1] as AABB).has_point((e[0] as Transform3D) * pos):
			return instances.get(id)
	return null


# --- The built buildings' grid -----------------------------------------------------------------

const GRID_CELL: float = 64.0
## Vector2i cell -> Array of instance ids whose world box overlaps it.
var _grid: Dictionary = {}
## Instance id -> [inverse of its transform, its local box, its cells]. Buildings never move once
## placed, so the transform is taken once.
var _boxes: Dictionary = {}


func _grid_add(id: StringName, inst: PoiInstance) -> void:
	_grid_remove(id)
	var wb: AABB = inst.world_bounds()
	var cells: Array[Vector2i] = []
	for cz: int in range(floori(wb.position.z / GRID_CELL), floori(wb.end.z / GRID_CELL) + 1):
		for cx: int in range(floori(wb.position.x / GRID_CELL), floori(wb.end.x / GRID_CELL) + 1):
			var k := Vector2i(cx, cz)
			if not _grid.has(k):
				_grid[k] = []
			(_grid[k] as Array).append(id)
			cells.append(k)
	_boxes[id] = [inst.global_transform.affine_inverse(), inst.local_bounds(), cells]


func _grid_remove(id: StringName) -> void:
	if not _boxes.has(id):
		return
	for k: Vector2i in _boxes[id][2]:
		var a: Array = _grid.get(k, [])
		a.erase(id)
		if a.is_empty():
			_grid.erase(k)
	_boxes.erase(id)


func is_indoors(pos: Vector3) -> bool:
	var inst: PoiInstance = poi_at(pos)
	return inst != null and inst.is_indoors(pos)


func room_type_at(pos: Vector3) -> String:
	var inst: PoiInstance = poi_at(pos)
	return inst.room_type_at(pos) if inst != null else ""


## Static collision roots of POIs overlapping an XZ rect (navigation baking).
func nav_roots_in_rect(r: Rect2) -> Array:
	var out: Array = []
	for inst: PoiInstance in instances.values():
		var b: AABB = inst.world_bounds()
		if Rect2(b.position.x, b.position.z, b.size.x, b.size.z).intersects(r):
			out.append(inst.shell)
	return out


func save_into(_session: GameSession) -> void:
	# POI state dictionaries live in WorldState.pois already (mutated in place).
	pass


func _exit_tree() -> void:
	for t: int in _tasks + _orphans:
		WorkerThreadPool.wait_for_task_completion(t)
	_tasks.clear()
	_orphans.clear()
	if world != null:
		Game.unregister_command(&"poi.disarm_trap")


## {player?, poi: instance id, trap: trap id} — a crouched player within reach takes an armed trap
## apart (or salvages a sprung one) and gets its parts (data/config/traps.json *_yield).
func _cmd_disarm_trap(args: Dictionary) -> Dictionary:
	if Game.session == null:
		return {"ok": false, "error": "no session"}
	var p: PlayerState = Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id))))
	if p == null or not p.stats.alive:
		return {"ok": false, "error": "no player"}
	var inst: PoiInstance = instances.get(StringName(str(args.get("poi", ""))))
	var tid: String = str(args.get("trap", ""))
	if inst == null or inst.layout.trap(tid).is_empty():
		return {"ok": false, "error": "no such trap"}
	var piece: Node3D = inst.traps.get(tid) as Node3D
	var node: Node3D = world.call(&"player_node", p.id) if world != null and world.has_method(&"player_node") else null
	if node != null and piece != null:
		if node.global_position.distance_to(piece.global_position) > float(Content.config(&"traps").get("disarm_reach", 3.0)):
			return {"ok": false, "error": "out of reach"}
		if inst.trap_state(tid) == "armed" and not bool(node.get(&"crouching")):
			return {"ok": false, "error": "not crouching"}
	var res: Dictionary = inst.disarm_trap(tid)
	if not bool(res.get("ok", false)):
		return res
	var items: Dictionary = res.get("items", {})
	var got: PackedStringArray = []
	for k: Variant in items.keys():
		var item := StringName(str(k))
		var n: int = int(items[k])
		var left: int = p.inventory.add_item(item, n)
		if left > 0 and piece != null:
			ItemDrop.spawn(world if world != null else self, ItemStack.make(item, left), piece.global_position + Vector3.UP * 0.4)
		var d: ItemDef = Content.item(item)
		got.append("%d %s" % [n, d.display_name if d != null else String(item)])
	Events.inventory_changed.emit(p.id)
	Events.trap_disarmed.emit(p.id, inst.instance_id, StringName(str(inst.layout.trap(tid).get("type", ""))), str(res.get("was", "")) == "armed")
	var what: String = str((piece as PoiPieces.Trap).label) if piece is PoiPieces.Trap else "trap"
	Events.player_status_message.emit(("%s %s" % ["Disarmed the" if str(res.get("was", "")) == "armed" else "Salvaged the", what]) +
		((": " + ", ".join(got) + ".") if not got.is_empty() else "."), &"info")
	return {"ok": true, "items": items}
