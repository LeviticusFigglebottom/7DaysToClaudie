class_name RoofBuilder
extends RefCounted
## Procedural roofs over a POI's massing (ADR-0019 surfaces, ADR-0021 planning). RoofPlanner splits
## the building's tops into wings; build_plan roofs each one and joins them:
##  * gable (ridge along x or z, overhanging eaves and rakes), hip and pyramid (four slopes), shed
##    (a lean-to against a taller wall), spire (an octagonal broach spire with a cross on a tower),
##    flat (a tar-and-gravel membrane behind a parapet in the exterior finish) or none;
##  * every slope is a plane over a convex polygon. Where two wings overlap (a leg running into its
##    main, a roof under a tower, an annex under a taller wall) each face is cut away wherever the
##    other wing's roof stands higher inside that wing's walls, which leaves valleys between cross
##    gables and roofs that stop at the walls they meet;
##  * trims follow what is left: painted fascia under the eaves and rake boards up the gable ends,
##    capped ridges and hips, half-round gutters (unless "gutters": false);
##  * gable and shed ends are kit-wall faces in the exterior finish, flush with the wall below
##    (they also close the storey band under them). Under an open roof (a room with "open_roof") the
##    roof shows weathered boards, rafters, a ridge beam, wall plates and collar ties, the gable ends
##    show the room's wall finish inside, and walls between it and closed rooms rise to the roof.
## Coverings come from game/data/materials/roofs.json: UVs in metres, U along the eave, V up the
## slope, so courses stay level and nothing repeats at a seam.
## Returns [geometry nodes..., collision Shape3D...] for the builder.

const THICK: float = 0.14
## Fascia board along the eaves and up the rakes (height, thickness).
const FASCIA := Vector2(0.2, 0.035)
const MAT_DIR: String = "res://assets/generated/materials/%s.tres"
## Seen from inside an open roof: the boards under the covering, and the timbers.
const DECK_MAT: String = "wood_weathered"
const TIMBER_MAT: String = "wood_raw"
const RAFTER_STEP: float = 0.6
const EPS: float = 0.002


## One planar roof face: h(x, z) = a x + b z + c over a convex XZ polygon, cut into the convex
## pieces other wings leave of it.
class Face:
	extends RefCounted
	var poly := PackedVector2Array()
	var pieces: Array = []
	var a: float = 0.0
	var b: float = 0.0
	var c: float = 0.0
	## Texture U axis (along the eave) and where V = 0 (the eave's height).
	var u_dir := Vector2.RIGHT
	var eave_h: float = 0.0
	var pitch: float = 0.0
	var wing: int = 0
	var mat: String = ""
	var open: bool = false
	## Trim lines: [p0: Vector2, p1: Vector2, tag: "eave" | "rake" | "ridge" | "hip"].
	var lines: Array = []

	func h(p: Vector2) -> float:
		return a * p.x + b * p.y + c

	func at(p: Vector2) -> Vector3:
		return Vector3(p.x, h(p), p.y)

	func normal() -> Vector3:
		return Vector3(-a, 1.0, -b).normalized()


# --- entry points ------------------------------------------------------------------------------

## One roof over one rectangle (tests and simple callers): a single-wing plan.
static func build(kind: String, rect: Rect2, y: float, spec: Dictionary) -> Array:
	if kind == "none":
		return []
	var w := RoofPlanner.Wing.new()
	w.type = kind
	w.cells = Rect2i(Vector2i(rect.position.round()), Vector2i(rect.size.round()))
	w.span = w.cells
	w.y = y
	w.spec = spec
	w.pitch = float(spec.get("pitch", 32.0))
	w.overhang = float(spec.get("overhang", 0.45))
	w.axis = str(spec.get("axis", "x" if rect.size.x >= rect.size.y else "z"))
	return build_plan([w], Vector2.ZERO, {"exterior": str(spec.get("exterior", "siding_white")), "decay": float(spec.get("decay", 0.4))})


## Roofs for a planned building. `origin`: the plan's offset in POI-local metres. `ctx`:
## {exterior, decay, finishes: {"L:c:r": interior wall finish index of open-roof cells},
##  walls: [[a: Vector2, b: Vector2, y0, finish index]] partitions to raise under open roofs}.
static func build_plan(wings: Array, origin: Vector2, ctx: Dictionary) -> Array:
	var job := Job.new(wings, origin, ctx)
	job.step()
	return job.out


## A roof plan built in stages (ADR-0038, TD-107: a big building's roof was one ~40 ms streaming
## step): step() runs its stages one item (a wing, a face, a material...) at a time until a
## deadline, in the same order as build_plan does at once, so the roof is the same either way.
## `out` holds the result once step() returns true.
class Job:
	extends RefCounted
	const STAGES: int = 12
	var wings: Array
	var origin: Vector2
	var ctx: Dictionary
	var out: Array = []
	var faces: Array[RoofBuilder.Face] = []
	var feet: Array[Rect2] = []
	var tops: Array[float] = []
	var by_mat: Dictionary = {}
	var collide := PackedVector3Array()
	var under := SurfaceTool.new()
	var kit: Dictionary = {}
	var stage: int = 0
	var i: int = 0

	func _init(p_wings: Array, p_origin: Vector2, p_ctx: Dictionary) -> void:
		wings = p_wings
		origin = p_origin
		ctx = p_ctx
		for w: RoofPlanner.Wing in wings:
			feet.append(w.rect_m(origin, w.span))
			tops.append(w.y + w.rise())

	## Runs items until `deadline` (Time.get_ticks_usec(); 0 = none) has passed, at least one;
	## true once the roof is done.
	func step(deadline: int = 0) -> bool:
		while stage < STAGES:
			if _item():
				stage += 1
				i = 0
			else:
				i += 1
			if deadline > 0 and Time.get_ticks_usec() >= deadline:
				break
		return stage >= STAGES

	## Frees the nodes made so far (a build given up half way).
	func free_nodes() -> void:
		for item: Variant in out:
			if item is Node and is_instance_valid(item):
				(item as Node).free()
		out = []

	## One item of the current stage (index i); true once the stage is through.
	func _item() -> bool:
		match stage:
			0:  # each wing's faces
				if i >= wings.size():
					return true
				var w: RoofPlanner.Wing = wings[i]
				match w.type:
					"gable":
						faces.append_array(RoofBuilder._gable_faces(w, origin, i))
					"hip", "pyramid":
						faces.append_array(RoofBuilder._hip_faces(w, origin, i))
					"shed":
						faces.append_array(RoofBuilder._shed_faces(w, origin, i))
					"flat":
						faces.append(RoofBuilder._flat_face(w, origin, i))
			1:  # each face cut where other wings stand higher (_clip)
				if i == 0:
					for f: RoofBuilder.Face in faces:
						f.pieces = [f.poly]
				if i >= faces.size():
					return true
				RoofBuilder._clip_face(faces[i], faces, feet)
			2:  # each face into its covering's mesh
				if i >= faces.size():
					return true
				var f2: RoofBuilder.Face = faces[i]
				if not by_mat.has(f2.mat):
					var st := SurfaceTool.new()
					st.begin(Mesh.PRIMITIVE_TRIANGLES)
					by_mat[f2.mat] = st
				RoofBuilder._emit_face(by_mat[f2.mat], f2, collide)
			3:  # undersides: boards (the sheathing), seen from an open room and from under the eaves
				# and rakes. The covering's own back read as a black hole under every overhang.
				if i == 0:
					under.begin(Mesh.PRIMITIVE_TRIANGLES)
				if i >= faces.size():
					return true
				RoofBuilder._emit_underside(under, faces[i])
			4:  # each covering's mesh
				if i >= by_mat.size():
					return true
				var mat_id: String = by_mat.keys()[i]
				out.append(RoofBuilder._mesh_node("Roof" if i == 0 else "Roof%d" % i, (by_mat[mat_id] as SurfaceTool).commit(), RoofBuilder._cover_material(mat_id, wings)))
			5:
				if not faces.is_empty():
					out.append(RoofBuilder._mesh_node("RoofDeck", under.commit(), RoofBuilder._material(RoofBuilder.DECK_MAT, "#6f6559")))
				return true
			6:
				out.append(RoofBuilder._trims(faces, wings))
				return true
			7:  # each wing's gable ends, parapets or spire
				if i >= wings.size():
					return true
				var w2: RoofPlanner.Wing = wings[i]
				if w2.type in ["gable", "shed"]:
					RoofBuilder._ends(w2, origin, wings, feet, tops, i, ctx, kit, collide)
				elif w2.type == "flat":
					RoofBuilder._parapets(w2, origin, wings, ctx, kit)
				elif w2.type == "spire":
					out.append_array(RoofBuilder._spire(w2, origin, collide))
			8:
				var timbers: MeshInstance3D = RoofBuilder._timbers(faces, wings, origin)
				if timbers != null:
					out.append(timbers)
				return true
			9:
				RoofBuilder._partitions(faces, ctx, kit)
				return true
			10:  # each kit-wall batch (gable ends, parapets, partitions)
				if i >= kit.size():
					return true
				var k: Dictionary = kit[kit.keys()[i]]
				out.append(RoofBuilder._kit_instance(str(k["name"]), (k["st"] as SurfaceTool).commit(), k["custom"], k["xf"]))
			_:
				if not collide.is_empty():
					var shape := ConcavePolygonShape3D.new()
					shape.backface_collision = true
					shape.set_faces(collide)
					out.append(shape)
				return true
		return false


# --- faces per roof type -----------------------------------------------------------------------

static func _face(w: RoofPlanner.Wing, i: int, poly: PackedVector2Array, a: float, b: float, c: float, u_dir: Vector2, eave_h: float) -> Face:
	var f := Face.new()
	f.poly = poly
	f.a = a
	f.b = b
	f.c = c
	f.u_dir = u_dir
	f.eave_h = eave_h
	f.pitch = deg_to_rad(w.pitch)
	f.wing = i
	f.mat = str(w.spec.get("material", "roof_shingle"))
	f.open = w.open
	return f


static func _rect_poly(x0: float, z0: float, x1: float, z1: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(x0, z0), Vector2(x1, z0), Vector2(x1, z1), Vector2(x0, z1)])


## Two slopes meeting at a ridge along the wing's axis. Rakes overhang only at exposed ends.
static func _gable_faces(w: RoofPlanner.Wing, origin: Vector2, i: int) -> Array[Face]:
	var r: Rect2 = w.rect_m(origin, w.span)
	var ov: float = w.overhang
	var t: float = tan(deg_to_rad(w.pitch))
	var out: Array[Face] = []
	var e0: float = ov if w.ends[0] else 0.0
	var e1: float = ov if w.ends[1] else 0.0
	if w.axis == "x":
		var xa: float = r.position.x - e0
		var xb: float = r.end.x + e1
		var zm: float = r.get_center().y
		var z0: float = r.position.y
		var z1: float = r.end.y
		var n := _face(w, i, _rect_poly(xa, z0 - ov, xb, zm), 0.0, t, w.y - z0 * t, Vector2.RIGHT, w.y - ov * t)
		n.lines = [[Vector2(xa, z0 - ov), Vector2(xb, z0 - ov), "eave"], [Vector2(xa, zm), Vector2(xb, zm), "ridge"]]
		var s := _face(w, i, _rect_poly(xa, zm, xb, z1 + ov), 0.0, -t, w.y + z1 * t, Vector2.RIGHT, w.y - ov * t)
		s.lines = [[Vector2(xa, z1 + ov), Vector2(xb, z1 + ov), "eave"], [Vector2(xa, zm), Vector2(xb, zm), "ridge"]]
		if w.ends[0]:
			n.lines.append([Vector2(xa, z0 - ov), Vector2(xa, zm), "rake"])
			s.lines.append([Vector2(xa, zm), Vector2(xa, z1 + ov), "rake"])
		if w.ends[1]:
			n.lines.append([Vector2(xb, z0 - ov), Vector2(xb, zm), "rake"])
			s.lines.append([Vector2(xb, zm), Vector2(xb, z1 + ov), "rake"])
		out = [n, s]
	else:
		var za: float = r.position.y - e0
		var zb: float = r.end.y + e1
		var xm: float = r.get_center().x
		var x0: float = r.position.x
		var x1: float = r.end.x
		var wf := _face(w, i, _rect_poly(x0 - ov, za, xm, zb), t, 0.0, w.y - x0 * t, Vector2.DOWN, w.y - ov * t)
		wf.lines = [[Vector2(x0 - ov, za), Vector2(x0 - ov, zb), "eave"], [Vector2(xm, za), Vector2(xm, zb), "ridge"]]
		var ef := _face(w, i, _rect_poly(xm, za, x1 + ov, zb), -t, 0.0, w.y + x1 * t, Vector2.DOWN, w.y - ov * t)
		ef.lines = [[Vector2(x1 + ov, za), Vector2(x1 + ov, zb), "eave"], [Vector2(xm, za), Vector2(xm, zb), "ridge"]]
		if w.ends[0]:
			wf.lines.append([Vector2(x0 - ov, za), Vector2(xm, za), "rake"])
			ef.lines.append([Vector2(xm, za), Vector2(x1 + ov, za), "rake"])
		if w.ends[1]:
			wf.lines.append([Vector2(x0 - ov, zb), Vector2(xm, zb), "rake"])
			ef.lines.append([Vector2(xm, zb), Vector2(x1 + ov, zb), "rake"])
		out = [wf, ef]
	return out


## Four slopes from eaves all round (a pyramid when the wing is square).
static func _hip_faces(w: RoofPlanner.Wing, origin: Vector2, i: int) -> Array[Face]:
	var r: Rect2 = w.rect_m(origin, w.span).grow(w.overhang)
	var t: float = tan(deg_to_rad(w.pitch))
	var ye: float = w.y - w.overhang * t
	var x0: float = r.position.x
	var x1: float = r.end.x
	var z0: float = r.position.y
	var z1: float = r.end.y
	var along_x: bool = r.size.x >= r.size.y
	var out: Array[Face] = []
	if along_x:
		var hd: float = r.size.y * 0.5
		var zm: float = r.get_center().y
		var ra := Vector2(x0 + hd, zm)
		var rb := Vector2(x1 - hd, zm)
		var nf := _face(w, i, PackedVector2Array([Vector2(x0, z0), Vector2(x1, z0), rb, ra]), 0.0, t, ye - z0 * t, Vector2.RIGHT, ye)
		var sf := _face(w, i, PackedVector2Array([Vector2(x1, z1), Vector2(x0, z1), ra, rb]), 0.0, -t, ye + z1 * t, Vector2.RIGHT, ye)
		var wf := _face(w, i, PackedVector2Array([Vector2(x0, z1), Vector2(x0, z0), ra]), t, 0.0, ye - x0 * t, Vector2.DOWN, ye)
		var ef := _face(w, i, PackedVector2Array([Vector2(x1, z0), Vector2(x1, z1), rb]), -t, 0.0, ye + x1 * t, Vector2.DOWN, ye)
		nf.lines = [[Vector2(x0, z0), Vector2(x1, z0), "eave"], [ra, rb, "ridge"], [Vector2(x0, z0), ra, "hip"], [Vector2(x1, z0), rb, "hip"]]
		sf.lines = [[Vector2(x0, z1), Vector2(x1, z1), "eave"], [ra, rb, "ridge"], [Vector2(x0, z1), ra, "hip"], [Vector2(x1, z1), rb, "hip"]]
		wf.lines = [[Vector2(x0, z0), Vector2(x0, z1), "eave"], [Vector2(x0, z0), ra, "hip"], [Vector2(x0, z1), ra, "hip"]]
		ef.lines = [[Vector2(x1, z0), Vector2(x1, z1), "eave"], [Vector2(x1, z0), rb, "hip"], [Vector2(x1, z1), rb, "hip"]]
		out = [nf, sf, wf, ef]
	else:
		var hw: float = r.size.x * 0.5
		var xm: float = r.get_center().x
		var ra2 := Vector2(xm, z0 + hw)
		var rb2 := Vector2(xm, z1 - hw)
		var wf2 := _face(w, i, PackedVector2Array([Vector2(x0, z1), Vector2(x0, z0), ra2, rb2]), t, 0.0, ye - x0 * t, Vector2.DOWN, ye)
		var ef2 := _face(w, i, PackedVector2Array([Vector2(x1, z0), Vector2(x1, z1), rb2, ra2]), -t, 0.0, ye + x1 * t, Vector2.DOWN, ye)
		var nf2 := _face(w, i, PackedVector2Array([Vector2(x0, z0), Vector2(x1, z0), ra2]), 0.0, t, ye - z0 * t, Vector2.RIGHT, ye)
		var sf2 := _face(w, i, PackedVector2Array([Vector2(x1, z1), Vector2(x0, z1), rb2]), 0.0, -t, ye + z1 * t, Vector2.RIGHT, ye)
		wf2.lines = [[Vector2(x0, z0), Vector2(x0, z1), "eave"], [ra2, rb2, "ridge"], [Vector2(x0, z0), ra2, "hip"], [Vector2(x0, z1), rb2, "hip"]]
		ef2.lines = [[Vector2(x1, z0), Vector2(x1, z1), "eave"], [ra2, rb2, "ridge"], [Vector2(x1, z0), ra2, "hip"], [Vector2(x1, z1), rb2, "hip"]]
		nf2.lines = [[Vector2(x0, z0), Vector2(x1, z0), "eave"], [Vector2(x0, z0), ra2, "hip"], [Vector2(x1, z0), ra2, "hip"]]
		sf2.lines = [[Vector2(x0, z1), Vector2(x1, z1), "eave"], [Vector2(x0, z1), rb2, "hip"], [Vector2(x1, z1), rb2, "hip"]]
		out = [wf2, ef2, nf2, sf2]
	return out


## One slope falling away from the taller wall toward `slope`; no overhang on the wall side.
static func _shed_faces(w: RoofPlanner.Wing, origin: Vector2, i: int) -> Array[Face]:
	var r: Rect2 = w.rect_m(origin, w.span)
	var ov: float = w.overhang
	var t: float = tan(deg_to_rad(w.pitch))
	var e0: float = ov if w.ends[0] else 0.0
	var e1: float = ov if w.ends[1] else 0.0
	var f: Face
	match w.slope:
		2:
			# Low side south (+z): high at z0.
			f = _face(w, i, _rect_poly(r.position.x - e0, r.position.y, r.end.x + e1, r.end.y + ov), 0.0, -t, w.y + r.end.y * t, Vector2.RIGHT, w.y - ov * t)
			f.lines = [[Vector2(r.position.x - e0, r.end.y + ov), Vector2(r.end.x + e1, r.end.y + ov), "eave"]]
			if w.ends[0]:
				f.lines.append([Vector2(r.position.x - e0, r.position.y), Vector2(r.position.x - e0, r.end.y + ov), "rake"])
			if w.ends[1]:
				f.lines.append([Vector2(r.end.x + e1, r.position.y), Vector2(r.end.x + e1, r.end.y + ov), "rake"])
		0:
			f = _face(w, i, _rect_poly(r.position.x - e0, r.position.y - ov, r.end.x + e1, r.end.y), 0.0, t, w.y - r.position.y * t, Vector2.RIGHT, w.y - ov * t)
			f.lines = [[Vector2(r.position.x - e0, r.position.y - ov), Vector2(r.end.x + e1, r.position.y - ov), "eave"]]
			if w.ends[0]:
				f.lines.append([Vector2(r.position.x - e0, r.position.y - ov), Vector2(r.position.x - e0, r.end.y), "rake"])
			if w.ends[1]:
				f.lines.append([Vector2(r.end.x + e1, r.position.y - ov), Vector2(r.end.x + e1, r.end.y), "rake"])
		1:
			f = _face(w, i, _rect_poly(r.position.x, r.position.y - e0, r.end.x + ov, r.end.y + e1), -t, 0.0, w.y + r.end.x * t, Vector2.DOWN, w.y - ov * t)
			f.lines = [[Vector2(r.end.x + ov, r.position.y - e0), Vector2(r.end.x + ov, r.end.y + e1), "eave"]]
			if w.ends[0]:
				f.lines.append([Vector2(r.position.x, r.position.y - e0), Vector2(r.end.x + ov, r.position.y - e0), "rake"])
			if w.ends[1]:
				f.lines.append([Vector2(r.position.x, r.end.y + e1), Vector2(r.end.x + ov, r.end.y + e1), "rake"])
		_:
			f = _face(w, i, _rect_poly(r.position.x - ov, r.position.y - e0, r.end.x, r.end.y + e1), t, 0.0, w.y - r.position.x * t, Vector2.DOWN, w.y - ov * t)
			f.lines = [[Vector2(r.position.x - ov, r.position.y - e0), Vector2(r.position.x - ov, r.end.y + e1), "eave"]]
			if w.ends[0]:
				f.lines.append([Vector2(r.position.x - ov, r.position.y - e0), Vector2(r.end.x, r.position.y - e0), "rake"])
			if w.ends[1]:
				f.lines.append([Vector2(r.position.x - ov, r.end.y + e1), Vector2(r.end.x, r.end.y + e1), "rake"])
	return [f]


## A flat roof's membrane, 0.25 m above the wall top and 0.15 m past the walls.
static func _flat_face(w: RoofPlanner.Wing, origin: Vector2, i: int) -> Face:
	var r: Rect2 = w.rect_m(origin, w.span).grow(0.15)
	var f := _face(w, i, _rect_poly(r.position.x, r.position.y, r.end.x, r.end.y), 0.0, 0.0, w.y + 0.25, Vector2.RIGHT, w.y + 0.25)
	f.pitch = 0.0
	f.mat = str(w.spec.get("flat_material", "roof_tar"))
	return f


# --- joining wings ---------------------------------------------------------------------------

## Cuts every face wherever another wing's roof stands higher inside that wing's walls (its roof
## span): valleys between cross gables, roofs stopped at the walls of a taller part or a tower.
static func _clip(faces: Array[Face], feet: Array[Rect2]) -> void:
	for f: Face in faces:
		f.pieces = [f.poly]
	for f2: Face in faces:
		_clip_face(f2, faces, feet)


## One face of _clip (it reads only the other faces' uncut polygons, so faces cut one at a time
## come out the same).
static func _clip_face(f2: Face, faces: Array[Face], feet: Array[Rect2]) -> void:
	for g: Face in faces:
		if g.wing == f2.wing:
			continue
		var region: PackedVector2Array = clip_rect(g.poly, feet[g.wing])
		if region.size() < 3:
			continue
		region = clip_half(region, g.a - f2.a, g.b - f2.b, g.c - f2.c - EPS)
		if region.size() < 3 or area(region) < 1e-5:
			continue
		var next: Array = []
		for piece: PackedVector2Array in f2.pieces:
			next.append_array(subtract(piece, region))
		f2.pieces = next


# --- 2D convex polygon helpers -------------------------------------------------------------------

## The part of a convex polygon where a x + b y + c >= 0 (Sutherland-Hodgman).
static func clip_half(poly: PackedVector2Array, a: float, b: float, c: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n: int = poly.size()
	for k: int in n:
		var p: Vector2 = poly[k]
		var q: Vector2 = poly[(k + 1) % n]
		var dp: float = a * p.x + b * p.y + c
		var dq: float = a * q.x + b * q.y + c
		if dp >= 0.0:
			out.append(p)
		if (dp >= 0.0) != (dq >= 0.0):
			out.append(p.lerp(q, dp / (dp - dq)))
	var clean := PackedVector2Array()
	for p2: Vector2 in out:
		if clean.is_empty() or clean[clean.size() - 1].distance_to(p2) > 1e-5:
			clean.append(p2)
	if clean.size() > 1 and clean[0].distance_to(clean[clean.size() - 1]) < 1e-5:
		clean.remove_at(clean.size() - 1)
	return clean


static func clip_rect(poly: PackedVector2Array, r: Rect2) -> PackedVector2Array:
	var p: PackedVector2Array = clip_half(poly, 1.0, 0.0, -r.position.x)
	p = clip_half(p, -1.0, 0.0, r.end.x)
	p = clip_half(p, 0.0, 1.0, -r.position.y)
	return clip_half(p, 0.0, -1.0, r.end.y)


static func area(poly: PackedVector2Array) -> float:
	var s: float = 0.0
	for k: int in poly.size():
		var p: Vector2 = poly[k]
		var q: Vector2 = poly[(k + 1) % poly.size()]
		s += p.x * q.y - q.x * p.y
	return absf(s) * 0.5


static func centroid(poly: PackedVector2Array) -> Vector2:
	var c := Vector2.ZERO
	for p: Vector2 in poly:
		c += p
	return c / float(maxi(1, poly.size()))


## A convex polygon minus a convex cut: the convex pieces left (each outside one edge of the cut).
static func subtract(poly: PackedVector2Array, cut: PackedVector2Array) -> Array:
	var pieces: Array = []
	var rest: PackedVector2Array = poly
	var cen: Vector2 = centroid(cut)
	var n: int = cut.size()
	for k: int in n:
		var p0: Vector2 = cut[k]
		var d: Vector2 = cut[(k + 1) % n] - p0
		var nrm := Vector2(-d.y, d.x)
		if nrm.dot(cen - p0) < 0.0:
			nrm = -nrm
		var c: float = -nrm.dot(p0)
		var outside: PackedVector2Array = clip_half(rest, -nrm.x, -nrm.y, -c)
		if outside.size() >= 3 and area(outside) > 1e-5:
			pieces.append(outside)
		rest = clip_half(rest, nrm.x, nrm.y, c)
		if rest.size() < 3 or area(rest) < 1e-7:
			return pieces
	return pieces


static func point_in(poly: PackedVector2Array, p: Vector2) -> bool:
	var n: int = poly.size()
	if n < 3:
		return false
	var sign_: float = 0.0
	for k: int in n:
		var a: Vector2 = poly[k]
		var b: Vector2 = poly[(k + 1) % n]
		var cr: float = (b - a).cross(p - a)
		if absf(cr) < 1e-6:
			continue
		if sign_ == 0.0:
			sign_ = signf(cr)
		elif signf(cr) != sign_:
			return false
	return true


## Height of the roof's top surface over a point (-INF where no face covers it).
static func height_at(faces: Array, p: Vector2) -> float:
	var best: float = -INF
	for f: Face in faces:
		for piece: PackedVector2Array in f.pieces:
			if point_in(piece, p):
				best = maxf(best, f.h(p))
	return best


# --- meshes --------------------------------------------------------------------------------------

static func _emit_face(st: SurfaceTool, f: Face, collide: PackedVector3Array) -> void:
	var n: Vector3 = f.normal()
	var sin_p: float = maxf(sin(f.pitch), 0.05)
	for piece: PackedVector2Array in f.pieces:
		for k: int in range(1, piece.size() - 1):
			for p: Vector2 in [piece[0], piece[k], piece[k + 1]]:
				var v: Vector3 = f.at(p)
				st.set_normal(n)
				if f.pitch > 0.001:
					st.set_uv(Vector2(p.dot(f.u_dir), (v.y - f.eave_h) / sin_p))
				else:
					st.set_uv(Vector2(p.x, p.y))
				st.add_vertex(v)
				collide.append(v)


## The face's back, THICK below it: the sheathing boards, seen from an open room, an attic or from
## under the eaves and rakes.
static func _emit_underside(st: SurfaceTool, f: Face) -> void:
	var n: Vector3 = f.normal()
	var drop: Vector3 = -n * THICK
	for piece: PackedVector2Array in f.pieces:
		for k: int in range(1, piece.size() - 1):
			for p: Vector2 in [piece[0], piece[k + 1], piece[k]]:
				var v: Vector3 = f.at(p) + drop
				st.set_normal(-n)
				st.set_uv(Vector2(p.dot(f.u_dir), p.dot(f.u_dir.orthogonal()) * 4.0))
				st.add_vertex(v)


static func _mesh_node(node_name: String, mesh: ArrayMesh, mat: Material) -> MeshInstance3D:
	if mesh.get_surface_count() > 0:
		mesh.surface_set_material(0, mat)
	var mi := MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = mesh
	return mi


static func _cover_material(mat_id: String, wings: Array) -> Material:
	var color: String = "#3b3633"
	for w: RoofPlanner.Wing in wings:
		if str(w.spec.get("material", "roof_shingle")) == mat_id:
			color = str(w.spec.get("color", color))
		elif str(w.spec.get("flat_material", "roof_tar")) == mat_id:
			color = str(w.spec.get("flat_color", "#2f2e2c"))
	return _material(mat_id, color)


static func _material(id: String, fallback: String) -> Material:
	var path: String = MAT_DIR % id
	if ResourceLoader.exists(path):
		var m: Material = load(path)
		if m is BaseMaterial3D:
			(m as BaseMaterial3D).cull_mode = BaseMaterial3D.CULL_DISABLED
		return m
	var sm := StandardMaterial3D.new()
	sm.albedo_color = Color.html(fallback)
	sm.roughness = 0.92
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	return sm


# --- trims ---------------------------------------------------------------------------------------

## Fascia and gutters along what is left of each eave, rake boards up exposed gable ends, caps
## folded over ridges and hips.
static func _trims(faces: Array[Face], wings: Array) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var gt := SurfaceTool.new()
	gt.begin(Mesh.PRIMITIVE_TRIANGLES)
	var caps := SurfaceTool.new()
	caps.begin(Mesh.PRIMITIVE_TRIANGLES)
	var gutters: int = 0
	var capped: int = 0
	for f: Face in faces:
		if f.pitch <= 0.001:
			continue
		var w: RoofPlanner.Wing = wings[f.wing]
		var n: Vector3 = f.normal()
		for piece: PackedVector2Array in f.pieces:
			var cen: Vector2 = centroid(piece)
			for k: int in piece.size():
				var p: Vector2 = piece[k]
				var q: Vector2 = piece[(k + 1) % piece.size()]
				if p.distance_to(q) < 0.05:
					continue
				var tag: String = _line_tag(f, p, q)
				if tag == "":
					continue
				var a: Vector3 = f.at(p)
				var b: Vector3 = f.at(q)
				var mid: Vector2 = (p + q) * 0.5
				var out2: Vector2 = (mid - cen)
				var along2: Vector2 = (q - p).normalized()
				out2 = (out2 - along2 * out2.dot(along2)).normalized()
				var out3 := Vector3(out2.x, 0.0, out2.y)
				match tag:
					"eave":
						_board(st, a, b, out3, FASCIA.x, FASCIA.y)
						if bool(w.spec.get("gutters", true)):
							_gutter(gt, a + out3 * (FASCIA.y + 0.06) - Vector3.UP * 0.05, b + out3 * (FASCIA.y + 0.06) - Vector3.UP * 0.05, out3)
							gutters += 1
					"rake":
						_board(st, a, b, out3, FASCIA.x * 0.8, FASCIA.y)
					"ridge", "hip":
						var down: Vector3 = (f.at(cen) - (a + b) * 0.5)
						var fold: Vector3 = (b - a).normalized()
						down = (down - fold * down.dot(fold)).normalized()
						var lift: Vector3 = n * 0.035
						var wide: float = 0.17
						for v: Vector3 in [a + lift, b + lift, b + down * wide + lift * 0.4, a + lift, b + down * wide + lift * 0.4, a + down * wide + lift * 0.4]:
							caps.set_normal(n)
							caps.set_uv(Vector2(v.x + v.z, v.y * 3.0))
							caps.add_vertex(v)
						capped += 1
	var trim: ArrayMesh = st.commit()
	if trim.get_surface_count() > 0:
		trim.surface_set_material(trim.get_surface_count() - 1, _material("kit_trim", "#d9d3c4"))
	if gutters > 0:
		gt.commit(trim)
		trim.surface_set_material(trim.get_surface_count() - 1, _material("metal_painted", "#7a7d7a"))
	if capped > 0:
		caps.commit(trim)
		var cap_mat: String = ""
		for w2: RoofPlanner.Wing in wings:
			if cap_mat == "" and w2.type in ["gable", "hip", "pyramid", "shed"]:
				cap_mat = str(w2.spec.get("material", "roof_shingle"))
		trim.surface_set_material(trim.get_surface_count() - 1, _cover_material(cap_mat, wings))
	var mi := MeshInstance3D.new()
	mi.name = "RoofTrim"
	mi.mesh = trim
	return mi


## The trim tag of the face line an edge lies on ("" for cut edges: valleys, walls, towers).
static func _line_tag(f: Face, p: Vector2, q: Vector2) -> String:
	for l: Array in f.lines:
		var a: Vector2 = l[0]
		var b: Vector2 = l[1]
		var d: Vector2 = b - a
		var len2: float = d.length_squared()
		if len2 < 1e-8:
			continue
		var ok: bool = true
		for x: Vector2 in [p, q]:
			var tt: float = (x - a).dot(d) / len2
			if tt < -0.01 or tt > 1.01 or absf(d.cross(x - a)) / sqrt(len2) > 0.01:
				ok = false
		if ok:
			return str(l[2])
	return ""


## A board of height h and thickness t whose top outer edge runs from a to b, standing just outside
## the edge (toward `out`).
static func _board(st: SurfaceTool, a: Vector3, b: Vector3, out: Vector3, h: float, t: float) -> void:
	var along: Vector3 = (b - a).normalized()
	var up: Vector3 = out.cross(along).normalized()
	if up.y < 0.0:
		up = -up
	var o: Vector3 = out * t
	var lo: Vector3 = -up * h
	var face: Array = [a + o, b + o, b + o + lo, a + o + lo]
	var bottom: Array = [a + lo, a + o + lo, b + o + lo, b + lo]
	var top: Array = [a, b, b + o, a + o]
	for quad: Array in [[face, out], [bottom, -up], [top, up]]:
		var p: Array = quad[0]
		var n: Vector3 = quad[1]
		for v: Vector3 in [p[0], p[1], p[2], p[0], p[2], p[3]]:
			st.set_normal(n)
			st.set_uv(Vector2((v - a).dot(along), (v - a).dot(up)))
			st.add_vertex(v)


## Half-round gutter (open channel of 6 facets) from a to b.
static func _gutter(st: SurfaceTool, a: Vector3, b: Vector3, out: Vector3) -> void:
	var r: float = 0.065
	var ring: Array[Vector3] = []
	for i: int in 7:
		var ang: float = PI * float(i) / 6.0
		ring.append(-out * cos(ang) * r - Vector3.UP * sin(ang) * r)
	var along: float = a.distance_to(b)
	for i: int in 6:
		var n: Vector3 = (ring[i] + ring[i + 1]).normalized()
		var quad: Array = [a + ring[i], b + ring[i], b + ring[i + 1], a + ring[i + 1]]
		for k: int in [0, 1, 2, 0, 2, 3]:
			var v: Vector3 = quad[k]
			st.set_normal(n)
			st.set_uv(Vector2(along if k in [1, 2] else 0.0, float(i) / 6.0))
			st.add_vertex(v)


## A rectangular timber from a to b (its centre line), `w` wide across `side` and `d` deep along
## `up` (the face toward +up is its top).
static func _beam(st: SurfaceTool, a: Vector3, b: Vector3, up: Vector3, w: float, d: float) -> void:
	var along: Vector3 = (b - a).normalized()
	var side: Vector3 = along.cross(up).normalized()
	var u: Vector3 = side.cross(along).normalized()
	var hw: Vector3 = side * (w * 0.5)
	var hd: Vector3 = u * (d * 0.5)
	var c0: Array = [a - hw - hd, a + hw - hd, a + hw + hd, a - hw + hd]
	var c1: Array = [b - hw - hd, b + hw - hd, b + hw + hd, b - hw + hd]
	var length: float = a.distance_to(b)
	for k: int in 4:
		var p0: Vector3 = c0[k]
		var p1: Vector3 = c0[(k + 1) % 4]
		var q0: Vector3 = c1[k]
		var q1: Vector3 = c1[(k + 1) % 4]
		var n: Vector3 = ((p0 + p1) * 0.5 - a).normalized()
		var uvs: Array[Vector2] = [Vector2(0, 0), Vector2(0, 0.15), Vector2(length, 0.15), Vector2(length, 0)]
		var quad: Array = [p0, p1, q1, q0]
		for idx: int in [0, 1, 2, 0, 2, 3]:
			st.set_normal(n)
			st.set_uv(uvs[idx] + Vector2(0.0, float(k) * 0.37))
			st.add_vertex(quad[idx])


# --- gable and shed ends, parapets, partitions (kit wall shader) ---------------------------------

## A kit-shaded batch keyed by finishes: [st, custom, transform].
static func _kit_batch(kit: Dictionary, node_name: String, custom: Color, y0: float) -> SurfaceTool:
	var key: String = "%s|%d|%d|%.2f" % [node_name, int(custom.r), int(custom.g), y0]
	if not kit.has(key):
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		kit[key] = {"name": node_name, "st": st, "custom": custom, "xf": Transform3D(Basis.IDENTITY, Vector3(0, y0, 0))}
	return (kit[key] as Dictionary)["st"]


## Adds a vertical polygon (3D points, convex) to a kit batch, wound to face `out` (kit_wall culls
## back faces; Godot's front faces are clockwise seen from the camera). `side`: 0 = finish A (r),
## 1 = finish B (g). Points are local to the batch (its transform lifts them by y0).
static func _kit_poly(st: SurfaceTool, pts: Array, out: Vector3, side: float) -> void:
	if pts.size() < 3:
		return
	for k: int in range(1, pts.size() - 1):
		var tri: Array = [pts[0], pts[k], pts[k + 1]]
		if Plane(tri[0], tri[1], tri[2]).normal.dot(out) < 0.0:
			tri = [tri[0], tri[2], tri[1]]
		for v: Vector3 in tri:
			st.set_normal(out)
			st.set_uv(Vector2(v.x + v.z, -v.y))
			st.set_uv2(Vector2(side, 0.0))
			# Kit vertex colour contract: R = AO, G = wear (none here), B = variation.
			st.set_color(Color(1.0, 0.0, 0.5, 1.0))
			st.add_vertex(v)


## Gable ends (two slopes) and shed ends (one): the wall polygon from the storey band up under the
## roof, flush with the wall face below, cut where a taller part of the building stands in it.
## Under an open roof the same polygon faces the room in its wall finish.
static func _ends(w: RoofPlanner.Wing, origin: Vector2, wings: Array, feet: Array[Rect2], tops: Array[float], i: int, ctx: Dictionary, kit: Dictionary, collide: PackedVector3Array) -> void:
	var r: Rect2 = w.rect_m(origin, w.span)
	var t: float = tan(deg_to_rad(w.pitch))
	var ext: int = PoiParts.finish_index("wall", str(w.spec.get("gable_finish", ctx.get("exterior", "siding_white"))))
	var decay: float = float(ctx.get("decay", 0.4))
	var inner: int = int(ctx.get("open_finish", {}).get(w.index, ext))
	var along_x: bool = (w.axis == "x") if w.type == "gable" else (w.slope in [0, 2])
	var y0: float = w.y - 0.2
	for k: int in 2:
		if not w.ends[k]:
			continue
		# End line position, its outward direction and the span along it.
		var pos: float
		var out: Vector3
		var s0: float
		var s1: float
		if along_x:
			pos = r.position.x if k == 0 else r.end.x
			out = Vector3(-1, 0, 0) if k == 0 else Vector3(1, 0, 0)
			s0 = r.position.y
			s1 = r.end.y
		else:
			pos = r.position.y if k == 0 else r.end.y
			out = Vector3(0, 0, -1) if k == 0 else Vector3(0, 0, 1)
			s0 = r.position.x
			s1 = r.end.x
		# The end's outline in (s, height): band, eaves, ridge or high edge.
		var outline: PackedVector2Array = []
		if w.type == "gable":
			var sm: float = (s0 + s1) * 0.5
			outline = PackedVector2Array([Vector2(s0, y0), Vector2(s1, y0), Vector2(s1, w.y), Vector2(sm, w.y + (s1 - s0) * 0.5 * t), Vector2(s0, w.y)])
		else:
			# Shed: high at the side away from `slope`.
			var high_at_s0: bool = w.slope in [2, 1]
			var rise: float = (s1 - s0) * t
			outline = PackedVector2Array([Vector2(s0, y0), Vector2(s1, y0), Vector2(s1, w.y + (0.0 if high_at_s0 else rise)),
				Vector2(s0, w.y + (rise if high_at_s0 else 0.0))])
		# A taller part standing in the end wall's plane (a tower on the facade) takes its place
		# there, up to its own wall top; a lower roof against the end (a chancel) leaves it whole.
		var parts: Array = [outline]
		for j: int in wings.size():
			var o: RoofPlanner.Wing = wings[j]
			if j == i or o.level <= w.level:
				continue
			var fr: Rect2 = o.rect_m(origin, o.cells)
			var crosses: bool = (pos > fr.position.x - 0.1 and pos < fr.end.x + 0.1) if along_x else (pos > fr.position.y - 0.1 and pos < fr.end.y + 0.1)
			if not crosses:
				continue
			var a0: float = fr.position.y if along_x else fr.position.x
			var a1: float = fr.end.y if along_x else fr.end.x
			var cut := PackedVector2Array([Vector2(a0, -100.0), Vector2(a1, -100.0), Vector2(a1, o.y), Vector2(a0, o.y)])
			var next: Array = []
			for part: PackedVector2Array in parts:
				next.append_array(subtract(part, cut))
			parts = next
		for part2: PackedVector2Array in parts:
			var outer: Array = []
			var inner_pts: Array = []
			for p: Vector2 in part2:
				var off_o: float = pos + (0.08 * (out.x + out.z))
				var off_i: float = pos - (0.08 * (out.x + out.z))
				outer.append(Vector3(off_o, p.y - y0, p.x) if along_x else Vector3(p.x, p.y - y0, off_o))
				inner_pts.append(Vector3(off_i, p.y - y0, p.x) if along_x else Vector3(p.x, p.y - y0, off_i))
			_kit_poly(_kit_batch(kit, "Gables", Color(ext, inner, decay, 0.5), y0), outer, out, 0.0)
			if w.open:
				_kit_poly(_kit_batch(kit, "Gables", Color(ext, inner, decay, 0.5), y0), inner_pts, -out, 1.0)
			for k2: int in range(1, outer.size() - 1):
				for v: Vector3 in [outer[0], outer[k2], outer[k2 + 1]]:
					collide.append(v + Vector3(0, y0, 0))


## A flat roof's parapet (16 cm wall in the exterior finish, capped) along every side that faces out
## (not where a taller wall or a roof of the same level continues).
static func _parapets(w: RoofPlanner.Wing, origin: Vector2, wings: Array, ctx: Dictionary, kit: Dictionary) -> void:
	var ph: float = float(w.spec.get("parapet", 0.6))
	if ph <= 0.01:
		return
	var layout: PoiLayout = ctx.get("layout")
	var ext: int = PoiParts.finish_index("wall", str(w.spec.get("gable_finish", ctx.get("exterior", "siding_white"))))
	var custom := Color(ext, ext, float(ctx.get("decay", 0.4)), 0.5)
	var st: SurfaceTool = _kit_batch(kit, "Parapet", custom, 0.0)
	var r: Rect2i = w.span
	var top: float = w.y + 0.25 + ph
	var hw: float = 0.08
	for side: int in 4:
		var cells: Array[Vector2i] = RoofPlanner._side_cells(r, side)
		var run_start: int = -1
		for k: int in cells.size() + 1:
			var open: bool = k < cells.size() and not _covered_beyond(layout, wings, w, cells[k])
			if open and run_start < 0:
				run_start = k
			elif not open and run_start >= 0:
				_parapet_run(st, r, side, run_start, k, origin, w.y, top, hw)
				run_start = -1


## Whether a cell beside a flat wing is built at its level or above (a wall or another roof there).
static func _covered_beyond(layout: PoiLayout, wings: Array, w: RoofPlanner.Wing, c: Vector2i) -> bool:
	if layout == null:
		return false
	if layout.is_built(w.level, c) or layout.is_built(w.level + 1, c):
		return true
	return false


static func _parapet_run(st: SurfaceTool, r: Rect2i, side: int, k0: int, k1: int, origin: Vector2, y: float, top: float, hw: float) -> void:
	var p0: Vector2
	var p1: Vector2
	match side:
		0:
			p0 = Vector2(r.position.x + k0, r.position.y)
			p1 = Vector2(r.position.x + k1, r.position.y)
		2:
			p0 = Vector2(r.position.x + k0, r.end.y)
			p1 = Vector2(r.position.x + k1, r.end.y)
		3:
			p0 = Vector2(r.position.x, r.position.y + k0)
			p1 = Vector2(r.position.x, r.position.y + k1)
		_:
			p0 = Vector2(r.end.x, r.position.y + k0)
			p1 = Vector2(r.end.x, r.position.y + k1)
	p0 += origin
	p1 += origin
	var d: Vector2 = (p1 - p0).normalized()
	var outward: Vector2 = Vector2(PoiLayout.DIRS[side])
	var e0: Vector2 = p0 - d * hw
	var e1: Vector2 = p1 + d * hw
	# From the storey band under the wall top (it would show as a recessed slab edge) to the cap.
	var y0: float = y - 0.2
	for s: float in [1.0, -1.0]:
		var o: Vector2 = outward * hw * s
		var q: Array = [Vector3(e0.x + o.x, y0, e0.y + o.y), Vector3(e1.x + o.x, y0, e1.y + o.y), Vector3(e1.x + o.x, top, e1.y + o.y), Vector3(e0.x + o.x, top, e0.y + o.y)]
		_kit_poly(st, q, Vector3(outward.x * s, 0.0, outward.y * s), 0.0 if s > 0.0 else 1.0)
	var cap: Array = [Vector3(e0.x + outward.x * hw, top, e0.y + outward.y * hw), Vector3(e1.x + outward.x * hw, top, e1.y + outward.y * hw),
		Vector3(e1.x - outward.x * hw, top, e1.y - outward.y * hw), Vector3(e0.x - outward.x * hw, top, e0.y - outward.y * hw)]
	_kit_poly(st, cap, Vector3.UP, 0.5)
	# The ends of a run that stops against a wall: close them.
	for e: Array in [[e0, -d], [e1, d]]:
		var at: Vector2 = e[0]
		var dir2: Vector2 = e[1]
		var q2: Array = [Vector3(at.x + outward.x * hw, y0, at.y + outward.y * hw), Vector3(at.x - outward.x * hw, y0, at.y - outward.y * hw),
			Vector3(at.x - outward.x * hw, top, at.y - outward.y * hw), Vector3(at.x + outward.x * hw, top, at.y + outward.y * hw)]
		_kit_poly(st, q2, Vector3(dir2.x, 0.0, dir2.y), 0.5)


## Walls between an open-roof room and a closed one rise from the storey band to the roof's
## underside, so the attic over the closed room does not open onto the room below.
static func _partitions(faces: Array[Face], ctx: Dictionary, kit: Dictionary) -> void:
	for p: Array in ctx.get("partitions", []):
		var a: Vector2 = p[0]
		var b: Vector2 = p[1]
		var y0: float = float(p[2])
		var fin_open: int = int(p[3])
		var fin_other: int = int(p[4])
		var toward_open: Vector2 = p[5]
		var pts_top: Array = []
		for k: int in 5:
			var q: Vector2 = a.lerp(b, float(k) / 4.0)
			var hq: float = height_at(faces, q + toward_open * 0.09)
			if hq == -INF:
				hq = y0 + 0.2
			pts_top.append(Vector3(q.x, hq - THICK - y0, q.y))
		var shift := Vector3(toward_open.x, 0.0, toward_open.y) * 0.08
		var poly_open: Array = [Vector3(a.x, 0.0, a.y) + shift]
		for v: Vector3 in pts_top:
			poly_open.append(v + shift)
		poly_open.append(Vector3(b.x, 0.0, b.y) + shift)
		# The batch key carries the finishes; the polygon is concave-free (a strip under a roof
		# line), emitted as a fan from the bottom corner.
		var custom := Color(fin_open, fin_other, float(ctx.get("decay", 0.4)), 0.5)
		var st: SurfaceTool = _kit_batch(kit, "Partitions", custom, y0)
		_kit_strip(st, Vector3(a.x, 0.0, a.y) + shift, Vector3(b.x, 0.0, b.y) + shift, pts_top, shift, Vector3(toward_open.x, 0.0, toward_open.y), 0.0)
		_kit_strip(st, Vector3(a.x, 0.0, a.y) - shift, Vector3(b.x, 0.0, b.y) - shift, pts_top, -shift, -Vector3(toward_open.x, 0.0, toward_open.y), 1.0)


## A vertical strip from a bottom edge (a..b) up to a polyline of top points (sampled along a..b).
static func _kit_strip(st: SurfaceTool, a: Vector3, b: Vector3, tops: Array, shift: Vector3, out: Vector3, side: float) -> void:
	var n: int = tops.size()
	for k: int in n - 1:
		var t0: Vector3 = (tops[k] as Vector3) + shift
		var t1: Vector3 = (tops[k + 1] as Vector3) + shift
		var b0: Vector3 = a.lerp(b, float(k) / float(n - 1))
		var b1: Vector3 = a.lerp(b, float(k + 1) / float(n - 1))
		_kit_poly(st, [b0, b1, t1, t0], out, side)


static func _kit_instance(node_name: String, mesh: ArrayMesh, custom: Color, xf: Transform3D) -> MultiMeshInstance3D:
	if mesh.get_surface_count() > 0:
		mesh.surface_set_material(0, PoiParts.kit_material("wall"))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = 1
	mm.set_instance_transform(0, xf)
	mm.set_instance_custom_data(0, custom)
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	return mmi


# --- open roofs: timbers ---------------------------------------------------------------------------

## Rafters every 0.6 m under each slope of a roof over an open room, a ridge beam, wall plates on
## the eave walls and collar ties every fourth pair on wide spans.
static func _timbers(faces: Array[Face], wings: Array, origin: Vector2) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var any: bool = false
	for i: int in wings.size():
		var w: RoofPlanner.Wing = wings[i]
		if not w.open or not w.type in ["gable", "shed"]:
			continue
		any = true
		var r: Rect2 = w.rect_m(origin, w.span)
		var t: float = tan(deg_to_rad(w.pitch))
		var along_x: bool = (w.axis == "x") if w.type == "gable" else (w.slope in [0, 2])
		var length: float = r.size.x if along_x else r.size.y
		var depth: float = r.size.y if along_x else r.size.x
		var n_raft: int = maxi(2, int(floor(length / RAFTER_STEP)))
		var step: float = length / float(n_raft)
		var drop: float = THICK / cos(atan(t)) + 0.09
		for k: int in n_raft + 1:
			var s: float = (r.position.x if along_x else r.position.y) + clampf(float(k) * step, 0.08, length - 0.08)
			if w.type == "gable":
				var half: float = depth * 0.5
				var mid: float = (r.position.y if along_x else r.position.x) + half
				for sgn: float in [-1.0, 1.0]:
					var edge: float = mid + sgn * half
					var p_low := Vector2(s, edge) if along_x else Vector2(edge, s)
					var p_top := Vector2(s, mid - sgn * 0.06) if along_x else Vector2(mid - sgn * 0.06, s)
					var lo := Vector3(p_low.x, w.y - drop, p_low.y)
					var hi := Vector3(p_top.x, w.y + half * t - drop, p_top.y)
					if _covered(faces, i, (p_low + p_top) * 0.5):
						_beam(st, lo, hi, Vector3.UP, 0.06, 0.16)
				if depth >= 6.0 and k % 4 == 2:
					var hy: float = w.y + half * t * 0.42 - drop
					var c0 := Vector2(s, mid - half * 0.58) if along_x else Vector2(mid - half * 0.58, s)
					var c1 := Vector2(s, mid + half * 0.58) if along_x else Vector2(mid + half * 0.58, s)
					if _covered(faces, i, (c0 + c1) * 0.5):
						_beam(st, Vector3(c0.x, hy, c0.y), Vector3(c1.x, hy, c1.y), Vector3.UP, 0.07, 0.18)
			else:
				var hi_at_low: bool = w.slope in [2, 1]
				var e_hi: float = (r.position.y if along_x else r.position.x) if hi_at_low else (r.end.y if along_x else r.end.x)
				var e_lo: float = (r.end.y if along_x else r.end.x) if hi_at_low else (r.position.y if along_x else r.position.x)
				var ph := Vector2(s, e_hi) if along_x else Vector2(e_hi, s)
				var pl := Vector2(s, e_lo) if along_x else Vector2(e_lo, s)
				if _covered(faces, i, (ph + pl) * 0.5):
					_beam(st, Vector3(pl.x, w.y - drop, pl.y), Vector3(ph.x, w.y + depth * t - drop, ph.y), Vector3.UP, 0.06, 0.16)
		if w.type == "gable":
			var mid2: float = (r.position.y if along_x else r.position.x) + depth * 0.5
			var ry: float = w.y + depth * 0.5 * t - drop - 0.04
			var a := Vector3(r.position.x, ry, mid2) if along_x else Vector3(mid2, ry, r.position.y)
			var b := Vector3(r.end.x, ry, mid2) if along_x else Vector3(mid2, ry, r.end.y)
			_beam(st, a, b, Vector3.UP, 0.1, 0.22)
			# Wall plates on both eave walls (they close the storey band under the open roof).
			for sgn2: float in [-1.0, 1.0]:
				var e: float = mid2 + sgn2 * depth * 0.5
				var pa := Vector3(r.position.x, w.y - 0.11, e) if along_x else Vector3(e, w.y - 0.11, r.position.y)
				var pb := Vector3(r.end.x, w.y - 0.11, e) if along_x else Vector3(e, w.y - 0.11, r.end.y)
				_beam(st, pa, pb, Vector3.UP, 0.18, 0.2)
	if not any:
		return null
	var mesh: ArrayMesh = st.commit()
	mesh.surface_set_material(0, _material(TIMBER_MAT, "#6b5642"))
	var mi := MeshInstance3D.new()
	mi.name = "RoofTimber"
	mi.mesh = mesh
	return mi


## Whether a point lies under what is left of one of a wing's faces.
static func _covered(faces: Array[Face], wing: int, p: Vector2) -> bool:
	for f: Face in faces:
		if f.wing != wing:
			continue
		for piece: PackedVector2Array in f.pieces:
			if point_in(piece, p):
				return true
	return false


# --- spires ---------------------------------------------------------------------------------------

## An octagonal broach spire on a square tower: eight steep faces to an apex, four broaches
## sloping up from the tower's corners onto the diagonal faces, and an iron cross on a ball.
static func _spire(w: RoofPlanner.Wing, origin: Vector2, collide: PackedVector3Array) -> Array:
	var r: Rect2 = w.rect_m(origin, w.span).grow(0.1)
	var cen := Vector3(r.get_center().x, w.y, r.get_center().y)
	var half: float = minf(r.size.x, r.size.y) * 0.5
	var height: float = w.rise()
	var apex: Vector3 = cen + Vector3.UP * height
	var a: float = half * tan(PI / 8.0)
	# Octagon vertices (on the square's sides), counter-clockwise from the east side.
	var octo: Array[Vector3] = []
	for k: int in 4:
		var ang: float = PI * 0.5 * float(k)
		var nrm := Vector3(cos(ang), 0.0, sin(ang))
		var tan_dir := Vector3(-sin(ang), 0.0, cos(ang))
		octo.append(cen + nrm * half - tan_dir * a)
		octo.append(cen + nrm * half + tan_dir * a)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k2: int in 8:
		var p: Vector3 = octo[k2]
		var q: Vector3 = octo[(k2 + 1) % 8]
		_spire_tri(st, p, q, apex, collide)
	# Broaches: from each corner up onto the diagonal face between its two octagon vertices.
	for k3: int in 4:
		var p2: Vector3 = octo[k3 * 2 + 1]
		var q2: Vector3 = octo[(k3 * 2 + 2) % 8]
		var corner: Vector3 = cen + (p2 + q2 - cen * 2.0).normalized() * half * sqrt(2.0)
		var on_face: Vector3 = ((p2 + q2) * 0.5).lerp(apex, 0.16)
		_spire_tri(st, corner, p2, on_face, collide)
		_spire_tri(st, q2, corner, on_face, collide)
	var mesh: ArrayMesh = st.commit()
	mesh.surface_set_material(0, _material(str(w.spec.get("material", "roof_cedar")), str(w.spec.get("color", "#4a463f"))))
	var mi := MeshInstance3D.new()
	mi.name = "RoofSpire"
	mi.mesh = mesh
	# Finial: a ball and an iron cross.
	var fin := SurfaceTool.new()
	fin.begin(Mesh.PRIMITIVE_TRIANGLES)
	var top: Vector3 = apex + Vector3.UP * 0.05
	_beam(fin, top, top + Vector3.UP * 1.1, Vector3.FORWARD, 0.06, 0.06)
	_beam(fin, top + Vector3(-0.28, 0.78, 0), top + Vector3(0.28, 0.78, 0), Vector3.UP, 0.06, 0.06)
	_beam(fin, top + Vector3(0, -0.02, 0), top + Vector3(0, 0.16, 0), Vector3.FORWARD, 0.18, 0.18)
	var fmesh: ArrayMesh = fin.commit()
	fmesh.surface_set_material(0, _material("metal_painted", "#2b2a28"))
	var fi := MeshInstance3D.new()
	fi.name = "RoofFinial"
	fi.mesh = fmesh
	return [mi, fi]


static func _spire_tri(st: SurfaceTool, p: Vector3, q: Vector3, apex: Vector3, collide: PackedVector3Array) -> void:
	var n: Vector3 = (q - p).cross(apex - p).normalized()
	var mid := Vector3((p.x + q.x) * 0.5, p.y, (p.z + q.z) * 0.5)
	if n.dot(Vector3(mid.x - apex.x, 0.0, mid.z - apex.z)) < 0.0:
		n = -n
	var u_dir: Vector3 = (q - p).normalized()
	var slope_len: float = mid.distance_to(apex)
	for v: Vector3 in [p, q, apex]:
		st.set_normal(n)
		var up_dist: float = (v.y - p.y) / maxf(0.01, apex.y - p.y) * slope_len
		st.set_uv(Vector2((v - p).dot(u_dir), up_dist))
		st.add_vertex(v)
		collide.append(v)
