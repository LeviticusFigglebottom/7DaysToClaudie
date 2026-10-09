extends SceneTree
## Renders the pre-rendered backdrops (ADR-0065): make stills. Needs a real renderer (software
## Vulkan under Xvfb is fine). The work lives in stills_runner.gd, loaded once the autoloads are
## registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/stills_runner.gd") as GDScript).new()
	runner.name = "Stills"
	root.add_child(runner)
