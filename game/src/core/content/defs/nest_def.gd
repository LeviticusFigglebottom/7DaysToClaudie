class_name NestDef
extends ContentDef
## A Bloom nest (ADR-0055): a grown mass of Bloom in the deep woods, a knot of roots and shelves round
## a hollow with pods hanging from it and the remains of what it took. BloomNests builds a placed one
## from this: its props, its Bloom zone, the Hollowed it seeds round itself while the player is near,
## and its burn (it takes fire damage only). Per-placement state lives in WorldState.nests.

const TIERS: PackedStringArray = ["", "normal", "seeded", "bloomed"]
const PROP_KEYS: PackedStringArray = ["prop", "offset", "rot", "scale", "pod"]
const SEED_KEYS: PackedStringArray = ["enemies", "count", "sleepers", "range", "leave_range", "respawn_hours", "tier", "ring"]
const BURN_KEYS: PackedStringArray = ["seconds", "scream", "fade_hours"]
const BLOOM_KEYS: PackedStringArray = ["radius", "strength"]

## [{prop: prop id, offset: [x, y, z] nest-local m (+Z front), rot: yaw degrees, scale: 1.0,
## pod: true when the Hollowed come out of it}]
var props: Array[Dictionary] = []
## The heart the player burns: nest-local centre [x, y, z] and box size [x, y, z] (m).
var core_offset: Vector3 = Vector3(0.0, 0.6, 0.0)
var core_size: Vector3 = Vector3(1.4, 1.2, 1.4)
## Bloom ground round it: a spot in the Bloom field (BloomWorld source &"nests"), radius (m) and peak
## strength 0..1.
var bloom_radius: float = 24.0
var bloom_strength: float = 0.8
## Who it seeds: {enemy id: weight}, how many in all, how many of them sleep in its roots (the
## rest wander round it), the player range (m) within which they are kept (and past which,
## `leave_range`, they are taken away), the game hours before a killed one comes back from the
## pods, their infected tier ("" = rolled like any), and the ring [min, max] (m) they stand in.
var seed_enemies: Dictionary = {"hollow": 1.0}
var seed_count: int = 3
var seed_sleepers: int = 2
var seed_range: float = 90.0
var seed_leave_range: float = 130.0
var seed_respawn_hours: float = 12.0
var seed_tier: String = ""
var seed_ring: Vector2 = Vector2(3.0, 10.0)
## Fire damage it takes before it burns.
var hp: float = 100.0
## The burn: seconds it burns, the scream's loudness (m: Stimuli.emit_sound), and the game hours its
## Bloom zone takes to fade once it is dead.
var burn_seconds: float = 15.0
var burn_scream: float = 140.0
var burn_fade_hours: float = 24.0
## Loot table its pods drop when it is dead, and how many times it is rolled.
var loot: StringName = &"nest_loot"
var loot_rolls: int = 1
## Times the `burn_nest` XP source is paid (data/config/progression.json xp).
var xp: float = 1.0


func _fields() -> PackedStringArray:
	return ["props", "core", "bloom", "seed", "hp", "burn", "loot", "loot_rolls", "xp"]


func _parse(r: DefReader) -> void:
	for pv: Variant in r.arr("props"):
		if not pv is Dictionary:
			r.err("props entries must be objects")
			continue
		var pr := DefReader.new(pv, "%s prop" % ctx())
		props.append({"prop": pr.sname("prop"), "offset": pr.vec3("offset"), "rot": pr.num("rot", 0.0),
			"scale": maxf(0.05, pr.num("scale", 1.0)), "pod": pr.boolean("pod", false)})
		if pr.sname("prop") == &"":
			pr.err("a prop entry needs 'prop'")
		pr.check_unknown(PROP_KEYS)
		r.errors.append_array(pr.errors)
	var cr := DefReader.new(r.dict("core"), "%s core" % ctx())
	core_offset = cr.vec3("offset", core_offset)
	core_size = cr.vec3("size", core_size)
	cr.check_unknown(["offset", "size"])
	r.errors.append_array(cr.errors)
	var br := DefReader.new(r.dict("bloom"), "%s bloom" % ctx())
	bloom_radius = br.num("radius", bloom_radius)
	bloom_strength = clampf(br.num("strength", bloom_strength), 0.0, 1.0)
	br.check_unknown(BLOOM_KEYS)
	r.errors.append_array(br.errors)
	var sr := DefReader.new(r.dict("seed"), "%s seed" % ctx())
	seed_enemies = sr.dict("enemies") if sr.has("enemies") else seed_enemies
	seed_count = maxi(0, sr.integer("count", seed_count))
	seed_sleepers = clampi(sr.integer("sleepers", seed_sleepers), 0, seed_count)
	seed_range = maxf(10.0, sr.num("range", seed_range))
	seed_leave_range = maxf(seed_range + 10.0, sr.num("leave_range", seed_range + 40.0))
	seed_respawn_hours = maxf(0.1, sr.num("respawn_hours", seed_respawn_hours))
	seed_tier = sr.enum_str("tier", TIERS, "")
	seed_ring = sr.range2("ring", seed_ring)
	sr.check_unknown(SEED_KEYS)
	r.errors.append_array(sr.errors)
	hp = maxf(1.0, r.num("hp", hp))
	var bu := DefReader.new(r.dict("burn"), "%s burn" % ctx())
	burn_seconds = maxf(0.5, bu.num("seconds", burn_seconds))
	burn_scream = maxf(0.0, bu.num("scream", burn_scream))
	burn_fade_hours = maxf(0.1, bu.num("fade_hours", burn_fade_hours))
	bu.check_unknown(BURN_KEYS)
	r.errors.append_array(bu.errors)
	loot = r.sname("loot", &"nest_loot")
	loot_rolls = maxi(0, r.integer("loot_rolls", 1))
	xp = maxf(0.0, r.num("xp", 1.0))
	if props.is_empty():
		r.err("a nest needs props")
	if bloom_radius <= 0.0:
		r.err("bloom.radius must be > 0")
	if seed_count > 0 and seed_enemies.is_empty():
		r.err("seed.enemies is empty but seed.count > 0")
	if seed_ring.x < 0.0 or seed_ring.y < seed_ring.x:
		r.err("seed.ring must be [min, max] with 0 <= min <= max")


func _validate(db: Node, out: PackedStringArray) -> void:
	for p: Dictionary in props:
		if not db.has_def(&"prop", p["prop"]):
			out.append("%s: prop '%s' unknown" % [ctx(), p["prop"]])
	for k: Variant in seed_enemies.keys():
		if not db.has_def(&"enemy", StringName(str(k))):
			out.append("%s: seed enemy '%s' unknown" % [ctx(), k])
		elif float(seed_enemies[k]) <= 0.0:
			out.append("%s: seed enemy '%s' needs a weight > 0" % [ctx(), k])
	if loot != &"" and not db.has_def(&"loot_table", loot):
		out.append("%s: loot table '%s' unknown" % [ctx(), loot])


## The pods (indices into props) the Hollowed come out of; the props themselves when none is marked.
func pods() -> Array[int]:
	var out: Array[int] = []
	for i: int in props.size():
		if bool(props[i].get("pod", false)):
			out.append(i)
	return out
