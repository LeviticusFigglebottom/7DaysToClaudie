@tool
class_name ContentDB
extends Node
## Content database (autoload `Content`).
##
## Loads every JSON definition under each registered *content pack* (base pack = res://data),
## builds typed ContentDef objects, then validates cross references. Adding content never
## requires code changes: drop a JSON file in the right folder (see CLAUDE.md "How to add ...").
##
## Packs: regions/expansions can ship their own `data/` folder and register it with
## `add_pack()` before `load_all()`; later packs may add new ids but not silently override
## (overrides must set "_override": true).

## The live autoload, readable from worker threads (scene-tree lookups are main-thread only).
static var instance: Node = null

const KINDS: Dictionary = {
	&"item": {"dir": "items", "script": preload("res://src/core/content/defs/item_def.gd")},
	&"recipe": {"dir": "recipes", "script": preload("res://src/core/content/defs/recipe_def.gd")},
	&"station": {"dir": "stations", "script": preload("res://src/core/content/defs/station_def.gd")},
	&"loot_table": {"dir": "loot/tables", "script": preload("res://src/core/content/defs/loot_table_def.gd")},
	&"container": {"dir": "loot/containers", "script": preload("res://src/core/content/defs/container_def.gd")},
	&"enemy": {"dir": "enemies", "script": preload("res://src/core/content/defs/enemy_def.gd")},
	&"structure": {"dir": "structures", "script": preload("res://src/core/content/defs/structure_def.gd")},
	&"blueprint": {"dir": "blueprints", "script": preload("res://src/core/content/defs/blueprint_def.gd")},
	&"attribute": {"dir": "progression/attributes", "script": preload("res://src/core/content/defs/attribute_def.gd")},
	&"perk": {"dir": "progression/perks", "script": preload("res://src/core/content/defs/perk_def.gd")},
	&"directive": {"dir": "progression/directives", "script": preload("res://src/core/content/defs/directive_def.gd")},
	&"species": {"dir": "vegetation", "script": preload("res://src/core/content/defs/species_def.gd")},
	&"biome": {"dir": "biomes", "script": preload("res://src/core/content/defs/biome_def.gd")},
	&"weather": {"dir": "weather", "script": preload("res://src/core/content/defs/weather_def.gd")},
	&"note": {"dir": "notes", "script": preload("res://src/core/content/defs/note_def.gd")},
	&"poi": {"dir": "pois/buildings", "script": preload("res://src/core/content/defs/poi_def.gd")},
	&"framework": {"dir": "pois/frameworks", "script": preload("res://src/core/content/defs/framework_def.gd")},
	&"quest": {"dir": "quests", "script": preload("res://src/core/content/defs/quest_def.gd")},
	&"prop": {"dir": "props", "script": preload("res://src/core/content/defs/prop_def.gd")},
	&"population": {"dir": "populations", "script": preload("res://src/core/content/defs/population_def.gd")},
}

const BASE_PACK: String = "res://data"

signal content_loaded(error_count: int)

var _packs: PackedStringArray = [BASE_PACK]
## kind -> { id -> ContentDef }
var _defs: Dictionary = {}
## name -> Dictionary  (data/config/*.json)
var _configs: Dictionary = {}
var _errors: PackedStringArray = []
var _loaded: bool = false


func _ready() -> void:
	instance = self
	load_all()


func add_pack(path: String) -> void:
	if not _packs.has(path):
		_packs.append(path)


func is_loaded() -> bool:
	return _loaded


## Loads (or reloads) everything. Returns the list of errors (empty = all good).
func load_all() -> PackedStringArray:
	_defs.clear()
	_configs.clear()
	_errors.clear()
	for kind: StringName in KINDS:
		_defs[kind] = {}
	for pack: String in _packs:
		_load_pack(pack)
	_validate_all()
	_loaded = true
	if _errors.is_empty():
		Log.info(&"content", "loaded %s" % summary())
	else:
		for e: String in _errors:
			Log.error(&"content", e)
	content_loaded.emit(_errors.size())
	return _errors


func errors() -> PackedStringArray:
	return _errors


func summary() -> String:
	var parts: PackedStringArray = []
	for kind: StringName in KINDS:
		var n: int = (_defs[kind] as Dictionary).size()
		if n > 0:
			parts.append("%d %s" % [n, kind])
	parts.append("%d configs" % _configs.size())
	return ", ".join(parts)


# --- Lookup ----------------------------------------------------------------------------------

func get_def(kind: StringName, id: StringName) -> ContentDef:
	var table: Dictionary = _defs.get(kind, {})
	return table.get(id, null)


func has_def(kind: StringName, id: StringName) -> bool:
	return (_defs.get(kind, {}) as Dictionary).has(id)


func all(kind: StringName) -> Array:
	var table: Dictionary = _defs.get(kind, {})
	var out: Array = table.values()
	out.sort_custom(func(a: ContentDef, b: ContentDef) -> bool: return String(a.id) < String(b.id))
	return out


func ids(kind: StringName) -> Array[StringName]:
	var out: Array[StringName] = []
	for k: StringName in (_defs.get(kind, {}) as Dictionary).keys():
		out.append(k)
	out.sort()
	return out


func with_tag(kind: StringName, tag: String) -> Array:
	return all(kind).filter(func(d: ContentDef) -> bool: return d.has_tag(tag))


func item(id: StringName) -> ItemDef:
	return get_def(&"item", id) as ItemDef


func recipe(id: StringName) -> RecipeDef:
	return get_def(&"recipe", id) as RecipeDef


func loot_table(id: StringName) -> LootTableDef:
	return get_def(&"loot_table", id) as LootTableDef


func enemy(id: StringName) -> EnemyDef:
	return get_def(&"enemy", id) as EnemyDef


func structure(id: StringName) -> StructureDef:
	return get_def(&"structure", id) as StructureDef


## Raw config dictionary from data/config/<name>.json ({} if missing).
func config(name: StringName) -> Dictionary:
	return _configs.get(name, {})


## Typed config value with a default, e.g. Content.cfg(&"world_clock", "day_length_minutes", 40.0)
func cfg(name: StringName, key: String, default: Variant) -> Variant:
	var c: Dictionary = config(name)
	return c.get(key, default)


# --- Loading ---------------------------------------------------------------------------------

func _load_pack(pack: String) -> void:
	if not DirAccess.dir_exists_absolute(pack):
		_errors.append("content pack '%s' does not exist" % pack)
		return
	for kind: StringName in KINDS:
		var info: Dictionary = KINDS[kind]
		var dir_path: String = pack.path_join(info["dir"])
		for file: String in _list_json(dir_path):
			_load_def_file(kind, info["script"], file, pack)
	for file: String in _list_json(pack.path_join("config")):
		var data: Variant = _read_json(file)
		if data is Dictionary:
			_configs[StringName(file.get_file().get_basename())] = data


func _load_def_file(kind: StringName, script: Script, file: String, pack: String) -> void:
	var data: Variant = _read_json(file)
	if data == null:
		return
	var rel: String = file.trim_prefix(pack + "/")
	var entries: Array = []
	if data is Array:
		entries = data
	elif data is Dictionary and (data as Dictionary).has("defs"):
		entries = data["defs"]
	elif data is Dictionary:
		entries = [data]
	for entry: Variant in entries:
		if not entry is Dictionary:
			_errors.append("%s: every def must be a JSON object" % rel)
			continue
		var def: ContentDef = script.new()
		var errs: PackedStringArray = def.parse(entry, kind, rel)
		_errors.append_array(errs)
		if def.id == &"":
			continue
		var table: Dictionary = _defs[kind]
		if table.has(def.id) and not (entry as Dictionary).get("_override", false):
			_errors.append("%s: duplicate %s id '%s' (also in %s)" % [rel, kind, def.id, (table[def.id] as ContentDef).source])
			continue
		table[def.id] = def


func _validate_all() -> void:
	for kind: StringName in KINDS:
		for def: ContentDef in (_defs[kind] as Dictionary).values():
			def._validate(self, _errors)


func _read_json(path: String) -> Variant:
	var text: String = FileAccess.get_file_as_string(path)
	if text.is_empty():
		_errors.append("%s: empty or unreadable" % path)
		return null
	var json := JSON.new()
	var err: int = json.parse(text)
	if err != OK:
		_errors.append("%s:%d: JSON parse error: %s" % [path, json.get_error_line(), json.get_error_message()])
		return null
	return json.data


static func _list_json(dir_path: String) -> PackedStringArray:
	var out: PackedStringArray = []
	if not DirAccess.dir_exists_absolute(dir_path):
		return out
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	for f: String in dir.get_files():
		if f.ends_with(".json"):
			out.append(dir_path.path_join(f))
	for sub: String in dir.get_directories():
		out.append_array(_list_json(dir_path.path_join(sub)))
	out.sort()
	return out
