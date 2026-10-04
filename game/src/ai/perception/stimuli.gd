class_name Stimuli
extends Node3D
## Stimulus fields — the shared perception layer every AI reads (novel system #1, ADR-0012).
##
##  * SOUND: short-lived events with a loudness (metres at which a normal listener just hears it).
##    Weather masks loudness (rain ~0.65x); walls/terrain between source and listener halve it.
##    Loud events also feed the heat/attention map.
##  * SCENT: a 64x64 grid of 4 m cells following the player. The player deposits scent (more when
##    bleeding or exerting, less when wet); it decays, diffuses and drifts with the wind. Hollowed
##    can follow the gradient to where you went, not just where you are.
##  * LIGHT/VISIBILITY: how visible the player is, from ambient light + nearby light sources + their
##    own light, scaled by stance, movement and perks.

static var current: Stimuli = null

const SOUND_LIFETIME: float = 2.5
const SCENT_CELL: float = 4.0
const SCENT_N: int = 64
const OCCLUSION_MASK: int = 1 | 2 | 16384

class SoundEvent:
	var pos: Vector3
	var loudness: float
	var kind: StringName
	var source_id: StringName
	var time: float

var sounds: Array[SoundEvent] = []
var scent := PackedFloat32Array()
var scent_origin := Vector2i.ZERO
## Dynamic light sources: node -> {"range": m, "energy": e}. Registered by torches, fires, lamps.
var lights: Dictionary = {}
var weather_noise_mask: float = 1.0
var wind := Vector2(1, 0)
var wind_strength: float = 0.3
var ambient_light: float = 1.0
var heat: HeatMap
var _time: float = 0.0
var _scent_accum: float = 0.0


func _enter_tree() -> void:
	current = self
	scent.resize(SCENT_N * SCENT_N)


func _exit_tree() -> void:
	if current == self:
		current = null


func now() -> float:
	return _time


func _process(delta: float) -> void:
	_time += delta
	while not sounds.is_empty() and _time - sounds[0].time > SOUND_LIFETIME:
		sounds.pop_front()
	_scent_accum += delta
	if _scent_accum >= 0.5:
		_update_scent(_scent_accum)
		_scent_accum = 0.0


# --- Sound ------------------------------------------------------------------------------------

## Emits a sound. loudness: metres at which it is just audible to a normal listener.
func emit_sound(pos: Vector3, loudness: float, kind: StringName, source_id: StringName = &"") -> void:
	var e := SoundEvent.new()
	e.pos = pos
	e.loudness = loudness * weather_noise_mask
	e.kind = kind
	e.source_id = source_id
	e.time = _time
	sounds.append(e)
	if heat != null and loudness >= 20.0:
		heat.add(pos, loudness / 20.0)


## Most salient sound a listener at `pos` hears since `since` (null if none).
## hearing: listener multiplier (EnemyDef perception.hearing). Ignores sounds from `ignore_id`.
func loudest_heard(pos: Vector3, hearing: float, since: float, ignore_id: StringName = &"") -> SoundEvent:
	var best: SoundEvent = null
	var best_score: float = 0.0
	for e: SoundEvent in sounds:
		if e.time < since or (ignore_id != &"" and e.source_id == ignore_id):
			continue
		var d: float = e.pos.distance_to(pos)
		var reach: float = e.loudness * hearing
		if d > reach:
			continue
		if d > reach * 0.5 and _occluded(e.pos, pos):
			reach *= 0.5
			if d > reach:
				continue
		var score: float = 1.0 - d / reach
		if score > best_score:
			best_score = score
			best = e
	return best


func _occluded(a: Vector3, b: Vector3) -> bool:
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state if is_inside_tree() else null
	if space == null:
		return false
	var q := PhysicsRayQueryParameters3D.create(a + Vector3.UP * 0.8, b + Vector3.UP * 0.8, OCCLUSION_MASK)
	return not space.intersect_ray(q).is_empty()


# --- Scent ------------------------------------------------------------------------------------

## Deposit scent at a world position (amount ~1 per second for a calm player).
func deposit_scent(pos: Vector3, amount: float) -> void:
	var c: Vector2i = _cell(pos)
	if c.x < 0:
		return
	scent[c.y * SCENT_N + c.x] = minf(scent[c.y * SCENT_N + c.x] + amount, 50.0)


func scent_at(pos: Vector3) -> float:
	var c: Vector2i = _cell(pos)
	return 0.0 if c.x < 0 else scent[c.y * SCENT_N + c.x]


## Direction of increasing scent (XZ) at pos; zero if flat.
func scent_gradient(pos: Vector3) -> Vector3:
	var c: Vector2i = _cell(pos)
	if c.x < 1 or c.y < 1 or c.x >= SCENT_N - 1 or c.y >= SCENT_N - 1:
		return Vector3.ZERO
	var gx: float = scent[c.y * SCENT_N + c.x + 1] - scent[c.y * SCENT_N + c.x - 1]
	var gz: float = scent[(c.y + 1) * SCENT_N + c.x] - scent[(c.y - 1) * SCENT_N + c.x]
	var g := Vector3(gx, 0.0, gz)
	return g.normalized() if g.length() > 0.01 else Vector3.ZERO


## Re-centres the scent window on `pos` (keeps overlapping cells).
func recenter(pos: Vector3) -> void:
	var want := Vector2i(int(floor(pos.x / SCENT_CELL)) - SCENT_N / 2, int(floor(pos.z / SCENT_CELL)) - SCENT_N / 2)
	var shift: Vector2i = want - scent_origin
	if absi(shift.x) < 8 and absi(shift.y) < 8:
		return
	var moved := PackedFloat32Array()
	moved.resize(SCENT_N * SCENT_N)
	for y: int in SCENT_N:
		for x: int in SCENT_N:
			var sx: int = x + shift.x
			var sy: int = y + shift.y
			if sx >= 0 and sy >= 0 and sx < SCENT_N and sy < SCENT_N:
				moved[y * SCENT_N + x] = scent[sy * SCENT_N + sx]
	scent = moved
	scent_origin = want


func _cell(pos: Vector3) -> Vector2i:
	var cx: int = int(floor(pos.x / SCENT_CELL)) - scent_origin.x
	var cz: int = int(floor(pos.z / SCENT_CELL)) - scent_origin.y
	if cx < 0 or cz < 0 or cx >= SCENT_N or cz >= SCENT_N:
		return Vector2i(-1, -1)
	return Vector2i(cx, cz)


func _update_scent(dt: float) -> void:
	# Decay + diffusion + wind advection (semi-Lagrangian, nearest-cell).
	var out := PackedFloat32Array()
	out.resize(SCENT_N * SCENT_N)
	var shift: Vector2 = wind * wind_strength * 1.2 * dt / SCENT_CELL
	var decay: float = pow(0.5, dt / 90.0)
	for y: int in range(1, SCENT_N - 1):
		for x: int in range(1, SCENT_N - 1):
			var sx: int = clampi(int(round(x - shift.x)), 1, SCENT_N - 2)
			var sy: int = clampi(int(round(y - shift.y)), 1, SCENT_N - 2)
			var i: int = sy * SCENT_N + sx
			var v: float = scent[i] * 0.6 + (scent[i - 1] + scent[i + 1] + scent[i - SCENT_N] + scent[i + SCENT_N]) * 0.1
			out[y * SCENT_N + x] = v * decay
	scent = out


# --- Light & visibility -------------------------------------------------------------------------

func register_light(node: Node3D, range_m: float, energy: float) -> void:
	lights[node] = {"range": range_m, "energy": energy}


func unregister_light(node: Node3D) -> void:
	lights.erase(node)


## Light falling on a point (0 = pitch dark .. ~1+ = daylight).
func light_at(pos: Vector3) -> float:
	var l: float = ambient_light
	for n: Variant in lights.keys():
		if not is_instance_valid(n):
			lights.erase(n)
			continue
		var node: Node3D = n
		if not node.is_visible_in_tree():
			continue
		var info: Dictionary = lights[n]
		var d: float = node.global_position.distance_to(pos)
		var r: float = float(info["range"])
		if d < r:
			l += float(info["energy"]) * (1.0 - d / r) * 0.6
	return l


## How far away (m) an observer with base sight range can notice the player.
## Combines light on the player, stance, motion and perks. Carried light makes you a beacon.
func detection_range(base_sight: float, light: float, crouched: bool, moving_speed: float, own_light: bool, visibility_mult: float) -> float:
	var r: float = base_sight * clampf(0.15 + light * 0.85, 0.12, 1.25)
	if crouched:
		r *= 0.55
	r *= 0.75 + clampf(moving_speed / 6.0, 0.0, 1.0) * 0.5
	if own_light:
		r = maxf(r, base_sight * 1.6 + 30.0)
	return r * maxf(0.2, 1.0 + visibility_mult)
