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

var state: PlayerState
var cfg: Dictionary = {}
var crouching: bool = false
var sprinting: bool = false
var input_enabled: bool = true
var look_enabled: bool = true
var in_water_depth: float = 0.0
var god_mode: bool = false

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D
@onready var collision: CollisionShape3D = $Collision
@onready var interaction: PlayerInteraction = $Interaction
@onready var equipment: PlayerEquipment = $Equipment

var _pitch: float = 0.0
var _step_dist: float = 0.0
var _bob_t: float = 0.0
var _was_on_floor: bool = true
var _fall_speed: float = 0.0
var _scent_t: float = 0.0
var _eye_height: float = 1.65
var _base_fov: float = 75.0
var _shake: float = 0.0


func _ready() -> void:
	cfg = Content.config(&"player")
	_eye_height = float(cfg.get("eye_height", 1.65))
	floor_max_angle = deg_to_rad(46.0)
	floor_snap_length = 0.45
	collision_layer = 1 << 3
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 11)
	_base_fov = Settings.fov
	camera.fov = _base_fov
	add_to_group(&"player")


func bind_state(p_state: PlayerState) -> void:
	state = p_state
	global_position = state.position
	rotation.y = state.yaw
	_pitch = state.pitch
	head.rotation.x = _pitch
	state.stats.died.connect(_on_died)


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
		var sens: float = Settings.mouse_sensitivity
		rotation.y -= m.relative.x * sens
		_pitch = clampf(_pitch - m.relative.y * sens * (-1.0 if Settings.invert_y else 1.0), deg_to_rad(-88.0), deg_to_rad(88.0))
		head.rotation.x = _pitch


func _physics_process(delta: float) -> void:
	if state == null:
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
	sprinting = want_sprint and not crouching and stats.stamina > 3.0
	if sprinting:
		speed = float(cfg.get("sprint_speed", 6.2))
	elif crouching:
		speed = float(cfg.get("crouch_speed", 1.7))
	speed *= 1.0 + mods.modifier("move_speed_mult")
	speed *= 1.0 - 0.12 * carrying
	if in_water_depth > 0.5:
		speed *= 0.55
	if stats.has_status(&"exhausted") or stats.health < 20.0:
		speed *= 0.8
	var wish: Vector3 = (transform.basis * Vector3(dir.x, 0.0, dir.y))
	wish.y = 0.0
	wish = wish.normalized() * speed * minf(dir.length(), 1.0)
	var on_floor: bool = is_on_floor()
	var accel: float = 10.0 if on_floor else 2.5
	velocity.x = lerpf(velocity.x, wish.x, minf(1.0, accel * delta))
	velocity.z = lerpf(velocity.z, wish.z, minf(1.0, accel * delta))
	if not on_floor:
		velocity.y -= 9.81 * delta
		_fall_speed = minf(_fall_speed, velocity.y)
	elif want_jump and not crouching and stats.spend_stamina(float(Content.config(&"survival").get("stamina", {}).get("jump", 8.0))):
		velocity.y = float(cfg.get("jump_velocity", 4.6))
		_emit_noise(float(cfg.get("noise", {}).get("walk", 6.0)), &"jump")
	if in_water_depth > 1.3:
		# Swimming: buoyancy toward the surface, stamina drain.
		velocity.y = lerpf(velocity.y, 1.2 if Input.is_action_pressed(&"jump") else 0.3, minf(1.0, 3.0 * delta))
		stats.tick_realtime(delta, 6.0)
	move_and_slide()
	_handle_landing()
	# Stamina.
	var sprint_cost: float = float(Content.config(&"survival").get("stamina", {}).get("sprint_per_sec", 9.0)) * (1.0 + mods.modifier("sprint_cost_mult"))
	var horizontal: float = Vector2(velocity.x, velocity.z).length()
	if in_water_depth <= 1.3:
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
	var stride: float = 0.75 if crouching else (1.3 if sprinting else 0.95)
	if _step_dist < stride:
		return
	_step_dist = 0.0
	var surface: String = _surface_under()
	var vol: float = -16.0 if crouching else (-6.0 if sprinting else -11.0)
	Audio.play_3d(StringName("sfx/footstep_" + surface), global_position, {"volume_db": vol, "max_distance": 40.0, "occlusion": false})
	var n: Dictionary = cfg.get("noise", {})
	var loud: float = float(n.get("crouch", 2.0)) if crouching else (float(n.get("sprint", 14.0)) if sprinting else float(n.get("walk", 6.0)))
	if surface in ["wood_floor", "gravel", "metal", "leaves"]:
		loud *= 1.3
	_emit_noise(loud, &"footstep")


const SURFACE_SOUNDS: Dictionary = {
	"forest_floor": "forest_floor", "moss_ground": "forest_floor", "grass_ground": "grass", "dirt": "dirt",
	"mud": "dirt", "gravel": "gravel", "sand": "dirt", "asphalt_cracked": "concrete", "concrete_slab": "concrete",
	"snow": "leaves", "rock_cliff": "concrete",
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
	camera.fov = lerpf(camera.fov, target_fov, minf(1.0, 6.0 * delta))


# --- Damage / death ---------------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if state == null or god_mode or not state.stats.alive:
		return
	var resist: float = clampf(state.progression.modifier("damage_resist"), 0.0, 0.6)
	var amount: float = info.amount * (1.0 - resist)
	state.stats.apply_damage(amount, info.cause)
	if info.type == &"zombie":
		var bleed: float = float(info.tool_power.get("bleed", 0.15)) * (1.0 - clampf(state.progression.modifier("bleed_resist"), 0.0, 0.8))
		state.stats.add_wound(bleed, float(info.tool_power.get("infection", 0.0)))
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
