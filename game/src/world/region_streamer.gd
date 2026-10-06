class_name RegionStreamer
extends Node
## Streams regions' 1 m terrain in and out around the players (ADR-0038, RWG_V2_PLAN §1.3).
##
## Every 0.25 s it asks RegionRings what should be attached, then:
## * a wanted region that isn't in memory gets a job on one of its own low-priority Threads (not
##   WorkerThreadPool tasks: a compose runs for seconds and must never starve chunk meshing or
##   scatter): load it from the disk cache or compose it (TerrainComposer.get_or_compose), nearest
##   and most-ahead first; jobs no longer wanted are cancelled (the composer checks `cancel`);
## * a region whose job is done is attached by a main-thread step (TerrainManager.attach_region)
##   run within a few milliseconds a frame (StepRunner), and one that left the rings detached;
## * prefetch regions are composed into the disk cache and dropped.
## Pins (the Hum's base) keep regions attached wherever the players go. Results come back through
## a slot made before the job starts (the TD-104 pattern) and a done list under the mutex.

## Kinds of job.
const LOAD: int = 0
const PREFETCH: int = 1
## How often the rings are re-planned (seconds).
const INTERVAL: float = 0.25

var terrain: TerrainManager
var rings: RegionRings
## (rid: String, cancel: Array) -> RegionTerrain or null: the default loads or composes the region
## at 1 m (tests inject a fast fake).
var compose_fn: Callable
## () -> Array of Vector3: the points to stream around (default: the terrain's focus).
var focus_fn: Callable
## Main-thread attach and detach steps, within budget_ms a frame.
var steps: StepRunner = StepRunner.new()

var _rects: Dictionary = {}
var _built: Dictionary = {}
var _attached: Dictionary = {}
## rid -> RegionTerrain composed and waiting for its attach step.
var _ready: Dictionary = {}
## rid -> job {rid, kind, priority, cancel: [bool], out: [RegionTerrain], state}
var _jobs: Dictionary = {}
var _pins: Dictionary = {}
var _extra_focus: Array = []
var _pool := Pool.new()
var _threads: Array[Thread] = []


## The job queue and the threads' loop, in an object of its own: a thread running a method of
## the streamer node would lock the node, which then can't be freed (the threads are joined in
## _exit_tree).
class Pool:
	extends RefCounted
	var mutex := Mutex.new()
	var sem := Semaphore.new()
	var queue: Array = []
	var done: Array = []
	var quit: bool = false
	var compose_fn: Callable

	func run() -> void:
		while true:
			sem.wait()
			mutex.lock()
			if quit:
				mutex.unlock()
				return
			var best: int = -1
			for i: int in queue.size():
				if best < 0 or float(queue[i]["priority"]) < float(queue[best]["priority"]):
					best = i
			if best < 0:
				mutex.unlock()
				continue
			var job: Dictionary = queue[best]
			queue.remove_at(best)
			job["state"] = 1
			var cancel: Array = job["cancel"]
			var out: Array = job["out"]
			var rid: String = job["rid"]
			mutex.unlock()
			out[0] = compose_fn.call(rid, cancel)
			mutex.lock()
			done.append(job)
			mutex.unlock()
var _accum: float = 0.0
var _stats: Dictionary = {"attached": 0, "composed": 0, "cancelled": 0, "last_attach_ms": 0.0}


## Starts streaming over `terrain`'s world. cfg: data/config/streaming.json.
func setup(p_terrain: TerrainManager, cfg: Dictionary, threads: int = -1) -> void:
	terrain = p_terrain
	var region_cfg: Dictionary = cfg.get("region", {})
	rings = RegionRings.new(region_cfg)
	steps.budget_ms = float((cfg.get("budget_ms", {}) as Dictionary).get("runtime", 4.0))
	var world: WorldDef = terrain.world
	for rid: String in world.regions:
		_rects[rid] = world.region_rect(rid)
		if world.is_region_built(rid):
			_built[rid] = true
	for rid2: String in terrain.regions:
		_attached[rid2] = true
	if not compose_fn.is_valid():
		compose_fn = func(rid: String, cancel: Array) -> RegionTerrain:
			return TerrainComposer.get_or_compose(world, rid, 1.0, Callable(), cancel)
	if not focus_fn.is_valid():
		focus_fn = func() -> Array:
			return [terrain.focus.global_position] if terrain.focus != null and is_instance_valid(terrain.focus) else []
	_pool.compose_fn = compose_fn
	var n: int = threads if threads > 0 else int(region_cfg.get("threads_runtime", 2))
	for i: int in n:
		var th := Thread.new()
		th.start(_pool.run, Thread.PRIORITY_LOW)
		_threads.append(th)


func _exit_tree() -> void:
	_pool.mutex.lock()
	_pool.quit = true
	for job: Dictionary in _jobs.values():
		(job["cancel"] as Array)[0] = true
	_pool.mutex.unlock()
	for th: Thread in _threads:
		_pool.sem.post()
	for th2: Thread in _threads:
		th2.wait_to_finish()
	_threads.clear()


func _process(delta: float) -> void:
	if terrain == null:
		return
	_collect()
	_accum += delta
	if _accum >= INTERVAL:
		_accum = 0.0
		update()
	steps.run_frame()


## Re-plans the rings and queues jobs and steps (also callable directly: tests, request_now).
func update() -> void:
	var focus: Array = focus_fn.call()
	focus.append_array(_extra_focus)
	if focus.is_empty():
		return
	var heading := Vector3.ZERO
	if terrain.focus != null and is_instance_valid(terrain.focus) and terrain.focus is CharacterBody3D:
		heading = (terrain.focus as CharacterBody3D).velocity
	var plan: Dictionary = rings.plan(_rects, _built, focus, heading, _attached, _pins)
	var prio: Dictionary = plan["priority"]
	var wanted: Dictionary = {}
	for rid: String in plan["target"]:
		wanted[rid] = true
		if _attached.has(rid):
			continue
		if _ready.has(rid):
			_queue_attach(rid)
		else:
			_request(rid, LOAD, float(prio[rid]))
	for rid2: String in plan["detach"]:
		_queue_detach(rid2)
	var prefetch: Dictionary = {}
	for rid3: String in plan["prefetch"]:
		prefetch[rid3] = true
		if not _ready.has(rid3) and not _attached.has(rid3):
			# After every wanted region: prefetch only fills the disk cache.
			_request(rid3, PREFETCH, 100000.0 + float(prio[rid3]))
	# Jobs nobody wants any more stop; composed regions nobody wants are dropped.
	_pool.mutex.lock()
	for rid4: String in _jobs.keys():
		if not wanted.has(rid4) and not prefetch.has(rid4):
			(_jobs[rid4]["cancel"] as Array)[0] = true
			_pool.queue.erase(_jobs[rid4])
			_jobs.erase(rid4)
			_stats["cancelled"] = int(_stats["cancelled"]) + 1
	_pool.mutex.unlock()
	for rid5: String in _ready.keys():
		if not wanted.has(rid5):
			_ready.erase(rid5)
			steps.cancel("attach %s" % rid5)


## Streams around `pos` at once (a teleport, a respawn), on top of the players' own focus, until
## clear_request().
func request_now(pos: Vector3) -> void:
	_extra_focus = [pos]
	update()


func clear_request() -> void:
	_extra_focus = []


## Keeps every region overlapping `rect` attached until unpin(key).
func pin(key: StringName, rect: Rect2) -> void:
	_pins[key] = rect
	update()


func unpin(key: StringName) -> void:
	_pins.erase(key)


## True when every built region within `radius` m of pos is attached.
func is_area_ready(pos: Vector3, radius: float = 0.0) -> bool:
	for rid: String in _built:
		if RegionRings.rect_distance(_rects[rid], Vector2(pos.x, pos.z)) <= radius and not _attached.has(rid):
			return false
	return true


func attached() -> Dictionary:
	return _attached


## {attached, ready, jobs, queued_steps, composed, cancelled, last_attach_ms}
func status() -> Dictionary:
	_pool.mutex.lock()
	var jobs: int = _jobs.size()
	_pool.mutex.unlock()
	var out: Dictionary = _stats.duplicate()
	out["attached"] = _attached.size()
	out["ready"] = _ready.size()
	out["jobs"] = jobs
	out["queued_steps"] = steps.pending()
	return out


# --- Jobs ----------------------------------------------------------------------------------

func _request(rid: String, kind: int, priority: float) -> void:
	_pool.mutex.lock()
	var job: Dictionary = _jobs.get(rid, {})
	if job.is_empty():
		job = {"rid": rid, "kind": kind, "priority": priority, "cancel": [false], "out": [null], "state": 0}
		_jobs[rid] = job
		_pool.queue.append(job)
		_pool.mutex.unlock()
		_pool.sem.post()
		return
	# Already queued or running: a wanted region outranks a prefetch of it, and priorities move
	# with the player.
	job["priority"] = priority
	if kind == LOAD:
		job["kind"] = LOAD
	_pool.mutex.unlock()


## Takes finished jobs on the main thread.
func _collect() -> void:
	_pool.mutex.lock()
	var done: Array = _pool.done
	_pool.done = []
	_pool.mutex.unlock()
	for job: Dictionary in done:
		var rid: String = job["rid"]
		var rt: RegionTerrain = job["out"][0]
		_pool.mutex.lock()
		if _jobs.get(rid) == job:
			_jobs.erase(rid)
		_pool.mutex.unlock()
		if bool(job["cancel"][0]) or rt == null:
			continue
		_stats["composed"] = int(_stats["composed"]) + 1
		if int(job["kind"]) == LOAD:
			_ready[rid] = rt
			_queue_attach(rid)


## Queues the main-thread attach of a composed region (once; a pending detach of it is dropped).
func _queue_attach(rid: String) -> void:
	steps.cancel("detach %s" % rid)
	if _attached.has(rid) or not _ready.has(rid):
		return
	steps.cancel("attach %s" % rid)
	steps.add(["Shaping the land around you…", func() -> void:
		var rt: RegionTerrain = _ready.get(rid)
		if rt == null or _attached.has(rid):
			return
		var t0: int = Time.get_ticks_usec()
		terrain.attach_region(rt)
		_stats["last_attach_ms"] = float(Time.get_ticks_usec() - t0) / 1000.0
		_ready.erase(rid)
		_attached[rid] = true, "attach %s" % rid])


## Queues the detach of a region that left the rings (once; a pending attach of it is dropped).
func _queue_detach(rid: String) -> void:
	steps.cancel("attach %s" % rid)
	_ready.erase(rid)
	if not _attached.has(rid):
		return
	steps.cancel("detach %s" % rid)
	steps.add(["", func() -> void:
		if _attached.has(rid):
			terrain.detach_region(rid)
			_attached.erase(rid), "detach %s" % rid])
