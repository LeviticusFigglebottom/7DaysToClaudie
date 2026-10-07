class_name SleeperAnchors
extends RefCounted
## Seats and beds for posed POI sleepers (ADR-0022). Prop defs carry seat and bed anchors
## (PropDef.anchors: kind, prop-local pos, facing, height, lean); a sleeper authored with pose "sit"
## or "lie" lands on the nearest free anchor of its kind within reach:
##   * "sit" takes a "seat" (a chair, pew, booth, stool, couch, bench, crate): the body sits on it
##     with its feet on the floor in front (idle_sleep_seat, or idle_sleep_hunch on a backless
##     seat), or legs out on a low one (lean "low": in a bathtub, on a mattress; idle_sleep_sit);
##   * "lie" takes a "bed" (a bed, cot, bunk, mattress, sleeping bag, a couch to stretch out on).
## Without one it keeps its floor pose (slumped against a wall, lying on the floor). A sleeper may
## pin its anchor ("anchor": "<prop id>") or opt out ("anchor": "floor": it lies where it fell).
## A sleeper in the yard (TD-269) always keeps its floor pose, on the ground.
##
## The choice is a pure function of the layout (no RNG, no spawn order): every (sleeper, anchor)
## pair in reach is sorted by pinned first, distance (plus a small penalty for facing away from the
## sleeper's authored "rot"), sleeper order, anchor order, and taken greedily. An anchor holds one
## sleeper, anchors on one prop closer than `exclusive` exclude each other (a bench's two facings),
## and a prop holds sitters or one lying body, never both (a couch).
##
## Each landed sleeper also gets an exit: the free floor spot it stands on once it has got up (in
## front of a chair, out at the end of a booth, beside a bed) and the way it faces there. Exits are
## tested against room cells, walls, stairwells and the footprints of the building's other props.

## Which anchor kind each pose lands on (PropDef.ANCHOR_KINDS).
const KIND_OF_POSE: Dictionary = {"sit": "seat", "lie": "bed"}
## How far a getting-up body stays clear of other furniture (its capsule radius plus a little).
const BODY_RADIUS: float = 0.26


## Tuning: data/config/traps.json "sleepers".
static func cfg() -> Dictionary:
	return ContentDB.instance.config(&"traps").get("sleepers", {})


## Every usable seat and bed of the layout's authored props, POI-local, in a fixed order (prop list
## order, then each prop's anchors). Left out: destroyed props (knocked over, collapsed), props
## stacked on something (a crate on a crate is no seat), anchors something else stands on (the crate
## on top of it, a lamp on the mattress), and seats whose feet would go through a wall, out of the
## building or down a stair well (_usable).
## {prop, slot, prop_key, prop_id, kind, lean, level, point (seat / mattress top under the pelvis),
##  floor (y the prop stands on), yaw (radians: the way a sitter faces, head to feet for a bed),
##  xf (the prop's transform), half (its footprint half-size x/z)}
static func collect(layout: PoiLayout) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var pb: PoiBuilder = _placer(layout)
	var placed: Array = _placed(layout, pb)
	for i: int in layout.props.size():
		var p: Dictionary = layout.props[i]
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null or pd.anchors.is_empty() or float(p.get("y", 0.0)) > 0.05:
			continue
		if str(p.get("variant", layout.style.get("prop_condition", "worn"))) == "destroyed":
			continue
		var xf: Transform3D = pb._prop_xf(p, pd)
		var prop_yaw: float = atan2(xf.basis.z.x, xf.basis.z.z)
		for j: int in pd.anchors.size():
			var a: Dictionary = pd.anchors[j]
			var ap: Array = a["pos"]
			var an: Dictionary = {"prop": i, "slot": j, "prop_key": str(p["pkey"]), "prop_id": str(p.get("id", "")),
				"kind": str(a["kind"]), "lean": str(a.get("lean", "back")), "level": int(p["level"]),
				"point": xf * Vector3(float(ap[0]), float(a["height"]), float(ap[1])), "floor": xf.origin.y,
				"yaw": wrapf(prop_yaw + deg_to_rad(float(a.get("facing", 0.0))), -PI, PI), "xf": xf,
				"half": Vector2(pd.size.x, pd.size.z) * 0.5}
			if _usable(layout, placed, an):
				out.append(an)
	return out


## [prop index, its transform, its def] of every placed prop that is not hung on a wall.
static func _placed(layout: PoiLayout, pb: PoiBuilder) -> Array:
	var out: Array = []
	for i: int in layout.props.size():
		var p: Dictionary = layout.props[i]
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd != null and not pd.wall_mounted:
			out.append([i, pb._prop_xf(p, pd), pd])
	return out


## Whether a body can take anchor `a` where the builder put its prop: the bed, or the seat and the
## floor its feet go on, inside a room (not over a stair or hatch well), the feet not through a wall,
## and no other prop standing on it (flat litter does not count: papers under a sleeping bag).
static func _usable(layout: PoiLayout, placed: Array, a: Dictionary) -> bool:
	var li: int = int(a["level"])
	var pt: Vector3 = a["point"]
	var probes: Array[Vector3] = [pt]
	if str(a["kind"]) == "seat" and str(a["lean"]) != "low":
		var yaw: float = float(a["yaw"])
		probes.append(pt + Vector3(sin(yaw), 0.0, cos(yaw)) * (float(cfg().get("seat_back", 0.40)) + 0.12))
	for q: Vector3 in probes:
		var cell := Vector2i(int(floor(q.x - layout.origin.x)), int(floor(q.z - layout.origin.y)))
		if not layout.is_room(layout.room_at(li, cell)) or layout.stairwell_cells(li).has(cell):
			return false
		if _crosses_wall(layout, li, pt, q):
			return false
	for e: Array in placed:
		if int(e[0]) == int(a["prop"]) or int(layout.props[int(e[0])]["level"]) != li:
			continue
		var o: Vector3 = (e[1] as Transform3D).origin
		var size: Vector3 = (e[2] as PropDef).size
		if size.y < 0.15:
			continue
		if o.y > pt.y - 0.12 and o.y < pt.y + 0.3 and Vector2(o.x - pt.x, o.z - pt.z).length() < maxf(size.x, size.z) * 0.5 + 0.15:
			return false
	return true


## The builder's own prop placement (against-wall snapping, porch decks, y offsets), so anchors sit
## exactly where PoiBuilder put the furniture.
static func _placer(layout: PoiLayout) -> PoiBuilder:
	var pb := PoiBuilder.new()
	pb.layout = layout
	pb._porch_cells = pb._porch_cell_set()
	return pb


## Lands every sit/lie sleeper of a layout. Returns:
##   "by_sleeper": sid -> {kind, lean, level, point, floor, yaw, exit, exit_yaw, prop_key, slot}
##                 (POI-local; exit = floor spot it stands on once up, exit_yaw = its facing there),
##   "floor": [sid] sit/lie sleepers left on the floor (none in reach, or all taken),
##   "errors": [message] pinned anchors that name no prop or a prop without that kind of anchor.
static func assign(layout: PoiLayout) -> Dictionary:
	var anchors: Array[Dictionary] = collect(layout)
	var reach: float = float(cfg().get("reach", 1.6))
	var exclusive: float = float(cfg().get("exclusive", 0.45))
	var face_cost: float = float(cfg().get("facing_cost", 0.25))
	var pairs: Array = []
	var wants: Dictionary = {}
	var errors: PackedStringArray = []
	for si: int in layout.sleepers.size():
		var s: Dictionary = layout.sleepers[si]
		var kind: String = str(KIND_OF_POSE.get(str(s.get("pose", "stand")), ""))
		var pin: String = str(s.get("anchor", ""))
		if kind == "" or pin == "floor":
			continue
		var sid: String = str(s["sid"])
		# A sleeper in the yard (TD-269) keeps its floor pose on the ground: seats and beds are
		# indoors (_usable), and one just inside a wall is no seat for a body outside it.
		if layout.is_yard(int(s["level"]), s["cell"]):
			if pin != "":
				errors.append("sleeper '%s' in the yard pins anchor '%s': seats and beds are indoors; give it \"anchor\": \"floor\" or none" % [sid, pin])
			continue
		wants[sid] = true
		var spos: Vector3 = layout.local_pos(int(s["level"]), s["pos"])
		var found: bool = false
		for ai: int in anchors.size():
			var a: Dictionary = anchors[ai]
			if str(a["kind"]) != kind or int(a["level"]) != int(s["level"]):
				continue
			if pin != "" and str(a["prop_id"]) != pin:
				continue
			var d: float = Vector2(spos.x - (a["point"] as Vector3).x, spos.z - (a["point"] as Vector3).z).length()
			if d > (reach * 2.0 if pin != "" else reach):
				continue
			found = true
			if s.has("rot"):
				var want_yaw: float = deg_to_rad(float(s["rot"]))
				d += absf(angle_difference(want_yaw, float(a["yaw"]))) / PI * face_cost
			pairs.append([0 if pin != "" else 1, d, si, ai])
		if pin != "" and not found:
			errors.append("sleeper '%s' anchor '%s': no %s on a prop with that id within %.1f m" % [sid, pin, kind, reach * 2.0])
	pairs.sort_custom(func(x: Array, y: Array) -> bool:
		for k: int in 4:
			if x[k] != y[k]:
				return x[k] < y[k]
		return false)
	var taken: Dictionary = {}
	var prop_kind: Dictionary = {}
	var by_sleeper: Dictionary = {}
	for pr: Array in pairs:
		var s2: Dictionary = layout.sleepers[int(pr[2])]
		var sid2: String = str(s2["sid"])
		var ai2: int = int(pr[3])
		var a2: Dictionary = anchors[ai2]
		if by_sleeper.has(sid2) or taken.has(ai2):
			continue
		var pk: int = int(a2["prop"])
		if prop_kind.has(pk) and str(prop_kind[pk]) != str(a2["kind"]):
			continue
		var blocked: bool = false
		for t: Variant in taken.keys():
			var at: Dictionary = anchors[int(t)]
			if int(at["prop"]) == pk and (at["point"] as Vector3).distance_to(a2["point"]) < exclusive:
				blocked = true
				break
		if blocked:
			continue
		taken[ai2] = true
		prop_kind[pk] = str(a2["kind"])
		var landed: Dictionary = {"kind": a2["kind"], "lean": a2["lean"], "level": a2["level"], "point": a2["point"],
			"floor": a2["floor"], "yaw": a2["yaw"], "prop": pk, "prop_key": a2["prop_key"], "slot": a2["slot"]}
		var ex: Dictionary = exit_for(layout, a2)
		landed["exit"] = ex["pos"]
		landed["exit_yaw"] = ex["yaw"]
		by_sleeper[sid2] = landed
	var floor_list: PackedStringArray = []
	for si2: int in layout.sleepers.size():
		var sid3: String = str(layout.sleepers[si2]["sid"])
		if wants.has(sid3) and not by_sleeper.has(sid3):
			floor_list.append(sid3)
	return {"by_sleeper": by_sleeper, "floor": floor_list, "errors": errors}


## Validator messages (PoiValidator._check_dungeon_life): {"errors": [...], "warnings": [...]}.
static func check(layout: PoiLayout) -> Dictionary:
	var res: Dictionary = assign(layout)
	var warns: PackedStringArray = []
	for sid: String in res["floor"]:
		var s: Dictionary = {}
		for sl: Dictionary in layout.sleepers:
			if str(sl["sid"]) == sid:
				s = sl
		var kind: String = str(KIND_OF_POSE.get(str(s.get("pose", "")), "seat"))
		warns.append("sleeper '%s' (%s) has no free %s within %.1f m: move it onto one, add a %s, or give it \"anchor\": \"floor\"" % [
			sid, s.get("pose", ""), kind, float(cfg().get("reach", 1.6)), "chair, pew or bench" if kind == "seat" else "bed or cot"])
	return {"errors": res["errors"], "warnings": warns}


# --- Exits -----------------------------------------------------------------------------------------

## Where a body that sat or lay on `a` stands once it has got up (POI-local floor point) and the way
## it faces: {"pos": Vector3, "yaw": float}. Seats: in front where its feet were, else out to the
## back (a backless bench) or a side (a booth with its table in front). Beds and low seats: beside
## it, else past the foot. Falls back to the first candidate when none is free (physics sorts it
## out).
static func exit_for(layout: PoiLayout, a: Dictionary) -> Dictionary:
	var c: Dictionary = cfg()
	var yaw: float = float(a["yaw"])
	var fwd := Vector3(sin(yaw), 0.0, cos(yaw))
	var right := Vector3(fwd.z, 0.0, -fwd.x)
	var pt: Vector3 = a["point"]
	var base := Vector3(pt.x, float(a["floor"]), pt.z)
	# [spot, facing, standing up in place (where the feet already are: the own seat may be right
	# behind it and the room needs less clearance)]
	var cands: Array = []
	if str(a["kind"]) == "seat" and str(a["lean"]) != "low":
		cands.append([base + fwd * float(c.get("seat_back", 0.40)), yaw, true])
		if str(a["lean"]) == "forward":
			cands.append([base - fwd * 0.5, wrapf(yaw + PI, -PI, PI), false])
		var side: float = float(c.get("seat_side_step", 0.8))
		cands.append([base + fwd * 0.15 + right * side, atan2(right.x, right.z), false])
		cands.append([base + fwd * 0.15 - right * side, atan2(-right.x, -right.z), false])
	else:
		# Beds, and low seats (sat in a tub or on a mattress, legs out): out over a side, else past
		# the feet.
		var clear: float = BODY_RADIUS + 0.1
		for dir: Vector3 in [right, -right]:
			cands.append([base + dir * (_to_edge(a, dir) + clear) + fwd * 0.1, atan2(dir.x, dir.z), false])
		cands.append([base + fwd * (_to_edge(a, fwd) + clear), yaw, false])
	for cand: Array in cands:
		if free_floor(layout, int(a["level"]), base, cand[0], int(a["prop"]), bool(cand[2])):
			return {"pos": cand[0], "yaw": float(cand[1])}
	return {"pos": cands[0][0], "yaw": float(cands[0][1])}


## Distance from an anchor's point to the edge of its own prop's footprint along `dir` (POI-local).
static func _to_edge(a: Dictionary, dir: Vector3) -> float:
	var xf: Transform3D = a["xf"]
	var inv: Transform3D = xf.affine_inverse()
	var lp: Vector3 = inv * (a["point"] as Vector3)
	var ld: Vector3 = (inv.basis * dir)
	var half: Vector2 = a["half"]
	var t: float = INF
	if absf(ld.x) > 1e-4:
		t = minf(t, ((half.x if ld.x > 0.0 else -half.x) - lp.x) / ld.x)
	if absf(ld.z) > 1e-4:
		t = minf(t, ((half.y if ld.z > 0.0 else -half.y) - lp.z) / ld.z)
	return maxf(0.0, t if t != INF else 0.5)


## Whether a body can stand at `q` (POI-local, level li) having got up at `from`: a room cell with a
## floor (not a stair or hatch well), no solid wall between, clear of every other authored prop by
## BODY_RADIUS and outside its own (`own` = prop index). `in_place`: it rises where its feet are
## (in front of its seat): its own seat does not count and other furniture needs less room.
static func free_floor(layout: PoiLayout, li: int, from: Vector3, q: Vector3, own: int, in_place: bool = false) -> bool:
	var cell := Vector2i(int(floor(q.x - layout.origin.x)), int(floor(q.z - layout.origin.y)))
	if not layout.is_room(layout.room_at(li, cell)) or layout.stairwell_cells(li).has(cell):
		return false
	if _crosses_wall(layout, li, from, q):
		return false
	var pb: PoiBuilder = null
	for i: int in layout.props.size():
		var p: Dictionary = layout.props[i]
		if int(p["level"]) != li:
			continue
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null or pd.collision == "none" or pd.wall_mounted or float(p.get("y", 0.0)) >= 1.2:
			continue
		if pb == null:
			pb = _placer(layout)
		if i == own and in_place:
			continue
		var lq: Vector3 = pb._prop_xf(p, pd).affine_inverse() * q
		var margin: float = 0.02 if i == own else (0.1 if in_place else BODY_RADIUS)
		if absf(lq.x) < pd.size.x * 0.5 + margin and absf(lq.z) < pd.size.z * 0.5 + margin:
			return false
	return true


## Whether the straight step from `a` to `b` (POI-local) passes a solid wall (an edge with no
## passable opening).
static func _crosses_wall(layout: PoiLayout, li: int, a: Vector3, b: Vector3) -> bool:
	var o := Vector2(layout.origin.x, layout.origin.y)
	var prev := Vector2i(int(floor(a.x - o.x)), int(floor(a.z - o.y)))
	var steps: int = maxi(1, int(ceil(Vector2(b.x - a.x, b.z - a.z).length() / 0.1)))
	for k: int in range(1, steps + 1):
		var t: float = float(k) / float(steps)
		var p: Vector3 = a.lerp(b, t)
		var cell := Vector2i(int(floor(p.x - o.x)), int(floor(p.z - o.y)))
		if cell == prev:
			continue
		var d: Vector2i = cell - prev
		# A diagonal step crosses two edges: test both ways round the corner.
		var paths: Array = [[prev, cell]] if absi(d.x) + absi(d.y) == 1 else [[prev, prev + Vector2i(d.x, 0), cell], [prev, prev + Vector2i(0, d.y), cell]]
		var ok_any: bool = false
		for path: Array in paths:
			var ok: bool = true
			for i: int in range(1, path.size()):
				if _edge_blocked(layout, li, path[i - 1], path[i]):
					ok = false
					break
			if ok:
				ok_any = true
				break
		if not ok_any:
			return true
		prev = cell
	return false


static func _edge_blocked(layout: PoiLayout, li: int, c0: Vector2i, c1: Vector2i) -> bool:
	var d: Vector2i = c1 - c0
	var side: int = PoiLayout.DIRS.find(d)
	if side < 0:
		return true
	var e: Array = PoiLayout.side_edge(c0, side)
	var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
	if wall.is_empty():
		return false
	var op: Dictionary = wall.get("opening", {})
	if op.is_empty():
		return true
	var t: String = str(op["type"])
	return t.begins_with("window") or t == "lancet" or str(op["state"]) in ["barricaded", "boarded"]


# --- Posing ------------------------------------------------------------------------------------------

## The body transform for a sleeper on an anchor, given its visual scale (the animation offsets
## scale with the body): {"origin": Vector3, "yaw": float} in the anchor's space.
##   seat: idle_sleep_seat / _hunch have the origin on the floor under the feet and the pelvis
##         seat_back behind it on a seat seat_height high; a taller seat lifts the body (feet on a
##         stool's ring), a lower one sinks it a little (never more than max_sink).
##   low seat (lean "low": in a tub, on a mattress on the floor): idle_sleep_sit has the pelvis
##         sit_back behind the origin, legs out along the ground plane: that plane goes on the
##         surface.
##   bed:  idle_sleep_lie has the pelvis lie_back behind the origin on the ground plane: the origin
##         goes on the mattress top, toward the feet, pressed in by mattress_sink.
static func body_origin(a: Dictionary, scale: Vector3) -> Dictionary:
	var c: Dictionary = cfg()
	var yaw: float = float(a["yaw"])
	var fwd := Vector3(sin(yaw), 0.0, cos(yaw))
	var pt: Vector3 = a["point"]
	var o: Vector3
	if str(a["kind"]) == "seat" and str(a.get("lean", "back")) == "low":
		o = pt + fwd * float(c.get("sit_back", 0.30)) * scale.z
	elif str(a["kind"]) == "seat":
		var lift: float = pt.y - float(a["floor"]) - float(c.get("seat_height", 0.46)) * scale.y
		o = Vector3(pt.x, float(a["floor"]) + maxf(lift, -float(c.get("max_sink", 0.05))), pt.z) + fwd * float(c.get("seat_back", 0.40)) * scale.z
	else:
		o = pt + fwd * float(c.get("lie_back", 0.45)) * scale.z - Vector3.UP * float(c.get("mattress_sink", 0.03))
	return {"origin": o, "yaw": yaw}
