extends SceneTree
## Frame times of a new game's load with and without the intro (ADR-0064's evidence):
##   godot --headless --path game -s res://src/tools/cli/intro_load_probe.gd -- [--intro] [--world random --world-seed N]
## Prints one INTRO_PROBE summary line: frames, the worst frame and frames over 50 ms during the
## load, and (with --intro) the same for frames where the intro was moving on screen (fading or
## typing), which are the ones a long frame would show as a stutter. Headless: a frame's time is
## its main-thread work, which is what the load's steps cost. The work lives in the runner.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("intro_load_probe_runner.gd")) as GDScript).new()
	runner.name = "IntroLoadProbe"
	root.add_child(runner)
