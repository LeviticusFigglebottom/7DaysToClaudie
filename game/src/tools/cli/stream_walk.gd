extends SceneTree
## Streaming check (ADR-0038, RWG v2 Phase 2):
##   godot --headless --path game -s res://src/tools/cli/stream_walk.gd -- [--world-seed N]
##       [--world-set size=5] [--km 3] [--speed 6.2] [--laps 2]
## Starts a streamed random world and carries the player across it at sprint speed and back,
## `laps` times: late seconds (the player's region not yet attached), the longest frame, the
## streamer's counts, static memory after each return (a leak shows as growth). Exit 1 when the
## player outran the streaming for more than 2 s or memory grew more than 5% between returns.
## The work lives in stream_walk_runner.gd (loaded once autoloads exist).


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("stream_walk_runner.gd")) as GDScript).new()
	runner.name = "StreamWalk"
	root.add_child(runner)
