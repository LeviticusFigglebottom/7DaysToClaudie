extends SceneTree
## Measures how roads and town pads sit on the land of a world, for terrain QA (player report 4):
##   godot --headless --path game -s res://src/tools/cli/terrain_audit.gd -- [--world DIR | --seed N
##       --size S [--preset id] [--set k=v ...]] [--regions a,b | --all] [--spacing 2] [--json out.json]
## Per region and in all: the cross-slope over each road's paved width, the grade along it, and the
## banks beside it (how high, how steep, and how far a steep bank runs unbroken along the road), and
## the banks round town lots. The work lives in terrain_audit_runner.gd, loaded once the autoloads
## exist (the composer needs Content for frameworks and POIs).


func _initialize() -> void:
	await process_frame
	var script: GDScript = load("res://src/tools/cli/terrain_audit_runner.gd") as GDScript
	if script == null or not script.can_instantiate():
		printerr("[audit] the runner does not compile")
		quit(2)
		return
	var runner: Node = script.new()
	runner.name = "TerrainAudit"
	root.add_child(runner)
