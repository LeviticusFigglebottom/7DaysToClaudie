extends SceneTree
## Renders one shot of the showcase trailer (make trailer-shot SHOT=<id>; tools/trailer_shot.sh
## runs it under Movie Maker). The work lives in trailer_runner.gd, loaded once the autoloads are
## registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/trailer_runner.gd") as GDScript).new()
	runner.name = "Trailer"
	root.add_child(runner)
