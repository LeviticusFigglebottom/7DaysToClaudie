extends SceneTree
## Captures the New Game screen's World tab with a generated map preview (ADR-0031), for UI QA:
##   xvfb-run godot --path game --rendering-driver vulkan --resolution 1600x900 \
##       -s res://src/tools/cli/rwg_preview_menu.gd -- --out /abs/menu.png [--world-seed N]
## Opens the main menu, presses Random World, generates the preview and saves the screen. Prints
## "SHOT done" at the end (tools/qa_watchdog.sh).


func _initialize() -> void:
	await process_frame
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = args[args.find("--out") + 1] if args.find("--out") >= 0 else "res://../build/rwg_menu.png"
	var main: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(main)
	for i: int in 3:
		await process_frame
	main.call(&"_open_new_game", true)
	for i2: int in 5:
		await process_frame
	var panel: Node = null
	for c: Node in main.get_children():
		if c.get_class() == "PanelContainer" and c.get(&"start_random") != null:
			panel = c
	if panel == null:
		printerr("SHOT no New Game panel")
		quit(1)
		return
	if args.find("--world-seed") >= 0:
		(panel.get(&"_wseed") as LineEdit).text = args[args.find("--world-seed") + 1]
	panel.call(&"_generate_preview")
	var t0: int = Time.get_ticks_msec()
	while int(panel.get(&"_task")) >= 0 and Time.get_ticks_msec() - t0 < 180000:
		await process_frame
	for i3: int in 10:
		await process_frame
	root.get_viewport().get_texture().get_image().save_png(out)
	print("SHOT %s" % out)
	print("SHOT done")
	quit(0)
