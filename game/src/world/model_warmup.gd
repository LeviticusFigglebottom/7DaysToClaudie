extends RefCounted
## Loads the scenes of models that spawn mid-game (Hollowed bodies, sleepers, wildlife) on the
## engine's loader threads shortly before they are needed, so the first of each to appear doesn't
## load its .glb on the main thread: a body's first load was 25-45 ms of a 35-77 ms frame
## (perf_capture "~visual load", "~wildlife spawn ..."), once per model per session.
## Callers ask for what they are about to spawn (request()) and spawn once ready() says so;
## only what actually spawns is loaded (asking for every body and animal at the world's start cost
## ~100 MB and ~1.4 s of settling).
## Off on the headless dummy renderer: its mesh storage is not thread-safe, and a mesh made on a
## loader thread while the main thread made another corrupted its RIDs ("Initializing already
## initialized RID" in the main smoke). There every model loads on the main thread, as before.

static var _pending: PackedStringArray = []


static func enabled() -> bool:
	return DisplayServer.get_name() != "headless"


static func path_of(id: String) -> String:
	return "res://assets/generated/models/%s.glb" % id


## Requests each model id's scene, skipping those cached, already asked for or missing.
static func request(model_ids: PackedStringArray) -> void:
	if not enabled():
		return
	for id: String in model_ids:
		var path: String = path_of(id)
		if id == "" or _pending.has(path) or ResourceLoader.has_cached(path) or not ResourceLoader.exists(path):
			continue
		if ResourceLoader.load_threaded_request(path, "PackedScene") == OK:
			_pending.append(path)


## Whether every one of these models can be had without loading on this thread: cached, missing
## (nothing to load: the stand-in body), or its load finished (taken now, which caches it). Always
## true where loading in threads is off.
static func ready(model_ids: PackedStringArray) -> bool:
	if not enabled():
		return true
	var all: bool = true
	for id: String in model_ids:
		var path: String = path_of(id)
		if id == "" or ResourceLoader.has_cached(path) or not ResourceLoader.exists(path):
			continue
		if not _pending.has(path):
			all = false
			continue
		match ResourceLoader.load_threaded_get_status(path):
			ResourceLoader.THREAD_LOAD_LOADED:
				ResourceLoader.load_threaded_get(path)
				_pending.erase(path)
			ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				all = false
			_:
				# Failed: the spawn will try the plain load (and fall back to the stand-in).
				_pending.erase(path)
	return all


## Asks for these models and says whether they are ready (request() then ready()).
static func want(model_ids: PackedStringArray) -> bool:
	request(model_ids)
	return ready(model_ids)


## Joins the loads still running (they'd otherwise outlive the world that asked for them).
static func finish() -> void:
	for path: String in _pending:
		if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			ResourceLoader.load_threaded_get(path)
	_pending.clear()
