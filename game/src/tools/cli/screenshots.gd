extends SceneTree
## Screenshot suite (visual QA): make screenshots [SHOTS_ARGS="--only name1,name2 --settle 6"]
## Needs a real renderer (software Vulkan under Xvfb is fine). The work lives in
## screenshots_runner.gd, loaded once the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/screenshots_runner.gd") as GDScript).new()
	runner.name = "Screenshots"
	root.add_child(runner)
