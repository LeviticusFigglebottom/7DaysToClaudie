extends SceneTree
## Renderer-side bakes: make bake (tree impostor atlases for ImpostorLibrary).
## Needs a real renderer (software Vulkan under Xvfb is fine). The work lives in bake_runner.gd,
## loaded once the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/bake_runner.gd") as GDScript).new()
	runner.name = "Bake"
	root.add_child(runner)
