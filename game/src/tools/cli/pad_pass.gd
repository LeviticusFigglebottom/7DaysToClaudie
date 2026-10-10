extends SceneTree
## The pad-only pass: the real menu, a new game, the intro, the journal, the roll, crafting, the
## map, the tether and pause, driven by gamepad events alone (no mouse, no keyboard). Rendered with
## the 3D off (the screens are what is under test), so under Xvfb:
##   xvfb-run -a godot --path game --rendering-driver vulkan -s res://src/tools/cli/pad_pass.gd
##   godot --main-pack /abs/Hollowmere.pck ... -s /abs/pad_pass.gd
## Prints PAD lines, one per step (OK / FAIL and what had the focus). Exit code = failures.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("pad_pass_runner.gd")) as GDScript).new()
	runner.name = "PadPass"
	root.add_child(runner)
