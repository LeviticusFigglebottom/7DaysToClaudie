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
## Severity is "error" for what the validator's route walks (its runs, the doorways it crosses),
## vaultable or not (named "(vault <m>)": the intended way should read without a climb), and
## "warn" for the other doorways and for props authored `route_ok` (named "<id>+route_ok": the
## author put them on the route on purpose).
## Then (round 4 of the owner's traversal reports): every door leaf fully open (_door_swings), the
## loot room's containers in reach (_loot_reach) and the route's rooms in the light (dark_route).
## A route step that is a floor break (a gap, a ledge: the free areas join only across a step
## the player takes) is named "floor step <m>".
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
				if str(hit["what"]) == "unknown":
					# Nothing stands in the way: the floor itself breaks (a gap, a ledge, a drop).
					var rise: float = _run_rise(space, inst, l, run, exclude)
					if rise > STEP_RISE:
						var jump: bool = rise <= VAULT_MAX
						hit["what"] = "floor step %.2f m%s" % [rise, " (vault)" if jump else ""]
						hit.merge({"kind": "route", "level": li2, "cell": first[1], "to": last[1],
							"severity": "error"})
						out.append(hit)
						continue
				# Something the player vaults (Player._try_vault) is named with its height. On the intended
				# route it is still an error: the way should read without a climb (an author's route_ok
				# says the climb is the point).
				var top: float = _top_over_floor(space, inst, l, li2, hit, exclude)
				var vault: bool = top >= 0.3 and top <= VAULT_MAX
				if vault:
					hit["what"] = "%s (vault %.2f m)" % [hit["what"], top]
				hit.merge({"kind": "route", "level": li2, "cell": first[1], "to": last[1],
					"severity": "warn" if str(hit["what"]).contains("+route_ok") else "error"})
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
				hit2.merge({"kind": "doorway", "level": li3, "cell": b2, "to": a2, "opening": str(op2["id"]), "severity": sev})
				out.append(hit2)
	out.append_array(_door_swings(inst, l, space, on_route))
	out.append_array(_ladders(inst, v, l, grids, space, exclude))
	out.append_array(_loot_reach(inst, v, l, grids, space))
	out.append_array(dark_route(l, v))
	return out


## Ladders (ADR-0051 round 5): the player takes one walking at its rails from the foot, or from the landing
## upstairs walking across the hatch toward them (Player._grab_ladder). So the spot in front of the
## rails must hold the standing capsule, the landing must too, and a hatch ladder's landing must
## lie across the hatch from the rails: from a landing beside it, walking into the hatch is walking
## past the rails, and the way down is a hole (the hatchery catwalk's). Errors on a ladder the
## validator's route climbs, warnings elsewhere.
static func _ladders(inst: PoiInstance, v: PoiValidator, l: PoiLayout, grids: Dictionary, space: PhysicsDirectSpaceState3D, exclude: Array[RID]) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	# Climbs on the route: "<level below>:<foot>:<landing>".
	var used: Dictionary = {}
	for leg: Variant in v.paths:
		var nodes: Array = leg
		for i: int in range(1, nodes.size()):
			var a: Variant = nodes[i - 1]
			var b: Variant = nodes[i]
			if not (a is Array and b is Array) or absi(int(a[0]) - int(b[0])) != 1:
				continue
			var lo: Array = a if int(a[0]) < int(b[0]) else b
			var hi: Array = b if int(a[0]) < int(b[0]) else a
			used["%d:%s:%s" % [int(lo[0]), lo[1], hi[1]]] = true
			if lo == b:
				used["down:%d:%s:%s" % [int(lo[0]), lo[1], hi[1]]] = true
	for ld: Dictionary in l.ladders:
		var li: int = ld["level"]
		var c: Vector2i = ld["cell"]
		var land: Vector2i = ld.get("landing", c)
		var d: Vector2i = PoiLayout.DIRS[int(ld["side"])]
		var sev: String = "error" if used.has("%d:%s:%s" % [li, c, land]) else "warn"
		# The foot: somewhere the body stands facing the rails within their reach (the cell's middle,
		# 0.38 m out from them, or 0.25 m further back: Player.LADDER_REACH is 0.75 m).
		var g: Dictionary = grids.get(li, {})
		var mid := Vector2i(c.x * 4 + 2, c.y * 4 + 2)
		var stand := Vector2i(c.x * 4 + 2 - d.x, c.y * 4 + 2 - d.y)
		if not g.is_empty() and not (g["free"] as Dictionary).has(stand) and not (g["free"] as Dictionary).has(mid):
			var y0: float = _cell_y(space, inst, l, li, c, exclude)
			var hit: Dictionary = _name(space, inst, _at(l, li, c - d, y0), _at(l, li, c, y0) - Vector3(d.x, 0, d.y) * 0.25, exclude)
			hit["what"] = "foot of the ladder: %s" % hit["what"]
			hit.merge({"kind": "ladder", "level": li, "cell": c, "to": land, "severity": sev}, true)
			out.append(hit)
		if not bool(ld["hatch"]):
			continue
		if land != c - d and land != c:
			# Up it, the climber still steps off sideways onto the landing: an error only where
			# the route climbs down.
			var sev2: String = "error" if used.has("down:%d:%s:%s" % [li, c, land]) else "warn"
			out.append({"kind": "ladder", "level": li, "cell": c, "to": land, "severity": sev2, "blocker": "-", "at": l.cell_center(li + 1, land),
				"what": "landing beside the hatch, not across it from the rails: from there the way down is a hole"})
		var g2: Dictionary = grids.get(li + 1, {})
		if not g2.is_empty() and land != c and not (g2["free"] as Dictionary).has(Vector2i(land.x * 4 + 2, land.y * 4 + 2)):
			var y1: float = l.level_y(li + 1)
			var hit2: Dictionary = _name(space, inst, _at(l, li + 1, c, y1), _at(l, li + 1, land, y1), exclude)
			hit2["what"] = "ladder landing: %s" % hit2["what"]
			hit2.merge({"kind": "ladder", "level": li, "cell": c, "to": land, "severity": sev}, true)
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
	var floor_y: Dictionary = {}
	for z: int in range(lo.y, hi.y + 1):
		for x: int in range(lo.x, hi.x + 1):
			var p: Vector3 = l.local_pos(li, Vector2(x, z) * GRID)
			var fy: float = floor_at(space, inst, p, exclude)
			p.y = fy + lift
			q.transform = Transform3D(Basis.IDENTITY, inst.global_transform * p)
			if space.intersect_shape(q, 1).is_empty():
				free[Vector2i(x, z)] = -1
				floor_y[Vector2i(x, z)] = fy
	# Join the free samples into areas (4-neighbour flood fill). Two samples join only where the
	# floor between them is a step the player takes (STEP_RISE): a gap in a deck, a missing bridge
	# board or a loft's edge over a drop finds the ground far below, which is free space too, and
	# used to join the deck's area across the gap.
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
				if free.has(n) and int(free[n]) < 0 and absf(float(floor_y[n]) - float(floor_y[c])) <= STEP_RISE:
					free[n] = next
					stack.append(n)
		next += 1
	return {"free": free, "y": floor_y}


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


## The tallest step (up or down) along a run's cells, centre to centre (max_rise).
static func _run_rise(space: PhysicsDirectSpaceState3D, inst: Node3D, l: PoiLayout, run: Array, exclude: Array[RID]) -> float:
	var worst: float = 0.0
	for i: int in range(1, run.size()):
		var a: Array = run[i - 1]
		var b: Array = run[i]
		var fa: Vector3 = _at(l, a[0], a[1], _cell_y(space, inst, l, a[0], a[1], exclude))
		var fb: Vector3 = _at(l, b[0], b[1], _cell_y(space, inst, l, b[0], b[1], exclude))
		worst = maxf(worst, maxf(absf(fa.y - fb.y), max_rise(space, inst, fa, fb, exclude)))
	return worst


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


## How far (m) from its hinge a fully open leaf may touch something: the jamb and the wall it is
## hung on. Past it, anything the leaf meets is a door swinging into a wall, a stair or a prop.
const SWING_HINGE: float = 0.25


## Every door leaf that, fully open, stands in something: a prop or container (it clips through
## it, or the prop sits in the clear space the door needs), a stair rail or flight, a wall. An error
## on a doorway the route crosses (the player opens it there), a warning elsewhere and for floor
## clutter under SWING_LOW. The leaf's first SWING_HINGE m (its own jamb) doesn't count.
static func _door_swings(inst: PoiInstance, l: PoiLayout, space: PhysicsDirectSpaceState3D, on_route: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var exclude: Array[RID] = _passable_bodies(inst)
	var stack: Array[Node] = [inst]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		stack.append_array(n.get_children())
		if not n is PoiPieces.Door:
			continue
		var d := n as PoiPieces.Door
		if d.state == "broken" or d.leaf_shape == null or not d.leaf_shape.shape is BoxShape3D:
			continue
		var op: Dictionary = l.opening(d.opening_id)
		if op.is_empty() or str(op["state"]) == "barricaded":
			continue
		var size: Vector3 = (d.leaf_shape.shape as BoxShape3D).size
		var leaf_xf: Transform3D = d.global_transform * d.open_leaf_transform()
		# Furniture first (SWING_LOW up to the head clearance); then the floor strip under it,
		# where a rag pile or a body the leaf sweeps over is a warning only.
		var hit: Dictionary = _leaf_hit(space, leaf_xf, size, SWING_LOW, size.y - 0.06, exclude)
		var low: bool = hit.is_empty()
		if low:
			hit = _leaf_hit(space, leaf_xf, size, 0.03, SWING_LOW, exclude)
		var obj: Object = null
		var what: String = ""
		if hit.is_empty():
			# Nothing to hit over a stair's well, or beside a flight: a leaf standing out over the
			# steps closes them (poi_walk shuts it to get past): an error wherever the door is.
			var flights: Dictionary = _flight_cells(l, int(op["level"]))
			for t: float in [0.5, 0.95]:
				var p: Vector3 = inst.global_transform.affine_inverse() * (leaf_xf * Vector3((t - 0.5) * size.x, 0.0, 0.0))
				var o: Vector3 = l.local_pos(int(op["level"]), Vector2.ZERO)
				if flights.has(Vector2i(floori(p.x - o.x), floori(p.z - o.z))):
					what = "stairs"
					low = false
			if what == "":
				continue
		else:
			obj = hit.get("collider")
			what = describe(obj, int(hit.get("shape", 0)))
		# A stopped leaf (PoiBuilder.DOORSTOP) lies flat against the side wall it stops on.
		if _is_closure(what) or (what == "structure" and d.max_open < 1.0):
			continue
		var li: int = op["level"]
		var edges: Array = PoiLayout.opening_edges(op)
		var route: bool = false
		for pair: Array in edges:
			route = route or on_route.has(_edge_id(li, pair[0], pair[1]))
		out.append({"kind": "swing", "level": li, "cell": edges[0][0], "to": edges[0][1], "opening": "%s (leaf %s)" % [op["id"], d.op_id],
			"what": what + (" (low)" if low else ""), "blocker": str(obj.get(&"name")) if obj != null else "?",
			"at": inst.global_transform.affine_inverse() * leaf_xf.origin, "severity": "error" if (route and not low) or what == "stairs" else "warn"})
	return out


## Level `li`'s stair cells: the flights rising from it (foot included) and the wells over the
## ones rising to it.
static func _flight_cells(l: PoiLayout, li: int) -> Dictionary:
	var out: Dictionary = l.stairwell_cells(li)
	for s: Dictionary in l.stairs:
		if int(s["level"]) == li:
			out[s["cell"]] = true
			for fc: Variant in s.get("cells", []):
				out[fc] = true
	return out


## Below this (m over the floor) what an open leaf sweeps over is floor clutter: a warning.
const SWING_LOW: float = 0.3


## The first thing (intersect_shape's result) in a thin slab of an open leaf (`leaf_xf` the leaf
## box's centre, `size` its size) from `y0` to `y1` over its bottom edge, past SWING_HINGE.
static func _leaf_hit(space: PhysicsDirectSpaceState3D, leaf_xf: Transform3D, size: Vector3, y0: float, y1: float, exclude: Array[RID]) -> Dictionary:
	var box := BoxShape3D.new()
	box.size = Vector3(maxf(size.x - SWING_HINGE - 0.02, 0.1), maxf(y1 - y0, 0.05), 0.01)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = box
	q.collision_mask = MASK
	q.exclude = exclude
	q.transform = leaf_xf * Transform3D(Basis.IDENTITY, Vector3((SWING_HINGE - 0.02) * 0.5, -size.y * 0.5 + (y0 + y1) * 0.5, 0.0))
	var hits: Array[Dictionary] = space.intersect_shape(q, 1)
	return hits[0] if not hits.is_empty() else {}


## The interaction ray (player.json interact_range) from the eyes (EYE m over the feet): a
## container is searched where it reaches the box from a spot the player stands on.
const LOOT_REACH: float = 2.6
const EYE: float = 1.55


## The loot room's containers the player can search from the areas the route walks on that level:
## a free spot whose eyes see the box within LOOT_REACH (the first thing a ray from them meets is
## the container, not a wall or a prop). None: an error (the route's prize is behind a bed, a
## counter, a wall or a gap). A single container out of reach while another is in it: a warning.
static func _loot_reach(inst: PoiInstance, v: PoiValidator, l: PoiLayout, grids: Dictionary, space: PhysicsDirectSpaceState3D) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if l.loot_room.is_empty():
		return out
	var li: int = int(l.loot_room.get("level", 0))
	if not grids.has(li):
		return out
	var g: Dictionary = grids[li]
	var free: Dictionary = g["free"]
	var route_areas: Dictionary = {}
	for leg: Variant in v.paths:
		for n: Variant in leg:
			if n is Array and int(n[0]) == li:
				route_areas.merge(_near_areas(g, n[1]))
	var to_local: Transform3D = inst.global_transform.affine_inverse()
	var exclude: Array[RID] = _passable_bodies(inst)
	var far: Array[String] = []
	var total: int = 0
	var first_at := Vector3.ZERO
	for c: Node in inst.get_children():
		if not c is PoiPieces.LootProp or not (c as PoiPieces.LootProp).bonus:
			continue
		var lp := c as PoiPieces.LootProp
		total += 1
		var rect := Rect2()
		var top: float = -INF
		var bottom: float = INF
		var started: bool = false
		for cs: Node in lp.get_children():
			if not cs is CollisionShape3D or not (cs as CollisionShape3D).shape is BoxShape3D:
				continue
			var half: Vector3 = ((cs as CollisionShape3D).shape as BoxShape3D).size * 0.5
			var xf: Transform3D = to_local * lp.global_transform * (cs as CollisionShape3D).transform
			for k: int in 8:
				var p: Vector3 = xf * Vector3(half.x * (1 if k & 1 else -1), half.y * (1 if k & 2 else -1), half.z * (1 if k & 4 else -1))
				top = maxf(top, p.y)
				bottom = minf(bottom, p.y)
				if not started:
					rect = Rect2(Vector2(p.x, p.z), Vector2.ZERO)
					started = true
				else:
					rect = rect.expand(Vector2(p.x, p.z))
		if not started:
			continue
		var reach: bool = false
		var aim_y: float = maxf(top - 0.05, bottom + 0.05)
		for s: Vector2i in free:
			if not route_areas.has(free[s]):
				continue
			var sp: Vector3 = l.local_pos(li, Vector2(s) * GRID)
			var pt := Vector2(sp.x, sp.z)
			# Its top, at the middle and part way in from the nearest side of its (level) bounds: a
			# turned box doesn't fill the corners of those.
			var nearest := Vector2(clampf(pt.x, rect.position.x, rect.end.x), clampf(pt.y, rect.position.y, rect.end.y))
			var eye := Vector3(pt.x, float((g["y"] as Dictionary)[s]) + EYE, pt.y)
			for aim2: Vector2 in [nearest.lerp(rect.get_center(), 0.4), rect.get_center()]:
				var aim := Vector3(aim2.x, aim_y, aim2.y)
				if eye.distance_to(aim) > LOOT_REACH:
					continue
				var q := PhysicsRayQueryParameters3D.create(inst.global_transform * eye, inst.global_transform * aim, MASK, exclude)
				var hit: Dictionary = space.intersect_ray(q)
				reach = reach or (not hit.is_empty() and hit["collider"] == lp)
			if reach:
				break
		if not reach:
			far.append(lp.prop_key)
			first_at = Vector3(rect.get_center().x, l.level_y(li), rect.get_center().y)
	if far.is_empty():
		return out
	var o: Vector3 = l.local_pos(li, Vector2.ZERO)
	var c0 := Vector2i(floori(first_at.x - o.x), floori(first_at.z - o.z))
	out.append({"kind": "loot", "level": li, "cell": c0, "to": c0, "what": "out of reach: %s (%d of %d loot room containers)" % [", ".join(far), far.size(), total],
		"blocker": "-", "at": first_at, "severity": "error" if far.size() == total else "warn"})
	return out


## How far past its range (x) a light still shows a route cell the way: shapes, a doorway.
const LIGHT_REACH: float = 1.5


## Route cells in pitch dark by day: in a room (with the rooms open to it) with no outside opening
## and no burning light (an authored light, a lit prop) within LIGHT_REACH of its range. The player
## still has a lighter, but a dark room the route has to search reads as a dead end. One finding
## per such room (its first dark route cell): a warning, except in the loot room, whose light must
## also be kept ("keep": true; else style.lights_on puts it out in some runs): an error.
## Pure layout: no physics.
static func dark_route(l: PoiLayout, v: PoiValidator) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if str((l.style.get("roof", {}) as Dictionary).get("type", "gable")) == "none":
		return out
	# Spaces: room volumes joined where nothing walls them apart (open_to, a gallery, an open
	# arch or a breach).
	var parent: Dictionary = {}
	for li: int in l.level_ids:
		var lv: Dictionary = l.levels[li]
		for y: int in int(lv["d"]):
			for x: int in int(lv["w"]):
				var c := Vector2i(x, y)
				if not l.is_built(li, c):
					continue
				for d: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
					var n: Vector2i = c + d
					if not l.is_built(li, n):
						continue
					var e: Array = PoiLayout.side_edge(c, PoiLayout.DIRS.find(d))
					var w: Dictionary = l.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
					var op: Dictionary = w.get("opening", {}) if not w.is_empty() else {}
					if w.is_empty() or str(op.get("type", "")) in ["open", "breach"]:
						_union(parent, _space_key(l, li, c), _space_key(l, li, n))
	var daylit: Dictionary = {}
	for op2: Dictionary in l.openings:
		var li2: int = op2["level"]
		for pair: Array in PoiLayout.opening_edges(op2):
			var a: bool = l.is_built(li2, pair[0])
			var b: bool = l.is_built(li2, pair[1])
			if a != b:
				daylit[_find(parent, _space_key(l, li2, pair[0] if a else pair[1]))] = true
	# One doorway on from a daylit room: an arch, a hole, a door standing open or one the route
	# opens on its way through lets that room's light in (not a stair: a cellar stays dark).
	var crossed: Dictionary = _route_edges(v)
	var spill: Dictionary = {}
	for op3: Dictionary in l.openings:
		var li4: int = op3["level"]
		var t3: String = str(op3["type"])
		if _is_vault(t3) or str(op3["state"]) in ["barricaded", "boarded"]:
			continue
		for pair2: Array in PoiLayout.opening_edges(op3):
			if not (l.is_built(li4, pair2[0]) and l.is_built(li4, pair2[1])):
				continue
			var opened: bool = not t3.begins_with("door") or str(op3["state"]) in ["open", "broken", "missing"] or crossed.has(_edge_id(li4, pair2[0], pair2[1]))
			if not opened:
				continue
			var sa: String = _find(parent, _space_key(l, li4, pair2[0]))
			var sb: String = _find(parent, _space_key(l, li4, pair2[1]))
			if daylit.has(sa) != daylit.has(sb):
				spill[sb if daylit.has(sa) else sa] = true
	daylit.merge(spill)
	# Lights: [space, layout-local xz, range, kept]. Per run a light burns with style.lights_on
	# (PoiDressing) unless it is kept ("keep": true).
	var all_on: bool = float(l.style.get("lights_on", PoiDressing.LIGHTS_ON)) >= 1.0
	var lights: Array = []
	for d2: Variant in l.lights:
		if d2 is Dictionary:
			var pl: Dictionary = l._placed(d2)
			lights.append([_find(parent, _space_key(l, int(pl["level"]), pl["cell"])), pl["pos"], float((d2 as Dictionary).get("range", 6.0)),
				all_on or bool((d2 as Dictionary).get("keep", false))])
	for p: Dictionary in l.props:
		if not bool(p.get("lit", false)):
			continue
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		var lt: Dictionary = pd.light_for(str(p.get("variant", l.style.get("prop_condition", "worn")))) if pd != null else {}
		if not lt.is_empty():
			lights.append([_find(parent, _space_key(l, int(p["level"]), p["cell"])), p["pos"], float(lt.get("range", 3.0)),
				all_on or bool(p.get("keep", false))])
	var seen: Dictionary = {}
	var lr: String = "%d:%s" % [int(l.loot_room.get("level", 0)), str(l.loot_room.get("room", ""))]
	for leg: Variant in v.paths:
		for n2: Variant in leg:
			if not n2 is Array or not l.is_built(int(n2[0]), n2[1]):
				continue
			var li3: int = n2[0]
			var c3: Vector2i = n2[1]
			var sp: String = _find(parent, _space_key(l, li3, c3))
			var loot: bool = _space_key(l, li3, c3) == lr
			if daylit.has(sp) or seen.has(sp + ("/loot" if loot else "")):
				continue
			var lit: bool = false
			var kept: bool = false
			for lt2: Array in lights:
				if str(lt2[0]) == sp and (lt2[1] as Vector2).distance_to(Vector2(c3) + Vector2(0.5, 0.5)) <= float(lt2[2]) * LIGHT_REACH:
					lit = true
					kept = kept or bool(lt2[3])
			# The loot room's light must burn every run: the prize is searched, not felt for.
			if kept or (lit and not loot):
				continue
			seen[sp + ("/loot" if loot else "")] = true
			var vol: Array = l.volume_of(li3, c3)
			var room: Dictionary = l.room_def(int(vol[0]), str(vol[1]))
			var why: String = "its only light can go out (keep one)" if lit else "no window, door out or light"
			out.append({"kind": "dark", "level": li3, "cell": c3, "to": c3, "what": "pitch dark: %s in %s%s" % [
				why, str(room.get("name", vol[1])), " (the loot room)" if loot else ""], "blocker": "-",
				"at": l.cell_center(li3, c3), "severity": "error" if loot else "warn"})
	return out


## A room volume's key: "level:char" of the room a cell belongs to (a tall room's base).
static func _space_key(l: PoiLayout, li: int, c: Vector2i) -> String:
	var vol: Array = l.volume_of(li, c)
	return "%d:%s" % [int(vol[0]), str(vol[1])] if not vol.is_empty() else "%d:." % li


static func _find(parent: Dictionary, k: String) -> String:
	while parent.has(k) and str(parent[k]) != k:
		k = str(parent[k])
	return k


static func _union(parent: Dictionary, a: String, b: String) -> void:
	var ra: String = _find(parent, a)
	var rb: String = _find(parent, b)
	if ra != rb:
		parent[ra] = rb


## One line per finding, for logs and test messages.
static func line(poi: String, f: Dictionary) -> String:
	var s: String = "%s %s %s L%d %s->%s blocked by %s (%s) at %s" % [str(f.get("severity", "warn")).to_upper(), poi, f["kind"], int(f["level"]), f["cell"], f["to"], f["what"], f["blocker"], f["at"]]
	if f.has("opening"):
		s += " opening '%s'" % f["opening"]
	return s
