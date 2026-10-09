class_name SaveSystem
extends RefCounted
## Versioned, migration-capable, chunk-based saves (ADR-0005).
##
## Layout of a slot (user://saves/<slot>/):
##   meta.json        small summary for the load menu (version, day, play time, ...)
##   session.json     GameSession.to_dict() wrapped as {save_version, session}
##   chunks/<k>.bin   per-chunk binary blobs (terrain height deltas, volume densities); a key's
##                    ':' is written as '~' (Windows forbids ':' in file names), both read back
##   world-<id>.zip   a random world's own files (v7, the world bundle): world.json, regions/,
##                    frameworks.json and meta.json from user://worlds/random/<id>/, restored from
##                    here when that folder is gone (deleted by hand, a save copied to another
##                    machine), so the run keeps the world it was played in (TD-082)
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
const CURRENT_VERSION: int = 7


## from_version -> Callable(Dictionary) -> Dictionary
static func _builtin_migrations() -> Dictionary:
	return {
		1: _drop_harvested_plants,
		2: _v2_to_v3,
		3: _v3_to_v4,
		4: _v4_to_v5,
		5: _v5_to_v6,
		6: _v6_to_v7,
	}


## 6 -> 7: a random run records the generator version that made its world (TD-140) and where its
## files live (RWG v2 §5). The world id hashes the version, so it is recovered from the id; a world
## id no version reproduces gets 1 (every v6 world was made by generator 1 to 5, and none since).
## Main-map saves change only in their version. The bump also keeps a v6 build from loading a
## streamed run. `world.traders` and `players[*].contracts` (traders, ADR-0039) carry through as
## they are: both load empty from an older save.
static func _v6_to_v7(d: Dictionary) -> Dictionary:
	var session: Dictionary = d.get("session", {})
	var gen: Variant = session.get("world_gen", {})
	if str(session.get("world_mode", "")) == "random" and gen is Dictionary and not (gen as Dictionary).is_empty() \
			and not session.has("generator_version"):
		var settings: RefCounted = (load("res://src/worldgen/rwg/world_gen_settings.gd") as GDScript).call(&"from_dict", gen)
		var v: int = int((load("res://src/worldgen/rwg/rwg_generator.gd") as GDScript).call(&"version_of", str(session.get("world_id", "")), settings))
		session["generator_version"] = v if v > 0 else 1
	if not session.has("world_files"):
		session["world_files"] = "shared"
	d["session"] = session
	return d


## 5 -> 6: a run records which world it is played in (ADR-0031): the handcrafted map or a random
## world's generator settings (GameSession.world_gen). Every older run is on the main map. The bump
## also stops an older build from loading a random-world run as if it were the main map.
static func _v5_to_v6(d: Dictionary) -> Dictionary:
	var session: Dictionary = d.get("session", {})
	if not session.has("world_gen"):
		session["world_gen"] = {}
	if str(session.get("world_mode", "")) == "":
		session["world_mode"] = "main_map"
	d["session"] = session
	return d


## 4 -> 5: buildings are dressed per run (ADR-0030): their alternatives, wear, scatter and decals
## follow the world seed. A run saved before that was played in the authored buildings with the
## instance-id scatter, so it keeps them: its world is marked legacy dressing (WorldState.poi_dressing).
static func _v4_to_v5(d: Dictionary) -> Dictionary:
	var session: Dictionary = d.get("session", {})
	var world: Dictionary = session.get("world", {})
	world["poi_dressing"] = 1
	session["world"] = world
	d["session"] = session
	return d


## 3 -> 4: the world keeps the fungal mounds Hum survivors leave where they rooted (ADR-0025). Older
## saves have none yet.
static func _v3_to_v4(d: Dictionary) -> Dictionary:
	var session: Dictionary = d.get("session", {})
	var world: Dictionary = session.get("world", {})
	if not world.has("mounds"):
		world["mounds"] = {}
	session["world"] = world
	d["session"] = session
	return d


## 2 -> 3: POI piece ids (ADR-0018) and the riverbank biome's new scatter.
## * POI piece states (containers, sleepers, traps, pickups) are keyed by authored ids now, no
##   longer by their position in the POI's lists (TD-031); see _mark_poi_keys_legacy.
## * The riverbank biome's medium/ground scatter changed, so harvested-plant instance indices
##   point at other plants again: their records are dropped as in 1 -> 2 (stumps stay).
static func _v2_to_v3(d: Dictionary) -> Dictionary:
	return _drop_harvested_plants(_mark_poi_keys_legacy(d))


## Which ids the old list positions map to depends on each building's layout, which only exists
## once the world is built, so every POI state is tagged as legacy ("keys": 1) and PoiInstance
## re-keys it from its layout the first time the building is built (every POI is built at world
## load).
static func _mark_poi_keys_legacy(d: Dictionary) -> Dictionary:
	var world: Dictionary = (d.get("session", {}) as Dictionary).get("world", {})
	var pois: Dictionary = world.get("pois", {})
	for k: Variant in pois.keys():
		if pois[k] is Dictionary and not (pois[k] as Dictionary).has("keys"):
			(pois[k] as Dictionary)["keys"] = 1
	return d


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


## Files other systems keep in a slot that a save carries over (the Load screen's thumbnail and card).
const SLOT_EXTRAS: PackedStringArray = ["thumb.webp", "card.json"]


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
	# The Load screen's card (Presentation's GameUI writes them after each save): carried over, so a
	# slot never shows without its picture between the swap and the next write.
	for extra: String in SLOT_EXTRAS:
		if FileAccess.file_exists(final_dir.path_join(extra)):
			DirAccess.copy_absolute(final_dir.path_join(extra), tmp_dir.path_join(extra))
	err = _carry_world_bundle(session, final_dir, tmp_dir)
	if err != OK:
		Log.warn(&"save", "could not bundle world %s into slot '%s' (%s); the save itself is fine" % [session.world_id, slot, error_string(err)])
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
	if session.is_random_world() and _restore_world_bundle(String(session.world_id), dir):
		session.world_files = &"slot"
	var chunk_dir: String = dir.path_join("chunks")
	if DirAccess.dir_exists_absolute(chunk_dir):
		for f: String in DirAccess.get_files_at(chunk_dir):
			if f.ends_with(".bin"):
				session.world.chunk_blobs[blob_key(f)] = FileAccess.get_file_as_bytes(chunk_dir.path_join(f))
	last_error = ""
	return session


# --- Composer changes under an existing run (TD-182) --------------------------------------------

## Composer version from which random worlds' towns paint `town` only on their streets (ADR-0047):
## the vegetation scatter in town chunks changed, so per-instance records there point elsewhere.
const TOWN_PAINT_COMPOSER: int = 12


## Brings a loaded run's saved state in line with the composer that now composes its world: a
## random run composed before TOWN_PAINT_COMPOSER loses its felled-tree and harvested-plant
## records in the 64 m vegetation chunks touching a town (they are addressed by scatter index,
## which now names other instances; the trees there simply stand again). Records the current
## version. Then, crossing BANKS_COMPOSER, any run loses those records by the roads, pads and towns
## whose ground and plants that composer changed (_drop_bank_chunks). Returns how many chunks were
## dropped. `world_def`: the WorldDef being played (its `towns`, `roads` and regions).
static func fix_composer_changes(session: GameSession, world_def: Object, current: int) -> int:
	var dropped: int = 0
	if session.is_random_world() and session.composer_version < TOWN_PAINT_COMPOSER and current >= TOWN_PAINT_COMPOSER and world_def != null:
		dropped += _drop_town_chunks(session, world_def, current)
	if session.composer_version < BANKS_COMPOSER and current >= BANKS_COMPOSER and world_def != null:
		dropped += _drop_bank_chunks(session, world_def)
	# Composer 14 moved the ground at a town's street junctions (TD-318): the town chunks again (a
	# run already dropped them on the way through 12 has nothing there left to drop).
	if session.is_random_world() and session.composer_version >= TOWN_PAINT_COMPOSER and session.composer_version < JUNCTIONS_COMPOSER \
			and current >= JUNCTIONS_COMPOSER and world_def != null:
		dropped += _drop_town_chunks(session, world_def, current)
	# Composer 15 moved the ground where roads meet (world roads pinned to each other; the nearest
	# road is the nearest edge, so bulbs and wide roads keep their width where a narrow one meets
	# them): any run drops the records by its roads again (a run crossing 13 just did).
	if session.composer_version >= BANKS_COMPOSER and session.composer_version < ROAD_EDGE_COMPOSER \
			and current >= ROAD_EDGE_COMPOSER and world_def != null:
		dropped += _drop_bank_chunks(session, world_def)
	session.composer_version = current
	return dropped


## Composer version from which a world town's streets are pinned together at their junctions.
const JUNCTIONS_COMPOSER: int = 14
## Composer version from which world roads meet at one height and the nearest road is the nearest edge.
const ROAD_EDGE_COMPOSER: int = 15


## Drops the felled-tree and harvested-plant records of the 64 m chunks touching a town.
static func _drop_town_chunks(session: GameSession, world_def: Object, current: int) -> int:
	var dropped: int = 0
	var towns: Array = world_def.get(&"towns")
	var margin: float = 20.0
	for key: String in session.world.trees.keys():
		var c: Vector2i = Ids.parse_chunk_key(key)
		var r := Rect2(c.x * 64.0, c.y * 64.0, 64.0, 64.0)
		for tw: Dictionary in towns:
			var near: Vector2 = (tw["center"] as Vector2).clamp(r.position, r.end)
			if (tw["bounds"] as Rect2).grow(margin).intersects(r) and near.distance_to(tw["center"]) <= float(tw["radius"]) + margin:
				session.world.trees.erase(key)
				dropped += 1
				break
	if dropped > 0:
		Log.info(&"save", "composer %d -> %d: dropped vegetation records in %d town chunks (TD-182)" % [session.composer_version, current, dropped])
	return dropped


## Composer version from which a generated world's roads and every pad meet the land in natural
## banks, and towns' yards and frameworks grow plants (player report 4): the ground and the
## vegetation scatter changed beside those roads, round those pads and over those towns.
const BANKS_COMPOSER: int = 13
## How far round a changed road (its centre line) and a changed pad (its bounding circle) a
## 64 m chunk's records are dropped (the bank reaches 26-30 m past the road's edge, 18 m past a pad).
const BANKS_ROAD_REACH: float = 40.0
const BANKS_PAD_REACH: float = 30.0


## Drops the vegetation records of the chunks the VERSION 13 banks and yards changed: near a
## generated world's roads (the main map's are graded as before), round every pad but those that
## keep their water, and over every organic town. Returns how many chunks were dropped.
static func _drop_bank_chunks(session: GameSession, world_def: Object) -> int:
	# Circles (Vector3: x, z, radius) and polylines with their reach, in world metres.
	var circles: Array[Vector3] = []
	var lines: Array = []
	if "towns" in world_def:
		for tw: Dictionary in world_def.get(&"towns"):
			var b: Rect2 = tw["bounds"]
			circles.append(Vector3(b.get_center().x, b.get_center().y, b.size.length() * 0.5 + BANKS_PAD_REACH))
	if session.is_random_world() and "roads" in world_def:
		for rd: Dictionary in world_def.get(&"roads"):
			lines.append(rd["line"])
	if "regions" in world_def and world_def.has_method(&"region_data"):
		var db: Node = ContentDB.instance
		for rid: Variant in (world_def.get(&"regions") as Dictionary).keys():
			for f: Variant in (world_def.call(&"region_data", str(rid)) as Dictionary).get("features", []):
				var fd: Dictionary = f
				var kind: String = str(fd.get("type", ""))
				if not kind in ["framework", "poi"] or bool(fd.get("keep_water", false)) or not fd.has("origin"):
					continue
				var size := Vector2(40, 40)
				var def: Object = null
				if db != null:
					def = db.call(&"get_def", StringName(kind), StringName(str(fd.get(kind, ""))))
				if def is FrameworkDef:
					size = Vector2((def as FrameworkDef).size)
				elif def is PoiDef:
					size = Vector2((def as PoiDef).footprint)
				var o := Vector2(float(fd["origin"][0]), float(fd["origin"][1]))
				var half: Vector2 = (size * 0.5).rotated(deg_to_rad(float(fd.get("rotation", 0.0))))
				circles.append(Vector3(o.x + half.x, o.y + half.y, size.length() * 0.5 + float(fd.get("skirt", 10.0)) + BANKS_PAD_REACH))
	var dropped: int = 0
	var chunk_r: float = 32.0 * sqrt(2.0)
	for key: String in session.world.trees.keys():
		var c: Vector2i = Ids.parse_chunk_key(key)
		var mid := Vector2(c.x * 64.0 + 32.0, c.y * 64.0 + 32.0)
		var hit: bool = false
		for cv: Vector3 in circles:
			if mid.distance_to(Vector2(cv.x, cv.y)) < cv.z + chunk_r:
				hit = true
				break
		if not hit:
			for ln: Variant in lines:
				var line: Polyline2 = ln
				if line.bounds.grow(BANKS_ROAD_REACH + chunk_r).has_point(mid) and line.closest(mid).x < BANKS_ROAD_REACH + chunk_r:
					hit = true
					break
		if hit:
			session.world.trees.erase(key)
			dropped += 1
	if dropped > 0:
		Log.info(&"save", "composer %d -> %d: dropped vegetation records in %d chunks by roads, pads and towns (TD-182)" % [session.composer_version, BANKS_COMPOSER, dropped])
	return dropped


# --- The world bundle (save v7, RWG v2 §5) ------------------------------------------------------

const WORLDS_ROOT: String = "user://worlds/random"
## Files of a world folder left out of its bundle (remade from the rest).
const BUNDLE_SKIP: PackedStringArray = ["map.png"]


static func bundle_name(world_id: String) -> String:
	return "world-%s.zip" % world_id


## A random run's slot gets its world's files once: copied from the previous save of the slot when
## it has them, else zipped from the world's folder. Main-map runs have none.
static func _carry_world_bundle(session: GameSession, final_dir: String, tmp_dir: String) -> Error:
	if not session.is_random_world():
		return OK
	var name: String = bundle_name(String(session.world_id))
	var prev: String = final_dir.path_join(name)
	if FileAccess.file_exists(prev):
		return DirAccess.copy_absolute(prev, tmp_dir.path_join(name))
	var src: String = WORLDS_ROOT.path_join(String(session.world_id))
	if not FileAccess.file_exists(src.path_join("world.json")):
		return ERR_FILE_NOT_FOUND
	return bundle(src, tmp_dir.path_join(name))


## Zips a world folder (every file but BUNDLE_SKIP, paths relative to it) into `zip_path`.
static func bundle(dir: String, zip_path: String) -> Error:
	var zp := ZIPPacker.new()
	var err: Error = zp.open(zip_path)
	if err != OK:
		return err
	for rel: String in _files_under(dir, ""):
		if BUNDLE_SKIP.has(rel):
			continue
		err = zp.start_file(rel)
		if err == OK:
			err = zp.write_file(FileAccess.get_file_as_bytes(dir.path_join(rel)))
		zp.close_file()
		if err != OK:
			zp.close()
			return err
	return zp.close()


## Unzips a bundle into `dir` (through a .tmp folder swapped in at the end).
static func unbundle(zip_path: String, dir: String) -> Error:
	var zr := ZIPReader.new()
	var err: Error = zr.open(zip_path)
	if err != OK:
		return err
	var tmp: String = dir + ".tmp"
	_remove_recursive(tmp)
	for rel: String in zr.get_files():
		if rel.ends_with("/") or rel.begins_with("/") or rel.contains(".."):
			continue
		var out: String = tmp.path_join(rel)
		DirAccess.make_dir_recursive_absolute(out.get_base_dir())
		var f := FileAccess.open(out, FileAccess.WRITE)
		if f == null:
			zr.close()
			return FileAccess.get_open_error()
		f.store_buffer(zr.read_file(rel))
		f.close()
	zr.close()
	if not FileAccess.file_exists(tmp.path_join("world.json")):
		_remove_recursive(tmp)
		return ERR_FILE_CORRUPT
	_remove_recursive(dir)
	return DirAccess.rename_absolute(tmp, dir)


## Restores a run's world folder from its slot's bundle when the folder is gone. True if it did.
static func _restore_world_bundle(world_id: String, slot_path: String) -> bool:
	var dir: String = WORLDS_ROOT.path_join(world_id)
	var zip: String = slot_path.path_join(bundle_name(world_id))
	if FileAccess.file_exists(dir.path_join("world.json")) or not FileAccess.file_exists(zip):
		return false
	DirAccess.make_dir_recursive_absolute(WORLDS_ROOT)
	var err: Error = unbundle(zip, dir)
	if err != OK:
		Log.warn(&"save", "could not restore world %s from its save (%s)" % [world_id, error_string(err)])
		return false
	Log.info(&"save", "restored world %s from its save" % world_id)
	return true


## What the load menu should say about a slot's world ("" when nothing): a random run whose world
## folder and bundle are both gone is remade by the current generator, which differs when the
## generator has moved on since.
static func world_warning(meta: Dictionary) -> String:
	if str(meta.get("world_mode", "")) != "random":
		return ""
	var wid: String = str(meta.get("world_id", ""))
	if FileAccess.file_exists(WORLDS_ROOT.path_join(wid).path_join("world.json")):
		return ""
	var slot: String = str(meta.get("slot", ""))
	if slot != "" and (FileAccess.file_exists(slot_dir(slot).path_join(bundle_name(wid))) or FileAccess.file_exists((slot_dir(slot) + ".old").path_join(bundle_name(wid)))):
		return ""
	return "This run's world is no longer on this computer; loading it makes a new world from the same settings."


static func _files_under(root: String, rel: String) -> PackedStringArray:
	var out := PackedStringArray()
	var here: String = root.path_join(rel) if rel != "" else root
	for f: String in DirAccess.get_files_at(here):
		out.append(rel.path_join(f) if rel != "" else f)
	for d: String in DirAccess.get_directories_at(here):
		out.append_array(_files_under(root, rel.path_join(d) if rel != "" else d))
	return out


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
