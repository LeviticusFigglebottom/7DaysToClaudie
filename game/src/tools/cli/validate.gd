extends SceneTree
## Headless validation: content cross-references, generated-asset references, POIs.
##   godot --headless --path game -s res://src/tools/cli/validate.gd [-- --strict-assets]
## Exit code 0 = clean. --strict-assets turns missing generated models/icons into errors (CI does
## this after `make assets`).

var _errors: int = 0
var _warnings: int = 0


func _initialize() -> void:
	await process_frame
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var strict: bool = args.has("--strict-assets")
	var content: Node = root.get_node("/root/Content")
	var errs: PackedStringArray = content.load_all()
	for e: String in errs:
		_err("content: " + e)
	print("[validate] content: %s" % content.summary())
	_check_assets(content, strict)
	_check_pois()
	print("[validate] %d errors, %d warnings" % [_errors, _warnings])
	quit(1 if _errors > 0 else 0)


func _check_assets(content: Node, strict: bool) -> void:
	var missing: PackedStringArray = []
	for d: ItemDef in content.all(&"item"):
		_need_model(d.model, "item %s" % d.id, missing)
	for s: StructureDef in content.all(&"structure"):
		_need_model(s.model, "structure %s" % s.id, missing)
	for sp: SpeciesDef in content.all(&"species"):
		for m: String in sp.models:
			_need_model(m, "species %s" % sp.id, missing)
	for p: PropDef in content.all(&"prop"):
		for v: Variant in p.variants.values():
			_need_model(str(v), "prop %s" % p.id, missing)
	for m: String in missing:
		if strict:
			_err("asset: " + m)
		else:
			_warn("asset: " + m)
	if not missing.is_empty() and not strict:
		print("[validate] %d generated models missing (run `make assets`)" % missing.size())


func _need_model(model_id: String, owner: String, missing: PackedStringArray) -> void:
	if model_id == "":
		return
	var path: String = "res://assets/generated/models/%s.glb" % model_id
	if not ResourceLoader.exists(path):
		missing.append("%s -> %s" % [owner, path])


func _check_pois() -> void:
	var script: Script = load("res://src/poi/poi_validator.gd") if ResourceLoader.exists("res://src/poi/poi_validator.gd") else null
	if script == null:
		return
	var report: Dictionary = script.call(&"validate_all")
	for e: String in report.get("errors", []):
		_err("poi: " + e)
	for w: String in report.get("warnings", []):
		_warn("poi: " + w)
	print("[validate] pois: %s" % report.get("summary", ""))


func _err(msg: String) -> void:
	_errors += 1
	printerr("ERROR " + msg)


func _warn(msg: String) -> void:
	_warnings += 1
	print("WARN  " + msg)
