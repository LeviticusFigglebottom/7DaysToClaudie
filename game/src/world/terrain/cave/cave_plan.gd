class_name CavePlan
extends RefCounted
## One cave's shape (ADR-0056, docs/CAVES_PLAN.md): pure, deterministic and thread-safe.
##
## M0 stub: a single straight capsule from the mouth into the hill, so the other workstreams can
## code against the contract. The full generator replaces the internals, not the interface.

const GEN_VERSION: int = 1

var id: StringName
var region_id: String = ""
var style: StringName = &"shelter"
var seed: int = 0
var ok: bool = false
var reason: String = ""
## Origin on the opening's floor, -Z into the hill.
var mouth := Transform3D()
var spine := PackedVector3Array()
var radii := PackedFloat32Array()
var floor_y := PackedFloat32Array()
var aabb := AABB()


static func build(spec: Dictionary, p_seed: int, height_fn: Callable, _cfg: Dictionary) -> CavePlan:
	var plan := CavePlan.new()
	plan.id = StringName(str(spec.get("id", "cave")))
	plan.region_id = str(spec.get("region_id", ""))
	plan.style = StringName(str(spec.get("style", "shelter")))
	plan.seed = p_seed
	var m: Array = spec.get("mouth", [0.0, 0.0])
	var x: float = float(m[0])
	var z: float = float(m[1])
	var y: float = float(height_fn.call(x, z))
	plan.mouth = Transform3D(Basis.IDENTITY, Vector3(x, y, z))
	var r: float = 2.5
	for i: int in 11:
		plan.spine.append(Vector3(x, y + 1.2, z - float(i)))
		plan.radii.append(r)
		plan.floor_y.append(y)
	plan.aabb = AABB(Vector3(x - r, y - 1.0, z - 10.0 - r), Vector3(r * 2.0, r * 2.0 + 1.0, 10.0 + r * 2.0))
	plan.ok = true
	return plan


## Signed distance to cave air: > 0 in rock, < 0 in the cave.
func sdf(p: Vector3) -> float:
	if spine.size() < 2:
		return INF
	var a: Vector3 = spine[0]
	var b: Vector3 = spine[spine.size() - 1]
	var ab: Vector3 = b - a
	var t: float = clampf((p - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
	var d: float = p.distance_to(a + ab * t) - radii[0]
	return maxf(d, floor_y[0] - p.y)


## min()s the cave into a padded block laid out like VolumeTerrain's chunks: (n + 3)³ samples,
## sample (i, j, k) at origin + (Vector3(i, j, k) - Vector3.ONE) * voxel, index (k * s + j) * s + i.
## Returns false when no sample changed.
func carve_block(origin: Vector3, n: int, voxel: float, density: PackedFloat32Array) -> bool:
	var s: int = n + 3
	var changed: bool = false
	for k: int in s:
		for j: int in s:
			for i: int in s:
				var p: Vector3 = origin + Vector3(i - 1, j - 1, k - 1) * voxel
				var idx: int = (k * s + j) * s + i
				var d: float = clampf(sdf(p), -2.0, 2.0)
				if d < density[idx]:
					density[idx] = d
					changed = true
	return changed


## Vector2i(16 m column) -> Vector2i(cy0, cy1): the volume chunks the cave reaches.
func columns() -> Dictionary:
	var out: Dictionary = {}
	var size: float = 16.0
	var lo: Vector3 = aabb.position
	var hi: Vector3 = aabb.end
	for cz: int in range(int(floor(lo.z / size)), int(floor(hi.z / size)) + 1):
		for cx: int in range(int(floor(lo.x / size)), int(floor(hi.x / size)) + 1):
			out[Vector2i(cx, cz)] = Vector2i(int(floor(lo.y / size)), int(floor(hi.y / size)))
	return out


## In cave air (sd < -0.2) and at least 1 m under the ground.
func is_inside(p: Vector3, ground_y: float) -> bool:
	return p.y <= ground_y - 1.0 and sdf(p) < -0.2


## The cave floor under p; NAN when p is not over cave air.
func floor_below(p: Vector3) -> float:
	if sdf(p) >= 0.0:
		return NAN
	return floor_y[0]


## The mouth apron, where vegetation must not grow.
func keep_out(x: float, z: float) -> bool:
	return Vector2(x, z).distance_to(Vector2(mouth.origin.x, mouth.origin.z)) < 4.0


## {pos: Vector3, normal: Vector3, kind: &"mouth"|&"tunnel"|&"chamber"|&"pocket"}
func anchors() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	out.append({"pos": mouth.origin, "normal": Vector3.UP, "kind": &"mouth"})
	return out


## [[Transform3D, size: Vector3, daylight_ratio: float]]
func probe_boxes() -> Array:
	return []


func digest() -> String:
	var parts: PackedStringArray = [str(GEN_VERSION), str(id), str(seed), str(ok)]
	for p: Vector3 in spine:
		parts.append("%.3f,%.3f,%.3f" % [p.x, p.y, p.z])
	return "|".join(parts).sha256_text()
