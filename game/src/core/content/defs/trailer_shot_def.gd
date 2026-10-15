class_name TrailerShotDef
extends ContentDef
## One shot of the showcase trailer (make trailer-shot SHOT=<id>), rendered by the game itself
## (src/tools/cli/trailer_runner.gd). The id is the clip id in the cut (tools/trailer/edit.json);
## `dur` is what the cut keeps and the runner records `tail` seconds more for the edit's handles.
##
## The timeline starts at -lead: the world plays (actions with t < 0 fire) while the frames are
## still trimmed, so a horde can be on its way by frame 0. Positions are offsets from `anchor`
## (world x/z, y from the ground there); with `terrain_follow` each camera key's y is its height
## above the ground under that key instead (a drone over rolling ground).

const CAMERA_MODES: PackedStringArray = ["path"]
const EASES: PackedStringArray = ["linear", "in", "out", "in_out"]
const ACTIONS: PackedStringArray = ["spawn", "hum", "command", "weather", "flag"]
## Debug flags an action may set (DebugTools): the rest would change what the shot shows.
const FLAGS: PackedStringArray = ["god_mode", "invisible"]

## World x/z every position is relative to; y is the ground height there.
var anchor: Vector2 = Vector2.ZERO
## Seconds the cut keeps, and the extra seconds recorded after it.
var dur: float = 4.0
var tail: float = 0.5
## Seconds simulated (not recorded) before frame 0.
var lead: float = 0.0
var day: int = 1
var hour: float = 12.0
## Hour at the end of the recording (time-lapse); < 0 = the clock runs at its normal rate.
var hour_end: float = -1.0
var weather: StringName = &"clear"
## The game's brightness setting for the shot (Settings.brightness): a night shot is graded up
## ("day for night"); a moonlit Hum meadow renders at ~1/255 at 1, its shapes there but unreadable.
var exposure: float = 1.0
## Show the HUD (the tether shots); off everywhere else.
var hud: bool = false
## Player (hidden, input off) position offset: what the Hum and the AI head for.
var player: Vector3 = Vector3.ZERO
## False: the player follows the camera's ground point (the forest streams round the lens).
var player_fixed: bool = false
var camera_mode: String = "path"
var ease: String = "in_out"
var terrain_follow: bool = false
## [{t, pos: Vector3, look: Vector3, fov}], sorted by t, t in [0, dur + tail].
var keys: Array[Dictionary] = []
## [{t, do, ...}] sorted by t; see ACTIONS and _parse_action().
var actions: Array[Dictionary] = []


func _fields() -> PackedStringArray:
	return ["anchor", "dur", "tail", "lead", "day", "hour", "hour_end", "weather", "exposure", "hud", "player", "camera", "actions"]


func _parse(r: DefReader) -> void:
	var a: Variant = r.raw("anchor", null)
	if a is Array and (a as Array).size() == 2:
		anchor = Vector2(float(a[0]), float(a[1]))
	else:
		r.err("field 'anchor' expected [x, z]")
	dur = r.num("dur", 4.0)
	tail = r.num("tail", 0.5)
	lead = r.num("lead", 0.0)
	if dur <= 0.0 or tail < 0.0 or lead < 0.0:
		r.err("dur must be > 0, tail and lead >= 0")
	day = maxi(1, r.integer("day", 1))
	hour = r.num("hour", 12.0)
	hour_end = r.num("hour_end", -1.0)
	if hour < 0.0 or hour >= 24.0 or hour_end >= 48.0:
		r.err("hour must be in [0, 24), hour_end below 48 (past midnight: + 24)")
	weather = r.sname("weather", &"clear")
	exposure = r.num("exposure", 1.0)
	if exposure < 0.25 or exposure > 32.0:
		r.err("exposure must be in [0.25, 32]")
	hud = r.boolean("hud", false)
	player = r.vec3("player", Vector3.ZERO)
	player_fixed = r.has("player")
	var c := DefReader.new(r.dict("camera"), "%s camera" % ctx())
	camera_mode = c.enum_str("mode", CAMERA_MODES, "path")
	ease = c.enum_str("ease", EASES, "in_out")
	terrain_follow = c.boolean("terrain_follow", false)
	var last_t: float = -1.0
	for k: Variant in c.arr("keys"):
		if not k is Dictionary:
			c.err("every camera key must be an object")
			continue
		var kr := DefReader.new(k, "%s camera key %d" % [ctx(), keys.size()])
		var key: Dictionary = {"t": kr.num("t", 0.0), "pos": kr.vec3("pos"), "look": kr.vec3("look"), "fov": kr.num("fov", 60.0)}
		kr.check_unknown(["t", "pos", "look", "fov"])
		if float(key["t"]) <= last_t:
			kr.err("keys must be in increasing t")
		if float(key["fov"]) < 10.0 or float(key["fov"]) > 120.0:
			kr.err("fov must be in [10, 120]")
		if (key["pos"] as Vector3).is_equal_approx(key["look"]):
			kr.err("pos and look must differ")
		last_t = float(key["t"])
		keys.append(key)
		c.errors.append_array(kr.errors)
	if keys.size() < 2:
		c.err("a path needs at least 2 keys")
	elif float(keys[0]["t"]) > 0.0 or last_t < dur + tail - 0.001:
		c.err("keys must cover t 0 .. dur + tail (%.2f)" % (dur + tail))
	c.check_unknown(["mode", "ease", "terrain_follow", "keys"])
	r.errors.append_array(c.errors)
	last_t = -INF
	for x: Variant in r.arr("actions"):
		if not x is Dictionary:
			r.err("every action must be an object")
			continue
		var ar := DefReader.new(x, "%s action %d" % [ctx(), actions.size()])
		var act: Dictionary = _parse_action(ar)
		if float(act["t"]) < last_t:
			ar.err("actions must be in increasing t")
		if float(act["t"]) < -lead or float(act["t"]) > dur + tail:
			ar.err("t must be in [-lead, dur + tail]")
		last_t = float(act["t"])
		actions.append(act)
		r.errors.append_array(ar.errors)


## spawn {enemy, at, count, spread, horde, target}: `count` bodies within `spread` m of `at`;
## horde ones run the Hum's flow field at the player, the rest are alerted to `target`.
## hum {until}: starts the Hum now (the clock jumps to its start), then runs the clock on to the
## hour `until` (e.g. 0.75: under a high moon; every wave due by then is queued).
## command {command, args}: Game.execute; vectors in args are written [x, y, z] (anchor-relative
## when the key ends in "pos"). weather {weather}. flag {flag, on}.
func _parse_action(ar: DefReader) -> Dictionary:
	var act: Dictionary = {"t": ar.num("t", 0.0), "do": ar.enum_str("do", ACTIONS, "spawn")}
	var known: PackedStringArray = ["t", "do"]
	match str(act["do"]):
		"spawn":
			act["enemy"] = ar.sname("enemy", &"hollow")
			act["at"] = ar.vec3("at")
			act["count"] = maxi(1, ar.integer("count", 1))
			act["spread"] = maxf(0.0, ar.num("spread", 0.0))
			act["horde"] = ar.boolean("horde", false)
			act["target"] = ar.vec3("target", Vector3.INF) if ar.has("target") else null
			known.append_array(["enemy", "at", "count", "spread", "horde", "target"])
		"command":
			act["command"] = ar.req_str("command")
			act["args"] = ar.dict("args")
			known.append_array(["command", "args"])
		"hum":
			act["until"] = ar.num("until", -1.0)
			if float(act["until"]) >= 24.0:
				ar.err("until is an hour of the night, [0, 24)")
			known.append("until")
		"weather":
			act["weather"] = ar.sname("weather", &"clear")
			known.append("weather")
		"flag":
			act["flag"] = ar.enum_str("flag", FLAGS, "god_mode")
			act["on"] = ar.boolean("on", true)
			known.append_array(["flag", "on"])
	ar.check_unknown(known)
	return act


func _validate(db: Node, out: PackedStringArray) -> void:
	if not db.has_def(&"weather", weather):
		out.append("%s: weather '%s' unknown" % [ctx(), weather])
	for act: Dictionary in actions:
		match str(act["do"]):
			"spawn":
				if not db.has_def(&"enemy", act["enemy"]):
					out.append("%s: spawn enemy '%s' unknown" % [ctx(), act["enemy"]])
			"weather":
				if not db.has_def(&"weather", act["weather"]):
					out.append("%s: weather '%s' unknown" % [ctx(), act["weather"]])


## Frames recorded (dur + tail at `fps`).
func frame_count(fps: int) -> int:
	return ceili((dur + tail) * float(fps) - 0.001)


## Camera pose at shot time t (anchor-relative, before terrain_follow): {pos, look, fov}. Time is
## eased over the whole shot, then the keys are joined by a Catmull-Rom spline (smooth through
## every key, no overshoot at the ends).
func camera_at(t: float) -> Dictionary:
	var total: float = float(keys[-1]["t"])
	var u: float = clampf(t / total, 0.0, 1.0) if total > 0.0 else 0.0
	match ease:
		"in":
			u = u * u
		"out":
			u = 1.0 - (1.0 - u) * (1.0 - u)
		"in_out":
			u = u * u * (3.0 - 2.0 * u)
	var te: float = u * total
	var i: int = 0
	while i < keys.size() - 2 and te > float(keys[i + 1]["t"]):
		i += 1
	var k1: Dictionary = keys[i]
	var k2: Dictionary = keys[i + 1]
	var k0: Dictionary = keys[maxi(i - 1, 0)]
	var k3: Dictionary = keys[mini(i + 2, keys.size() - 1)]
	var span: float = float(k2["t"]) - float(k1["t"])
	var s: float = clampf((te - float(k1["t"])) / span, 0.0, 1.0) if span > 0.0 else 0.0
	return {
		"pos": _catmull(k0["pos"], k1["pos"], k2["pos"], k3["pos"], s),
		"look": _catmull(k0["look"], k1["look"], k2["look"], k3["look"], s),
		"fov": lerpf(float(k1["fov"]), float(k2["fov"]), s * s * (3.0 - 2.0 * s)),
	}


static func _catmull(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, s: float) -> Vector3:
	return p1.cubic_interpolate(p2, p0, p3, s)
