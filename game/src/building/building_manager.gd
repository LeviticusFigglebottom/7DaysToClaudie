class_name BuildingManager
extends Node3D
## Player building (ADR-0006): blueprint ghosts from the field manual, freeform log placement with
## snapping (LogSnapper), structural support (StructureGraph), damage, collapse into falling logs
## and debris, hammer repair/upgrade, and persistence (WorldState.structures / .blueprints).
##
## Authoritative operations are commands on the Game bus (ADR-0003); input and previews only
## call Game.execute():
##   build.place_blueprint {player, blueprint, pos:[3], yaw}     -> {ok, site}
##   build.deliver         {player, site}                        -> {ok, complete}
##   build.place_log       {player, site?, slot? | pos:[3], rot:[4]} -> {ok, piece}
##   build.repair / build.upgrade {player, piece}
##   build.demolish        {player, site}                        -> {ok, refund} (take a placed ghost down: hold cancel on it)
##   build.dismantle       {player, piece}                       (take a piece down for part of its cost)
##   build.add_fuel        {player, piece, item?}                -> {ok, fuel}
##   build.light           {player, piece}                       (needs fuel and a lighter or torch)
##   build.place_item      {player, item, pos:[3], yaw}          (a placeable item: the can chime)
##   build.rack_store      {player, piece, count?}               -> {ok, stored} (ADR-0035 racks)
##   build.rack_take       {player, piece, count?}               -> {ok, taken}
##   build.toggle_door     {player, piece}                       -> {ok, open}

const LOG_DEF: StringName = &"log_piece"
const CELL: float = 4.0
const REACH: float = 6.0
const MAX_PLACE_DIST: float = 7.5
const GROUND_TOLERANCE: float = 0.22
## Log orientation presets cycled with build_mode_toggle: flat, upright post, roof pitch.
const LOG_POSES: Array[String] = ["flat", "post", "pitched"]

var world: Node
var graph := StructureGraph.new()
var pieces: Dictionary = {}
var sites: Dictionary = {}
var preview: BuildPreview
var placing: BlueprintDef = null
var _place_yaw: float = 0.0
var _log_yaw: float = 0.0
var _log_pose: int = 0
var _log_target: Dictionary = {}
var _bp_target: Dictionary = {}
var _cells: Dictionary = {}

const COMMANDS: Array[StringName] = [&"build.place_blueprint", &"build.deliver", &"build.place_log", &"build.repair",
	&"build.upgrade", &"build.demolish", &"build.dismantle", &"build.add_fuel", &"build.light", &"build.place_item",
	&"build.rack_store", &"build.rack_take", &"build.toggle_door"]
## What a fire is fed with, in order, when the player doesn't hold a fuel item: kindling first,
## logs last (they are walls too). Cloth only burns when held: it is bandages.
const FUEL_ORDER: Array[StringName] = [&"stick", &"leaf_bundle", &"wood_plank", &"log"]
## Pieces that burn fuel (id -> StructurePiece), so the burn tick doesn't walk every wall.
var _fires: Dictionary = {}
## A full-health piece struck once with a hammer is armed for reinforcing; a second strike on the
## same piece within UPGRADE_CONFIRM seconds spends the materials (no accidental upgrades).
const UPGRADE_CONFIRM: float = 3.0
var _upgrade_armed: StringName = &""
var _upgrade_armed_at: float = -100.0


func setup_world(w: Node) -> void:
	world = w
	preview = BuildPreview.new()
	preview.name = "Preview"
	add_child(preview)
	Game.register_command(&"build.place_blueprint", _cmd_place_blueprint)
	Game.register_command(&"build.deliver", _cmd_deliver)
	Game.register_command(&"build.place_log", _cmd_place_log)
	Game.register_command(&"build.repair", _cmd_repair)
	Game.register_command(&"build.upgrade", _cmd_upgrade)
	Game.register_command(&"build.demolish", _cmd_demolish)
	Game.register_command(&"build.dismantle", _cmd_dismantle)
	Game.register_command(&"build.add_fuel", _cmd_add_fuel)
	Game.register_command(&"build.light", _cmd_light)
	Game.register_command(&"build.place_item", _cmd_place_item)
	Game.register_command(&"build.rack_store", _cmd_rack_store)
	Game.register_command(&"build.rack_take", _cmd_rack_take)
	Game.register_command(&"build.toggle_door", _cmd_toggle_door)
	Events.terrain_modified.connect(_on_terrain_modified)
	if w.get(&"clock_driver") != null:
		w.clock_driver.game_minutes_passed.connect(_burn_fires)
	_restore(Game.session.world)


func _exit_tree() -> void:
	for c: StringName in COMMANDS:
		Game.unregister_command(c)


# --- Queries -----------------------------------------------------------------------------------

static func cell_of(p: Vector3) -> Vector2i:
	return Vector2i(int(floor(p.x / CELL)), int(floor(p.z / CELL)))


func pieces_in_radius(pos: Vector3, r: float) -> Array[StructurePiece]:
	var out: Array[StructurePiece] = []
	var c0: Vector2i = cell_of(pos - Vector3(r, 0, r))
	var c1: Vector2i = cell_of(pos + Vector3(r, 0, r))
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			for id: StringName in _cells.get(Vector2i(cx, cz), []):
				var p: StructurePiece = pieces.get(id)
				if p != null and p.global_position.distance_to(pos) <= r + 2.5:
					out.append(p)
	return out


func stations_near(pos: Vector3, r: float = 3.0) -> PackedStringArray:
	var out: PackedStringArray = []
	for p: StructurePiece in pieces_in_radius(pos, r):
		var s: StringName = p.station_id()
		if s != &"" and p.global_position.distance_to(pos) <= r and not out.has(String(s)):
			if p.provides("light") and not p.lit:
				continue
			out.append(String(s))
	return out


## Extra warmth (°C) from lit fires at a position.
func warmth_at(pos: Vector3) -> float:
	var w: float = 0.0
	for p: StructurePiece in pieces_in_radius(pos, 6.0):
		w += p.warmth_at(pos)
	return w


## Roof overhead (any structure within 6 m straight up).
func is_sheltered(pos: Vector3) -> bool:
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 1.0, pos + Vector3.UP * 7.0, StructurePiece.LAYER)
	return not space.intersect_ray(q).is_empty()


func stability_of(id: StringName) -> float:
	return graph.stability(id)


# --- Input & previews --------------------------------------------------------------------------

func is_placing() -> bool:
	return placing != null


func begin_placement(bp_id: StringName) -> bool:
	var bp: BlueprintDef = Content.get_def(&"blueprint", bp_id) as BlueprintDef
	var p: PlayerState = Game.local_player()
	if bp == null or p == null:
		return false
	if not p.progression.knows_blueprint(bp):
		Events.player_status_message.emit("You haven't learned how to build that.", &"warning")
		return false
	placing = bp
	_place_yaw = 0.0
	preview.show_blueprint(bp)
	return true


func cancel_placement() -> void:
	placing = null
	preview.hide_preview()


## Attack button hook (PlayerEquipment.primary): returns true if building consumed the press.
func handle_primary(player: Player) -> bool:
	if placing != null:
		if _bp_target.get("ok", false):
			var xf: Transform3D = _bp_target["xform"]
			var res: Dictionary = Game.execute(&"build.place_blueprint", {"player": player.state.id, "blueprint": String(placing.id),
				"pos": [xf.origin.x, xf.origin.y, xf.origin.z], "yaw": xf.basis.get_euler().y})
			if bool(res.get("ok", false)):
				cancel_placement()
		else:
			Audio.play_2d(&"ui/error", -8.0)
		return true
	return try_place_carried(player)


## Places a carried log into the targeted ghost slot, or freeform at the preview.
func try_place_carried(player: Player) -> bool:
	if player.state.inventory.count_of(&"log") <= 0:
		return false
	var slot: Dictionary = _aimed_slot(player)
	if not slot.is_empty():
		Game.execute(&"build.place_log", {"player": player.state.id, "site": String(slot["site"]), "slot": int(slot["slot"])})
		return true
	if _log_target.get("ok", false):
		var xf: Transform3D = _log_target["xform"]
		var q: Quaternion = xf.basis.get_rotation_quaternion()
		Game.execute(&"build.place_log", {"player": player.state.id, "pos": [xf.origin.x, xf.origin.y, xf.origin.z], "rot": [q.x, q.y, q.z, q.w]})
	else:
		Audio.play_2d(&"ui/error", -10.0)
	return true


func _aimed_slot(player: Player) -> Dictionary:
	var inter: PlayerInteraction = player.get_node_or_null(^"Interaction") as PlayerInteraction
	if inter != null and inter.target is BlueprintSite.GhostSlot:
		var gs: BlueprintSite.GhostSlot = inter.target
		return {"site": gs.site.site_id, "slot": gs.index}
	# Near-miss: the ghost slot nearest the freeform aim point.
	if _log_target.has("xform"):
		var pos: Vector3 = (_log_target["xform"] as Transform3D).origin
		for s: BlueprintSite in sites.values():
			if s.bp.mode == "pieces" and s.global_position.distance_to(pos) < 8.0:
				var i: int = s.nearest_open_slot(pos, 0.6)
				if i >= 0:
					return {"site": s.site_id, "slot": i}
	return {}


## Drops a carried log in front of the player; `nth` stacks several dropped at once upward.
func drop_log(p: PlayerState, nth: int = 0) -> void:
	var node: Player = world.player_node(p.id) if world != null else null
	if node == null or world.get(&"loose") == null:
		return
	var fwd: Vector3 = -node.global_transform.basis.z
	var pos: Vector3 = node.global_position + Vector3.UP * (1.3 + 0.55 * nth) + fwd * 1.0
	var yaw: float = node.global_rotation.y + PI * 0.5
	var l: LogEntity = world.loose.spawn_log(pos, Basis(Vector3.UP, yaw))
	l.linear_velocity = fwd * 1.5
	Audio.play_3d(&"sfx/log_drop", pos, {"volume_db": -2.0})


func _physics_process(_delta: float) -> void:
	var player: Player = world.player if world != null else null
	if player == null or player.state == null or not player.input_enabled:
		preview.hide_preview()
		return
	var captured: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	# [G] while looking at a fire feeds it (before G drops a carried log).
	if captured and placing == null and Input.is_action_just_pressed(&"drop"):
		var focus: StructurePiece = player.interaction.target as StructurePiece if player.interaction != null else null
		if focus != null and focus.burns_fuel():
			Game.execute(&"build.add_fuel", {"player": player.state.id, "piece": String(focus.piece_id)})
			return
	if placing != null:
		if captured and Input.is_action_just_pressed(&"rotate_piece"):
			_place_yaw += deg_to_rad(15.0)
		if captured and (Input.is_action_just_pressed(&"cancel") or Input.is_action_just_pressed(&"block")):
			cancel_placement()
			return
		_update_blueprint_target(player)
		return
	if player.state.inventory.count_of(&"log") > 0 and captured:
		if Input.is_action_just_pressed(&"drop"):
			Game.execute(&"inventory.drop", {"player": player.state.id, "item": "log", "count": 1})
			return
		if Input.is_action_just_pressed(&"rotate_piece"):
			_log_yaw += PI * 0.5
		if Input.is_action_just_pressed(&"build_mode_toggle"):
			_log_pose = (_log_pose + 1) % LOG_POSES.size()
			Events.player_status_message.emit("Log: %s" % LOG_POSES[_log_pose], &"info")
		_update_log_target(player)
	else:
		_log_target = {}
		if preview.mode == &"log":
			preview.hide_preview()


func _aim(player: Player, reach: float, mask: int) -> Dictionary:
	var cam: Camera3D = player.camera
	var from: Vector3 = cam.global_position
	var dir: Vector3 = -cam.global_transform.basis.z
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * reach, mask)
	q.exclude = [player.get_rid()]
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	return {"from": from, "dir": dir, "hit": hit}


func _update_blueprint_target(player: Player) -> void:
	var a: Dictionary = _aim(player, REACH * 1.6, 1 | (StructurePiece.LAYER if placing.on_structures else 0))
	var hit: Dictionary = a["hit"]
	var pos: Vector3
	if hit.is_empty():
		pos = (a["from"] as Vector3) + (a["dir"] as Vector3) * REACH * 1.6
	else:
		pos = hit["position"]
	# On a log floor (ADR-0035): stand on the logs where the aim lands; elsewhere on the ground.
	var floor_y: float = _structure_floor(placing, pos)
	pos.y = floor_y if floor_y > -INF else _footprint_height(placing, pos)
	var yaw: float = player.global_rotation.y + _place_yaw
	var xf := Transform3D(Basis(Vector3.UP, yaw), pos)
	var why: String = _blueprint_blocker(placing, xf)
	_bp_target = {"ok": why == "", "xform": xf, "why": why}
	preview.global_transform = xf
	preview.show_blueprint(placing)
	preview.set_state(why == "")


## The top of the log floor or platform under `pos` (a ray down from just above it onto horizontal
## logs), or -INF: not an on_structures blueprint, or no logs there.
func _structure_floor(bp: BlueprintDef, pos: Vector3) -> float:
	var under: StructurePiece = support_under(pos) if bp != null and bp.on_structures and is_inside_tree() else null
	if under == null:
		return -INF
	return under.global_position.y + LogSnapper.RADIUS


## The horizontal log a thing standing at `pos` rests on (within half a metre below or above).
func support_under(pos: Vector3) -> StructurePiece:
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.5, pos + Vector3.DOWN * 0.6, StructurePiece.LAYER)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	var piece := hit.get("collider") as StructurePiece if not hit.is_empty() else null
	if piece == null or not piece.is_log() or LogSnapper.is_vertical(piece.global_transform.basis):
		return null
	return piece


func _footprint_radius(bp: BlueprintDef) -> float:
	if bp.mode == "assembly":
		var s: StructureDef = Content.structure(bp.result)
		return 0.5 * Vector2(s.size.x, s.size.z).length() if s != null else 1.0
	var r: float = 0.0
	for p: Dictionary in bp.pieces:
		r = maxf(r, Vector2((p["pos"] as Vector3).x, (p["pos"] as Vector3).z).length() + 0.5)
	return r


## Pieces blueprints sit at the lowest terrain point under them; assemblies at their centre.
func _footprint_height(bp: BlueprintDef, pos: Vector3) -> float:
	var h: float = world.height_at(pos.x, pos.z)
	if bp.mode == "assembly":
		return h
	var r: float = _footprint_radius(bp) * 0.7
	for o: Vector2 in [Vector2(r, r), Vector2(-r, r), Vector2(r, -r), Vector2(-r, -r)]:
		h = minf(h, world.height_at(pos.x + o.x, pos.z + o.y))
	return h


func _blueprint_blocker(bp: BlueprintDef, xf: Transform3D) -> String:
	var pos: Vector3 = xf.origin
	var p: Player = world.player
	if p.global_position.distance_to(pos) > REACH * 1.8:
		return "too far"
	var on_floor: StructurePiece = support_under(pos) if bp.on_structures and is_inside_tree() else null
	var n: Vector3 = (world.terrain as TerrainManager).normal_at(pos.x, pos.z)
	if on_floor == null and rad_to_deg(n.angle_to(Vector3.UP)) > bp.max_slope:
		return "too steep"
	var wsys: Node = world.get(&"water")
	if wsys != null and wsys.has_method(&"depth_at") and float(wsys.call(&"depth_at", pos)) > 0.25:
		return "in water"
	var r: float = _footprint_radius(bp)
	for other: StructurePiece in pieces_in_radius(pos, r):
		var flat: float = Vector2(other.global_position.x - pos.x, other.global_position.z - pos.z).length()
		# The floor logs it stands on are not in its way.
		if on_floor != null and other.is_log() and other.global_position.y < pos.y - 0.05:
			continue
		if flat < r * 0.6 and absf(other.global_position.y - pos.y) < 2.5:
			return "blocked"
	for s: BlueprintSite in sites.values():
		if s.global_position.distance_to(pos) < (r + _footprint_radius(s.bp)) * 0.6:
			return "blocked"
	var pois: Node = world.get(&"pois")
	if pois != null and pois.call(&"poi_at", pos + Vector3.UP) != null:
		return "inside a building"
	var half: Vector2 = _footprint_half(bp)
	var flat_p := Vector2(p.global_position.x - pos.x, p.global_position.z - pos.z).rotated(xf.basis.get_euler().y)
	if absf(flat_p.x) < half.x + 0.3 and absf(flat_p.y) < half.y + 0.3 and absf(p.global_position.y - pos.y) < 2.0:
		return "you are standing in the way"
	return _footprint_obstacle(xf, half)


## Half extents (x, z) of a blueprint's footprint in its own frame.
func _footprint_half(bp: BlueprintDef) -> Vector2:
	if bp.mode == "assembly":
		var sd: StructureDef = Content.structure(bp.result)
		return Vector2(sd.size.x, sd.size.z) * 0.5 if sd != null else Vector2(0.5, 0.5)
	var h := Vector2(0.5, 0.5)
	for pc: Dictionary in bp.pieces:
		var at: Vector3 = pc["pos"]
		h = Vector2(maxf(h.x, absf(at.x) + 0.3), maxf(h.y, absf(at.z) + 0.3))
	return h


## Trees, rocks and deadfall inside a footprint (vegetation has its own physics layer; the
## terrain is left out so a slope never blocks).
func _footprint_obstacle(xf: Transform3D, half: Vector2) -> String:
	var box := BoxShape3D.new()
	box.size = Vector3(half.x * 2.0 - 0.2, 1.6, half.y * 2.0 - 0.2)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = box
	q.transform = Transform3D(xf.basis, xf.origin + Vector3.UP * 1.2)
	q.collision_mask = 1 << 12
	if not get_world_3d().direct_space_state.intersect_shape(q, 1).is_empty():
		return "a tree or rock is in the way"
	return ""


## Why the current preview can't be placed, for the HUD ("" when it can or nothing is shown).
func placement_hint() -> String:
	var t: Dictionary = _bp_target if placing != null else _log_target
	if t.is_empty() or bool(t.get("ok", true)):
		return ""
	return "Can't place: %s" % str(t.get("why", ""))


## Sets down a carried placeable item (a can chime) where the player aims, across their line of
## sight. The command spends the item and saves the piece like any other structure.
func place_item_structure(player: Player, item_id: StringName) -> void:
	var a: Dictionary = _aim(player, REACH, 1 | StructurePiece.LAYER)
	var hit: Dictionary = a["hit"]
	if hit.is_empty():
		Events.player_status_message.emit("Aim at the ground to set it down.", &"warning")
		return
	var pos: Vector3 = hit["position"]
	var res: Dictionary = Game.execute(&"build.place_item", {"player": player.state.id, "item": String(item_id),
		"pos": [pos.x, pos.y, pos.z], "yaw": player.global_rotation.y})
	if not bool(res.get("ok", false)):
		Events.player_status_message.emit("Can't set it here: %s." % str(res.get("error", "blocked")), &"warning")


func _cmd_place_item(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var item := StringName(str(args.get("item", "")))
	var idef: ItemDef = Content.item(item)
	if p == null or idef == null or not p.inventory.has(item):
		return _fail("not carried")
	var sdef: StructureDef = Content.structure(StringName(str(idef.equip.get("structure", ""))))
	if sdef == null:
		return _fail("not placeable")
	var a: Array = args.get("pos", [0, 0, 0])
	var pos := Vector3(float(a[0]), float(a[1]), float(a[2]))
	var node: Player = world.player_node(p.id)
	if node != null and node.global_position.distance_to(pos) > MAX_PLACE_DIST:
		return _fail("too far")
	var n: Vector3 = (world.terrain as TerrainManager).normal_at(pos.x, pos.z)
	if pos.y <= world.height_at(pos.x, pos.z) + 0.3 and rad_to_deg(n.angle_to(Vector3.UP)) > 35.0:
		return _fail("too steep")
	var wsys: Node = world.get(&"water")
	if wsys != null and float(wsys.call(&"depth_at", pos)) > 0.25:
		return _fail("in water")
	for other: StructurePiece in pieces_in_radius(pos, 1.5):
		if not other.is_log() and other.global_position.distance_to(pos) < 0.8:
			return _fail("blocked")
	p.inventory.remove(item, 1)
	var id: StringName = Game.session.ids.next("s")
	var xf := Transform3D(Basis(Vector3.UP, float(args.get("yaw", 0.0))), pos)
	var mult: float = _hp_mult(p)
	_add_piece(id, sdef, xf, sdef.hp * mult, true, mult)
	p.progression.award("build_piece")
	Audio.play_3d(&"sfx/item_place_mat", pos, {"volume_db": -4.0})
	Events.inventory_changed.emit(p.id)
	Events.structure_placed.emit(id, sdef.id, pos)
	return {"ok": true, "piece": String(id)}


func _log_free_basis(player: Player) -> Basis:
	var yaw: float = player.global_rotation.y + _log_yaw + PI * 0.5
	var b := Basis(Vector3.UP, yaw)
	match LOG_POSES[_log_pose]:
		"post":
			b = b * Basis(Vector3.BACK, PI * 0.5)
		"pitched":
			b = b * Basis(Vector3.BACK, deg_to_rad(20.0))
	return b


func _update_log_target(player: Player) -> void:
	var a: Dictionary = _aim(player, REACH, 1 | StructurePiece.LAYER)
	var hit: Dictionary = a["hit"]
	var b: Basis = _log_free_basis(player)
	var pos: Vector3
	if hit.is_empty():
		pos = (a["from"] as Vector3) + (a["dir"] as Vector3) * REACH * 0.8
	else:
		pos = (hit["position"] as Vector3) + (hit["normal"] as Vector3) * LogSnapper.RADIUS
		if LOG_POSES[_log_pose] == "post":
			pos = (hit["position"] as Vector3) + Vector3.UP * (LogSnapper.LENGTH * 0.5 - 0.15)
	var free := Transform3D(b, pos)
	var neighbours: Array[Transform3D] = []
	for p: StructurePiece in pieces_in_radius(pos, 5.0):
		if p.is_log():
			neighbours.append(p.global_transform)
	var snap: Dictionary = LogSnapper.best_snap(free, neighbours)
	var xf: Transform3D = snap["xform"] if snap["ok"] else free
	var why: String = log_blocker(xf, player.global_position)
	if hit.is_empty() and not snap["ok"]:
		why = "nothing to rest on"
	_log_target = {"ok": why == "", "xform": xf, "snapped": snap["ok"], "why": why}
	preview.global_transform = xf
	preview.show_log()
	preview.set_state(why == "", snap["ok"])


## Why a log can't go here ("" = it can). Used by the preview and re-checked by the command.
func log_blocker(xf: Transform3D, from: Vector3) -> String:
	if xf.origin.distance_to(from + Vector3.UP * 1.5) > MAX_PLACE_DIST:
		return "too far"
	var ground: float = world.height_at(xf.origin.x, xf.origin.z)
	if xf.origin.y < ground - 0.15:
		return "buried"
	var touching: bool = _log_grounded(xf)
	for p: StructurePiece in pieces_in_radius(xf.origin, 5.0):
		if not p.is_log():
			continue
		if LogSnapper.overlaps(xf, p.global_transform):
			return "blocked"
		if LogSnapper.relation(xf, p.global_transform) != &"":
			touching = true
	return "" if touching else "unsupported"


func _log_grounded(xf: Transform3D) -> bool:
	var seg: PackedVector3Array = LogSnapper.segment(xf)
	for i: int in 5:
		var p: Vector3 = seg[0].lerp(seg[1], float(i) / 4.0)
		var bottom: float = p.y - LogSnapper.RADIUS * absf(xf.basis.x.normalized().dot(Vector3.UP) - 1.0)
		if LogSnapper.is_vertical(xf.basis):
			bottom = minf(seg[0].y, seg[1].y)
		if bottom <= world.height_at(p.x, p.z) + GROUND_TOLERANCE:
			return true
	return false


# --- Commands ------------------------------------------------------------------------------------

func _player_state(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id))))


static func _fail(why: String) -> Dictionary:
	return {"ok": false, "error": why}


func _cmd_place_blueprint(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var bp: BlueprintDef = Content.get_def(&"blueprint", StringName(str(args.get("blueprint", "")))) as BlueprintDef
	if p == null or bp == null:
		return _fail("unknown blueprint")
	if not p.progression.knows_blueprint(bp):
		return _fail("not learned")
	var a: Array = args.get("pos", [0, 0, 0])
	var xf := Transform3D(Basis(Vector3.UP, float(args.get("yaw", 0.0))), Vector3(float(a[0]), float(a[1]), float(a[2])))
	var why: String = _blueprint_blocker(bp, xf)
	if why != "":
		Events.player_status_message.emit("Can't build here: %s." % why, &"warning")
		return _fail(why)
	var id: StringName = Game.session.ids.next("bp")
	var site: BlueprintSite = _spawn_site(id, bp, xf, {}, [])
	Audio.play_3d(&"sfx/blueprint_place", xf.origin, {"volume_db": -6.0})
	Game.session.world.blueprints[String(id)] = site.to_dict()
	return {"ok": true, "site": String(id)}


func _cmd_deliver(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var site: BlueprintSite = sites.get(StringName(str(args.get("site", ""))))
	if p == null or site == null or site.bp.mode != "assembly":
		return _fail("no site")
	var gave: int = 0
	var rem: Dictionary = site.remaining()
	for k: Variant in rem.keys():
		var item := StringName(str(k))
		var n: int = mini(int(rem[k]), p.inventory.count_of(item))
		if n > 0 and p.inventory.remove(item, n):
			site.delivered[k] = int(site.delivered.get(k, 0)) + n
			gave += n
	if gave == 0:
		return _fail("nothing to add")
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/build_add_material", site.global_position, {"volume_db": -4.0})
	site.on_delivered()
	Game.session.world.blueprints[String(site.site_id)] = site.to_dict()
	if site.is_complete():
		_complete_assembly(site, p)
		return {"ok": true, "complete": true}
	return {"ok": true, "complete": false}


func _complete_assembly(site: BlueprintSite, p: PlayerState) -> void:
	var def: StructureDef = Content.structure(site.bp.result)
	var xf: Transform3D = site.global_transform
	var id: StringName = Game.session.ids.next("s")
	_remove_site(site.site_id)
	var mult: float = _hp_mult(p)
	# Standing on a log floor (ADR-0035): it rests on that log and comes down with it.
	var under: StructurePiece = support_under(xf.origin) if site.bp.on_structures and is_inside_tree() else null
	var built: StructurePiece = _add_piece(id, def, xf, def.hp * mult, under == null, mult)
	if under != null:
		graph.set_grounded(id, false)
		graph.link(id, under.piece_id, StructureGraph.Link.ON)
	if built.burns_fuel():
		built.fuel = built.station_def().start_fuel
	Audio.play_3d(&"sfx/build_complete", xf.origin, {"volume_db": -2.0})
	p.progression.award("complete_blueprint")
	Events.blueprint_completed.emit(site.site_id, def.id)
	Events.structure_placed.emit(id, def.id, xf.origin)


func _cmd_place_log(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	if p == null or not p.inventory.has(&"log"):
		return _fail("no log")
	var def: StructureDef = Content.structure(LOG_DEF)
	var xf: Transform3D
	var site: BlueprintSite = null
	var slot: int = -1
	if args.has("site"):
		site = sites.get(StringName(str(args["site"])))
		slot = int(args.get("slot", -1))
		if site == null or slot < 0 or slot >= site.bp.pieces.size() or site.placed.has(slot):
			return _fail("bad slot")
		def = site.slot_def(slot)
		xf = site.slot_global(slot)
	else:
		var a: Array = args.get("pos", [0, 0, 0])
		var r: Array = args.get("rot", [0, 0, 0, 1])
		xf = Transform3D(Basis(Quaternion(float(r[0]), float(r[1]), float(r[2]), float(r[3])).normalized()), Vector3(float(a[0]), float(a[1]), float(a[2])))
		var node: Player = world.player_node(p.id)
		var why: String = log_blocker(xf, node.global_position if node != null else p.position)
		if why != "":
			return _fail(why)
	p.inventory.remove(&"log", 1)
	Events.inventory_changed.emit(p.id)
	var id: StringName = Game.session.ids.next("s")
	var mult: float = _hp_mult(p)
	_add_piece(id, def, xf, def.hp * mult, _log_grounded(xf), mult)
	Audio.play_3d(&"sfx/log_place", xf.origin, {"volume_db": -2.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(xf.origin, 14.0, &"build", p.id)
	# A log nothing holds up simply falls (and can be picked up again). Support is settled before
	# anything is paid: a log that falls earns no XP, counts for no directive and leaves its
	# blueprint slot open, so dropping the same log into thin air is not a farm.
	var failed: Array[StringName] = graph.recompute([id])
	if failed.has(id):
		_collapse_unsupported(failed)
		Events.player_status_message.emit("Nothing holds that log up.", &"warning")
		return {"ok": true, "piece": String(id), "fell": true}
	p.progression.award("build_piece")
	if site != null:
		site.mark_placed(slot)
		Game.session.world.blueprints[String(site.site_id)] = site.to_dict()
		if site.is_complete():
			_remove_site(site.site_id)
			Events.blueprint_completed.emit(site.site_id, site.bp.id)
			Audio.play_3d(&"sfx/build_complete", xf.origin, {"volume_db": -2.0})
	Events.structure_placed.emit(id, def.id, xf.origin)
	if not failed.is_empty():
		_collapse_unsupported(failed)
	return {"ok": true, "piece": String(id)}


func _cmd_repair(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if p == null or piece == null:
		return _fail("no piece")
	if piece.hp >= piece.max_hp() - 0.5:
		return _fail("not damaged")
	var cost: Dictionary = repair_cost(piece.def)
	if not p.inventory.has_all(cost):
		Events.player_status_message.emit("Repair needs %s." % _cost_text(cost), &"warning")
		return _fail("missing materials")
	for k: Variant in cost.keys():
		p.inventory.remove(StringName(str(k)), int(cost[k]))
	piece.hp = minf(piece.max_hp(), piece.hp + float(piece.def.repair.get("amount", piece.max_hp() * 0.3)))
	Events.inventory_changed.emit(p.id)
	Events.structure_damaged.emit(piece.piece_id, piece.hp, piece.max_hp())
	Audio.play_3d(&"sfx/hammer_repair", piece.global_position, {"volume_db": -2.0})
	return {"ok": true, "hp": piece.hp}


func _cmd_upgrade(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if p == null or piece == null or piece.def.upgrade.is_empty():
		return _fail("not upgradable")
	var to: StructureDef = Content.structure(StringName(str(piece.def.upgrade.get("to", ""))))
	var cost: Dictionary = piece.def.upgrade.get("cost", {})
	if to == null:
		return _fail("bad upgrade")
	if not p.inventory.has_all(cost):
		Events.player_status_message.emit("Upgrade needs %s." % _cost_text(cost), &"warning")
		return _fail("missing materials")
	for k: Variant in cost.keys():
		p.inventory.remove(StringName(str(k)), int(cost[k]))
	var id: StringName = piece.piece_id
	var xf: Transform3D = piece.global_transform
	var grounded: bool = graph.pieces[id].grounded if graph.has_piece(id) else true
	var links: Dictionary = (graph.pieces[id] as StructureGraph.Piece).links.duplicate() if graph.has_piece(id) else {}
	_free_piece_node(id)
	graph.pieces.erase(id)
	var mult: float = _hp_mult(p)
	_spawn_piece(id, to, xf, to.hp * mult, mult)
	graph.add_from_def(id, to, grounded)
	p.progression.award("upgrade_piece")
	for nid: StringName in links:
		if graph.has_piece(nid):
			match links[nid]:
				&"below":
					graph.link(id, nid, StructureGraph.Link.ON)
				&"above":
					graph.link(nid, id, StructureGraph.Link.ON)
				_:
					graph.link(id, nid, StructureGraph.Link.SIDE)
	graph.recompute([id])
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/hammer_upgrade", xf.origin, {"volume_db": -1.0})
	return {"ok": true}


## Takes a placed ghost down (BlueprintSite.alt_interact: the cancel key held on it). Everything
## handed over comes back, at your feet if it doesn't fit; logs already set in a log blueprint stay
## where they are, ordinary logs now.
func _cmd_demolish(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var site: BlueprintSite = sites.get(StringName(str(args.get("site", ""))))
	if p == null or site == null:
		return _fail("no site")
	if not p.stats.alive:
		return _fail("dead")
	var at: Vector3 = site.global_position
	var node: Player = world.player_node(p.id) if world != null else null
	if node != null and node.global_position.distance_to(at) > REACH + 2.0:
		return _fail("too far")
	var refund: Dictionary = {}
	var back: PackedStringArray = []
	for k: Variant in site.delivered.keys():
		var item := StringName(str(k))
		var n: int = int(site.delivered[k])
		if n <= 0:
			continue
		refund[String(item)] = n
		var idef: ItemDef = Content.item(item)
		back.append("%d %s" % [n, idef.display_name if idef != null else String(item)])
		var left: int = p.inventory.add_item(item, n)
		if left > 0 and world != null:
			# Logs that don't fit on the shoulder are dropped as logs, stacked so they don't collide.
			if item == &"log" and world.get(&"loose") != null:
				for i: int in left:
					world.loose.spawn_log(at + Vector3.UP * (0.6 + 0.5 * i), Basis(Vector3.UP, site.global_rotation.y), &"")
			else:
				ItemDrop.spawn(world, ItemStack.make(item, left), at + Vector3.UP)
	var name_: String = site.bp.display_name
	_remove_site(site.site_id)
	Audio.play_3d(&"sfx/blueprint_place", at, {"volume_db": -8.0})
	Events.inventory_changed.emit(p.id)
	Events.player_status_message.emit("Took down the %s blueprint%s." % [name_, (": " + ", ".join(back) + " back") if not back.is_empty() else ""], &"info")
	return {"ok": true, "refund": refund}


## What one hammer repair costs: the def's own repair cost, else a quarter of what it took to
## build (at least one of each), so nothing is mended for free.
static func repair_cost(def: StructureDef) -> Dictionary:
	if def.repair.has("cost"):
		return def.repair["cost"]
	var out: Dictionary = {}
	for k: Variant in def.cost.keys():
		out[k] = maxi(1, int(ceil(float(def.cost[k]) * 0.25)))
	return out


## Half of a piece's build cost (rounded down), returned when it is dismantled whole, but at
## least one of everything it cost: half of a single item (a placed can chime) is not nothing.
## A log comes back as the log itself.
static func dismantle_refund(def: StructureDef) -> Dictionary:
	if def.piece_kind == "log":
		return {"log": 1}
	var out: Dictionary = {}
	for k: Variant in def.cost.keys():
		if int(def.cost[k]) > 0:
			out[k] = maxi(1, int(floor(float(def.cost[k]) * 0.5)))
	return out


## The line under the crosshair while a hammer is aimed at a piece: its health and what the next
## strike would do.
func hammer_hint(piece: StructurePiece, p: PlayerState) -> String:
	var t: String = "%s  %d / %d" % [piece.def.display_name, ceili(piece.hp), ceili(piece.max_hp())]
	if piece.hp < piece.max_hp() - 0.5:
		var cost: Dictionary = repair_cost(piece.def)
		t += "  ·  [LMB] repair: %s%s" % [_cost_text(cost), "" if p.inventory.has_all(cost) else " (missing)"]
	elif not piece.def.upgrade.is_empty():
		t += "  ·  [LMB] twice to reinforce: %s" % _cost_text(piece.def.upgrade.get("cost", {}))
	return t + "  ·  crouch + hold [E] to dismantle"


func _cmd_dismantle(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if p == null or piece == null:
		return _fail("no piece")
	var held: ItemDef = Content.item(p.equipped_item())
	if held == null or not held.provides_tool("hammer"):
		return _fail("needs a hammer")
	var node: Player = world.player_node(p.id) if world != null else null
	if node != null and node.global_position.distance_to(piece.global_position) > REACH + 2.0:
		return _fail("too far")
	if piece.inventory != null and not piece.inventory.is_empty():
		Events.player_status_message.emit("Empty it first.", &"warning")
		return _fail("not empty")
	var id: StringName = piece.piece_id
	var def: StructureDef = piece.def
	var at: Vector3 = piece.global_position + Vector3.UP * 0.6
	# A battered piece gives back less: the refund scales with its remaining health.
	var whole: float = clampf(piece.hp / maxf(1.0, piece.max_hp()), 0.0, 1.0)
	for k: Variant in dismantle_refund(def).keys():
		var n: int = int(round(float(dismantle_refund(def)[k]) * (1.0 if def.piece_kind == "log" else whole)))
		if n <= 0:
			continue
		var left: int = p.inventory.add_item(StringName(str(k)), n)
		if left > 0:
			if StringName(str(k)) == &"log" and world.get(&"loose") != null:
				world.loose.spawn_log(at, piece.global_transform.basis, &"")
			else:
				ItemDrop.spawn(world, ItemStack.make(StringName(str(k)), left), at)
	_free_piece_node(id)
	Game.session.world.containers.erase(String(id))
	Audio.play_3d(&"sfx/hammer_nail", at, {"volume_db": -3.0})
	Events.structure_destroyed.emit(id, def.id, at)
	for cid: StringName in graph.remove_and_cascade(id):
		_collapse_node(cid)
	Events.inventory_changed.emit(p.id)
	return {"ok": true}


static func _cost_text(cost: Dictionary) -> String:
	var parts: PackedStringArray = []
	for k: Variant in cost.keys():
		var d: ItemDef = Content.item(StringName(str(k)))
		parts.append("%d %s" % [int(cost[k]), d.display_name if d != null else str(k)])
	return ", ".join(parts)


# --- Fires ---------------------------------------------------------------------------------------

## The fuel item a player would put on `piece` now: the held item if it burns, else FUEL_ORDER.
static func fuel_choice(p: PlayerState, _piece: StructurePiece = null) -> StringName:
	var held: StringName = p.equipped_item()
	if held != &"" and Content.item(held) != null and Content.item(held).fuel > 0.0 and p.inventory.has(held):
		return held
	for id: StringName in FUEL_ORDER:
		if p.inventory.has(id):
			return id
	return &""


## Game minutes one item keeps a fire going: its `fuel` is real seconds at the current day length.
static func fuel_minutes(item: ItemDef) -> float:
	var mps: float = Game.session.clock.minutes_per_real_second() if Game.session != null else 0.4
	return item.fuel * mps


func _cmd_add_fuel(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if p == null or piece == null or not piece.burns_fuel():
		return _fail("not a fire")
	var item: StringName = StringName(str(args["item"])) if args.has("item") else fuel_choice(p, piece)
	var def: ItemDef = Content.item(item)
	if def == null or def.fuel <= 0.0 or not p.inventory.has(item):
		Events.player_status_message.emit("Nothing to burn: sticks, leaves or a log.", &"warning")
		return _fail("no fuel")
	if piece.fuel >= piece.max_fuel() - 1.0:
		Events.player_status_message.emit("The fire can't take any more.", &"info")
		return _fail("full")
	p.inventory.remove(item, 1)
	piece.fuel = minf(piece.max_fuel(), piece.fuel + fuel_minutes(def))
	Audio.play_3d(&"sfx/log_drop" if item in [&"log", &"wood_plank"] else &"sfx/stick_pickup", piece.global_position, {"volume_db": -6.0})
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "fuel": piece.fuel}


# --- Racks and doors (ADR-0035) ------------------------------------------------------------------

## The piece a command names, if the player is close enough to reach it.
func _reachable_piece(p: PlayerState, args: Dictionary) -> StructurePiece:
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if piece == null or p == null:
		return null
	var pl: Player = world.player_node(p.id) if world != null else null
	if pl != null and pl.global_position.distance_to(piece.global_position) > REACH + maxf(piece.def.size.x, piece.def.size.z):
		return null
	return piece


## Puts carried items of the rack's kind on it, up to its capacity (all carried, or `count`).
func _cmd_rack_store(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = _reachable_piece(p, args)
	if piece == null or piece.rack_capacity() <= 0:
		return _fail("not a rack")
	var item: StringName = piece.rack_item()
	var room: int = piece.rack_capacity() - piece.rack_count()
	var n: int = mini(p.inventory.count_of(item), room)
	if args.has("count"):
		n = mini(n, int(args["count"]))
	if n <= 0:
		return _fail("full" if room <= 0 else "none carried")
	var stored: int = 0
	for st: ItemStack in p.inventory.take(item, n):
		var rest: int = piece.inventory.add(st)
		stored += st.count - rest
		if rest > 0:
			st.count = rest
			p.inventory.add(st)
	Events.inventory_changed.emit(p.id)
	piece.on_contents_changed()
	Audio.play_3d(&"sfx/log_drop" if item == &"log" else &"sfx/stick_pickup", piece.global_position, {"volume_db": -6.0})
	return {"ok": stored > 0, "stored": stored}


## Takes items off a rack (one, or `count`), as many as the player can carry.
func _cmd_rack_take(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = _reachable_piece(p, args)
	if piece == null or piece.rack_capacity() <= 0:
		return _fail("not a rack")
	var item: StringName = piece.rack_item()
	var n: int = mini(int(args.get("count", 1)), piece.rack_count())
	if n <= 0:
		return _fail("empty")
	var taken: int = 0
	for st: ItemStack in piece.inventory.take(item, n):
		var rest: int = p.inventory.add(st)
		taken += st.count - rest
		if rest > 0:
			st.count = rest
			piece.inventory.add(st)
	if taken <= 0:
		Events.player_status_message.emit("You can't carry any more.", &"warning")
		return _fail("can't carry")
	Events.inventory_changed.emit(p.id)
	piece.on_contents_changed()
	return {"ok": true, "taken": taken}


func _cmd_toggle_door(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = _reachable_piece(p, args)
	if piece == null or piece.def.piece_kind != "door":
		return _fail("not a door")
	piece.set_door_open(not piece.door_open)
	if piece.door_open:
		Game.session.world.flags["open:%s" % piece.piece_id] = true
	else:
		Game.session.world.flags.erase("open:%s" % piece.piece_id)
	Audio.play_3d(&"sfx/door_open_creak" if piece.door_open else &"sfx/door_close", piece.global_position + Vector3.UP, {"volume_db": -4.0})
	return {"ok": true, "open": piece.door_open}


func _cmd_light(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player_state(args)
	var piece: StructurePiece = pieces.get(StringName(str(args.get("piece", ""))))
	if p == null or piece == null or not piece.provides("light") or piece.lit:
		return _fail("nothing to light")
	if not StructurePiece.has_igniter(p):
		Events.player_status_message.emit("You need something to light it with.", &"warning")
		return _fail("no igniter")
	if piece.burns_fuel() and piece.fuel <= 0.0:
		return _fail("no fuel")
	piece.set_lit(true)
	Audio.play_3d(&"sfx/fire_ignite", piece.global_position, {"volume_db": -2.0})
	return {"ok": true}


## Lit fires burn their fuel down with game time (sleeping by one burns it too), add attention
## to the heat map, and go out when they run dry.
func _burn_fires(minutes: float) -> void:
	for id: StringName in _fires.keys():
		var piece: StructurePiece = _fires[id]
		if not is_instance_valid(piece):
			_fires.erase(id)
			continue
		if not piece.lit:
			continue
		piece.fuel -= minutes
		var sd: StationDef = piece.station_def()
		if sd != null and sd.heat_per_minute > 0.0:
			Game.session.heat.add(piece.global_position, sd.heat_per_minute * minutes)
		if piece.fuel <= 0.0:
			piece.fuel = 0.0
			piece.set_lit(false)
			var pl: Player = world.player if world != null else null
			if pl != null and pl.global_position.distance_to(piece.global_position) < 30.0:
				Events.player_status_message.emit("The %s has burned out." % piece.def.display_name.to_lower(), &"info")


# --- Pieces, support, damage ---------------------------------------------------------------------

## Toughness multiplier a player's pieces get (Wits per level + Builder perk).
static func _hp_mult(p: PlayerState) -> float:
	return 1.0 + maxf(0.0, p.progression.modifier("structure_hp_mult")) if p != null else 1.0


func _spawn_piece(id: StringName, def: StructureDef, xf: Transform3D, hp: float, hp_mult: float = 1.0) -> StructurePiece:
	var piece := StructurePiece.new()
	piece.setup(id, def, self, hp, hp_mult)
	piece.name = String(id).replace(":", "_")
	add_child(piece)
	piece.global_transform = xf
	pieces[id] = piece
	if piece.burns_fuel():
		_fires[id] = piece
	var c: Vector2i = cell_of(xf.origin)
	if not _cells.has(c):
		_cells[c] = []
	(_cells[c] as Array).append(id)
	return piece


## Adds a piece to the world and the support graph, linking it to the logs it touches.
func _add_piece(id: StringName, def: StructureDef, xf: Transform3D, hp: float, grounded: bool, hp_mult: float = 1.0) -> StructurePiece:
	var piece: StructurePiece = _spawn_piece(id, def, xf, hp, hp_mult)
	graph.add_from_def(id, def, grounded or def.piece_kind != "log")
	if def.piece_kind == "log":
		for other: StructurePiece in pieces_in_radius(xf.origin, 5.0):
			if other == piece or not other.is_log():
				continue
			match LogSnapper.relation(xf, other.global_transform):
				&"on":
					graph.link(id, other.piece_id, StructureGraph.Link.ON)
				&"under":
					graph.link(other.piece_id, id, StructureGraph.Link.ON)
				&"side":
					graph.link(id, other.piece_id, StructureGraph.Link.SIDE)
	return piece


func _free_piece_node(id: StringName) -> void:
	var piece: StructurePiece = pieces.get(id)
	if piece == null:
		return
	var c: Vector2i = cell_of(piece.global_position)
	if _cells.has(c):
		(_cells[c] as Array).erase(id)
	pieces.erase(id)
	_fires.erase(id)
	if piece.lit and Game.session != null:
		Game.session.world.flags.erase("lit:%s" % id)
	if piece.door_open and Game.session != null:
		Game.session.world.flags.erase("open:%s" % id)
	piece.queue_free()


func damage_piece(piece: StructurePiece, info: DamageInfo) -> void:
	if not pieces.has(piece.piece_id):
		return
	if info.tool_power.has("repair") and Game.session.players.has(info.source_id):
		var args: Dictionary = {"player": String(info.source_id), "piece": String(piece.piece_id)}
		if piece.hp < piece.max_hp() - 0.5:
			Game.execute(&"build.repair", args)
		elif not piece.def.upgrade.is_empty():
			var now: float = Time.get_ticks_msec() / 1000.0
			if _upgrade_armed == piece.piece_id and now - _upgrade_armed_at <= UPGRADE_CONFIRM:
				_upgrade_armed = &""
				Game.execute(&"build.upgrade", args)
			else:
				_upgrade_armed = piece.piece_id
				_upgrade_armed_at = now
				var to: StructureDef = Content.structure(StringName(str(piece.def.upgrade.get("to", ""))))
				Events.player_status_message.emit("Strike again to reinforce it into a %s (%s)." % [
					to.display_name.to_lower() if to != null else "?", _cost_text(piece.def.upgrade.get("cost", {}))], &"info")
				Audio.play_3d(&"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -8.0})
		else:
			Audio.play_3d(&"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -8.0})
		return
	var amount: float = float(info.tool_power.get("structure", info.amount))
	var mult: float = float(piece.def.damage_mult.get(String(info.type), 1.0))
	if info.cause == &"zombie":
		mult *= float(piece.def.damage_mult.get("zombie", 1.0))
	amount *= mult
	if amount <= 0.0:
		return
	piece.hp -= amount
	Events.structure_damaged.emit(piece.piece_id, piece.hp, piece.max_hp())
	var stone: bool = piece.def.material in ["stone", "concrete"]
	Audio.play_3d(&"sfx/hit_stone" if stone else &"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -3.0})
	FxLibrary.burst(self, "stone" if stone else "splinters", info.hit_pos, -info.direction, 0.5)
	if piece.hp <= 0.0:
		destroy_piece(piece.piece_id)


func destroy_piece(id: StringName) -> void:
	var piece: StructurePiece = pieces.get(id)
	if piece == null:
		return
	var def: StructureDef = piece.def
	var center: Vector3 = piece.global_transform * Vector3(0, 0 if def.piece_kind == "log" else def.size.y * 0.5, 0)
	var stone: bool = def.material in ["stone", "concrete"]
	FxLibrary.burst(self, "stone" if stone else "splinters", center, Vector3.UP, 1.6)
	FxLibrary.burst(self, "dust", center, Vector3.UP, 1.0)
	Audio.play_3d(&"sfx/structure_break_wood" if not stone else &"sfx/structure_break_stone", center, {"volume_db": 0.0, "max_distance": 80.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(center, 35.0, &"structure_break", id)
	if def.fracture != "" and ModelLibrary.has_model(def.fracture):
		StructureDebris.spawn(get_parent(), ModelLibrary.mesh(def.fracture), piece.global_transform, def.size, Vector3.UP * 1.5)
	if piece.inventory != null:
		for s: ItemStack in piece.inventory.stacks:
			ItemDrop.spawn(world, s, center + Vector3(randf_range(-0.4, 0.4), 0.4, randf_range(-0.4, 0.4)))
		Game.session.world.containers.erase(String(id))
	_free_piece_node(id)
	Events.structure_destroyed.emit(id, def.id, center)
	var collapsed: Array[StringName] = graph.remove_and_cascade(id)
	for cid: StringName in collapsed:
		_collapse_node(cid)


## Removes unsupported pieces (and whatever they were holding up).
func _collapse_unsupported(failed: Array[StringName]) -> void:
	var queue: Array[StringName] = failed.duplicate()
	while not queue.is_empty():
		var id: StringName = queue.pop_front()
		if not graph.has_piece(id):
			continue
		var more: Array[StringName] = graph.remove_piece(id)
		_collapse_node(id)
		for m: StringName in more:
			if not queue.has(m):
				queue.append(m)


## A piece that lost support falls: logs become loose logs, everything else tumbling debris.
func _collapse_node(id: StringName) -> void:
	var piece: StructurePiece = pieces.get(id)
	if piece == null:
		return
	var xf: Transform3D = piece.global_transform
	var loose: Node = world.get(&"loose") if world != null else null
	if piece.is_log() and loose != null:
		var l: LogEntity = loose.call(&"spawn_log", xf.origin, xf.basis, &"")
		l.linear_velocity = Vector3(randf_range(-0.5, 0.5), -0.5, randf_range(-0.5, 0.5))
	else:
		var m: Mesh = ModelLibrary.mesh(piece.def.model, "box") if ModelLibrary.has_model(piece.def.model) else null
		if m != null:
			StructureDebris.spawn(get_parent(), m, xf, piece.def.size, Vector3.ZERO)
	Audio.play_3d(&"sfx/structure_collapse", xf.origin, {"volume_db": -2.0, "max_distance": 80.0})
	Events.structure_destroyed.emit(id, piece.def.id, xf.origin)
	_free_piece_node(id)


func _on_terrain_modified(aabb: AABB) -> void:
	var grown: AABB = aabb.grow(1.5)
	var seeds: Array = []
	for id: StringName in pieces:
		var p: StructurePiece = pieces[id]
		if not grown.has_point(p.global_position) or not p.is_log() or not graph.has_piece(id):
			continue
		var g: bool = _log_grounded(p.global_transform)
		if g != (graph.pieces[id] as StructureGraph.Piece).grounded:
			graph.set_grounded(id, g)
			seeds.append(id)
	if not seeds.is_empty():
		var failed: Array[StringName] = graph.recompute(seeds)
		if not failed.is_empty():
			_collapse_unsupported(failed)


# --- Sites -----------------------------------------------------------------------------------------

func _spawn_site(id: StringName, bp: BlueprintDef, xf: Transform3D, delivered: Dictionary, placed: Array) -> BlueprintSite:
	var site := BlueprintSite.new()
	site.setup(id, bp, self, delivered, placed)
	site.name = String(id).replace(":", "_")
	add_child(site)
	site.global_transform = xf
	sites[id] = site
	return site


func _remove_site(id: StringName) -> void:
	var s: BlueprintSite = sites.get(id)
	if s != null:
		s.queue_free()
	sites.erase(id)
	Game.session.world.blueprints.erase(String(id))


# --- Persistence -----------------------------------------------------------------------------------

func _restore(ws: WorldState) -> void:
	for k: Variant in ws.structures.keys():
		var e: Dictionary = ws.structures[k]
		var def: StructureDef = Content.structure(StringName(str(e.get("def", ""))))
		if def == null:
			Log.warn("building", "dropping structure %s: unknown def %s" % [k, e.get("def")])
			continue
		var id := StringName(str(k))
		var mult: float = float(e.get("hp_mult", 1.0))
		var piece: StructurePiece = _spawn_piece(id, def, _xf(e), float(e.get("hp", def.hp * mult)), mult)
		if piece.burns_fuel():
			# Saves from before fuel existed: the fire keeps its kindling.
			piece.fuel = float(e.get("fuel", piece.station_def().start_fuel))
			if piece.lit and piece.fuel <= 0.0:
				piece.set_lit(false)
		graph.add_from_def(id, def, bool(e.get("grounded", true)))
	for k: Variant in ws.structures.keys():
		var id := StringName(str(k))
		if not graph.has_piece(id):
			continue
		var links: Dictionary = (ws.structures[k] as Dictionary).get("links", {})
		for nk: Variant in links.keys():
			var nid := StringName(str(nk))
			match str(links[nk]):
				"below":
					graph.link(id, nid, StructureGraph.Link.ON)
				"above":
					graph.link(nid, id, StructureGraph.Link.ON)
				_:
					graph.link(id, nid, StructureGraph.Link.SIDE)
	graph.recompute()
	for k: Variant in ws.blueprints.keys():
		var e: Dictionary = ws.blueprints[k]
		var bp: BlueprintDef = Content.get_def(&"blueprint", StringName(str(e.get("def", "")))) as BlueprintDef
		if bp != null:
			_spawn_site(StringName(str(k)), bp, _xf(e), e.get("delivered", {}), e.get("placed", []))


static func _xf(e: Dictionary) -> Transform3D:
	var a: Array = e.get("pos", [0, 0, 0])
	var r: Array = e.get("rot", [0, 0, 0, 1])
	return Transform3D(Basis(Quaternion(float(r[0]), float(r[1]), float(r[2]), float(r[3])).normalized()), Vector3(float(a[0]), float(a[1]), float(a[2])))


func save_into(session: GameSession) -> void:
	var out: Dictionary = {}
	for id: StringName in pieces:
		var p: StructurePiece = pieces[id]
		var gp: StructureGraph.Piece = graph.pieces.get(id)
		var links: Dictionary = {}
		if gp != null:
			for nid: StringName in gp.links:
				links[String(nid)] = String(gp.links[nid])
		var q: Quaternion = p.global_transform.basis.get_rotation_quaternion()
		var o: Vector3 = p.global_position
		out[String(id)] = {"def": String(p.def.id), "pos": [o.x, o.y, o.z], "rot": [q.x, q.y, q.z, q.w], "hp": p.hp,
			"grounded": gp.grounded if gp != null else true, "links": links}
		if not is_equal_approx(p.hp_mult, 1.0):
			out[String(id)]["hp_mult"] = p.hp_mult
		if p.burns_fuel():
			out[String(id)]["fuel"] = snappedf(p.fuel, 0.1)
		if p.inventory != null:
			session.world.set_container_items(id, p.inventory)
	session.world.structures = out
	var bps: Dictionary = {}
	for id: StringName in sites:
		bps[String(id)] = (sites[id] as BlueprintSite).to_dict()
	session.world.blueprints = bps
