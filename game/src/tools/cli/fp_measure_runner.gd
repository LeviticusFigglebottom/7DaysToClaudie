extends Node
## Runner for fp_measure.gd: freezes each key, then measures the right hand against its target,
## and for a hand on the bolt knob how the key reads from the camera (TD-294: a hand measured on the
## knob still read as a hand on the scope when the knob sat behind the ocular bell from the eye).

const VM_JSON: String = "res://data/config/viewmodel.json"
## The viewmodel's frame in tan units (58 deg vertical FOV at 16:9).
const VIEW_TAN := Vector2(0.985, 0.554)
## A hand on the knob reads as on the knob with this much screen gap (m at the knob's depth) to the
## scope's footprint: about the fist's half-width round the knob.
const KNOB_GAP_MIN: float = 0.02

var _vm: ViewModel
## The misses measured, for --fix: [{use, frame, miss} or {hold, miss}].
var _fixes: Array = []
var _cam: Camera3D


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var item: String = _arg(args, "--item", "hunting_rifle")
	var uses: PackedStringArray = _arg(args, "--uses", "").split(",", false)
	var fix: bool = args.has("--fix")
	_cam = Camera3D.new()
	add_child(_cam)
	_cam.make_current()
	_vm = (load("res://src/player/viewmodel.gd") as GDScript).new() as ViewModel
	_cam.add_child(_vm)
	await _frames(4)
	_vm.show_item(StringName(item))
	_vm.motion.equip = 1.0
	await _frames(10)
	var text: String = FileAccess.get_file_as_string(VM_JSON)
	var data: Dictionary = JSON.parse_string(text)
	var worst: float = 0.0
	var read_fails: int = 0
	# The hold's own idle first: its right hand is meant on the stock's wrist (holds.<class>.pose.R).
	var hold_name: String = _arg(args, "--hold", "")
	if hold_name != "":
		var hr: Dictionary = (((data["holds"] as Dictionary).get(hold_name, {}) as Dictionary).get("pose", {}) as Dictionary).get("R", {})
		if not hr.is_empty():
			# The hold's base loop (fp_<hold>) at its first frame.
			_vm.freeze_action(StringName("fp_" + hold_name), 0.0)
			await _frames(3)
			var m0: Vector3 = _miss("grip")
			var rig1: Node3D = _vm.get(&"_rig") as Node3D
			var lh: Node3D = (_vm.get(&"_sock") as Dictionary).get("L", null)
			var rh: Node3D = (_vm.get(&"_sock") as Dictionary).get("R", null)
			if lh != null and rh != null:
				print("FP_MEASURE hold %s baked L %s R %s" % [hold_name, rig1.global_transform.affine_inverse() * lh.global_position, rig1.global_transform.affine_inverse() * rh.global_position])
				var inv1: Transform3D = rig1.global_transform.affine_inverse()
				var held1: Node3D = _vm.held_item()
				for sn: String in ["socket_muzzle", "socket_grip_r", "socket_sight"]:
					var sk: Node3D = held1.find_child(sn, true, false) as Node3D
					if sk != null:
						print("FP_MEASURE hold %s %s %s" % [hold_name, sn, inv1 * sk.global_position])
				print("FP_MEASURE hold %s knob %s" % [hold_name, inv1 * knob(held1)])
				var bolt1: Node3D = held1.find_child("bolt", true, false) as Node3D
				if bolt1 != null:
					var bx: Transform3D = inv1 * bolt1.global_transform
					print("FP_MEASURE hold %s bolt origin %s axis %s" % [hold_name, bx.origin, bx.basis.z.normalized()])
				print("FP_MEASURE hold %s L basis %s" % [hold_name, (inv1 * lh.global_transform).basis.orthonormalized()])
			worst = maxf(worst, m0.length())
			print("FP_MEASURE hold %s grip %.1f cm  [%.3f, %.3f, %.3f]" % [hold_name, m0.length() * 100.0, m0.x, m0.y, m0.z])
			_fixes.append({"hold": hold_name, "miss": [m0.x, m0.y, m0.z]})
	for use: String in uses:
		var u: Dictionary = (data["uses"] as Dictionary).get(use, {})
		for key: Array in u.get("keys", []):
			var r: Variant = (key[1] as Dictionary).get("R")
			if not r is Dictionary:
				continue
			var target: String = target_of(r as Dictionary)
			if target == "":
				continue
			_vm.freeze_action(StringName("fp_" + use), float(key[0]) / 30.0)
			await _frames(3)
			var miss: Vector3 = _miss(target)
			worst = maxf(worst, miss.length())
			print("FP_MEASURE %s f%d %s %.1f cm  [%.3f, %.3f, %.3f] (item in %s)" % [use, int(key[0]), target, miss.length() * 100.0, miss.x, miss.y, miss.z, _item_hand()])
			if target == "knob":
				var rd: Dictionary = _read()
				var ok: bool = rd["gap"] >= KNOB_GAP_MIN and rd["l_in"] and rd["r_low"]
				read_fails += 0 if ok else 1
				print("FP_READ %s f%d knob gap %.1f cm | L screen (%.2f, %.2f) %s | R elbow %.1f cm below the wrist, %.2f m deep | %s" % [
					use, int(key[0]), rd["gap"] * 100.0, rd["l"].x, rd["l"].y, "in" if rd["l_in"] else "OUT",
					rd["drop"] * 100.0, rd["depth"], "ok" if ok else "FAIL"])
			var tgt: Vector3 = _target_pos(target)
			_fixes.append({"use": use, "frame": int(key[0]), "miss": [miss.x, miss.y, miss.z], "target": [tgt.x, tgt.y, tgt.z]})
		_vm.release_action()
		await _frames(2)
	print("FP_MEASURE worst %.1f cm" % (worst * 100.0))
	print("FP_READ %d knob key(s) failing" % read_fails)
	if fix:
		# Only the misses are written: tools/fp_fix_grips.py adds them to viewmodel.json keeping its
		# formatting (Godot's JSON writer would rewrite every number in the file).
		var f := FileAccess.open(_arg(args, "--fix-out", "user://fp_measure_fix.json"), FileAccess.WRITE)
		f.store_string(JSON.stringify(_fixes))
		f.close()
		print("FP_MEASURE fixes written (%d)" % _fixes.size())
	print("FP_MEASURE done")
	get_tree().quit(0)


## What a right-hand key's fist is meant on: the bolt knob (a working grip, fist 0.72), the
## stock's wrist (a firing grip, fist 0.9+), or nothing (fetching a round, thumbing it in).
static func target_of(r: Dictionary) -> String:
	var fist: float = float(r.get("fist", 0.0))
	if absf(fist - 0.72) < 0.015:
		return "knob"
	if fist >= 0.9:
		return "grip"
	return ""


## Where a target is now, in the rig's own space.
func _target_pos(target: String) -> Vector3:
	var rig: Node3D = _vm.get(&"_rig") as Node3D
	var held: Node3D = _vm.held_item()
	var inv: Transform3D = rig.global_transform.affine_inverse()
	if target == "knob":
		return inv * knob(held)
	var s: Node3D = held.find_child("socket_grip_r", true, false) as Node3D
	return inv * s.global_position if s != null else Vector3.ZERO


## The target minus the right hand's grip, in the rig's own space (the space keys are written in).
func _miss(target: String) -> Vector3:
	var rig: Node3D = _vm.get(&"_rig") as Node3D
	var socks: Dictionary = _vm.get(&"_sock")
	var hand: Node3D = socks.get("R", null)
	var held: Node3D = _vm.held_item()
	if rig == null or hand == null or held == null:
		return Vector3.ZERO
	var inv: Transform3D = rig.global_transform.affine_inverse()
	var at: Vector3 = Vector3.ZERO
	if target == "knob":
		at = knob(held)
	else:
		var s: Node3D = held.find_child("socket_grip_r", true, false) as Node3D
		at = s.global_position if s != null else Vector3.ZERO
	return inv * at - inv * hand.global_position


## How the frozen knob key reads from the camera: the knob's gap to the scope's screen footprint
## ("gap", m at the knob's depth, < 0 inside it), the left hand's screen point ("l", tan units) and
## whether it is in the frame ("l_in"), and the right forearm's way in ("drop": how far the elbow is
## below the wrist, "depth": the elbow's distance in front of the lens; "r_low" when it comes in low
## from below, not down from the top corner past the lens).
func _read() -> Dictionary:
	var inv: Transform3D = _cam.global_transform.affine_inverse()
	var held: Node3D = _vm.held_item()
	var kn: Vector3 = inv * knob(held)
	var out: Dictionary = {"gap": scope_gap(inv, held.find_child("scope", true, false) as Node3D, kn)}
	var lh: Node3D = (_vm.get(&"_sock") as Dictionary).get("L", null)
	var l: Vector2 = to_screen(inv * lh.global_position) if lh != null else Vector2(9.0, 9.0)
	out["l"] = l
	out["l_in"] = absf(l.x) <= VIEW_TAN.x * 0.92 and l.y >= -VIEW_TAN.y * 0.9 and l.y <= VIEW_TAN.y
	var el: Vector3 = inv * _bone_pos("forearm.R")
	var wr: Vector3 = inv * _bone_pos("hand.R")
	out["drop"] = wr.y - el.y
	out["depth"] = -el.z
	out["r_low"] = wr.y - el.y >= 0.05 and -el.z >= 0.12
	return out


## A camera-space point on the screen, in tan units (x right, y up).
static func to_screen(v: Vector3) -> Vector2:
	return Vector2(v.x, v.y) / maxf(-v.z, 0.001)


## The gap (m at p's depth) between camera-space point p and the screen footprint (convex hull) of
## the scope's mesh; negative inside it.
static func scope_gap(inv: Transform3D, scope: Node3D, p: Vector3) -> float:
	if scope == null:
		return 9.0
	var pts := PackedVector2Array()
	for mi: Node in scope.find_children("*", "MeshInstance3D", true, true) + ([scope] if scope is MeshInstance3D else []):
		var m: MeshInstance3D = mi as MeshInstance3D
		if m == null or m.mesh == null:
			continue
		var xf: Transform3D = inv * m.global_transform
		for v: Vector3 in m.mesh.get_faces():
			var c: Vector3 = xf * v
			if -c.z > 0.02:
				pts.append(to_screen(c))
	var hull: PackedVector2Array = Geometry2D.convex_hull(pts)
	if hull.size() < 3:
		return 9.0
	var sp: Vector2 = to_screen(p)
	var d: float = INF
	for i: int in hull.size() - 1:
		d = minf(d, sp.distance_to(Geometry2D.get_closest_point_to_segment(sp, hull[i], hull[i + 1])))
	return (-d if Geometry2D.is_point_in_polygon(sp, hull) else d) * -p.z


## A bone's head in world space on the arms ("forearm.R" heads at the elbow, "hand.R" at the wrist).
func _bone_pos(bone: String) -> Vector3:
	var arms: Node3D = _vm.get(&"_arms") as Node3D
	if arms == null:
		return Vector3.ZERO
	for n: Node in arms.find_children("*", "Skeleton3D", true, false):
		var sk: Skeleton3D = n as Skeleton3D
		var i: int = sk.find_bone(bone)
		if i < 0:
			i = sk.find_bone(bone.replace(".", "_"))
		if i >= 0:
			return sk.global_transform * sk.get_bone_global_pose(i).origin
	return Vector3.ZERO


## The bolt handle's knob: the bolt's vertex farthest from the bore (its local Z axis).
static func knob(held: Node3D) -> Vector3:
	var bolt: Node3D = held.find_child("bolt", true, false) as Node3D
	if bolt == null:
		return held.global_position
	var best := Vector3.ZERO
	var best_d: float = -1.0
	for mi: Node in bolt.find_children("*", "MeshInstance3D", true, true) + ([bolt] if bolt is MeshInstance3D else []):
		var m: MeshInstance3D = mi as MeshInstance3D
		if m == null or m.mesh == null:
			continue
		var to_bolt: Transform3D = bolt.global_transform.affine_inverse() * m.global_transform
		for v: Vector3 in m.mesh.get_faces():
			var lv: Vector3 = to_bolt * v
			var d: float = Vector2(lv.x, lv.y).length()
			if d > best_d:
				best_d = d
				best = lv
	return bolt.global_transform * best


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default


## Which hand socket the held item hangs from now ("L", "R" or "").
func _item_hand() -> String:
	var socks: Dictionary = _vm.get(&"_sock")
	var held: Node3D = _vm.held_item()
	for k: String in socks:
		if held != null and socks[k] != null and (socks[k] as Node).is_ancestor_of(held):
			return k
	return ""
