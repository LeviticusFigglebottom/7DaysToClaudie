class_name ProgramDrone
extends Node3D
## The Remand Program's heavy-lift drone bringing a supply lift in (ADR-0023, TD-029). Its flight
## is a pure function of time (Flight): in from the valley's edge at cruise height, braking to a
## hover over the drop spot, letting the canister go, then away and climbing. SupplyDrops' Drop
## owns the clock and moves both, so a frame skip or a test's one big step lands the canister where
## the drone let it go. Eight rotors spin over a faint blur disc, the nav lights burn and the top
## strobe flashes, and the rotor loop is pitch-shifted for the doppler as it passes the listener.
## Numbers come from data/config/program_drone.json.

const MODEL: String = "props/program_drone"
const ROTOR_MODEL: String = "props/program_drone_rotor"
## Rotor hubs (props_ext_program.py ARM_R / ROTOR_Z): arms at 45 + 90k degrees, coaxial pairs.
const ARM_R: float = 1.15
const ROTOR_Z: float = 0.135
## Where the canister's base hangs below the airframe's origin (sling to the lifting lugs).
const HANG := Vector3(0.0, -1.9, 0.0)
const SPEED_OF_SOUND: float = 343.0


## A drone's path in time: from `start` at cruise height in a straight line to `hover` over the
## spot, braking over the last `brake` metres; a hover; then accelerating away to `end`.
class Flight:
	extends RefCounted
	var start := Vector3.ZERO
	var hover := Vector3.ZERO
	var end := Vector3.ZERO
	var speed: float = 30.0
	var brake: float = 120.0
	var hover_time: float = 3.0
	var release_after: float = 1.2
	var t_arrive: float = 0.0
	var t_leave: float = 0.0
	var t_end: float = 0.0

	func setup() -> Flight:
		brake = minf(brake, minf(start.distance_to(hover), hover.distance_to(end)) * 0.5)
		t_arrive = _leg_time(start.distance_to(hover))
		t_leave = t_arrive + hover_time
		t_end = t_leave + _leg_time(hover.distance_to(end))
		return self

	## Seconds after the start at which the canister is let go.
	func release_time() -> float:
		return t_arrive + release_after

	func position(t: float) -> Vector3:
		if t <= t_arrive:
			return start.lerp(hover, _leg_distance(t, start.distance_to(hover), false) / maxf(start.distance_to(hover), 1e-3))
		if t <= t_leave:
			return hover
		var d: float = hover.distance_to(end)
		return hover.lerp(end, _leg_distance(t - t_leave, d, true) / maxf(d, 1e-3))

	func velocity(t: float) -> Vector3:
		return (position(t + 0.05) - position(t - 0.05)) / 0.1

	func heading() -> Vector3:
		var h := Vector3(end.x - start.x, 0.0, end.z - start.z)
		return h.normalized() if h.length_squared() > 1e-6 else Vector3.FORWARD

	## Time for a leg of `d` metres: cruise, plus a ramp of `brake` metres at half speed on average.
	func _leg_time(d: float) -> float:
		return (d - brake) / speed + 2.0 * brake / speed

	## Distance covered `t` seconds into a leg of `d` metres: cruising then braking to a stop
	## (`from_rest` false), or starting from rest and accelerating to cruise (true).
	func _leg_distance(t: float, d: float, from_rest: bool) -> float:
		var ramp_t: float = 2.0 * brake / speed
		var a: float = speed * speed / (2.0 * maxf(brake, 1e-3))
		if from_rest:
			if t < ramp_t:
				return 0.5 * a * t * t
			return minf(d, brake + speed * (t - ramp_t))
		var cruise_t: float = (d - brake) / speed
		if t < cruise_t:
			return speed * t
		var tau: float = minf(t - cruise_t, ramp_t)
		return minf(d, d - brake + speed * tau - 0.5 * a * tau * tau)


## The flight that delivers a drop to `ground`: from a bearing fixed by the world seed and `key`,
## `approach_m` out at `cruise_alt`, to a hover `release_alt` up, then on along the same bearing.
static func plan_flight(ground: Vector3, key: String, world_seed: int, cfg: Dictionary, release_alt: float) -> Flight:
	var bearing: float = float(Ids.hash31("drone:%d:%s" % [world_seed, key]) % 3600) / 3600.0 * TAU
	var dir := Vector3(sin(bearing), 0.0, cos(bearing))
	var f := Flight.new()
	f.speed = float(cfg.get("cruise_speed", 30.0))
	f.brake = float(cfg.get("brake_m", 120.0))
	f.hover_time = float(cfg.get("hover_s", 3.0))
	f.release_after = float(cfg.get("release_after_s", 1.2))
	f.hover = ground + Vector3.UP * release_alt
	f.start = ground - dir * float(cfg.get("approach_m", 650.0)) + Vector3.UP * float(cfg.get("cruise_alt", 140.0))
	f.end = ground + dir * float(cfg.get("depart_m", 900.0)) + Vector3.UP * float(cfg.get("depart_alt", 190.0))
	return f.setup()


## Pitch factor a moving source gets at a listener (> 1 approaching, < 1 receding).
static func doppler(src_pos: Vector3, src_vel: Vector3, lis_pos: Vector3, lis_vel: Vector3) -> float:
	var to_src: Vector3 = src_pos - lis_pos
	if to_src.length_squared() < 1e-4:
		return 1.0
	var n: Vector3 = to_src.normalized()
	# Positive when the gap is opening.
	var v_away: float = (src_vel - lis_vel).dot(n)
	return clampf(SPEED_OF_SOUND / maxf(SPEED_OF_SOUND + v_away, 1.0), 0.5, 2.0)


var flight: Flight
var cfg: Dictionary = {}
## The drop spot on the ground (its hover noise is heard there).
var ground := Vector3.ZERO
var _rotors: Array[Node3D] = []
var _rotor_spin: float = 0.0
var _loop: AudioStreamPlayer3D
var _strobe: OmniLight3D
var _released: bool = false
var _listener_prev := Vector3.INF
var _pitch: float = 1.0
var _t: float = 0.0


func _ready() -> void:
	top_level = true
	if cfg.is_empty():
		cfg = Content.config(&"program_drone")
	var body := MeshInstance3D.new()
	body.name = "Airframe"
	body.mesh = ModelLibrary.mesh(MODEL, "box") if ModelLibrary.has_model(MODEL) else _fallback_body()
	add_child(body)
	var rotor_mesh: Mesh = ModelLibrary.mesh(ROTOR_MODEL, "box") if ModelLibrary.has_model(ROTOR_MODEL) else _fallback_rotor()
	for k: int in 4:
		var a: float = deg_to_rad(45.0 + 90.0 * k)
		for up: float in [1.0, -1.0]:
			# Blender (x, y, z) -> Godot (x, z, -y).
			var r := MeshInstance3D.new()
			r.mesh = rotor_mesh
			r.position = Vector3(cos(a) * ARM_R, ROTOR_Z * up, -sin(a) * ARM_R)
			r.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(r)
			_rotors.append(r)
	_strobe = OmniLight3D.new()
	_strobe.name = "Strobe"
	_strobe.light_color = Color(0.92, 0.95, 1.0)
	_strobe.omni_range = 30.0
	_strobe.light_energy = 0.0
	_strobe.shadow_enabled = false
	_strobe.position = Vector3(0.0, 0.25, -0.3)
	add_child(_strobe)
	_loop = AudioStreamPlayer3D.new()
	_loop.name = "Rotors"
	_loop.stream = Audio.stream(&"sfx/drone_rotor_loop")
	_loop.bus = &"SFX"
	_loop.unit_size = float(cfg.get("sound_unit_size", 45.0))
	_loop.max_distance = float(cfg.get("sound_range", 700.0))
	_loop.volume_db = float(cfg.get("sound_db", -2.0))
	add_child(_loop)
	if _loop.stream != null:
		_loop.play()
	if flight != null:
		fly(0.0)


## Places the drone at `t` seconds into its flight (called by its Drop every frame).
func fly(t: float) -> void:
	if flight == null:
		return
	var delta: float = maxf(0.0, t - _t)
	_t = t
	if t > flight.t_end:
		queue_free()
		return
	var p: Vector3 = flight.position(t)
	var v: Vector3 = flight.velocity(t)
	var acc: Vector3 = (flight.velocity(t + 0.25) - flight.velocity(t - 0.25)) / 0.5
	var fwd: Vector3 = flight.heading()
	# A multirotor leans into its acceleration: nose down to speed up, back to brake.
	var pitch: float = clampf(-acc.dot(fwd) * 0.045, -0.35, 0.35)
	var wobble: float = sin(t * 1.7) * 0.012 + sin(t * 2.9 + 1.0) * 0.008
	var basis := Basis.looking_at(-fwd, Vector3.UP).rotated(fwd.cross(Vector3.UP).normalized(), pitch)
	global_transform = Transform3D(basis.rotated(fwd, wobble), p + Vector3.UP * sin(t * 1.1) * 0.15 * float(t > flight.t_arrive and t < flight.t_leave))
	_rotor_spin += delta * TAU * float(cfg.get("rotor_rps", 7.0))
	for i: int in _rotors.size():
		_rotors[i].rotation.y = _rotor_spin * (1.0 if i % 2 == 0 else -1.0) + float(i) * 0.7
	# Strobe: a double flash every 1.4 s.
	var ph: float = fposmod(t, 1.4)
	_strobe.light_energy = 4.0 if (ph < 0.06 or (ph > 0.18 and ph < 0.24)) else 0.0
	if not _released and t >= flight.release_time():
		_released = true
		Audio.play_3d(&"sfx/drone_release", p + HANG * 0.3, {"volume_db": 2.0, "max_distance": 220.0, "unit_size": 20.0})
		# The racket over the spot carries to the ground: Hollowed nearby come to look.
		if Stimuli.current != null:
			Stimuli.current.emit_sound(ground, float(cfg.get("hover_noise", 70.0)), &"drone", &"")
	_update_doppler(p, v, delta)


func _update_doppler(p: Vector3, v: Vector3, delta: float) -> void:
	if _loop == null or not is_inside_tree():
		return
	var cam: Camera3D = get_viewport().get_camera_3d() if get_viewport() != null else null
	if cam == null:
		return
	var lp: Vector3 = cam.global_position
	var lv := Vector3.ZERO
	if _listener_prev != Vector3.INF and delta > 1e-4:
		lv = (lp - _listener_prev) / delta
	_listener_prev = lp
	var target: float = doppler(p, v, lp, lv)
	_pitch = lerpf(_pitch, target, clampf(delta * 6.0, 0.0, 1.0))
	_loop.pitch_scale = _pitch


# --- Stand-ins before `make assets` ---------------------------------------------------------------

static func _fallback_body() -> Mesh:
	var m := BoxMesh.new()
	m.size = Vector3(0.66, 0.3, 1.46)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.85, 0.84, 0.8)
	m.material = mat
	return m


static func _fallback_rotor() -> Mesh:
	var m := CylinderMesh.new()
	m.top_radius = 0.48
	m.bottom_radius = 0.48
	m.height = 0.01
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.1, 0.1, 0.1, 0.25)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.material = mat
	return m
