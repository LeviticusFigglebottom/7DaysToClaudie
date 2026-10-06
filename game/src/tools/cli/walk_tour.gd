extends SceneTree
## Walks the player up to every kind of thing in the world and hits, harvests and uses it:
##   godot --headless --path game -s res://src/tools/cli/walk_tour.gd [-- --mode survival]
## Runs the game as a player would (real movement input, sprinting into things, swinging at them)
## so a crash on contact shows up as a dead process instead of a passing smoke run. Works with or
## without generated assets (ADR-0036): CI runs it on the stand-ins. Exit code = failures.
## The work lives in walk_tour_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/walk_tour_runner.gd") as GDScript).new()
	runner.name = "WalkTour"
	root.add_child(runner)
