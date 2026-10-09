extends SceneTree
## The menu freeze guard (Build #94's frozen menu): the real main menu, used for ~20 s by fake
## mouse input, every frame timed. Rendered, so it sees what a player's machine draws:
##   xvfb-run -a godot --path game --rendering-driver vulkan -s res://src/tools/cli/menu_guard.gd
##   godot --main-pack /abs/Hollowmere.pck --rendering-driver vulkan -s /abs/menu_guard.gd -- --expect-pictures
## (make menu-guard). Options after `--`: --seconds N (20), --limit S (1.5: the longest frame
## allowed), --expect-pictures (fail when the backdrop shows no pictures). Exit code = failures.
## The work lives in menu_guard_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	# The runner beside this script: res:// normally; a filesystem path when an exported build
	# (which leaves the CLI tools out) runs it with `-s /path/to/menu_guard.gd` (ADR-0036).
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("menu_guard_runner.gd")) as GDScript).new()
	runner.name = "MenuGuard"
	root.add_child(runner)
