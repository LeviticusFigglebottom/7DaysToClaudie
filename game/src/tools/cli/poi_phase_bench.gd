extends SceneTree
## Times PoiBuilder's streamed build step by step (TD-107, ADR-0038 §8): for each building the
## longest step of each phase in ms (the fastest of --repeat builds), its worst step and its steps.
##   godot --headless --path game -s res://src/tools/cli/poi_phase_bench.gd -- \
##       [--repeat 3] [--slice 8] [--generated 2] [poi_id ...]
## --slice MS steps with that budget, as PoiManager does (0 = one whole phase a step); no ids =
## the heavy authored buildings plus every pool building (wilderness pool and town set pieces).
## A thin launcher: the work lives in poi_phase_bench_runner.gd, loaded once the autoloads exist.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/poi_phase_bench_runner.gd") as GDScript).new()
	runner.name = "PoiPhaseBench"
	root.add_child(runner)
