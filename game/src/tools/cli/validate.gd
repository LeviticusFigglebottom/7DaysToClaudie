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
	_check_world_gen(content)
	# Climbable structures (ADR-0057): every "climb" structure has its ladder or rope laid out.
	var climb: Script = load("res://src/building/climb_mount.gd")
	if climb != null:
		for e3: String in climb.call(&"problems", content):
			_err(e3)
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
	for w: WildlifeDef in content.all(&"wildlife"):
		for m: Variant in w.models.keys():
			_need_model(str(m), "wildlife %s" % w.id, missing)
		_need_model(w.model, "wildlife %s" % w.id, missing)
	# Garden crops (ADR-0049): every stage, and the dead plant they all share.
	for c: CropDef in content.all(&"crop"):
		for i: int in c.stages:
			_need_model(c.stage_model(i), "crop %s" % c.id, missing)
	if not content.all(&"crop").is_empty():
		_need_model("crops/dead_plant", "crops", missing)  # FarmVisual.DEAD_MODEL (no autoload classes in -s scripts)
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


## Random worlds (ADR-0031): data/config/world_gen.json against its typed schema (unknown keys,
## option specs, presets, the places and frameworks its pool names).
func _check_world_gen(content: Node) -> void:
	var script: Script = load("res://src/worldgen/rwg/world_gen_settings.gd")
	if script == null:
		return
	var errs: PackedStringArray = script.call(&"schema_errors", content)
	for e: String in errs:
		_err("world_gen: " + e)
	print("[validate] world_gen: %d options, %d presets" % [(script.call(&"options") as Dictionary).size(), (script.call(&"presets") as Dictionary).size()])
	# The organic town planner's tuning (ADR-0040): data/config/town_planner.json.
	var planner: Script = load("res://src/worldgen/rwg/rwg_town_planner.gd")
	if planner != null:
		for e2: String in planner.call(&"config_errors", content.call(&"config", &"town_planner")):
			_err("town_planner: " + e2)


func _err(msg: String) -> void:
	_errors += 1
	printerr("ERROR " + msg)


func _warn(msg: String) -> void:
	_warnings += 1
	print("WARN  " + msg)
