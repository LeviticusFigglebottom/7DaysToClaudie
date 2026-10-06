class_name WorldGenSettings
extends RefCounted
## The settings of a random world (ADR-0031): a map seed plus every option of
## data/config/world_gen.json, resolved once from option defaults <- preset <- the player's
## overrides, coerced and clamped to the schema (like GameRules, ADR-0014). Saved with the session
## (GameSession.world_gen) so a loaded run regenerates, or reads from cache, the identical world:
## the world is a pure function of `key()` (seed, values and RwgGenerator.VERSION).
##
## The config is typed here: `schema_errors()` reports unknown keys, bad option specs, presets that
## name unknown options and tuning that names unknown POIs or frameworks (`make validate`).
## Worker-thread safe: content comes from ContentDB.instance, never the `Content` autoload.

const CONFIG: StringName = &"world_gen"
const CONFIG_PATH: String = "res://data/config/world_gen.json"
const TOP_KEYS: PackedStringArray = ["categories", "options", "presets", "tuning", "names"]
const OPTION_KEYS: PackedStringArray = ["category", "type", "min", "max", "step", "default", "label", "values"]
const OPTION_TYPES: PackedStringArray = ["int", "float", "enum"]
const PRESET_KEYS: PackedStringArray = ["label", "description", "values"]
const TUNING_KEYS: PackedStringArray = ["macro_step", "biome_step", "region_margin", "terrain", "rivers", "lakes", "towns", "roads", "wilderness", "drop_site", "bloom"]
const POOL_KEYS: PackedStringArray = ["poi", "site", "per_region", "max", "access", "biome", "min_danger", "keep_water", "skirt"]
## tuning.towns (organic towns, ADR-0040; the planner's own numbers are town_planner.json).
const TOWN_KEYS: PackedStringArray = ["mix", "spacing", "edge", "candidates", "core_relief", "disc_relief", "max_slope", "water", "score", "core_smoothing",
	"stub", "authored_max", "clearance"]
## The size classes a town-size mix may name (town_planner.json `kinds`).
const KIND_KEYS: PackedStringArray = ["hamlet", "village", "town"]
const SITES: PackedStringArray = ["summit", "forest", "waterside", "lake_shore", "remote", "roadside"]
const ACCESS: PackedStringArray = ["trail", "track", "drive"]
const NAME_KEYS: PackedStringArray = ["towns", "regions", "region_words", "lakes", "rivers"]

var preset: StringName = &"standard"
## Map seed: what the land, water, towns and places follow (the run seed, GameSession.world_seed,
## still drives loot, scatter, the Hum and how buildings are dressed and picked).
var seed: int = 0
var values: Dictionary = {}

static var _file_cache: Dictionary = {}


## The parsed config: ContentDB's copy when content is loaded, else read straight from disk (tools).
static func schema() -> Dictionary:
	var db: Node = ContentDB.instance
	if db != null:
		var c: Dictionary = db.call(&"config", CONFIG)
		if not c.is_empty():
			return c
	if _file_cache.is_empty():
		var j := JSON.new()
		if j.parse(FileAccess.get_file_as_string(CONFIG_PATH)) == OK and j.data is Dictionary:
			_file_cache = j.data
	return _file_cache


static func options() -> Dictionary:
	return schema().get("options", {})


static func tuning() -> Dictionary:
	return schema().get("tuning", {})


static func names() -> Dictionary:
	return schema().get("names", {})


static func presets() -> Dictionary:
	return schema().get("presets", {})


## Settings for a preset with the player's overrides (returns a WorldGenSettings).
static func resolve(preset_id: StringName, overrides: Dictionary = {}, p_seed: int = 0) -> RefCounted:
	# Loaded by path: this compiles before the editor registers the class name (ADR-0030's pattern).
	var s: Variant = (load("res://src/worldgen/rwg/world_gen_settings.gd") as GDScript).new()
	var opts: Dictionary = options()
	for k: String in opts:
		s.values[k] = GameRules.coerce(opts[k], (opts[k] as Dictionary).get("default"))
	var ps: Dictionary = presets()
	if not ps.has(String(preset_id)):
		preset_id = &"standard"
	s.preset = preset_id
	s._apply((ps.get(String(preset_id), {}) as Dictionary).get("values", {}))
	s._apply(overrides)
	s.seed = p_seed
	return s as RefCounted


## Sets known options, coerced and clamped to the schema; ignores unknown and `_` keys.
func _apply(d: Dictionary) -> void:
	var opts: Dictionary = options()
	for k: Variant in d.keys():
		var key: String = str(k)
		if key.begins_with("_") or not opts.has(key):
			continue
		values[key] = GameRules.coerce(opts[key], d[k])


func num(key: String) -> float:
	return float(values.get(key, 0.0))


func integer(key: String) -> int:
	return int(values.get(key, 0))


func choice(key: String) -> String:
	return str(values.get(key, ""))


## Options that differ from the preset (what the player customised).
func customised() -> Dictionary:
	var base_values: Dictionary = resolve(preset, {}, seed).get(&"values")
	var out: Dictionary = {}
	for k: String in values:
		if base_values.get(k) != values[k]:
			out[k] = values[k]
	return out


## Canonical text of everything the world depends on: sorted keys, fixed float formatting.
func key() -> String:
	var keys: Array = values.keys()
	keys.sort()
	var parts: PackedStringArray = ["seed=%d" % seed]
	for k: Variant in keys:
		var v: Variant = values[k]
		parts.append("%s=%s" % [k, ("%.4f" % float(v)) if v is float else str(v)])
	return "|".join(parts)


func to_dict() -> Dictionary:
	return {"preset": String(preset), "seed": str(seed), "values": values.duplicate()}


## Saved values win; options added since the save get their preset's value.
static func from_dict(d: Dictionary) -> RefCounted:
	var s: RefCounted = resolve(StringName(str(d.get("preset", "standard"))), {}, int(str(d.get("seed", "0"))))
	s.call(&"_apply", d.get("values", {}))
	return s


## One line for menus and logs: "4 x 4 km, rolling, 2 towns per 16 km² (mixed), seed 1234".
func summary() -> String:
	return "%d x %d km, %s, %s towns per 16 km² (%s), seed %d" % [integer("size"), integer("size"), choice("terrain"), String.num(num("town_density"), 2),
		choice("town_size"), seed]


# --- Schema checks (make validate, tests) -------------------------------------------------------

## Problems with data/config/world_gen.json: unknown keys at any level the generator reads, option
## specs, presets naming unknown options or out-of-range values, and pool entries naming unknown
## POIs, frameworks, sites or access kinds (`db`: ContentDB for those cross-references, may be null).
static func schema_errors(db: Node = null) -> PackedStringArray:
	var out: PackedStringArray = []
	var c: Dictionary = schema()
	if c.is_empty():
		out.append("world_gen.json: missing or unreadable")
		return out
	_unknown(c, TOP_KEYS, "world_gen.json", out)
	var opts: Dictionary = c.get("options", {})
	for k: String in opts:
		var spec: Dictionary = opts[k]
		_unknown(spec, OPTION_KEYS, "world_gen.json options.%s" % k, out)
		if not OPTION_TYPES.has(str(spec.get("type", ""))):
			out.append("world_gen.json options.%s: type must be one of %s" % [k, ", ".join(OPTION_TYPES)])
		if str(spec.get("type", "")) == "enum" and not (spec.get("values", []) as Array).has(spec.get("default")):
			out.append("world_gen.json options.%s: default is not one of its values" % k)
	for pid: String in c.get("presets", {}):
		var p: Dictionary = c["presets"][pid]
		_unknown(p, PRESET_KEYS, "world_gen.json presets.%s" % pid, out)
		for ok: Variant in (p.get("values", {}) as Dictionary).keys():
			if not opts.has(str(ok)):
				out.append("world_gen.json presets.%s: unknown option '%s'" % [pid, ok])
			elif GameRules.coerce(opts[str(ok)], p["values"][ok]) != p["values"][ok]:
				out.append("world_gen.json presets.%s: %s = %s is out of range" % [pid, ok, p["values"][ok]])
	var t: Dictionary = c.get("tuning", {})
	_unknown(t, TUNING_KEYS, "world_gen.json tuning", out)
	for tt: String in ["flat", "rolling", "hilly", "mountainous"]:
		if not (t.get("terrain", {}) as Dictionary).has(tt):
			out.append("world_gen.json tuning.terrain: no profile for '%s'" % tt)
	var towns: Dictionary = t.get("towns", {})
	_unknown(towns, TOWN_KEYS, "world_gen.json tuning.towns", out)
	for mix_id: Variant in (towns.get("mix", {}) as Dictionary).keys():
		if not (opts.get("town_size", {}) as Dictionary).get("values", []).has(str(mix_id)):
			out.append("world_gen.json tuning.towns.mix: '%s' is not a town_size value" % mix_id)
		for kind: Variant in ((towns["mix"] as Dictionary)[mix_id] as Dictionary).keys():
			if not KIND_KEYS.has(str(kind)):
				out.append("world_gen.json tuning.towns.mix.%s: '%s' is not a size class (%s)" % [mix_id, kind, ", ".join(KIND_KEYS)])
	for v: Variant in (opts.get("town_size", {}) as Dictionary).get("values", []):
		if not (towns.get("mix", {}) as Dictionary).has(str(v)):
			out.append("world_gen.json tuning.towns.mix: no mix for town_size '%s'" % v)
	var wild: Dictionary = t.get("wilderness", {})
	_unknown(wild, ["pool", "farmsteads", "spacing", "max_relief"], "world_gen.json tuning.wilderness", out)
	for e: Variant in wild.get("pool", []):
		var pe: Dictionary = e
		var where: String = "world_gen.json tuning.wilderness.pool[%s]" % pe.get("poi", "?")
		_unknown(pe, POOL_KEYS, where, out)
		if not SITES.has(str(pe.get("site", ""))):
			out.append("%s: site must be one of %s" % [where, ", ".join(SITES)])
		if not ACCESS.has(str(pe.get("access", ""))):
			out.append("%s: access must be one of %s" % [where, ", ".join(ACCESS)])
		if db != null and not bool(db.call(&"has_def", &"poi", StringName(str(pe.get("poi", ""))))):
			out.append("%s: unknown poi" % where)
		if db != null and pe.has("biome") and not bool(db.call(&"has_def", &"biome", StringName(str(pe["biome"])))):
			out.append("%s: unknown biome '%s'" % [where, pe["biome"]])
	var farm: Dictionary = wild.get("farmsteads", {})
	if db != null and not farm.is_empty() and not bool(db.call(&"has_def", &"framework", StringName(str(farm.get("framework", ""))))):
		out.append("world_gen.json tuning.wilderness.farmsteads: unknown framework '%s'" % farm.get("framework", ""))
	_unknown(c.get("names", {}), NAME_KEYS, "world_gen.json names", out)
	for nk: String in NAME_KEYS:
		if (c.get("names", {}) as Dictionary).get(nk, []).is_empty():
			out.append("world_gen.json names.%s: empty" % nk)
	return out


static func _unknown(d: Dictionary, known: PackedStringArray, where: String, out: PackedStringArray) -> void:
	for k: Variant in d.keys():
		var key: String = str(k)
		if not key.begins_with("_") and not known.has(key):
			out.append("%s: unknown key '%s' (%s)" % [where, key, ", ".join(known)])
