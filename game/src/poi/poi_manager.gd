class_name PoiManager
extends Node3D
## Places frameworks and POIs from the composed regions' placements (region.json features ->
## RegionTerrain.placements), builds each building with PoiBuilder, spawns/despawns sleepers as
## you approach, tracks visits, and answers indoor / room queries for survival, audio and nav.
##
## Placement frames: a placement origin is the pad corner; its rotation (degrees) turns the
## framework/POI plane the same way the composer did (Vector2.rotated), i.e. node yaw = -angle.
## Inside a framework, a lot's POI is centred in its rect with its front (+Z) toward `facing`.
## Owns the poi.* commands (ADR-0003): poi.disarm_trap takes a POI trap apart for its parts.
## A building whose weak floor gives way gets its nav tiles rebaked (ADR-0022).

const SLEEPER_SPAWN: float = 46.0
const SLEEPER_DESPAWN: float = 95.0

var world: Node
var instances: Dictionary = {}
var _t: float = 0.0
var _inside: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	Game.register_command(&"poi.disarm_trap", _cmd_disarm_trap)
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
	for fi: int in fw.fixtures.size():
		var f: Dictionary = fw.fixtures[fi]
		var pdef: PropDef = Content.get_def(&"prop", StringName(str(f.get("prop", "")))) as PropDef
		if pdef == null:
			continue
		var p: Array = f.get("pos", [0, 0])
		var lp: Vector3 = fxf * Vector3(float(p[0]), 0.0, float(p[1]))
		lp.y = world.height_at(lp.x, lp.z)
		# Street fixtures with a container (dumpster, wrecks, mailbox) are searchable like any
		# prop indoors: same LootProp, tier 1, its id from the framework and the fixture's own id.
		var cdef: ContainerDef = Content.get_def(&"container", pdef.container) as ContainerDef if pdef.container != &"" else null
		var body: StaticBody3D
		if cdef != null:
			var lpr := PoiPieces.LootProp.new()
			lpr.prop = pdef
			lpr.cdef = cdef
			lpr.container_id = StringName("c:%s:%s" % [pl["id"], str(f.get("id", "fx%d" % fi))])
			lpr.tier = 1
			body = lpr
		else:
			body = StaticBody3D.new()
		body.name = "Fixture_%s_%d" % [pdef.id, fi]
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
	inst.geometry_changed.connect(_on_poi_geometry_changed)
	return inst


## A building's walkable geometry changed (a weak floor gave way, ADR-0022): rebake the nav tiles
## there so the Hollowed stop pathing over the hole.
func _on_poi_geometry_changed(pos: Vector3) -> void:
	var ai: Node = world.get(&"ai") if world != null else null
	var nav: NavTiles = ai.get(&"nav") as NavTiles if ai != null else null
	if nav != null:
		nav.mark_dirty(pos)


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
				var first: bool = not bool(inst.state.get("visited", false))
				if first:
					var p: PlayerState = Game.local_player()
					if p != null:
						p.progression.award("discover_poi", inst.tier)
				inst.state["visited"] = true
				Events.poi_entered.emit(id)
				if first:
					Events.poi_discovered.emit(id)
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


func _exit_tree() -> void:
	if world != null:
		Game.unregister_command(&"poi.disarm_trap")


## {player?, poi: instance id, trap: trap id} — a crouched player within reach takes an armed trap
## apart (or salvages a sprung one) and gets its parts (data/config/traps.json *_yield).
func _cmd_disarm_trap(args: Dictionary) -> Dictionary:
	if Game.session == null:
		return {"ok": false, "error": "no session"}
	var p: PlayerState = Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id))))
	if p == null or not p.stats.alive:
		return {"ok": false, "error": "no player"}
	var inst: PoiInstance = instances.get(StringName(str(args.get("poi", ""))))
	var tid: String = str(args.get("trap", ""))
	if inst == null or inst.layout.trap(tid).is_empty():
		return {"ok": false, "error": "no such trap"}
	var piece: Node3D = inst.traps.get(tid) as Node3D
	var node: Node3D = world.call(&"player_node", p.id) if world != null and world.has_method(&"player_node") else null
	if node != null and piece != null:
		if node.global_position.distance_to(piece.global_position) > float(Content.config(&"traps").get("disarm_reach", 3.0)):
			return {"ok": false, "error": "out of reach"}
		if inst.trap_state(tid) == "armed" and not bool(node.get(&"crouching")):
			return {"ok": false, "error": "not crouching"}
	var res: Dictionary = inst.disarm_trap(tid)
	if not bool(res.get("ok", false)):
		return res
	var items: Dictionary = res.get("items", {})
	var got: PackedStringArray = []
	for k: Variant in items.keys():
		var item := StringName(str(k))
		var n: int = int(items[k])
		var left: int = p.inventory.add_item(item, n)
		if left > 0 and piece != null:
			ItemDrop.spawn(world if world != null else self, ItemStack.make(item, left), piece.global_position + Vector3.UP * 0.4)
		var d: ItemDef = Content.item(item)
		got.append("%d %s" % [n, d.display_name if d != null else String(item)])
	Events.inventory_changed.emit(p.id)
	Events.trap_disarmed.emit(p.id, inst.instance_id, StringName(str(inst.layout.trap(tid).get("type", ""))), str(res.get("was", "")) == "armed")
	var what: String = str((piece as PoiPieces.Trap).label) if piece is PoiPieces.Trap else "trap"
	Events.player_status_message.emit(("%s %s" % ["Disarmed the" if str(res.get("was", "")) == "armed" else "Salvaged the", what]) +
		((": " + ", ".join(got) + ".") if not got.is_empty() else "."), &"info")
	return {"ok": true, "items": items}
