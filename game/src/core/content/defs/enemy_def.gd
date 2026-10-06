class_name EnemyDef
extends ContentDef
## An enemy archetype (Hollowed variants, animals, later Ashen tribe roles).

const ARCHETYPES: PackedStringArray = ["walker", "feral", "screamer", "crawler", "spitter", "armored", "breaker", "hound", "animal", "tribe"]
const FACTIONS: PackedStringArray = ["hollowed", "ashen", "wildlife"]

var archetype: String = "walker"
var faction: String = "hollowed"
## Body model ids (variants), e.g. ["characters/hollow_a", ...]
var bodies: PackedStringArray = []
var health: float = 100.0
## Limb hp: head, torso, arm_l, arm_r, leg_l, leg_r
var limbs: Dictionary = {}
## m/s: day_walk, day_run, night_walk, night_run
var speed: Dictionary = {}
## damage, range, cooldown, structure_damage, infection
var attack: Dictionary = {}
## sight_day, sight_night, fov, hearing, smell
var perception: Dictionary = {}
## scream, scream_radius, scream_cooldown, sleeper_poses, crawl_on_leg_loss
var behavior: Dictionary = {}
var xp: int = 10
var loot_table: StringName = &""
## Heat contributed while alive/active nearby (attention system).
var heat_value: float = 1.0
## Spawn gating by gamestage.
var gamestage_min: int = 0
var scale_range: Vector2 = Vector2(0.95, 1.05)


func _fields() -> PackedStringArray:
	return ["archetype", "faction", "bodies", "health", "limbs", "speed", "attack", "perception",
		"behavior", "xp", "loot_table", "heat_value", "gamestage_min", "scale"]


func _parse(r: DefReader) -> void:
	archetype = r.enum_str("archetype", ARCHETYPES, "walker")
	faction = r.enum_str("faction", FACTIONS, "hollowed")
	bodies = r.strings("bodies")
	health = r.num("health", 100.0)
	limbs = r.dict("limbs")
	speed = r.dict("speed")
	attack = r.dict("attack")
	perception = r.dict("perception")
	behavior = r.dict("behavior")
	xp = r.integer("xp", 10)
	loot_table = r.sname("loot_table")
	heat_value = r.num("heat_value", 1.0)
	gamestage_min = r.integer("gamestage_min", 0)
	scale_range = r.range2("scale", Vector2(0.95, 1.05))
	for k: String in ["day_walk", "night_walk"]:
		if not speed.has(k):
			r.err("speed.%s required" % k)


func _validate(db: Node, out: PackedStringArray) -> void:
	if loot_table != &"" and not db.has_def(&"loot_table", loot_table):
		out.append("%s: loot_table '%s' unknown" % [ctx(), loot_table])


func speed_for(is_night: bool, running: bool) -> float:
	var key: String = ("night_" if is_night else "day_") + ("run" if running else "walk")
	return float(speed.get(key, speed.get(("night_" if is_night else "day_") + "walk", 1.0)))


func perc(key: String, default: float) -> float:
	return float(perception.get(key, default))


func atk(key: String, default: float) -> float:
	return float(attack.get(key, default))


func beh(key: String, default: Variant) -> Variant:
	return behavior.get(key, default)
