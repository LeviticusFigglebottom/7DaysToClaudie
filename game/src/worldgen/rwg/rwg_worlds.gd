class_name RwgWorlds
extends RefCounted
## Generated worlds on disk (ADR-0031). A random world lives in user://worlds/random/<world id>/ as
## the same files a handcrafted world has (world.json, regions/<id>/region.json) plus its towns'
## frameworks (frameworks.json), its map (map.png) and a meta.json naming the settings key it was
## made from. The id hashes the map seed, the settings and RwgGenerator.VERSION, so the folder is a
## cache: a new game or a loaded save with the same settings reuses it, and anything else makes
## its own. Composed terrain caches under user://cache/worlds/<world id>/ like any world's.
##
## Before such a world loads, its towns' frameworks are registered with ContentDB
## (add_runtime_def), so the composer, PoiManager and TerrainHoles find them by id like authored
## ones. Worker-thread safe (call `ensure` from the world loader's task).

const ROOT: String = "user://worlds/random"
## How many generated worlds to keep on disk beyond those a save names (the oldest are removed,
## composed caches included). A save's own world is never removed (TD-082).
const KEEP: int = 8

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const MapImage := preload("res://src/worldgen/rwg/rwg_map.gd")


static func dir_for(world_id: String) -> String:
	return ROOT.path_join(world_id)


## The world for these settings, generated now or read from the cache. Returns {ok, dir, world_id,
## generated: bool, error, ms}. `register`: add its frameworks to ContentDB (to play it).
static func ensure(settings: RefCounted, progress: Callable = Callable(), register: bool = true) -> Dictionary:
	var t0: int = Time.get_ticks_msec()
	var wid: String = Generator.world_id_for(settings)
	var dir: String = dir_for(wid)
	var key: String = str(settings.call(&"key"))
	var out: Dictionary = {"ok": true, "dir": dir, "world_id": wid, "generated": false, "error": ""}
	if not is_cached(dir, key):
		var g: RefCounted = Generator.generate(settings, progress)
		var err: Error = write(g, dir)
		if err != OK:
			return {"ok": false, "dir": dir, "world_id": wid, "generated": true, "error": "could not write %s (%s)" % [dir, error_string(err)]}
		out["generated"] = true
		prune(wid)
	elif progress.is_valid():
		progress.call("Reading the map", 1.0)
	if register:
		var errs: PackedStringArray = register_frameworks(dir)
		for e: String in errs:
			push_warning("RwgWorlds: %s" % e)
	out["ms"] = Time.get_ticks_msec() - t0
	return out


static func is_cached(dir: String, key: String) -> bool:
	var meta: Dictionary = MapImage._read(dir.path_join("meta.json"))
	return not meta.is_empty() and str(meta.get("key", "")) == key and int(meta.get("version", -1)) == Generator.VERSION \
		and FileAccess.file_exists(dir.path_join("world.json")) and FileAccess.file_exists(dir.path_join("frameworks.json"))


## Writes a generator's output into `dir` (through a .tmp folder swapped in at the end).
static func write(g: RefCounted, dir: String) -> Error:
	var tmp: String = dir + ".tmp"
	_remove(tmp)
	var err: Error = DirAccess.make_dir_recursive_absolute(tmp.path_join("regions"))
	if err != OK:
		return err
	err = _write_json(tmp.path_join("world.json"), g.call(&"world_json"))
	if err != OK:
		return err
	var ids: Dictionary = g.call(&"region_ids")
	for cell: Variant in ids:
		var rdir: String = tmp.path_join("regions").path_join(str(ids[cell]))
		DirAccess.make_dir_recursive_absolute(rdir)
		err = _write_json(rdir.path_join("region.json"), g.call(&"region_json", str(cell)))
		if err != OK:
			return err
	err = _write_json(tmp.path_join("frameworks.json"), g.call(&"frameworks_json"))
	if err != OK:
		return err
	var settings: RefCounted = g.get(&"settings")
	err = _write_json(tmp.path_join("meta.json"), {"key": settings.call(&"key"), "version": Generator.VERSION,
		"settings": settings.call(&"to_dict"), "created": int(Time.get_unix_time_from_system()), "timings_ms": g.get(&"timings"),
		"warnings": Array(g.get(&"warnings"))})
	if err != OK:
		return err
	var img: Image = MapImage.render_dir(tmp, 1024)
	if img != null:
		img.save_png(tmp.path_join("map.png"))
	_remove(dir)
	return DirAccess.rename_absolute(tmp, dir)


## Registers a generated world's town frameworks with ContentDB. Returns problems (parse and
## cross-reference errors); a bad town is reported, never fatal.
static func register_frameworks(dir: String) -> PackedStringArray:
	var errs: PackedStringArray = []
	var db: Node = ContentDB.instance
	if db == null:
		errs.append("no content loaded")
		return errs
	var data: Dictionary = MapImage._read(dir.path_join("frameworks.json"))
	for d: Variant in data.get("defs", []):
		var fw := FrameworkDef.new()
		var pe: PackedStringArray = fw.parse(d, &"framework", "%s/frameworks.json" % dir.get_file())
		errs.append_array(pe)
		if fw.id == &"":
			continue
		fw._validate(db, errs)
		db.call(&"add_runtime_def", fw)
	return errs


## Keeps the newest KEEP generated worlds, `keep_id` and every world a save slot names, removing the
## rest with their composed terrain caches.
static func prune(keep_id: String) -> void:
	if not DirAccess.dir_exists_absolute(ROOT):
		return
	var saved: Dictionary = {}
	for meta0: Dictionary in SaveSystem.list_slots():
		saved[str(meta0.get("world_id", ""))] = true
	var dirs: Array = []
	for d: String in DirAccess.get_directories_at(ROOT):
		if d.ends_with(".tmp"):
			continue
		var meta: Dictionary = MapImage._read(ROOT.path_join(d).path_join("meta.json"))
		dirs.append([int(meta.get("created", 0)), d])
	dirs.sort_custom(func(a: Array, b: Array) -> bool: return int(a[0]) > int(b[0]))
	for k: int in range(KEEP, dirs.size()):
		var wid: String = str(dirs[k][1])
		if wid == keep_id or saved.has(wid):
			continue
		_remove(ROOT.path_join(wid))
		_remove("user://cache/worlds".path_join(wid))


static func _write_json(path: String, data: Variant) -> Error:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(JSON.stringify(data, "", false))
	f.close()
	return OK


static func _remove(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return
	for f: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(f))
	for d: String in DirAccess.get_directories_at(path):
		_remove(path.path_join(d))
	DirAccess.remove_absolute(path)
