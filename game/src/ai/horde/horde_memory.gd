class_name HordeMemory
extends RefCounted
## Adaptive horde memory (novel system #2, see DESIGN.md).
##
## After every Hum the HordeDirector files a report: per compass sector (8 around the base) how
## many Hollowed were sent, how many died there, how many structures they broke, and what killed
## them. Memory keeps exponential moving averages and the planner uses them to shape the next Hum:
##   - avoid sectors that turned into killing fields (flank around them),
##   - send a siege group at the sector whose walls held best (later: Rammers / diggers),
##   - escalate Keeners/Lurchers if the player cleared the last nights quickly,
##   - remember the dominant cause of death (spikes, fire, guns) for counter-tactics + forecast text.
## Deterministic: same memory + same RNG seed -> same plan.

const SECTORS: int = 8
const SECTOR_NAMES: PackedStringArray = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

var nights: Array[Dictionary] = []
var lethality: PackedFloat32Array = []
var resistance: PackedFloat32Array = []
var cause_share: Dictionary = {}
## EMA of how quickly waves were cleared (0 = instantly, 1 = never).
var clear_time: float = 0.6
var horde_index: int = 0


func _init() -> void:
	lethality.resize(SECTORS)
	resistance.resize(SECTORS)
	lethality.fill(0.0)
	resistance.fill(0.0)


## Sector index (0 = north, clockwise) of `pos` around `base` on the XZ plane. North = -Z.
static func sector_of(base: Vector3, pos: Vector3) -> int:
	var d: Vector3 = pos - base
	var ang: float = atan2(d.x, -d.z)  # 0 = north, +pi/2 = east
	var idx: int = int(round(ang / (TAU / SECTORS)))
	return posmod(idx, SECTORS)


static func sector_dir(sector: int) -> Vector3:
	var ang: float = float(sector) * TAU / SECTORS
	return Vector3(sin(ang), 0.0, -cos(ang))


## report keys: day, spawned:[8], killed:[8], breaches:[8], causes:{cause:n}, clear_time:0..1
func record_night(report: Dictionary) -> void:
	var cfg: Dictionary = Content.config(&"horde").get("memory", {})
	var alpha: float = float(cfg.get("learning_rate", 0.5))
	var spawned: Array = report.get("spawned", [])
	var killed: Array = report.get("killed", [])
	var breaches: Array = report.get("breaches", [])
	for s: int in SECTORS:
		var sp: float = float(spawned[s]) if s < spawned.size() else 0.0
		if sp <= 0.0:
			continue
		var kl: float = float(killed[s]) if s < killed.size() else 0.0
		var br: float = float(breaches[s]) if s < breaches.size() else 0.0
		lethality[s] = lerpf(lethality[s], clampf(kl / sp, 0.0, 1.0), alpha)
		# "Held" = many attackers, few breaches.
		var held: float = clampf(1.0 - br / maxf(1.0, sp * 0.25), 0.0, 1.0)
		resistance[s] = lerpf(resistance[s], held, alpha)
	var causes: Dictionary = report.get("causes", {})
	var total: float = 0.0
	for c: Variant in causes.keys():
		total += float(causes[c])
	if total > 0.0:
		for c: Variant in causes.keys():
			cause_share[str(c)] = lerpf(float(cause_share.get(str(c), 0.0)), float(causes[c]) / total, alpha)
	clear_time = lerpf(clear_time, clampf(float(report.get("clear_time", 0.6)), 0.0, 1.0), alpha)
	nights.append(report.duplicate(true))
	var keep: int = int(cfg.get("keep_reports", 12))
	while nights.size() > keep:
		nights.pop_front()
	horde_index += 1


## Builds the plan for the next Hum. Returns:
## {total, waves:[{start_min, sector, units:{enemy_id: n}, role:"assault"|"siege"|"flank"}],
##  focus_sector, avoid_sectors:[...], tactics:[strings for the tether forecast]}
func plan(gamestage: int, rng: RandomNumberGenerator) -> Dictionary:
	var cfg: Dictionary = Content.config(&"horde")
	var pc: Dictionary = cfg.get("planner", {})
	var total: int = int(pc.get("base_count", 10)) + int(float(pc.get("per_horde", 6)) * horde_index) \
		+ int(float(pc.get("per_gamestage", 0.5)) * gamestage)
	# World setting: Hum horde size (the cap scales with it so large settings still grow).
	var size: float = GameRules.current().num("hum_size")
	total = mini(int(round(total * size)), int(float(pc.get("max_total", 80)) * maxf(1.0, size)))
	var mix: Dictionary = (pc.get("mix", {"hollow": 0.72, "lurcher": 0.22, "keener": 0.06}) as Dictionary).duplicate()
	# Special Hollowed join the Hum as the gamestage rises.
	for b: Variant in pc.get("mix_by_gamestage", []):
		if int((b as Dictionary).get("gs", 0)) <= gamestage:
			var add: Dictionary = (b as Dictionary).get("add", {})
			for k: String in add:
				mix[k] = float(mix.get(k, 0.0)) + float(add[k])
	var tactics: PackedStringArray = []

	# Escalation when the player cleared fast.
	if nights.size() > 0 and clear_time < float(pc.get("fast_clear_threshold", 0.45)):
		mix["lurcher"] = float(mix.get("lurcher", 0.0)) + 0.1
		mix["keener"] = float(mix.get("keener", 0.0)) + 0.04
		tactics.append("They come faster now. Something is calling them.")

	# Sector weights: flank killing fields.
	var weights := PackedFloat32Array()
	var avoid: Array[int] = []
	var flank_bias: float = float(pc.get("flank_bias", 1.6))
	for s: int in SECTORS:
		var w: float = 1.0 + flank_bias * (0.5 - lethality[s])
		if lethality[s] > 0.6:
			avoid.append(s)
		weights.append(maxf(0.05, w))
	if not avoid.is_empty():
		var names: PackedStringArray = []
		for s: int in avoid:
			names.append(SECTOR_NAMES[s])
		tactics.append("They avoid the %s approach now — it cost them too many." % "/".join(names))

	# Siege focus: where the walls held best (only meaningful once memory has data).
	var focus: int = -1
	if nights.size() > 0:
		var best: float = 0.55
		for s: int in SECTORS:
			if resistance[s] > best:
				best = resistance[s]
				focus = s
		if focus >= 0:
			tactics.append("A heavy group is massing toward the %s wall that held." % SECTOR_NAMES[focus])

	var dominant: String = ""
	var dom_v: float = 0.35
	for c: String in cause_share:
		if float(cause_share[c]) > dom_v:
			dom_v = float(cause_share[c])
			dominant = c
	if dominant == "spikes" or dominant == "trap":
		tactics.append("They step around the stakes. Traps alone won't hold them.")
	elif dominant == "fire":
		tactics.append("The Hollowed fear the fire less each Hum.")

	# Waves.
	var wave_count: int = clampi(int(pc.get("waves", 4)) + horde_index / 2, 2, 8)
	var window_min: float = float(pc.get("window_minutes", 300.0))
	var waves: Array[Dictionary] = []
	var remaining: int = total
	for wi: int in wave_count:
		var n: int = int(ceil(float(remaining) / float(wave_count - wi)))
		remaining -= n
		var role: String = "assault"
		var sector: int = Weighted.pick_index(weights, rng)
		if focus >= 0 and wi == wave_count - 1:
			sector = focus
			role = "siege"
		elif wi % 3 == 2:
			role = "flank"
		var units: Dictionary = {}
		for i: int in n:
			var e: String = str(Weighted.pick_key(mix, rng))
			units[e] = int(units.get(e, 0)) + 1
		var start: float = window_min * float(wi) / float(wave_count) + rng.randf_range(0.0, 8.0)
		waves.append({"start_min": start, "sector": sector, "units": units, "role": role})
	if tactics.is_empty():
		tactics.append("The ground hums. They will come from every side.")
	return {"total": total, "mix": mix, "waves": waves, "focus_sector": focus, "avoid_sectors": avoid, "tactics": tactics}


func to_dict() -> Dictionary:
	return {
		"nights": nights, "lethality": Array(lethality), "resistance": Array(resistance),
		"causes": cause_share, "clear_time": clear_time, "index": horde_index,
	}


func from_dict(d: Dictionary) -> void:
	nights.clear()
	for n: Variant in d.get("nights", []):
		if n is Dictionary:
			nights.append(n)
	var l: Array = d.get("lethality", [])
	var r: Array = d.get("resistance", [])
	for s: int in SECTORS:
		lethality[s] = float(l[s]) if s < l.size() else 0.0
		resistance[s] = float(r[s]) if s < r.size() else 0.0
	cause_share = (d.get("causes", {}) as Dictionary).duplicate()
	clear_time = float(d.get("clear_time", 0.6))
	horde_index = int(d.get("index", 0))
