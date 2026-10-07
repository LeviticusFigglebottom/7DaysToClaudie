extends SceneTree
## Traversal audit (ADR-0051): builds POIs and walks the player's capsule along every route step and
## through every doorway, printing what blocks them.
##   godot --headless --path game -s res://src/tools/cli/traversal_audit.gd -- [ids...] [--gen N] [--seed S]
## (no ids: every authored POI; --gen N: also N generated buildings per building template;
## --seed S: dress every building as a run with world seed S does). Lines start "TRAVERSAL".
## The work lives in traversal_audit_runner.gd, loaded after the autoloads are registered.


func _initialize() -> void:
	await process_frame
	var runner: Node = (load("res://src/tools/cli/traversal_audit_runner.gd") as GDScript).new()
	runner.name = "TraversalAudit"
	root.add_child(runner)
