extends SceneTree
## Exterior QA renders for the moon, bridges, prop lights and the Program drone (ADR-0023):
##   flock build/.godot.lock xvfb-run -a -s "-screen 0 1920x1080x24" .tools/godot/godot --path game \
##       --rendering-driver vulkan --audio-driver Dummy --resolution 1600x900 \
##       -s res://src/tools/cli/exterior_qa.gd -- --out /abs/dir [--only moon_full,lamps_night] \
##       [--settle 4] [--stream-wait 240]
## The work lives in exterior_qa_runner.gd, loaded once the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/exterior_qa_runner.gd") as GDScript).new()
	runner.name = "ExteriorQA"
	root.add_child(runner)
