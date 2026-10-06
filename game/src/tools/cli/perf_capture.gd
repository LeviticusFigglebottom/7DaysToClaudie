extends SceneTree
## Performance capture (TD-003, ADR-0036):
##   godot --path game -s res://src/tools/cli/perf_capture.gd -- [--out DIR] [--frames N] [--no-ablate]
## Headless it measures CPU: each world module's share of the main thread's process and physics time
## (measured by switching the module off for a while) and the hitches of sprinting through
## streaming terrain. Rendered (Xvfb + Vulkan) it adds draw calls, primitives and objects per view;
## software Vulkan frame times are not GPU numbers (TD-002). The work lives in perf_capture_runner.gd.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("perf_capture_runner.gd")) as GDScript).new()
	runner.name = "PerfCapture"
	root.add_child(runner)
