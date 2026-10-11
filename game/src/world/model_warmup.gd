extends RefCounted
## Loads the scenes of models that spawn mid-game (Hollowed bodies, wildlife) on the engine's
## loader threads at the world's start, so the first of each to appear doesn't load its .glb on
## the main thread: a body's first load was 25-45 ms of a 35-77 ms frame (perf_capture
## "~visual load", "~wildlife spawn ..."), once per model per session. load() later finds the
## scene cached, or waits on its load already under way. Requests are fire and forget; finish()
## joins those still loading (a world leaving before they're done).

static var _pending: PackedStringArray = []


## Requests each model id's scene ("models/<id>.glb"), skipping those cached or missing.
static func request(model_ids: PackedStringArray) -> int:
	var n: int = 0
	for id: String in model_ids:
		var path: String = "res://assets/generated/models/%s.glb" % id
		if id == "" or _pending.has(path) or ResourceLoader.has_cached(path) or not ResourceLoader.exists(path):
			continue
		if ResourceLoader.load_threaded_request(path, "PackedScene") == OK:
			_pending.append(path)
			n += 1
	return n


## Joins the loads still running (they'd otherwise outlive the world that asked for them).
static func finish() -> void:
	for path: String in _pending:
		if ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			ResourceLoader.load_threaded_get(path)
	_pending.clear()
