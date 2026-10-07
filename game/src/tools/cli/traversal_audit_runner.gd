extends Node3D
## Runs TraversalAudit over POIs (see traversal_audit.gd for the arguments) and prints one line per
## blocked sweep and a summary: "TRAVERSAL <poi> <kind> ..." and "TRAVERSAL summary {...}".

var _ids: PackedStringArray = []
var _gen: int = 0
var _seed: int = -1


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < a.size():
		match a[i]:
			"--gen":
				i += 1
				_gen = int(a[i])
			"--seed":
				i += 1
				_seed = int(a[i])
			_:
				_ids.append(a[i])
		i += 1
	if _ids.is_empty():
		for d: PoiDef in Content.all(&"poi"):
			_ids.append(String(d.id))
	for t: Resource in Content.all(&"building_template"):
		for n: int in _gen:
			_ids.append("gen:%s:%d" % [str(t.get(&"id")), n + 1])
	var by_what: Dictionary = {}
	var pois: int = 0
	var bad: int = 0
	for id: String in _ids:
		var pd: PoiDef = _def(id)
		if pd == null:
			print("TRAVERSAL %s unknown" % id)
			continue
		var found: Array[Dictionary] = await audit_one(self, pd, id, _seed)
		pois += 1
		if not found.is_empty():
			bad += 1
		for f: Dictionary in found:
			print("TRAVERSAL " + TraversalAudit.line(id, f))
			var w: String = str(f["what"])
			by_what[w] = int(by_what.get(w, 0)) + 1
	print("TRAVERSAL summary %s" % JSON.stringify({"pois": pois, "with_findings": bad, "by_what": by_what}))
	get_tree().quit(0)


## Builds `pd` under `parent`, waits for its bodies to enter the physics space, audits it and frees
## it. `seed` >= 0 dresses it as a run with that world seed does.
static func audit_one(parent: Node3D, pd: PoiDef, id: String, seed: int = -1) -> Array[Dictionary]:
	if seed >= 0:
		var session: GameSession = GameSession.create_new({"seed": seed, "game_mode": "survival"})
		pd = PoiManager.dress_for(pd, StringName("audit/%s" % id), session)
	var v: PoiValidator = PoiValidator.validate(pd)
	var layout: PoiLayout = PoiLayout.compile(pd)
	var inst: PoiInstance = PoiBuilder.build(layout, StringName("audit/%s" % id))
	parent.add_child(inst)
	for f: int in 3:
		await parent.get_tree().physics_frame
	var found: Array[Dictionary] = TraversalAudit.audit(inst, v, parent.get_world_3d().direct_space_state)
	inst.queue_free()
	await parent.get_tree().process_frame
	return found


func _def(id: String) -> PoiDef:
	if id.begins_with("gen:"):
		var parts: PackedStringArray = id.split(":")
		var t: Resource = Content.get_def(&"building_template", StringName(parts[1]))
		if t == null:
			return null
		var gen: GDScript = load("res://src/poi/building_generator.gd")
		return gen.call(&"generate", t, int(parts[2])) as PoiDef
	return Content.get_def(&"poi", StringName(id)) as PoiDef
