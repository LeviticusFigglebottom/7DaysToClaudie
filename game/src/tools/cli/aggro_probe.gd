extends SceneTree
## How far the Hollowed notice the player (the owner's priority 1: "passive until close"):
##   godot --headless --path game -s res://src/tools/cli/aggro_probe.gd -- [--enemies hollow,lurcher]
## For each enemy, day and night, the player standing or walking, it spawns one awake wanderer
## facing the player at 5..60 m and reports whether it starts a chase within 4 s.
##   godot --headless --fixed-fps 60 --path game -s res://src/tools/cli/aggro_probe.gd -- --flat \
##       [--enemies hollow,lurcher --dists 10,20,30,40,60 --stances still,walk,crouch,sprint,torch,cover]
## runs the flat-floor matrix instead (time to notice and to reach, docs/AI_TUNING.md).
## The work lives in aggro_probe_runner.gd, loaded once autoloads exist.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("aggro_probe_runner.gd")) as GDScript).new()
	runner.name = "AggroProbe"
	root.add_child(runner)
