class_name RouteCues
extends RefCounted
## Route cues on windows (ADR-0022): an entry window on a POI's route should read from the
## street. A window the validated route climbs in through gets the default cues (traps.json
## "route_cues".default); any opening can ask for its own with "cue" (a kind or a list, "none" for
## none):
##   * "curtain": a torn curtain hanging inside, dragged out over the sill and down the outside
##     wall (props/cue_curtain, _wide on 2 m windows); only in a window that is open, broken or
##     missing;
##   * "crate": a crate stood under it outside to climb on (two stacked when the sill is high),
##     solid, on the pad or the porch deck;
##   * "scuffs": muddy boot scuffs up the outside wall below it and a bloody handprint on the sill;
##   * "light": a propane lantern left burning on the inside sill (at most max_lights per building).
## Built into the PoiInstance when it enters the tree; deterministic per building and window. With
## the models not generated yet a cue is simply left out.

const KINDS: PackedStringArray = ["curtain", "crate", "scuffs", "light"]
const WALL_T: float = 0.16
## Def -> {opening id: [cue kinds]} (content is immutable; a POI placed twice plans once).
static var _plans: Dictionary = {}


static func cfg() -> Dictionary:
	return Content.config(&"traps").get("route_cues", {})


## Window opening types (glass, a sill to climb over).
static func is_window(t: String) -> bool:
	return t.begins_with("window") or t == "lancet"


## The authored "cue" of every opening that has one: opening id -> raw value.
static func authored(layout: PoiLayout) -> Dictionary:
	var out: Dictionary = {}
	for o: Variant in layout.def.layout.get("openings", []):
		if o is Dictionary and (o as Dictionary).has("cue"):
			out[str((o as Dictionary).get("id", ""))] = (o as Dictionary)["cue"]
	return out


## Validator messages: {"errors": [...], "warnings": [...]} for authored cues.
static func check(layout: PoiLayout) -> Dictionary:
	var errors: PackedStringArray = []
	var warnings: PackedStringArray = []
	var raw: Dictionary = authored(layout)
	for op_id: String in raw:
		var op: Dictionary = layout.opening(op_id)
		var kinds: Variant = _kinds(raw[op_id])
		if kinds == null:
			errors.append("opening '%s' cue must be one of %s, a list of them, or \"none\"" % [op_id, ", ".join(KINDS)])
			continue
		if op.is_empty():
			errors.append("a cue names opening '%s', which has no id or does not exist" % op_id)
			continue
		var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(int(op["level"]), op["axis"], op["edge"]), {})
		if not wall.is_empty() and not bool(wall["exterior"]):
			warnings.append("opening '%s' cue: cues read from the street; this is an interior wall" % op_id)
		if (kinds as PackedStringArray).has("curtain") and not (is_window(str(op["type"])) and str(op["state"]) in ["open", "broken", "missing"]):
			warnings.append("opening '%s' cue 'curtain' needs a window that is open, broken or missing (it hangs out over the sill)" % op_id)
	return {"errors": errors, "warnings": warnings}


## [kinds] for an authored cue value (null when malformed).
static func _kinds(v: Variant) -> Variant:
	var list: Array = v if v is Array else [v]
	var out: PackedStringArray = []
	for k: Variant in list:
		var s: String = str(k)
		if s == "none" and list.size() == 1:
			return out
		if not KINDS.has(s):
			return null
		out.append(s)
	return out


## Opening id -> [cue kinds] for every opening that gets cues.
static func plan(layout: PoiLayout) -> Dictionary:
	var key: int = layout.def.get_instance_id()
	if _plans.has(key):
		return _plans[key]
	var out: Dictionary = {}
	var raw: Dictionary = authored(layout)
	var default: PackedStringArray = PackedStringArray(cfg().get("default", ["curtain", "crate", "scuffs"]))
	for op_id: String in entry_windows(layout):
		out[op_id] = default
	for op_id: String in raw:
		var k: Variant = _kinds(raw[op_id])
		if k == null or layout.opening(op_id).is_empty():
			continue
		if (k as PackedStringArray).is_empty():
			out.erase(op_id)
		else:
			out[op_id] = k
	_plans[key] = out
	return out


## Window openings the route climbs in through from outside: opening id -> true. Walks the route
## legs that start outside the building with the validator's own graph (PoiValidator._bfs, without
## keys: nobody brings the key in from the street), not the whole validation, which costs seconds
## for the big buildings and this runs as each one is built at world load.
static func entry_windows(layout: PoiLayout) -> Dictionary:
	var v := PoiValidator.new()
	v.layout = layout
	var paths: Array = []
	var prev: Variant = "out"
	for wp: Dictionary in layout.route:
		var li: int = int(wp["level"])
		var c: Vector2i = wp["cell"]
		if not v._walkable(li, c):
			continue
		if prev is String or not layout.is_room(layout.room_at(int(prev[0]), prev[1])):
			var seen: Dictionary = v._bfs([prev], {})
			var k: String = PoiValidator.node_key(li, c)
			if seen.has(k):
				paths.append(v._reconstruct(seen, k))
		prev = [li, c]
	var out: Dictionary = {}
	for path: Array in paths:
		for i: int in range(1, path.size()):
			var a: Variant = path[i - 1]
			var b: Variant = path[i]
			if not (a is Array and b is Array) or int(a[0]) != int(b[0]):
				continue
			var li: int = int(a[0])
			var ca: Vector2i = a[1]
			var cb: Vector2i = b[1]
			if layout.is_room(layout.room_at(li, ca)) or not layout.is_room(layout.room_at(li, cb)):
				continue
			var side: int = PoiLayout.DIRS.find(cb - ca)
			if side < 0:
				continue
			var e: Array = PoiLayout.side_edge(ca, side)
			var op: Dictionary = (layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {}) as Dictionary).get("opening", {})
			if not op.is_empty() and is_window(str(op["type"])):
				out[str(op["id"])] = true
	return out


## Builds the planned cues into a built POI.
static func build(inst: PoiInstance) -> void:
	var layout: PoiLayout = inst.layout
	var cues: Dictionary = plan(layout)
	if cues.is_empty():
		return
	var pb := PoiBuilder.new()
	pb.layout = layout
	var porch: Dictionary = pb._porch_cell_set()
	var lights: int = 0
	var max_lights: int = int(cfg().get("max_lights", 1))
	var ids: Array = cues.keys()
	ids.sort()
	for op_id: String in ids:
		var op: Dictionary = layout.opening(op_id)
		var f: Dictionary = frame(layout, op)
		if f.is_empty():
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("cue:%s:%s" % [inst.instance_id, op_id])
		for kind: String in cues[op_id]:
			match kind:
				"curtain":
					_curtain(inst, op, f, rng)
				"crate":
					_crate(inst, layout, op, f, porch, rng)
				"scuffs":
					_scuffs(inst, op, f, rng)
				"light":
					if lights < max_lights and _light(inst, op, f):
						lights += 1


## A window's frame, POI-local: {centre (on the wall's centre plane at the storey's floor), out
## (unit, toward the street), along (unit), width (m of wall), sill / w / h (the opening), cell_out
## (the outside cell)}; {} for an interior wall.
static func frame(layout: PoiLayout, op: Dictionary) -> Dictionary:
	var li: int = int(op["level"])
	var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, op["axis"], op["edge"]), {})
	if wall.is_empty() or not bool(wall["exterior"]):
		return {}
	var e: Vector2i = op["edge"]
	var width: float = float(op["width"])
	var y: float = layout.level_y(li)
	var centre: Vector3
	var along: Vector3
	var a_out: Vector3
	if str(op["axis"]) == "h":
		centre = Vector3(layout.origin.x + e.x + width * 0.5, y, layout.origin.y + e.y)
		along = Vector3.RIGHT
		a_out = Vector3.BACK
	else:
		centre = Vector3(layout.origin.x + e.x, y, layout.origin.y + e.y + width * 0.5)
		along = Vector3.BACK
		a_out = Vector3.RIGHT
	# The "a" side (south / east of the edge) is the street when it is not a room.
	var out: Vector3 = a_out if not layout.is_room(str(wall["a"])) else -a_out
	var cells: Array[Vector2i] = _edge_cells(str(op["axis"]), e)
	var cell_out: Vector2i = cells[0] if not layout.is_room(str(wall["a"])) else cells[1]
	var spec: Dictionary = PoiParts.OPENINGS.get(str(op["type"]), PoiParts.OPENINGS["window"])
	return {"centre": centre, "out": out, "along": along, "width": width, "sill": float(spec.get("sill", 0.9)),
		"w": float(spec.get("w", 0.7)), "h": float(spec.get("h", 1.1)), "cell_out": cell_out, "level": li}


static func _edge_cells(axis: String, c: Vector2i) -> Array[Vector2i]:
	if axis == "h":
		return [c, Vector2i(c.x, c.y - 1)]
	return [c, Vector2i(c.x - 1, c.y)]


static func _yaw_of(dir: Vector3) -> float:
	return atan2(dir.x, dir.z)


static func _curtain(inst: PoiInstance, op: Dictionary, f: Dictionary, rng: RandomNumberGenerator) -> void:
	if not is_window(str(op["type"])) or not str(op["state"]) in ["open", "broken", "missing"]:
		return
	var model: String = "props/cue_curtain_wide" if float(f["width"]) > 1.5 else "props/cue_curtain"
	var decay: float = float(inst.layout.style.get("decay", 0.25 + 0.1 * inst.layout.def.tier))
	if rng.randf() < decay * 1.4 and ModelLibrary.has_model(model + "_worn"):
		model += "_worn"
	if not ModelLibrary.has_model(model):
		return
	var mi := MeshInstance3D.new()
	mi.name = "Cue_curtain_" + str(op["id"])
	mi.mesh = ModelLibrary.mesh(model)
	mi.transform = Transform3D(Basis(Vector3.UP, _yaw_of(f["out"])), f["centre"])
	inst.add_child(mi)


## A crate under the window outside (two when the sill is high above the ground), solid to climb.
static func _crate(inst: PoiInstance, layout: PoiLayout, op: Dictionary, f: Dictionary, porch: Dictionary,
		rng: RandomNumberGenerator) -> void:
	var li: int = int(f["level"])
	if li != 0 or layout.is_room(layout.room_at(0, f["cell_out"])):
		return
	var pid: String = str(cfg().get("crate", "crate_wood"))
	var pd: PropDef = Content.get_def(&"prop", StringName(pid)) as PropDef
	if pd == null:
		return
	var ground: float = layout.level_y(0) if porch.has(f["cell_out"]) else 0.0
	var top: float = layout.level_y(li) + float(f["sill"])
	var stack: int = 2 if top - ground > float(cfg().get("crate_high", 1.6)) else 1
	var out: Vector3 = f["out"]
	var pos: Vector3 = (f["centre"] as Vector3) + out * (WALL_T * 0.5 + pd.size.z * 0.5 + 0.04)
	pos.y = ground
	var model: String = pd.model_for("worn")
	for k: int in stack:
		var body := StaticBody3D.new()
		body.name = "Cue_crate_%s_%d" % [op["id"], k]
		body.collision_layer = 1
		body.collision_mask = 0
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(model, "box")
		body.add_child(mi)
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = pd.size
		cs.shape = box
		cs.position = Vector3(0, pd.size.y * 0.5, 0)
		body.add_child(cs)
		var yaw: float = _yaw_of(-out) + rng.randf_range(-0.2, 0.2) + (PI * 0.5 if k == 1 else 0.0)
		body.transform = Transform3D(Basis(Vector3.UP, yaw), pos + Vector3.UP * pd.size.y * float(k) + (f["along"] as Vector3) * rng.randf_range(-0.08, 0.08))
		inst.add_child(body)


## Boot scuffs up the street face below the sill and a handprint on the sill.
static func _scuffs(inst: PoiInstance, op: Dictionary, f: Dictionary, rng: RandomNumberGenerator) -> void:
	var c: Dictionary = cfg()
	var out: Vector3 = f["out"]
	var sill: float = float(f["sill"])
	var wall_dec: Decal = _decal(str(c.get("scuff_decal", "footprints_mud")))
	if wall_dec != null and sill > 0.3:
		# The band of siding a climber's boots scrape, from about knee height up to the sill.
		var h: float = 0.95
		wall_dec.size = Vector3(float(f["w"]) * 0.9, 0.12, h)
		var toward: Vector3 = -out
		wall_dec.position = (f["centre"] as Vector3) + Vector3.UP * (sill - h * 0.5) - toward * (WALL_T * 0.5)
		wall_dec.basis = Basis.looking_at(toward, Vector3.UP) * Basis(Vector3.RIGHT, PI * 0.5)
		wall_dec.name = "Cue_scuffs_" + str(op["id"])
		inst.add_child(wall_dec)
	var sill_dec: Decal = _decal(str(c.get("sill_decal", "blood_handprint")))
	if sill_dec != null:
		sill_dec.size = Vector3(0.28, 0.3, 0.22)
		sill_dec.position = (f["centre"] as Vector3) + Vector3.UP * (sill + 0.1) + (f["along"] as Vector3) * rng.randf_range(-0.15, 0.15)
		sill_dec.rotation.y = rng.randf_range(-0.5, 0.5) + _yaw_of(out)
		sill_dec.name = "Cue_sill_" + str(op["id"])
		inst.add_child(sill_dec)


static func _decal(id: String) -> Decal:
	var path: String = "res://assets/generated/textures/decal_%s_albedo.png" % id
	if not ResourceLoader.exists(path):
		return null
	var d := Decal.new()
	d.texture_albedo = load(path)
	var npath: String = path.replace("_albedo.png", "_normal.png")
	if ResourceLoader.exists(npath):
		d.texture_normal = load(npath)
	d.cull_mask = 1
	return d


## A lantern left burning on the inside sill: the window glows after dark. Lit the way a POI's
## "lit" props are (PropLights, ADR-0023), so it burns only if its worn variant can.
static func _light(inst: PoiInstance, op: Dictionary, f: Dictionary) -> bool:
	var pd: PropDef = Content.get_def(&"prop", StringName(str(cfg().get("light_prop", "lantern_camping")))) as PropDef
	if pd == null:
		return false
	var l: Dictionary = pd.light_for("worn")
	if l.is_empty():
		return false
	var out: Vector3 = f["out"]
	# On the room half of the window stool (it projects ~0.13 m from the wall's centre plane).
	var xf := Transform3D(Basis(Vector3.UP, _yaw_of(out)), (f["centre"] as Vector3) - out * 0.1 + Vector3.UP * float(f["sill"]))
	var mi: MeshInstance3D = PropLights.lit_mesh(pd.model_for("worn"), xf, true)
	mi.name = "Cue_light_" + str(op["id"])
	inst.add_child(mi)
	var light: Node3D = PropLights.light_node(l, xf)
	light.name = "Cue_lamp_" + str(op["id"])
	inst.add_child(light)
	return true
