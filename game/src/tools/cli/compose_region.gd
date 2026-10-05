extends SceneTree
## Composes a region and writes inspection images (hillshade, biome, dominant splat, vegetation).
##   godot --headless --path game -s res://src/tools/cli/compose_region.gd -- \
##       [--world res://world/main_map] [--region d6_larch_hollow] [--spacing 1.0] [--out DIR] [--no-cache]
## A thin launcher: the composer needs Content (frameworks, POIs), and a `-s` script is compiled
## before the autoloads exist, so the work lives in compose_region_runner.gd, loaded a frame later.
## Composed without content, the region lacked its town pads and streets, and that result was
## cached under the real input hash for the game to load.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/compose_region_runner.gd") as GDScript).new()
	runner.name = "ComposeRegion"
	root.add_child(runner)
