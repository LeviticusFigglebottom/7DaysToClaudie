extends SceneTree
## Walks the player up to every kind of thing in the world and hits, harvests and uses it:
##   godot --headless --path game -s res://src/tools/cli/walk_tour.gd [-- --mode survival]
##       [--world random --world-seed N --world-set size=3]   (a random world, ADR-0031)
## Runs the game as a player would (real movement input, sprinting into things, swinging at them)
## so a crash on contact shows up as a dead process instead of a passing smoke run. Works with or
## without generated assets (ADR-0036): CI runs it on the stand-ins. Exit code = failures.
## The work lives in walk_tour_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	# The runner beside this script: res:// normally; a filesystem path when an exported build
	# (which leaves the CLI tools out) runs it with `-s /path/to/walk_tour.gd` (ADR-0036).
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("walk_tour_runner.gd")) as GDScript).new()
	runner.name = "WalkTour"
	root.add_child(runner)
