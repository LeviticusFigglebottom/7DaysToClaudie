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
## ADR-0030: every building is dressed for its run before it is built (dress_for: alternatives
## picked from the world seed and pinned in its saved state, per-run wear), and lots without an
## authored pick hold what LotPicker chooses: an authored building from the pool or a generated one.
## Its ProbeBudget keeps the buildings' interior reflection probes within the renderer's atlas.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Dressing := preload("res://src/poi/poi_dressing.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const ProbeBudget := preload("res://src/poi/interior_probe_budget.gd")

const SLEEPER_SPAWN: float = 46.0
const SLEEPER_DESPAWN: float = 95.0

var world: Node
var instances: Dictionary = {}
var _t: float = 0.0
var _inside: Dictionary = {}
## Shows only the interior probes nearest the camera (interior_probe_budget.gd).
var probes: Node


## While set (during setup_world in a GameWorld that is booting), _place_poi queues each building
## here instead of building it: GameWorld runs them as boot steps, a few per frame (ADR-0036). A
## 22-building town used to build in one frame of several seconds, and the OS called the game not
## responding.
var _queue: Array = []
var _queue_builds: Array = []
var _queueing: bool = false
## Route checks still running on worker threads (joined in _exit_tree).
var _tasks: Array[int] = []
## Every building placed in this world, built yet or not (all_buildings()): instance id -> entry.
var _placed: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	# Before any building enters the tree, so the probe cap holds from the first one built.
	probes = ProbeBudget.new()
	probes.name = "ProbeBudget"
	add_child(probes)
	Game.register_command(&"poi.disarm_trap", _cmd_disarm_trap)
	Settings.graphics_changed.connect(_on_graphics_changed)
	# Tools and tests that set up a bare world still get every building built here and now.
	_queueing = w.has_method(&"is_booting") and bool(w.call(&"is_booting"))
	_place_all(w)
	_queueing = false


## The buildings queued by setup_world as [label, Callable, name] boot steps (empties the queue):
## every building's plan first, then every build.
func boot_steps() -> Array:
	var out: Array = _queue + _queue_builds
	_queue = []
	_queue_builds = []
	return out


func _place_all(w: Node) -> void:
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
	var seed: int = Game.session.world_seed if Game.session != null else 0
	# The world loader may have resolved the lots (and generated their buildings) already.
	var cache: Dictionary = world.get(&"poi_lots") if world.get(&"poi_lots") is Dictionary else {}
	var resolved: Array = cache.get(str(pl["id"]), [])
	if resolved.is_empty():
		for r: Dictionary in Lots.resolve(fw, str(pl["id"]), seed):
			resolved.append([r, null if str(r["kind"]) in ["reserved", "empty"] else Lots.def_for(r)])
	for pair: Array in resolved:
		var res: Dictionary = pair[0]
		var l: Dictionary = res["lot"]
		if str(res["kind"]) in ["reserved", "empty"]:
			continue
		var pd: PoiDef = pair[1]
		if pd == null:
			Log.warn("poi", "lot %s: nothing to place (%s %s)" % [l.get("id"), res["kind"], res.get("def_id", res.get("template", ""))])
			continue
		var xf: Transform3D = fxf * lot_xf(l, pd.footprint)
		_place_poi(pd.id, StringName(str(res["instance"])), xf, Vector2(pd.footprint), pd)
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


## A lot's POI frame in its framework: the footprint centred in the rect, its front (+Z) toward
## the lot's `facing`.
static func lot_xf(l: Dictionary, footprint: Vector2i) -> Transform3D:
	var rect: Array = l["rect"]
	var center := Vector3(float(rect[0]) + float(rect[2]) * 0.5, 0.0, float(rect[1]) + float(rect[3]) * 0.5)
	var yaw: float = {"S": 0.0, "E": PI * 0.5, "N": PI, "W": -PI * 0.5}.get(str(l.get("facing", "S")), 0.0)
	var b := Basis(Vector3.UP, yaw)
	return Transform3D(b, center - b * Vector3(footprint.x * 0.5, 0.0, footprint.y * 0.5))


## The def as this run builds it at this placement (ADR-0030): per-run picks and wear for a world
## dressed per run, the authored defaults and the old scatter for a legacy save. A run keeps the
## picks it made the first time (pinned in the POI's saved state), even if content gains options.
static func dress_for(pd: PoiDef, instance_id: StringName, session: GameSession) -> PoiDef:
	var mode: int = Dressing.MODE_LEGACY
	var world_seed: int = 0
	var st: Dictionary = {}
	if session != null:
		mode = session.world.poi_dressing
		world_seed = session.world_seed
		st = session.world.poi_state(instance_id)
	var seed: int = Dressing.dressing_seed(world_seed, instance_id, mode)
	var picks: Dictionary = {}
	if mode == Dressing.MODE_PER_RUN and Dressing.has_alternatives(pd):
		picks = Dressing.roll(pd, seed)
		var pinned: Dictionary = st.get("picks", {})
		for g: Dictionary in Dressing.groups(pd):
			var gid: String = str(g.get("id", ""))
			if pinned.has(gid) and Dressing.option_ids(g).has(str(pinned[gid])):
				picks[gid] = str(pinned[gid])
		if session != null:
			st["picks"] = picks.duplicate()
	return Dressing.resolve(pd, picks, {"mode": mode, "seed": seed})


func _place_poi(def_id: StringName, instance_id: StringName, xf: Transform3D, _pad: Vector2, def: PoiDef = null) -> PoiInstance:
	var pd: PoiDef = def if def != null else Content.get_def(&"poi", def_id) as PoiDef
	if pd == null:
		Log.warn("poi", "poi %s not found" % def_id)
		return null
	_placed[instance_id] = {"id": instance_id, "def": pd.id, "name": pd.display_name, "tier": pd.tier,
		"kind": "generated" if pd.template != &"" else "authored", "pos": xf * Vector3(pd.footprint.x * 0.5, 0.0, pd.footprint.y * 0.5)}
	if _queueing:
		# Two steps a building: compile it (and start its route check on a worker thread), then,
		# once every compile has started its check, build it as soon as its check is done.
		var job: Dictionary = {"pd": pd, "id": instance_id, "xf": xf}
		var label: String = "Raising %s…" % pd.display_name if pd.display_name != "" else "Raising the town…"
		_queue.append(["Surveying the town…", _prepare_poi.bind(job), "poi plan %s" % instance_id])
		_queue_builds.append([label, _finish_poi.bind(job), "poi %s" % instance_id])
		return null
	return _build_poi(pd, instance_id, xf)


## Boot step: compiles a queued building's layout (main thread: the per-run picks are pinned in
## the session) and starts its PoiValidator on a worker thread.
func _prepare_poi(job: Dictionary) -> void:
	var layout := PoiLayout.compile(dress_for(job["pd"], job["id"], Game.session))
	for e: String in layout.errors:
		Log.warn("poi", e)
	var v := PoiValidator.new()
	v.layout = layout
	job["layout"] = layout
	job["checked"] = v
	job["task"] = WorkerThreadPool.add_task(v._run, false, "poi check %s" % job["id"])
	_tasks.append(job["task"])


## Boot step: builds a prepared building once its check is done (false = not yet, ask again).
func _finish_poi(job: Dictionary) -> bool:
	var task: int = int(job.get("task", -1))
	if task >= 0:
		if not WorkerThreadPool.is_task_completed(task):
			return false
		WorkerThreadPool.wait_for_task_completion(task)
		_tasks.erase(task)
		job.erase("task")
	_build_poi(job["pd"], job["id"], job["xf"], job.get("layout"), job.get("checked"))
	return true


func _build_poi(pd: PoiDef, instance_id: StringName, xf: Transform3D, layout: PoiLayout = null, checked: PoiValidator = null) -> PoiInstance:
	if layout == null:
		layout = PoiLayout.compile(dress_for(pd, instance_id, Game.session))
		for e: String in layout.errors:
			Log.warn("poi", e)
	var inst: PoiInstance = PoiBuilder.build(layout, instance_id, checked)
	add_child(inst)
	inst.global_transform = xf
	instances[instance_id] = inst
	_limit_draw_distance(inst)
	inst.geometry_changed.connect(_on_poi_geometry_changed)
	return inst


## Draw distances for a building's props, doors, pieces and prop batches (the kit batches keep the
## building's shape at any range). They had none: every prop of every building in the valley was
## drawn, shadow passes included, about 2.4 M triangles in 2,400 instances from any view (TD-003,
## ADR-0037). Small things stop at the graphics setting object_distance, door-sized ones at 2.5x,
## anything over 8 m (a steeple, a silo) is never cut.
func _limit_draw_distance(root: Node) -> void:
	var near: float = float(Settings.gfx("object_distance", 140.0))
	for n: Node in root.find_children("*", "GeometryInstance3D", true, false):
		var mi: GeometryInstance3D = n
		var mesh: Mesh = null
		if mi is MeshInstance3D:
			mesh = (mi as MeshInstance3D).mesh
		elif mi is MultiMeshInstance3D and _is_model_batch(mi as MultiMeshInstance3D):
			mesh = (mi as MultiMeshInstance3D).multimesh.mesh
		if mesh == null:
			continue
		if not mi.has_meta(&"hm_extent"):
			var b: Basis = mi.global_transform.basis
			mi.set_meta(&"hm_extent", (mesh.get_aabb().size * b.get_scale()).length())
		var extent: float = float(mi.get_meta(&"hm_extent"))
		var end: float = 0.0 if extent > 8.0 else (near * 2.5 if extent > 2.5 else near)
		mi.visibility_range_end = end
		# Hysteresis, no fade: a dithered fade would make every prop draw as transparency.
		mi.visibility_range_end_margin = 0.0 if end == 0.0 else end * 0.08
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED


## PoiBuilder batches props and other models ("@family/id" pieces, named MM_<family>_...) beside
## the kit pieces (walls, floors, roofs: the building's shape, never cut).
const MODEL_FAMILIES: PackedStringArray = ["props", "items", "trees", "plants", "rocks", "structures", "animals", "characters"]


static func _is_model_batch(mmi: MultiMeshInstance3D) -> bool:
	if mmi.multimesh == null or mmi.multimesh.mesh == null:
		return false
	var n: String = String(mmi.name)
	for f: String in MODEL_FAMILIES:
		if n.begins_with("MM_%s_" % f):
			return true
	return false


func _on_graphics_changed() -> void:
	for inst: Node in instances.values():
		if is_instance_valid(inst):
			_limit_draw_distance(inst)


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

## Every building this world places, whether built yet or not: {id: instance id, def: def id,
## name, tier, kind: "authored" | "generated", pos: its centre}. The one lookup for "what buildings
## does this world have" (the directives use it): when buildings stream by distance, `instances`
## holds only the nearby ones, so this switches to the PoiRegistry of every placement
## (docs/RWG_V2_PLAN.md §1.7) instead.
func all_buildings() -> Array:
	return _placed.values()


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
	for t: int in _tasks:
		WorkerThreadPool.wait_for_task_completion(t)
	_tasks.clear()
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
