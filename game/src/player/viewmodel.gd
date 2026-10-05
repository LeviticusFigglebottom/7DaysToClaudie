class_name ViewModel
extends Node3D
## First-person presentation of the held item: idle sway, walk bob, swing/recoil animation.
## Uses the generated first-person arms (models/characters/fp_arms.glb, docs/CHARACTERS.md) with
## the item parented to their `socket_hand.R`, and their fp_* actions for idle/walk/swing. Without
## the arms model the item floats at a rest pose and swings procedurally.
## Items use their viewmodel model (models/viewmodels/<id>.glb) or the plain item model.

const ARMS_PATH: String = "res://assets/generated/models/characters/fp_arms.glb"
const LOOPING: Array[StringName] = [&"fp_idle", &"fp_walk_bob", &"fp_carry_log"]

var _item_root: Node3D
var _rig: Node3D
var _arms: Node3D = null
var _arms_anim: AnimationPlayer = null
var _hand: Node3D = null
var _held: Node3D = null
var _held_def: ItemDef = null
var _swing_t: float = -1.0
var _swing_len: float = 0.8
var _recoil: float = 0.0
var _lit: bool = false
var _rest := Transform3D(Basis.from_euler(Vector3(deg_to_rad(8.0), deg_to_rad(-12.0), deg_to_rad(4.0))), Vector3(0.28, -0.3, -0.52))
var _t: float = 0.0
var _prev_cam_basis := Basis()
var _one_shot: bool = false
var _hold: bool = false


func _ready() -> void:
	_rig = Node3D.new()
	_rig.name = "Rig"
	add_child(_rig)
	_item_root = Node3D.new()
	_item_root.name = "Held"
	add_child(_item_root)
	_item_root.transform = _rest
	if ResourceLoader.exists(ARMS_PATH):
		_arms = (load(ARMS_PATH) as PackedScene).instantiate() as Node3D
		_arms.name = "Arms"
		# Authored looking down Blender -Y, which imports facing +Z: turn it to the camera's -Z.
		_arms.rotation_degrees = Vector3(0.0, 180.0, 0.0)
		_rig.add_child(_arms)
		_set_layers(_arms)
		_hand = _find_socket(_arms, "socket_hand.R")
		_arms_anim = _arms.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if _arms_anim != null:
			for a: StringName in LOOPING:
				if _arms_anim.has_animation(a):
					_arms_anim.get_animation(a).loop_mode = Animation.LOOP_LINEAR
			_arms_anim.animation_finished.connect(func(_n: StringName) -> void: _one_shot = _hold)
			_play(&"fp_idle")


## Bone-attached empties import under BoneAttachment3D, with "." replaced in their names.
static func _find_socket(root: Node, socket: String) -> Node3D:
	var n: Node = root.find_child(socket, true, false)
	if n == null:
		n = root.find_child(socket.replace(".", "_"), true, false)
	return n as Node3D


func show_item(item_id: StringName) -> void:
	if _held != null:
		_held.queue_free()
		_held = null
	_held_def = null
	if item_id == &"":
		return
	var def: ItemDef = Content.item(item_id)
	_held_def = def
	var vm_id: String = str(def.equip.get("viewmodel", "")) if def != null else ""
	var vm_path: String = "res://assets/generated/models/viewmodels/%s.glb" % vm_id
	var node: Node3D = null
	var is_vm: bool = vm_id != "" and ResourceLoader.exists(vm_path)
	if is_vm:
		node = (load(vm_path) as PackedScene).instantiate() as Node3D
		if _hand == null:
			node.rotation_degrees = _rest_pose(node, def)
	else:
		node = ItemVisuals.make_model(item_id)
		node.rotation_degrees = Vector3(-60.0, 20.0, 0.0)
	_set_layers(node)
	_held = node
	# Viewmodels are authored in the hand-socket frame (grip at the origin), so they sit in the
	# hand at identity; plain item models (food, placeables) rest on the palm, scaled down.
	if _hand != null:
		_hand.add_child(node)
		if not is_vm:
			node.rotation_degrees = Vector3.ZERO
			node.scale = Vector3.ONE * 0.8
		else:
			node.rotation_degrees = grip_rotation(def)
	else:
		_item_root.add_child(node)


## Orientation of a viewmodel in the hand socket (equip.grip_rot, degrees). Tools stand on their
## handle along the socket's +Y (towards the thumb); pointing items (barrel, beam) aim along +Z,
## which is the back of the hand, so guns and lights turn +90 deg about Y to aim along the
## fingers, and a spear turns its shaft forward.
static func grip_rotation(def: ItemDef) -> Vector3:
	var g: Array = def.equip.get("grip_rot", []) if def != null else []
	return Vector3(float(g[0]), float(g[1]), float(g[2])) if g.size() == 3 else Vector3.ZERO


## Floating pose for a viewmodel when there are no arms. Viewmodels import facing the camera:
## melee tools stand on their handle (+Y) with the edge toward +Z; pointing items (muzzle, beam,
## flame sockets) aim along +Z. Turn them around and tilt them into a carried pose.
static func _rest_pose(node: Node3D, def: ItemDef) -> Vector3:
	var pointing: bool = false
	for s: String in ["socket_muzzle", "socket_light", "socket_flame"]:
		if node.find_child(s, true, false) != null:
			pointing = true
	if def != null and def.id == &"torch":
		return Vector3(-50.0, 180.0, 0.0)
	if pointing:
		return Vector3(0.0, 180.0, 0.0)
	if def != null and str(def.equip.get("damage_type", "")) == "pierce":
		return Vector3(-80.0, 0.0, 0.0)
	return Vector3(30.0, 180.0, 0.0)


func _set_layers(n: Node) -> void:
	if n is GeometryInstance3D:
		var g: GeometryInstance3D = n
		g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for c: Node in n.get_children():
		_set_layers(c)


func _play(anim_name: StringName, speed: float = 1.0, blend: float = 0.15) -> void:
	if _arms_anim == null or not _arms_anim.has_animation(anim_name):
		return
	if _arms_anim.current_animation == anim_name and _arms_anim.is_playing():
		_arms_anim.speed_scale = speed
		return
	_arms_anim.play(anim_name, blend)
	_arms_anim.speed_scale = speed


## Plays a one-shot arms action (fp_swing, fp_stab, fp_use, fp_raise_wrist...); with `hold` the
## arms stay on its last frame until the next action. Returns false if the arms or the action are
## missing so callers can fall back.
func play_action(anim_name: StringName, duration: float = 0.0, hold: bool = false) -> bool:
	if _arms_anim == null or not _arms_anim.has_animation(anim_name):
		return false
	_hold = hold
	var length: float = _arms_anim.get_animation(anim_name).length
	_arms_anim.play(anim_name, 0.08)
	_arms_anim.speed_scale = length / duration if duration > 0.05 else 1.0
	_one_shot = true
	return true


func play_swing(duration: float) -> void:
	var held_pierce: bool = _held_def != null and str(_held_def.equip.get("damage_type", "")) == "pierce"
	if play_action(&"fp_stab" if held_pierce else &"fp_swing", duration):
		return
	_swing_t = 0.0
	_swing_len = maxf(0.2, duration)


func play_recoil() -> void:
	_recoil = 1.0


func set_lit(on: bool) -> void:
	_lit = on


func _process(delta: float) -> void:
	_t += delta
	var player: Player = owner as Player if owner is Player else null
	var speed: float = player.horizontal_speed() if player != null else 0.0
	var bob := Vector3(sin(_t * 6.0) * 0.006, absf(cos(_t * 6.0)) * 0.008, 0.0) * clampf(speed / 3.0, 0.0, 1.5)
	var breathe := Vector3(0.0, sin(_t * 1.3) * 0.003, 0.0)
	# Sway: lag behind camera rotation.
	var cam: Camera3D = get_parent() as Camera3D
	var sway := Vector3.ZERO
	if cam != null:
		var d: Basis = _prev_cam_basis.inverse() * cam.global_transform.basis
		var e: Vector3 = d.get_euler()
		sway = Vector3(-e.y * 0.6, e.x * 0.6, 0.0).limit_length(0.05)
		_prev_cam_basis = cam.global_transform.basis
	if _arms_anim != null and not _one_shot:
		if player != null and player.equipment != null and player.equipment.carried_logs() > 0:
			_play(&"fp_carry_log")
		else:
			_play(&"fp_walk_bob" if speed > 0.6 else &"fp_idle", clampf(speed / 3.0, 0.6, 1.6) if speed > 0.6 else 1.0)
	var rig := Transform3D(Basis(), sway + (breathe if _arms != null else Vector3.ZERO))
	if _recoil > 0.0:
		_recoil = maxf(0.0, _recoil - delta * 6.0)
		rig.basis = Basis(Vector3.RIGHT, _recoil * 0.2)
		rig.origin += Vector3(0.0, 0.0, _recoil * 0.05)
	_rig.transform = _rig.transform.interpolate_with(rig, minf(1.0, 20.0 * delta))
	var tr: Transform3D = _rest
	tr.origin += bob + breathe + sway
	if _swing_t >= 0.0:
		_swing_t += delta
		var k: float = clampf(_swing_t / _swing_len, 0.0, 1.0)
		# Wind-up (0..0.35), strike (0.35..0.5), recover.
		var a: float
		if k < 0.35:
			a = -ease(k / 0.35, 0.5) * 0.9
		elif k < 0.5:
			a = lerpf(-0.9, 0.8, (k - 0.35) / 0.15)
		else:
			a = lerpf(0.8, 0.0, ease((k - 0.5) / 0.5, 0.4))
		tr.basis = tr.basis * Basis(Vector3.RIGHT, a) * Basis(Vector3.FORWARD, -a * 0.35)
		tr.origin += Vector3(-a * 0.08, a * 0.05, -absf(a) * 0.06)
		if k >= 1.0:
			_swing_t = -1.0
	if _recoil > 0.0 and _arms == null:
		tr.basis = tr.basis * Basis(Vector3.RIGHT, _recoil * 0.35)
		tr.origin += Vector3(0.0, 0.0, _recoil * 0.06)
	_item_root.transform = _item_root.transform.interpolate_with(tr, minf(1.0, 20.0 * delta))
