class_name RegionCache
extends RefCounted
## The disk cache of composed regions (ADR-0038): user://cache/worlds/<world id>/<region id>_<spacing
## x 100>.bin (RegionTerrain's files, keyed inside by TerrainComposer.input_hash), plus an LRU
## index, index.json: {world_id: {file: [bytes, last_used unix seconds]}}.
##
## A streamed world composes its 1 m regions as the player walks (about 4 MB each, so a fully
## explored 16 x 16 world is about 1 GB). After every detail write (any spacing finer than 16 m)
## the detail files are trimmed to a budget, least recently used first across worlds, never the
## file just written nor any path in `keep`. Coarse files (16 m and coarser, ~25 KB a region,
## every region of every world at load) are never evicted here: RwgWorlds.prune removes them
## with their world, and keeps every world a save names.
##
## The index only orders evictions. A missing or unreadable index, a file another process wrote,
## or one removed behind its back is read back from the folders (size; modified time as the last
## use) at the next trim, and leftover temporary files older than an hour are removed then.
## Thread-safe (one mutex); the composer's threads share `shared()`.

const ROOT: String = "user://cache/worlds"
const INDEX_FILE: String = "index.json"
## spacing x 100 from which a file is coarse (never evicted by a trim).
const COARSE_SUFFIX: int = 1600
## The detail budget when data/config/streaming.json gives no cache.detail_max_mb.
const DEFAULT_BUDGET_MB: int = 2048
## A leftover temporary file (a crash mid-write) older than this is removed by a trim.
const TMP_MAX_AGE_S: int = 3600
## Cache hits reach index.json at most this often; writes always do.
const TOUCH_FLUSH_S: int = 10

static var _shared: RegionCache = null
static var _shared_mutex := Mutex.new()

## The cache folder (tests use their own).
var root: String = ROOT
## The detail budget in MB; -1 reads streaming.json (cache.detail_max_mb), else DEFAULT_BUDGET_MB.
var budget_mb: int = -1
var _index: Dictionary = {}
var _loaded: bool = false
var _dirty: bool = false
var _last_flush: int = 0
var _mutex := Mutex.new()


## The cache every compose shares (user://cache/worlds).
static func shared() -> RegionCache:
	_shared_mutex.lock()
	if _shared == null:
		_shared = RegionCache.new()
	var s: RegionCache = _shared
	_shared_mutex.unlock()
	return s


## Where a region's composed terrain is cached (v1's path; the file holds its input hash).
static func path_for(world_id: String, region_id: String, spacing: float) -> String:
	return "%s/%s/%s_%d.bin" % [ROOT, world_id, region_id, int(spacing * 100)]


## True for a file finer than 16 m ("<region>_<spacing x 100>.bin" below 1600): what a trim evicts.
static func is_detail(file: String) -> bool:
	var parts: PackedStringArray = file.get_file().get_basename().rsplit("_", true, 1)
	return parts.size() == 2 and parts[1].is_valid_int() and int(parts[1]) < COARSE_SUFFIX


## Records a file just written and, for a detail file, trims the detail files to the budget (never
## `path` itself, nor `keep`). Returns the evicted paths.
func wrote(path: String, keep: PackedStringArray = []) -> PackedStringArray:
	_mutex.lock()
	_load()
	_record(path, _size_of(path))
	var removed := PackedStringArray()
	if is_detail(path):
		var k: PackedStringArray = keep.duplicate()
		k.append(path)
		removed = _trim(budget_bytes(), k)
	_flush()
	_mutex.unlock()
	return removed


## A cache hit: `path` was used now.
func touch(path: String) -> void:
	_mutex.lock()
	_load()
	var e: Variant = (_index.get(path.get_base_dir().get_file(), {}) as Dictionary).get(path.get_file())
	_record(path, int(e[0]) if e is Array else _size_of(path))
	if _now() - _last_flush >= TOUCH_FLUSH_S:
		_flush()
	_mutex.unlock()


## Evicts detail files, least recently used first, until they fit `budget` bytes (never a path in
## `keep`). Returns the evicted paths.
func trim(budget: int, keep: PackedStringArray = []) -> PackedStringArray:
	_mutex.lock()
	_load()
	var removed: PackedStringArray = _trim(budget, keep)
	_flush()
	_mutex.unlock()
	return removed


## Writes the index now (e.g. when a session ends, so its last hits count).
func flush() -> void:
	_mutex.lock()
	_flush()
	_mutex.unlock()


func budget_bytes() -> int:
	var mb: int = budget_mb
	if mb < 0:
		mb = DEFAULT_BUDGET_MB
		var db: Node = ContentDB.instance
		if db != null:
			var cache: Variant = (db.call(&"config", &"streaming") as Dictionary).get("cache", {})
			if cache is Dictionary and (cache as Dictionary).has("detail_max_mb"):
				mb = int(cache["detail_max_mb"])
	return mb * 1048576


## {detail_bytes, detail_files, coarse_bytes, coarse_files, worlds} after reading the folders.
func stats() -> Dictionary:
	_mutex.lock()
	_load()
	_reconcile()
	var out: Dictionary = {"detail_bytes": 0, "detail_files": 0, "coarse_bytes": 0, "coarse_files": 0, "worlds": _index.size()}
	for wid: String in _index:
		var files: Dictionary = _index[wid]
		for file: String in files:
			var kind: String = "detail" if is_detail(file) else "coarse"
			out["%s_bytes" % kind] = int(out["%s_bytes" % kind]) + int(files[file][0])
			out["%s_files" % kind] = int(out["%s_files" % kind]) + 1
	_flush()
	_mutex.unlock()
	return out


# --- Internals (under _mutex) ------------------------------------------------------------------

func _trim(budget: int, keep: PackedStringArray) -> PackedStringArray:
	_reconcile()
	var detail: Array = []
	var total: int = 0
	for wid: String in _index:
		var files: Dictionary = _index[wid]
		for file: String in files:
			if is_detail(file):
				detail.append([int(files[file][1]), "%s/%s" % [wid, file], int(files[file][0])])
				total += int(files[file][0])
	var removed := PackedStringArray()
	if total <= budget:
		return removed
	detail.sort_custom(func(a: Array, b: Array) -> bool: return int(a[0]) < int(b[0]) or (int(a[0]) == int(b[0]) and str(a[1]) < str(b[1])))
	for d: Array in detail:
		if total <= budget:
			break
		var p: String = root.path_join(str(d[1]))
		if keep.has(p):
			continue
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)
		var wid2: String = str(d[1]).get_base_dir()
		(_index.get(wid2, {}) as Dictionary).erase(str(d[1]).get_file())
		total -= int(d[2])
		removed.append(p)
		_dirty = true
	return removed


## Brings the index in line with the folders: adds files it doesn't know (size, modified time),
## drops files and worlds gone, and removes stale temporary files.
func _reconcile() -> void:
	if not DirAccess.dir_exists_absolute(root):
		if not _index.is_empty():
			_index.clear()
			_dirty = true
		return
	var now: int = _now()
	var seen: Dictionary = {}
	for wid: String in DirAccess.get_directories_at(root):
		var dir: String = root.path_join(wid)
		var files: Dictionary = _index.get(wid, {})
		var present: Dictionary = {}
		for file: String in DirAccess.get_files_at(dir):
			var p: String = dir.path_join(file)
			if file.ends_with(".tmp"):
				if now - int(FileAccess.get_modified_time(p)) > TMP_MAX_AGE_S:
					DirAccess.remove_absolute(p)
				continue
			if not file.ends_with(".bin"):
				continue
			present[file] = true
			if not files.has(file):
				files[file] = [_size_of(p), int(FileAccess.get_modified_time(p))]
				_dirty = true
		for known: String in files.keys():
			if not present.has(known):
				files.erase(known)
				_dirty = true
		if files.is_empty():
			_index.erase(wid)
		else:
			_index[wid] = files
		seen[wid] = true
	for wid2: String in _index.keys():
		if not seen.has(wid2):
			_index.erase(wid2)
			_dirty = true


func _record(path: String, bytes: int) -> void:
	var wid: String = path.get_base_dir().get_file()
	if not _index.has(wid):
		_index[wid] = {}
	(_index[wid] as Dictionary)[path.get_file()] = [bytes, _now()]
	_dirty = true


func _load() -> void:
	if _loaded:
		return
	_loaded = true
	_last_flush = _now()
	var p: String = root.path_join(INDEX_FILE)
	if not FileAccess.file_exists(p):
		return
	# A JSON instance: a damaged index is simply rebuilt, never an engine error.
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(p)) != OK or not json.data is Dictionary:
		return
	for wid: Variant in json.data:
		var files: Variant = json.data[wid]
		if not files is Dictionary:
			continue
		var clean: Dictionary = {}
		for file: Variant in files:
			var e: Variant = files[file]
			if e is Array and (e as Array).size() == 2:
				clean[str(file)] = [int(e[0]), int(e[1])]
		if not clean.is_empty():
			_index[str(wid)] = clean


func _flush() -> void:
	if not _dirty:
		return
	_dirty = false
	_last_flush = _now()
	if not DirAccess.dir_exists_absolute(root):
		DirAccess.make_dir_recursive_absolute(root)
	var p: String = root.path_join(INDEX_FILE)
	var tmp: String = "%s.%d_%d.tmp" % [p, OS.get_process_id(), OS.get_thread_caller_id()]
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(_index, "", true))
	f.close()
	if DirAccess.rename_absolute(tmp, p) != OK:
		DirAccess.remove_absolute(p)
		if DirAccess.rename_absolute(tmp, p) != OK:
			DirAccess.remove_absolute(tmp)


static func _size_of(path: String) -> int:
	var f := FileAccess.open(path, FileAccess.READ)
	return f.get_length() if f != null else 0


static func _now() -> int:
	return int(Time.get_unix_time_from_system())
