extends SceneTree
## First-person viewmodel QA renders (ADR-0029): the arms and held items in their hold poses,
## mid-swing, guarding, reading the tether, lit at noon or by their own torch at night, in a small
## lit clearing (no world load, so it takes seconds rather than minutes):
##   flock build/.godot.lock xvfb-run -a -s "-screen 0 1920x1080x24" .tools/godot/godot --path game \
##       --rendering-driver vulkan --audio-driver Dummy --resolution 1600x900 \
##       -s res://src/tools/cli/fp_preview.gd -- --out /abs/dir [--only axe_idle,torch_night] [--size 1280x720]
## The shots (an item, optionally an action frozen at a frame, the guard, the tether, lit, at night,
## a forced base loop) are listed in fp_preview_runner.gd SHOTS; --only picks some by name. The work
## lives in fp_preview_runner.gd, loaded once the autoloads exist.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/fp_preview_runner.gd") as GDScript).new()
	runner.name = "FpPreview"
	root.add_child(runner)
