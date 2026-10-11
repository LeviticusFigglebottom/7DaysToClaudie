extends SceneTree
## A Hum night against a player holed up indoors (the hub's audit after TD-340 / TD-342 / TD-011):
##   godot --headless --fixed-fps 60 --path game -s res://src/tools/cli/hum_siege.gd -- \
##       [--mode house|shelter] [--secs 240] [--out user://hum_siege]
## house: the player deep in a town house (doors as built: closed, boarded, open windows);
## shelter: the player in a sealed 4 x 4 m log hut. Reports how and when the horde gets in, bodies
## stuck outside a wall for 10 s or more, how far the flow field and each body's own nav path
## disagree, and frame time with the full horde. The work is in hum_siege_runner.gd.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("hum_siege_runner.gd")) as GDScript).new()
	runner.name = "HumSiege"
	root.add_child(runner)
