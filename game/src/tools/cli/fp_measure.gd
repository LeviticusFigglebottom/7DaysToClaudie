extends SceneTree
## Where the baked first-person hands really land on a held item (TD-294): for each key of the
## given uses whose right hand is meant on a part of the item, how far the right hand's grip
## (socket_hand.R) is from that part in the rig's space. The pose solver moves grips (the reach,
## the wrist's range) and the item moves with the other hand, so a hand authored on the gun can
## land centimetres off it. --fix [--fix-out file.json] writes the misses; `tools/fp_fix_grips.py
## file.json` adds them to those keys' R.grip in viewmodel.json (then re-bake fp_arms and measure again).
##   godot --headless --path game -s res://src/tools/cli/fp_measure.gd -- --item hunting_rifle \
##       --hold rifle --uses fire_rifle,reload_rifle_open,reload_rifle,reload_rifle_close,inspect_rifle [--fix]
## Prints FP_MEASURE lines: use, frame, target, miss (cm) and the miss vector.


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("fp_measure_runner.gd")) as GDScript).new()
	runner.name = "FpMeasure"
	root.add_child(runner)
