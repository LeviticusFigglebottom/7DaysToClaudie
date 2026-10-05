class_name WildlifeBrain
extends RefCounted
## What a wild animal makes of what is around it (ADR-0027): pure functions, so the rules are
## tested without a scene. Animals read the same world the Hollowed do (ADR-0012): how visible a
## person is (light, stance, movement), the wind carrying their scent, sounds by loudness. A deer
## sees a standing man at 80 m in daylight and bolts inside 32; downwind it smells him at 90 m;
## a crouched hunter in shadow, upwind, gets close.

enum Threat { NONE, ALERT, FLEE }


## How a person at `threat_pos` registers with an animal at `pos`. visibility: the share of the
## animal's sight range at which this person shows (Stimuli light/stance/movement, 0..1.25).
## wind: the direction the wind blows towards (XZ, normalised), strength 0..1.5.
static func person_threat(def: WildlifeDef, pos: Vector3, threat_pos: Vector3, visibility: float, crouched: bool,
		wind: Vector2, wind_strength: float, night: bool = false) -> Threat:
	var d: float = Vector2(pos.x - threat_pos.x, pos.z - threat_pos.z).length()
	var sight: float = def.sense("sight", 50.0) * clampf(visibility, 0.05, 1.25) * (0.45 if night else 1.0)
	var flee: float = def.sense("flee", 20.0) * (0.55 if crouched else 1.0)
	var alert: float = def.sense("alert", 40.0) * (0.6 if crouched else 1.0)
	if downwind(pos, threat_pos, wind, wind_strength) and d < def.sense("smell", 40.0) * clampf(0.5 + wind_strength, 0.5, 1.5):
		return Threat.FLEE
	if d < flee and d < maxf(sight, flee * 0.5):
		return Threat.FLEE
	if d < minf(alert, sight):
		return Threat.ALERT
	if d < sight * 0.5 and d < alert * 1.5:
		return Threat.ALERT
	return Threat.NONE


## The animal is downwind of `from`: the wind blows from there towards it (within ~60°).
static func downwind(pos: Vector3, from: Vector3, wind: Vector2, wind_strength: float) -> bool:
	if wind_strength < 0.05 or wind.length() < 0.01:
		return false
	var to := Vector2(pos.x - from.x, pos.z - from.z)
	if to.length() < 0.01:
		return true
	return wind.normalized().dot(to.normalized()) > 0.5


## An awake Hollowed this close sends it off (they smell of death; a deer never lets one near).
static func hollowed_threat(def: WildlifeDef, pos: Vector3, hollowed_pos: Vector3) -> Threat:
	var d: float = pos.distance_to(hollowed_pos)
	if d < def.sense("hollowed", 30.0):
		return Threat.FLEE
	if d < def.sense("hollowed", 30.0) * 1.6:
		return Threat.ALERT
	return Threat.NONE


## A sound of `loudness` (m) at `dist`: loud enough to bolt it (a gunshot, a scream, a falling
## tree), or just to make it look up.
static func sound_threat(def: WildlifeDef, loudness: float, dist: float) -> Threat:
	var heard: float = loudness * def.sense("hearing", 1.0)
	if dist > heard:
		return Threat.NONE
	if loudness >= def.sense("bolt_loudness", 25.0) and dist < heard * 0.8:
		return Threat.FLEE
	return Threat.ALERT


## Which way to run: away from every threat (nearer ones count more), bent by `jitter` (radians,
## the herd scatters a little) and away from where it cannot go (`blocked` directions, XZ).
static func flee_direction(pos: Vector3, threats: Array[Vector3], jitter: float = 0.0) -> Vector3:
	var acc := Vector3.ZERO
	for t: Vector3 in threats:
		var away := Vector3(pos.x - t.x, 0.0, pos.z - t.z)
		var d: float = maxf(away.length(), 0.5)
		acc += away.normalized() / d
	if acc.length() < 1e-4:
		acc = Vector3.FORWARD
	return acc.normalized().rotated(Vector3.UP, jitter)


## A flock on its perch at `pos` flushes for: a person within its radius (crouched and still,
## a person can slip by at half of it), an awake Hollowed nearer still, a loud enough sound.
## Returns the cause ("" = stays put).
static func flush_cause(def: WildlifeDef, pos: Vector3, people: Array, hollowed: Array[Vector3], loud: Dictionary) -> String:
	for p: Dictionary in people:
		var r: float = def.flush_radius
		if bool(p.get("crouched", false)):
			r *= 0.5 if float(p.get("speed", 0.0)) < 2.0 else 0.75
		elif float(p.get("speed", 0.0)) > 4.5:
			r *= 1.3
		if (p["pos"] as Vector3).distance_to(pos) < r:
			return "person"
	for h: Vector3 in hollowed:
		if h.distance_to(pos) < def.sense("hollowed", def.flush_radius * 0.7):
			return "hollowed"
	if not loud.is_empty() and float(loud.get("loudness", 0.0)) >= def.sense("bolt_loudness", 25.0) \
			and (loud["pos"] as Vector3).distance_to(pos) < float(loud["loudness"]):
		return "noise"
	return ""
