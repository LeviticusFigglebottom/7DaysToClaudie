class_name TerrainHoles
extends RefCounted
## Openings cut into the heightmap terrain over the below-ground rooms of placed POIs (level -1
## cellars; TD-026, ADR-0007).
##
## The holes are derived from the POI placements and layouts every time the world loads (the
## same placements always cut the same holes), so nothing about them is saved. Each hole is the
## union of a building's below-ground room cells, transformed to world XZ and merged into convex
## rectangles. The terrain subtracts them exactly — render mesh at every near LOD (skirts too),
## collision, navigation source and the SDF volume when a column there is handed off — along
## the cellar's outer cell edges. The POI's own cellar walls stand centred on those edges (16 cm
## thick, from the cellar floor up past the pad) and the ground floor closes the top, so the cut
## edge is always inside a wall: nothing outside the walls is lost and no gap shows from the
## yard. Far tiles (16 m) are not cut: past the near square nobody can see into a cellar, and
## the terrain there is hidden under the ground floor anyway.
##
## Immutable after construction; every query is safe from worker threads.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Lots := preload("res://src/poi/lot_picker.gd")

## Area below which a clipped piece is dropped (m^2): slivers from exact-edge contacts.
const EPS_AREA: float = 1e-6
## Thickness of a kit floor slab (docs/POI_KIT.md: origin at its top, 0.2 m down).
const SLAB: float = 0.2


class Hole:
	## Placement / instance id of the POI ("okafor_farm/house").
	var id: StringName = &""
	## World height of the lowest below-ground floor (top of its slab).
	var floor_y: float = 0.0
	## Pad height the hole is cut into (the POI placement's y).
	var top_y: float = 0.0
	## Underside of the ground floor over the cellar: a point below it is down in the cellar.
	var ceiling_y: float = 0.0
	var bounds := Rect2()
	## Convex counter-clockwise (in x, z) quads covering the cells, world XZ.
	var pieces: Array[PackedVector2Array] = []
	var piece_bounds: Array[Rect2] = []
	## Outline of the union (pairs of points: segment a, b, a, b, ...), world XZ.
	var outline := PackedVector2Array()


var holes: Array[Hole] = []
var bounds := Rect2()
## Buried levels' cells (ADR-0044: mine levels and caves running on under the ground beyond the
## building), one floor-only Hole per level: they cut nothing (the surface stays whole over them,
## so the mesher, collision, nav and volumes never see them), but ground_below finds their floors.
var buried: Array[Hole] = []


func is_empty() -> bool:
	return holes.is_empty()


func has_buried() -> bool:
	return not buried.is_empty()


# --- Construction ---------------------------------------------------------------------------------

## The holes of `parts` (TerrainHoles, in order) as one new object, keeping only those of the POIs
## in `only` (instance id -> anything) unless `only` is null. Holes are shared, not copied: they
## are immutable. A streamed world cuts only built buildings' cellars (ADR-0038 §8): a pit where
## the ring has not built the building yet would be a hole in an empty lot.
static func combined(parts: Array, only: Variant = null) -> TerrainHoles:
	var th := TerrainHoles.new()
	var gate: Dictionary = only if only is Dictionary else {}
	for part: Variant in parts:
		for h: Hole in (part as TerrainHoles).holes:
			if only == null or gate.has(h.id):
				th.bounds = h.bounds if th.holes.is_empty() else th.bounds.merge(h.bounds)
				th.holes.append(h)
		for b: Hole in (part as TerrainHoles).buried:
			if only == null or gate.has(owner_of(b.id)):
				th.buried.append(b)
	return th


## The POI a hole belongs to: a buried level's hole is "<poi id>@<level>".
static func owner_of(hole_id: StringName) -> StringName:
	var s: String = String(hole_id)
	var at: int = s.rfind("@")
	return StringName(s.substr(0, at)) if at >= 0 else hole_id


## Whether any hole (cut or buried) belongs to POI `id`, and where: its holes' bounds merged
## (Rect2() when none).
func bounds_of(id: StringName) -> Rect2:
	var out := Rect2()
	for h: Hole in holes + buried:
		if h.id == id or owner_of(h.id) == id:
			out = h.bounds if out.size == Vector2.ZERO else out.merge(h.bounds)
	return out

## Holes for every POI placed in `regions` (region id -> RegionTerrain; the detailed regions,
## which are the ones PoiManager builds).
static func from_regions(regions: Dictionary) -> TerrainHoles:
	var th := TerrainHoles.new()
	var ids: Array = regions.keys()
	ids.sort()
	for rid: Variant in ids:
		var rt: RegionTerrain = regions[rid]
		for e: Dictionary in placed_pois(rt.placements):
			th.add_poi(e["def"], e["id"], e["xf"])
	return th


## Expands composer placements (standalone POIs and framework lots) into
## [{def: PoiDef, id: StringName, xf: Transform3D}] with the transform PoiManager gives the
## building node: a placement turns its plane by `rotation` degrees (node yaw = -angle), and a
## lot centres the POI footprint in its rect with the front (+Z) toward `facing`.
static func placed_pois(placements: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var db: Node = ContentDB.instance
	if db == null:
		return out
	for pl: Variant in placements:
		if not pl is Dictionary:
			continue
		var p: Dictionary = pl
		var o: Array = p.get("origin", [0, 0, 0])
		var xf := Transform3D(Basis(Vector3.UP, -deg_to_rad(float(p.get("rotation", 0.0)))), Vector3(float(o[0]), float(o[1]), float(o[2])))
		match str(p.get("kind", "")):
			"poi":
				var pd: PoiDef = db.call(&"get_def", &"poi", StringName(str(p.get("def", "")))) as PoiDef
				if pd != null:
					out.append({"def": pd, "id": StringName(str(p.get("id", pd.id))), "xf": xf})
			"framework", "town":
				var fw: FrameworkDef = db.call(&"get_def", &"framework", StringName(str(p.get("def", "")))) as FrameworkDef
				if fw == null:
					continue
				# An organic town (ADR-0040) comes once per region it touches: its lots centred in `rect`.
				var only := Rect2()
				if p.has("rect"):
					only = Rect2(float(p["rect"][0]), float(p["rect"][1]), float(p["rect"][2]), float(p["rect"][3]))
				# Lots without a pick hold what LotPicker chooses (ADR-0030), resolved as PoiManager does;
				# generated buildings have no cellars, so only authored ones can cut a hole.
				for res: Dictionary in Lots.resolve(fw, str(p.get("id", fw.id)), Lots.session_seed()):
					var l: Dictionary = res["lot"]
					var lpd: PoiDef = db.call(&"get_def", &"poi", res["def_id"]) as PoiDef if str(res["kind"]) == "authored" else null
					if lpd == null or (only.has_area() and not only.has_point(Lots.lot_center(l))):
						continue
					if l.has("frame"):
						out.append({"def": lpd, "id": StringName("%s/%s" % [p.get("id", fw.id), l["id"]]), "xf": xf * Lots.lot_local_xf(l, lpd.footprint)})
						continue
					var rect: Array = l["rect"]
					var center := Vector3(float(rect[0]) + float(rect[2]) * 0.5, 0.0, float(rect[1]) + float(rect[3]) * 0.5)
					var yaw: float = {"S": 0.0, "E": PI * 0.5, "N": PI, "W": -PI * 0.5}.get(str(l.get("facing", "S")), 0.0)
					var b := Basis(Vector3.UP, yaw)
					var local_origin: Vector3 = center - b * Vector3(lpd.footprint.x * 0.5, 0.0, lpd.footprint.y * 0.5)
					out.append({"def": lpd, "id": StringName("%s/%s" % [p.get("id", fw.id), l["id"]]), "xf": xf * Transform3D(b, local_origin)})
	return out


## Adds the hole of one placed POI (nothing when it has no below-ground rooms).
func add_poi(def: PoiDef, id: StringName, xf: Transform3D) -> void:
	var below: bool = false
	for lv: Variant in def.layout.get("levels", []):
		if lv is Dictionary and int((lv as Dictionary).get("level", 0)) < 0:
			below = true
	if not below:
		return
	var layout: PoiLayout = PoiLayout.compile(def)
	var cells: Array[Vector2i] = []
	var seen: Dictionary = {}
	var lowest: int = 0
	# A buried level's cells cut the surface only under a ground-floor room (the building closes
	# them); the rest lie under the ground and get a floor-only hole per level.
	var covered: Dictionary = {}
	for c0: Vector2i in layout.room_cells(0):
		covered[c0] = true
	for li: int in layout.level_ids:
		if li >= 0:
			continue
		var is_buried: bool = bool((layout.levels[li] as Dictionary).get("buried", false))
		var deep: Array[Vector2i] = []
		for c: Vector2i in layout.room_cells(li):
			if is_buried and not covered.has(c):
				deep.append(c)
				continue
			lowest = mini(lowest, li)
			if not seen.has(c):
				seen[c] = true
				cells.append(c)
		if not deep.is_empty():
			add_buried(StringName("%s@%d" % [id, li]), deep, layout.origin, xf, xf.origin.y + layout.level_y(li),
				xf.origin.y + layout.level_y(li) + PoiLayout.STOREY - SLAB)
	if cells.is_empty():
		return
	add_cells(id, cells, layout.origin, xf, xf.origin.y + layout.level_y(lowest), xf.origin.y, xf.origin.y + layout.level_y(0) - SLAB)


## A buried level's floor under (x, z) for a point at height y: the floor of the buried level
## whose storey holds y, or the lowest buried floor there when y is below them all; NAN when no
## buried level lies under (x, z) or y is above every one of them.
func buried_floor(x: float, z: float, y: float) -> float:
	var p := Vector2(x, z)
	var lowest: float = NAN
	for h: Hole in buried:
		if not h.bounds.grow(0.001).has_point(p):
			continue
		for poly: PackedVector2Array in h.pieces:
			if not point_in_convex(poly, p):
				continue
			if y >= h.floor_y - 0.5 and y < h.ceiling_y:
				return h.floor_y
			if y < h.floor_y and (is_nan(lowest) or h.floor_y < lowest):
				lowest = h.floor_y
	return lowest


## Adds a buried level's floor-only hole (see `buried`).
func add_buried(id: StringName, cells: Array[Vector2i], origin: Vector2, xf: Transform3D, floor_y: float, ceiling_y: float) -> void:
	var keep: Array[Hole] = holes.duplicate()
	var keep_bounds: Rect2 = bounds
	add_cells(id, cells, origin, xf, floor_y, floor_y, ceiling_y)
	buried.append(holes.pop_back())
	holes = keep
	bounds = keep_bounds


## Adds a hole over plan cells (1 m, POI-local: cell (c, r) spans x origin.x+c..+1, z
## origin.y+r..+1) placed by `xf`. ceiling_y: underside of the floor that closes it on top.
func add_cells(id: StringName, cells: Array[Vector2i], origin: Vector2, xf: Transform3D, floor_y: float, top_y: float, ceiling_y: float) -> void:
	var h := Hole.new()
	h.id = id
	h.floor_y = floor_y
	h.top_y = top_y
	h.ceiling_y = ceiling_y
	var in_hole: Dictionary = {}
	for c: Vector2i in cells:
		in_hole[c] = true
	var to_world := func(lx: float, lz: float) -> Vector2:
		var p: Vector3 = xf * Vector3(origin.x + lx, 0.0, origin.y + lz)
		return Vector2(p.x, p.z)
	for r: Rect2i in merge_cells(cells):
		var quad := PackedVector2Array([to_world.call(r.position.x, r.position.y), to_world.call(r.end.x, r.position.y),
			to_world.call(r.end.x, r.end.y), to_world.call(r.position.x, r.end.y)])
		if signed_area(quad) < 0.0:
			quad.reverse()
		h.pieces.append(quad)
		h.piece_bounds.append(_poly_bounds(quad))
	# Outline: cell sides with no hole cell beyond them.
	var sorted_cells: Array[Vector2i] = cells.duplicate()
	sorted_cells.sort()
	for c: Vector2i in sorted_cells:
		if not in_hole.has(c + Vector2i(0, -1)):
			h.outline.append_array([to_world.call(c.x, c.y), to_world.call(c.x + 1, c.y)])
		if not in_hole.has(c + Vector2i(1, 0)):
			h.outline.append_array([to_world.call(c.x + 1, c.y), to_world.call(c.x + 1, c.y + 1)])
		if not in_hole.has(c + Vector2i(0, 1)):
			h.outline.append_array([to_world.call(c.x + 1, c.y + 1), to_world.call(c.x, c.y + 1)])
		if not in_hole.has(c + Vector2i(-1, 0)):
			h.outline.append_array([to_world.call(c.x, c.y + 1), to_world.call(c.x, c.y)])
	h.bounds = h.piece_bounds[0]
	for pb: Rect2 in h.piece_bounds:
		h.bounds = h.bounds.merge(pb)
	bounds = h.bounds if holes.is_empty() else bounds.merge(h.bounds)
	holes.append(h)


## Greedy rectangle cover of a cell set: runs along each row, merged downward while the next
## row has the same run. Deterministic (sorted), few rectangles for room-shaped plans.
static func merge_cells(cells: Array[Vector2i]) -> Array[Rect2i]:
	var rows: Dictionary = {}
	for c: Vector2i in cells:
		if not rows.has(c.y):
			rows[c.y] = []
		(rows[c.y] as Array).append(c.x)
	var row_keys: Array = rows.keys()
	row_keys.sort()
	# Runs per row: [x0, x1) spans.
	var runs: Dictionary = {}
	for r: Variant in row_keys:
		var xs: Array = rows[r]
		xs.sort()
		var list: Array[Vector2i] = []
		var start: int = int(xs[0])
		var prev: int = start
		for k: int in range(1, xs.size()):
			var x: int = int(xs[k])
			if x == prev:
				continue
			if x != prev + 1:
				list.append(Vector2i(start, prev + 1))
				start = x
			prev = x
		list.append(Vector2i(start, prev + 1))
		runs[int(r)] = list
	var out: Array[Rect2i] = []
	var used: Dictionary = {}
	for r2: Variant in row_keys:
		var row: int = int(r2)
		for span: Vector2i in runs[row]:
			if used.has(Vector3i(span.x, span.y, row)):
				continue
			var bottom: int = row + 1
			while runs.has(bottom) and (runs[bottom] as Array).has(span) and not used.has(Vector3i(span.x, span.y, bottom)):
				used[Vector3i(span.x, span.y, bottom)] = true
				bottom += 1
			out.append(Rect2i(span.x, row, span.y - span.x, bottom - row))
	return out


# --- Queries --------------------------------------------------------------------------------------

func intersects(r: Rect2) -> bool:
	if holes.is_empty() or not bounds.intersects(r):
		return false
	for h: Hole in holes:
		if h.bounds.intersects(r):
			return true
	return false


## Convex pieces (world XZ) whose bounds overlap `r` — the cutters a mesh over `r` subtracts.
func pieces_in(r: Rect2) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	if holes.is_empty() or not bounds.intersects(r):
		return out
	for h: Hole in holes:
		if not h.bounds.intersects(r):
			continue
		for i: int in h.pieces.size():
			if h.piece_bounds[i].intersects(r):
				out.append(h.pieces[i])
	return out


## The hole whose cells contain (x, z), or null.
func hole_at(x: float, z: float) -> Hole:
	if holes.is_empty() or not bounds.grow(0.001).has_point(Vector2(x, z)):
		return null
	var p := Vector2(x, z)
	for h: Hole in holes:
		if not h.bounds.grow(0.001).has_point(p):
			continue
		for poly: PackedVector2Array in h.pieces:
			if point_in_convex(poly, p):
				return h
	return null


func contains(x: float, z: float) -> bool:
	return hole_at(x, z) != null


## Horizontal distance to the nearest hole outline: negative inside a hole, positive outside
## (INF far from every hole). Exact for the union (outline segments, not the merged pieces).
func signed_distance(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var best: float = INF
	for h: Hole in holes:
		if h.bounds.grow(4.0).has_point(p) or best == INF:
			for k: int in range(0, h.outline.size(), 2):
				best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, h.outline[k], h.outline[k + 1])))
	return -best if contains(x, z) else best


# --- Geometry -------------------------------------------------------------------------------------

## Twice-signed area sign convention: positive = counter-clockwise in (x, z) math orientation,
## which is what the terrain winds as front faces seen from above.
static func signed_area(poly: PackedVector2Array) -> float:
	var a: float = 0.0
	for i: int in poly.size():
		var p: Vector2 = poly[i]
		var q: Vector2 = poly[(i + 1) % poly.size()]
		a += p.x * q.y - q.x * p.y
	return a * 0.5


static func point_in_convex(poly: PackedVector2Array, p: Vector2, eps: float = 1e-6) -> bool:
	for i: int in poly.size():
		var a: Vector2 = poly[i]
		var b: Vector2 = poly[(i + 1) % poly.size()]
		if (b - a).cross(p - a) < -eps:
			return false
	return true


## Keeps the part of convex `poly` left of a->b (inside, `left` true) or right of it (outside).
## Points on the line belong to both sides; slivers are dropped by the callers' area test.
static func clip_half(poly: PackedVector2Array, a: Vector2, b: Vector2, left: bool) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n: int = poly.size()
	if n == 0:
		return out
	var e: Vector2 = b - a
	var sgn: float = 1.0 if left else -1.0
	for i: int in n:
		var p: Vector2 = poly[i]
		var q: Vector2 = poly[(i + 1) % n]
		var sp: float = e.cross(p - a) * sgn
		var sq: float = e.cross(q - a) * sgn
		if sp >= 0.0:
			out.append(p)
		if (sp > 0.0 and sq < 0.0) or (sp < 0.0 and sq > 0.0):
			out.append(p.lerp(q, sp / (sp - sq)))
	return out


## Convex pieces of convex `poly` outside convex `cutter` (both counter-clockwise): split off
## the part beyond each cutter edge in turn, keep cutting what is left inside.
static func subtract_convex(poly: PackedVector2Array, cutter: PackedVector2Array) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	var rest: PackedVector2Array = poly
	for i: int in cutter.size():
		var a: Vector2 = cutter[i]
		var b: Vector2 = cutter[(i + 1) % cutter.size()]
		var outside: PackedVector2Array = clip_half(rest, a, b, false)
		if outside.size() >= 3 and absf(signed_area(outside)) > EPS_AREA:
			out.append(outside)
		rest = clip_half(rest, a, b, true)
		if rest.size() < 3 or absf(signed_area(rest)) <= EPS_AREA:
			return out
	return out


## Convex `poly` minus every cutter, as convex pieces (an empty array when fully covered).
static func cut(poly: PackedVector2Array, cutters: Array[PackedVector2Array]) -> Array[PackedVector2Array]:
	var pieces: Array[PackedVector2Array] = [poly]
	for c: PackedVector2Array in cutters:
		var next: Array[PackedVector2Array] = []
		for p: PackedVector2Array in pieces:
			next.append_array(subtract_convex(p, c))
		pieces = next
		if pieces.is_empty():
			break
	return pieces


## Parameter intervals (x = t0, y = t1) of segment a->b lying outside every cutter, in order.
static func segment_outside(a: Vector2, b: Vector2, cutters: Array[PackedVector2Array]) -> Array[Vector2]:
	var inside: Array[Vector2] = []
	var d: Vector2 = b - a
	for poly: PackedVector2Array in cutters:
		var t0: float = 0.0
		var t1: float = 1.0
		var empty: bool = false
		for i: int in poly.size():
			var p0: Vector2 = poly[i]
			var e: Vector2 = poly[(i + 1) % poly.size()] - p0
			var s0: float = e.cross(a - p0)
			var s1: float = e.cross(b - p0)
			if s0 < 0.0 and s1 < 0.0:
				empty = true
				break
			if s0 >= 0.0 and s1 >= 0.0:
				continue
			var t: float = s0 / (s0 - s1)
			if s0 < 0.0:
				t0 = maxf(t0, t)
			else:
				t1 = minf(t1, t)
		if not empty and t1 - t0 > 1e-6 and d.length() * (t1 - t0) > 1e-4:
			inside.append(Vector2(t0, t1))
	inside.sort_custom(func(u: Vector2, v: Vector2) -> bool: return u.x < v.x)
	var out: Array[Vector2] = []
	var cur: float = 0.0
	for iv: Vector2 in inside:
		if iv.x > cur + 1e-6:
			out.append(Vector2(cur, iv.x))
		cur = maxf(cur, iv.y)
	if cur < 1.0 - 1e-6:
		out.append(Vector2(cur, 1.0))
	return out


## Barycentric weights of p in triangle (a, b, c).
static func barycentric(p: Vector2, a: Vector2, b: Vector2, c: Vector2) -> Vector3:
	var v0: Vector2 = b - a
	var v1: Vector2 = c - a
	var v2: Vector2 = p - a
	var den: float = v0.x * v1.y - v1.x * v0.y
	if absf(den) < 1e-12:
		return Vector3(1.0, 0.0, 0.0)
	var v: float = (v2.x * v1.y - v1.x * v2.y) / den
	var w: float = (v0.x * v2.y - v2.x * v0.y) / den
	return Vector3(1.0 - v - w, v, w)


static func _poly_bounds(poly: PackedVector2Array) -> Rect2:
	var r := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		r = r.expand(p)
	return r
