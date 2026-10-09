class_name WorldLoader
extends RefCounted
## Loads a world for play: parses WorldDef, composes built regions at 1 m and every other region
## at 16 m (far field), using the on-disk cache. Run `load_world()` on a worker thread and poll
## `progress` / `stage` from the main thread (loading screen).
## A random world (ADR-0031, `load_random_world()`) is generated first (or read from
## user://worlds/random/), its towns' frameworks registered, and then loaded the same way; all of
## its regions are built, so they compose in parallel on a few threads of their own.

var world: WorldDef
var detailed: Dictionary = {}
var coarse: Dictionary = {}
var progress: float = 0.0
var stage: String = ""
var done: bool = false
var error: String = ""
## The generated world's id when it differs from the one asked for (regenerated after the
## generator changed and its old folder was gone); "" otherwise.
var world_id: String = ""
## Set before loading to also resolve every framework's lots here, on the worker thread (ADR-0036):
## placement id -> [[lot result, PoiDef or null]] (LotPicker.resolve / def_for). Generating Pell's
## Crossing's houses took a second of the main thread's load.
var resolve_lots: bool = false
var world_seed: int = 0
var lots: Dictionary = {}
## Every building of the world as data (RWG v2 Phase 3), made with the lots: a streamed world
## builds its buildings from it by distance.
var registry: PoiRegistry = null
## The Bloom field over the detailed regions, built here too when resolve_lots is set (about a
## second of the main thread on a 3x3 random world, ADR-0036); null otherwise.
var bloom_tiles: BloomTiles = null
## What building it took (ms).
var bloom_ms: int = 0
## Streamed loading (ADR-0038): only the first area is composed at 1 m (random worlds; set before
## loading). spawn_hint: where the player will stand (a saved position), NAN for the drop site.
var stream: bool = false
var spawn_hint: Vector3 = Vector3(NAN, NAN, NAN)
## Where the first area was centred (read after the load).
var spawn_at: Vector3 = Vector3.ZERO
## Load the models of the buildings around the spawn on this thread (RWG v2 Phase 3): the kit
## pieces and the props of the authored buildings within the build ring, so the boot's and the
## ring's first builds find them in ModelLibrary instead of loading them on the main thread. Off
## under the headless dummy renderer, whose mesh table is not thread-safe (TD-103).
var warm_models: bool = false
## Models warmed by the last load (tools, LoadMeter).
var warmed: int = 0
## Set before loading to also prepare the terrain's pure data here (TD-197): the cellars and
## splat images of the 1 m regions (RegionTerrain meta "holes" / "splat", which TerrainManager
## takes) and the layer textures' data. They were ~250 ms of the boot's terrain frame.
var prepare_terrain: bool = false
## TerrainTextures.prepare() when prepare_terrain is set and none are shared yet; null otherwise.
var terrain_textures: TerrainTextures = null
## A random world's map image (the loading screen shows it, ADR-0038 §4); "" otherwise.
var map_path: String = ""
## Region states for the loading screen's map: rid -> LoadingMap.PENDING/WORKING/DONE.
var _states: Dictionary = {}
var _mutex := Mutex.new()

const Lots := preload("res://src/poi/lot_picker.gd")


func load_world(world_dir: String, detail_spacing: float = 1.0, coarse_spacing: float = 16.0, only_regions: PackedStringArray = []) -> void:
	var wd: WorldDef = WorldDef.load_from(world_dir)
	_mutex.lock()
	world = wd
	_mutex.unlock()
	if world == null:
		error = "cannot load world at %s" % world_dir
		done = true
		return
	var ids: Array = world.regions.keys()
	ids.sort()
	if not world.generator.is_empty() and stream:
		_compose_streamed(ids, detail_spacing, coarse_spacing)
		_resolve_lots()
		_prepare_terrain()
		_set_stage("Ready", 1.0)
		done = true
		return
	if not world.generator.is_empty():
		_compose_parallel(ids, detail_spacing, coarse_spacing, only_regions)
		_resolve_lots()
		_prepare_terrain()
		_set_stage("Ready", 1.0)
		done = true
		return
	var total: int = ids.size()
	var k: int = 0
	for rid: String in ids:
		k += 1
		var built: bool = world.is_region_built(rid) and (only_regions.is_empty() or only_regions.has(rid))
		_set_stage("%s %s" % ["Shaping" if built else "Surveying", str(world.regions[rid].get("name", rid))], float(k - 1) / total)
		if built:
			var rt: RegionTerrain = TerrainComposer.get_or_compose(world, rid, detail_spacing)
			_mutex.lock()
			detailed[rid] = rt
			_mutex.unlock()
		else:
			var ct: RegionTerrain = TerrainComposer.get_or_compose(world, rid, coarse_spacing)
			_mutex.lock()
			coarse[rid] = ct
			_mutex.unlock()
	_resolve_lots()
	_prepare_terrain()
	_set_stage("Ready", 1.0)
	done = true


## See prepare_terrain. The detailed regions are this thread's until the load is done.
func _prepare_terrain() -> void:
	if not prepare_terrain:
		return
	_set_stage("Laying the ground", 0.995)
	for rid: String in detailed:
		var rt: RegionTerrain = detailed[rid]
		rt.set_meta(&"holes", TerrainHoles.from_regions({rid: rt}, world_seed))
		TerrainManager.prepare_splat(rt)
	if not TerrainTextures.is_shared_ready():
		terrain_textures = TerrainTextures.prepare()


func _resolve_lots() -> void:
	if not resolve_lots or ContentDB.instance == null:
		return
	_set_stage("Spreading the Bloom", 0.97)
	# A streamed world's field covers every region, the coarse ones too (a region past the first
	# area must not be Bloom-free), but only the first area's tiles are composed now, at 1 m; the
	# rest are composed near the player as it goes (BloomTiles, TD-106).
	var spread: Dictionary = detailed
	if stream:
		spread = coarse.duplicate()
		spread.merge(detailed, true)
	var tb: int = Time.get_ticks_msec()
	bloom_tiles = BloomTiles.build(world, spread, ContentDB.instance.config(&"bloom"), stream)
	bloom_ms = Time.get_ticks_msec() - tb
	print("[bloom] built in %d ms, %d zones, %d tiles, %.1f MB" % [bloom_ms, bloom_tiles.zones.size(), bloom_tiles.tile_count(), bloom_tiles.memory_bytes() / 1048576.0])
	_set_stage("Planning the towns", 0.98)
	var to_make: Array = []
	for rid: String in detailed:
		for pl: Dictionary in (detailed[rid] as RegionTerrain).placements:
			# An organic town (ADR-0040) has a "town" placement in every region it touches: resolved once.
			if not str(pl.get("kind", "")) in ["framework", "town"] or lots.has(str(pl["id"])):
				continue
			var fw: FrameworkDef = ContentDB.instance.call(&"get_def", &"framework", StringName(str(pl["def"]))) as FrameworkDef
			if fw == null:
				continue
			var out: Array = []
			for res: Dictionary in Lots.resolve(fw, str(pl["id"]), world_seed):
				# A streamed world generates a lot's building on a worker when it enters the
				# build ring (PoiManager); only a world built whole at load needs them all now.
				var placed: bool = not stream and not str(res["kind"]) in ["reserved", "empty"]
				var pair: Array = [res, null]
				if placed:
					to_make.append(pair)
				out.append(pair)
			lots[str(pl["id"])] = out
	# The buildings of a world built whole, made on the worker pool at once: a generated house takes
	# tens of milliseconds (its validator retries more), and Pell's Crossing's west end (ADR-0059)
	# made one after another added 5-10 s to the main map's load. Each task writes only its own
	# pair's slot; the defs are pure (BuildingGenerator and LotPicker read ContentDB.instance).
	if not to_make.is_empty():
		var task: int = WorkerThreadPool.add_group_task(func(i: int) -> void:
			var pr: Array = to_make[i]
			pr[1] = Lots.def_for(pr[0]), to_make.size(), -1, true, "lot buildings")
		WorkerThreadPool.wait_for_group_task_completion(task)
	# Every region's placements, the coarse ones too: a streamed world composes only the first
	# area at 1 m, and the rest of its towns still need their lots resolved (not generated).
	var all: Dictionary = coarse.duplicate()
	all.merge(detailed, true)
	registry = PoiRegistry.build(world, all, lots, world_seed)
	if stream and warm_models:
		_set_stage("Unpacking the towns", 0.99)
		_warm_models(spawn_at)


## See warm_models. ModelLibrary takes its own mutex; a model the main thread loads meanwhile is
## at worst loaded twice.
func _warm_models(at: Vector3) -> void:
	var db: Node = ContentDB.instance
	var cfg: Dictionary = (db.call(&"config", &"streaming") as Dictionary).get("poi", {}) if db != null else {}
	var want: Dictionary = {}
	for f: String in ResourceLoader.list_directory("res://assets/generated/models/kit"):
		if f.ends_with(".glb"):
			want["kit/" + f.get_basename()] = true
	var defs: Dictionary = {}
	for hit: Array in registry.near(Vector2(at.x, at.z), float(cfg.get("build", 450.0))):
		var did: StringName = registry.def_id(hit[0])
		if did != &"":
			defs[did] = true
	for did: StringName in defs:
		var pd: PoiDef = db.call(&"get_def", &"poi", did) as PoiDef
		if pd == null:
			continue
		for p: Variant in pd.layout.get("props", []):
			var pdef: PropDef = db.call(&"get_def", &"prop", StringName(str((p as Dictionary).get("prop", "")))) as PropDef
			if pdef != null:
				want[pdef.model_for(str((p as Dictionary).get("variant", "worn")))] = true
	for m: String in want:
		if m != "" and ModelLibrary.has_model(m):
			ModelLibrary.mesh(m)
			warmed += 1


## A random world: the saved world `world_id` when it is still on disk (identical to what the run
## was played in, even if the generator has changed since), else generated from `gen`
## (WorldGenSettings.to_dict()) or read from its cache; then loaded like any world.
func load_random_world(gen: Dictionary, saved_id: String = "", detail_spacing: float = 1.0, only_regions: PackedStringArray = []) -> void:
	var worlds: GDScript = load("res://src/worldgen/rwg/rwg_worlds.gd") as GDScript
	var dir: String = ""
	if saved_id != "" and FileAccess.file_exists(str(worlds.call(&"dir_for", saved_id)).path_join("world.json")):
		dir = worlds.call(&"dir_for", saved_id)
		for e: String in worlds.call(&"register_frameworks", dir):
			push_warning("WorldLoader: %s" % e)
		world_id = saved_id
	else:
		var settings: RefCounted = (load("res://src/worldgen/rwg/world_gen_settings.gd") as GDScript).call(&"from_dict", gen)
		var res: Dictionary = worlds.call(&"ensure", settings, func(s: String, t: float) -> void: _set_stage(s, t * 0.25), true)
		if not bool(res.get("ok", false)):
			error = str(res.get("error", "could not generate the world"))
			done = true
			return
		dir = res["dir"]
		world_id = res["world_id"]
	if FileAccess.file_exists(dir.path_join("map.png")):
		_mutex.lock()
		map_path = dir.path_join("map.png")
		_mutex.unlock()
	load_world(dir, detail_spacing, 16.0, only_regions)


## Composes every region on up to three threads of its own (a generated world builds all of them).
func _compose_parallel(ids: Array, detail_spacing: float, coarse_spacing: float, only_regions: PackedStringArray) -> void:
	var jobs: Array = []
	for rid: String in ids:
		var built: bool = world.is_region_built(rid) and (only_regions.is_empty() or only_regions.has(rid))
		jobs.append([rid, detail_spacing if built else coarse_spacing, built])
	_compose_jobs(jobs, "Shaping the land (%d of %d regions)", 0.25, 1.0)


## Streamed worlds (ADR-0038, RWG_V2_PLAN §1.4/§4): every region at the coarse spacing (far
## tiles, water, the height_at fallback), then only the regions within first_area m of the spawn
## at 1 m; the RegionStreamer brings in the rest as the player moves.
func _compose_streamed(ids: Array, detail_spacing: float, coarse_spacing: float) -> void:
	var jobs: Array = []
	for rid: String in ids:
		jobs.append([rid, coarse_spacing, false])
	_compose_jobs(jobs, "Surveying the far hills (%d of %d regions)", 0.25, 0.6)
	var cfg: Dictionary = (ContentDB.instance.call(&"config", &"streaming") as Dictionary).get("region", {}) if ContentDB.instance != null else {}
	var first_r: float = float(cfg.get("first_area", 300.0))
	var at: Vector3 = spawn_hint if is_finite(spawn_hint.x) else _drop_site()
	_mutex.lock()
	spawn_at = at
	_mutex.unlock()
	var first: Array = []
	for rid2: String in ids:
		if world.is_region_built(rid2) and RegionRings.rect_distance(world.region_rect(rid2), Vector2(at.x, at.z)) <= first_r:
			first.append([rid2, detail_spacing, true])
	_compose_jobs(first, "Shaping the land around you (%d of %d regions)", 0.6, 1.0)


## Where a new game starts: the drop_site spawn of the coarse regions (their metadata has the
## spawns), else the world's centre.
func _drop_site() -> Vector3:
	for rid: String in coarse:
		var rt: RegionTerrain = coarse[rid]
		if rt.spawns.has("drop_site"):
			var a: Array = rt.spawns["drop_site"]["pos"]
			return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return Vector3.ZERO


## Composes [rid, spacing, into_detailed] jobs on up to three threads of their own, reporting
## progress from p0 to p1 with `stage_fmt` (% [done, total]).
func _compose_jobs(jobs: Array, stage_fmt: String, p0: float, p1: float) -> void:
	for job: Array in jobs:
		world.region_data(str(job[0]))
	var next: Array[int] = [0]
	var finished: Array[int] = [0]
	var run := func() -> void:
		while true:
			_mutex.lock()
			var i: int = next[0]
			next[0] += 1
			_mutex.unlock()
			if i >= jobs.size():
				return
			var rid3: String = jobs[i][0]
			var spacing: float = jobs[i][1]
			var into_detailed: bool = jobs[i][2]
			_mutex.lock()
			_states[rid3] = LoadingMap.WORKING
			_mutex.unlock()
			var rt: RegionTerrain = TerrainComposer.get_or_compose(world, rid3, spacing)
			_mutex.lock()
			if into_detailed:
				detailed[rid3] = rt
			else:
				coarse[rid3] = rt
			_states[rid3] = LoadingMap.DONE
			finished[0] += 1
			stage = stage_fmt % [finished[0], jobs.size()]
			progress = p0 + (p1 - p0) * float(finished[0]) / maxf(1.0, jobs.size())
			_mutex.unlock()
	_set_stage(stage_fmt % [0, jobs.size()], p0)
	var count: int = mini(clampi(OS.get_processor_count() - 1, 1, 3), jobs.size())
	var threads: Array[Thread] = []
	for t: int in count:
		var th := Thread.new()
		th.start(run)
		threads.append(th)
	for th2: Thread in threads:
		th2.wait_to_finish()


## [stage, progress] for the loading screen, read under the lock the worker writes them with (a
## String read while another thread replaces it can free it twice).
func status() -> Array:
	_mutex.lock()
	var out: Array = [stage, progress]
	_mutex.unlock()
	return out


func map_file() -> String:
	_mutex.lock()
	var out: String = map_path
	_mutex.unlock()
	return out


## The loading screen's map marks (LoadingMap): every region's state on the world's grid.
## Read from the main thread while the loader runs: world and map_path are set under the lock.
func marks() -> Dictionary:
	_mutex.lock()
	if world == null:
		_mutex.unlock()
		return {}
	var cells: Dictionary = {}
	for rid: String in world.regions:
		cells[WorldDef.cell_coords(str(world.regions[rid]["cell"]))] = int(_states.get(rid, LoadingMap.PENDING))
	_mutex.unlock()
	return {"grid": Vector2i(world.cols, world.rows), "cells": cells}


func _set_stage(s: String, p: float) -> void:
	_mutex.lock()
	stage = s
	progress = p
	_mutex.unlock()
