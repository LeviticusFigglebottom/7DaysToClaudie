extends SceneTree
## Plans organic towns (ADR-0040, RwgTownPlanner) on synthetic land and draws them, for QA:
##   godot --headless --path game -s res://src/tools/cli/rwg_town_preview.gd -- \
##       [--out /abs/dir] [--kind hamlet,village,town] [--land rolling,hilly] [--seeds 1,2,3] [--px 1400]
## Writes <kind>_<land>_<seed>.png (the town and its outskirts) and <kind>_<land>_<seed>_core.png (the
## town disc) and prints each plan's counts and time. A 2D Image drawn in code: no 3D render, no
## render lock. A thin launcher (the CLAUDE.md gotcha): the work lives in rwg_town_preview_runner.gd,
## loaded a frame later.


func _initialize() -> void:
	await process_frame
	var script: GDScript = load("res://src/tools/cli/rwg_town_preview_runner.gd") as GDScript
	if script == null or not script.can_instantiate():
		printerr("[towns] the preview runner does not compile")
		quit(2)
		return
	var runner: Node = script.new()
	runner.name = "RwgTownPreview"
	root.add_child(runner)
