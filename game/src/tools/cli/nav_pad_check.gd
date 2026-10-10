extends SceneTree
## POI pads on the navmesh (TD-340): whether each building's yard is joined to the ground round it.
##   godot --headless --path game -s res://src/tools/cli/nav_pad_check.gd -- [--world random --world-seed N] [--poi id,id] [--max N]
## For each building (nearest the drop first): the player stands beside it, its tiles bake, and paths
## run in 16 directions from its pad (1.25 m off its last built cell that way: a yard, or the ground
## off the wall; never a room, where a shut door rightly holds a path) to points 8 m outside its edge. A path over 2.5 times the
## straight line, none at all, or an end the navmesh doesn't reach is a finding. The work lives in
## nav_pad_check_runner.gd.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var script: GDScript = load(here.path_join("nav_pad_check_runner.gd")) as GDScript
	if script == null or not script.can_instantiate():
		# A runner that doesn't compile would leave the tool idling until its timeout.
		printerr("[navpad] the runner doesn't compile")
		quit(3)
		return
	var runner: Node = script.new()
	runner.name = "NavPadCheck"
	root.add_child(runner)
