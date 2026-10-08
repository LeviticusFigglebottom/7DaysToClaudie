extends SceneTree
## Plans an organic town (ADR-0040's planner) on the main map's own ground, for authoring:
##   godot --headless --path game -s res://src/tools/cli/plan_main_town.gd -- --out /abs/plan.json \
##       [--region d6_larch_hollow] [--id pell_outskirts] [--name "Pell's Crossing"] [--kind village]
##       [--center x,z] [--radius 300] [--seed 7] [--arterial route9] [--png /abs/map.png]
## Writes {framework, town} JSON: the framework def (layout "organic", frame lots with their `y` from
## the composed ground) and the world.json `towns` entry. Everything already in the region keeps it
## out (its pads, roads, paths, spawns, caves and water). The work lives in plan_main_town_runner.gd.


func _initialize() -> void:
	await process_frame
	var script: GDScript = load("res://src/tools/cli/plan_main_town_runner.gd") as GDScript
	if script == null or not script.can_instantiate():
		printerr("[plan] the runner does not compile")
		quit(2)
		return
	var runner: Node = script.new()
	runner.name = "PlanMainTown"
	root.add_child(runner)
