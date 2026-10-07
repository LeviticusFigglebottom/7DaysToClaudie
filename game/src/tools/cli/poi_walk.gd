extends SceneTree
## Headless POI traversal bot (the owner's priority #2):
##   godot --headless --fixed-fps 60 --path game -s res://src/tools/cli/poi_walk.gd -- \
##       [--poi id[,id]] [--all] [--pool] [--generated N] [--seed N] [--out DIR] [--verbose] [ids...]
## Ids: a POI id, "gen:<template>:<seed>", "lot:<framework>:<lot>". The real Player body walks each
## building's route and every room it can reach; see poi_walk_runner.gd and docs/DEBUG_TOOLS.md.
## Exit code = buildings with blocking problems. The work lives in poi_walk_runner.gd, loaded after
## the autoloads are registered (the slice_smoke pattern).


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("poi_walk_runner.gd")) as GDScript).new()
	runner.name = "PoiWalk"
	root.add_child(runner)
