extends SceneTree
## A staged look at the far-tree impostors (TD-005 review): every tree species in a row of its
## impostor quads, one per variant, in summer and in winter, from 60-140 m. A thin SceneTree: the
## runner (impostor_shot_runner.gd) needs the autoloads.
##
##   xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/impostor_shot.gd -- --out DIR
## Writes DIR/impostors_summer.png and DIR/impostors_winter.png.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/impostor_shot_runner.gd") as GDScript).new()
	root.add_child(runner)
