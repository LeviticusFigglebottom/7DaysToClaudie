class_name TraversalAudit
extends RefCounted
## Walks a built POI with the player's real capsule (ADR-0051): every step of the validator's route
## and every doorway, swept through the physics space, so a prop that blocks a door or stands on
## the route is found the way a player finds it: by walking into it. The validator works on a 1 m
## cell graph and never sees a prop's box, a door's swing or a stair rail in the way.
##
## The standing capsule (Player: radius 0.33, 1.75 m tall) is tested a step height off the floor,
## so thresholds and sills under a step don't count. Doors and locks count as open (the route opens
## them); windows are vaults (not walked); stairs, ladders and drops are their own moves.
## What stops a sweep is reported by what it is: a prop (by id), a container, a door's leaf
## (`kind` door_leaf: a leaf posed open into another doorway), or the building's structure.

const RADIUS: float = 0.33
const HEIGHT: float = 1.75
## Player.STEP_HEIGHT and a little: what the player steps over without noticing.
const STEP: float = 0.38 + 0.04
## The collision layers the player walks into (Player's collision_mask).
const MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 12)
## Openings crouched through (a knocked-through hole): checked with the crouched capsule.
const CROUCH_TYPES: PackedStringArray = ["breach"]
## Player.VAULT_MAX: the tallest obstacle the player vaults or mantles.
const VAULT_MAX: float = 1.3
## Player.CROUCH_HEIGHT.
const CROUCH_HEIGHT: float = 1.1
## The tallest rise a doorway may ask the player to step up without a step (Player.STEP_HEIGHT).
const STEP_RISE: float = 0.38


## Grid spacing (m) of the free-space samples: cell centres and cell edges (doorways) fall on it.
const GRID: float = 0.25


## Every blocked step of `inst` (built and in a physics space): [{kind: "route"|"doorway", level,
## cell, to, what, blocker, at, severity}], with `what` "prop:<id>", "container:<prop>", "door_leaf", "piece",
## "structure" or "unknown". `v` is the building's validator (its route paths).
##
## Each level is sampled every GRID metres for where the capsule fits (feet a step off the floor),
## and the free samples are joined into connected areas. A route step is blocked when no area
## reaches both cells; a doorway when the capsule doesn't fit on its centre line or the line's
## area doesn't reach both sides. A straight sweep between the two then names what is in the way.
## Severity is "error" for what the validator's route walks (its runs, the doorways it crosses) and
## "warn" for the other doorways, for what the player vaults, and for props authored `route_ok`
## (named "<id>+route_ok": the author put them on the route on purpose).
static func audit(inst: PoiInstance, v: PoiValidator, space: PhysicsDirectSpaceState3D) -> Array[Dictionary]:
	var l: PoiLayout = inst.layout
	var out: Array[Dictionary] = []
	var exclude: Array[RID] = _passable_bodies(inst)
	var grids: Dictionary = {}
	for li: int in l.level_ids:
		grids[li] = _free_grid(l, li, inst, space, exclude)
	var skip: Dictionary = _special_cells(l)
	var on_route: Dictionary = _route_edges(v)
	for leg: Variant in v.paths:
		for run: Array in _runs(l, leg as Array, skip):
			var first: Array = run[0]
			var last: Array = run[run.size() - 1]
			var li2: int = first[0]
			var g: Dictionary = grids[li2]
			# A run's ends are reached by getting next to them: a waypoint is often the bench or bed
			# itself, and the validator's path to a stair or a doorway is one of many. The doorways
			# themselves are checked below.
			var from_areas: Dictionary = _near_areas(g, first[1])
			var to_areas: Dictionary = _near_areas(g, last[1])
			var ok: bool = false
			for area: Variant in to_areas:
				ok = ok or from_areas.has(area)
			if not ok:
				var hit: Dictionary = _name_run(space, inst, l, run, exclude)
				# Something the player vaults (Player._try_vault) slows the way but doesn't close it.
				var top: float = _top_over_floor(space, inst, l, li2, hit, exclude)
				var vault: bool = top >= 0.3 and top <= VAULT_MAX
				if vault:
					hit["what"] = "%s (vault %.2f m)" % [hit["what"], top]
				hit.merge({"kind": "route", "level": li2, "cell": first[1], "to": last[1],
					"severity": "warn" if vault or str(hit["what"]).ends_with("+route_ok") else "error"})
				out.append(hit)
	out.append_array(_route_windows(inst, v, l, space, exclude))
	for op2: Dictionary in l.openings:
		var t: String = str(op2["type"])
		if _is_vault(t) or str(op2["state"]) in ["barricaded", "boarded"]:
			continue
		var li3: int = op2["level"]
		if not grids.has(li3):
			continue
		var g3: Dictionary = grids[li3]
		var cells: Array[Vector2i] = PoiLayout.edge_cells(str(op2["axis"]), op2["edge"])
		var along: Vector2i = Vector2i(1, 0) if str(op2["axis"]) == "h" else Vector2i(0, 1)
		for k: int in int(op2["width"]):
			var a2: Vector2i = cells[0] + along * k
			var b2: Vector2i = cells[1] + along * k
			if not (_walkable(v, li3, a2) and _walkable(v, li3, b2)) or skip.has(PoiValidator.node_key(li3, a2)) or skip.has(PoiValidator.node_key(li3, b2)):
				continue
			# The sample on the doorway's centre line, where the wall's two cells meet.
			var s: Vector2i = (a2 + b2) * 2 + Vector2i(2, 2)
			var sev: String = "error" if on_route.has(_edge_id(li3, a2, b2)) else "warn"
			var rise: float = max_rise(space, inst, _at(l, li3, b2, _cell_y(space, inst, l, li3, b2, exclude)), _at(l, li3, a2, _cell_y(space, inst, l, li3, a2, exclude)), exclude)
			if rise > STEP_RISE:
				# Up to VAULT_MAX the player climbs it with Jump (a loading dock, a hole in a wall).
				var climbable: bool = rise <= VAULT_MAX
				out.append({"kind": "doorway", "level": li3, "cell": b2, "to": a2, "opening": str(op2["id"]),
					"what": "step %.2f m%s" % [rise, " (vault)" if climbable else ""], "blocker": "-",
					"at": _at(l, li3, a2, l.level_y(li3)), "severity": "warn" if climbable else sev})
				continue
			var from2: Vector3 = _at(l, li3, b2, _cell_y(space, inst, l, li3, b2, exclude))
			var to2: Vector3 = _at(l, li3, a2, _cell_y(space, inst, l, li3, a2, exclude))
			var hit2: Dictionary = {}
			if CROUCH_TYPES.has(t):
				hit2 = sweep(space, inst, from2, to2, exclude, CROUCH_HEIGHT)
			else:
				var area2: Variant = (g3["free"] as Dictionary).get(s, null)
				if area2 == null or not (_areas(g3, a2).has(area2) and _areas(g3, b2).has(area2)):
					hit2 = _name(space, inst, from2, to2, exclude)
			if not hit2.is_empty() and not _is_closure(str(hit2["what"])):
				if str(hit2["what"]).ends_with("+route_ok"):
					sev = "warn"
				var top2: float = _top_over_floor(space, inst, l, li3, hit2, exclude)
				if top2 >= 0.3 and top2 <= VAULT_MAX:
					hit2["what"] = "%s (vault %.2f m)" % [hit2["what"], top2]
					sev = "warn"
				hit2.merge({"kind": "doorway", "level": li3, "cell": b2, "to": a2, "opening": str(op2["id"]), "severity": sev})
				out.append(hit2)
	return out


## {free: {sample: area id}} for level `li`: samples every GRID metres (Vector2i in GRID units from
## the layout origin, so cell (x, y)'s centre is (4x + 2, 4y + 2)) where the capsule fits.
static func _free_grid(l: PoiLayout, li: int, inst: Node3D, space: PhysicsDirectSpaceState3D, exclude: Array[RID]) -> Dictionary:
	var lv: Dictionary = l.levels.get(li, {})
	var pad: int = PoiValidator.YARD if li == 0 else 0
	var lo := Vector2i(-pad, -pad) * 4
	var hi := Vector2i(int(lv.get("w", 0)) + pad, int(lv.get("d", 0)) + pad) * 4
	var q: PhysicsShapeQueryParameters3D = _query(exclude)
	var lift: float = STEP + (q.shape as CapsuleShape3D).height * 0.5
	var free: Dictionary = {}
	for z: int in range(lo.y, hi.y + 1):
		for x: int in range(lo.x, hi.x + 1):
			var p: Vector3 = l.local_pos(li, Vector2(x, z) * GRID)
			p.y = floor_at(space, inst, p, exclude) + lift
			q.transform = Transform3D(Basis.IDENTITY, inst.global_transform * p)
			if space.intersect_shape(q, 1).is_empty():
				free[Vector2i(x, z)] = -1
	# Join the free samples into areas (4-neighbour flood fill).
	var next: int = 0
	for s: Vector2i in free.keys():
		if int(free[s]) >= 0:
			continue
		var stack: Array[Vector2i] = [s]
		free[s] = next
		while not stack.is_empty():
			var c: Vector2i = stack.pop_back()
			for d: Vector2i in PoiLayout.DIRS:
				var n: Vector2i = c + d
				if free.has(n) and int(free[n]) < 0:
					free[n] = next
					stack.append(n)
		next += 1
	return {"free": free}


## The floor under a cell's centre (floor_at).
static func _cell_y(space: PhysicsDirectSpaceState3D, inst: Node3D, l: PoiLayout, li: int, c: Vector2i, exclude: Array[RID]) -> float:
	return floor_at(space, inst, l.cell_center(li, c), exclude)


## The floor under a POI-local point on a level (`p.y` its floor height): the first surface a ray
## finds going down from a step above it (a porch deck, a stoop, the level's own floor), or the
## ground (0) outside where nothing is built. Starting a step up keeps tables and beds out of it.
static func floor_at(space: PhysicsDirectSpaceState3D, inst: Node3D, p: Vector3, exclude: Array[RID]) -> float:
	var q := PhysicsRayQueryParameters3D.create(inst.global_transform * (p + Vector3(0, STEP + 0.05, 0)),
		inst.global_transform * (p - Vector3(0, 1.5, 0)), MASK, exclude)
	var hit: Dictionary = space.intersect_ray(q)
	if hit.is_empty():
		return minf(p.y, 0.0)
	return (inst.global_transform.affine_inverse() * (hit["position"] as Vector3)).y


## The tallest step between floor heights sampled every 5 cm from `from` to `to` (feet positions,
## POI-local), each found by a ray down from a step above the higher floor: the step a player has to take, up or
## down (the way in is the way back out).
static func max_rise(space: PhysicsDirectSpaceState3D, inst: Node3D, from: Vector3, to: Vector3, exclude: Array[RID]) -> float:
	# From just above a step over the higher floor: anything taller is an obstacle (the sweeps' job),
	# not a step (a crate inside the door isn't a sill).
	var top: float = maxf(from.y, to.y) + STEP_RISE + 0.02
	var prev: float = NAN
	var worst: float = 0.0
	var n: int = maxi(2, int(from.distance_to(to) / 0.05))
	for i: int in n + 1:
		var p: Vector3 = from.lerp(to, float(i) / n)
		var q := PhysicsRayQueryParameters3D.create(inst.global_transform * Vector3(p.x, top, p.z), inst.global_transform * Vector3(p.x, minf(from.y, to.y) - 1.0, p.z), MASK, exclude)
		var hit: Dictionary = space.intersect_ray(q)
		# Nothing built: the ground (the audit has no terrain under the building).
		var y: float = 0.0 if hit.is_empty() else (inst.global_transform.affine_inverse() * (hit["position"] as Vector3)).y
		if y >= top - 0.01:
			# The ray started inside something taller than a step: an obstacle, not a floor.
			continue
		if not is_nan(prev):
			worst = maxf(worst, absf(y - prev))
		prev = y
	return worst


## A leg of the validator's route split into the runs walked on one level: [[level, cell, is a
## waypoint], ...] per run, broken at openings (the doorway check covers them), level changes and
## stair, ladder and hole cells.
static func _runs(l: PoiLayout, leg: Array, skip: Dictionary) -> Array:
	var runs: Array = []
	var cur: Array = []
	for i: int in leg.size():
		var n: Variant = leg[i]
		var end: bool = i == 0 or i == leg.size() - 1
		if n is String or skip.has(PoiValidator.node_key(int(n[0]), n[1])):
			if cur.size() >= 2:
				runs.append(cur)
			cur = []
			continue
		var node: Array = [int(n[0]), n[1] as Vector2i, end]
		if not cur.is_empty():
			var prev: Array = cur[cur.size() - 1]
			var d: Vector2i = (n[1] as Vector2i) - (prev[1] as Vector2i)
			var op: Dictionary = _opening_between(l, int(prev[0]), prev[1], n[1]) if int(prev[0]) == int(n[0]) else {}
			if int(prev[0]) != int(n[0]) or absi(d.x) + absi(d.y) != 1 or not op.is_empty():
				if cur.size() >= 2:
					runs.append(cur)
				cur = []
		cur.append(node)
	if cur.size() >= 2:
		runs.append(cur)
	return runs


## What stops the capsule along a run's cells, step by step (the first thing hit).
static func _name_run(space: PhysicsDirectSpaceState3D, inst: Node3D, l: PoiLayout, run: Array, exclude: Array[RID]) -> Dictionary:
	for i: int in range(1, run.size()):
		var a: Array = run[i - 1]
		var b: Array = run[i]
		var hit: Dictionary = sweep(space, inst, _at(l, a[0], a[1], _cell_y(space, inst, l, a[0], a[1], exclude)), _at(l, b[0], b[1], _cell_y(space, inst, l, b[0], b[1], exclude)), exclude)
		if not hit.is_empty():
			return hit
	return {"what": "unknown", "blocker": "-", "at": l.cell_center(int(run[0][0]), run[0][1])}


## The areas reachable from next to cell `c`: its own and its four neighbours'.
static func _near_areas(g: Dictionary, c: Vector2i) -> Dictionary:
	var out: Dictionary = _areas(g, c)
	for d: Vector2i in PoiLayout.DIRS:
		out.merge(_areas(g, c + d))
	return out


## The areas the capsule reaches inside cell `c` (its 3x3 inner samples), as a set.
static func _areas(g: Dictionary, c: Vector2i) -> Dictionary:
	var free: Dictionary = g["free"]
	var out: Dictionary = {}
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var s: Vector2i = c * 4 + Vector2i(2 + dx, 2 + dz)
			if free.has(s):
				out[free[s]] = true
	return out


## Cells the route crosses by other moves than walking: stair flights and wells, ladder cells and
## their landings, holes. Steps touching them aren't walked.
static func _special_cells(l: PoiLayout) -> Dictionary:
	var out: Dictionary = {}
	for li: int in l.level_ids:
		for c: Vector2i in l.stairwell_cells(li):
			out[PoiValidator.node_key(li, c)] = true
	for s: Dictionary in l.stairs:
		var li2: int = s["level"]
		out[PoiValidator.node_key(li2, s["cell"])] = true
		out[PoiValidator.node_key(li2 + 1, s["landing"])] = true
		for fc: Variant in s.get("cells", []):
			out[PoiValidator.node_key(li2, fc)] = true
	for ld: Dictionary in l.ladders:
		out[PoiValidator.node_key(int(ld["level"]), ld["cell"])] = true
		out[PoiValidator.node_key(int(ld["level"]) + 1, ld.get("landing", ld["cell"]))] = true
	for h: Dictionary in l.holes:
		out[PoiValidator.node_key(int(h["level"]), h["cell"])] = true
	return out


static func _query(exclude: Array[RID], height: float = HEIGHT) -> PhysicsShapeQueryParameters3D:
	var shape := CapsuleShape3D.new()
	shape.radius = RADIUS
	# Only the body above a step: a capsule from STEP to the top of the head.
	shape.height = maxf(height - STEP, RADIUS * 2.0)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.collision_mask = MASK
	q.exclude = exclude
	return q


## What a straight sweep from `from` to `to` runs into (`what` "unknown" when it runs clear: the
## way round is blocked elsewhere).
static func _name(space: PhysicsDirectSpaceState3D, inst: Node3D, from: Vector3, to: Vector3, exclude: Array[RID]) -> Dictionary:
	var hit: Dictionary = sweep(space, inst, from, to, exclude)
	return hit if not hit.is_empty() else {"what": "unknown", "blocker": "-", "at": (from + to) * 0.5}


## Sweeps the player's capsule (feet a step off the floor) from `from` to `to` (POI-local feet
## positions). Empty when clear, else {what, blocker, at} for what stopped it.
static func sweep(space: PhysicsDirectSpaceState3D, inst: Node3D, from: Vector3, to: Vector3, exclude: Array[RID], height: float = HEIGHT) -> Dictionary:
	var q: PhysicsShapeQueryParameters3D = _query(exclude, height)
	var lift := Vector3(0, STEP + (q.shape as CapsuleShape3D).height * 0.5, 0)
	var g_from: Vector3 = inst.global_transform * from + lift
	var g_to: Vector3 = inst.global_transform * to + lift
	q.transform = Transform3D(Basis.IDENTITY, g_from)
	q.motion = g_to - g_from
	# Already inside something at the start: report that instead.
	var start: Dictionary = space.get_rest_info(q) if not space.intersect_shape(q, 1).is_empty() else {}
	if start.is_empty():
		var frac: PackedFloat32Array = space.cast_motion(q)
		if frac.size() < 2 or frac[1] >= 1.0:
			return {}
		q.transform = Transform3D(Basis.IDENTITY, g_from + q.motion * frac[1])
		q.motion = Vector3.ZERO
		start = space.get_rest_info(q)
		if start.is_empty():
			return {}
	var obj: Object = instance_from_id(int(start.get("collider_id", 0)))
	return {"what": describe(obj, int(start.get("shape", 0))), "blocker": str(obj.get(&"name")) if obj != null else "?",
		"at": inst.global_transform.affine_inverse() * (start.get("point", Vector3.ZERO) as Vector3)}


## A prop that closes a doorway on purpose (tagged "door": a roll-up bay door pulled down).
static func _is_closure(what: String) -> bool:
	if not what.begins_with("prop:"):
		return false
	var pd: PropDef = Content.get_def(&"prop", StringName(what.substr(5).trim_suffix("+route_ok"))) as PropDef
	return pd != null and pd.tags.has("door")


## What a collider is: "prop:<id>" (a shape PoiBuilder tagged), "container:<prop>", "door_leaf",
## "trap:<id>" (a shotgun's chair rig), "piece" (breakables, cues) or "structure" (walls, floors, stairs, the building's shell).
static func describe(obj: Object, shape_idx: int) -> String:
	if obj is PoiPieces.LootProp:
		var lp := obj as PoiPieces.LootProp
		return "container:%s" % (str(lp.prop.id) if lp.prop != null else "?")
	if obj is PoiPieces.Door:
		return "door_leaf"
	if obj is Node and (obj as Node).get_parent() is PoiPieces.Trap:
		return "trap:%s" % str((obj as Node).get_parent().get(&"trap_id"))
	if obj is CollisionObject3D:
		var co := obj as CollisionObject3D
		var owner_id: int = co.shape_find_owner(shape_idx)
		var sh: Object = co.shape_owner_get_owner(owner_id) if owner_id >= 0 else null
		if sh != null and (sh as Node).has_meta(&"prop"):
			return "prop:%s" % str((sh as Node).get_meta(&"prop"))
		if co.get_parent() is PoiInstance and co.name != "Shell":
			return "piece"
	return "structure"


## The door leaves and lock bodies of `inst`: the route opens them, so sweeps pass through.
static func _passable_bodies(inst: Node) -> Array[RID]:
	var out: Array[RID] = []
	var stack: Array[Node] = [inst]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is PoiPieces.Door or n is PoiPieces.LockBody:
			out.append((n as CollisionObject3D).get_rid())
		stack.append_array(n.get_children())
	return out


## How high the thing a run ran into rises over the floor at the hit point (a ray down from 2.2 m
## over the floor); -1 for nothing found.
static func _top_over_floor(space: PhysicsDirectSpaceState3D, inst: Node3D, l: PoiLayout, li: int, hit: Dictionary, exclude: Array[RID]) -> float:
	if not hit.has("at") or str(hit.get("what", "")) == "unknown":
		return -1.0
	var at: Vector3 = hit["at"]
	var fy: float = l.level_y(li)
	var q := PhysicsRayQueryParameters3D.create(inst.global_transform * Vector3(at.x, fy + 2.2, at.z), inst.global_transform * Vector3(at.x, fy - 0.5, at.z), MASK, exclude)
	var r: Dictionary = space.intersect_ray(q)
	if r.is_empty():
		return -1.0
	return (inst.global_transform.affine_inverse() * (r["position"] as Vector3)).y - fy


## Every window or pony wall the validator's route climbs through: the sill must be within a vault
## (VAULT_MAX) of the highest thing the player can stand on in front of it on the way in: the ground,
## a porch, or the route cue's crates (RouteCues: one, or two stacked under a high sill), each of
## which must itself be within a vault of the ground. A crate is climbed by the same vault.
static func _route_windows(inst: PoiInstance, v: PoiValidator, l: PoiLayout, space: PhysicsDirectSpaceState3D, exclude: Array[RID]) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var seen: Dictionary = {}
	for leg: Variant in v.paths:
		var nodes: Array = leg
		for i: int in range(1, nodes.size()):
			var a: Variant = nodes[i - 1]
			var b: Variant = nodes[i]
			if not (a is Array and b is Array) or int(a[0]) != int(b[0]):
				continue
			var li: int = a[0]
			var op: Dictionary = _opening_between(l, li, a[1], b[1])
			if op.is_empty() or not _is_vault(str(op["type"])):
				continue
			var key: String = "%s:%s" % [op["id"], a[1]]
			if seen.has(key):
				continue
			seen[key] = true
			var from: Vector3 = _at(l, li, a[1], 0.0)
			var to: Vector3 = _at(l, li, b[1], 0.0)
			var mid: Vector3 = (from + to) * 0.5
			var dir: Vector3 = (to - from).normalized()
			var floor_y: float = l.level_y(li)
			# The sill: the top of what fills the opening below its glass (a ray down its middle).
			var sill: float = _ray_down(space, inst, mid + Vector3(0, floor_y + 2.0, 0), floor_y - 1.0, exclude)
			# Where the climber stands: the highest surface 0.3-0.9 m out in front of the wall.
			var stand: float = -INF
			var ground: float = INF
			# Along the opening too: a 2 m window's crate stands under its middle.
			var side := Vector3(-dir.z, 0.0, dir.x)
			for w: float in [-0.5, -0.25, 0.0, 0.25, 0.5]:
				for d: float in [0.3, 0.5, 0.7, 0.9]:
					var p: Vector3 = mid - dir * d + side * w
					var y: float = _ray_down(space, inst, p + Vector3(0, sill - 0.05, 0), floor_y - 3.0, exclude)
					stand = maxf(stand, y)
					ground = minf(ground, y)
			var rise: float = sill - stand
			var climb: float = stand - ground
			if rise > VAULT_MAX or climb > VAULT_MAX:
				out.append({"kind": "window", "level": li, "cell": a[1], "to": b[1], "opening": str(op["id"]),
					"what": "sill %.2f m over where you stand (%.2f m over the ground)" % [rise, sill - ground], "blocker": "-",
					"at": mid + Vector3(0, sill, 0), "severity": "error"})
	return out


## The height (POI-local y) of the first surface below `from` (POI-local), down to `bottom`; the
## ground (0) when nothing is built there.
static func _ray_down(space: PhysicsDirectSpaceState3D, inst: Node3D, from: Vector3, bottom: float, exclude: Array[RID]) -> float:
	var q := PhysicsRayQueryParameters3D.create(inst.global_transform * from, inst.global_transform * Vector3(from.x, bottom, from.z), MASK, exclude)
	var hit: Dictionary = space.intersect_ray(q)
	if hit.is_empty():
		return minf(0.0, from.y)
	return (inst.global_transform.affine_inverse() * (hit["position"] as Vector3)).y


## The edges the validator's route walks across, by _edge_id.
static func _route_edges(v: PoiValidator) -> Dictionary:
	var out: Dictionary = {}
	for leg: Variant in v.paths:
		var nodes: Array = leg
		for i: int in range(1, nodes.size()):
			var a: Variant = nodes[i - 1]
			var b: Variant = nodes[i]
			if a is Array and b is Array and int(a[0]) == int(b[0]):
				out[_edge_id(int(a[0]), a[1], b[1])] = true
	return out


static func _edge_id(li: int, a: Vector2i, b: Vector2i) -> String:
	var lo: Vector2i = a.min(b)
	var hi: Vector2i = a.max(b)
	return "%d:%d:%d:%d:%d" % [li, lo.x, lo.y, hi.x, hi.y]


## Openings climbed over rather than walked through: windows and the 1 m pony wall ("half").
static func _is_vault(t: String) -> bool:
	return PoiLayout.is_window(t) or t == "half"


static func _opening_between(l: PoiLayout, li: int, a: Vector2i, b: Vector2i) -> Dictionary:
	var d: Vector2i = b - a
	var side: int = PoiLayout.DIRS.find(d)
	if side < 0:
		return {}
	var e: Array = PoiLayout.side_edge(a, side)
	var wall: Dictionary = l.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
	return wall.get("opening", {}) if not wall.is_empty() else {}



static func _at(l: PoiLayout, li: int, c: Vector2i, y: float) -> Vector3:
	var p: Vector3 = l.cell_center(li, c)
	p.y = y
	return p


static func _walkable(v: PoiValidator, li: int, c: Vector2i) -> bool:
	return v.call(&"_walkable", li, c)


## One line per finding, for logs and test messages.
static func line(poi: String, f: Dictionary) -> String:
	var s: String = "%s %s %s L%d %s->%s blocked by %s (%s) at %s" % [str(f.get("severity", "warn")).to_upper(), poi, f["kind"], int(f["level"]), f["cell"], f["to"], f["what"], f["blocker"], f["at"]]
	if f.has("opening"):
		s += " opening '%s'" % f["opening"]
	return s
