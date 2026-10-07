extends RefCounted
## Test stand-ins for the cave generator's CavePlan and CaveSet (docs/CAVES_PLAN.md contract), so
## the volume streaming tests run without WS-A's files: a box of air with a flat floor, and an
## immutable set of them. Only the duck-typed calls VolumeTerrain and TerrainManager make.


## A box of cave air (centre, half extents); the floor is its bottom face.
class FakeCave:
	extends RefCounted
	var id: StringName
	var ok: bool = true
	var reason: String = ""
	var center: Vector3
	var half: Vector3
	var aabb: AABB

	func _init(p_id: StringName, p_center: Vector3, p_half: Vector3) -> void:
		id = p_id
		center = p_center
		half = p_half
		aabb = AABB(center - half, half * 2.0).grow(0.5)

	## > 0 in rock, < 0 in the air (a box SDF).
	func sdf(p: Vector3) -> float:
		var q: Vector3 = (p - center).abs() - half
		return Vector3(maxf(q.x, 0.0), maxf(q.y, 0.0), maxf(q.z, 0.0)).length() + minf(maxf(q.x, maxf(q.y, q.z)), 0.0)

	func carve_block(origin: Vector3, n: int, voxel: float, density: PackedFloat32Array) -> bool:
		var s: int = n + 3
		var changed: bool = false
		for k: int in s:
			for j: int in s:
				for i: int in s:
					var idx: int = (k * s + j) * s + i
					var d: float = clampf(sdf(origin + Vector3(i - 1, j - 1, k - 1) * voxel), -2.0, 2.0)
					if d < density[idx]:
						density[idx] = d
						changed = true
		return changed

	func columns() -> Dictionary:
		var out: Dictionary = {}
		for cz: int in range(int(floor(aabb.position.z / 16.0)), int(floor(aabb.end.z / 16.0)) + 1):
			for cx: int in range(int(floor(aabb.position.x / 16.0)), int(floor(aabb.end.x / 16.0)) + 1):
				out[Vector2i(cx, cz)] = Vector2i(int(floor(aabb.position.y / 16.0)), int(floor(aabb.end.y / 16.0)))
		return out

	func floor_y() -> float:
		return center.y - half.y

	func floor_below(p: Vector3) -> float:
		return floor_y() if sdf(p) < 0.0 else NAN


## An immutable set of FakeCaves (CaveSet's calls; no grid index: tests hold a few).
class FakeCaveSet:
	extends RefCounted
	var plans: Array = []

	func _init(p_plans: Array = []) -> void:
		plans = p_plans.duplicate()

	## CaveSet.combined's stand-in: parts are sets or plans, extra is id -> plan.
	static func combined(parts: Array, extra: Dictionary) -> FakeCaveSet:
		var all: Array = []
		for part: Variant in parts:
			if part is FakeCaveSet:
				all.append_array((part as FakeCaveSet).plans)
			elif part != null:
				all.append(part)
		for k: Variant in extra:
			all.append(extra[k])
		return FakeCaveSet.new(all)

	func touching(box: AABB) -> Array:
		var out: Array = []
		for p: FakeCave in plans:
			if p.aabb.intersects(box):
				out.append(p)
		return out

	func floor_below(p: Vector3) -> float:
		for c: FakeCave in plans:
			var f: float = c.floor_below(p)
			if not is_nan(f):
				return f
		return NAN

	func is_inside(p: Vector3, ground_y: float) -> bool:
		for c: FakeCave in plans:
			if p.y <= ground_y - 1.0 and c.sdf(p) < -0.2:
				return true
		return false

	func keep_out(_x: float, _z: float) -> bool:
		return false

	func is_empty() -> bool:
		return plans.is_empty()
