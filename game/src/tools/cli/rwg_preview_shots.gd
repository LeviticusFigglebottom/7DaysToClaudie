extends SceneTree
## In-world screenshots of a random world (ADR-0031), for visual QA:
##   xvfb-run godot --path game --rendering-driver vulkan --resolution 1600x900 \
##       -s res://src/tools/cli/rwg_preview_shots.gd -- --out /abs/dir [--world-seed N] \
##       [--world-preset id] [--world-set key=value ...] [--only a,b] [--settle 4]
## Starts a game on the generated world and frames shots from the world's own data: a town's main
## street and the town from above, a river valley, a wilderness place, the drop site and the land
## from the air. Prints "SHOT done" at the end (tools/qa_watchdog.sh). The work lives in
## rwg_preview_shots_runner.gd, loaded once the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var script: GDScript = load("res://src/tools/cli/rwg_preview_shots_runner.gd") as GDScript
	if script == null or not script.can_instantiate():
		printerr("SHOT the runner does not compile")
		quit(2)
		return
	var runner: Node = script.new()
	runner.name = "RwgShots"
	root.add_child(runner)
