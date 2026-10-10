extends SceneTree
## POI pads on the navmesh (TD-340): whether each building's yard is joined to the ground round it.
##   godot --headless --path game -s res://src/tools/cli/nav_pad_check.gd -- [--world random --world-seed N] [--poi id,id] [--max N]
## For each building (nearest the drop first): the player stands beside it, its tiles bake, and paths
## run from 16 points inside its footprint to points 8 m outside its edge. A path over 2.5 times the
## straight line, none at all, or an end the navmesh doesn't reach is a finding. The work lives in
## nav_pad_check_runner.gd.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("nav_pad_check_runner.gd")) as GDScript).new()
	runner.name = "NavPadCheck"
	root.add_child(runner)
