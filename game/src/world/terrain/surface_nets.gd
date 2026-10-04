class_name SurfaceNets
extends RefCounted
## Smooth isosurface extraction for SDF volume chunks (naive surface nets): one vertex per
## sign-changing cell at the mean of its edge crossings, one quad per sign-changing edge joining
## the four cells around it. Smooth, no lookup tables, cheap enough for GDScript on a worker.
## Pure function over a density array (positive = solid, negative = air).
##
## Padded layout so neighbouring chunks meet without seams: a chunk of n cells per axis stores
## (n + 3)^3 samples for local sample indices -1 .. n+1 (array index = local + 1), x fastest, then
## y, then z. A chunk emits the quads of the edges that START at samples 0..n-1, and cells -1..n
## provide their vertices, so the surface between two chunks is built once from identical data.
## Returns {"vertices", "normals", "indices"} in chunk-local metres (sample 0 at the origin).

const CORNERS: Array[Vector3i] = [Vector3i(0, 0, 0), Vector3i(1, 0, 0), Vector3i(0, 1, 0), Vector3i(1, 1, 0),
	Vector3i(0, 0, 1), Vector3i(1, 0, 1), Vector3i(0, 1, 1), Vector3i(1, 1, 1)]
const EDGES: Array[Vector2i] = [Vector2i(0, 1), Vector2i(2, 3), Vector2i(4, 5), Vector2i(6, 7), Vector2i(0, 2), Vector2i(1, 3),
	Vector2i(4, 6), Vector2i(5, 7), Vector2i(0, 4), Vector2i(1, 5), Vector2i(2, 6), Vector2i(3, 7)]


static func size_for(n: int) -> int:
	return (n + 3) * (n + 3) * (n + 3)


## Array index of local sample (x, y, z), each in -1 .. n+1.
static func at(n: int, x: int, y: int, z: int) -> int:
	var s: int = n + 3
	return ((z + 1) * s + (y + 1)) * s + (x + 1)


static func mesh(density: PackedFloat32Array, n: int, voxel: float) -> Dictionary:
	var cells: int = n + 2
	var vert_index := PackedInt32Array()
	vert_index.resize(cells * cells * cells)
	vert_index.fill(-1)
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var vals: Array[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
	# Pass 1: a vertex per sign-changing cell (cells -1 .. n).
	for z: int in range(-1, n + 1):
		for y: int in range(-1, n + 1):
			for x: int in range(-1, n + 1):
				var solid: int = 0
				for c: int in 8:
					var o: Vector3i = CORNERS[c]
					var v: float = density[at(n, x + o.x, y + o.y, z + o.z)]
					vals[c] = v
					if v > 0.0:
						solid += 1
				if solid == 0 or solid == 8:
					continue
				var acc := Vector3.ZERO
				var cnt: int = 0
				for e: Vector2i in EDGES:
					var a: float = vals[e.x]
					var b: float = vals[e.y]
					if (a > 0.0) == (b > 0.0):
						continue
					acc += Vector3(CORNERS[e.x]).lerp(Vector3(CORNERS[e.y]), a / (a - b))
					cnt += 1
				vert_index[((z + 1) * cells + (y + 1)) * cells + (x + 1)] = verts.size()
				verts.append((Vector3(x, y, z) + acc / float(cnt)) * voxel)
				normals.append(_normal(vals))
	# Pass 2: quads across sign-changing edges that start inside this chunk.
	var idx := PackedInt32Array()
	for z: int in n:
		for y: int in n:
			for x: int in n:
				var d0: float = density[at(n, x, y, z)]
				var s0: bool = d0 > 0.0
				if (density[at(n, x + 1, y, z)] > 0.0) != s0:
					_quad(idx, vert_index, cells, [Vector3i(x, y - 1, z - 1), Vector3i(x, y, z - 1), Vector3i(x, y, z), Vector3i(x, y - 1, z)], s0)
				if (density[at(n, x, y + 1, z)] > 0.0) != s0:
					_quad(idx, vert_index, cells, [Vector3i(x - 1, y, z - 1), Vector3i(x - 1, y, z), Vector3i(x, y, z), Vector3i(x, y, z - 1)], s0)
				if (density[at(n, x, y, z + 1)] > 0.0) != s0:
					_quad(idx, vert_index, cells, [Vector3i(x - 1, y - 1, z), Vector3i(x, y - 1, z), Vector3i(x, y, z), Vector3i(x - 1, y, z)], s0)
	return {"vertices": verts, "normals": normals, "indices": idx}


static func _quad(idx: PackedInt32Array, vi: PackedInt32Array, cells: int, q: Array, flip: bool) -> void:
	var ids: Array[int] = [0, 0, 0, 0]
	for k: int in 4:
		var c: Vector3i = q[k]
		var i: int = vi[((c.z + 1) * cells + (c.y + 1)) * cells + (c.x + 1)]
		if i < 0:
			return
		ids[k] = i
	if flip:
		idx.append_array([ids[0], ids[1], ids[2], ids[0], ids[2], ids[3]])
	else:
		idx.append_array([ids[0], ids[2], ids[1], ids[0], ids[3], ids[2]])


## Outward (toward air) normal from the cell's corner values.
static func _normal(vals: Array[float]) -> Vector3:
	var g := Vector3.ZERO
	for c: int in 8:
		var o: Vector3i = CORNERS[c]
		g += Vector3(float(o.x) * 2.0 - 1.0, float(o.y) * 2.0 - 1.0, float(o.z) * 2.0 - 1.0) * vals[c]
	return (-g).normalized() if g.length() > 0.00001 else Vector3.UP
