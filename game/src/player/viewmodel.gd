class_name ViewModel
extends Node3D
## First-person presentation of the held item: idle sway, walk bob, swing/recoil animation.
## Uses the generated viewmodel model (models/viewmodels/<id>.glb) or the item model, and the
## generated first-person arms when present (models/characters/fp_arms.glb).

var _item_root: Node3D
var _swing_t: float = -1.0
var _swing_len: float = 0.8
var _recoil: float = 0.0
var _lit: bool = false
var _rest := Transform3D(Basis.from_euler(Vector3(deg_to_rad(8.0), deg_to_rad(-12.0), deg_to_rad(4.0))), Vector3(0.28, -0.3, -0.52))
var _t: float = 0.0
var _prev_cam_basis := Basis()


func _ready() -> void:
	_item_root = Node3D.new()
	_item_root.name = "Held"
	add_child(_item_root)
	_item_root.transform = _rest


func show_item(item_id: StringName) -> void:
	for c: Node in _item_root.get_children():
		c.queue_free()
	if item_id == &"":
		return
	var def: ItemDef = Content.item(item_id)
	var vm_id: String = str(def.equip.get("viewmodel", "")) if def != null else ""
	var node: Node3D = null
	if vm_id != "" and ResourceLoader.exists("res://assets/generated/models/viewmodels/%s.glb" % vm_id):
		node = (load("res://assets/generated/models/viewmodels/%s.glb" % vm_id) as PackedScene).instantiate()
		node.rotation_degrees = Vector3(-70.0, 0.0, 0.0)
	else:
		node = ItemVisuals.make_model(item_id)
		node.rotation_degrees = Vector3(-60.0, 20.0, 0.0)
	_set_layers(node)
	_item_root.add_child(node)


func _set_layers(n: Node) -> void:
	if n is GeometryInstance3D:
		var g: GeometryInstance3D = n
		g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for c: Node in n.get_children():
		_set_layers(c)


func play_swing(duration: float) -> void:
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
	if _recoil > 0.0:
		_recoil = maxf(0.0, _recoil - delta * 6.0)
		tr.basis = tr.basis * Basis(Vector3.RIGHT, _recoil * 0.35)
		tr.origin += Vector3(0.0, 0.0, _recoil * 0.06)
	_item_root.transform = _item_root.transform.interpolate_with(tr, minf(1.0, 20.0 * delta))
