extends SceneTree
## Lists a region's forest encounters (ADR-0054): where each site stands, its def and kind, its
## biome, slope and distances, and a tally per def, with the planner's time.
##   godot --headless --path game -s res://src/tools/cli/list_encounters.gd -- \
##       [--world res://world/main_map | --world-seed N [--world-set size=4,...]] [--region RID | --all]
##       [--density D] [--spacing S]
## Default: Larch Hollow on the main map at 1 m (from the region cache when it is there). A thin
## launcher: the planner needs Content, and a `-s` script is compiled before the autoloads exist.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/list_encounters_runner.gd") as GDScript).new()
	runner.name = "ListEncounters"
	root.add_child(runner)
