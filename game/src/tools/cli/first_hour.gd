extends SceneTree
## The first-hour UX audit run (first_hour_runner.gd, loaded once the autoloads exist): a new game
## on the main map driven through its first hour, a frame and the screen's words at each step.
##   make first-hour        (rendered: xvfb + software Vulkan, slow)  -> build/first_hour/


func _initialize() -> void:
	await process_frame
	# The runner beside this script: res:// normally; a filesystem path when an exported build
	# (which leaves the CLI tools out) runs it with `-s /path/to/first_hour.gd` (ADR-0036).
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("first_hour_runner.gd")) as GDScript).new()
	runner.name = "FirstHour"
	root.add_child(runner)
