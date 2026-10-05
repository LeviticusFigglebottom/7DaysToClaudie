class_name RoofBuilder
extends RefCounted
## Procedural roofs over a POI level's footprint rectangle: gable (ridge along the long side,
## overhanging eaves, gable ends in the exterior wall finish, painted fascia and rake boards,
## a capped ridge and gutters) or flat (a tar-and-gravel membrane behind a parapet in the
## exterior finish). Coverings come from game/data/materials/roofs.json (ADR-0019).
## Returns [geometry nodes..., collision Shape3D...] for the builder.

const THICK: float = 0.14
## Fascia board along the eaves and up the rakes (height, thickness).
const FASCIA := Vector2(0.2, 0.035)
const MAT_DIR: String = "res://assets/generated/materials/%s.tres"


static func build(kind: String, rect: Rect2, y: float, spec: Dictionary) -> Array:
	match kind:
		"flat":
			return _flat(rect, y, spec)
		"none":
			# An open top (a lookout's catwalk, a roofless ruin): authors mark it, nothing is built.
			return []
	return _gable(rect, y, spec)


static func _roof_material(spec: Dictionary) -> Material:
	return _material(str(spec.get("material", "roof_shingle")), str(spec.get("color", "#3b3633")))


static func _material(id: String, fallback: String) -> Material:
	var path: String = MAT_DIR % id
	if ResourceLoader.exists(path):
		var m: Material = load(path)
		if m is BaseMaterial3D:
			(m as BaseMaterial3D).cull_mode = BaseMaterial3D.CULL_DISABLED
		return m
	var sm := StandardMaterial3D.new()
	sm.albedo_color = Color.html(fallback)
	sm.roughness = 0.92
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	return sm


## Exterior wall finish slice and decay for kit-shaded parts (gable ends, parapets).
static func _kit_custom(spec: Dictionary) -> Color:
	var ext: int = PoiParts.finish_index("wall", str(spec.get("gable_finish", spec.get("exterior", "siding_white"))))
	return Color(ext, ext, float(spec.get("decay", 0.4)), 0.5)


static func _gable(rect: Rect2, y: float, spec: Dictionary) -> Array:
	var ov: float = float(spec.get("overhang", 0.45))
	var pitch: float = deg_to_rad(float(spec.get("pitch", 32.0)))
	var along_x: bool = str(spec.get("axis", "x" if rect.size.x >= rect.size.y else "z")) == "x"
	var half: float = (rect.size.y if along_x else rect.size.x) * 0.5
	var rise: float = half * tan(pitch)
	var eave: float = y - ov * tan(pitch)
	var ridge: float = y + rise
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var faces := PackedVector3Array()
	var quads: Array = []
	if along_x:
		var x0: float = rect.position.x - ov
		var x1: float = rect.end.x + ov
		var zm: float = rect.get_center().y
		quads.append([Vector3(x0, eave, rect.position.y - ov), Vector3(x1, eave, rect.position.y - ov), Vector3(x1, ridge, zm), Vector3(x0, ridge, zm)])
		quads.append([Vector3(x1, eave, rect.end.y + ov), Vector3(x0, eave, rect.end.y + ov), Vector3(x0, ridge, zm), Vector3(x1, ridge, zm)])
	else:
		var z0: float = rect.position.y - ov
		var z1: float = rect.end.y + ov
		var xm: float = rect.get_center().x
		quads.append([Vector3(rect.position.x - ov, eave, z1), Vector3(rect.position.x - ov, eave, z0), Vector3(xm, ridge, z0), Vector3(xm, ridge, z1)])
		quads.append([Vector3(rect.end.x + ov, eave, z0), Vector3(rect.end.x + ov, eave, z1), Vector3(xm, ridge, z1), Vector3(xm, ridge, z0)])
	# UVs in metres: u along the ridge, v up the slope from the eave, so streaks run downhill and
	# courses stay level however long the roof.
	var slope_m: float = 1.0 / sin(pitch)
	for q: Array in quads:
		var n: Vector3 = ((q[1] as Vector3) - (q[0] as Vector3)).cross((q[3] as Vector3) - (q[0] as Vector3)).normalized()
		if n.y < 0.0:
			n = -n
		for tri: Array in [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]:
			for v: Vector3 in tri:
				st.set_normal(n)
				st.set_uv(Vector2(v.x if along_x else v.z, (v.y - eave) * slope_m))
				st.add_vertex(v)
				faces.append(v)
		# Underside / fascia thickness: offset copy.
		for tri2: Array in [[q[0], q[2], q[1]], [q[0], q[3], q[2]]]:
			for v2: Vector3 in tri2:
				st.set_normal(-n)
				st.set_uv(Vector2(v2.x + v2.z, v2.y))
				st.add_vertex(v2 - n * THICK)
	# Ridge cap: a narrow fold of the covering laid over the ridge line.
	var r0: Vector3 = (quads[0][3] as Vector3)
	var r1: Vector3 = (quads[0][2] as Vector3)
	var ridge_dir: Vector3 = (r1 - r0).normalized()
	var across := Vector3(-ridge_dir.z, 0.0, ridge_dir.x)
	var cap_w: float = 0.17
	var drop: float = cap_w * tan(pitch)
	for s: float in [-1.0, 1.0]:
		var a0: Vector3 = r0 + Vector3.UP * 0.035
		var a1: Vector3 = r1 + Vector3.UP * 0.035
		var b0: Vector3 = a0 + across * s * cap_w - Vector3.UP * drop
		var b1: Vector3 = a1 + across * s * cap_w - Vector3.UP * drop
		var cn: Vector3 = (a1 - a0).cross(b0 - a0).normalized()
		if cn.y < 0.0:
			cn = -cn
		for v3: Vector3 in [a0, a1, b1, a0, b1, b0]:
			st.set_normal(cn)
			st.set_uv(Vector2(v3.x + v3.z, v3.y * 3.0))
			st.add_vertex(v3)
	var roof_mesh: ArrayMesh = st.commit()
	roof_mesh.surface_set_material(0, _roof_material(spec))
	var mi := MeshInstance3D.new()
	mi.name = "Roof"
	mi.mesh = roof_mesh
	var out: Array = [mi, _gable_trim(quads, eave, ridge, spec)]
	# Gable ends in the exterior wall finish (kit wall shader, one MultiMesh instance).
	var g := SurfaceTool.new()
	g.begin(Mesh.PRIMITIVE_TRIANGLES)
	var tris: Array = []
	if along_x:
		var zm2: float = rect.get_center().y
		for x: float in [rect.position.x, rect.end.x]:
			tris.append([Vector3(x, y, rect.position.y), Vector3(x, y, rect.end.y), Vector3(x, ridge, zm2), Vector3(-1 if x == rect.position.x else 1, 0, 0)])
	else:
		var xm2: float = rect.get_center().x
		for z: float in [rect.position.y, rect.end.y]:
			tris.append([Vector3(rect.position.x, y, z), Vector3(rect.end.x, y, z), Vector3(xm2, ridge, z), Vector3(0, 0, -1 if z == rect.position.y else 1)])
	for t: Array in tris:
		# kit_wall culls back faces: wind each end clockwise as seen from outside.
		var order: Array = [t[0], t[1], t[2]]
		if Plane(t[0], t[1], t[2]).normal.dot(t[3]) < 0.0:
			order = [t[0], t[2], t[1]]
		for v4: Vector3 in order:
			g.set_normal(t[3])
			g.set_uv(Vector2(v4.x + v4.z, -v4.y))
			g.set_uv2(Vector2(0, 0))
			# Kit vertex colour contract: R = AO, G = wear (none on a plain gable), B = variation.
			g.set_color(Color(1.0, 0.0, 0.5, 1.0))
			g.add_vertex(v4)
			faces.append(v4)
	out.append(_kit_instance("Gables", g.commit(), spec))
	var shape := ConcavePolygonShape3D.new()
	shape.backface_collision = true
	shape.set_faces(faces)
	out.append(shape)
	return out


## Fascia boards along both eaves and up the four rakes, plus a half-round gutter under each eave.
static func _gable_trim(quads: Array, eave: float, ridge: float, spec: Dictionary) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q: Array in quads:
		var e0: Vector3 = q[0]
		var e1: Vector3 = q[1]
		var top0: Vector3 = q[3]
		var top1: Vector3 = q[2]
		var out_dir: Vector3 = Vector3(e0.x - top0.x, 0.0, e0.z - top0.z).normalized()
		_board(st, e0, e1, out_dir, FASCIA.x, FASCIA.y)
		_board(st, e0, top0, ((e0 - e1) * Vector3(1, 0, 1)).normalized(), FASCIA.x * 0.8, FASCIA.y)
		_board(st, e1, top1, ((e1 - e0) * Vector3(1, 0, 1)).normalized(), FASCIA.x * 0.8, FASCIA.y)
	var trim: ArrayMesh = st.commit()
	trim.surface_set_material(0, _material("kit_trim", "#d9d3c4"))
	if bool(spec.get("gutters", true)):
		var gt := SurfaceTool.new()
		gt.begin(Mesh.PRIMITIVE_TRIANGLES)
		for q2: Array in quads:
			var a: Vector3 = q2[0]
			var b: Vector3 = q2[1]
			var od: Vector3 = Vector3(a.x - (q2[3] as Vector3).x, 0.0, a.z - (q2[3] as Vector3).z).normalized()
			_gutter(gt, a + od * (FASCIA.y + 0.06) - Vector3.UP * 0.05, b + od * (FASCIA.y + 0.06) - Vector3.UP * 0.05, od)
		gt.commit(trim)
		trim.surface_set_material(1, _material("metal_painted", "#7a7d7a"))
	var mi := MeshInstance3D.new()
	mi.name = "RoofTrim"
	mi.mesh = trim
	return mi


## A board of height h and thickness t whose top outer edge runs from a to b, standing just outside
## the edge (toward `out`).
static func _board(st: SurfaceTool, a: Vector3, b: Vector3, out: Vector3, h: float, t: float) -> void:
	var along: Vector3 = (b - a).normalized()
	var up: Vector3 = out.cross(along).normalized()
	if up.y < 0.0:
		up = -up
	var o: Vector3 = out * t
	var lo: Vector3 = -up * h
	var face: Array = [a + o, b + o, b + o + lo, a + o + lo]
	var bottom: Array = [a + lo, a + o + lo, b + o + lo, b + lo]
	var top: Array = [a, b, b + o, a + o]
	for quad: Array in [[face, out], [bottom, -up], [top, up]]:
		var p: Array = quad[0]
		var n: Vector3 = quad[1]
		for v: Vector3 in [p[0], p[1], p[2], p[0], p[2], p[3]]:
			st.set_normal(n)
			st.set_uv(Vector2((v - a).dot(along), (v - a).dot(up)))
			st.add_vertex(v)


## Half-round gutter (open channel of 6 facets) from a to b.
static func _gutter(st: SurfaceTool, a: Vector3, b: Vector3, out: Vector3) -> void:
	var r: float = 0.065
	var ring: Array[Vector3] = []
	for i: int in 7:
		var ang: float = PI * float(i) / 6.0
		ring.append(-out * cos(ang) * r - Vector3.UP * sin(ang) * r)
	var along: float = a.distance_to(b)
	for i: int in 6:
		var n: Vector3 = (ring[i] + ring[i + 1]).normalized()
		var quad: Array = [a + ring[i], b + ring[i], b + ring[i + 1], a + ring[i + 1]]
		for k: int in [0, 1, 2, 0, 2, 3]:
			var v: Vector3 = quad[k]
			st.set_normal(n)
			st.set_uv(Vector2(along if k in [1, 2] else 0.0, float(i) / 6.0))
			st.add_vertex(v)


static func _kit_instance(node_name: String, mesh: ArrayMesh, spec: Dictionary) -> MultiMeshInstance3D:
	mesh.surface_set_material(0, PoiParts.kit_material("wall"))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D.IDENTITY)
	mm.set_instance_custom_data(0, _kit_custom(spec))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	return mmi


static func _flat(rect: Rect2, y: float, spec: Dictionary) -> Array:
	# Membrane: a quad with metre UVs (roof_tar tiles at 2 m) and the slab's edge strips.
	var x0: float = rect.position.x - 0.15
	var x1: float = rect.end.x + 0.15
	var z0: float = rect.position.y - 0.15
	var z1: float = rect.end.y + 0.15
	var top: float = y + 0.25
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for v: Vector3 in [Vector3(x0, top, z0), Vector3(x1, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z1)]:
		st.set_normal(Vector3.UP)
		st.set_uv(Vector2(v.x, v.z))
		st.add_vertex(v)
	var corners: Array[Vector3] = [Vector3(x0, 0, z0), Vector3(x1, 0, z0), Vector3(x1, 0, z1), Vector3(x0, 0, z1)]
	for i: int in 4:
		var a: Vector3 = corners[i]
		var b: Vector3 = corners[(i + 1) % 4]
		var n := Vector3(b.z - a.z, 0.0, a.x - b.x).normalized()
		if n.dot(Vector3(a.x + b.x, 0, a.z + b.z) * 0.5 - Vector3(rect.get_center().x, 0, rect.get_center().y)) < 0.0:
			n = -n
		var q: Array = [Vector3(a.x, y, a.z), Vector3(b.x, y, b.z), Vector3(b.x, top, b.z), Vector3(a.x, top, a.z)]
		for k: int in [0, 1, 2, 0, 2, 3]:
			var v2: Vector3 = q[k]
			st.set_normal(n)
			st.set_uv(Vector2(v2.x + v2.z, v2.y))
			st.add_vertex(v2)
	var slab: ArrayMesh = st.commit()
	slab.surface_set_material(0, _material(str(spec.get("flat_material", "roof_tar")), str(spec.get("flat_color", "#2f2e2c"))))
	var mi := MeshInstance3D.new()
	mi.name = "RoofFlat"
	mi.mesh = slab
	var out: Array = [mi]
	# Parapet: a 16 cm wall in the exterior finish (both faces and a cap), kit wall shader.
	var ph: float = float(spec.get("parapet", 0.6))
	if ph > 0.01:
		var pt := SurfaceTool.new()
		pt.begin(Mesh.PRIMITIVE_TRIANGLES)
		var rc: Array[Vector2] = [rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)]
		var w: float = 0.08
		for i2: int in 4:
			var p0: Vector2 = rc[i2]
			var p1: Vector2 = rc[(i2 + 1) % 4]
			var d: Vector2 = (p1 - p0).normalized()
			var nrm := Vector2(d.y, -d.x)                     # outward for the clockwise-in-plan corners
			if nrm.dot((p0 + p1) * 0.5 - rect.get_center()) < 0.0:
				nrm = -nrm
			var ext0: Vector2 = p0 - d * w
			var ext1: Vector2 = p1 + d * w
			for side: float in [1.0, -1.0]:
				var o: Vector2 = nrm * w * side
				var n3 := Vector3(nrm.x * side, 0.0, nrm.y * side)
				var q2: Array = [Vector3(ext0.x + o.x, y, ext0.y + o.y), Vector3(ext1.x + o.x, y, ext1.y + o.y),
					Vector3(ext1.x + o.x, top + ph, ext1.y + o.y), Vector3(ext0.x + o.x, top + ph, ext0.y + o.y)]
				# Both windings: whichever is front-facing for this side survives back-face culling.
				for k2: int in [0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2]:
					pt.set_normal(n3)
					pt.set_uv2(Vector2(0.0 if side > 0.0 else 1.0, 0.0))
					pt.set_color(Color(1.0, 0.0, 0.5, 1.0))
					pt.add_vertex(q2[k2])
			var cap: Array = [Vector3(ext0.x + nrm.x * w, top + ph, ext0.y + nrm.y * w), Vector3(ext1.x + nrm.x * w, top + ph, ext1.y + nrm.y * w),
				Vector3(ext1.x - nrm.x * w, top + ph, ext1.y - nrm.y * w), Vector3(ext0.x - nrm.x * w, top + ph, ext0.y - nrm.y * w)]
			for k3: int in [0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2]:
				pt.set_normal(Vector3.UP)
				pt.set_uv2(Vector2(0.5, 0.0))
				pt.set_color(Color(1.0, 0.0, 0.5, 1.0))
				pt.add_vertex(cap[k3])
		out.append(_kit_instance("Parapet", pt.commit(), spec))
	var faces := PackedVector3Array()
	faces.append_array([Vector3(x0, top, z0), Vector3(x1, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z1)])
	var cshape := ConcavePolygonShape3D.new()
	cshape.backface_collision = true
	cshape.set_faces(faces)
	out.append(cshape)
	return out
