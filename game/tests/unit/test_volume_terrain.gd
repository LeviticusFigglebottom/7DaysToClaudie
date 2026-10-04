extends GutTest
## SDF volume terrain: surface-nets meshing (orientation, smoothness, seams) and digging.


class FakeTerrain:
	extends Node
	var textures: Variant = null

	func base_height_at(_x: float, _z: float) -> float:
		return 10.0


func _field(fn: Callable, n: int = 16, voxel: float = 0.5, origin := Vector3.ZERO) -> PackedFloat32Array:
	var d := PackedFloat32Array()
	d.resize(SurfaceNets.size_for(n))
	for z: int in range(-1, n + 2):
		for y: int in range(-1, n + 2):
			for x: int in range(-1, n + 2):
				d[SurfaceNets.at(n, x, y, z)] = fn.call(origin + Vector3(x, y, z) * voxel)
	return d


## Godot front faces are clockwise seen from outside: (b - a) x (c - a) points INTO the solid.
func _faces_outward(m: Dictionary, outward: Callable) -> bool:
	var v: PackedVector3Array = m["vertices"]
	var idx: PackedInt32Array = m["indices"]
	for t: int in range(0, idx.size(), 3):
		var a: Vector3 = v[idx[t]]
		var b: Vector3 = v[idx[t + 1]]
		var c: Vector3 = v[idx[t + 2]]
		var cross: Vector3 = (b - a).cross(c - a)
		if cross.length() < 1e-9:
			continue
		if cross.dot(outward.call((a + b + c) / 3.0)) >= 0.0:
			return false
	return true


func test_flat_ground_meshes_flat_and_faces_up() -> void:
	var m: Dictionary = SurfaceNets.mesh(_field(func(p: Vector3) -> float: return 3.2 - p.y), 16, 0.5)
	assert_gt((m["indices"] as PackedInt32Array).size(), 0)
	for p: Vector3 in (m["vertices"] as PackedVector3Array):
		assert_almost_eq(p.y, 3.2, 0.01)
	for nrm: Vector3 in (m["normals"] as PackedVector3Array):
		assert_gt(nrm.y, 0.99)
	assert_true(_faces_outward(m, func(_c: Vector3) -> Vector3: return Vector3.UP), "front faces look up")


func test_sphere_is_closed_and_outward() -> void:
	var c := Vector3(4, 4, 4)
	var m: Dictionary = SurfaceNets.mesh(_field(func(p: Vector3) -> float: return 2.5 - p.distance_to(c)), 16, 0.5)
	var v: PackedVector3Array = m["vertices"]
	assert_gt(v.size(), 50)
	for p: Vector3 in v:
		assert_almost_eq(p.distance_to(c), 2.5, 0.2)
	assert_true(_faces_outward(m, func(q: Vector3) -> Vector3: return (q - c).normalized()), "front faces point away from the centre")
	# Closed surface: every edge is shared by exactly two triangles.
	var edges: Dictionary = {}
	var idx: PackedInt32Array = m["indices"]
	for t: int in range(0, idx.size(), 3):
		for k: int in 3:
			var a: int = idx[t + k]
			var b: int = idx[t + (k + 1) % 3]
			var key: Vector2i = Vector2i(mini(a, b), maxi(a, b))
			edges[key] = int(edges.get(key, 0)) + 1
	var open: int = 0
	for e: Vector2i in edges:
		if int(edges[e]) != 2:
			open += 1
	assert_eq(open, 0, "watertight")


func test_neighbouring_chunks_share_their_seam() -> void:
	# Two chunks side by side over a tilted plane: vertices on the shared face coincide.
	var fn := func(p: Vector3) -> float: return 4.0 + 0.3 * p.x - p.y
	var a: Dictionary = SurfaceNets.mesh(_field(fn, 16, 0.5, Vector3.ZERO), 16, 0.5)
	var b: Dictionary = SurfaceNets.mesh(_field(fn, 16, 0.5, Vector3(8, 0, 0)), 16, 0.5)
	var seam_a: Dictionary = {}
	for p: Vector3 in (a["vertices"] as PackedVector3Array):
		if absf(p.x - 7.75) < 0.01 or absf(p.x - 8.25) < 0.3:
			seam_a[Vector3i(roundi(p.x * 100), roundi(p.y * 100), roundi(p.z * 100))] = true
	var shared: int = 0
	for p2: Vector3 in (b["vertices"] as PackedVector3Array):
		var w: Vector3 = p2 + Vector3(8, 0, 0)
		if seam_a.has(Vector3i(roundi(w.x * 100), roundi(w.y * 100), roundi(w.z * 100))):
			shared += 1
	assert_gt(shared, 10, "border cells are meshed identically by both chunks")


func test_digging_removes_material_and_persists() -> void:
	var t := FakeTerrain.new()
	add_child_autofree(t)
	var vol := VolumeTerrain.new()
	t.add_child(vol)
	vol.setup(t)
	var removed: float = vol.edit_sphere(Vector3(5, 9.5, 5), 1.5, 3.0)
	assert_gt(removed, 0.5, "earth removed")
	assert_true(vol.is_volume_column(5, 5))
	var key: Vector3i = VolumeTerrain.chunk_of(Vector3(5, 9.5, 5))
	var c: VolumeTerrain.VChunk = vol.chunks[key]
	var o := Vector3(key.x, key.y, key.z) * VolumeTerrain.SIZE
	var local: Vector3i = Vector3i(((Vector3(5, 9.5, 5) - o) / VolumeTerrain.VOXEL).round())
	assert_lt(c.density[SurfaceNets.at(VolumeTerrain.N, local.x, local.y, local.z)], 0.0, "the dig centre is air now")
	vol.flush()
	assert_not_null(c.body, "collision built")
	var ws := WorldState.new()
	vol.save_into(ws)
	var vol2 := VolumeTerrain.new()
	t.add_child(vol2)
	vol2.setup(t)
	vol2.load_from(ws)
	var c2: VolumeTerrain.VChunk = vol2.chunks[key]
	assert_almost_eq(c2.density[SurfaceNets.at(VolumeTerrain.N, local.x, local.y, local.z)], c.density[SurfaceNets.at(VolumeTerrain.N, local.x, local.y, local.z)], 0.05)
	vol2.flush()
