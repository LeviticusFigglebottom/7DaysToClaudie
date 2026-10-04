class_name SaveSystem
extends RefCounted
## Versioned, migration-capable, chunk-based saves (ADR-0005).
##
## Layout of a slot (user://saves/<slot>/):
##   meta.json        small summary for the load menu (version, day, play time, ...)
##   session.json     GameSession.to_dict() wrapped as {save_version, session}
##   chunks/<k>.bin   per-chunk binary blobs (terrain height deltas, volume densities)
## Writes are atomic: everything goes to <slot>.tmp, then swaps in.
##
## Migrations: when the save format changes, bump CURRENT_VERSION and register a function
## that upgrades a dictionary from version N to N+1 in _builtin_migrations(). Old saves are
## upgraded step by step on load. Never edit an existing migration after release.

const SAVE_ROOT: String = "user://saves"
const CURRENT_VERSION: int = 1


## from_version -> Callable(Dictionary) -> Dictionary
static func _builtin_migrations() -> Dictionary:
	return {
		# 1: func(d: Dictionary) -> Dictionary: ... (first real migration goes here)
	}


static func slot_dir(slot: String) -> String:
	return SAVE_ROOT.path_join(_sanitize(slot))


static func slot_exists(slot: String) -> bool:
	return FileAccess.file_exists(slot_dir(slot).path_join("session.json"))


static func save_session(session: GameSession, slot: String) -> Error:
	var final_dir: String = slot_dir(slot)
	var tmp_dir: String = final_dir + ".tmp"
	var old_dir: String = final_dir + ".old"
	_remove_recursive(tmp_dir)
	var err: Error = DirAccess.make_dir_recursive_absolute(tmp_dir.path_join("chunks"))
	if err != OK:
		return err
	var meta: Dictionary = {
		"save_version": CURRENT_VERSION,
		"game_version": str(ProjectSettings.get_setting("application/config/version", "0")),
		"slot": slot,
		"saved_unix": int(Time.get_unix_time_from_system()),
		"play_seconds": session.play_seconds,
		"day": session.clock.day(),
		"hour": session.clock.hour_f(),
		"world_mode": String(session.world_mode),
		"world_id": String(session.world_id),
		"seed": str(session.world_seed),
		"game_mode": String(session.game_mode),
		"player": session.local_player().display_name if session.local_player() else "",
	}
	err = _write_json(tmp_dir.path_join("meta.json"), meta)
	if err != OK:
		return err
	err = _write_json(tmp_dir.path_join("session.json"), {"save_version": CURRENT_VERSION, "session": session.to_dict()})
	if err != OK:
		return err
	for key: Variant in session.world.chunk_blobs.keys():
		var f := FileAccess.open(tmp_dir.path_join("chunks").path_join("%s.bin" % key), FileAccess.WRITE)
		if f == null:
			return FileAccess.get_open_error()
		f.store_buffer(session.world.chunk_blobs[key])
		f.close()
	# Swap in atomically-ish (rename is atomic per directory on the same filesystem).
	_remove_recursive(old_dir)
	if DirAccess.dir_exists_absolute(final_dir):
		err = DirAccess.rename_absolute(final_dir, old_dir)
		if err != OK:
			return err
	err = DirAccess.rename_absolute(tmp_dir, final_dir)
	if err != OK:
		DirAccess.rename_absolute(old_dir, final_dir)
		return err
	_remove_recursive(old_dir)
	return OK


## Loads and migrates a slot. Returns null on failure (details in Log).
static func load_session(slot: String) -> GameSession:
	var dir: String = slot_dir(slot)
	var data: Variant = _read_json(dir.path_join("session.json"))
	if not data is Dictionary:
		Log.error(&"save", "slot '%s' has no readable session.json" % slot)
		return null
	var migrated: Dictionary = migrate(data)
	if migrated.is_empty():
		return null
	var session: GameSession = GameSession.from_dict(migrated.get("session", {}))
	var chunk_dir: String = dir.path_join("chunks")
	if DirAccess.dir_exists_absolute(chunk_dir):
		for f: String in DirAccess.get_files_at(chunk_dir):
			if f.ends_with(".bin"):
				session.world.chunk_blobs[f.get_basename()] = FileAccess.get_file_as_bytes(chunk_dir.path_join(f))
	return session


## Upgrades a save dictionary to `target` version using `migrations` (defaults: built-ins).
## Returns {} if the save is newer than this build or a migration step is missing.
static func migrate(data: Dictionary, target: int = CURRENT_VERSION, migrations: Dictionary = {}) -> Dictionary:
	var steps: Dictionary = migrations if not migrations.is_empty() else _builtin_migrations()
	var out: Dictionary = data.duplicate(true)
	var v: int = int(out.get("save_version", 0))
	if v > target:
		Log.error(&"save", "save version %d is newer than supported %d" % [v, target])
		return {}
	while v < target:
		if not steps.has(v):
			Log.error(&"save", "no migration from save version %d" % v)
			return {}
		out = (steps[v] as Callable).call(out)
		v += 1
		out["save_version"] = v
		Log.info(&"save", "migrated save to version %d" % v)
	return out


static func list_slots() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not DirAccess.dir_exists_absolute(SAVE_ROOT):
		return out
	for d: String in DirAccess.get_directories_at(SAVE_ROOT):
		if d.ends_with(".tmp") or d.ends_with(".old"):
			continue
		var meta: Variant = _read_json(SAVE_ROOT.path_join(d).path_join("meta.json"))
		if meta is Dictionary:
			out.append(meta)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.get("saved_unix", 0)) > int(b.get("saved_unix", 0)))
	return out


static func delete_slot(slot: String) -> void:
	_remove_recursive(slot_dir(slot))


static func _sanitize(slot: String) -> String:
	var out: String = ""
	for c: String in slot:
		out += c if (c.is_valid_identifier() or c == "-" or (c >= "0" and c <= "9")) else "_"
	return out if out != "" else "slot"


static func _write_json(path: String, data: Variant) -> Error:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(JSON.stringify(data, "\t", false, true))
	f.close()
	return OK


static func _read_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	return JSON.parse_string(FileAccess.get_file_as_string(path))


static func _remove_recursive(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return
	for f: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(f))
	for d: String in DirAccess.get_directories_at(path):
		_remove_recursive(path.path_join(d))
	DirAccess.remove_absolute(path)
