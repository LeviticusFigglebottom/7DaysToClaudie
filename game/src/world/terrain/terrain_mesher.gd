class_name TerrainMesher
extends RefCounted
## Builds terrain chunk meshes (with skirts) from a height sampler. Thread-safe: pure functions
## over provided data, no scene access. Heights come through a Callable(x, z) -> float so chunks
## that straddle region borders sample the neighbour (or macro) seamlessly.
##
## Cutting (TD-026): `cutters` are convex counter-clockwise XZ polygons in world space (POI
## cellar footprints from TerrainHoles). Quads they cover are dropped, quads they cross are
## clipped exactly — new vertices are interpolated inside the original triangle, so the surface
## outside the cut is unchanged to the millimetre and meets the cellar wall on its centre line.

## Builds an ArrayMesh for a square chunk at `origin` (world XZ of the chunk's min corner),
## `size` metres, vertex step `step` metres. Vertices are chunk-local (node sits at origin).
## colors: optional Callable(x, z) -> Color baked into COLOR (far tiles).
## hole_fn: optional Callable(x, z) -> bool; quads whose centre it marks are left out (columns
## handed over to the SDF volume terrain).
## cutters: convex world-XZ polygons cut out of the surface and its skirt (cellar holes).
static func build_chunk(origin: Vector2, size: float, step: float, height_fn: Callable, skirt: float, colors: Callable = Callable(), hole_fn: Callable = Callable(), cutters: Array[PackedVector2Array] = []) -> ArrayMesh:
	return finish(build_chunk_job(origin, size, step, height_fn, skirt, colors, hole_fn, cutters))


## True under the headless dummy renderer, whose mesh RID table is not thread-safe (TD-103): a
## mesh made on a worker races meshes made elsewhere ("Attempting to initialize the wrong RID",
## "unimplemented base type" in scene cull). The real renderers' tables are thread-safe.
static var meshes_on_main: bool = DisplayServer.get_name() == "headless"


## build_chunk for worker threads: the ArrayMesh, or under the dummy renderer its surface arrays,
## which the main thread turns into the mesh with finish().
static func build_chunk_job(origin: Vector2, size: float, step: float, height_fn: Callable, skirt: float, colors: Callable = Callable(), hole_fn: Callable = Callable(), cutters: Array[PackedVector2Array] = []) -> Variant:
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
	var local_cut: Array[PackedVector2Array] = _to_local(cutters, origin)
	var cut_bounds: Array[Rect2] = _bounds_of(local_cut)
	var idx := PackedInt32Array()
	idx.resize(res * res * 6)
	var w: int = 0
	var extra := PackedInt32Array()
	var holes: bool = hole_fn.is_valid()
	for j: int in res:
		for i: int in res:
			if holes and bool(hole_fn.call(origin.x + (i + 0.5) * step, origin.y + (j + 0.5) * step)):
				continue
			var a: int = j * vcount + i
			var b: int = a + 1
			var c: int = a + vcount
			var d: int = c + 1
			if not local_cut.is_empty():
				var hit: Array[PackedVector2Array] = _touching(local_cut, cut_bounds, Rect2(i * step, j * step, step, step))
				if not hit.is_empty():
					if _covered(hit, Vector2(i * step, j * step), step):
						continue
					var tris: PackedInt32Array = [a, b, d, a, d, c] if (i + j) % 2 == 0 else [a, b, c, b, d, c]
					for t: int in 2:
						_cut_triangle(verts, normals, cols, use_colors, extra, tris[t * 3], tris[t * 3 + 1], tris[t * 3 + 2], hit)
					continue
			# Alternate the diagonal to avoid directional artifacts.
			if (i + j) % 2 == 0:
				idx[w] = a; idx[w + 1] = b; idx[w + 2] = d
				idx[w + 3] = a; idx[w + 4] = d; idx[w + 5] = c
			else:
				idx[w] = a; idx[w + 1] = b; idx[w + 2] = c
				idx[w + 3] = b; idx[w + 4] = d; idx[w + 5] = c
			w += 6
	idx.resize(w)
	idx.append_array(extra)
	if skirt > 0.0:
		_add_skirt(verts, normals, cols, idx, vcount, skirt, use_colors, local_cut)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = idx
	if use_colors:
		arrays[Mesh.ARRAY_COLOR] = cols
	return arrays if meshes_on_main else finish(arrays)


## The mesh of a build_chunk_job result (an ArrayMesh passes through; on the main thread).
static func finish(job: Variant) -> ArrayMesh:
	if job is ArrayMesh or job == null:
		return job
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, job as Array)
	return mesh


## Skirt: a vertical strip hanging below every border edge hides LOD cracks. Border edges are
## clipped against the cutters too, or a cellar under a chunk border would get a curtain of
## grass hanging into it.
static func _add_skirt(verts: PackedVector3Array, normals: PackedVector3Array, cols: PackedColorArray, idx: PackedInt32Array, vcount: int, depth: float, use_colors: bool, cutters: Array[PackedVector2Array] = []) -> void:
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
	var cut_bounds: Array[Rect2] = _bounds_of(cutters)
	for k: int in border.size() - 1:
		var a: int = border[k]
		var b: int = border[k + 1]
		var a2: int = base + k
		var b2: int = base + k + 1
		if not cutters.is_empty():
			var pa := Vector2(verts[a].x, verts[a].z)
			var pb := Vector2(verts[b].x, verts[b].z)
			var hit: Array[PackedVector2Array] = _touching(cutters, cut_bounds, Rect2(pa, Vector2.ZERO).expand(pb).grow(0.001))
			if not hit.is_empty():
				for iv: Vector2 in TerrainHoles.segment_outside(pa, pb, hit):
					var n0: int = verts.size()
					for t: float in [iv.x, iv.y]:
						var top: Vector3 = verts[a].lerp(verts[b], t)
						var nrm: Vector3 = normals[a].lerp(normals[b], t).normalized()
						verts.append(top)
						verts.append(top - Vector3(0, depth, 0))
						normals.append(nrm)
						normals.append(nrm)
						if use_colors:
							var col: Color = cols[a].lerp(cols[b], t)
							cols.append(col)
							cols.append(col)
					idx.append(n0); idx.append(n0 + 1); idx.append(n0 + 2)
					idx.append(n0 + 2); idx.append(n0 + 1); idx.append(n0 + 3)
				continue
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


## Ground triangles of a square (3 vertices per face, local to `origin`, front faces up) for a
## ConcavePolygonShape3D or a navigation source: used where holes must be cut exactly, which a
## HeightMapShape3D (whole quads only) cannot do. Quads whose centre `hole_fn` marks are left out.
static func surface_faces(origin: Vector2, size: float, step: float, height_fn: Callable, hole_fn: Callable = Callable(), cutters: Array[PackedVector2Array] = []) -> PackedVector3Array:
	var res: int = int(round(size / step))
	var vcount: int = res + 1
	var verts := PackedVector3Array()
	verts.resize(vcount * vcount)
	for j: int in vcount:
		for i: int in vcount:
			verts[j * vcount + i] = Vector3(i * step, height_fn.call(origin.x + i * step, origin.y + j * step), j * step)
	var local_cut: Array[PackedVector2Array] = _to_local(cutters, origin)
	var cut_bounds: Array[Rect2] = _bounds_of(local_cut)
	var out := PackedVector3Array()
	out.resize(res * res * 6)
	var w: int = 0
	var extra := PackedVector3Array()
	var holes: bool = hole_fn.is_valid()
	for j: int in res:
		for i: int in res:
			if holes and bool(hole_fn.call(origin.x + (i + 0.5) * step, origin.y + (j + 0.5) * step)):
				continue
			var a: int = j * vcount + i
			var b: int = a + 1
			var c: int = a + vcount
			var d: int = c + 1
			# Same diagonals as the render mesh, so collision matches what you see.
			var tris: PackedInt32Array = [a, b, d, a, d, c] if (i + j) % 2 == 0 else [a, b, c, b, d, c]
			if not local_cut.is_empty():
				var hit: Array[PackedVector2Array] = _touching(local_cut, cut_bounds, Rect2(i * step, j * step, step, step))
				if not hit.is_empty():
					if _covered(hit, Vector2(i * step, j * step), step):
						continue
					for t: int in 2:
						var va: Vector3 = verts[tris[t * 3]]
						var vb: Vector3 = verts[tris[t * 3 + 1]]
						var vc: Vector3 = verts[tris[t * 3 + 2]]
						var pa := Vector2(va.x, va.z)
						var pb := Vector2(vb.x, vb.z)
						var pc := Vector2(vc.x, vc.z)
						for piece: PackedVector2Array in TerrainHoles.cut(PackedVector2Array([pa, pb, pc]), hit):
							var pts := PackedVector3Array()
							for p: Vector2 in piece:
								var bc: Vector3 = TerrainHoles.barycentric(p, pa, pb, pc)
								pts.append(Vector3(p.x, va.y * bc.x + vb.y * bc.y + vc.y * bc.z, p.y))
							for k: int in range(1, pts.size() - 1):
								extra.append(pts[0])
								extra.append(pts[k])
								extra.append(pts[k + 1])
					continue
			for t2: int in 6:
				out[w + t2] = verts[tris[t2]]
			w += 6
	out.resize(w)
	out.append_array(extra)
	return out


# --- Cutting helpers ---------------------------------------------------------------------------

static func _to_local(cutters: Array[PackedVector2Array], origin: Vector2) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	for poly: PackedVector2Array in cutters:
		var lp := PackedVector2Array()
		for p: Vector2 in poly:
			lp.append(p - origin)
		out.append(lp)
	return out


static func _bounds_of(polys: Array[PackedVector2Array]) -> Array[Rect2]:
	var out: Array[Rect2] = []
	for poly: PackedVector2Array in polys:
		out.append(TerrainHoles._poly_bounds(poly))
	return out


## Cutters whose bounds overlap the rect with some area (touching an edge is not overlapping).
static func _touching(polys: Array[PackedVector2Array], bounds: Array[Rect2], r: Rect2) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	for i: int in polys.size():
		if bounds[i].intersects(r, false):
			out.append(polys[i])
	return out


## Whether one cutter covers the whole quad (its four corners inside one convex piece).
static func _covered(hit: Array[PackedVector2Array], p0: Vector2, step: float) -> bool:
	for poly: PackedVector2Array in hit:
		if TerrainHoles.point_in_convex(poly, p0) and TerrainHoles.point_in_convex(poly, p0 + Vector2(step, 0)) \
				and TerrainHoles.point_in_convex(poly, p0 + Vector2(step, step)) and TerrainHoles.point_in_convex(poly, p0 + Vector2(0, step)):
			return true
	return false


## Appends the parts of triangle (ia, ib, ic) outside the cutters as new vertices (position,
## normal and colour interpolated inside the triangle) plus fan indices into `extra`.
static func _cut_triangle(verts: PackedVector3Array, normals: PackedVector3Array, cols: PackedColorArray, use_colors: bool, extra: PackedInt32Array, ia: int, ib: int, ic: int, hit: Array[PackedVector2Array]) -> void:
	var va: Vector3 = verts[ia]
	var vb: Vector3 = verts[ib]
	var vc: Vector3 = verts[ic]
	var pa := Vector2(va.x, va.z)
	var pb := Vector2(vb.x, vb.z)
	var pc := Vector2(vc.x, vc.z)
	for piece: PackedVector2Array in TerrainHoles.cut(PackedVector2Array([pa, pb, pc]), hit):
		var base: int = verts.size()
		for p: Vector2 in piece:
			var bc: Vector3 = TerrainHoles.barycentric(p, pa, pb, pc)
			verts.append(Vector3(p.x, va.y * bc.x + vb.y * bc.y + vc.y * bc.z, p.y))
			normals.append((normals[ia] * bc.x + normals[ib] * bc.y + normals[ic] * bc.z).normalized())
			if use_colors:
				cols.append(cols[ia] * bc.x + cols[ib] * bc.y + cols[ic] * bc.z)
		for k: int in range(1, piece.size() - 1):
			extra.append(base)
			extra.append(base + k)
			extra.append(base + k + 1)
