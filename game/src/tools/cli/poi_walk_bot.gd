extends Node
## POI traversal bot (the owner's priority #2: doorways blocked, items lying in the way, climbs
## that need an interact or a vault). Builds one building with PoiBuilder on a bare flat pad, puts
## the real Player scene (same capsule, controller, step-up and vault as play) outside its
## entrance, and walks the validator's route through it with real movement: the move action held,
## the body turned toward each target (cell centres, so doorway centres and stair lines), Jump
## pressed only when it stalls (a jump or the player's own vault), Crouch after that. Doors are
## opened (and unlocked with the keys the validator finds on the route) the way a player would.
## After the route it walks to every room the layout says it can reach. It teleports only to
## restart after a leg it could not finish.
##
## Each walk returns a report Dictionary (see `walk`): legs with what they needed, the colliders
## that stopped the body (node path, prop id, POI-local cell), rooms never reached, ladder climbs
## (an interact by design), and props whose collision box stands in a doorway's clear width or on
## a route cell. Used by poi_walk_runner.gd (the CLI) and test_poi_walk.gd.
## Not in exported builds (src/tools/cli is excluded).

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const Lots := preload("res://src/poi/lot_picker.gd")
const Generator := preload("res://src/poi/building_generator.gd")

## Within this horizontal distance (m) of a target the body has reached it.
const REACH: float = 0.24
## Physics frames without 3 cm of progress before the bot tries something (0.6 s).
const STALL_FRAMES: int = 36
## Give up on one target after this many frames (12 s), whatever was tried.
const TARGET_FRAMES: int = 720
## Opening types a player walks through upright: needing a jump or a vault there is a finding.
const WALK_THROUGH: PackedStringArray = ["door", "door2", "door2_tall", "open", "breach"]
## Clear zone either side of a doorway's wall line (m) checked for props.
const DOOR_DEPTH: float = 0.55
## Plan costs on top of 1 a step: through a prop, and under a stair flight or over a stairwell.
const CLUTTER_COST: float = 25.0
## How far clear of a leaf's swing the bot stands to open a door (past REACH's slack).
const ASIDE_MARGIN: float = 0.4
const BLOCKED_COST: float = 200.0
const WINDOW_COST: float = 15.0

## Print every leg as it is walked.
var verbose: bool = false

var layout: PoiLayout
var validator: PoiValidator
var inst: PoiInstance
var player: Player
var _world: Node3D
var _helper: PoiBuilder
## Authored props with collision: {id, prop, pkey, level, cell, box: AABB (POI-local), container}
var _props: Array[Dictionary] = []
## "L:char" -> true for every room the body has stood in.
var _visited: Dictionary = {}
var _cur: Array = []
var _hits: Array[Dictionary] = []
var _keys: Dictionary = {}
## Door leaves shut on the current leg (instance ids), so one is not toggled back and forth.
var _shut: Dictionary = {}
## Open leaves the walk had to shut to get past: {opening, leaf}.
var _door_leaves: Array = []
var _frames: int = 0
var _report: Dictionary = {}


## A building by walk id: a POI id, "gen:<template>:<seed>" (what that template generates from
## that seed) or "lot:<framework>:<lot id>" (what a run with `world_seed` stands on that lot).
## Returns [PoiDef dressed for the run, instance id] or [] when the id names nothing.
static func resolve(id: String, world_seed: int, session: GameSession) -> Array:
	var pd: PoiDef = null
	var iid: String = "walk/" + id.replace(":", "_")
	if id.begins_with("lot:"):
		var lp: PackedStringArray = id.split(":")
		var fw: FrameworkDef = Content.get_def(&"framework", StringName(lp[1])) as FrameworkDef if lp.size() > 2 else null
		if fw == null:
			return []
		for res: Dictionary in Lots.resolve(fw, lp[1], world_seed):
			if str((res["lot"] as Dictionary).get("id", "")) == lp[2]:
				iid = str(res["instance"])
				pd = Lots.def_for(res)
		if pd == null:
			return []
	elif id.begins_with("gen:"):
		var parts: PackedStringArray = id.split(":")
		var t: Resource = Content.get_def(&"building_template", StringName(parts[1])) if parts.size() > 1 else null
		if t == null:
			return []
		pd = Generator.generate(t, int(parts[2]) if parts.size() > 2 else 1) as PoiDef
	else:
		pd = Content.get_def(&"poi", StringName(id)) as PoiDef
	if pd == null:
		return []
	return [PoiManager.dress_for(pd, StringName(iid), session), iid]


## Every lot of every framework as a walk id (authored picks and generated houses alike).
static func pool_ids(world_seed: int) -> PackedStringArray:
	var out: PackedStringArray = []
	for fw: FrameworkDef in Content.all(&"framework"):
		for res: Dictionary in Lots.resolve(fw, String(fw.id), world_seed):
			if str(res["kind"]) in ["authored", "generated"]:
				out.append("lot:%s:%s" % [fw.id, (res["lot"] as Dictionary).get("id", "")])
	return out


# --- the walk ------------------------------------------------------------------------------------

## Builds `pd` at the origin, walks it and frees it again. Report keys: poi, instance, validator
## (its errors), legs [{from, to, kind, opening, ok, needed, blocker, frames}], blocked (legs the
## body could not finish: doorways, stairs, ladders, steps), assisted (legs on a walk-through
## opening, a stair flight or plain floor that needed a jump, a vault or a crouch), climbs (ladder
## interacts), unreached (rooms the layout reaches that the body never stood in), sealed (rooms the
## layout itself cannot reach), corridor (props in a doorway's clear width or on a route cell),
## blocking (the count that fails the building) and frames walked.
func walk(pd: PoiDef, instance_id: String) -> Dictionary:
	_report = {"poi": String(pd.id), "name": pd.display_name, "instance": instance_id, "legs": [], "blocked": [], "assisted": [],
		"climbs": [], "unreached": [], "sealed": [], "corridor": [], "leaf_in_way": [], "waypoints_on_props": [], "validator": [],
		"blocking": 0, "frames": 0}
	_visited.clear()
	_cluttered.clear()
	_hits.clear()
	_frames = 0
	validator = PoiValidator.validate(pd)
	layout = validator.layout
	_report["validator"] = Array(validator.errors)
	_keys = (validator._keys_found as Dictionary).duplicate()
	_build(instance_id)
	_index_props()
	_index_steps()
	_check_corridor()
	await _settle(3)
	if OS.has_environment("POI_WALK_PROBE"):
		var pp: PackedStringArray = OS.get_environment("POI_WALK_PROBE").split(",")
		var q := PhysicsRayQueryParameters3D.create(Vector3(float(pp[0]), 3.0, float(pp[1])), Vector3(float(pp[0]), -3.0, float(pp[1])), 0xFFFFFFFF)
		var hit: Dictionary = player.get_world_3d().direct_space_state.intersect_ray(q)
		print("[poi_walk]     probe %s %s" % [hit, (hit["collider"] as Node).get_path() if not hit.is_empty() else ""])
	await _walk_route()
	await _explore()
	_rooms_report()
	Input.action_release(&"move_forward")
	_world.queue_free()
	await _settle(2)
	_world = null
	inst = null
	player = null
	var blocking: int = (_report["blocked"] as Array).size() + (_report["unreached"] as Array).size()
	_report["blocking"] = blocking
	_report["frames"] = _frames
	return _report


func _settle(n: int) -> void:
	for i: int in n:
		await get_tree().physics_frame


func _build(instance_id: String) -> void:
	_world = Node3D.new()
	_world.name = "PoiWalkWorld"
	add_child(_world)
	_ground()
	inst = PoiBuilder.build(layout, StringName(instance_id), validator)
	_world.add_child(inst)
	_helper = PoiBuilder.new()
	_helper.layout = layout
	_helper._porch_cells = _helper._porch_cell_set()
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.name = "Player"
	_world.add_child(player)
	player.bind_state(PlayerState.new())
	player.god_mode = true
	player.input_enabled = true
	for k: String in _keys:
		player.state.inventory.add_item(StringName(k), 1)


## A flat pad at y = 0 (the top of thin slabs) round and under the building, open over every cell a
## level below the ground has a room under a ground-floor room (TerrainHoles cuts those in play).
func _ground() -> void:
	var body := StaticBody3D.new()
	body.name = "Ground"
	body.collision_layer = 1
	body.set_meta(&"surface", "dirt")
	_world.add_child(body)
	var ext: Rect2 = layout.extent().grow(4.0)
	var x0: int = floori(ext.position.x)
	var z0: int = floori(ext.position.y)
	var x1: int = ceili(ext.end.x)
	var z1: int = ceili(ext.end.y)
	var far: float = 60.0
	# The ring round the building's area.
	_slab(body, Rect2(x0 - far, z0 - far, (x1 - x0) + far * 2.0, far))
	_slab(body, Rect2(x0 - far, z1, (x1 - x0) + far * 2.0, far))
	_slab(body, Rect2(x0 - far, z0, far, z1 - z0))
	_slab(body, Rect2(x1, z0, far, z1 - z0))
	var below: Array[int] = []
	for li: int in layout.level_ids:
		if li < 0:
			below.append(li)
	for z: int in range(z0, z1):
		# (A run start, not a -1 sentinel: the pad starts at negative x.)
		var running: bool = false
		var run: int = 0
		for x: int in range(x0, x1 + 1):
			var open: bool = false
			if x < x1:
				var c := Vector2i(floori(x - layout.origin.x), floori(z - layout.origin.y))
				if layout.is_built(0, c):
					for li: int in below:
						open = open or layout.is_built(li, c)
			if x < x1 and not open:
				if not running:
					running = true
					run = x
			elif running:
				_slab(body, Rect2(run, z, x - run, 1))
				running = false


func _slab(body: StaticBody3D, r: Rect2) -> void:
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = Vector3(r.size.x, 0.3, r.size.y)
	cs.shape = b
	cs.position = Vector3(r.get_center().x, -0.15, r.get_center().y)
	body.add_child(cs)


## The authored props that collide, with their boxes in POI-local space (the builder's own
## placement: PoiBuilder._prop_xf).
func _index_props() -> void:
	_props.clear()
	for p: Dictionary in layout.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null:
			continue
		var cont: String = str(p.get("container", pd.container))
		var is_cont: bool = cont != "" and Content.get_def(&"container", StringName(cont)) != null
		if pd.collision == "none" and not is_cont:
			continue
		var xf: Transform3D = _helper._prop_xf(p, pd)
		var size: Vector3 = pd.size.max(Vector3(0.2, 0.2, 0.2) if is_cont else Vector3(0.05, 0.05, 0.05))
		var box := AABB(pd.box_centre() - size * 0.5, size)
		_props.append({"id": str(p.get("id", "")), "prop": String(pd.id), "pkey": str(p["pkey"]), "level": int(p["level"]),
			"cell": p["cell"], "box": xf * box, "container": is_cont, "route_ok": bool(p.get("route_ok", false))})
	# Solid things the builder adds that are not authored props: the chimney stack (it stands in
	# a yard cell) and the crates RouteCues stands under entry windows.
	var chim: Variant = layout.style.get("chimney", null)
	if chim is Array:
		var cp := Vector3(layout.origin.x + float(chim[0]) + 0.5, 0.0, layout.origin.y + float(chim[1]) + 0.5)
		_props.append({"id": "chimney", "prop": "chimney", "pkey": "style.chimney", "level": 0, "cell": Vector2i(int(chim[0]), int(chim[1])),
			"box": AABB(cp + Vector3(-0.4, 0.0, -0.3), Vector3(0.8, 6.0, 0.6)), "container": false, "route_ok": false})
	# Every other solid body the build adds in the body's way (barricade boards and furniture piles,
	# trap rigs, the crates RouteCues stands under entry windows), so the plan goes round them.
	_add_bodies(inst)


func _add_bodies(n: Node) -> void:
	for c: Node in n.get_children():
		_add_bodies(c)
	if not n is CollisionObject3D or n == inst.shell or n is PoiPieces.Door or n is PoiPieces.LootProp or n is PoiPieces.Ladder:
		return
	if (n as CollisionObject3D).collision_layer & player.collision_mask == 0:
		return
	if n is PoiPieces.Breakable and (n as PoiPieces.Breakable).kind == "glass":
		return
	for cs: Node in n.get_children():
		if not cs is CollisionShape3D or not (cs as CollisionShape3D).shape is BoxShape3D or (cs as CollisionShape3D).disabled:
			continue
		var sz: Vector3 = ((cs as CollisionShape3D).shape as BoxShape3D).size
		var bx: AABB = (cs as CollisionShape3D).global_transform * AABB(-sz * 0.5, sz)
		var label: String = str(inst.get_path_to(n))
		if n is PoiPieces.Breakable:
			label = "barricade:" + (n as PoiPieces.Breakable).piece_id
		_props.append({"id": label, "prop": label, "pkey": label, "level": 0,
			"cell": Vector2i(floori(bx.get_center().x - layout.origin.x), floori(bx.get_center().z - layout.origin.y)), "box": bx,
			"container": false, "route_ok": true, "cue": true})


# --- static corridor check -------------------------------------------------------------------------

## Props whose collision box stands in a walk-through doorway's clear width (DOOR_DEPTH either side
## of the wall, up to 2 m) or in the middle of a route cell (where the capsule passes, above step
## height). Authored `route_ok` props are listed on route cells but flagged.
func _check_corridor() -> void:
	var out: Array = _report["corridor"]
	for op: Dictionary in layout.openings:
		var t: String = str(op["type"])
		if not WALK_THROUGH.has(t) or str(op["state"]) in ["barricaded", "boarded"]:
			continue
		var spec: Dictionary = PoiParts.OPENINGS[t]
		var xf: Transform3D = _helper._edge_xf(int(op["level"]), op["axis"], op["edge"], int(spec["len"]))
		var w: float = float(spec["w"])
		var zone: AABB = xf * AABB(Vector3(-w * 0.5, 0.05, -DOOR_DEPTH), Vector3(w, 2.0, DOOR_DEPTH * 2.0))
		for pr: Dictionary in _props:
			if bool(pr.get("cue", false)):
				continue
			var ov: AABB = zone.intersection(pr["box"])
			if ov.size.x > 0.02 and ov.size.z > 0.02 and ov.size.y > 0.02:
				out.append({"what": "doorway", "opening": str(op["id"]), "level": int(op["level"]), "prop": pr["prop"], "id": pr["id"],
					"pkey": pr["pkey"], "cell": _v2(pr["cell"]), "overlap_m": snappedf(minf(ov.size.x, ov.size.z), 0.01)})
	var seen: Dictionary = {}
	for path: Array in validator.paths:
		for n: Variant in path:
			if not n is Array or seen.has(_nk(n)):
				continue
			seen[_nk(n)] = true
			var li: int = n[0]
			var c: Vector2i = n[1]
			var ctr: Vector3 = _cell_pos(li, c)
			var zone2 := AABB(ctr + Vector3(-Player.RADIUS, Player.STEP_HEIGHT, -Player.RADIUS), Vector3(Player.RADIUS * 2.0, Player.STAND_HEIGHT - Player.STEP_HEIGHT, Player.RADIUS * 2.0))
			for pr2: Dictionary in _props:
				if bool(pr2.get("cue", false)):
					continue
				var ov2: AABB = zone2.intersection(pr2["box"])
				if ov2.size.x > 0.02 and ov2.size.z > 0.02 and ov2.size.y > 0.02:
					out.append({"what": "route_cell", "level": li, "cell": _v2(c), "prop": pr2["prop"], "id": pr2["id"], "pkey": pr2["pkey"],
						"route_ok": pr2["route_ok"], "overlap_m": snappedf(minf(ov2.size.x, ov2.size.z), 0.01)})


# --- route ----------------------------------------------------------------------------------------------

## Walks the authored route waypoint to waypoint. The legs between them are planned here over the
## validator's own graph (PoiValidator._neighbors: doors, stairs, ladders, holes, keys), minus its
## "out" node (which joins every yard cell at once): a step up more than the body steps (no stairs
## or porch steps there) and a cell whose middle a prop stands in cost extra, so the plan goes round
## a table the way a player would and only climbs where nothing else gets there.
func _walk_route() -> void:
	var start: Array = _start_node()
	if start.is_empty():
		return
	await _start_outside(start)
	_cur = start
	for wp: Dictionary in layout.route:
		var goal: Array = [int(wp["level"]), wp["cell"]]
		if not validator._walkable(goal[0], goal[1]):
			continue
		if _same(goal, _cur):
			continue
		var goals: Array = [goal]
		if _is_cluttered(goal):
			# A waypoint on a table or a counter: beside it, in the same room, will do.
			(_report["waypoints_on_props"] as Array).append({"waypoint": str(wp.get("label", "")), "level": goal[0], "cell": _v2(goal[1])})
			for d: Vector2i in PoiLayout.DIRS:
				var nb: Array = [goal[0], (goal[1] as Vector2i) + d]
				if layout.volume_of(nb[0], nb[1]) == layout.volume_of(goal[0], goal[1]) and validator._walkable(nb[0], nb[1]) and not _is_cluttered(nb):
					goals.append(nb)
		var path: Array = _plan(_cur, goals)
		if path.is_empty():
			var leg: Dictionary = _new_leg(_cur, goal, "route")
			_end_leg(leg, false, _cell_pos(goal[0], goal[1]), {"kind": "no way from here in the layout (with the keys found)"})
			_cur = goal
			continue
		await _walk_nodes(path)


## Where the walk starts: the route's first waypoint when it is outside, else the last yard cell
## the validator's first path crosses before it goes in.
func _start_node() -> Array:
	if layout.route.is_empty():
		return []
	var wp0: Dictionary = layout.route[0]
	if int(wp0["level"]) == 0 and not layout.is_built(0, wp0["cell"]):
		return [0, wp0["cell"]]
	var best: Array = []
	if not validator.paths.is_empty():
		for n: Variant in validator.paths[0]:
			if n is Array and int(n[0]) == 0 and not layout.is_built(0, n[1]):
				best = n
			elif n is Array and not best.is_empty():
				break
	return best


## Puts the body a couple of metres out from the start cell (away from the building; in front of
## the nearest porch step when the start is on a porch that has steps) and walks it there.
func _start_outside(start: Array) -> void:
	var cell: Vector2i = start[1]
	var target: Vector3 = _cell_pos(0, cell)
	var ctr: Vector2 = layout.extent().get_center()
	var away := Vector3(target.x - ctr.x, 0.0, target.z - ctr.y)
	away = away.normalized() if away.length() > 0.1 else Vector3.BACK
	# The nearest exterior side of the building from the start cell, when it is right beside it.
	for side: int in 4:
		var n: Vector2i = cell - PoiLayout.DIRS[side]
		if layout.is_built(0, n) or _helper._porch_cells.has(n):
			away = Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
			break
	var waypoints: Array[Vector3] = []
	var porch: Dictionary = layout.style.get("porch", {})
	if _helper._porch_cells.has(cell) and not _step_cells.is_empty():
		var best: Vector2i = cell
		var bd: float = INF
		for sc: Vector2i in _step_cells:
			if Vector2(sc - cell).length() < bd:
				bd = Vector2(sc - cell).length()
				best = sc
		var side2: int = PoiLayout.SIDES.get(str(porch.get("side", "S")), 2)
		var out_d := Vector3(PoiLayout.DIRS[side2].x, 0, PoiLayout.DIRS[side2].y)
		var step_pos: Vector3 = _cell_pos(0, best)
		_place(Vector3(step_pos.x, 0.0, step_pos.z) + out_d * 2.6, -out_d)
		waypoints = [step_pos, target]
	else:
		_place(Vector3(target.x, 0.0, target.z) + away * 2.5, -away)
		waypoints = [target]
	await _settle(4)
	var leg: Dictionary = _new_leg("outside", start, "approach")
	var ok: bool = true
	for wp: Vector3 in waypoints:
		ok = ok and await _go(wp, true, leg)
	_end_leg(leg, ok, waypoints.back())


## Outer-row porch cells that have steps down to the yard.
var _step_cells: Dictionary = {}
## "L:c:r" of cells whose middle (where the capsule passes) a prop's collision box stands in.
var _cluttered: Dictionary = {}


## Whether a prop's collision box stands where the capsule passes (above step height): through a
## cell's middle, or (with `from`, on one level) anywhere along the straight line between two
## cells' middles. Cached.
func _is_cluttered(n: Array, from: Array = []) -> bool:
	var k: String = _nk(n) + ((">" + _nk(from)) if not from.is_empty() else "")
	if not _cluttered.has(k):
		var ctr: Vector3 = _cell_pos(n[0], n[1])
		var zone := AABB(ctr + Vector3(-Player.RADIUS, Player.STEP_HEIGHT, -Player.RADIUS), Vector3(Player.RADIUS * 2.0, Player.STAND_HEIGHT - Player.STEP_HEIGHT, Player.RADIUS * 2.0))
		if not from.is_empty() and int(from[0]) == int(n[0]):
			var c2: Vector3 = _cell_pos(from[0], from[1])
			zone = zone.merge(AABB(c2 + Vector3(-Player.RADIUS, Player.STEP_HEIGHT, -Player.RADIUS), zone.size))
		var hit: bool = false
		for pr: Dictionary in _props:
			var ov: AABB = zone.intersection(pr["box"])
			if ov.size.x > 0.02 and ov.size.z > 0.02 and ov.size.y > 0.02:
				hit = true
				break
		_cluttered[k] = hit
	return bool(_cluttered[k])


func _index_steps() -> void:
	_step_cells.clear()
	var porch: Dictionary = layout.style.get("porch", {})
	if porch.is_empty() or layout.level_ids.is_empty():
		return
	var lv: Dictionary = layout.levels[0 if layout.levels.has(0) else layout.level_ids.front()]
	var side: int = PoiLayout.SIDES.get(str(porch.get("side", "S")), 2)
	var k: int = int(porch.get("depth", 2)) - 1
	for i: Variant in porch.get("steps", []):
		var c: Vector2i
		match side:
			2:
				c = Vector2i(int(i), int(lv["d"]) + k)
			0:
				c = Vector2i(int(i), -1 - k)
			1:
				c = Vector2i(int(lv["w"]) + k, int(i))
			_:
				c = Vector2i(-1 - k, int(i))
		_step_cells[c] = side


## Least-cost path (Dijkstra) from node `from` to the nearest of `goals` over the validator's graph
## without "out"; [] when there is none.
func _plan(from: Array, goals: Array) -> Array:
	var want: Dictionary = {}
	for g: Array in goals:
		want[_nk(g)] = true
	var dist: Dictionary = {_nk(from): 0.0}
	var prev: Dictionary = {_nk(from): null}
	var node_of: Dictionary = {_nk(from): from}
	var open: Array = [from]
	var guard: int = 0
	while not open.is_empty() and guard < 20000:
		guard += 1
		var bi: int = 0
		for i: int in open.size():
			if float(dist[_nk(open[i])]) < float(dist[_nk(open[bi])]):
				bi = i
		var cur: Array = open[bi]
		open.remove_at(bi)
		var ck: String = _nk(cur)
		if want.has(ck):
			var path: Array = [cur]
			var k: Variant = prev[ck]
			while k != null:
				path.push_front(node_of[k])
				k = prev[k]
			return path
		for n: Variant in validator._neighbors(int(cur[0]), cur[1], _keys):
			if n is String:
				continue
			var nn: Array = n
			if not validator._walkable(int(nn[0]), nn[1]):
				continue
			var nk: String = _nk(nn)
			var d: float = float(dist[ck]) + _step_cost(cur, nn)
			if not dist.has(nk) or d < float(dist[nk]):
				if not dist.has(nk):
					open.append(nn)
				dist[nk] = d
				prev[nk] = ck
				node_of[nk] = nn
	return []


func _step_cost(a: Array, b: Array) -> float:
	var cost: float = 1.0
	var ya: float = _cell_pos(a[0], a[1]).y
	var yb: float = _cell_pos(b[0], b[1]).y
	if int(a[0]) == int(b[0]) and yb - ya > Player.STEP_HEIGHT + 0.02:
		var stepped: bool = _step_cells.has(b[1]) and (b[1] as Vector2i) - (a[1] as Vector2i) == -PoiLayout.DIRS[int(_step_cells[b[1]])]
		if not stepped:
			cost += 6.0
	if _is_cluttered(b, a):
		cost += CLUTTER_COST
	# Through a window only when nothing else gets there (the route says when one is the way in).
	if int(a[0]) == int(b[0]) and (a[1] as Vector2i).distance_squared_to(b[1]) == 1:
		var e: Array = PoiLayout.side_edge(a[1], PoiLayout.DIRS.find((b[1] as Vector2i) - (a[1] as Vector2i)))
		var w: Dictionary = layout.walls.get(PoiLayout.edge_key(int(a[0]), e[0], e[1]), {})
		if not w.is_empty() and not (w["opening"] as Dictionary).is_empty() and PoiLayout.is_window(str(w["opening"]["type"])):
			cost += WINDOW_COST
	# The validator walks a stair flight's cells on the floor below it and the open well over it
	# on the floor above; the body can do neither (the flight is in the way, there is no floor).
	if int(a[0]) == int(b[0]) and (_under_flight(b) or validator._over_well(int(b[0]), b[1])):
		cost += BLOCKED_COST
	return cost


## A cell a stair flight rises over on its base level (all but its foot, where the climb starts).
func _under_flight(n: Array) -> bool:
	for s: Dictionary in layout.stairs:
		if int(s["level"]) == int(n[0]) and (s["cells"] as Array).has(n[1]) and s["cell"] != n[1]:
			return true
	return false


## Where in a cell to steer for: its middle, else the nearest of a few spots round it that no prop
## box (grown by the capsule's radius) covers at body height (a fire pole in a drop hole, a chair
## by a table).
func _free_point(li: int, c: Vector2i) -> Vector3:
	var ctr: Vector3 = _cell_pos(li, c)
	for off: Vector2 in [Vector2.ZERO, Vector2(0.3, 0), Vector2(-0.3, 0), Vector2(0, 0.3), Vector2(0, -0.3),
			Vector2(0.34, 0.34), Vector2(-0.34, 0.34), Vector2(0.34, -0.34), Vector2(-0.34, -0.34)]:
		# Not toward a wall on that side of the cell: the capsule fits its middle only.
		var walled: bool = false
		for side: int in 4:
			var d: Vector2i = PoiLayout.DIRS[side]
			if (d.x != 0 and off.x * d.x > 0.1) or (d.y != 0 and off.y * d.y > 0.1):
				var e: Array = PoiLayout.side_edge(c, side)
				var ek: String = PoiLayout.edge_key(li, e[0], e[1])
				walled = walled or layout.walls.has(ek) or layout.galleries.has(ek)
		if walled:
			continue
		var p: Vector3 = ctr + Vector3(off.x, 0.0, off.y)
		var body := AABB(p + Vector3(-Player.RADIUS, Player.STEP_HEIGHT, -Player.RADIUS), Vector3(Player.RADIUS * 2.0, Player.STAND_HEIGHT - Player.STEP_HEIGHT, Player.RADIUS * 2.0))
		var free: bool = true
		for pr: Dictionary in _props:
			if body.intersects(pr["box"]):
				free = false
				break
		if free:
			return p
	return ctr


## Walks a list of nodes, leg by leg.
func _walk_nodes(nodes: Array) -> void:
	for i: int in range(1, nodes.size()):
		await _leg(nodes[i - 1], nodes[i])
		_cur = nodes[i]


## What a step from node a to node b is, from the layout.
func _classify(a: Array, b: Array) -> Dictionary:
	var la: int = a[0]
	var lb: int = b[0]
	var ca: Vector2i = a[1]
	var cb: Vector2i = b[1]
	for s: Dictionary in layout.stairs:
		if int(s["level"]) == la and s["cell"] == ca and lb == la + 1 and s["landing"] == cb:
			return {"kind": "stairs_up", "stairs": s}
		if int(s["level"]) + 1 == la and s["landing"] == ca and lb == la - 1 and s["cell"] == cb:
			return {"kind": "stairs_down", "stairs": s}
	for l: Dictionary in layout.ladders:
		if int(l["level"]) == la and l["cell"] == ca and lb == la + 1:
			return {"kind": "ladder_up", "ladder": l}
		if int(l["level"]) + 1 == la and l.get("landing", l["cell"]) == ca and lb == la - 1:
			return {"kind": "ladder_down", "ladder": l}
	if ca == cb and lb < la:
		return {"kind": "drop_hole"}
	var d: Vector2i = cb - ca
	var side: int = PoiLayout.DIRS.find(d)
	if side < 0:
		return {"kind": "jump"}
	var e: Array = PoiLayout.side_edge(ca, side)
	var ek: String = PoiLayout.edge_key(la, e[0], e[1])
	var out: Dictionary = {"kind": "floor" if lb == la else "drop", "edge": ek}
	var wall: Dictionary = layout.walls.get(ek, layout.galleries.get(ek, {}))
	if not wall.is_empty() and not (wall["opening"] as Dictionary).is_empty():
		out["opening"] = wall["opening"]
		if lb == la:
			out["kind"] = str((wall["opening"] as Dictionary)["type"])
	return out


func _new_leg(a: Variant, b: Variant, kind: String) -> Dictionary:
	return {"from": _node_str(a), "to": _node_str(b), "kind": kind, "ok": false, "needed": [], "frames": 0, "_t0": _frames}


## One step of the route: a door opened, a doorway, a flight of stairs, a ladder, a drop.
func _leg(a: Array, b: Array) -> void:
	var cls: Dictionary = _classify(a, b)
	var kind: String = cls["kind"]
	var leg: Dictionary = _new_leg(a, b, kind)
	if cls.has("opening"):
		leg["opening"] = str((cls["opening"] as Dictionary)["id"])
	var ok: bool = true
	var end: Vector3 = _free_point(b[0], b[1])
	match kind:
		"stairs_up", "stairs_down":
			var s: Dictionary = cls["stairs"]
			var cells: Array = s["cells"]
			var pts: Array[Vector3] = []
			if kind == "stairs_up":
				for k: int in range(1, cells.size()):
					pts.append(_cell_pos(int(s["level"]), cells[k]))
			else:
				for k: int in range(cells.size() - 1, -1, -1):
					pts.append(_cell_pos(int(s["level"]), cells[k]))
			for p: Vector3 in pts:
				ok = await _go(p, false, leg)
				if not ok:
					break
			if ok:
				ok = await _go(end, true, leg)
		"ladder_up", "ladder_down":
			var l: Dictionary = cls["ladder"]
			# To the foot (or the landing above), then the ladder's interact: the only way a
			# ladder climbs (PoiPieces.Ladder moves the body to its other end).
			ok = await _go(_cell_pos(a[0], a[1]), true, leg)
			var lad: PoiPieces.Ladder = _ladder_at(l)
			if lad == null:
				ok = false
				leg["blocker"] = {"kind": "no ladder node built at %s level %d" % [l["cell"], l["level"]]}
			else:
				lad.interact(player)
				(leg["needed"] as Array).append("interact")
				await _settle(4)
				ok = _near(end, 0.8, true)
				if not ok:
					ok = await _go(end, true, leg)
			(_report["climbs"] as Array).append({"ladder": "%s L%d" % [_v2(l["cell"]), int(l["level"])], "dir": kind, "ok": ok})
		"drop_hole", "drop":
			ok = await _go(end, true, leg)
		"jump":
			ok = false
			leg["blocker"] = {"kind": "the route jumps between cells that do not touch"}
		_:
			if cls.has("opening"):
				await _open_doors(cls["opening"], leg)
				# Line up square to the opening, then through its middle: as a player does, and
				# clear of a leaf swung open beside it.
				var op: Dictionary = cls["opening"]
				var spec: Dictionary = PoiParts.OPENINGS[str(op["type"])]
				var mid: Vector3 = _helper._edge_xf(int(op["level"]), op["axis"], op["edge"], int(spec["len"])).origin
				var from: Vector3 = _cell_pos(a[0], a[1])
				mid.y = from.y
				var n := Vector3(mid.x - from.x, 0.0, mid.z - from.z)
				if str(op["axis"]) == "h":
					n = Vector3(0, 0, signf(n.z))
				else:
					n = Vector3(signf(n.x), 0, 0)
				ok = await _go(mid - n * 0.55, false, leg)
				ok = ok and await _go(mid + n * 0.1, false, leg)
				ok = ok and await _go(end, true, leg)
			else:
				ok = await _go(end, true, leg)
	_end_leg(leg, ok, end)


func _end_leg(leg: Dictionary, ok: bool, end: Vector3, blocker: Dictionary = {}) -> void:
	_release()
	leg["ok"] = ok
	leg["frames"] = _frames - int(leg["_t0"])
	leg.erase("_t0")
	if not blocker.is_empty():
		leg["blocker"] = blocker
	var kind: String = leg["kind"]
	var needed: Array = leg["needed"]
	if not ok:
		if not leg.has("blocker"):
			leg["blocker"] = _blocker()
		leg["category"] = category(kind)
		(_report["blocked"] as Array).append(leg)
		# Restart from where the leg should have ended.
		_place(end, -player.global_transform.basis.z)
	else:
		var physical: Array = needed.filter(func(n: String) -> bool: return n in ["jump", "vault", "crouch"])
		var expected_vault: bool = kind.begins_with("window") or kind in ["half", "lancet"]
		if not physical.is_empty() and not expected_vault:
			(_report["assisted"] as Array).append(leg)
	for n: String in needed:
		if n.begins_with("close_door:"):
			(_report["leaf_in_way"] as Array).append({"leaf": n.trim_prefix("close_door:"), "leg": "%s %s -> %s" % [kind, leg["from"], leg["to"]]})
	(_report["legs"] as Array).append(leg)
	if verbose:
		print("[poi_walk]   %s %s -> %s %s%s%s" % ["ok  " if ok else "FAIL", leg["from"], leg["to"], kind,
			(" needed " + ",".join(PackedStringArray(needed))) if not needed.is_empty() else "",
			(" blocker " + str(leg["blocker"])) if leg.has("blocker") else ""])
	_hits.clear()
	_shut.clear()


## What kind of place a leg kind is, for the summary: doorway (a door, arch or breach), climb
## (stairs, a ladder), window (a vault is the way), drop (a hole, a gallery gap), entrance (from the
## yard up to the first cell) or floor.
static func category(kind: String) -> String:
	if WALK_THROUGH.has(kind):
		return "doorway"
	if kind.begins_with("stairs") or kind.begins_with("ladder"):
		return "climb"
	if kind.begins_with("window") or kind in ["half", "lancet"]:
		return "window"
	if kind.begins_with("drop"):
		return "drop"
	if kind == "approach":
		return "entrance"
	return "floor"


## Opens (unlocking first, with a key or from the bolt's side) every closed leaf of a door
## opening, as the player's interact does; waits for the leaves to swing.
func _open_doors(op: Dictionary, leg: Dictionary) -> void:
	var t: String = str(op["type"])
	if not t.begins_with("door"):
		return
	var opened: bool = false
	for n: Node in inst.get_children():
		if not n is PoiPieces.Door:
			continue
		var d: PoiPieces.Door = n
		if OS.has_environment("POI_WALK_DEBUG") and d.opening_id == str(op["id"]):
			print("[poi_walk]     door %s state %s at %s, body %s in_sweep %s" % [d.op_id, d.state, d.global_position, player.global_position, _in_sweep(d, player.global_position)])
		if d.opening_id != str(op["id"]) or d.is_broken():
			continue
		if d.is_locked():
			d.interact(player)
			if d.is_locked():
				leg["note"] = "door '%s' stays %s (key %s)" % [op["id"], d.state, d.key]
				continue
		if d.state != "open" and float(d.get(&"_target")) < 0.5:
			if _in_sweep(d, player.global_position):
				await _stand_clear(d, leg)
			d.interact(player)
			opened = true
	if opened:
		(leg["needed"] as Array).append("open_door")
		await _settle(30)
		_track()


## Whether a body at `p` stands where the leaf swings (door-local +Z side, within the leaf's
## reach of its hinge): opening it there would sweep the leaf through the capsule.
func _in_sweep(d: PoiPieces.Door, p: Vector3) -> bool:
	var lp: Vector3 = d.global_transform.affine_inverse() * p
	var hinge: Vector3 = d.pivot.position
	var reach: float = d.leaf_local.origin.x * 2.0 + Player.RADIUS + 0.05
	return lp.z > -Player.RADIUS and Vector2(lp.x - hinge.x, lp.z - hinge.z).length() < reach


## Before opening a door whose leaf would swing through the body, steps where a player would stand
## to pull it open: past the leaf's free end along the wall, else straight back, else beside the
## hinge. Records "open_door_aside".
func _stand_clear(d: PoiPieces.Door, leg: Dictionary) -> void:
	var w: float = d.leaf_local.origin.x * 2.0
	var hx: float = d.pivot.position.x
	# The leaf's free end lies toward the opening's middle from its hinge.
	var toward: float = 1.0 if hx < 0.0 else -1.0
	var side: float = 1.0 if (d.global_transform.affine_inverse() * player.global_position).z >= 0.0 else -1.0
	var cands: Array[Vector3] = [Vector3(hx + toward * (w + Player.RADIUS + ASIDE_MARGIN), 0.0, side * 0.5),
		Vector3(hx, 0.0, side * (w + Player.RADIUS + ASIDE_MARGIN)), Vector3(hx - toward * (Player.RADIUS + ASIDE_MARGIN), 0.0, side * 0.5)]
	var here: Vector3 = player.global_position
	var loc: Array = _locate(here)
	var room: Array = layout.volume_of(loc[0], loc[1]) if not loc.is_empty() else []
	for c: Vector3 in cands:
		var wp: Vector3 = d.global_transform * c
		wp.y = here.y
		# Only somewhere in the room the body is in (never round through another doorway).
		var wl: Array = _locate(wp + Vector3.UP * 0.1)
		if room.is_empty() or wl.is_empty() or layout.volume_of(wl[0], wl[1]) != room:
			continue
		var reached: bool = await _go(wp, false, leg, false, 150)
		if OS.has_environment("POI_WALK_DEBUG"):
			print("[poi_walk]     aside to %s: %s (body %s)" % [wp, reached, player.global_position])
		if reached:
			if not (leg["needed"] as Array).has("open_door_aside"):
				(leg["needed"] as Array).append("open_door_aside")
			return
		await _go(here, false, leg, false, 150)


func _ladder_at(l: Dictionary) -> PoiPieces.Ladder:
	var want: Vector3 = layout.cell_center(int(l["level"]), l["cell"])
	for n: Node in inst.get_children():
		if n is PoiPieces.Ladder and (n as PoiPieces.Ladder).bottom_local.distance_to(want) < 0.05:
			return n
	return null


## After the route: every room the layout reaches that the body has not stood in, nearest first.
func _explore() -> void:
	var keys: Dictionary = _keys.duplicate()
	var reach: Dictionary = validator._reach_all(keys)
	var rooms: Array = _all_rooms()
	for r: Array in rooms:
		var rk: String = "%d:%s" % [r[0], r[1]]
		if _visited.has(rk):
			continue
		var reachable: bool = false
		for c: Vector2i in r[2]:
			if reach.has(_nk([r[0], c])):
				reachable = true
				break
		if not reachable:
			continue
		if _cur.is_empty():
			continue
		var goals: Array = []
		for c2: Vector2i in r[2]:
			goals.append([r[0], c2])
		var best: Array = _plan(_cur, goals)
		if best.size() < 2:
			continue
		if verbose:
			print("[poi_walk]  explore room %s" % rk)
		await _walk_nodes(best)


## [level, char, cells] of every room, in level then plan order.
func _all_rooms() -> Array:
	var by: Dictionary = {}
	var order: Array = []
	for li: int in layout.level_ids:
		for c: Vector2i in layout.room_cells(li):
			var k: String = "%d:%s" % [li, layout.room_at(li, c)]
			if not by.has(k):
				by[k] = [li, layout.room_at(li, c), []]
				order.append(k)
			((by[k] as Array)[2] as Array).append(c)
	var out: Array = []
	for k2: String in order:
		out.append(by[k2])
	return out


func _rooms_report() -> void:
	var keys: Dictionary = _keys.duplicate()
	var reach: Dictionary = validator._reach_all(keys)
	for r: Array in _all_rooms():
		var rk: String = "%d:%s" % [r[0], r[1]]
		if _visited.has(rk):
			continue
		var reachable: bool = false
		for c: Vector2i in r[2]:
			reachable = reachable or reach.has(_nk([r[0], c]))
		var name: String = str(layout.room_def(r[0], r[1]).get("name", layout.room_def(r[0], r[1]).get("type", "")))
		var entry: Dictionary = {"room": r[1], "level": r[0], "name": name, "cells": (r[2] as Array).size()}
		(_report["unreached" if reachable else "sealed"] as Array).append(entry)


# --- steering ----------------------------------------------------------------------------------------

## Walks the body to `t` with the move action, turning toward it every frame. When it stalls:
## open a door in the way, press Jump (the player's vault, else a jump), back off and come again,
## Jump again, then Crouch; after all of that, or TARGET_FRAMES, it gives up. What it needed goes
## in leg.needed.
func _go(t: Vector3, check_y: bool, leg: Dictionary, assist: bool = true, max_frames: int = TARGET_FRAMES) -> bool:
	var best: float = INF
	var since: int = 0
	var tries: int = 0
	var frames: int = 0
	var needed: Array = leg["needed"]
	Input.action_press(&"move_forward")
	while frames < max_frames:
		player.state.stats.stamina = 100.0
		var pos: Vector3 = player.global_position
		var to := Vector3(t.x - pos.x, 0.0, t.z - pos.z)
		var d: float = to.length()
		if d < REACH and (not check_y or absf(pos.y - t.y) < 0.45) and not player.is_vaulting():
			return true
		if d > 0.05:
			player.rotation.y = atan2(-to.x, -to.z)
		await get_tree().physics_frame
		frames += 1
		_frames += 1
		_track()
		if player.is_vaulting():
			if not needed.has("vault"):
				needed.append("vault")
			since = 0
			continue
		var d2: float = Vector2(t.x - player.global_position.x, t.z - player.global_position.z).length()
		if d2 < best - 0.03:
			best = d2
			since = 0
			continue
		since += 1
		if since < STALL_FRAMES or not player.is_on_floor():
			continue
		if not assist:
			break
		since = 0
		best = d2
		tries += 1
		# An open leaf (one this walk opened, or open as authored) in the way: shut it, as a player
		# would, and note it.
		if await _close_leaf_in_way(needed, str(leg.get("opening", ""))):
			tries -= 1
			continue
		match tries:
			1:
				if not await _open_near(leg):
					await _jump(needed)
			2:
				await _jump(needed)
			3:
				await _back_off()
			4:
				await _jump(needed)
			5:
				_crouch(true)
				if player.crouching and not needed.has("crouch"):
					needed.append("crouch")
			_:
				if OS.has_environment("POI_WALK_DEBUG"):
					print("[poi_walk]     give up at %s crouching=%s floor=%s vel=%s" % [player.global_position, player.crouching, player.is_on_floor(), player.velocity])
				break
	_release()
	return false


## When the body is pressing on an open door leaf (not one of this leg's doorway, and not shut
## before on this leg), closes it. Returns whether it did.
func _close_leaf_in_way(needed: Array, own: String) -> bool:
	for h: Dictionary in _hits.slice(maxi(0, _hits.size() - 20)):
		var o: Object = h["collider"]
		if not is_instance_valid(o) or not o is PoiPieces.Door:
			continue
		var d: PoiPieces.Door = o
		if d.state != "open" or _shut.has(d.get_instance_id()) or d.opening_id == own:
			continue
		_shut[d.get_instance_id()] = true
		d.interact(player)
		needed.append("close_door:" + d.op_id)
		_door_leaves.append({"opening": d.opening_id, "leaf": d.op_id})
		await _settle(30)
		_hits.clear()
		return true
	return false


## A closed door within reach ahead: open it (as the player would, interacting).
func _open_near(leg: Dictionary) -> bool:
	for n: Node in inst.get_children():
		if not n is PoiPieces.Door:
			continue
		var d: PoiPieces.Door = n
		if d.is_broken() or d.state == "open" or d.global_position.distance_to(player.global_position) > 1.6:
			continue
		var op: Dictionary = layout.opening(d.opening_id)
		if op.is_empty():
			continue
		await _open_doors(op, leg)
		return true
	return false


## Presses Jump as a player does: the controller reads it as just pressed on the next physics
## frame (Input.action_press inside a physics frame registers for the next one), so it is held for
## two frames. Notes whether the player's vault took it or it was a plain jump.
func _jump(needed: Array) -> void:
	Input.action_press(&"jump")
	var vaulted: bool = false
	var jumped: bool = false
	for i: int in 3:
		await get_tree().physics_frame
		_frames += 1
		vaulted = vaulted or player.is_vaulting()
		jumped = jumped or player.velocity.y > 1.0
	Input.action_release(&"jump")
	if OS.has_environment("POI_WALK_DEBUG"):
		print("[poi_walk]     jump at %s vaulted=%s jumped=%s" % [player.global_position, vaulted, jumped])
	if vaulted:
		if not needed.has("vault"):
			needed.append("vault")
	elif jumped and not needed.has("jump"):
		needed.append("jump")


## Steps back half a metre and a little sideways, then carries on (a capsule snagged on a jamb).
func _back_off() -> void:
	Input.action_release(&"move_forward")
	Input.action_press(&"move_back")
	Input.action_press(&"move_left")
	for i: int in 12:
		await get_tree().physics_frame
		_frames += 1
	Input.action_release(&"move_back")
	Input.action_release(&"move_left")
	Input.action_press(&"move_forward")


func _crouch(on: bool) -> void:
	if player.crouching == on:
		return
	player._set_crouch(on)


func _release() -> void:
	Input.action_release(&"move_forward")
	Input.action_release(&"jump")
	_crouch(false)


func _place(pos: Vector3, forward: Vector3) -> void:
	player.global_position = pos + Vector3.UP * 0.05
	if Vector2(forward.x, forward.z).length() > 0.01:
		player.rotation.y = atan2(-forward.x, -forward.z)
	player.velocity = Vector3.ZERO


func _near(t: Vector3, r: float, check_y: bool) -> bool:
	var p: Vector3 = player.global_position
	return Vector2(t.x - p.x, t.z - p.z).length() < r and (not check_y or absf(p.y - t.y) < 0.6)


## Notes the room under the body and the walls and props it is pressing against.
func _track() -> void:
	var loc: Array = _locate(player.global_position)
	if not loc.is_empty():
		var v: Array = layout.volume_of(loc[0], loc[1])
		if not v.is_empty():
			_visited["%d:%s" % [v[0], v[1]]] = true
	for i: int in player.get_slide_collision_count():
		var col: KinematicCollision3D = player.get_slide_collision(i)
		if col.get_normal().y > 0.7:
			continue
		_hits.append({"collider": col.get_collider(), "shape": col.get_collider_shape_index(), "pos": col.get_position(), "normal": col.get_normal()})
	if _hits.size() > 90:
		_hits = _hits.slice(_hits.size() - 60)


## [level, cell] of a world point (the building stands at the origin).
func _locate(p: Vector3) -> Array:
	var c := Vector2i(floori(p.x - layout.origin.x), floori(p.z - layout.origin.y))
	var li_best: int = 0
	var found: bool = false
	for li: int in layout.level_ids:
		if p.y >= layout.level_y(li) - 0.4 and layout.is_built(li, c):
			li_best = li
			found = true
	return [li_best, c] if found else []


## The collider the body pushed against most while stalled, described for the report.
func _blocker() -> Dictionary:
	if _hits.is_empty():
		return {"kind": "nothing touched (fell short, or wrong height)", "at": _v3(player.global_position)}
	var counts: Dictionary = {}
	var last: Dictionary = {}
	for h: Dictionary in _hits:
		var o: Object = h["collider"]
		if not is_instance_valid(o):
			continue
		var k: String = "%d:%d" % [o.get_instance_id(), int(h["shape"])]
		counts[k] = int(counts.get(k, 0)) + 1
		last[k] = h
	var top: String = ""
	for k2: String in counts:
		if top == "" or int(counts[k2]) > int(counts[top]):
			top = k2
	if top == "":
		return {"kind": "unknown"}
	return describe(last[top])


## A collision as {kind, node, shape, cell, level, at, ...}: a door leaf (opening, state, how far
## open), glass or boards, a container prop, an authored prop or a wall of the shell, a ledge.
func describe(h: Dictionary) -> Dictionary:
	var o: Object = h["collider"]
	var pos: Vector3 = h["pos"]
	var inside: Vector3 = pos - (h["normal"] as Vector3) * 0.04
	var loc: Array = _locate(player.global_position + Vector3.UP * 0.1)
	var li: int = int(loc[0]) if not loc.is_empty() else 0
	var cell := Vector2i(floori(inside.x - layout.origin.x), floori(inside.z - layout.origin.y))
	var out: Dictionary = {"cell": _v2(cell), "level": li, "at": _v3(pos), "shape": int(h["shape"])}
	if o is Node:
		out["node"] = str(inst.get_path_to(o as Node)) if inst.is_ancestor_of(o as Node) else str((o as Node).name)
	if o is PoiPieces.Door:
		var d: PoiPieces.Door = o
		out["kind"] = "door"
		out["opening"] = d.op_id
		out["state"] = d.state
		out["open"] = snappedf(float(d.get(&"_open_amount")), 0.01)
		return out
	if o is PoiPieces.Breakable:
		out["kind"] = (o as PoiPieces.Breakable).kind
		out["piece"] = (o as PoiPieces.Breakable).piece_id
		return out
	if o is PoiPieces.LootProp:
		var lp: PoiPieces.LootProp = o
		out["kind"] = "prop"
		out["prop"] = String(lp.prop.id) if lp.prop != null else ""
		out["pkey"] = lp.prop_key
		return out
	if o == inst.shell:
		var sh: Node = inst.shell.shape_owner_get_owner(inst.shell.shape_find_owner(int(h["shape"]))) as Node
		if sh != null:
			out["node"] = str(inst.get_path_to(sh))
			if sh is CollisionShape3D and (sh as CollisionShape3D).shape is BoxShape3D:
				out["box"] = _v3(((sh as CollisionShape3D).shape as BoxShape3D).size)
		for pr: Dictionary in _props:
			if (pr["box"] as AABB).grow(0.06).has_point(inside):
				out["kind"] = "prop"
				out["prop"] = pr["prop"]
				out["pkey"] = pr["pkey"]
				if str(pr["id"]) != "":
					out["id"] = pr["id"]
				return out
		var wall: String = _wall_near(li, Vector2(inside.x, inside.z))
		if wall != "":
			out["kind"] = "wall"
			out["edge"] = wall
			var w: Dictionary = layout.walls.get(wall, {})
			if not w.is_empty() and not (w["opening"] as Dictionary).is_empty():
				out["opening"] = str(w["opening"]["id"])
				out["opening_type"] = str(w["opening"]["type"])
			return out
		out["kind"] = "shell"
	elif o is Node and (o as Node).name == "Ground":
		out["kind"] = "ground"
	elif o is Node and String((o as Node).name).begins_with("Cue_crate"):
		out["kind"] = "route_cue_crate"
	else:
		out["kind"] = (o as Object).get_class() if o != null else "unknown"
	# How high the obstacle stands over the feet (a ledge, a sill, a step).
	var space: PhysicsDirectSpaceState3D = player.get_world_3d().direct_space_state
	var probe: Vector3 = inside - (h["normal"] as Vector3) * 0.04
	var q := PhysicsRayQueryParameters3D.create(Vector3(probe.x, player.global_position.y + 2.2, probe.z), Vector3(probe.x, player.global_position.y - 0.2, probe.z), Player.WORLD_MASK, [player.get_rid()])
	var top: Dictionary = space.intersect_ray(q)
	if not top.is_empty():
		out["rise_m"] = snappedf((top["position"] as Vector3).y - player.global_position.y, 0.01)
	return out


## The wall edge key within 15 cm of a POI-local plan point on a level ("" if none).
func _wall_near(li: int, p: Vector2) -> String:
	var lx: float = p.x - layout.origin.x
	var lz: float = p.y - layout.origin.y
	if absf(lz - roundf(lz)) < 0.15:
		var k: String = PoiLayout.edge_key(li, "h", Vector2i(floori(lx), roundi(lz)))
		if layout.walls.has(k):
			return k
	if absf(lx - roundf(lx)) < 0.15:
		var k2: String = PoiLayout.edge_key(li, "v", Vector2i(roundi(lx), floori(lz)))
		if layout.walls.has(k2):
			return k2
	return ""


# --- helpers ---------------------------------------------------------------------------------------

## World point a node stands at: a room cell's floor, the porch deck, or the pad.
func _cell_pos(li: int, c: Vector2i) -> Vector3:
	var p: Vector3 = layout.cell_center(li, c)
	if li == 0 and not layout.is_built(0, c):
		p.y = layout.floor_height if _helper._porch_cells.has(c) else 0.0
	return p


static func _nk(n: Array) -> String:
	return PoiLayout.node_key(int(n[0]), n[1])


static func _same(a: Variant, b: Variant) -> bool:
	if a is String or b is String:
		return a is String and b is String
	return int(a[0]) == int(b[0]) and a[1] == b[1]


static func _node_str(n: Variant) -> String:
	if n is String:
		return str(n)
	return "L%d(%d,%d)" % [int(n[0]), (n[1] as Vector2i).x, (n[1] as Vector2i).y]


static func _v2(c: Vector2i) -> Array:
	return [c.x, c.y]


static func _v3(v: Vector3) -> Array:
	return [snappedf(v.x, 0.01), snappedf(v.y, 0.01), snappedf(v.z, 0.01)]
