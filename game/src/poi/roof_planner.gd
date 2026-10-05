class_name RoofPlanner
extends RefCounted
## Plans a POI's roofs from its massing (ADR-0021). The tops of the building (every built cell with
## nothing built over it, a tall room's void included) are decomposed level by level into wings:
## rectangles roofed at their own height, largest first. Each wing then gets a roof that suits where
## it sits:
##  * the main body: the style's roof (gable by default, ridge along style.roof.axis or its long side);
##  * a leg of the same height beside a bigger wing (an L, T or U): a gable whose ridge runs into the
##    bigger roof, which RoofBuilder cuts along the valleys (cross gables);
##  * an annex against a taller wall: a lean-to (shed) sloping away from the wall when it is shallow,
##    an abutting gable when it is deep, a flat roof behind a parapet on commercial and industrial
##    buildings; its pitch is lowered until it stays under the windows of the wall it leans on;
##  * a tower (a small top a storey or more above the rest): a hip, pyramid or spire. A tower that
##    rises through a bigger roof (a church belfry) leaves that roof whole around it.
## style.roof.roofs overrides a wing: {"level": L, "at": [col, row] (a cell of the wing), "type",
## "axis", "pitch", "overhang", "slope" (a shed's low side N/E/S/W), "material", ...}.
## RoofBuilder.build_plan turns the wings into geometry.

const TYPES: PackedStringArray = ["gable", "hip", "shed", "flat", "pyramid", "spire", "none"]
## Keys of style.roof (the building's defaults) and of a style.roof.roofs override entry.
const ROOF_KEYS: PackedStringArray = ["type", "axis", "pitch", "overhang", "material", "color", "flat_material", "flat_color",
	"parapet", "gutters", "gable_finish", "roofs"]
const WING_KEYS: PackedStringArray = ["level", "at", "type", "axis", "pitch", "overhang", "slope", "material", "color",
	"flat_material", "flat_color", "parapet", "gutters", "gable_finish", "height"]
## A top no wider or deeper than this (cells), a storey or more above the building around it: a tower.
const TOWER_MAX: int = 8
## An annex no deeper than this (m) from the taller wall it leans on gets a lean-to.
const SHED_DEPTH: float = 4.5
## Lowest pitch a pitched roof keeps (degrees) before it becomes a lean-to or a flat roof.
const MIN_PITCH: float = 9.0
## Gap left under an opening's sill (or the wall top) on the wall an annex roof leans on (m).
const FLASHING: float = 0.25


## One roof over a rectangle of a building's top.
class Wing:
	extends RefCounted
	var level: int = 0
	## Plan cells under it (the rectangle its walls stand on).
	var cells := Rect2i()
	## Plan cells its roof spans: a leg's runs on into the wing it joins.
	var span := Rect2i()
	## Top of its walls (the eave line at the wall plane), POI-local metres.
	var y: float = 3.0
	var type: String = "gable"
	## Ridge direction of a gable or hip ("x" or "z").
	var axis: String = "x"
	## A shed's low side (PoiLayout.SIDES index: N 0, E 1, S 2, W 3).
	var slope: int = 2
	var pitch: float = 30.0
	var overhang: float = 0.45
	## main | leg | annex | tower
	var role: String = "main"
	## style.roof merged with this wing's override.
	var spec: Dictionary = {}
	## Gable ends (or shed ends) at the low and high end of the ridge (shed: of the eave side) are
	## outside walls: false where another roof or a taller wall closes them.
	var ends: Array[bool] = [true, true]
	## Rooms under it have no ceiling: they see the roof's boards and rafters.
	var open: bool = false
	## The wing a leg runs into.
	var joins: Wing = null
	## Index in the plan (stable: names, seeds).
	var index: int = 0

	## Plan-cell rectangle of the roof in POI-local metres.
	func rect_m(origin: Vector2, r: Rect2i) -> Rect2:
		return Rect2(origin + Vector2(r.position), Vector2(r.size))

	## Rise of the roof above its wall top (ridge or a shed's high edge).
	func rise() -> float:
		var t: float = tan(deg_to_rad(pitch))
		match type:
			"gable":
				return (float(span.size.y) if axis == "x" else float(span.size.x)) * 0.5 * t
			"hip", "pyramid":
				return minf(float(span.size.x), float(span.size.y)) * 0.5 * t
			"shed":
				return (float(span.size.y) if slope in [0, 2] else float(span.size.x)) * t
			"spire":
				return float(spec.get("height", maxf(span.size.x, span.size.y) * 2.2))
		return 0.25


## Errors from the last plan (overrides that name no wing, bad keys or values).
static var last_errors: PackedStringArray = []


## The wings of a compiled layout, ready for RoofBuilder.build_plan.
static func plan(layout: PoiLayout) -> Array[Wing]:
	last_errors = []
	var base: Dictionary = (layout.style.get("roof", {"type": "gable"}) as Dictionary).duplicate()
	var overrides: Array = base.get("roofs", [])
	base.erase("roofs")
	var wings: Array[Wing] = []
	for li: int in layout.level_ids:
		if li < 0:
			continue
		var region: Dictionary = _top_cells(layout, li)
		for c: Vector2i in _through_cells(layout, li, region):
			region[c] = true
		for r: Rect2i in decompose(region):
			var w := Wing.new()
			w.level = li
			w.cells = r
			w.span = r
			w.y = layout.level_y(li) + PoiLayout.STOREY
			w.index = wings.size()
			wings.append(w)
	for w: Wing in wings:
		w.spec = base.duplicate()
		w.pitch = float(base.get("pitch", 30.0))
		w.overhang = float(base.get("overhang", 0.45))
		w.open = _open_under(layout, w)
	var forced: Dictionary = _apply_overrides(layout, wings, overrides)
	_assign(layout, wings, base, forced)
	return wings


## Built cells of a level with nothing built over them.
static func _top_cells(layout: PoiLayout, li: int) -> Dictionary:
	var out: Dictionary = {}
	var lv: Dictionary = layout.levels[li]
	for r: int in int(lv["d"]):
		for c: int in int(lv["w"]):
			var cell := Vector2i(c, r)
			if layout.is_built(li, cell) and not layout.is_built(li + 1, cell):
				out[cell] = true
	return out


## Cells of a tower that rises through this level's roof: a small rectangular column built on the
## storey above, bordered by this level's tops on two or more sides. The roof runs on under it
## (RoofBuilder cuts it away inside the tower's walls) instead of breaking into strips around it.
static func _through_cells(layout: PoiLayout, li: int, tops: Dictionary) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	if not layout.levels.has(li + 1):
		return out
	var seen: Dictionary = {}
	var lv: Dictionary = layout.levels[li + 1]
	for r: int in int(lv["d"]):
		for c: int in int(lv["w"]):
			var start := Vector2i(c, r)
			if seen.has(start) or not layout.is_built(li + 1, start):
				continue
			var comp: Array[Vector2i] = []
			var stack: Array[Vector2i] = [start]
			seen[start] = true
			while not stack.is_empty():
				var cur: Vector2i = stack.pop_back()
				comp.append(cur)
				for d: Vector2i in PoiLayout.DIRS:
					var n: Vector2i = cur + d
					if not seen.has(n) and layout.is_built(li + 1, n):
						seen[n] = true
						stack.append(n)
			var box := Rect2i(comp[0], Vector2i.ONE)
			for cc: Vector2i in comp:
				box = box.merge(Rect2i(cc, Vector2i.ONE))
			if comp.size() != box.size.x * box.size.y or box.size.x > TOWER_MAX or box.size.y > TOWER_MAX:
				continue
			var under: bool = true
			for cc2: Vector2i in comp:
				under = under and layout.is_built(li, cc2)
			if not under:
				continue
			var sides: int = 0
			for s: int in 4:
				for cc3: Vector2i in _side_cells(box, s):
					if tops.has(cc3):
						sides += 1
						break
			if sides >= 2:
				out.append_array(comp)
	return out


## The cells just outside one side of a rectangle (PoiLayout.SIDES order).
static func _side_cells(r: Rect2i, side: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	match side:
		0:
			for x: int in range(r.position.x, r.end.x):
				out.append(Vector2i(x, r.position.y - 1))
		2:
			for x: int in range(r.position.x, r.end.x):
				out.append(Vector2i(x, r.end.y))
		3:
			for z: int in range(r.position.y, r.end.y):
				out.append(Vector2i(r.position.x - 1, z))
		_:
			for z: int in range(r.position.y, r.end.y):
				out.append(Vector2i(r.end.x, z))
	return out


## Greedy rectangle decomposition of a cell set: the largest rectangle first (ties: the one found
## first scanning rows top to bottom), until no cell is left.
static func decompose(cells: Dictionary) -> Array[Rect2i]:
	var out: Array[Rect2i] = []
	var left: Dictionary = cells.duplicate()
	while not left.is_empty():
		var r: Rect2i = _largest_rect(left)
		if r.size.x <= 0:
			break
		for z: int in range(r.position.y, r.end.y):
			for x: int in range(r.position.x, r.end.x):
				left.erase(Vector2i(x, z))
		out.append(r)
	return out


## Largest axis-aligned rectangle of cells (histogram method per row).
static func _largest_rect(cells: Dictionary) -> Rect2i:
	var lo := Vector2i(1 << 20, 1 << 20)
	var hi := Vector2i(-(1 << 20), -(1 << 20))
	for c: Vector2i in cells:
		lo = Vector2i(mini(lo.x, c.x), mini(lo.y, c.y))
		hi = Vector2i(maxi(hi.x, c.x), maxi(hi.y, c.y))
	var w: int = hi.x - lo.x + 1
	var heights: PackedInt32Array = []
	heights.resize(w)
	var best := Rect2i()
	var best_area: int = 0
	for z: int in range(lo.y, hi.y + 1):
		for i: int in w:
			heights[i] = heights[i] + 1 if cells.has(Vector2i(lo.x + i, z)) else 0
		# Largest rectangle under the histogram (stack of increasing heights).
		var stack: Array[int] = []
		for i2: int in w + 1:
			var h: int = heights[i2] if i2 < w else 0
			while not stack.is_empty() and heights[stack.back()] >= h:
				var top: int = stack.pop_back()
				var height: int = heights[top]
				var left_i: int = stack.back() + 1 if not stack.is_empty() else 0
				var area: int = height * (i2 - left_i)
				if area > best_area:
					best_area = area
					best = Rect2i(lo.x + left_i, z - height + 1, i2 - left_i, height)
			stack.append(i2)
	return best


static func _open_under(layout: PoiLayout, w: Wing) -> bool:
	for z: int in range(w.cells.position.y, w.cells.end.y):
		for x: int in range(w.cells.position.x, w.cells.end.x):
			var c := Vector2i(x, z)
			if layout.is_built(w.level, c) and layout.open_roof_at(w.level, c):
				return true
	return false


## Applies style.roof.roofs entries to the wings holding their cell; returns wing index -> the keys
## an author set (they win over the planner's choices).
static func _apply_overrides(layout: PoiLayout, wings: Array[Wing], overrides: Array) -> Dictionary:
	var forced: Dictionary = {}
	for o: Variant in overrides:
		if not o is Dictionary:
			last_errors.append("style.roof.roofs entries must be objects")
			continue
		var d: Dictionary = o
		for k: Variant in d.keys():
			if not str(k).begins_with("_") and not WING_KEYS.has(str(k)):
				last_errors.append("roof override has unknown key '%s' (%s)" % [k, ", ".join(WING_KEYS)])
		var at: Array = d.get("at", [])
		if at.size() != 2:
			last_errors.append("roof override needs \"at\": [col, row] (a cell of the wing it changes)")
			continue
		var li: int = int(d.get("level", 0))
		var cell := Vector2i(int(at[0]), int(at[1]))
		var hit: Wing = null
		for w: Wing in wings:
			if w.level == li and w.cells.has_point(cell):
				hit = w
		if hit == null:
			last_errors.append("roof override at %s level %d: no roof there (the top of the building at that cell is on another level)" % [cell, li])
			continue
		var t: String = str(d.get("type", ""))
		if t != "" and not TYPES.has(t):
			last_errors.append("roof override at %s: type '%s' unknown (%s)" % [cell, t, ", ".join(TYPES)])
			continue
		if d.has("slope") and not PoiLayout.SIDES.has(str(d["slope"])):
			last_errors.append("roof override at %s: slope must be N/E/S/W" % cell)
			continue
		if d.has("axis") and not str(d["axis"]) in ["x", "z"]:
			last_errors.append("roof override at %s: axis must be x or z" % cell)
			continue
		for k2: Variant in d.keys():
			if not str(k2) in ["level", "at"]:
				hit.spec[str(k2)] = d[k2]
		forced[hit.index] = d
		if d.has("pitch"):
			hit.pitch = float(d["pitch"])
		if d.has("overhang"):
			hit.overhang = float(d["overhang"])
	return forced


## Roles, types, axes, pitches, leg spans and exposed ends.
static func _assign(layout: PoiLayout, wings: Array[Wing], base: Dictionary, forced: Dictionary) -> void:
	var style_type: String = str(base.get("type", "gable"))
	var commercial: bool = false
	for z: String in layout.def.zoning:
		commercial = commercial or z in ["commercial", "industrial"]
	# Largest first: a leg's type follows the wing it joins.
	var order: Array[Wing] = wings.duplicate()
	order.sort_custom(func(a: Wing, b: Wing) -> bool:
		var aa: int = a.cells.get_area()
		var ab: int = b.cells.get_area()
		return a.level > b.level if a.level != b.level else (aa > ab if aa != ab else a.index < b.index))
	for w: Wing in order:
		var o: Dictionary = forced.get(w.index, {})
		var contact: Array = _taller_contact(layout, w)
		var joins: Wing = _same_level_neighbour(wings, w)
		var long_axis: String = "x" if w.cells.size.x >= w.cells.size.y else "z"
		if style_type in ["flat", "none"]:
			w.type = style_type
			w.role = "annex" if int(contact[1]) > 0 else "main"
		elif joins != null:
			w.role = "leg"
			w.joins = joins
			w.type = joins.type if joins.type in ["gable", "hip", "flat"] else "gable"
			if w.type == "hip":
				w.type = "gable"
			w.axis = "x" if _junction_side(w, joins) in [1, 3] else "z"
		elif int(contact[1]) > 0:
			w.role = "annex"
			var side: int = contact[0]
			var depth: float = float(w.cells.size.y if side in [0, 2] else w.cells.size.x)
			if depth <= SHED_DEPTH:
				w.type = "shed"
				w.slope = (side + 2) % 4
			elif commercial:
				w.type = "flat"
			else:
				w.type = "gable"
				w.axis = "z" if side in [0, 2] else "x"
		elif _is_tower(layout, w):
			w.role = "tower"
			w.type = "hip"
			w.axis = long_axis
		else:
			w.role = "main"
			w.type = style_type if TYPES.has(style_type) else "gable"
			w.axis = str(base.get("axis", long_axis)) if _is_principal(wings, w) else long_axis
		# The author's word wins.
		if o.has("type"):
			w.type = str(o["type"])
		if o.has("axis"):
			w.axis = str(o["axis"])
		if o.has("slope"):
			w.slope = int(PoiLayout.SIDES[str(o["slope"])])
		elif w.type == "shed" and w.role != "annex":
			w.slope = 2 if w.cells.size.x >= w.cells.size.y else 1
		if w.type == "pyramid":
			w.axis = long_axis
		if w.type == "spire" and not w.spec.has("pitch"):
			w.pitch = 75.0
		if w.role == "leg" and w.type == "gable" and not o.has("axis"):
			_extend_leg(w)
		if w.role == "annex" and not o.has("pitch"):
			_clamp_annex(layout, w, contact)
	for w2: Wing in wings:
		w2.ends = _exposed_ends(layout, wings, w2)


## The side (PoiLayout.SIDES index) along which the cells just outside the wing are built a storey
## higher, and how many such cells: [side, count] (count 0 when nothing taller touches it).
static func _taller_contact(layout: PoiLayout, w: Wing) -> Array:
	var best: Array = [0, 0]
	for s: int in 4:
		var n: int = 0
		for c: Vector2i in _side_cells(w.cells, s):
			if layout.is_built(w.level + 1, c):
				n += 1
		if n > int(best[1]):
			best = [s, n]
	return best


## A wing on the same level sharing a side with this one and larger than it (the one a leg runs
## into), or null.
static func _same_level_neighbour(wings: Array[Wing], w: Wing) -> Wing:
	var best: Wing = null
	for o: Wing in wings:
		if o == w or o.level != w.level:
			continue
		var bigger: bool = o.cells.get_area() > w.cells.get_area() or (o.cells.get_area() == w.cells.get_area() and o.index < w.index)
		if not bigger or _junction_side(w, o) < 0:
			continue
		if best == null or o.cells.get_area() > best.cells.get_area():
			best = o
	return best


## The side of `w` that touches `o` along at least one cell edge (-1 if they do not touch).
static func _junction_side(w: Wing, o: Wing) -> int:
	var a: Rect2i = w.cells
	var b: Rect2i = o.cells
	var over_x: bool = mini(a.end.x, b.end.x) > maxi(a.position.x, b.position.x)
	var over_z: bool = mini(a.end.y, b.end.y) > maxi(a.position.y, b.position.y)
	if over_x and a.position.y == b.end.y:
		return 0
	if over_x and a.end.y == b.position.y:
		return 2
	if over_z and a.position.x == b.end.x:
		return 3
	if over_z and a.end.x == b.position.x:
		return 1
	return -1


## A small top a storey or more above some part of the building, with no top of its own level
## beside it. Something lower must be built outside its footprint: a small two-storey house on its
## own is a house (the style's roof), not a tower.
static func _is_tower(layout: PoiLayout, w: Wing) -> bool:
	if w.level < 1 or w.cells.size.x > TOWER_MAX or w.cells.size.y > TOWER_MAX:
		return false
	for s: int in 4:
		for c: Vector2i in _side_cells(w.cells, s):
			if layout.is_built(w.level, c):
				return false
	for li: int in layout.level_ids:
		if li < 0 or li >= w.level:
			continue
		var lv: Dictionary = layout.levels[li]
		for r: int in int(lv["d"]):
			for c2: int in int(lv["w"]):
				var cell := Vector2i(c2, r)
				if not w.cells.has_point(cell) and layout.is_built(li, cell):
					return true
	return false


## The building's principal roof: the largest wing of the highest level that has more than a tower.
static func _is_principal(wings: Array[Wing], w: Wing) -> bool:
	var best: Wing = null
	for o: Wing in wings:
		if best == null or o.cells.get_area() > best.cells.get_area() or (o.cells.get_area() == best.cells.get_area() and o.level > best.level):
			best = o
	return best == w


## A leg's roof runs on into the wing it joins: to that roof's ridge when it is lower than it, right
## across when it is the taller (a cross gable). A leg joining the end of a roof whose ridge points
## at it stops at that gable wall instead.
static func _extend_leg(w: Wing) -> void:
	var m: Wing = w.joins
	var side: int = _junction_side(w, m)
	var m_ridge_along: String = m.axis if m.type in ["gable", "hip"] else ("x" if m.cells.size.x >= m.cells.size.y else "z")
	# The junction runs along x for N/S sides: the main's ridge must run along it too.
	var junction_along: String = "x" if side in [0, 2] else "z"
	if m.type == "flat" or m_ridge_along != junction_along:
		return
	var leg_half: float = float(w.cells.size.x if side in [0, 2] else w.cells.size.y) * 0.5
	var main_half: float = float(m.cells.size.y if side in [0, 2] else m.cells.size.x) * 0.5
	var lower: bool = leg_half * tan(deg_to_rad(w.pitch)) <= main_half * tan(deg_to_rad(m.pitch)) + 0.01
	var r: Rect2i = w.span
	match side:
		0:
			var to0: int = m.cells.position.y + int(ceil(main_half)) if lower else m.cells.position.y
			r = Rect2i(r.position.x, to0, r.size.x, r.end.y - to0)
		2:
			var to2: int = m.cells.end.y - int(ceil(main_half)) if lower else m.cells.end.y
			r = Rect2i(r.position.x, r.position.y, r.size.x, to2 - r.position.y)
		3:
			var to3: int = m.cells.position.x + int(ceil(main_half)) if lower else m.cells.position.x
			r = Rect2i(to3, r.position.y, r.end.x - to3, r.size.y)
		_:
			var to1: int = m.cells.end.x - int(ceil(main_half)) if lower else m.cells.end.x
			r = Rect2i(r.position.x, r.position.y, to1 - r.position.x, r.size.y)
	w.span = r


## Lowers an annex roof until its high side stays under the openings (or the top) of the taller
## wall it leans on; a gable too flat to read becomes a lean-to, a lean-to too flat a flat roof.
static func _clamp_annex(layout: PoiLayout, w: Wing, contact: Array) -> void:
	if int(contact[1]) <= 0 or not w.type in ["shed", "gable"]:
		return
	var side: int = contact[0]
	var room: float = _headroom(layout, w, side)
	var t: float = tan(deg_to_rad(w.pitch))
	if w.type == "gable":
		var half: float = float(w.cells.size.x if side in [0, 2] else w.cells.size.y) * 0.5
		if half * t > room:
			var p: float = rad_to_deg(atan(room / half))
			if p >= MIN_PITCH + 3.0:
				w.pitch = p
				return
			w.type = "shed"
			w.slope = (side + 2) % 4
			t = tan(deg_to_rad(w.pitch))
		else:
			return
	var depth: float = float(w.cells.size.y if side in [0, 2] else w.cells.size.x)
	if depth * t > room:
		var p2: float = rad_to_deg(atan(room / depth))
		if p2 < MIN_PITCH * 0.6:
			w.type = "flat"
		else:
			w.pitch = p2


## Height above an annex's wall top its roof may reach on the taller wall: up to just under the
## lowest window or door sill there, else just under that wall's top.
static func _headroom(layout: PoiLayout, w: Wing, side: int) -> float:
	var room: float = INF
	var cells: Array[Vector2i] = _side_cells(w.cells, side)
	for c: Vector2i in cells:
		if not layout.is_built(w.level + 1, c):
			continue
		var top: int = w.level + 1
		while layout.is_built(top + 1, c):
			top += 1
		room = minf(room, float(top - w.level) * PoiLayout.STOREY - 0.35)
		# The wall over the annex: between the cell above the annex and the taller cell.
		var inner: Vector2i = c - PoiLayout.DIRS[side]
		var e: Array = PoiLayout.side_edge(inner, side)
		for li: int in range(w.level + 1, top + 1):
			var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
			if wall.is_empty() or (wall["opening"] as Dictionary).is_empty():
				continue
			var op: Dictionary = wall["opening"]
			var sill: float = 0.0 if str(op["type"]).begins_with("door") or str(op["type"]) in ["open", "breach"] else 0.85
			room = minf(room, float(li - w.level - 1) * PoiLayout.STOREY + sill - FLASHING)
	return maxf(room, 0.3) if room != INF else 2.5


## Whether each end of a wing's roof is an outside wall (a gable or shed end to close): not where the
## cells beyond it are built at its level and their roof stands at least as high as its own.
static func _exposed_ends(layout: PoiLayout, wings: Array[Wing], w: Wing) -> Array[bool]:
	var out: Array[bool] = [true, true]
	if not w.type in ["gable", "shed"]:
		return out
	var along_x: bool = (w.axis == "x") if w.type == "gable" else (w.slope in [0, 2])
	var r: Rect2i = w.span
	var top: float = w.y + w.rise()
	for k: int in 2:
		var cells: Array[Vector2i] = _side_cells(r, (3 if k == 0 else 1) if along_x else (0 if k == 0 else 2))
		var closed: int = 0
		for c: Vector2i in cells:
			if layout.is_built(w.level + 1, c):
				closed += 1
				continue
			if not layout.is_built(w.level, c):
				continue
			for o: Wing in wings:
				if o != w and o.level == w.level and o.cells.has_point(c) and o.y + o.rise() >= top - 0.01:
					closed += 1
					break
		out[k] = closed < cells.size()
	return out
