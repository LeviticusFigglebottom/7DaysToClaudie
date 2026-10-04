extends SceneTree
## Fast compile check: loads every GDScript under res://src (and tests) and reports failures.
##   godot --headless --path game -s res://src/tools/cli/check_scripts.gd

var _fail: int = 0
var _count: int = 0


func _initialize() -> void:
	await process_frame
	for root_dir: String in ["res://src", "res://tests"]:
		_scan(root_dir)
	print("[check] %d scripts, %d failed" % [_count, _fail])
	quit(1 if _fail > 0 else 0)


func _scan(dir_path: String) -> void:
	var d := DirAccess.open(dir_path)
	if d == null:
		return
	for f: String in d.get_files():
		if f.ends_with(".gd"):
			_count += 1
			var path: String = dir_path.path_join(f)
			var s: Script = ResourceLoader.load(path)
			if s == null or not s.can_instantiate() and not path.ends_with("_def.gd"):
				_fail += 1
				printerr("[check] FAILED ", path)
	for sub: String in d.get_directories():
		_scan(dir_path.path_join(sub))
