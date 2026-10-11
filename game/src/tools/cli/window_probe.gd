extends SceneTree
## Whether the Hollowed come in through windows in a real town (TD-011, WindowLinks):
##   godot --headless --fixed-fps 60 --path game -s res://src/tools/cli/window_probe.gd -- [--trials 6]
## The work lives in window_probe_runner.gd, loaded once autoloads exist.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("window_probe_runner.gd")) as GDScript).new()
	runner.name = "WindowProbe"
	root.add_child(runner)
