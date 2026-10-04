extends SceneTree
## POI layout preview: builds authored buildings into an empty lit scene and saves screenshots
## (per-level cut-away plans with route/sleeper/pickup markers + exterior views) for layout QA.
##   make poi-preview POI="mile9_diner pell_pharmacy" [POI_ARGS="--size 1600x900 --no-exterior"]
##   (= xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/poi_preview.gd -- \
##        --out build/poi_preview mile9_diner ...)
## The work lives in poi_preview_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/poi_preview_runner.gd") as GDScript).new()
	runner.name = "PoiPreview"
	root.add_child(runner)
