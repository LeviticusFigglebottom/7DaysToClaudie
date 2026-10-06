class_name WildlifeDef
extends ContentDef
## A wild animal or bird flock (ADR-0027, data/wildlife/*.json). WildlifeManager spawns them
## deterministically around the player by biome and time of day; WildlifeBrain decides when they
## look up, bolt or flush.
##
##  * kind `grazer`: a herd of deer or a lone hare. `models` {model id: weight} (a buck among the
##    does); `speed` {walk, trot, flee} m/s and `anim_speed` {walk, trot, gallop}: the speed each
##    locomotion action shows at playback 1.0. Shot or struck down it leaves a carcass to butcher
##    (`carcass`), which bleeds scent the Hollowed follow.
##  * kind `flock`: songbirds or crows drawn as instances (`model` holds a `fly` and a `perch`
##    mesh). `perch` canopy (tree crowns) / ground. A flush is a sound the Hollowed hear
##    (`flush_loudness` metres): birds give your position away. Crows `circle` over what flushed
##    them, calling, before they settle again.
## `biomes` {biome id: weight} scales `density` (groups per km² at weight 1) per biome; `edge` is
## the multiplier where another biome lies within 40 m (deer at the forest's edge); `activity`
## {dawn, day, dusk, night} scales it by the time of day.
## `murmur` (crows, ADR-0034): the chance a flock you flush turns into a Murmur that follows you
## and marks you for the Hollowed (see BirdFlock and data/wildlife/birds.json for its keys).

const KINDS: PackedStringArray = ["grazer", "flock"]
const PERIODS: PackedStringArray = ["dawn", "day", "dusk", "night"]

var wkind: String = "grazer"
## Grazer models {model id ("animals/<id>"): weight}.
var models: Dictionary = {}
## Flock model ("animals/<id>": a glb with `fly` and `perch` meshes).
var model: String = ""
var biomes: Dictionary = {}
var density: float = 1.0
var edge: float = 1.0
var activity: Dictionary = {"dawn": 1.0, "day": 1.0, "dusk": 1.0, "night": 1.0}
var group: Vector2i = Vector2i(1, 1)
var speed: Dictionary = {"walk": 1.2, "trot": 3.0, "flee": 10.0}
var anim_speed: Dictionary = {"walk": 1.2, "trot": 3.0, "gallop": 10.0}
## sight / smell (m), hearing (multiplier), alert / flee distance from a person (m), flee distance
## from an awake Hollowed (m), and the loudness (m) of a sound that bolts it wherever it came from.
var senses: Dictionary = {}
var health: float = 50.0
var head_mult: float = 2.0
## {yields {item: [min, max]}, tools [tool kinds], time s, scent per s, lifetime s}.
var carcass: Dictionary = {}
## Sound ids: alarm, hurt, death, call (flocks: call, alarm, flush).
var sounds: Dictionary = {}
## Loudness (m) of the stimulus a bolting herd's alarm makes (0 = silent to the Hollowed).
var alarm_loudness: float = 0.0
var beds_at_night: bool = true
var size: Vector2 = Vector2(1.0, 1.0)
# Flocks.
var perch: String = "ground"
var flush_radius: float = 15.0
var flush_loudness: float = 40.0
var circle_seconds: float = 0.0
var return_seconds: float = 60.0
var fly_speed: float = 8.0
## Murmur tuning (empty: this flock never marks anyone).
var murmur: Dictionary = {}


func _fields() -> PackedStringArray:
	return ["kind", "models", "model", "biomes", "density", "edge", "activity", "group", "speed", "anim_speed", "senses",
		"health", "head_mult", "carcass", "sounds", "alarm_loudness", "beds_at_night", "size", "perch", "flush_radius",
		"flush_loudness", "circle_seconds", "return_seconds", "fly_speed", "murmur"]


func _parse(r: DefReader) -> void:
	wkind = r.enum_str("kind", KINDS, "grazer")
	models = r.dict("models")
	model = r.str_field("model", "")
	biomes = r.dict("biomes")
	density = r.num("density", 1.0)
	edge = r.num("edge", 1.0)
	var act: Dictionary = r.dict("activity")
	for k: Variant in act.keys():
		if not PERIODS.has(str(k)):
			r.err("activity.%s: one of %s" % [k, ", ".join(PERIODS)])
		activity[str(k)] = float(act[k])
	var g: Vector2 = r.range2("group", Vector2(1, 1))
	group = Vector2i(int(g.x), int(g.y))
	for k: Variant in r.dict("speed").keys():
		speed[str(k)] = float(r.dict("speed")[k])
	for k: Variant in r.dict("anim_speed").keys():
		anim_speed[str(k)] = float(r.dict("anim_speed")[k])
	senses = r.dict("senses")
	health = r.num("health", 50.0)
	head_mult = r.num("head_mult", 2.0)
	carcass = r.dict("carcass")
	sounds = r.dict("sounds")
	alarm_loudness = r.num("alarm_loudness", 0.0)
	beds_at_night = r.boolean("beds_at_night", true)
	size = r.range2("size", Vector2(1.0, 1.0))
	perch = r.enum_str("perch", ["canopy", "ground"], "ground")
	flush_radius = r.num("flush_radius", 15.0)
	flush_loudness = r.num("flush_loudness", 40.0)
	circle_seconds = r.num("circle_seconds", 0.0)
	return_seconds = r.num("return_seconds", 60.0)
	fly_speed = r.num("fly_speed", 8.0)
	murmur = r.dict("murmur")
	if wkind == "grazer" and models.is_empty():
		r.err("a grazer needs models {model id: weight}")
	if wkind == "flock" and model == "":
		r.err("a flock needs a model")
	if biomes.is_empty():
		r.err("wildlife needs biomes {biome id: weight}")
	if group.x < 1 or group.y < group.x:
		r.err("group must be [min >= 1, max >= min]")


func _validate(db: Node, out: PackedStringArray) -> void:
	for b: Variant in biomes.keys():
		if not db.has_def(&"biome", StringName(str(b))):
			out.append("%s: biome '%s' unknown" % [ctx(), b])
	for m: Variant in models.keys():
		if not str(m).begins_with("animals/"):
			out.append("%s: model '%s' must be an animal model (animals/<id>)" % [ctx(), m])
	for it: Variant in (carcass.get("yields", {}) as Dictionary).keys():
		if not db.has_def(&"item", StringName(str(it))):
			out.append("%s: carcass yield '%s' unknown" % [ctx(), it])


## Senses with defaults.
func sense(key: String, default: float) -> float:
	return float(senses.get(key, default))


## The model a grazer wears, picked by weight from a deterministic roll in [0, 1).
func pick_model(roll: float) -> String:
	var total: float = 0.0
	for k: Variant in models.keys():
		total += float(models[k])
	var acc: float = 0.0
	var keys: Array = models.keys()
	keys.sort()
	for k: Variant in keys:
		acc += float(models[k]) / maxf(total, 1e-6)
		if roll < acc:
			return str(k)
	return str(keys.back()) if not keys.is_empty() else ""
