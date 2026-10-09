extends SceneTree
## Screenshots of the menus and UI screens without loading a world (fast visual QA, ADR-0063):
##   make ui-shots [UI_SHOTS="roll,roll_campfire,menu,options,new_game"]
## Writes build/ui_shots/<name>.png. The work lives in ui_shots_runner.gd, loaded after the
## autoloads are registered.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("ui_shots_runner.gd")) as GDScript).new()
	runner.name = "UiShots"
	root.add_child(runner)
