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
## The Bloom field over the detailed regions, built here too when resolve_lots is set (about a
## second of the main thread on a 3x3 random world, ADR-0036); null otherwise.
var bloom_field: BloomField = null
## Streamed loading (ADR-0038): only the first area is composed at 1 m (random worlds; set before
## loading). spawn_hint: where the player will stand (a saved position), NAN for the drop site.
var stream: bool = false
var spawn_hint: Vector3 = Vector3(NAN, NAN, NAN)
## Where the first area was centred (read after the load).
var spawn_at: Vector3 = Vector3.ZERO
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
		_set_stage("Ready", 1.0)
		done = true
		return
	if not world.generator.is_empty():
		_compose_parallel(ids, detail_spacing, coarse_spacing, only_regions)
		_resolve_lots()
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
	_set_stage("Ready", 1.0)
	done = true


func _resolve_lots() -> void:
	if not resolve_lots or ContentDB.instance == null:
		return
	_set_stage("Spreading the Bloom", 0.97)
	bloom_field = BloomField.build(world, detailed, ContentDB.instance.config(&"bloom"))
	_set_stage("Planning the towns", 0.98)
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
				var placed: bool = not str(res["kind"]) in ["reserved", "empty"]
				out.append([res, Lots.def_for(res) if placed else null])
			lots[str(pl["id"])] = out


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
