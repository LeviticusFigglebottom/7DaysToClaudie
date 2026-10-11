extends SceneTree
## Light on walking into a room (player report 3, ADR-0050): the camera walks in from outside a
## building at 13:00 and the picture's mean luma is printed every 0.25 s for the first 5 s, with the
## room's probe state (parked, waiting, rendered) and the stand-in fill beside it.
##   xvfb-run godot --path game --rendering-driver vulkan --fixed-fps 60 -s res://src/tools/cli/entry_light.gd --
##       [--out DIR] [--only garage_office,pharmacy_stock] [--before] [--cold]
## --before switches off what the fix added (the room jumping the probe queue, the stand-in fill,
## cellars at 0.3) to measure the old behaviour. Run with --fixed-fps 60 so a frame is 1/60 s of
## game time however slowly software Vulkan draws it. The work lives in entry_light_runner.gd.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var script: GDScript = load(here.path_join("entry_light_runner.gd")) as GDScript
	if script == null or not script.can_instantiate():
		printerr("ENTRY the runner doesn't compile")
		quit(3)
		return
	var runner: Node = script.new()
	runner.name = "EntryLight"
	root.add_child(runner)
