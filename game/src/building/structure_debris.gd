class_name StructureDebris
extends RigidBody3D
## A collapsed or broken building piece tumbling down. Settles, then sinks away after a while
## (loose logs from a collapse become LogEntity instead and stay reusable).

const LIFETIME: float = 9.0

var mesh: Mesh
var size := Vector3.ONE
var _t: float = 0.0


static func spawn(parent: Node, p_mesh: Mesh, xform: Transform3D, p_size: Vector3, impulse: Vector3 = Vector3.ZERO) -> StructureDebris:
	var d := StructureDebris.new()
	d.mesh = p_mesh
	d.size = p_size
	parent.add_child(d)
	d.global_transform = xform
	d.apply_central_impulse(impulse * d.mass)
	d.apply_torque_impulse(Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * d.mass * 0.4)
	return d


func _ready() -> void:
	collision_layer = 1 << 8
	collision_mask = (1 << 0) | (1 << 1) | (1 << 8) | (1 << 12)
	mass = clampf(size.x * size.y * size.z * 400.0, 5.0, 120.0)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	add_child(mi)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size.max(Vector3(0.1, 0.1, 0.1))
	cs.shape = box
	cs.position = Vector3(0, size.y * 0.5, 0) if mesh != null and mesh.get_aabb().position.y >= -0.01 else Vector3.ZERO
	add_child(cs)


func _physics_process(delta: float) -> void:
	_t += delta
	if _t > LIFETIME:
		# Sink below ground then free (no pop).
		freeze = true
		global_position.y -= delta * 0.4
		if _t > LIFETIME + 3.0:
			queue_free()
