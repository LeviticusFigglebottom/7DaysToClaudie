extends SceneTree
## Watch a Hum close up (TD-011: does the crowd separation look right?): a forced Hum in Pell's
## Crossing with the player standing in the street (god mode); once enough of the Hum's Hollowed are within
## 30 m it saves a strip of frames from above and behind the player and logs, for the bodies within
## 30 m, how much their headings turn a tick (jitter) and how often two stand closer than 0.5 m.
##   xvfb-run godot --path game --rendering-driver opengl3 -s res://src/tools/cli/hum_watch.gd -- \
##       --out DIR [--frames 16] [--every 0.5] [--start 6] [--height 18] [--no-crowd]
## The work lives in hum_watch_runner.gd (autoload classes are only usable after a frame).


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("hum_watch_runner.gd")) as GDScript).new()
	runner.name = "HumWatch"
	root.add_child(runner)
