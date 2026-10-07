class_name Player
extends CharacterBody3D
## First-person player body: movement, stances, stamina, footsteps, noise & scent emission into
## the stimulus fields, fall damage, damage intake and death. Presentation of the authoritative
## PlayerState (position/rotation are written back on save).

signal died(cause: String)
signal landed(impact_speed: float)

const STAND_HEIGHT: float = 1.75
const CROUCH_HEIGHT: float = 1.1
const RADIUS: float = 0.33
## Ledges up to this height are climbed by walking (door thresholds, porch steps, roots).
const STEP_HEIGHT: float = 0.38
## Obstacles up to this height can be vaulted or mantled with Jump (window sills, fences, crates).
const VAULT_MAX: float = 1.3
const VAULT_TIME: float = 0.55
const WORLD_MASK: int = (1 << 0) | (1 << 1) | (1 << 2)

var state: PlayerState
var cfg: Dictionary = {}
var crouching: bool = false
var sprinting: bool = false
## Set when sprinting empties stamina: no sprinting again until it has recovered to
## survival.json stamina.sprint_recover (holding Shift at empty stamina stutter-sprinted forever).
var _sprint_locked: bool = false
## Feet this far under the surface float the eyes just above it.
const SWIM_DEPTH: float = 1.35
var input_enabled: bool = true
var look_enabled: bool = true
var in_water_depth: float = 0.0
var god_mode: bool = false

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D
@onready var collision: CollisionShape3D = $Collision
@onready var interaction: PlayerInteraction = $Interaction
@onready var equipment: PlayerEquipment = $Equipment
## Raising a gun to the eye (ADR-0057): zoom, slower walk and turn.
var aim: PlayerAim = null

var _pitch: float = 0.0
var _step_dist: float = 0.0
var _bob_t: float = 0.0
var _was_on_floor: bool = true
var _fall_speed: float = 0.0
var _scent_t: float = 0.0
var _eye_height: float = 1.65
var _base_fov: float = 75.0
## The field of view before aiming narrows it (the sprint kick eases in and out of it).
var _fov: float = 75.0
var _shake: float = 0.0
## Active vault: control points (start, over the top, landing) and progress 0..1 (-1 = none).
var _vault_path: PackedVector3Array = []
var _vault_t: float = -1.0
var _vault_restand: bool = false
## Footsteps taken (the first-person bob alternates its sway with each one, ADR-0029).
var step_count: int = 0


func _ready() -> void:
	cfg = Content.config(&"player")
	_eye_height = float(cfg.get("eye_height", 1.65))
	floor_max_angle = deg_to_rad(46.0)
	floor_snap_length = 0.45
	collision_layer = 1 << 3
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 12)
	_base_fov = Settings.fov
	_fov = _base_fov
	camera.fov = _base_fov
	# The options screen can change the field of view mid-game.
	Settings.settings_changed.connect(_on_settings_changed)
	add_to_group(&"player")
	var sense := SleeperSense.new()
	sense.name = "SleeperSense"
	sense.player = self
	add_child(sense)
	aim = PlayerAim.new()
	aim.name = "Aim"
	add_child(aim)



func _on_settings_changed() -> void:
	_base_fov = Settings.fov

func bind_state(p_state: PlayerState) -> void:
	state = p_state
	global_position = state.position
	rotation.y = state.yaw
	_pitch = state.pitch
	head.rotation.x = _pitch
	state.stats.died.connect(_on_died)


## Holds the body still (no gravity, no fall building up) while the ground under it may not exist
## yet. A load places the player at the saved spot before the terrain's collision is there (a real
## renderer meshes it on worker threads): falling meanwhile, then being put back on the ground at
## full speed, killed the player on arrival and respawned them at the drop site (player report 3).
func freeze(on: bool) -> void:
	set_physics_process(not on)
	velocity = Vector3.ZERO
	_fall_speed = 0.0


func write_state() -> void:
	if state == null:
		return
	state.position = global_position
	state.yaw = rotation.y
	state.pitch = _pitch


# --- Input --------------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if not look_enabled or Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		return
	if event is InputEventMouseMotion:
		var m: InputEventMouseMotion = event
		var sens: float = Settings.mouse_sensitivity * (aim.look_mult() if aim != null else 1.0)
		rotation.y -= m.relative.x * sens
		_pitch = clampf(_pitch - m.relative.y * sens * (-1.0 if Settings.invert_y else 1.0), deg_to_rad(-88.0), deg_to_rad(88.0))
		head.rotation.x = _pitch


func _physics_process(delta: float) -> void:
	if state == null:
		return
	if _vault_t >= 0.0:
		_vault_step(delta)
		return
	var stats: SurvivalStats = state.stats
	var alive: bool = stats.alive or god_mode
	var dir := Vector2.ZERO
	var want_sprint: bool = false
	var want_crouch: bool = crouching
	var want_jump: bool = false
	if input_enabled and alive:
		dir = Input.get_vector(&"move_left", &"move_right", &"move_forward", &"move_back")
		want_sprint = Input.is_action_pressed(&"sprint") and dir.y < -0.1
		if Input.is_action_just_pressed(&"crouch"):
			want_crouch = not crouching
		want_jump = Input.is_action_just_pressed(&"jump")
	_set_crouch(want_crouch)
	var carrying: int = equipment.carried_logs() if equipment != null else 0
	var mods: Progression = state.progression
	var speed: float = float(cfg.get("walk_speed", 3.4))
	if stats.stamina <= 3.0:
		_sprint_locked = true
	elif _sprint_locked and stats.stamina >= float(Content.config(&"survival").get("stamina", {}).get("sprint_recover", 30.0)):
		_sprint_locked = false
	sprinting = want_sprint and not crouching and not _sprint_locked and not (aim != null and aim.wanted)
	if sprinting:
		speed = float(cfg.get("sprint_speed", 6.2))
	elif crouching:
		speed = float(cfg.get("crouch_speed", 1.7))
	speed *= 1.0 + mods.modifier("move_speed_mult")
	speed *= 1.0 - 0.12 * carrying
	if aim != null:
		speed *= aim.move_mult()
	var swimming: bool = in_water_depth > SWIM_DEPTH - 0.1
	if in_water_depth > 0.5:
		speed *= 0.55
		# Water breaks a fall: a dive into the lake is not a drop onto its bed.
		_fall_speed = 0.0
	if swimming and stats.stamina <= 3.0:
		speed *= 0.6
	if stats.has_status(&"exhausted") or stats.health < 20.0:
		speed *= 0.8
	var wish: Vector3 = (transform.basis * Vector3(dir.x, 0.0, dir.y))
	wish.y = 0.0
	wish = wish.normalized() * speed * minf(dir.length(), 1.0)
	var on_floor: bool = is_on_floor()
	var accel: float = 10.0 if on_floor else 2.5
	velocity.x = lerpf(velocity.x, wish.x, minf(1.0, accel * delta))
	velocity.z = lerpf(velocity.z, wish.z, minf(1.0, accel * delta))
	if not on_floor and not swimming:
		velocity.y -= 9.81 * delta
		_fall_speed = minf(_fall_speed, velocity.y)
	elif want_jump and _try_vault():
		return
	elif want_jump and not crouching and stats.spend_stamina(float(Content.config(&"survival").get("stamina", {}).get("jump", 8.0))):
		velocity.y = float(cfg.get("jump_velocity", 4.6))
		_emit_noise(float(cfg.get("noise", {}).get("walk", 6.0)), &"jump")
	if swimming:
		# Float at swimming depth (gravity is off in the water; it used to win and sink you to the
		# bed at ~3 m/s). Jump climbs higher, onto a bank. Stroking costs stamina; treading less.
		var rise: float = clampf((in_water_depth - SWIM_DEPTH) * 2.5, -1.5, 2.0)
		if input_enabled and alive and Input.is_action_pressed(&"jump"):
			rise = maxf(rise, 1.6)
		velocity.y = lerpf(velocity.y, rise, minf(1.0, 6.0 * delta))
		stats.tick_realtime(delta, 6.0 if dir.length() > 0.1 else 1.5)
	if on_floor:
		_try_step_up(delta)
	move_and_slide()
	_handle_landing()
	# Stamina.
	var sprint_cost: float = float(Content.config(&"survival").get("stamina", {}).get("sprint_per_sec", 9.0)) * (1.0 + mods.modifier("sprint_cost_mult"))
	var horizontal: float = Vector2(velocity.x, velocity.z).length()
	if not swimming:
		stats.tick_realtime(delta, sprint_cost if sprinting and horizontal > 2.0 else 0.0)
	_footsteps(delta, horizontal)
	_head_motion(delta, horizontal)
	_scent(delta, horizontal)


func _set_crouch(on: bool) -> void:
	if on == crouching:
		return
	if not on:
		# Only stand up if there is headroom.
		var q := PhysicsShapeQueryParameters3D.new()
		var s := CapsuleShape3D.new()
		s.radius = RADIUS * 0.9
		s.height = STAND_HEIGHT
		q.shape = s
		q.transform = Transform3D(Basis(), global_position + Vector3.UP * (STAND_HEIGHT * 0.5 + 0.05))
		q.collision_mask = (1 << 0) | (1 << 1) | (1 << 2)
		q.exclude = [get_rid()]
		if not get_world_3d().direct_space_state.intersect_shape(q, 1).is_empty():
			return
	crouching = on
	var cap: CapsuleShape3D = collision.shape
	cap.height = CROUCH_HEIGHT if on else STAND_HEIGHT
	collision.position.y = cap.height * 0.5


# --- Traversal: steps and vaults -------------------------------------------------------------

## A capsule stops dead at a 15 cm door threshold (the contact normal is too steep to count as
## floor), so when walking into a low ledge with headroom above and floor on top, lift the body
## onto it. The camera eases up instead of popping.
func _try_step_up(delta: float) -> void:
	var h := Vector3(velocity.x, 0.0, velocity.z)
	if h.length() < 0.3:
		return
	var motion: Vector3 = h.normalized() * maxf(h.length() * delta, RADIUS * 0.5)
	var xf: Transform3D = global_transform
	var hit := KinematicCollision3D.new()
	if not test_move(xf, motion, hit):
		return
	if hit.get_normal().angle_to(Vector3.UP) <= floor_max_angle:
		return
	var up := Vector3.UP * STEP_HEIGHT
	if test_move(xf, up):
		return
	var raised: Transform3D = xf.translated(up)
	if test_move(raised, motion):
		return
	var down := KinematicCollision3D.new()
	if not test_move(raised.translated(motion), -up, down):
		return
	if down.get_normal().angle_to(Vector3.UP) > floor_max_angle:
		return
	var rise: float = STEP_HEIGHT - down.get_travel().length()
	if rise < 0.03:
		return
	global_position.y += rise
	head.position.y -= rise


## Jump in front of a window sill, fence, car hood or crate up to VAULT_MAX: crouch, climb over and
## drop on the far side, or mantle onto the top if the far side is blocked. Returns true if a
## vault started.
func _try_vault() -> bool:
	var fwd: Vector3 = -global_transform.basis.z
	fwd.y = 0.0
	if fwd.length() < 0.1:
		return false
	fwd = fwd.normalized()
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var feet: Vector3 = global_position
	var low: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(feet + Vector3.UP * 0.4, feet + Vector3.UP * 0.4 + fwd * (RADIUS + 0.75), WORLD_MASK, [get_rid()]))
	if low.is_empty() or (low["normal"] as Vector3).angle_to(Vector3.UP) <= floor_max_angle:
		return false
	var cost: float = float(Content.config(&"survival").get("stamina", {}).get("jump", 8.0))
	if state.stats.stamina < cost:
		return false
	var face: Vector3 = low["position"]
	# Top of the obstacle just past its face; several depths so thin fence boards are found too.
	var rise: float = -1.0
	for depth: float in [0.03, 0.08, 0.15]:
		var probe: Vector3 = face + fwd * depth
		var from := Vector3(probe.x, feet.y + VAULT_MAX + 0.15, probe.z)
		var pq := PhysicsPointQueryParameters3D.new()
		pq.position = from
		pq.collision_mask = WORLD_MASK
		if not space.intersect_point(pq, 1).is_empty():
			return false  # solid above vault height: a wall, not a sill
		var top: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, Vector3(probe.x, feet.y + 0.25, probe.z), WORLD_MASK, [get_rid()]))
		if not top.is_empty():
			rise = maxf(rise, (top["position"] as Vector3).y - feet.y)
	if rise < 0.3 or rise > VAULT_MAX:
		return false
	var was_crouching: bool = crouching
	_set_crouch(true)
	if not crouching:
		return false
	_vault_restand = not was_crouching
	var lift := Vector3.UP * (rise + 0.08)
	var xf: Transform3D = global_transform
	if test_move(xf, lift):
		_set_crouch(was_crouching)
		return false
	var raised: Transform3D = xf.translated(lift)
	var to_face: float = maxf(0.0, (face - feet).dot(fwd))
	# Far side first (windows, fences), then onto the top (crates, car hoods, low roofs).
	for extra: float in [0.8, 1.1, 0.5, 0.25]:
		var across: Vector3 = fwd * (to_face + extra)
		if test_move(raised, across):
			continue
		var land := KinematicCollision3D.new()
		var drop := Vector3.DOWN * (rise + 1.6)
		if not test_move(raised.translated(across), drop, land):
			continue
		if land.get_normal().angle_to(Vector3.UP) > floor_max_angle:
			continue
		var over: Vector3 = raised.origin + across
		var end: Vector3 = over + drop.normalized() * land.get_travel().length()
		# Straight up (checked above), across at the top (checked), then down (checked).
		_vault_path = PackedVector3Array([feet, raised.origin, over, end])
		_vault_t = 0.0
		velocity = Vector3.ZERO
		state.stats.spend_stamina(cost)
		_emit_noise(float(cfg.get("noise", {}).get("vault", 8.0)), &"vault")
		Audio.play_3d(&"sfx/land_soft", global_position, {"volume_db": -8.0})
		return true
	_set_crouch(was_crouching)
	return false


func _vault_step(delta: float) -> void:
	_vault_t = minf(1.0, _vault_t + delta / VAULT_TIME)
	# Rise to the top in the first half, carry across and settle in the second.
	var p: Vector3
	if _vault_t < 0.45:
		p = _vault_path[0].lerp(_vault_path[1], ease(_vault_t / 0.45, 0.6))
	elif _vault_t < 0.8:
		p = _vault_path[1].lerp(_vault_path[2], (_vault_t - 0.45) / 0.35)
	else:
		p = _vault_path[2].lerp(_vault_path[3], ease((_vault_t - 0.8) / 0.2, 1.8))
	global_position = p
	_head_motion(delta, 0.0)
	if _vault_t >= 1.0:
		_vault_t = -1.0
		_vault_path = PackedVector3Array()
		_was_on_floor = true
		_fall_speed = 0.0
		if _vault_restand:
			_set_crouch(false)


func is_vaulting() -> bool:
	return _vault_t >= 0.0


func _handle_landing() -> void:
	var on_floor: bool = is_on_floor()
	if on_floor and not _was_on_floor:
		var impact: float = -_fall_speed
		landed.emit(impact)
		if impact > 9.5 and not god_mode:
			var dmg: float = (impact - 9.5) * 9.0
			var info := DamageInfo.make(dmg, &"fall", &"fall", state.id)
			take_damage(info)
		if impact > 3.0:
			_emit_noise(float(cfg.get("noise", {}).get("jump_land", 10.0)) * clampf(impact / 6.0, 0.5, 1.5), &"land")
			Audio.play_3d(&"sfx/land_hard" if impact > 7.0 else &"sfx/land_soft", global_position, {"volume_db": -4.0})
			_shake = clampf(impact * 0.02, 0.0, 0.3)
		_fall_speed = 0.0
	_was_on_floor = on_floor


# --- Footsteps, noise, scent ------------------------------------------------------------------

func _footsteps(delta: float, speed: float) -> void:
	if not is_on_floor() or speed < 0.4:
		return
	_step_dist += speed * delta
	if _step_dist < _stride():
		return
	_step_dist = 0.0
	step_count += 1
	var surface: String = _surface_under()
	var vol: float = -16.0 if crouching else (-6.0 if sprinting else -11.0)
	Audio.play_3d(StringName("sfx/footstep_" + surface), global_position, {"volume_db": vol, "max_distance": 40.0, "occlusion": false})
	var n: Dictionary = cfg.get("noise", {})
	var loud: float = float(n.get("crouch", 2.0)) if crouching else (float(n.get("sprint", 14.0)) if sprinting else float(n.get("walk", 6.0)))
	if surface in ["wood_floor", "gravel", "metal", "leaves"]:
		loud *= 1.3
	_emit_noise(loud, &"footstep")


## Metres per footstep for the current gait.
func _stride() -> float:
	return 0.75 if crouching else (1.3 if sprinting else 0.95)


## 0..1 through the current footstep (0 = a foot just landed), for the first-person bob.
func step_phase() -> float:
	return clampf(_step_dist / _stride(), 0.0, 1.0)


const SURFACE_SOUNDS: Dictionary = {
	"forest_floor": "forest_floor", "moss_ground": "forest_floor", "grass_ground": "grass", "dirt": "dirt",
	"mud": "dirt", "gravel": "gravel", "sand": "dirt", "asphalt_cracked": "concrete", "concrete_slab": "concrete",
	"snow": "leaves", "rock_cliff": "concrete",
	# Burnt soil and peat step like bare ground (ADR-0047): the forest floor's needle crunch read wrong
	# on both. Their own crunch and squelch sets are still to come.
	"ash_char": "dirt", "peat": "dirt",
}


func _surface_under() -> String:
	if in_water_depth > 0.15:
		return "water"
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(global_position + Vector3.UP * 0.3, global_position + Vector3.DOWN * 0.6, (1 << 0) | (1 << 1) | (1 << 2))
	q.exclude = [get_rid()]
	var hit: Dictionary = space.intersect_ray(q)
	if not hit.is_empty():
		var col: Object = hit["collider"]
		if col is Node and (col as Node).has_meta(&"surface"):
			return str((col as Node).get_meta(&"surface"))
	var world: Node = Game.world
	if world != null and world.get("terrain") != null:
		var layer: String = world.terrain.surface_at(global_position.x, global_position.z)
		return str(SURFACE_SOUNDS.get(layer, "forest_floor"))
	return "forest_floor"


func _emit_noise(loudness: float, kind: StringName) -> void:
	if Stimuli.current == null or state == null:
		return
	var mult: float = maxf(0.2, 1.0 + state.progression.modifier("noise_mult"))
	Stimuli.current.emit_sound(global_position, loudness * mult, kind, state.id)


func _scent(delta: float, speed: float) -> void:
	_scent_t += delta
	if _scent_t < 0.5 or Stimuli.current == null:
		return
	var amount: float = _scent_t * (1.0 + speed * 0.15 + state.stats.bleeding * 6.0) * (1.0 - state.stats.wetness * 0.6)
	if in_water_depth > 0.4:
		amount = 0.0
	Stimuli.current.deposit_scent(global_position, amount)
	Stimuli.current.recenter(global_position)
	_scent_t = 0.0


func _head_motion(delta: float, speed: float) -> void:
	var target_eye: float = (float(cfg.get("crouch_eye_height", 1.0)) if crouching else _eye_height)
	var bob_amt: float = Settings.head_bob * (0.0 if not is_on_floor() else clampf(speed / 6.0, 0.0, 1.0))
	_bob_t += delta * (8.5 if sprinting else 6.5) * clampf(speed / 3.0, 0.3, 1.6)
	var bob := Vector3(cos(_bob_t * 0.5) * 0.03, absf(sin(_bob_t)) * 0.045, 0.0) * bob_amt
	head.position = head.position.lerp(Vector3(0.0, target_eye, 0.0) + bob, minf(1.0, 12.0 * delta))
	if _shake > 0.0:
		_shake = maxf(0.0, _shake - delta)
		camera.h_offset = randf_range(-1.0, 1.0) * _shake * 0.1
		camera.v_offset = randf_range(-1.0, 1.0) * _shake * 0.1
	else:
		camera.h_offset = 0.0
		camera.v_offset = 0.0
	var target_fov: float = _base_fov + (6.0 if sprinting and speed > 4.0 else 0.0)
	_fov = lerpf(_fov, target_fov, minf(1.0, 6.0 * delta))
	# Aiming narrows it by the gun's zoom, eased with the raise itself (PlayerAim).
	camera.fov = aim.fov(_fov) if aim != null else _fov


# --- Damage / death ---------------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if state == null or god_mode or not state.stats.alive:
		return
	var resist: float = clampf(state.progression.modifier("damage_resist"), 0.0, 0.6)
	# A raised guard takes its share of a blow from the front, and of the wound (ADR-0029).
	var guarded: float = equipment.guard_factor(info) if equipment != null else 1.0
	var amount: float = info.amount * (1.0 - resist) * guarded
	state.stats.apply_damage(amount, info.cause)
	if info.type == &"zombie":
		var bleed: float = float(info.tool_power.get("bleed", 0.15)) * (1.0 - clampf(state.progression.modifier("bleed_resist"), 0.0, 0.8))
		state.stats.add_wound(bleed * guarded, float(info.tool_power.get("infection", 0.0)) * guarded)
	elif info.tool_power.has("infection"):
		# Spores and other non-bite exposure: Bloom infection without a bleeding wound.
		state.stats.add_wound(0.0, float(info.tool_power["infection"]))
	_shake = clampf(amount * 0.015, 0.05, 0.4)
	Audio.play_3d(&"voice/player_hurt", global_position, {"volume_db": -2.0, "occlusion": false})
	Events.player_damaged.emit(state.id, amount, info.to_dict())


func _on_died(cause: String) -> void:
	input_enabled = false
	Audio.play_2d(&"voice/player_death", 0.0, &"SFX")
	Events.player_died.emit(state.id, cause)
	died.emit(cause)


func is_crouching() -> bool:
	return crouching


func horizontal_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


func eye_position() -> Vector3:
	return camera.global_position


func look_direction() -> Vector3:
	return -camera.global_transform.basis.z
