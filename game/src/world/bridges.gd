class_name BridgeBuilder
extends Node3D
## Builds the road bridges the terrain composer leaves room for (RegionTerrain.bridges: the deck
## height and the two ends of each span, where the road ramps meet it), along the road's own
## centreline (ADR-0023, TD-036):
##  * The deck is cut into ~8 m generated sections, each a straight chord of the road's curve,
##    angled to the next one and lengthened just enough that their outer edges close over the bend.
##  * Each bank gets an abutment: a concrete seat where the ground has fallen away below the
##    girders, with U-wing approach walls back to the span end retaining the fill under the road.
##  * Piers stand evenly spaced between the abutments. The river profile says which stand in the
##    water (a wall pier with cutwaters turned to the current) and how deep the bed is; the rest are
##    two-column bents on the banks.
##  * Guardrails carry a reflector on every post; there is no deck lighting (the valley has no
##    power, ADR-0023).
## Boxes stand in before `make assets`. One static body carries the deck, curbs, rails, piers and
## abutments. The layout is a pure function of the centreline and the ground (plan()), so tests can
## check it without a world.

const DECK_MODEL: String = "props/bridge_deck"
const APPROACH_MODEL: String = "props/bridge_approach"
const ABUTMENT_MODEL: String = "props/bridge_abutment"
const PIER_MODEL: String = "props/bridge_pier"
const BENT_MODEL: String = "props/bridge_bent"
## Section length and width the kit models are authored at (props_ext_street.py BRIDGE_*).
const SECTION: float = 8.0
const MODEL_WIDTH: float = 9.0
## Underside of the girders below the road surface.
const DEPTH: float = 1.28
## The abutment's seat stands where the bank has fallen this far below the girders' underside, so
## the first span clears the ground.
const SEAT_CLEARANCE: float = 0.7
## Span lengths the piers aim for (steel plate girders of this size span 20-25 m).
const TARGET_SPAN: float = 22.0
## A pier in the water turns its cutwaters to the current unless the crossing is skewed further.
const MAX_PIER_SKEW: float = deg_to_rad(35.0)
## Piers this close to the river's edge, on ground less than FLOOD_RISE above its level, stand in
## its flood channel and get cutwaters like the ones in the water.
const FLOOD_MARGIN: float = 5.0
const FLOOD_RISE: float = 1.0
## The kit's road surface sits this far above the deck height: the span ends meet the terrain's
## graded road there, and coplanar surfaces would fight.
const LIFT: float = 0.025
## How far below the road a pier or abutment reaches into the ground (the models' buried depth).
const PIER_REACH: float = 15.2
const ABUTMENT_REACH: float = 7.3
## How far the approach's wing walls reach below the road (props_ext_street.py).
const APPROACH_REACH: float = 4.6
## Shortest approach run: a shorter one would squash the kit section to a sliver.
const MIN_APPROACH: float = SECTION * 0.6

var world: Node
## Built spans: [{"from": Vector3, "to": Vector3, "width": float, "path": PackedVector3Array,
## "plan": Dictionary}] (deck-surface ends and centreline).
var spans: Array[Dictionary] = []


func setup_world(w: Node) -> void:
	world = w
	var seen: Dictionary = {}
	var terrain: TerrainManager = w.terrain
	var all: Array = []
	for rid: String in terrain.regions:
		all.append(terrain.regions[rid])
	for rid: String in terrain.coarse:
		all.append(terrain.coarse[rid])
	for rt: RegionTerrain in all:
		for b: Dictionary in rt.bridges:
			var f: Array = b["from"]
			var t: Array = b["to"]
			# The same span is recorded by every region the road passes through.
			var key: String = "%s:%d_%d" % [str(b.get("road", "")), roundi(float(f[0])), roundi(float(f[2]))]
			if seen.has(key):
				continue
			seen[key] = true
			var a := Vector3(float(f[0]), float(f[1]), float(f[2]))
			var c := Vector3(float(t[0]), float(t[1]), float(t[2]))
			var path: PackedVector3Array = deck_path(road_points(all, str(b.get("road", ""))), a, c)
			build(path, float(b.get("width", MODEL_WIDTH)))


## Every centreline point the regions recorded for road `road_id` (each records its own stretch,
## sampled at the same arc positions), without duplicates. Ordered along the road when one region
## holds it; deck_path() only needs the stretch around one span, which one region normally holds.
static func road_points(regions: Array, road_id: String) -> PackedVector3Array:
	var best := PackedVector3Array()
	for rt: RegionTerrain in regions:
		for r: Dictionary in rt.roads:
			if str(r.get("id", "")) != road_id:
				continue
			var pts := PackedVector3Array()
			for p: Array in r.get("points", []):
				pts.append(Vector3(float(p[0]), float(p[1]), float(p[2])))
			if pts.size() > best.size():
				best = pts
	return best


## The deck centreline from `a` to `b` (deck-surface span ends) along the road's points: the ends
## projected onto the polyline with every point between them, all at the deck height. The straight
## chord when the road's points don't reach the span.
static func deck_path(road: PackedVector3Array, a: Vector3, b: Vector3) -> PackedVector3Array:
	var chord := PackedVector3Array([a, Vector3(b.x, a.y, b.z)])
	if road.size() < 2:
		return chord
	var pa: Vector2 = _project(road, a)
	var pb: Vector2 = _project(road, b)
	if pa.y > 3.0 or pb.y > 3.0:
		return chord
	var forward: bool = pa.x <= pb.x
	var s0: float = minf(pa.x, pb.x)
	var s1: float = maxf(pa.x, pb.x)
	var out := PackedVector3Array()
	out.append(_point_at(road, s0))
	for i: int in range(int(floor(s0)) + 1, int(ceil(s1))):
		if float(i) > s0 + 0.05 and float(i) < s1 - 0.05:
			out.append(road[i])
	out.append(_point_at(road, s1))
	if not forward:
		out.reverse()
	for i: int in out.size():
		out[i].y = a.y
	return out


## (segment index + fraction along it, horizontal distance) of the point on `line` nearest `p`.
static func _project(line: PackedVector3Array, p: Vector3) -> Vector2:
	var best := Vector2(0.0, INF)
	for i: int in line.size() - 1:
		var a := Vector2(line[i].x, line[i].z)
		var ab := Vector2(line[i + 1].x, line[i + 1].z) - a
		var t: float = clampf((Vector2(p.x, p.z) - a).dot(ab) / maxf(ab.length_squared(), 1e-6), 0.0, 1.0)
		var d: float = (a + ab * t).distance_to(Vector2(p.x, p.z))
		if d < best.y:
			best = Vector2(float(i) + t, d)
	return best


static func _point_at(line: PackedVector3Array, f: float) -> Vector3:
	var i: int = clampi(int(floor(f)), 0, line.size() - 2)
	return line[i].lerp(line[i + 1], clampf(f - float(i), 0.0, 1.0))


## Builds one bridge along `path` (deck-surface centreline) `width` wide.
func build(path: PackedVector3Array, width: float) -> void:
	if path.size() < 2:
		return
	var ground := func(x: float, z: float) -> float: return float(world.call(&"height_at", x, z))
	var p: Dictionary = plan(path, width, ground, _river_fn())
	if (p["sections"] as Array).is_empty():
		return
	spans.append({"from": path[0], "to": path[path.size() - 1], "width": width, "path": path, "plan": p})
	var root := Node3D.new()
	root.name = "Bridge_%d_%d" % [roundi(path[0].x), roundi(path[0].z)]
	add_child(root)
	# One MultiMesh per kit model: deck and approach sections, abutments, river piers, bents.
	var by_model: Dictionary = {}
	for s: Dictionary in p["sections"]:
		_add_xf(by_model, s["model"], s["xf"])
	for a: Dictionary in p["abutments"]:
		_add_xf(by_model, ABUTMENT_MODEL, a["xf"])
	for q: Dictionary in p["piers"]:
		_add_xf(by_model, PIER_MODEL if bool(q["wet"]) else BENT_MODEL, q["xf"])
	for m: String in by_model:
		var xfs: Array[Transform3D] = []
		xfs.assign(by_model[m])
		root.add_child(_instances(ModelLibrary.mesh(m, "box") if ModelLibrary.has_model(m) else _fallback(m), xfs))
	root.add_child(_body(p, width))


static func _add_xf(by_model: Dictionary, model: String, xf: Transform3D) -> void:
	if not by_model.has(model):
		by_model[model] = []
	(by_model[model] as Array).append(xf)


## Water at a point: {"level": surface height, "flow": Vector2 downstream} or {} when dry. Read
## from the regions' river profiles (centreline, width and level every 6 m).
func _river_fn() -> Callable:
	var rivers: Array = []
	var terrain: TerrainManager = world.get(&"terrain") as TerrainManager
	if terrain != null:
		for rid: String in terrain.regions:
			for wb: Dictionary in (terrain.regions[rid] as RegionTerrain).water:
				if str(wb.get("kind", "")) == "river":
					rivers.append(wb)
	return func(x: float, z: float) -> Dictionary: return river_at(rivers, x, z, FLOOD_MARGIN)


## Water at (x, z) from river profiles ({"points": [[x, z]], "widths", "levels"}): the nearest
## centreline segment within half its width plus `margin`.
static func river_at(rivers: Array, x: float, z: float, margin: float = 0.0) -> Dictionary:
	var best: Dictionary = {}
	var best_d: float = INF
	for wb: Dictionary in rivers:
		var pts: Array = wb.get("points", [])
		var widths: Array = wb.get("widths", [])
		var levels: Array = wb.get("levels", [])
		for i: int in pts.size() - 1:
			var a := Vector2(float(pts[i][0]), float(pts[i][1]))
			var ab := Vector2(float(pts[i + 1][0]), float(pts[i + 1][1])) - a
			var t: float = clampf((Vector2(x, z) - a).dot(ab) / maxf(ab.length_squared(), 1e-6), 0.0, 1.0)
			var d: float = (a + ab * t).distance_to(Vector2(x, z))
			var half: float = lerpf(float(widths[i]), float(widths[i + 1]), t) * 0.5 + margin
			if d <= half and d < best_d:
				best_d = d
				best = {"level": lerpf(float(levels[i]), float(levels[i + 1]), t), "flow": ab.normalized()}
	return best


## Layout of a bridge along `path` (deck-surface centreline, constant height) `width` wide, over
## ground(x, z) -> height and river(x, z) -> {"level", "flow"} | {}:
## {"length": m, "seats": Vector2(s, s) (abutment faces along the path),
##  "sections": [{"model", "xf", "a", "b", "dir", "length", "ext": overhang past a and b}],
##  "abutments": [{"xf", "s"}], "piers": [{"xf", "s", "wet", "ground"}]}
static func plan(path: PackedVector3Array, width: float, ground: Callable, river: Callable) -> Dictionary:
	var cum := PackedFloat32Array([0.0])
	for i: int in range(1, path.size()):
		cum.append(cum[i - 1] + _flat(path[i] - path[i - 1]).length())
	var length: float = cum[cum.size() - 1]
	var out: Dictionary = {"length": length, "sections": [], "abutments": [], "piers": [], "seats": Vector2(0.0, length)}
	if length < 1.0:
		return out
	var deck: float = path[0].y
	# Abutment seats: walking in from each end, the first point where the bank has fallen clear of
	# the girders (never more than a third of the way across).
	var clear: float = deck - DEPTH - SEAT_CLEARANCE
	var s0: float = 0.0
	while s0 < length * 0.33 and float(_ground_at(path, cum, s0, ground)) > clear:
		s0 += 0.5
	var s1: float = length
	while s1 > length * 0.67 and float(_ground_at(path, cum, s1, ground)) > clear:
		s1 -= 0.5
	# A sliver of approach is lengthened while the bank there still holds the wing walls' footing;
	# past a cliff edge the girders reach the span end instead.
	if s0 > 0.0 and s0 < MIN_APPROACH:
		s0 = MIN_APPROACH if deck - _ground_at(path, cum, MIN_APPROACH, ground) < APPROACH_REACH else 0.0
	if s1 < length and length - s1 < MIN_APPROACH:
		s1 = length - MIN_APPROACH if deck - _ground_at(path, cum, length - MIN_APPROACH, ground) < APPROACH_REACH else length
	out["seats"] = Vector2(s0, s1)
	# Chords: approaches over the fill, girder deck between the seats.
	var chords: Array = []
	for run: Array in [[0.0, s0, APPROACH_MODEL], [s0, s1, DECK_MODEL], [s1, length, APPROACH_MODEL]]:
		var ra: float = run[0]
		var rb: float = run[1]
		if rb - ra < 0.5:
			continue
		var n: int = maxi(1, ceili((rb - ra) / SECTION - 0.15))
		for k: int in n:
			chords.append([at(path, cum, ra + (rb - ra) * k / n), at(path, cum, ra + (rb - ra) * (k + 1) / n), run[2]])
	# Each section reaches past its ends by half the width times the tangent of half the bend there,
	# so the outer edges of neighbouring sections meet.
	for k: int in chords.size():
		var a: Vector3 = chords[k][0]
		var b: Vector3 = chords[k][1]
		var dir: Vector3 = _flat(b - a).normalized()
		var ext_a: float = 0.0
		var ext_b: float = 0.0
		if k > 0:
			ext_a = _joint_overlap(_flat(chords[k - 1][1] - chords[k - 1][0]).normalized(), dir, width)
		if k < chords.size() - 1:
			ext_b = _joint_overlap(dir, _flat(chords[k + 1][1] - chords[k + 1][0]).normalized(), width)
		var len_k: float = _flat(b - a).length()
		var full: float = len_k + ext_a + ext_b
		var centre: Vector3 = (a + b) * 0.5 + dir * (ext_b - ext_a) * 0.5
		var basis := Basis(dir, Vector3.UP, dir.cross(Vector3.UP))
		(out["sections"] as Array).append({"model": chords[k][2], "a": a, "b": b, "dir": dir, "length": full,
			"ext": Vector2(ext_a, ext_b), "xf": Transform3D(basis.scaled_local(Vector3(full / SECTION, 1.0, width / MODEL_WIDTH)), centre + Vector3.UP * LIFT)})
	# Abutments face into the span from each seat.
	for e: Array in [[s0, 1.0], [s1, -1.0]]:
		var se: float = e[0]
		var p: Vector3 = at(path, cum, se)
		var d: Vector3 = tangent(path, cum, se) * float(e[1])
		var ab := Basis(d, Vector3.UP, d.cross(Vector3.UP))
		(out["abutments"] as Array).append({"s": se, "xf": Transform3D(ab.scaled_local(Vector3(1.0, 1.0, width / MODEL_WIDTH)), p)})
	# Piers evenly spaced between the seats; a pier standing in the river is a wall pier turned to
	# the current.
	var spans_n: int = maxi(1, roundi((s1 - s0) / TARGET_SPAN))
	for k: int in range(1, spans_n):
		var s: float = s0 + (s1 - s0) * k / spans_n
		var p: Vector3 = at(path, cum, s)
		var d: Vector3 = tangent(path, cum, s)
		var across: Vector3 = d.cross(Vector3.UP)
		var g: float = float(ground.call(p.x, p.z))
		var w: Dictionary = river.call(p.x, p.z) if river.is_valid() else {}
		var wet: bool = not w.is_empty() and g < float(w["level"]) + FLOOD_RISE
		var basis := Basis(d, Vector3.UP, across)
		if wet:
			var flow: Vector2 = w["flow"]
			var f := Vector3(flow.x, 0.0, flow.y).normalized()
			if f.dot(across) < 0.0:
				f = -f
			if absf(across.signed_angle_to(f, Vector3.UP)) <= MAX_PIER_SKEW:
				basis = Basis(Vector3.UP.cross(f), Vector3.UP, f)
		(out["piers"] as Array).append({"s": s, "wet": wet, "ground": g,
			"xf": Transform3D(basis.scaled_local(Vector3(1.0, 1.0, width / MODEL_WIDTH)), p)})
	return out


static func _ground_at(path: PackedVector3Array, cum: PackedFloat32Array, s: float, ground: Callable) -> float:
	var p: Vector3 = at(path, cum, s)
	return float(ground.call(p.x, p.z))


static func _flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0.0, v.z)


## Extra length at a joint between two section directions so their outer edges meet.
static func _joint_overlap(d0: Vector3, d1: Vector3, width: float) -> float:
	var bend: float = absf(d0.signed_angle_to(d1, Vector3.UP))
	return width * 0.5 * tan(bend * 0.5) + (0.02 if bend > 0.001 else 0.0)


## Point at arc length `s` along `path` (cumulative horizontal lengths `cum`).
static func at(path: PackedVector3Array, cum: PackedFloat32Array, s: float) -> Vector3:
	var i: int = clampi(cum.bsearch(s) - 1, 0, path.size() - 2)
	var seg: float = cum[i + 1] - cum[i]
	return path[i].lerp(path[i + 1], clampf((s - cum[i]) / seg, 0.0, 1.0) if seg > 1e-4 else 0.0)


## Horizontal unit direction of `path` at arc length `s`.
static func tangent(path: PackedVector3Array, cum: PackedFloat32Array, s: float) -> Vector3:
	var i: int = clampi(cum.bsearch(s) - 1, 0, path.size() - 2)
	return _flat(path[i + 1] - path[i]).normalized()


func _instances(mesh: Mesh, xfs: Array[Transform3D]) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = xfs.size()
	for i: int in xfs.size():
		mm.set_instance_transform(i, xfs[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.visibility_range_end = 900.0
	return mmi


## Deck slabs (top at the road surface), curbs and guardrails per section; a block per pier and
## abutment from its cap down into the ground.
func _body(p: Dictionary, width: float) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = 1
	body.collision_mask = 0
	body.set_meta(&"surface", "concrete")
	for s: Dictionary in p["sections"]:
		var dir: Vector3 = s["dir"]
		var side: Vector3 = dir.cross(Vector3.UP)
		var mid: Vector3 = ((s["a"] as Vector3) + (s["b"] as Vector3)) * 0.5
		var basis := Basis(dir, Vector3.UP, side)
		var l: float = s["length"]
		_add_box(body, Transform3D(basis, mid + Vector3.UP * (LIFT - 0.2)), Vector3(l, 0.4, width))
		for sg: float in [-1.0, 1.0]:
			# curb + guardrail as one wall along each edge (1.05 m above the road)
			_add_box(body, Transform3D(basis, mid + side * sg * (width * 0.5 - 0.25) + Vector3.UP * 0.45), Vector3(l, 1.1, 0.5))
	for q: Dictionary in p["piers"]:
		var xf: Transform3D = q["xf"]
		var top: float = xf.origin.y - DEPTH - 1.0
		var h: float = maxf(1.0, top - float(q["ground"]) + 1.0)
		var b := Basis(xf.basis.x.normalized(), Vector3.UP, xf.basis.z.normalized())
		_add_box(body, Transform3D(b, Vector3(xf.origin.x, top - h * 0.5, xf.origin.z)), Vector3(1.2, h, width * 0.75))
	for a: Dictionary in p["abutments"]:
		var axf: Transform3D = a["xf"]
		var ab := Basis(axf.basis.x.normalized(), Vector3.UP, axf.basis.z.normalized())
		# The stem (props_ext_street.py bridge_abutment): 1.6 m thick under the girder ends, from the
		# seat down 5.2 m.
		_add_box(body, Transform3D(ab, axf.origin - ab.x * 0.05 - Vector3.UP * (DEPTH + 0.06 + 2.6)), Vector3(1.6, 5.2, width + 0.6))
	return body


func _add_box(body: StaticBody3D, xf: Transform3D, size: Vector3) -> void:
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.transform = xf
	body.add_child(cs)


## Deck surfaces the navigation tiles add as walkable ground (tile rects in world XZ).
func nav_faces_in_rect(r: Rect2) -> PackedVector3Array:
	var out := PackedVector3Array()
	for sp: Dictionary in spans:
		var half: float = float(sp["width"]) * 0.5 - 0.5
		for s: Dictionary in (sp["plan"] as Dictionary)["sections"]:
			var dir: Vector3 = s["dir"]
			var side: Vector3 = dir.cross(Vector3.UP) * half
			var mid: Vector3 = ((s["a"] as Vector3) + (s["b"] as Vector3)) * 0.5
			var hl: Vector3 = dir * float(s["length"]) * 0.5
			var p0: Vector3 = mid - hl - side
			var p1: Vector3 = mid + hl - side
			var p2: Vector3 = mid + hl + side
			var p3: Vector3 = mid - hl + side
			var box := Rect2(Vector2(p0.x, p0.z), Vector2.ZERO).expand(Vector2(p1.x, p1.z)).expand(Vector2(p2.x, p2.z)).expand(Vector2(p3.x, p3.z))
			if box.intersects(r):
				out.append_array(PackedVector3Array([p0, p1, p2, p0, p2, p3]))
	return out


## Whether a point lies over a bridge deck (within `margin` of a section's footprint), for
## RoadMarkings, which keeps its paint off the decks.
func on_deck(p: Vector3, margin: float = 1.0) -> bool:
	for sp: Dictionary in spans:
		if on_plan_deck(sp["plan"], float(sp["width"]), p, margin):
			return true
	return false


static func on_plan_deck(plan_d: Dictionary, width: float, p: Vector3, margin: float) -> bool:
	for s: Dictionary in plan_d["sections"]:
		var dir: Vector3 = s["dir"]
		var mid: Vector3 = ((s["a"] as Vector3) + (s["b"] as Vector3)) * 0.5
		var v := Vector3(p.x - mid.x, 0.0, p.z - mid.z)
		if absf(v.dot(dir)) <= float(s["length"]) * 0.5 + margin and absf(v.dot(dir.cross(Vector3.UP))) <= width * 0.5 + margin:
			return true
	return false


# --- Stand-ins before `make assets` ---------------------------------------------------------------

func _fallback(model: String) -> Mesh:
	match model:
		DECK_MODEL, APPROACH_MODEL:
			var m := BoxMesh.new()
			m.size = Vector3(SECTION, 0.4, MODEL_WIDTH)
			return _shifted(m, Vector3(0.0, -0.2, 0.0), Color(0.42, 0.42, 0.4))
		ABUTMENT_MODEL:
			var a := BoxMesh.new()
			a.size = Vector3(1.6, ABUTMENT_REACH, MODEL_WIDTH + 0.6)
			return _shifted(a, Vector3(-0.6, -ABUTMENT_REACH * 0.5 - 0.4, 0.0), Color(0.5, 0.5, 0.48))
	var p := BoxMesh.new()
	p.size = Vector3(1.0, 14.0, MODEL_WIDTH * 0.62)
	return _shifted(p, Vector3(0.0, -DEPTH - 8.0, 0.0), Color(0.5, 0.5, 0.48))


static func _shifted(m: PrimitiveMesh, offset: Vector3, col: Color) -> Mesh:
	var st := SurfaceTool.new()
	st.create_from(m, 0)
	var arr: Array = st.commit_to_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += offset
	arr[Mesh.ARRAY_VERTEX] = v
	var out := ArrayMesh.new()
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	out.surface_set_material(0, mat)
	return out
