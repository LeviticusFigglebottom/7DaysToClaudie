@tool
extends EditorScenePostImport
## Post-import for every generated .glb (set in the .import sidecar by the asset pipeline).
## Swaps glTF placeholder materials named "M_<id>" for the generated material library
## (res://assets/generated/materials/<id>.tres) so all assets share real, data-driven materials.
## Unknown ids keep the glTF fallback colour and log a warning (add them to materials.json).

const MATERIAL_DIR: String = "res://assets/generated/materials/"


func _post_import(scene: Node) -> Object:
	_walk(scene)
	return scene


func _walk(n: Node) -> void:
	if n is MeshInstance3D:
		_remap((n as MeshInstance3D).mesh)
	for c: Node in n.get_children():
		_walk(c)


func _remap(mesh: Mesh) -> void:
	if mesh == null:
		return
	for i: int in mesh.get_surface_count():
		var m: Material = mesh.surface_get_material(i)
		if m == null:
			continue
		var mat_name: String = m.resource_name
		if not mat_name.begins_with("M_"):
			continue
		var path: String = MATERIAL_DIR + mat_name.substr(2) + ".tres"
		if ResourceLoader.exists(path):
			mesh.surface_set_material(i, load(path))
		else:
			push_warning("post-import: material '%s' has no %s (add it to data/materials/materials.json)" % [mat_name, path])
