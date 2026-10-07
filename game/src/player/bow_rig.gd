class_name BowRig
extends Node3D
## The held bow's string and nocked arrow (ADR-0057), strung to the drawing hand every frame rather
## than baked, so they follow any arms action: the idle's light hold, a draw frozen at its
## fraction, the snap back after a release (the string quivers a moment). Lives under the held bow,
## in its tool frame: grip at the origin, limbs along +-Y, the face toward the target along +Z, the
## string behind on the archer's side (-Z). The bow itself is the item's first-person model
## (models/<item model>_fp.glb, item_hunting), shown in place of the ground model the viewmodel
## made; before `make assets` a plain bow (riser and two bent limbs).

## Tip height above / below the grip, how far the tips sit back of the grip, the string's height
## of the nocking point and the arrow rest (on the fist, on the bow's left side).
const TIP_Y: float = 0.6
const TIP_BACK: float = 0.1
const NOCK_Y: float = 0.045
const REST := Vector3(0.0, 0.05, 0.02)
const REST_SIDE: float = 0.014
## The drawing hand's socket is the middle of its hooked fingers: the string sits a little
## further in, under the first joints.
const HAND_IN: float = 0.01
const QUIVER_TIME: float = 0.3

## Shows the nocked arrow (PlayerEquipment's BowHandler clears it after a release until the next
## arrow is on the string, and when none are carried).
var nocked: bool = true:
	set(v):
		nocked = v
		if _arrow != null:
			_arrow.visible = v
## The nocked arrow's item (its model).
var arrow_item: StringName = &"arrow_stone"
## How far back the string is drawn (m behind its brace), for tests and the HUD.
var drawn: float = 0.0

var _hand: Node3D = null
var _top: MeshInstance3D
var _bottom: MeshInstance3D
var _arrow: Node3D = null
var _quiver_t: float = -1.0
var _quiver_amp: float = 0.0


## Strings `held` (a bow `def` just made for the viewmodel) to `hand` (the drawing hand's
## socket). Built at once so FpMaterials sees the meshes.
static func attach(held: Node3D, hand: Node3D, def: ItemDef) -> BowRig:
	var rig := BowRig.new()
	rig.name = "BowRig"
	rig._hand = hand
	rig._build(held, fp_model_path(def))
	held.add_child(rig)
	return rig


## The rig on a held item, if it is a bow.
static func of(held: Node) -> BowRig:
	return held.get_node_or_null(^"BowRig") as BowRig if held != null else null


func set_hand(hand: Node3D) -> void:
	_hand = hand


func set_arrow_item(item: StringName) -> void:
	if item == arrow_item and _arrow != null:
		return
	arrow_item = item
	if _arrow != null:
		_arrow.queue_free()
	_arrow = Arrow.make_visual(item)
	_arrow.name = "NockedArrow"
	_arrow.visible = nocked
	add_child(_arrow)
	_apply_fp(_arrow)


## The bow's first-person model (tool frame), "" when not built yet.
static func fp_model_path(def: ItemDef) -> String:
	if def == null or def.model == "":
		return ""
	var path: String = "res://assets/generated/models/%s_fp.glb" % def.model
	return path if ResourceLoader.exists(path) else ""


func _build(held: Node3D, fp_path: String) -> void:
	var cord := StandardMaterial3D.new()
	cord.albedo_color = Color(0.5, 0.43, 0.32)
	cord.roughness = 0.8
	_top = _segment(cord, 0.0017)
	_bottom = _segment(cord, 0.0017)
	_arrow = Arrow.make_visual(arrow_item)
	_arrow.name = "NockedArrow"
	add_child(_arrow)
	# The ground model the viewmodel made lies on its side: the bow in hand is the canonical one.
	for c: Node in held.get_children():
		if c is Node3D:
			(c as Node3D).visible = false
	var ps: PackedScene = load(fp_path) as PackedScene if fp_path != "" else null
	if ps != null:
		add_child(ps.instantiate())
	else:
		_build_plain_bow()
	_update(0.0)


func _segment(mat: Material, r: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r
	cm.bottom_radius = r
	cm.height = 1.0
	cm.radial_segments = 5
	cm.rings = 1
	cm.material = mat
	mi.mesh = cm
	add_child(mi)
	return mi


## Riser and limbs, bent back toward the archer (a strung self bow) along the same curve the
## tips sit on.
func _build_plain_bow() -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.46, 0.33, 0.2)
	wood.roughness = 0.75
	var wrap := StandardMaterial3D.new()
	wrap.albedo_color = Color(0.36, 0.27, 0.19)
	wrap.roughness = 0.95
	var n: int = 8
	for sgn: float in [1.0, -1.0]:
		for i: int in n:
			var t0: float = float(i) / n
			var t1: float = float(i + 1) / n
			var a := _limb_point(sgn * t0)
			var b := _limb_point(sgn * t1)
			var r: float = lerpf(0.016, 0.008, (t0 + t1) * 0.5)
			var seg := _segment(wood, r)
			_place(seg, a, b)
	var grip := _segment(wrap, 0.019)
	_place(grip, Vector3(0, -0.07, 0.0), Vector3(0, 0.07, 0.0))


## A point on the limb at u in [-1, 1] (tip to tip): back toward the archer by TIP_BACK at the tips.
static func _limb_point(u: float) -> Vector3:
	return Vector3(0.0, u * TIP_Y, -TIP_BACK * u * u)


## The nocking point now: on the drawing hand while it holds the string, else at brace.
func nock_point() -> Vector3:
	var rest := Vector3(0.0, NOCK_Y, -TIP_BACK)
	if _hand == null or not is_instance_valid(_hand) or not _hand.is_inside_tree() or not is_inside_tree():
		return rest
	var h: Vector3 = global_transform.affine_inverse() * _hand.global_position
	# Holding the string: close to the bow's plane, level with the grip, behind the string's line.
	if absf(h.x) < 0.05 and h.y > -0.2 and h.y < 0.25 and h.z < -TIP_BACK + 0.05 and h.z > -0.95:
		return Vector3(0.0, clampf(h.y, -0.06, 0.12), minf(h.z + HAND_IN, -TIP_BACK))
	return rest


func _process(delta: float) -> void:
	_update(delta)


func _update(delta: float) -> void:
	var nock: Vector3 = nock_point()
	var was: float = drawn
	drawn = -TIP_BACK - nock.z
	# Let go from a draw: the string snaps through and quivers.
	if was > 0.06 and drawn < 0.01:
		_quiver_t = 0.0
		_quiver_amp = minf(0.02, was * 0.05)
	if _quiver_t >= 0.0:
		_quiver_t += delta
		if _quiver_t > QUIVER_TIME:
			_quiver_t = -1.0
		else:
			nock.z += _quiver_amp * sin(_quiver_t * 90.0) * (1.0 - _quiver_t / QUIVER_TIME)
	_place(_top, _limb_point(1.0), nock)
	_place(_bottom, _limb_point(-1.0), nock)
	if _arrow != null:
		# Nock on the string, shaft through the rest on the bow's left (toward the camera's left).
		var side: float = REST_SIDE
		var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
		if cam != null:
			var left: Vector3 = global_transform.basis.inverse() * (-cam.global_transform.basis.x)
			side = REST_SIDE * signf(left.x if absf(left.x) > 0.001 else 1.0)
		var rest: Vector3 = REST + Vector3(side, 0.0, 0.0)
		var dir: Vector3 = (rest - nock).normalized()
		var tip: Vector3 = nock + dir * Arrow.LENGTH
		_arrow.transform = Transform3D(_basis_z(-dir), tip)


## A basis whose +Z is `z` (unit).
static func _basis_z(z: Vector3) -> Basis:
	var up: Vector3 = Vector3.UP if absf(z.y) < 0.95 else Vector3.RIGHT
	var x: Vector3 = up.cross(z).normalized()
	return Basis(x, z.cross(x), z)


## Stretches a unit cylinder (axis +Y) from a to b.
static func _place(mi: MeshInstance3D, a: Vector3, b: Vector3) -> void:
	var d: Vector3 = b - a
	var l: float = maxf(d.length(), 0.0001)
	var y: Vector3 = d / l
	var ref: Vector3 = Vector3.FORWARD if absf(y.dot(Vector3.FORWARD)) < 0.95 else Vector3.RIGHT
	var x: Vector3 = y.cross(ref).normalized()
	var z: Vector3 = x.cross(y)
	mi.transform = Transform3D(Basis(x, y * l, z), (a + b) * 0.5)


func _apply_fp(n: Node) -> void:
	# Built after the viewmodel converted the held item's materials: convert this one too.
	FpMaterials.apply(n)
