extends SceneTree
## The first-hour UX audit run (first_hour_runner.gd, loaded once the autoloads exist): a new game
## on the main map driven through its first hour, a frame and the screen's words at each step.
##   make first-hour        (rendered: xvfb + software Vulkan, slow)  -> build/first_hour/


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/first_hour_runner.gd") as GDScript).new()
	runner.name = "FirstHour"
	root.add_child(runner)
