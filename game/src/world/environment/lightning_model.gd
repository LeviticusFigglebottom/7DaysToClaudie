class_name LightningModel
extends RefCounted
## Lightning as a pure function of the world seed and the game clock (ADR-0033). Game time is cut
## into slots of `slot_minutes`; a slot holds a strike with chance rate x slot / 60, decided by a
## hash of the seed and the slot, so the same world and the same clock give the same storm however
## the frames fall, and a save reloads into the same strikes. A strike has a moment inside its
## slot, a bearing, a distance (log-uniform: most fall kilometres off), 1..4 return strokes, and a
## shape seed for the bolt the sky draws. Its thunder arrives distance / speed of sound later.

## Default numbers (data/config/weather.json "lightning" overrides them).
const DEFAULTS: Dictionary = {"slot_minutes": 0.5, "distance_m": [350.0, 9000.0], "strokes": [1, 4], "stroke_gap_s": [0.05, 0.18],
	"flash_s": 0.11, "speed_of_sound": 343.0}


## Strikes whose moment lies in [from_min, to_min) game minutes at `rate` strikes per game hour,
## oldest first. Contiguous windows never count a strike twice or miss one.
static func strikes_between(seed: int, from_min: float, to_min: float, rate: float, cfg: Dictionary = {}) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if rate <= 0.0 or to_min <= from_min:
		return out
	var slot_m: float = maxf(0.01, float(cfg.get("slot_minutes", DEFAULTS["slot_minutes"])))
	for slot: int in range(floori(from_min / slot_m), floori(to_min / slot_m) + 1):
		var s: Dictionary = strike_in_slot(seed, slot, rate, cfg)
		if not s.is_empty() and float(s["at_min"]) >= from_min and float(s["at_min"]) < to_min:
			out.append(s)
	return out


## The strike in one slot, or {} when the slot is quiet at this rate.
static func strike_in_slot(seed: int, slot: int, rate: float, cfg: Dictionary = {}) -> Dictionary:
	var slot_m: float = maxf(0.01, float(cfg.get("slot_minutes", DEFAULTS["slot_minutes"])))
	var h: int = _mix(Ids.hash64("%d|lightning|%d" % [seed, slot]))
	var chance: float = clampf(rate * slot_m / 60.0, 0.0, 1.0)
	if _u(h, 0) >= chance:
		return {}
	var h2: int = _mix(Ids.hash64("%d|lightning_shape|%d" % [seed, slot]))
	var dr: Array = cfg.get("distance_m", DEFAULTS["distance_m"])
	var d0: float = maxf(1.0, float(dr[0]))
	var d1: float = maxf(d0, float(dr[1]))
	var sr: Array = cfg.get("strokes", DEFAULTS["strokes"])
	var gr: Array = cfg.get("stroke_gap_s", DEFAULTS["stroke_gap_s"])
	# Single and double flashes are the most common; four strokes are rare.
	var n: int = int(sr[0]) + int(floor(pow(_u(h2, 0), 1.6) * float(int(sr[1]) - int(sr[0]) + 1)))
	n = clampi(n, int(sr[0]), int(sr[1]))
	var offsets: PackedFloat32Array = [0.0]
	var t: float = 0.0
	for k: int in range(1, n):
		t += lerpf(float(gr[0]), float(gr[1]), _u(h2, k % 4) * 0.5 + _u(h, (k + 1) % 4) * 0.5)
		offsets.append(t)
	return {
		"slot": slot,
		"at_min": (float(slot) + _u(h, 1) * 0.999) * slot_m,
		"bearing": _u(h, 2) * TAU,
		"distance": d0 * pow(d1 / d0, _u(h, 3)),
		"strokes": offsets,
		"shape": (h2 >> 20) & 0xFFFF,
	}


## Real seconds from a strike to its thunder at `distance` metres.
static func thunder_delay(distance: float, cfg: Dictionary = {}) -> float:
	return distance / maxf(1.0, float(cfg.get("speed_of_sound", DEFAULTS["speed_of_sound"])))


## Brightness of a strike `since` real seconds after it began, 0..1: each return stroke flashes
## up in a few milliseconds and dies away over flash_s, the first brightest.
static func flash(strike: Dictionary, since: float, cfg: Dictionary = {}) -> float:
	if strike.is_empty() or since < 0.0:
		return 0.0
	var fs: float = maxf(0.01, float(cfg.get("flash_s", DEFAULTS["flash_s"])))
	var out: float = 0.0
	var offsets: PackedFloat32Array = strike.get("strokes", PackedFloat32Array([0.0]))
	for k: int in offsets.size():
		var dt: float = since - offsets[k]
		if dt < 0.0:
			continue
		var peak: float = 1.0 if k == 0 else 0.75 - 0.1 * float(k)
		out = maxf(out, peak * smoothstep(0.0, 0.012, dt) * exp(-dt / fs))
	return out


## Seconds a strike stays visible (its last stroke has died away).
static func duration(strike: Dictionary, cfg: Dictionary = {}) -> float:
	var offsets: PackedFloat32Array = strike.get("strokes", PackedFloat32Array([0.0]))
	return offsets[offsets.size() - 1] + 5.0 * float(cfg.get("flash_s", DEFAULTS["flash_s"]))


## Direction toward the light of a strike: the cloud base it lights (about 1.6 km up) over its
## bearing, so near strikes light from high and far ones from the horizon.
static func light_direction(strike: Dictionary) -> Vector3:
	var b: float = float(strike.get("bearing", 0.0))
	var e: float = atan2(1600.0, maxf(1.0, float(strike.get("distance", 3000.0))))
	return Vector3(cos(b) * cos(e), sin(e), sin(b) * cos(e)).normalized()


## A 64-bit finaliser (MurmurHash3's fmix64): FNV-1a of strings that differ only in their last
## digits leaves its low bits poorly mixed, which skewed the slot draws (a storm struck at a third of
## its rate). Shifts are masked to be logical: GDScript's >> keeps the sign.
static func _mix(h: int) -> int:
	h = h ^ ((h >> 33) & 0x7FFFFFFF)
	h = h * -49064778989728563
	h = h ^ ((h >> 33) & 0x7FFFFFFF)
	h = h * -4265267296055464877
	h = h ^ ((h >> 33) & 0x7FFFFFFF)
	return h


## The k-th 16-bit uniform (0..3) of a 64-bit hash, in [0, 1).
static func _u(h: int, k: int) -> float:
	return float((h >> (16 * k)) & 0xFFFF) / 65536.0
