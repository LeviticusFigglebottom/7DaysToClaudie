class_name FallingTree
extends Node3D
## A felled tree toppling about its base like a rigid rod on a pivot (θ'' = 3g / 2L · sin θ),
## then breaking into logs, sticks and boughs where it lands. Kinematic rather than simulated so
## it always falls the way it was cut and never jitters through terrain. Whatever is under the
## trunk when it lands gets hurt (the player included).

const G: float = 9.8
const MAX_ANGLE: float = 1.955  # 112°, falls past horizontal on downhill slopes

var mesh: Mesh
var species: SpeciesDef
var instance_scale: float = 1.0
var fall_dir := Vector3.FORWARD
var tree_id: StringName = &""

var _mi: MeshInstance3D
var _started: bool = false
var _pivot := Vector3.ZERO
var _base_basis := Basis()
var _axis := Vector3.RIGHT
var _theta: float = 0.03
var _omega: float = 0.0
var _height: float = 20.0
var _landed: bool = false


func _ready() -> void:
	_mi = MeshInstance3D.new()
	_mi.mesh = mesh
	add_child(_mi)


func _physics_process(delta: float) -> void:
	if _landed:
		return
	if not _started:
		_start()
	var alpha: float = 3.0 * G / (2.0 * _height) * sin(_theta)
	_omega += alpha * delta
	_theta += _omega * delta
	var rot := Basis(_axis, _theta)
	global_transform = Transform3D(rot * _base_basis, _pivot)
	if _theta > 0.35 and (_touching_ground(rot) or _theta >= MAX_ANGLE):
		_land(rot)


func _start() -> void:
	_started = true
	_pivot = global_position
	_base_basis = global_transform.basis
	var d: Vector3 = Vector3(fall_dir.x, 0.0, fall_dir.z)
	d = d.normalized() if d.length() > 0.01 else Vector3.FORWARD
	_axis = Vector3.UP.cross(d).normalized()
	var top: float = mesh.get_aabb().end.y if mesh != null else 20.0
	_height = maxf(4.0, top * instance_scale)


func _point_along(rot: Basis, t: float) -> Vector3:
	return _pivot + rot * (Vector3.UP * _height * t)


func _ground(p: Vector3) -> float:
	var w: Node = Game.world
	return w.call(&"height_at", p.x, p.z) if w != null and w.has_method(&"height_at") else -INF


func _touching_ground(rot: Basis) -> bool:
	for t: float in [0.45, 0.75, 1.0]:
		var p: Vector3 = _point_along(rot, t)
		if p.y <= _ground(p) + 0.25 + 0.4 * (1.0 - t):
			return true
	return false


func _land(rot: Basis) -> void:
	_landed = true
	var base: Vector3 = _pivot
	var tip: Vector3 = _point_along(rot, 1.0)
	var dir: Vector3 = Vector3(tip.x - base.x, 0.0, tip.z - base.z).normalized()
	var crown: Vector3 = _point_along(rot, 0.7)
	Audio.play_3d(&"sfx/tree_fall_impact", crown, {"volume_db": 2.0, "max_distance": 160.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(crown, 55.0, &"tree_fall", &"")
	FxLibrary.burst(get_parent(), "dust", crown, Vector3.UP, 2.5)
	FxLibrary.burst(get_parent(), "leaves", crown + Vector3.UP, Vector3.UP, 2.0)
	_crush(base, tip)
	_spawn_yields(base, dir)
	queue_free()


## Damage anything standing along the trunk line.
func _crush(a: Vector3, b: Vector3) -> void:
	var w: Node = Game.world
	if w == null:
		return
	var targets: Array = []
	var pl: Node3D = w.get(&"player")
	if pl != null:
		targets.append(pl)
	targets.append_array(get_tree().get_nodes_in_group(&"enemies"))
	for n: Node in targets:
		var t: Node3D = n as Node3D
		if t == null or not t.has_method(&"take_damage"):
			continue
		var p: Vector3 = t.global_position + Vector3.UP * 0.9
		var closest: Vector3 = Geometry3D.get_closest_point_to_segment(p, a, b)
		if closest.distance_to(p) < 1.1 and a.distance_to(closest) > 1.5:
			var info := DamageInfo.make(45.0, &"blunt", &"tree", tree_id)
			info.hit_pos = closest
			info.source_pos = a
			info.direction = (p - closest).normalized()
			info.stagger = 1.0
			t.call(&"take_damage", info)


func _spawn_yields(base: Vector3, dir: Vector3) -> void:
	if species == null or Game.session == null:
		return
	var rng: RandomNumberGenerator = Game.session.rng.stream("harvest")
	var logs: int = 0
	var extra: Dictionary = {}
	for item: Variant in species.yields.keys():
		var r: Array = species.yields[item]
		var n: int = rng.randi_range(int(r[0]), int(r[1]))
		if String(item) == "log":
			logs = n
		elif n > 0:
			extra[item] = n
	var yaw: float = atan2(dir.z, dir.x)
	# Logs lie end to end along the fall line (log models are 4 m along +X).
	var loose: Node = Game.world.get(&"loose") if Game.world != null else null
	for i: int in logs:
		var along: float = 2.6 + float(i) * 4.25
		if along > _height - 1.0:
			break
		var p: Vector3 = base + dir * along
		p.y = _ground(p) + 0.3
		var basis := Basis(Vector3.UP, -yaw)
		if loose != null and loose.has_method(&"spawn_log"):
			loose.call(&"spawn_log", p, basis, species.id)
		else:
			ItemDrop.spawn(get_parent(), ItemStack.make(&"log", 1), p)
	var crown_p: Vector3 = base + dir * _height * 0.72
	for item: Variant in extra:
		var p2: Vector3 = crown_p + Vector3(rng.randf_range(-1.2, 1.2), 0.0, rng.randf_range(-1.2, 1.2))
		p2.y = _ground(p2) + 0.4
		ItemDrop.spawn(Game.world, ItemStack.make(StringName(str(item)), int(extra[item])), p2)
