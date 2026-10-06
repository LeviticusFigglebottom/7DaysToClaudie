extends SceneTree
## Generates a random world (ADR-0031) and writes its map, for QA:
##   godot --headless --path game -s res://src/tools/cli/rwg_preview.gd -- --seed 1234 --size 5 \
##       --out /abs/path.png [--preset standard] [--set towns=4 --set terrain=hilly ...] [--px 1024] [--fresh]
##       [--compose] [--crop x,z,metres]
## Prints the world's id, folder, towns, places, rivers, lakes, roads, warnings and timings.
## A thin launcher: the generator needs Content (POI footprints, templates), and a `-s` script is
## compiled before the autoloads exist, so the work lives in rwg_preview_runner.gd, loaded a frame
## later.


func _initialize() -> void:
	await process_frame
	var script: GDScript = load("res://src/tools/cli/rwg_preview_runner.gd") as GDScript
	if script == null or not script.can_instantiate():
		printerr("[rwg] the preview runner does not compile")
		quit(2)
		return
	var runner: Node = script.new()
	runner.name = "RwgPreview"
	root.add_child(runner)
