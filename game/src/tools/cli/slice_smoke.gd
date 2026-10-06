extends SceneTree
## End-to-end smoke run of the M1 slice, headless:
##   godot --headless --path game -s res://src/tools/cli/slice_smoke.gd      (make smoke)
## New game -> world ready -> fell a tree -> carry a log -> place logs (freeform) -> lay out and
## complete a campfire -> craft a stone axe -> survival ticks -> night wanderers -> a Hum night
## with waves and a memory report -> save -> load -> state restored. Exit code = failures.
## The work lives in slice_smoke_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	# The runner beside this script: res:// normally; a filesystem path when an exported build
	# (which leaves the CLI tools out) runs it with `-s /path/to/slice_smoke.gd` (ADR-0036).
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("slice_smoke_runner.gd")) as GDScript).new()
	runner.name = "SliceSmoke"
	root.add_child(runner)
