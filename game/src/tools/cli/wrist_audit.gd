extends SceneTree
## The wrist (tether) audit (wrist_audit_runner.gd, loaded once the autoloads exist; player report
## 5): the tether raised in every movement state and with every hold class, a frame each, and how
## steady the reading hands are.
##   make wrist-audit [WRIST_RES=3840x2160] [WRIST_ARGS="--steady"]   -> build/wrist_audit/


func _initialize() -> void:
	await process_frame
	var here: String = (get_script() as Script).resource_path.get_base_dir()
	var runner: Node = (load(here.path_join("wrist_audit_runner.gd")) as GDScript).new()
	runner.name = "WristAudit"
	root.add_child(runner)
