class_name Encounters
extends Node3D
## Forest encounters (ADR-0054): small things to find between the towns, a campsite or a wreck
## every few hundred metres of forest. A region's sites are planned on a worker thread when its
## 1 m terrain attaches (EncounterPlanner: deterministic from the world seed and the region's data,
## so the main map and random worlds alike), then built one a streaming step (the streamer's
## StepRunner in a streamed world, a runner of our own on the main map), and taken down when the
## region detaches. The vegetation hides its trees and undergrowth around each site at runtime
## (VegetationManager.add_clearing): nothing composed changes, so no golden or cache moves.
##
## Kinds (EncounterDef.ekind): "scene" sites are EncounterSite nodes built here; "poi" sites are
## tiny buildings PoiManager builds (place_extra); any other kind belongs to the system that
## registers it:
##     Encounters.register_kind(&"nest", on_place, on_unplace)
## on_place(site: Dictionary) gets {id: StringName (stable), kind, def, pos: Vector3 (on the ground),
## yaw, region: StringName, seed: int} when the site's region attaches (and at once for sites
## already standing when the kind registers); on_unplace(id: StringName) when it detaches. The
## sites, their density and their exclusions come from the same data files (data/encounters).
##
## State (differences only, WorldState.encounters by site id): visited, dead sleepers, taken
## pickups; containers in WorldState.containers. A site's sleepers spawn within
## `sleeper_spawn` m (config) and despawn past `sleeper_despawn`, as a POI's do.

## Registered kinds: kind -> [on_place, on_unplace]. Static so a system may register before or
## after this module exists; a kind whose callables died with their object is skipped.
static var _kinds: Dictionary = {}
## The live module (null outside a world).
static var current: Encounters = null

var world: Node
var terrain: TerrainManager
## Region id -> its planned sites (kept for the session: a region that comes back is not planned
## again).
var plans: Dictionary = {}
## Site id -> {site, node (EncounterSite or null), region}: what stands now.
var placed: Dictionary = {}
## The world setting and data/config/encounters.json, read when the module starts.
var density: float = 1.0
var cfg: Dictionary = {}
## Main-thread work when there is no streamer (the main map, tests).
var steps: StepRunner = StepRunner.new()
## (x, z) -> ground; default the terrain's.
var height_fn: Callable
## (rid, density, cfg) -> Array of sites: replaces the worker plan (tests).
var plan_fn: Callable

## rid -> {task, out: [sites]}
var _jobs: Dictionary = {}
## Regions detached while their plan was running: its result is not kept.
var _dropped: Dictionary = {}
## site id -> {sid: Enemy} awake sleepers that followed the player away from a site taken down.
var _roaming: Dictionary = {}
var _t: float = 0.0


## Registers who builds a kind's sites (see the class doc). Replaces an earlier registration.
static func register_kind(kind: StringName, on_place: Callable, on_unplace: Callable) -> void:
	_kinds[kind] = [on_place, on_unplace]
	if current != null:
		current._catch_up(kind)


## Takes a kind's sites down (on_unplace for each standing one) and forgets its callables.
static func unregister_kind(kind: StringName) -> void:
	if current != null:
		for id: StringName in current.placed.keys():
			if StringName(str((current.placed[id]["site"] as Dictionary)["kind"])) == kind:
				current._unplace(id)
	_kinds.erase(kind)


static func is_registered(kind: StringName) -> bool:
	if not _kinds.has(kind):
		return false
	return (_kinds[kind][0] as Callable).is_valid()


## The saved state of a site ({} when nothing happened there); `create` adds it.
static func state_of(id: StringName, create: bool = false) -> Dictionary:
	if Game.session == null:
		return {}
	var all: Dictionary = Game.session.world.encounters
	if not all.has(String(id)):
		if not create:
			return {}
		all[String(id)] = {"visited": false, "dead": [], "taken": []}
	return all[String(id)]


func setup_world(w: Node) -> void:
	world = w
	terrain = w.get(&"terrain") as TerrainManager
	current = self
	density = GameRules.current().num("encounter_density")
	cfg = Content.config(&"encounters")
	steps.budget_ms = float(cfg.get("budget_ms", 3.0))
	if not height_fn.is_valid() and terrain != null:
		height_fn = terrain.height_at
	if terrain == null:
		return
	terrain.region_attached.connect(_on_attached)
	terrain.region_detached.connect(_on_detached)
	for rid: String in terrain.regions:
		_on_attached(rid)


func _exit_tree() -> void:
	for job: Dictionary in _jobs.values():
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
	_jobs.clear()
	if current == self:
		current = null


## The StepRunner its builds go through: the streamer's (metered with the rest) when streaming.
func _runner() -> StepRunner:
	if terrain != null and terrain.streamer != null:
		return terrain.streamer.steps
	return steps


# --- Regions ----------------------------------------------------------------------------------

func _on_attached(rid: String) -> void:
	_dropped.erase(rid)
	if plans.has(rid):
		_queue_region(rid)
		return
	if _jobs.has(rid) or density <= 0.0:
		return
	if plan_fn.is_valid():
		plans[rid] = plan_fn.call(rid, density, cfg)
		_queue_region(rid)
		return
	var rt: RegionTerrain = terrain.regions.get(rid)
	if rt == null:
		return
	var out: Array = [[]]
	var seed_v: int = Game.session.world_seed
	var d: float = density
	var c: Dictionary = cfg.duplicate(true)
	var hf: Callable = height_fn
	# Content (the defs and the species tables the tree anchors read) is warm on the main thread.
	VegetationScatter.warm()
	var task: int = WorkerThreadPool.add_task(func() -> void:
		out[0] = EncounterPlanner.plan_region(rt, seed_v, d, c, hf), false, "encounters %s" % rid)
	_jobs[rid] = {"task": task, "out": out}


func _on_detached(rid: String) -> void:
	if _jobs.has(rid):
		_dropped[rid] = true
	_runner().cancel("encounter %s/" % rid)
	for id: StringName in placed.keys():
		if String((placed[id] as Dictionary)["region"]) == rid:
			_unplace(id)


func _collect() -> void:
	for rid: String in _jobs.keys():
		var job: Dictionary = _jobs[rid]
		if not WorkerThreadPool.is_task_completed(int(job["task"])):
			continue
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
		_jobs.erase(rid)
		if _dropped.has(rid):
			# Planned over ground that left mid-plan (the coarse terrain may have answered).
			_dropped.erase(rid)
			continue
		plans[rid] = (job["out"] as Array)[0]
		if terrain.regions.has(rid):
			_queue_region(rid)


func _queue_region(rid: String) -> void:
	var run: StepRunner = _runner()
	var focus: Vector3 = _focus()
	for site: Dictionary in plans.get(rid, []):
		var id: StringName = site["id"]
		if placed.has(id):
			continue
		var dist: float = focus.distance_to(site["pos"]) if focus != Vector3.INF else 0.0
		# After the region's terrain and buildings at the same distance.
		run.add(["", _place.bind(site), "encounter %s/%s" % [rid, id]], 150.0 + dist)


func _focus() -> Vector3:
	var p: Variant = world.get(&"player") if world != null else null
	if p is Node3D and is_instance_valid(p):
		return (p as Node3D).global_position
	return Vector3.INF


# --- Placing ----------------------------------------------------------------------------------

## Builds one site (a streaming step). Skipped when its region left meanwhile, when a building
## (built or still to come) or a player's structure now stands there.
func _place(site: Dictionary) -> void:
	var id: StringName = site["id"]
	var rid: String = String(site["region"])
	if placed.has(id) or terrain == null or not terrain.regions.has(rid):
		return
	var def: EncounterDef = Content.get_def(&"encounter", StringName(str(site["def"]))) as EncounterDef
	if def == null or not _site_free(site["pos"], def.radius):
		return
	var entry: Dictionary = {"site": site, "node": null, "region": rid}
	match def.ekind:
		&"scene":
			var node := EncounterSite.new()
			node.build(site, def, height_fn)
			add_child(node)
			entry["node"] = node
		&"poi":
			var pois: Node = world.get(&"pois")
			if pois == null or not pois.has_method(&"place_extra"):
				return
			pois.call(&"place_extra", id, def.poi, _poi_xf(site, def), rid)
		_:
			if not is_registered(def.ekind):
				return
			(_kinds[def.ekind][0] as Callable).call(EncounterPlanner.public_site(site))
	placed[id] = entry
	var veg: Node = world.get(&"vegetation")
	if veg != null and veg.has_method(&"add_clearing"):
		var p: Vector3 = site["pos"]
		veg.call(&"add_clearing", id, Vector2(p.x, p.z), def.clear_trees, def.clear_brush)


## A hermit's shack's transform: its footprint centred on the site, turned by the site's yaw, its
## floor on the highest ground under the footprint (never buried on a slope).
func _poi_xf(site: Dictionary, def: EncounterDef) -> Transform3D:
	var pd: PoiDef = Content.get_def(&"poi", def.poi) as PoiDef
	var fp := Vector2(pd.footprint) if pd != null else Vector2(8, 8)
	var b := Basis(Vector3.UP, float(site["yaw"]))
	var c: Vector3 = site["pos"]
	var top: float = -INF
	for q: Vector2 in [Vector2(0, 0), Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
		var w: Vector3 = c + b * Vector3(q.x * fp.x * 0.5, 0.0, q.y * fp.y * 0.5)
		top = maxf(top, float(height_fn.call(w.x, w.z)) if height_fn.is_valid() else c.y)
	var origin: Vector3 = c - b * Vector3(fp.x * 0.5, 0.0, fp.y * 0.5)
	origin.y = top
	return Transform3D(b, origin)


## True when nothing built stands within `r` m of p: a building (PoiManager.footprint_at sees
## every building of a streamed world, built or not; poi_at the built ones) or a player's piece.
func _site_free(p: Vector3, r: float) -> bool:
	var pois: Node = world.get(&"pois")
	if pois != null:
		if pois.has_method(&"footprint_at") and pois.call(&"footprint_at", p, r) != &"":
			return false
		if pois.has_method(&"poi_at") and pois.call(&"poi_at", p) != null:
			return false
	var building: Node = world.get(&"building")
	if building != null and building.has_method(&"pieces_in_radius") and not (building.call(&"pieces_in_radius", p, r + 2.0) as Array).is_empty():
		return false
	return true


func _unplace(id: StringName) -> void:
	var entry: Dictionary = placed.get(id, {})
	if entry.is_empty():
		return
	placed.erase(id)
	var site: Dictionary = entry["site"]
	var kind: StringName = StringName(str(site["kind"]))
	var node: EncounterSite = entry["node"]
	if node != null and is_instance_valid(node):
		_despawn_sleepers(node)
		node.queue_free()
	elif kind == &"poi":
		var pois: Node = world.get(&"pois") if world != null else null
		if pois != null and pois.has_method(&"free_extra"):
			pois.call(&"free_extra", id)
	elif kind != &"scene" and _kinds.has(kind) and (_kinds[kind][1] as Callable).is_valid():
		(_kinds[kind][1] as Callable).call(id)
	var veg: Node = world.get(&"vegetation") if world != null else null
	if veg != null and veg.has_method(&"remove_clearing"):
		veg.call(&"remove_clearing", id)


## A kind registered while its regions were already attached: its planned sites go up now.
func _catch_up(kind: StringName) -> void:
	for rid: String in plans:
		if terrain == null or not terrain.regions.has(rid):
			continue
		for site: Dictionary in plans[rid]:
			if StringName(str(site["kind"])) == kind and not placed.has(site["id"]):
				_place(site)


# --- Sleepers and visits ----------------------------------------------------------------------

func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_collect()
	if _runner() == steps:
		steps.run_frame()
	_t += delta
	if _t >= 1.0:
		_t = 0.0
		_tick()
	StreamMeter.note("encounters", t0)


func _tick() -> void:
	var focus: Vector3 = _focus()
	if focus == Vector3.INF:
		return
	var ai: Node = world.get(&"ai")
	var near: float = float(cfg.get("sleeper_spawn", 46.0))
	var far: float = float(cfg.get("sleeper_despawn", 95.0))
	for id: StringName in placed:
		var node: EncounterSite = (placed[id] as Dictionary)["node"]
		if node == null or not is_instance_valid(node):
			continue
		var d: float = node.global_position.distance_to(focus)
		if d < near and not node.sleepers_spawned:
			_spawn_sleepers(node, ai)
		elif d > far and node.sleepers_spawned:
			_despawn_sleepers(node)
		if d < node.def.radius + 6.0:
			var st: Dictionary = state_of(id, true)
			if not bool(st.get("visited", false)):
				st["visited"] = true
				var ps: PlayerState = Game.local_player()
				if ps != null:
					ps.progression.award("discover_encounter")


func _spawn_sleepers(node: EncounterSite, ai: Node) -> void:
	node.sleepers_spawned = true
	if ai == null or not ai.has_method(&"spawn_sleeper"):
		return
	var dead: Array = state_of(node.site_id).get("dead", [])
	var out: Dictionary = _roaming.get(node.site_id, {})
	for s: Dictionary in node.sleeper_plan:
		var sid: String = s["sid"]
		if dead.has(sid):
			continue
		var roamer: Variant = out.get(sid, null)
		if is_instance_valid(roamer) and (roamer as Enemy).is_alive():
			continue
		out.erase(sid)
		var e: Enemy = ai.call(&"spawn_sleeper", s["enemy"], s["pos"], float(s["yaw"]), str(s["pose"]), node.site_id, StringName(sid),
			node.def.tier) as Enemy
		if e != null:
			node.sleepers[sid] = e
			e.died.connect(_on_sleeper_died.bind(node.site_id, sid))


## Dormant sleepers are put away; awake ones that followed the player are handed to the director
## as wanderers (their kill still counts here: the died hook is ours).
func _despawn_sleepers(node: EncounterSite) -> void:
	var ai: Node = world.get(&"ai") if world != null else null
	for sid: String in node.sleepers:
		var e: Variant = node.sleepers[sid]
		if not is_instance_valid(e) or not (e as Enemy).is_alive():
			continue
		var en: Enemy = e
		if en.state == Enemy.State.SLEEP and ai != null:
			ai.call(&"despawn", en)
		else:
			en.poi_id = &""
			if not _roaming.has(node.site_id):
				_roaming[node.site_id] = {}
			(_roaming[node.site_id] as Dictionary)[sid] = en
	node.sleepers.clear()
	node.sleepers_spawned = false


func _on_sleeper_died(_e: Enemy, site_id: StringName, sid: String) -> void:
	var st: Dictionary = state_of(site_id, true)
	var dead: Array = st.get("dead", [])
	if not dead.has(sid):
		dead.append(sid)
	st["dead"] = dead
	(_roaming.get(site_id, {}) as Dictionary).erase(sid)


# --- Queries (debug overlay, CLI, tests) ------------------------------------------------------

## Every planned site within `r` m of p: [{site, placed: bool, state}], nearest first.
func sites_near(p: Vector3, r: float) -> Array:
	var out: Array = []
	for rid: String in plans:
		for site: Dictionary in plans[rid]:
			var d: float = Vector2(p.x, p.z).distance_to(Vector2((site["pos"] as Vector3).x, (site["pos"] as Vector3).z))
			if d <= r:
				out.append({"site": site, "placed": placed.has(site["id"]), "state": state_of(site["id"]), "d": d})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["d"]) < float(b["d"]))
	return out


func node_of(id: StringName) -> EncounterSite:
	var e: Dictionary = placed.get(id, {})
	return e.get("node") as EncounterSite if not e.is_empty() else null
