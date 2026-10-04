class_name TerrainMesher
extends RefCounted
## Builds terrain chunk meshes (with skirts) from a height sampler. Thread-safe: pure functions
## over provided data, no scene access. Heights come through a Callable(x, z) -> float so chunks
## that straddle region borders sample the neighbour (or macro) seamlessly.

## Builds an ArrayMesh for a square chunk at `origin` (world XZ of the chunk's min corner),
## `size` metres, vertex step `step` metres. Vertices are chunk-local (node sits at origin).
## colors: optional Callable(x, z) -> Color baked into COLOR (far tiles).
## hole_fn: optional Callable(x, z) -> bool; quads whose centre it marks are left out (columns
## handed over to the SDF volume terrain).
static func build_chunk(origin: Vector2, size: float, step: float, height_fn: Callable, skirt: float, colors: Callable = Callable(), hole_fn: Callable = Callable()) -> ArrayMesh:
	var res: int = int(round(size / step))
	var vcount: int = res + 1
	# Sample heights on a padded grid (+1 ring) for normals.
	var pad: int = vcount + 2
	var hs := PackedFloat32Array()
	hs.resize(pad * pad)
	for j: int in pad:
		var z: float = origin.y + (j - 1) * step
		for i: int in pad:
			hs[j * pad + i] = height_fn.call(origin.x + (i - 1) * step, z)
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var cols := PackedColorArray()
	var use_colors: bool = colors.is_valid()
	verts.resize(vcount * vcount)
	normals.resize(vcount * vcount)
	if use_colors:
		cols.resize(vcount * vcount)
	for j: int in vcount:
		for i: int in vcount:
			var pi: int = (j + 1) * pad + (i + 1)
			var h: float = hs[pi]
			var k: int = j * vcount + i
			verts[k] = Vector3(i * step, h, j * step)
			var hl: float = hs[pi - 1]
			var hr: float = hs[pi + 1]
			var hu: float = hs[pi - pad]
			var hd: float = hs[pi + pad]
			normals[k] = Vector3(hl - hr, 2.0 * step, hu - hd).normalized()
			if use_colors:
				cols[k] = colors.call(origin.x + i * step, origin.y + j * step)
	var idx := PackedInt32Array()
	idx.resize(res * res * 6)
	var w: int = 0
	var holes: bool = hole_fn.is_valid()
	for j: int in res:
		for i: int in res:
			if holes and bool(hole_fn.call(origin.x + (i + 0.5) * step, origin.y + (j + 0.5) * step)):
				continue
			var a: int = j * vcount + i
			var b: int = a + 1
			var c: int = a + vcount
			var d: int = c + 1
			# Alternate the diagonal to avoid directional artifacts.
			if (i + j) % 2 == 0:
				idx[w] = a; idx[w + 1] = b; idx[w + 2] = d
				idx[w + 3] = a; idx[w + 4] = d; idx[w + 5] = c
			else:
				idx[w] = a; idx[w + 1] = b; idx[w + 2] = c
				idx[w + 3] = b; idx[w + 4] = d; idx[w + 5] = c
			w += 6
	idx.resize(w)
	if skirt > 0.0:
		_add_skirt(verts, normals, cols, idx, vcount, skirt, use_colors)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = idx
	if use_colors:
		arrays[Mesh.ARRAY_COLOR] = cols
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


## Skirt: a vertical strip hanging below every border edge hides LOD cracks.
static func _add_skirt(verts: PackedVector3Array, normals: PackedVector3Array, cols: PackedColorArray, idx: PackedInt32Array, vcount: int, depth: float, use_colors: bool) -> void:
	var border: Array[int] = []
	for i: int in vcount:
		border.append(i)
	for j: int in range(1, vcount):
		border.append(j * vcount + vcount - 1)
	for i: int in range(vcount - 2, -1, -1):
		border.append((vcount - 1) * vcount + i)
	for j: int in range(vcount - 2, 0, -1):
		border.append(j * vcount)
	border.append(0)
	var base: int = verts.size()
	for k: int in border.size():
		var src: int = border[k]
		verts.append(verts[src] - Vector3(0, depth, 0))
		normals.append(normals[src])
		if use_colors:
			cols.append(cols[src])
	for k: int in border.size() - 1:
		var a: int = border[k]
		var b: int = border[k + 1]
		var a2: int = base + k
		var b2: int = base + k + 1
		# Outward-facing (walk order is clockwise seen from above with +Z down).
		idx.append(a); idx.append(a2); idx.append(b)
		idx.append(b); idx.append(a2); idx.append(b2)


## Heights for a HeightMapShape3D covering the chunk (vcount x vcount, row-major, 1 m step).
static func collision_heights(origin: Vector2, size: float, step: float, height_fn: Callable) -> PackedFloat32Array:
	var vcount: int = int(round(size / step)) + 1
	var out := PackedFloat32Array()
	out.resize(vcount * vcount)
	for j: int in vcount:
		for i: int in vcount:
			out[j * vcount + i] = height_fn.call(origin.x + i * step, origin.y + j * step)
	return out
