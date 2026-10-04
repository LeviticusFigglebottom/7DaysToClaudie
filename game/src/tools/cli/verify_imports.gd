extends SceneTree
## Post-import check (run by `make import`): finds generated .glb scenes still carrying a glTF
## placeholder material "M_<id>" although the material library now has <id>.tres (the model was
## imported before its material existed — Godot does not track that dependency) and invalidates
## their import cache so the next `--import` pass re-runs the post-import swap.
## Exit code 2 = some imports were invalidated (run --import again), 0 = all good.

const MODELS: String = "res://assets/generated/models"
const MATERIALS: String = "res://assets/generated/materials/"

var _stale: PackedStringArray = []


func _initialize() -> void:
	_scan(MODELS)
	for path: String in _stale:
		var imp: ConfigFile = ConfigFile.new()
		if imp.load(path + ".import") != OK:
			continue
		for dest: Variant in imp.get_value("deps", "dest_files", []):
			var d: String = str(dest)
			for f: String in [d, d.get_basename() + ".md5", d.replace(".scn", ".md5")]:
				if FileAccess.file_exists(f):
					DirAccess.remove_absolute(ProjectSettings.globalize_path(f))
		var md5: String = "res://.godot/imported/%s-%s.md5" % [path.get_file(), path.md5_text()]
		if FileAccess.file_exists(md5):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(md5))
	if not _stale.is_empty():
		print("[verify-imports] %d model(s) need re-import for their materials" % _stale.size())
	quit(2 if not _stale.is_empty() else 0)


func _scan(dir: String) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	for f: String in d.get_files():
		if f.ends_with(".glb"):
			var path: String = dir.path_join(f)
			if _needs_reimport(path):
				_stale.append(path)
	for sub: String in d.get_directories():
		_scan(dir.path_join(sub))


func _needs_reimport(path: String) -> bool:
	var ps: PackedScene = load(path) as PackedScene
	if ps == null:
		return false
	var scene: Node = ps.instantiate()
	var stale: bool = false
	for n: Node in scene.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (n as MeshInstance3D).mesh
		if mesh == null:
			continue
		for i: int in mesh.get_surface_count():
			var m: Material = mesh.surface_get_material(i)
			if m != null and m.resource_name.begins_with("M_") and FileAccess.file_exists(MATERIALS + m.resource_name.substr(2) + ".tres"):
				stale = true
	scene.free()
	return stale
