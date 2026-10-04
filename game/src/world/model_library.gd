class_name ModelLibrary
extends RefCounted
## Loads generated model scenes as single merged meshes (for MultiMesh instancing) plus their
## collision shapes, with procedural placeholders when an asset has not been generated yet.
## Cached for the session. Thread-safe for reads after first load (load on main thread).

static var _meshes: Dictionary = {}
static var _shapes: Dictionary = {}
static var _mutex := Mutex.new()


static func model_path(model_id: String) -> String:
	return "res://assets/generated/models/%s.glb" % model_id


static func has_model(model_id: String) -> bool:
	return ResourceLoader.exists(model_path(model_id))


## Merged mesh for a model id (all MeshInstance3D surfaces baked into one ArrayMesh).
static func mesh(model_id: String, placeholder: String = "box") -> Mesh:
	_mutex.lock()
	var m: Mesh = _meshes.get(model_id)
	_mutex.unlock()
	if m != null:
		return m
	if has_model(model_id):
		var scene: Node3D = (load(model_path(model_id)) as PackedScene).instantiate()
		m = merge_meshes(scene)
		_extract_shapes(model_id, scene)
		scene.free()
	if m == null:
		m = make_placeholder(placeholder)
	_mutex.lock()
	_meshes[model_id] = m
	_mutex.unlock()
	return m


## [{shape: Shape3D, transform: Transform3D}] from the model's collision nodes (empty if none).
static func shapes(model_id: String) -> Array:
	mesh(model_id)
	return _shapes.get(model_id, [])


static func merge_meshes(root: Node) -> ArrayMesh:
	var out := ArrayMesh.new()
	var surfaces: Dictionary = {}
	_collect(root, Transform3D.IDENTITY, surfaces)
	if surfaces.is_empty():
		return null
	# One surface per material: concatenate arrays with transformed vertices.
	for mat: Variant in surfaces.keys():
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for entry: Array in surfaces[mat]:
			var arrays: Array = entry[0]
			var xf: Transform3D = entry[1]
			var tmp := ArrayMesh.new()
			tmp.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			st.append_from(tmp, 0, xf)
		var arr: Array = st.commit_to_arrays()
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		if mat is Material:
			out.surface_set_material(out.get_surface_count() - 1, mat)
	return out


static func _collect(n: Node, xf: Transform3D, surfaces: Dictionary) -> void:
	var here: Transform3D = xf
	if n is Node3D:
		here = xf * (n as Node3D).transform
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		var mi: MeshInstance3D = n
		for s: int in mi.mesh.get_surface_count():
			var mat: Material = mi.get_surface_override_material(s)
			if mat == null:
				mat = mi.mesh.surface_get_material(s)
			var key: Variant = mat if mat != null else "none"
			if not surfaces.has(key):
				surfaces[key] = []
			(surfaces[key] as Array).append([mi.mesh.surface_get_arrays(s), here])
	for c: Node in n.get_children():
		if c is CollisionObject3D:
			continue
		_collect(c, here if n is Node3D else xf, surfaces)


static func _extract_shapes(model_id: String, root: Node) -> void:
	var list: Array = []
	for c: Node in root.find_children("*", "CollisionShape3D", true, false):
		var cs: CollisionShape3D = c
		if cs.shape != null:
			list.append({"shape": cs.shape, "transform": _global_xf(cs, root)})
	_mutex.lock()
	_shapes[model_id] = list
	_mutex.unlock()


static func _global_xf(n: Node3D, root: Node) -> Transform3D:
	var xf: Transform3D = n.transform
	var p: Node = n.get_parent()
	while p != null and p != root:
		if p is Node3D:
			xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf


## Simple stand-ins so the world is playable before `make assets`.
static func make_placeholder(kind: String) -> Mesh:
	var mat := StandardMaterial3D.new()
	mat.roughness = 0.9
	match kind:
		"conifer":
			var st := SurfaceTool.new()
			var trunk := CylinderMesh.new()
			trunk.top_radius = 0.12
			trunk.bottom_radius = 0.3
			trunk.height = 20.0
			var crown := CylinderMesh.new()
			crown.top_radius = 0.05
			crown.bottom_radius = 3.0
			crown.height = 16.0
			var am := ArrayMesh.new()
			var tm := StandardMaterial3D.new()
			tm.albedo_color = Color(0.22, 0.15, 0.1)
			var cm := StandardMaterial3D.new()
			cm.albedo_color = Color(0.08, 0.16, 0.08)
			am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _shifted(trunk, Vector3(0, 10, 0)))
			am.surface_set_material(0, tm)
			am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _shifted(crown, Vector3(0, 13, 0)))
			am.surface_set_material(1, cm)
			return am
		"deciduous":
			var am2 := ArrayMesh.new()
			var trunk2 := CylinderMesh.new()
			trunk2.top_radius = 0.08
			trunk2.bottom_radius = 0.18
			trunk2.height = 14.0
			var crown2 := SphereMesh.new()
			crown2.radius = 3.0
			crown2.height = 7.0
			var tm2 := StandardMaterial3D.new()
			tm2.albedo_color = Color(0.75, 0.73, 0.68)
			var cm2 := StandardMaterial3D.new()
			cm2.albedo_color = Color(0.45, 0.4, 0.1)
			am2.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _shifted(trunk2, Vector3(0, 7, 0)))
			am2.surface_set_material(0, tm2)
			am2.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _shifted(crown2, Vector3(0, 11, 0)))
			am2.surface_set_material(1, cm2)
			return am2
		"rock":
			var s := SphereMesh.new()
			s.radius = 1.0
			s.height = 1.3
			s.radial_segments = 8
			s.rings = 4
			mat.albedo_color = Color(0.42, 0.41, 0.39)
			s.material = mat
			return s
		"log":
			# 4 m log lying along +X (structure/log entity convention).
			var cyl := CylinderMesh.new()
			cyl.top_radius = 0.17
			cyl.bottom_radius = 0.17
			cyl.height = 4.0
			cyl.radial_segments = 10
			cyl.rings = 1
			var arr: Array = cyl.get_mesh_arrays()
			var rot := Basis(Vector3.BACK, -PI * 0.5)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var norms: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
			for i: int in verts.size():
				verts[i] = rot * verts[i]
				norms[i] = rot * norms[i]
			arr[Mesh.ARRAY_VERTEX] = verts
			arr[Mesh.ARRAY_NORMAL] = norms
			arr[Mesh.ARRAY_TANGENT] = null
			var lm := ArrayMesh.new()
			lm.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
			mat.albedo_color = Color(0.36, 0.27, 0.19)
			lm.surface_set_material(0, mat)
			return lm
		"plant":
			var q := QuadMesh.new()
			q.size = Vector2(0.6, 0.6)
			q.center_offset = Vector3(0, 0.3, 0)
			mat.albedo_color = Color(0.2, 0.32, 0.1)
			mat.cull_mode = BaseMaterial3D.CULL_DISABLED
			q.material = mat
			return q
	var b := BoxMesh.new()
	b.size = Vector3(0.5, 0.5, 0.5)
	b.material = mat
	return b


static func _shifted(m: PrimitiveMesh, offset: Vector3) -> Array:
	var arr: Array = m.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += offset
	arr[Mesh.ARRAY_VERTEX] = v
	return arr
