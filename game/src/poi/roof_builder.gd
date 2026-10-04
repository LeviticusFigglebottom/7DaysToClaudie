class_name RoofBuilder
extends RefCounted
## Procedural roofs over a POI level's footprint rectangle: gable (ridge along the long side,
## overhanging eaves, gable ends in the exterior wall finish) or flat (tar slab + low parapet).
## Returns [geometry nodes..., collision Shape3D...] for the builder.

const THICK: float = 0.14


static func build(kind: String, rect: Rect2, y: float, spec: Dictionary) -> Array:
	if kind == "flat":
		return _flat(rect, y, spec)
	return _gable(rect, y, spec)


static func _roof_material(spec: Dictionary) -> Material:
	var id: String = str(spec.get("material", "roof_shingle"))
	var path: String = "res://assets/generated/materials/%s.tres" % id
	if ResourceLoader.exists(path):
		var m: Material = load(path)
		if m is BaseMaterial3D:
			(m as BaseMaterial3D).cull_mode = BaseMaterial3D.CULL_DISABLED
		return m
	var sm := StandardMaterial3D.new()
	sm.albedo_color = Color.html(str(spec.get("color", "#3b3633")))
	sm.roughness = 0.92
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	return sm


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
	for q: Array in quads:
		var n: Vector3 = ((q[1] as Vector3) - (q[0] as Vector3)).cross((q[3] as Vector3) - (q[0] as Vector3)).normalized()
		if n.y < 0.0:
			n = -n
		for tri: Array in [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]:
			for v: Vector3 in tri:
				st.set_normal(n)
				st.set_uv(Vector2(v.x + v.z, v.y * 1.6))
				st.add_vertex(v)
				faces.append(v)
		# Underside / fascia thickness: offset copy.
		for tri2: Array in [[q[0], q[2], q[1]], [q[0], q[3], q[2]]]:
			for v2: Vector3 in tri2:
				st.set_normal(-n)
				st.set_uv(Vector2(v2.x + v2.z, v2.y))
				st.add_vertex(v2 - n * THICK)
	var roof_mesh: ArrayMesh = st.commit()
	roof_mesh.surface_set_material(0, _roof_material(spec))
	var mi := MeshInstance3D.new()
	mi.name = "Roof"
	mi.mesh = roof_mesh
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
		for v3: Vector3 in [t[0], t[1], t[2]]:
			g.set_normal(t[3])
			g.set_uv(Vector2(v3.x + v3.z, -v3.y))
			g.set_uv2(Vector2(0, 0))
			g.add_vertex(v3)
			faces.append(v3)
	var gable_mesh: ArrayMesh = g.commit()
	gable_mesh.surface_set_material(0, PoiParts.kit_material("wall"))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = gable_mesh
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D.IDENTITY)
	var ext: int = PoiParts.finish_index("wall", str(spec.get("gable_finish", spec.get("exterior", "siding_white"))))
	mm.set_instance_custom_data(0, Color(ext, ext, 0.4, 0.5))
	var gmi := MultiMeshInstance3D.new()
	gmi.name = "Gables"
	gmi.multimesh = mm
	var shape := ConcavePolygonShape3D.new()
	shape.backface_collision = true
	shape.set_faces(faces)
	return [mi, gmi, shape]


static func _flat(rect: Rect2, y: float, spec: Dictionary) -> Array:
	var slab := BoxMesh.new()
	slab.size = Vector3(rect.size.x + 0.3, 0.25, rect.size.y + 0.3)
	var sm := StandardMaterial3D.new()
	sm.albedo_color = Color.html(str(spec.get("flat_color", "#2f2e2c")))
	sm.roughness = 0.95
	slab.material = sm
	var mi := MeshInstance3D.new()
	mi.name = "RoofFlat"
	mi.mesh = slab
	mi.position = Vector3(rect.get_center().x, y + 0.125, rect.get_center().y)
	var out: Array = [mi]
	var holder := MeshInstance3D.new()
	holder.name = "Parapet"
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var ph: float = float(spec.get("parapet", 0.6))
	var corners: Array[Vector2] = [rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)]
	for i: int in 4:
		var a: Vector2 = corners[i]
		var b: Vector2 = corners[(i + 1) % 4]
		var n3 := Vector3(b.y - a.y, 0, a.x - b.x).normalized()
		var quad: Array = [Vector3(a.x, y, a.y), Vector3(b.x, y, b.y), Vector3(b.x, y + ph, b.y), Vector3(a.x, y + ph, a.y)]
		for tri: Array in [[quad[0], quad[1], quad[2]], [quad[0], quad[2], quad[3]]]:
			for v: Vector3 in tri:
				st.set_normal(-n3)
				st.add_vertex(v)
	var pm: ArrayMesh = st.commit()
	var pmat := StandardMaterial3D.new()
	pmat.albedo_color = Color(0.55, 0.53, 0.5)
	pmat.cull_mode = BaseMaterial3D.CULL_DISABLED
	pm.surface_set_material(0, pmat)
	holder.mesh = pm
	out.append(holder)
	var faces := PackedVector3Array()
	var x0: float = rect.position.x - 0.15
	var x1: float = rect.end.x + 0.15
	var z0: float = rect.position.y - 0.15
	var z1: float = rect.end.y + 0.15
	var top: float = y + 0.25
	faces.append_array([Vector3(x0, top, z0), Vector3(x1, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z0), Vector3(x1, top, z1), Vector3(x0, top, z1)])
	var cshape := ConcavePolygonShape3D.new()
	cshape.backface_collision = true
	cshape.set_faces(faces)
	out.append(cshape)
	return out
