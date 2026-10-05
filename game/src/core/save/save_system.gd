class_name SaveSystem
extends RefCounted
## Versioned, migration-capable, chunk-based saves (ADR-0005).
##
## Layout of a slot (user://saves/<slot>/):
##   meta.json        small summary for the load menu (version, day, play time, ...)
##   session.json     GameSession.to_dict() wrapped as {save_version, session}
##   chunks/<k>.bin   per-chunk binary blobs (terrain height deltas, volume densities); a key's
##                    ':' is written as '~' (Windows forbids ':' in file names), both read back
## Writes are atomic: everything goes to <slot>.tmp, then swaps in. A slot whose session.json is
## missing or unreadable falls back to <slot>.old, the previous save kept during the swap.
##
## One slot per run: a new game gets the next free "runN" and every save of that run (manual,
## autosave on waking and after a Hum, quicksave) writes to it, so starting a new game never
## overwrites another run and a permadeath run leaves nothing behind to reload.
##
## Migrations: when the save format changes, bump CURRENT_VERSION and register a function
## that upgrades a dictionary from version N to N+1 in _builtin_migrations(). Old saves are
## upgraded step by step on load. Never edit an existing migration after release.

const SAVE_ROOT: String = "user://saves"
const CURRENT_VERSION: int = 2


## from_version -> Callable(Dictionary) -> Dictionary
static func _builtin_migrations() -> Dictionary:
	return {
		1: _drop_harvested_plants,
	}


## 1 -> 2: the medium and ground vegetation layers were re-laid out (patches, moss, litter), so
## the instance indices of harvested plants, stones and deadfall now point at other instances.
## Their records are dropped (those plants are simply back); felled trees keep their stumps
## because the tree layer, which comes first, is unchanged.
static func _drop_harvested_plants(d: Dictionary) -> Dictionary:
	var world: Dictionary = (d.get("session", {}) as Dictionary).get("world", {})
	var trees: Dictionary = world.get("trees", {})
	for ck: Variant in trees.keys():
		var per_chunk: Dictionary = trees[ck]
		for idx: Variant in per_chunk.keys():
			if str((per_chunk[idx] as Dictionary).get("state", "")) != "stump":
				per_chunk.erase(idx)
		if per_chunk.is_empty():
			trees.erase(ck)
	return d


static func slot_dir(slot: String) -> String:
	return SAVE_ROOT.path_join(_sanitize(slot))


static func slot_exists(slot: String) -> bool:
	return FileAccess.file_exists(slot_dir(slot).path_join("session.json")) \
		or FileAccess.file_exists(slot_dir(slot) + ".old/session.json")


## The first free "runN" slot name for a new game.
static func new_run_slot() -> String:
	var n: int = 1
	while DirAccess.dir_exists_absolute(slot_dir("run%d" % n)) or DirAccess.dir_exists_absolute(slot_dir("run%d" % n) + ".old"):
		n += 1
	return "run%d" % n


## Chunk blob keys hold ':' ("t:3_-4"); file names must not (Windows).
static func blob_file_name(key: String) -> String:
	return key.replace(":", "~") + ".bin"


static func blob_key(file_name: String) -> String:
	return file_name.get_basename().replace("~", ":")


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
		"preset": String(session.rules.preset) if session.rules != null else "",
		"player": session.local_player().display_name if session.local_player() else "",
	}
	err = _write_json(tmp_dir.path_join("meta.json"), meta)
	if err != OK:
		return err
	err = _write_json(tmp_dir.path_join("session.json"), {"save_version": CURRENT_VERSION, "session": session.to_dict()})
	if err != OK:
		return err
	for key: Variant in session.world.chunk_blobs.keys():
		var f := FileAccess.open(tmp_dir.path_join("chunks").path_join(blob_file_name(str(key))), FileAccess.WRITE)
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


## Why the last load_session() failed, for the menu ("" after a success).
static var last_error: String = ""


## Loads and migrates a slot. Returns null on failure (reason in last_error and the Log).
static func load_session(slot: String) -> GameSession:
	var dir: String = slot_dir(slot)
	var data: Variant = _read_json(dir.path_join("session.json"))
	if not data is Dictionary and data_is_readable(dir + ".old"):
		# Interrupted swap or a damaged write: the previous save is still whole.
		Log.warn(&"save", "slot '%s' is damaged; loading its previous save" % slot)
		dir += ".old"
		data = _read_json(dir.path_join("session.json"))
	if not data is Dictionary:
		last_error = "the save is missing or damaged"
		Log.error(&"save", "slot '%s' has no readable session.json" % slot)
		return null
	var migrated: Dictionary = migrate(data)
	if migrated.is_empty():
		last_error = "the save is from a newer version of the game" if int((data as Dictionary).get("save_version", 0)) > CURRENT_VERSION \
			else "the save could not be upgraded"
		return null
	var session: GameSession = GameSession.from_dict(migrated.get("session", {}))
	var chunk_dir: String = dir.path_join("chunks")
	if DirAccess.dir_exists_absolute(chunk_dir):
		for f: String in DirAccess.get_files_at(chunk_dir):
			if f.ends_with(".bin"):
				session.world.chunk_blobs[blob_key(f)] = FileAccess.get_file_as_bytes(chunk_dir.path_join(f))
	last_error = ""
	return session


static func data_is_readable(dir: String) -> bool:
	return _read_json(dir.path_join("session.json")) is Dictionary


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
	var dirs: PackedStringArray = DirAccess.get_directories_at(SAVE_ROOT)
	for d: String in dirs:
		if d.ends_with(".tmp"):
			continue
		# A lone .old (the swap was interrupted) still lists, under its slot's name.
		if d.ends_with(".old") and dirs.has(d.trim_suffix(".old")):
			continue
		var meta: Variant = _read_json(SAVE_ROOT.path_join(d).path_join("meta.json"))
		if meta is Dictionary:
			out.append(meta)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.get("saved_unix", 0)) > int(b.get("saved_unix", 0)))
	return out


static func delete_slot(slot: String) -> void:
	_remove_recursive(slot_dir(slot))
	_remove_recursive(slot_dir(slot) + ".old")
	_remove_recursive(slot_dir(slot) + ".tmp")


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
	# A JSON instance reports a damaged file as a return code instead of an engine error.
	var j := JSON.new()
	if j.parse(FileAccess.get_file_as_string(path)) != OK:
		return null
	return j.data


static func _remove_recursive(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return
	for f: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(f))
	for d: String in DirAccess.get_directories_at(path):
		_remove_recursive(path.path_join(d))
	DirAccess.remove_absolute(path)
