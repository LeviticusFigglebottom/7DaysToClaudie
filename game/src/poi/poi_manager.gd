class_name PoiManager
extends Node3D
## Places frameworks and POIs from the composed regions' placements (region.json features ->
## RegionTerrain.placements), builds each building with PoiBuilder, spawns/despawns sleepers as
## you approach, tracks visits, and answers indoor / room queries for survival, audio and nav.
##
## Placement frames: a placement origin is the pad corner; its rotation (degrees) turns the
## framework/POI plane the same way the composer did (Vector2.rotated), i.e. node yaw = -angle.
## Inside a framework, a lot's POI is centred in its rect with its front (+Z) toward `facing`.

const SLEEPER_SPAWN: float = 46.0
const SLEEPER_DESPAWN: float = 95.0

var world: Node
var instances: Dictionary = {}
var _t: float = 0.0
var _inside: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	for rid: String in (w.terrain as TerrainManager).regions:
		var rt: RegionTerrain = w.terrain.regions[rid]
		for pl: Dictionary in rt.placements:
			match str(pl.get("kind", "")):
				"framework":
					_place_framework(pl)
				"poi":
					_place_poi(StringName(str(pl["def"])), StringName(str(pl["id"])), _placement_xf(pl), Vector2(pl.get("size", [0, 0])[0], pl.get("size", [0, 0])[1]))


static func _placement_xf(pl: Dictionary) -> Transform3D:
	var o: Array = pl["origin"]
	return Transform3D(Basis(Vector3.UP, -deg_to_rad(float(pl.get("rotation", 0.0)))), Vector3(float(o[0]), float(o[1]), float(o[2])))


func _place_framework(pl: Dictionary) -> void:
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(pl["def"]))) as FrameworkDef
	if fw == null:
		Log.warn("poi", "framework %s not found" % pl["def"])
		return
	var fxf: Transform3D = _placement_xf(pl)
	for lot: Variant in fw.lots:
		var l: Dictionary = lot
		var pick: String = str(l.get("pick", ""))
		if pick == "":
			continue
		var rect: Array = l["rect"]
		var center := Vector3(float(rect[0]) + float(rect[2]) * 0.5, 0.0, float(rect[1]) + float(rect[3]) * 0.5)
		var yaw: float = {"S": 0.0, "E": PI * 0.5, "N": PI, "W": -PI * 0.5}.get(str(l.get("facing", "S")), 0.0)
		var pd: PoiDef = Content.get_def(&"poi", StringName(pick)) as PoiDef
		if pd == null:
			Log.warn("poi", "lot %s picks unknown poi %s" % [l.get("id"), pick])
			continue
		var b := Basis(Vector3.UP, yaw)
		var local_origin: Vector3 = center - b * Vector3(pd.footprint.x * 0.5, 0.0, pd.footprint.y * 0.5)
		var xf: Transform3D = fxf * Transform3D(b, local_origin)
		_place_poi(StringName(pick), StringName("%s/%s" % [pl["id"], l["id"]]), xf, Vector2(pd.footprint))
	for fx: Variant in fw.fixtures:
		var f: Dictionary = fx
		var pdef: PropDef = Content.get_def(&"prop", StringName(str(f.get("prop", "")))) as PropDef
		if pdef == null:
			continue
		var p: Array = f.get("pos", [0, 0])
		var lp: Vector3 = fxf * Vector3(float(p[0]), 0.0, float(p[1]))
		lp.y = world.height_at(lp.x, lp.z)
		var body := StaticBody3D.new()
		body.name = "Fixture_%s" % pdef.id
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(pdef.model_for(str(f.get("variant", "worn"))), "box")
		body.add_child(mi)
		if pdef.collision != "none":
			var cs := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = pdef.size
			cs.shape = box
			cs.position = Vector3(0, pdef.size.y * 0.5, 0)
			body.add_child(cs)
		add_child(body)
		body.global_transform = Transform3D(fxf.basis * Basis(Vector3.UP, deg_to_rad(float(f.get("rot", 0.0)))), lp)


func _place_poi(def_id: StringName, instance_id: StringName, xf: Transform3D, _pad: Vector2) -> PoiInstance:
	var pd: PoiDef = Content.get_def(&"poi", def_id) as PoiDef
	if pd == null:
		Log.warn("poi", "poi %s not found" % def_id)
		return null
	var layout := PoiLayout.compile(pd)
	for e: String in layout.errors:
		Log.warn("poi", e)
	var inst: PoiInstance = PoiBuilder.build(layout, instance_id)
	add_child(inst)
	inst.global_transform = xf
	instances[instance_id] = inst
	return inst


func _process(delta: float) -> void:
	_t += delta
	if _t < 1.0 or world == null or world.player == null or not world.is_ready:
		return
	_t = 0.0
	var ppos: Vector3 = world.player.global_position
	var ai: Node = world.get(&"ai")
	for id: StringName in instances:
		var inst: PoiInstance = instances[id]
		var b: AABB = inst.world_bounds()
		var d: float = b.get_center().distance_to(ppos) - b.size.length() * 0.4
		if d < SLEEPER_SPAWN and not inst.sleepers_spawned:
			inst.spawn_sleepers(ai)
		elif d > SLEEPER_DESPAWN and inst.sleepers_spawned:
			inst.despawn_sleepers(ai)
		var inside: bool = b.has_point(ppos)
		if inside != bool(_inside.get(id, false)):
			_inside[id] = inside
			if inside:
				if not bool(inst.state.get("visited", false)):
					var p: PlayerState = Game.local_player()
					if p != null:
						p.progression.award("discover_poi", inst.tier)
				inst.state["visited"] = true
				Events.poi_entered.emit(id)
			else:
				Events.poi_exited.emit(id)


# --- Queries ---------------------------------------------------------------------------------

func poi_at(pos: Vector3) -> PoiInstance:
	for inst: PoiInstance in instances.values():
		if inst.world_bounds().has_point(pos):
			return inst
	return null


func is_indoors(pos: Vector3) -> bool:
	var inst: PoiInstance = poi_at(pos)
	return inst != null and inst.is_indoors(pos)


func room_type_at(pos: Vector3) -> String:
	var inst: PoiInstance = poi_at(pos)
	return inst.room_type_at(pos) if inst != null else ""


## Static collision roots of POIs overlapping an XZ rect (navigation baking).
func nav_roots_in_rect(r: Rect2) -> Array:
	var out: Array = []
	for inst: PoiInstance in instances.values():
		var b: AABB = inst.world_bounds()
		if Rect2(b.position.x, b.position.z, b.size.x, b.size.z).intersects(r):
			out.append(inst.shell)
	return out


func save_into(_session: GameSession) -> void:
	# POI state dictionaries live in WorldState.pois already (mutated in place).
	pass
