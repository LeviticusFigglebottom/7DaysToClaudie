class_name Sound3D
extends AudioStreamPlayer3D
## Positional sound with geometry occlusion: a few times per second it raycasts to the listener
## (camera) and lowers the attenuation filter cutoff + volume when walls/terrain are in the way,
## so a zombie behind a wall sounds muffled. one_shot players free themselves when finished.

const OCCLUDED_CUTOFF_HZ: float = 900.0
const OPEN_CUTOFF_HZ: float = 16000.0
const CHECK_INTERVAL: float = 0.2
## world + structures + props + sight_blockers
const OCCLUSION_MASK: int = 1 | 2 | 4 | 16384

var occlusion: bool = true
var one_shot: bool = false
var _t: float = 0.0
var _base_volume: float = 0.0
var _occ: float = 0.0


func _ready() -> void:
	_base_volume = volume_db
	attenuation_filter_cutoff_hz = OPEN_CUTOFF_HZ
	attenuation_filter_db = -18.0
	if one_shot:
		finished.connect(queue_free)


func _physics_process(delta: float) -> void:
	if not occlusion or not playing:
		return
	_t -= delta
	if _t > 0.0:
		return
	_t = CHECK_INTERVAL
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam == null:
		return
	var from: Vector3 = global_position
	var to: Vector3 = cam.global_position
	if from.distance_squared_to(to) > max_distance * max_distance:
		return
	var q := PhysicsRayQueryParameters3D.create(from, to, OCCLUSION_MASK)
	var hits: int = 0
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var res: Dictionary = space.intersect_ray(q)
	if not res.is_empty():
		hits += 1
		# Second probe from the far side to estimate thickness (two walls = heavier muffling).
		var q2 := PhysicsRayQueryParameters3D.create(to, from, OCCLUSION_MASK)
		var res2: Dictionary = space.intersect_ray(q2)
		if not res2.is_empty() and (res2["position"] as Vector3).distance_to(res["position"]) > 1.0:
			hits += 1
	# One wall muffles clearly (about 2 kHz, -6 dB), two walls nearly to a thud.
	var target: float = 0.0 if hits == 0 else (0.7 if hits == 1 else 1.0)
	_occ = lerpf(_occ, target, 0.5)
	# Interpolated in octaves (the ear hears pitch logarithmically; a linear blend stayed bright).
	attenuation_filter_cutoff_hz = OPEN_CUTOFF_HZ * pow(OCCLUDED_CUTOFF_HZ / OPEN_CUTOFF_HZ, _occ)
	volume_db = _base_volume - 9.0 * _occ
