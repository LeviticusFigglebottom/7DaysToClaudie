extends SceneTree
## Continue puts the player back where they saved (player report 3), headless:
##   godot --headless --path game -s res://src/tools/cli/continue_check.gd [-- --world random --world-seed 7 --world-set size=5]
## New game -> move the player far from the drop site, turn and tilt the view -> save -> quit to
## the menu -> Continue (the newest slot) -> the player stands where they saved, facing the same
## way, unhurt, and stays there. Exit code = failures. The work lives in continue_check_runner.gd.
## Options: --distance M (how far to move, default 160), --indoor (save upstairs in the nearest
## building), --no-stream (random world built whole), --slow-ms N (slow frames while loading),
## --late-ground S (the ground's collision arrives S seconds after the player ticks, as on a real
## renderer, which meshes the terrain on worker threads: before the fix the player fell meanwhile
## and died of the landing, then respawned at the drop site).


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("continue_check_runner.gd")) as GDScript).new()
	runner.name = "ContinueCheck"
	root.add_child(runner)
