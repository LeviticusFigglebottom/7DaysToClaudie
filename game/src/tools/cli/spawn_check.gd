extends SceneTree
## Starts a new game the way the New Game screen does and checks the player can move and look
## (player report 3: a new random world left the player unable to move, the arms adrift):
##   godot --headless --path game -s res://src/tools/cli/spawn_check.gd -- [--world random
##       --world-seed N --world-set size=4] [--no-stream] [--load SLOT]
## Exit code = failures. The work lives in spawn_check_runner.gd, loaded once autoloads exist.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("spawn_check_runner.gd")) as GDScript).new()
	runner.name = "SpawnCheck"
	root.add_child(runner)
