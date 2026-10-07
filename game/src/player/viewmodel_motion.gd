class_name ViewModelMotion
extends RefCounted
## Procedural first-person motion layered over the baked arm poses (ADR-0029): breathing, sway that
## lags the view, inertia against movement, a bob tied to the footsteps, the lowered sprint pose,
## landing dips, the drop-and-raise of a newly equipped item, swing recoil, stagger jolts and the
## camera kick. Springs stepped by update(); no nodes, so a fixed input sequence gives a fixed
## result (tests drive it directly). Numbers come from data/config/viewmodel.json `motion`.


## A damped 3-vector spring (x chases a target; impulses kick its velocity).
class Spring:
	var x := Vector3.ZERO
	var v := Vector3.ZERO

	func step(target: Vector3, stiffness: float, damping: float, dt: float) -> Vector3:
		# Sub-step so a long frame can't make a stiff spring explode.
		var n: int = maxi(1, ceili(dt / 0.008))
		var h: float = dt / float(n)
		for i: int in n:
			v += ((target - x) * stiffness - v * damping) * h
			x += v * h
		return x

	func impulse(dv: Vector3) -> void:
		v += dv


var cfg: Dictionary = {}
var t: float = 0.0
## Rig rotation lag behind the view (degrees: pitch, yaw, roll).
var sway := Spring.new()
## Rig position and rotation against the movement.
var move := Spring.new()
var move_rot := Spring.new()
## Camera kick (degrees) and rig recoil (metres), jolt (degrees): impacts, shots, staggers.
var kick := Spring.new()
var recoil := Spring.new()
var jolt := Spring.new()
var land := Spring.new()
## 0..1 blends.
var sprint_w: float = 0.0
var bob_w: float = 0.0
## Raise progress of the item in hand: 0 just switched (lowered) .. 1 up.
var equip: float = 1.0
## Narrowing of the viewmodel while reading the tether (0..1), set by the view model.
var reading: float = 0.0

var _pos := Vector3.ZERO
var _rot := Vector3.ZERO
var _kick_k: float = 170.0
var _kick_c: float = 20.0


func setup(viewmodel_cfg: Dictionary) -> void:
	cfg = viewmodel_cfg.get("motion", {})
	var ik: Dictionary = viewmodel_cfg.get("impact", {})
	_kick_k = float(ik.get("kick_stiffness", _kick_k))
	_kick_c = float(ik.get("kick_damping", _kick_c))


func _v3(a: Variant, d: Vector3 = Vector3.ZERO) -> Vector3:
	if a is Array and (a as Array).size() == 3:
		return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return d


## A new item was equipped: drop it out of view and raise it again over motion.equip seconds.
func start_equip() -> void:
	equip = 0.0


## Landed at `speed` m/s: the arms dip with the knees.
func landed(speed: float) -> void:
	var l: Dictionary = cfg.get("land", {})
	var dip: float = minf(speed * float(l.get("per_mps", 0.006)), float(l.get("max", 0.05)))
	land.impulse(Vector3(0.0, -dip * 14.0, 0.0))


## A swing connected: the camera kicks (degrees) and the rig recoils back up its swing (metres).
func impact(kick_deg: Vector3, recoil_m: float) -> void:
	kick.impulse(kick_deg * 22.0)
	recoil.impulse(Vector3(0.0, recoil_m * 0.6, recoil_m) * 30.0)


## Took a hit: the arms are knocked (degrees, scaled by the caller) and the view jolts.
func stagger(deg: float, pos_m: float, side: float) -> void:
	jolt.impulse(Vector3(-deg * 0.6, deg * 0.8 * side, deg * side) * 18.0)
	recoil.impulse(Vector3(-pos_m * side, -pos_m, pos_m) * 30.0)
	kick.impulse(Vector3(deg * 0.25, deg * 0.2 * side, deg * 0.35 * side) * 18.0)


## A shot: the muzzle climbs.
func gun_recoil(strength: float) -> void:
	kick.impulse(Vector3(2.5, 0.0, 0.0) * 22.0 * strength)
	jolt.impulse(Vector3(9.0, 0.0, 0.0) * 18.0 * strength)
	recoil.impulse(Vector3(0.0, 0.01, 0.05) * 30.0 * strength)


## Steps the motion. look_rate: (yaw, pitch) of the view in rad/s (yaw + = turning left, pitch + =
## looking up); vel: velocity in camera space (m/s); speed: horizontal speed; step_phase: 0..1
## through the current footstep, step_index: footsteps taken (parity alternates the sway);
## walk_speed: what speed counts as a full bob.
func update(dt: float, look_rate: Vector2, vel: Vector3, speed: float, sprinting: bool, crouching: bool,
		on_floor: bool, step_phase: float, step_index: int, walk_speed: float = 3.4) -> void:
	t += dt
	var deg := Vector3.ZERO
	var pos := Vector3.ZERO
	# Breathing.
	var br: Dictionary = cfg.get("breathe", {})
	var w: float = TAU * t / maxf(0.5, float(br.get("period", 4.2)))
	pos += _v3(br.get("pos")) * sin(w)
	deg += _v3(br.get("rot")) * sin(w + 0.6)
	# Sway: the rig lags the turn, rolling a little into it.
	var sw: Dictionary = cfg.get("sway", {})
	var k: Vector3 = _v3(sw.get("deg_per_rad_s"), Vector3(1.6, 1.6, 0.6))
	var mx: float = float(sw.get("max_deg", 6.0))
	var target := Vector3(clampf(-look_rate.y * k.x, -mx, mx), clampf(-look_rate.x * k.y, -mx, mx), clampf(look_rate.x * k.z, -mx, mx))
	sway.step(target, float(sw.get("stiffness", 95.0)), float(sw.get("damping", 13.0)), dt)
	deg += sway.x
	var ppd: float = float(sw.get("pos_per_deg", 0.0012))
	pos += Vector3(sway.x.y * ppd, -sway.x.x * ppd, 0.0)
	# Inertia: the arms trail the movement.
	var mv: Dictionary = cfg.get("move", {})
	# Only walking pace drives it: a fall, a knockback or a teleport once flung the arms off into
	# the sky (a player stuck in a -74 m/s free fall, looking up, moved them 0.4 m).
	vel = vel.limit_length(float(mv.get("max_mps", 6.0)))
	var pk: Vector3 = _v3(mv.get("pos_per_mps"), Vector3(0.004, 0.0, 0.006))
	var rk: Vector3 = _v3(mv.get("rot_per_mps"), Vector3(0.6, 0.0, 1.0))
	move.step(Vector3(-vel.x * pk.x, -vel.y * pk.y, -vel.z * pk.z), float(mv.get("stiffness", 45.0)), float(mv.get("damping", 10.0)), dt)
	move_rot.step(Vector3(vel.z * rk.x, 0.0, -vel.x * rk.z), float(mv.get("stiffness", 45.0)), float(mv.get("damping", 10.0)), dt)
	pos += move.x
	deg += move_rot.x
	# Footstep bob: lowest as each foot lands, swaying side to side every other step.
	var bb: Dictionary = cfg.get("bob", {})
	var want_bob: float = clampf(speed / maxf(0.1, walk_speed), 0.0, 1.5) if on_floor else 0.0
	bob_w = move_toward(bob_w, want_bob, dt * 4.0)
	var mult: float = float(bb.get("sprint", 1.8)) if sprinting else (float(bb.get("crouch", 0.55)) if crouching else 1.0)
	var side_ph: float = PI * (step_phase + float(step_index % 2))
	var down: float = 0.5 + 0.5 * cos(TAU * step_phase)
	var bp: Vector3 = _v3(bb.get("pos"), Vector3(0.006, 0.010, 0.0))
	var bro: Vector3 = _v3(bb.get("rot"), Vector3(0.9, 0.5, 1.1))
	pos += Vector3(bp.x * sin(side_ph), -bp.y * down, 0.0) * bob_w * mult
	deg += Vector3(-bro.x * down, bro.y * sin(side_ph), bro.z * sin(side_ph)) * bob_w * mult
	# The lowered sprint pose.
	var sp: Dictionary = cfg.get("sprint", {})
	sprint_w = move_toward(sprint_w, 1.0 if sprinting and speed > 2.5 else 0.0, dt * float(sp.get("blend", 6.0)))
	var se: float = sprint_w * sprint_w * (3.0 - 2.0 * sprint_w)
	pos += _v3(sp.get("pos"), Vector3(0.03, -0.07, 0.06)) * se
	deg += _v3(sp.get("rot"), Vector3(-20, 26, 12)) * se
	# Landing, recoil, jolts and the camera kick all spring back to rest.
	land.step(Vector3.ZERO, 120.0, 14.0, dt)
	recoil.step(Vector3.ZERO, 160.0, 18.0, dt)
	jolt.step(Vector3.ZERO, 140.0, 16.0, dt)
	kick.step(Vector3.ZERO, _kick_k, _kick_c, dt)
	pos += land.x + recoil.x
	deg += jolt.x
	# A new item comes up from below.
	if equip < 1.0:
		equip = minf(1.0, equip + dt / maxf(0.05, float(cfg.get("equip", 0.3))))
	var e: float = 1.0 - equip
	pos += Vector3(0.0, -0.16, 0.06) * e * e
	deg += Vector3(-28.0, 0.0, 0.0) * e * e
	# Reading the tether steadies the arms (no bob or sway to chase the screen).
	if reading > 0.0:
		var keep: float = 1.0 - 0.8 * reading
		pos *= keep
		deg *= keep
	_pos = pos
	_rot = deg


## The rig's offset this frame (rotations pivot near the chest so a lowered pose drops the arms).
func rig_transform(pivot: Vector3 = Vector3(0.0, -0.3, 0.05)) -> Transform3D:
	var b := Basis.from_euler(Vector3(deg_to_rad(_rot.x), deg_to_rad(_rot.y), deg_to_rad(_rot.z)))
	return Transform3D(b, _pos + pivot - b * pivot)


## The camera kick this frame (radians: pitch, yaw, roll).
func camera_kick() -> Vector3:
	return kick.x * (PI / 180.0)


func rig_rotation_deg() -> Vector3:
	return _rot


func rig_position() -> Vector3:
	return _pos
