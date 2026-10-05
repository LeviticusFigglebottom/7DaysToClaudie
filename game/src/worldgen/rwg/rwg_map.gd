class_name RwgMap
extends RefCounted
## The map of a generated world (ADR-0031): shaded relief tinted by biome, lakes and rivers,
## roads by class with their bridges, towns with their lots and streets, places, trails, Bloom
## patches and the drop site, over the region grid with its cell labels. Drawn from the world's own
## JSON (world.json, its regions and frameworks), so the New Game screen, the CLI
## (rwg_preview.gd) and QA all see exactly what the game will load. Pure Image work: safe on a
## worker thread.

const BIOME_COLORS: Dictionary = {
	"conifer_forest": Color(0.25, 0.36, 0.22), "birch_grove": Color(0.45, 0.55, 0.33), "meadow": Color(0.62, 0.64, 0.4),
	"rocky_slope": Color(0.56, 0.55, 0.5), "riverbank": Color(0.45, 0.52, 0.42), "town": Color(0.6, 0.58, 0.52),
}
const WATER := Color(0.23, 0.4, 0.55)
const WATER_EDGE := Color(0.16, 0.28, 0.4)
const ZONE_COLORS: Dictionary = {
	"residential": Color(0.86, 0.76, 0.58), "commercial": Color(0.9, 0.55, 0.3), "civic": Color(0.62, 0.5, 0.78),
	"industrial": Color(0.55, 0.55, 0.6), "roadside": Color(0.9, 0.55, 0.3),
}
const ROAD_STYLE: Dictionary = {
	"highway": [Color(0.12, 0.12, 0.13), 4.5, Color(0.95, 0.85, 0.45), 1.5],
	"county": [Color(0.35, 0.3, 0.24), 3.0, Color(0.78, 0.7, 0.55), 1.2],
	"track": [Color(0.38, 0.28, 0.18), 2.0, Color(0.0, 0.0, 0.0, 0.0), 0.0],
	"drive": [Color(0.2, 0.2, 0.22), 2.0, Color(0.0, 0.0, 0.0, 0.0), 0.0],
}
## 3 x 5 glyphs for the cell labels (A-G, 1-7), one row of three bits per entry.
const GLYPHS: Dictionary = {
	"A": [2, 5, 7, 5, 5], "B": [6, 5, 6, 5, 6], "C": [3, 4, 4, 4, 3], "D": [6, 5, 5, 5, 6], "E": [7, 4, 6, 4, 7], "F": [7, 4, 6, 4, 4],
	"G": [3, 4, 5, 5, 3], "1": [2, 6, 2, 2, 7], "2": [6, 1, 2, 4, 7], "3": [6, 1, 2, 1, 6], "4": [5, 5, 7, 1, 1], "5": [7, 4, 6, 1, 6],
	"6": [3, 4, 6, 5, 2], "7": [7, 1, 2, 2, 2],
}

var img: Image
var px: int = 1024
var wr := Rect2()


## Renders a world directory (world.json, regions/*/region.json, frameworks.json) at px x px.
static func render_dir(dir: String, size_px: int = 1024) -> Image:
	var world: Dictionary = _read(dir.path_join("world.json"))
	var fws: Dictionary = _read(dir.path_join("frameworks.json"))
	var regions: Array = []
	for r: Variant in world.get("regions", []):
		regions.append(_read(dir.path_join("regions").path_join(str((r as Dictionary).get("id", ""))).path_join("region.json")))
	var m: RefCounted = (load("res://src/worldgen/rwg/rwg_map.gd") as GDScript).new()
	return m.call(&"render", world, regions, fws, size_px)


static func _read(path: String) -> Dictionary:
	var j := JSON.new()
	if not FileAccess.file_exists(path) or j.parse(FileAccess.get_file_as_string(path)) != OK or not j.data is Dictionary:
		return {}
	return j.data


func render(world: Dictionary, regions: Array, fws: Dictionary, size_px: int) -> Image:
	px = size_px
	var cols: int = int(world.get("cols", 4))
	var rs: float = float(world.get("region_size", 1024.0))
	wr = Rect2(Vector2(-cols * 0.5, -cols * 0.5) * rs, Vector2(cols, cols) * rs)
	_relief(world)
	for l: Variant in world.get("lakes", []):
		var poly: PackedVector2Array = _poly((l as Dictionary).get("polygon", []))
		_fill(poly, WATER)
		_outline(poly, WATER_EDGE, 1.0)
	for rv: Variant in world.get("rivers", []):
		var r: Dictionary = rv
		var line: Polyline2 = Polyline2.from_array(r.get("points", []))
		var s: float = 0.0
		while s <= line.total_length:
			var w: float = line.value_at(r.get("width", 10.0), s)
			_dot(line.point_at(s), maxf(1.6, w / _mpp()), WATER)
			s += _mpp() * 0.5
	# Bloom patches, faint, under the roads.
	for reg: Variant in regions:
		for f: Variant in (reg as Dictionary).get("features", []):
			var fd: Dictionary = f
			if str(fd.get("type", "")) == "bloom" and fd.has("at"):
				_disc(_v2(fd["at"]), float(fd.get("radius", 40.0)), Color(0.78, 0.42, 0.82, 0.3))
	# Trails.
	for reg2: Variant in regions:
		for f2: Variant in (reg2 as Dictionary).get("features", []):
			var fd2: Dictionary = f2
			if str(fd2.get("type", "")) == "path":
				_dashed(Polyline2.from_array(fd2.get("points", [])), Color(0.45, 0.33, 0.2), 1.3)
	# Roads: casing then centre line, in class order so highways draw on top.
	for cls: String in ["track", "drive", "county", "highway"]:
		var st: Array = ROAD_STYLE[cls]
		for rdv: Variant in world.get("roads", []):
			var rd: Dictionary = rdv
			if str(rd.get("class", "county")) != cls:
				continue
			var line2: Polyline2 = Polyline2.from_array(rd.get("points", []))
			_stroke(line2, st[0], float(st[1]))
			if float(st[3]) > 0.0:
				_stroke(line2, st[2], float(st[3]))
			for b: Variant in rd.get("bridges", []):
				var bd: Dictionary = b
				var a: Vector2 = _v2(bd["from"])
				var e: Vector2 = _v2(bd["to"])
				_segment(a, e, Color(0.08, 0.08, 0.08), float(st[1]) + 2.5)
				_segment(a, e, Color(0.85, 0.82, 0.75), maxf(1.2, float(st[1]) - 1.0))
	# Towns: pad, lots by zoning, streets.
	var fw_by_id: Dictionary = {}
	for d: Variant in fws.get("defs", []):
		fw_by_id[str((d as Dictionary).get("id", ""))] = d
	for reg3: Variant in regions:
		for f3: Variant in (reg3 as Dictionary).get("features", []):
			var fd3: Dictionary = f3
			match str(fd3.get("type", "")):
				"framework":
					_town(fd3, fw_by_id.get(str(fd3.get("framework", "")), {}))
				"poi":
					_place(fd3)
	# The drop site: a yellow ring.
	var gen: Dictionary = world.get("generator", {})
	if gen.has("drop_site"):
		var dp: Vector2 = _v2(gen["drop_site"])
		_dot(dp, 13.0, Color(0.05, 0.05, 0.05))
		_dot(dp, 10.0, Color(1.0, 0.85, 0.15))
		_dot(dp, 5.0, Color(0.05, 0.05, 0.05))
	_grid(cols, rs)
	return img


# --- Layers --------------------------------------------------------------------------------------

func _relief(world: Dictionary) -> void:
	var macro: Dictionary = world.get("macro", {})
	var rows: Array = macro.get("corner_heights", [])
	var n: int = rows.size()
	var step: float = float(macro.get("step", 32.0))
	var hs := PackedFloat32Array()
	for row: Variant in rows:
		for v: Variant in row:
			hs.append(float(v))
	var bm: Dictionary = world.get("biome_map", {})
	var ids: Array = bm.get("ids", [])
	var bstep: float = float(bm.get("step", 64.0))
	var bcols: int = int(bm.get("cols", 0))
	var brows: Array = bm.get("rows_data", [])
	var half: int = px / 2
	var lo: Image = Image.create(half, half, false, Image.FORMAT_RGB8)
	var hmin: float = INF
	var hmax: float = -INF
	for v2: float in hs:
		hmin = minf(hmin, v2)
		hmax = maxf(hmax, v2)
	var light := Vector3(-0.55, 0.62, -0.56).normalized()
	var mpp: float = wr.size.x / half
	for j: int in half:
		var z: float = wr.position.y + (j + 0.5) * mpp
		for i: int in half:
			var x: float = wr.position.x + (i + 0.5) * mpp
			var hc: float = _h(hs, n, step, x, z)
			var dx: float = _h(hs, n, step, x + mpp, z) - _h(hs, n, step, x - mpp, z)
			var dz: float = _h(hs, n, step, x, z + mpp) - _h(hs, n, step, x, z - mpp)
			# Relief exaggerated 3x so gentle country still reads on a map.
			var nrm := Vector3(-dx * 3.0, 2.0 * mpp, -dz * 3.0).normalized()
			var lit: float = clampf(nrm.dot(light) * 1.05 + 0.12, 0.12, 1.2)
			var col: Color = BIOME_COLORS["conifer_forest"]
			if bcols > 0:
				# Biome colours blended between cell centres (the game wanders the edges too).
				var fxb: float = clampf((x - wr.position.x) / bstep - 0.5, 0.0, bcols - 1.001)
				var fzb: float = clampf((z - wr.position.y) / bstep - 0.5, 0.0, brows.size() - 1.001)
				var bi: int = int(fxb)
				var bj: int = int(fzb)
				var c00: Color = _bcol(brows, ids, bi, bj, col)
				var c10: Color = _bcol(brows, ids, bi + 1, bj, col)
				var c01: Color = _bcol(brows, ids, bi, bj + 1, col)
				var c11: Color = _bcol(brows, ids, bi + 1, bj + 1, col)
				col = c00.lerp(c10, fxb - bi).lerp(c01.lerp(c11, fxb - bi), fzb - bj)
			var e: float = (hc - hmin) / maxf(1.0, hmax - hmin)
			col = col.lerp(Color(0.86, 0.84, 0.8), smoothstep(0.82, 1.0, e) * 0.5)
			lo.set_pixel(i, j, Color(col.r * lit, col.g * lit, col.b * lit))
	lo.resize(px, px, Image.INTERPOLATE_BILINEAR)
	img = lo


static func _bcol(brows: Array, ids: Array, i: int, j: int, fallback: Color) -> Color:
	var row: String = str(brows[clampi(j, 0, brows.size() - 1)])
	var ch: int = row.unicode_at(clampi(i, 0, row.length() - 1)) - 48
	return BIOME_COLORS.get(str(ids[ch]), fallback) if ch >= 0 and ch < ids.size() else fallback


static func _h(hs: PackedFloat32Array, n: int, step: float, x: float, z: float) -> float:
	var half_w: float = (n - 1) * step * 0.5
	var gx: float = clampf((x + half_w) / step, 0.0, n - 1.001)
	var gz: float = clampf((z + half_w) / step, 0.0, n - 1.001)
	var i: int = int(gx)
	var j: int = int(gz)
	var fx: float = gx - i
	var fz: float = gz - j
	var k: int = j * n + i
	return lerpf(lerpf(hs[k], hs[k + 1], fx), lerpf(hs[k + n], hs[k + n + 1], fx), fz)


func _town(f: Dictionary, fw: Dictionary) -> void:
	var o: Vector2 = _v2(f.get("origin", [0, 0]))
	var rot: float = deg_to_rad(float(f.get("rotation", 0.0)))
	var sz: Array = fw.get("size", [60, 60])
	var pad := PackedVector2Array([o, o + Vector2(float(sz[0]), 0).rotated(rot), o + Vector2(float(sz[0]), float(sz[1])).rotated(rot), o + Vector2(0, float(sz[1])).rotated(rot)])
	_fill(pad, Color(0.66, 0.64, 0.6))
	for l: Variant in fw.get("lots", []):
		var lot: Dictionary = l
		var r: Array = lot.get("rect", [0, 0, 0, 0])
		var a := Vector2(float(r[0]), float(r[1]))
		var poly := PackedVector2Array([o + a.rotated(rot), o + (a + Vector2(float(r[2]), 0)).rotated(rot), o + (a + Vector2(float(r[2]), float(r[3]))).rotated(rot), o + (a + Vector2(0, float(r[3]))).rotated(rot)])
		var zon: String = str((lot.get("zoning", ["residential"]) as Array)[0])
		_fill(_shrink(poly, 1.5), ZONE_COLORS.get(zon, Color(0.8, 0.8, 0.8)))
		_outline(_shrink(poly, 1.5), Color(0.3, 0.27, 0.22), 1.0)
	for rdv: Variant in fw.get("roads", []):
		var pts: Array = (rdv as Dictionary).get("points", [])
		for k: int in pts.size() - 1:
			_segment(o + _v2(pts[k]).rotated(rot), o + _v2(pts[k + 1]).rotated(rot), Color(0.16, 0.16, 0.17), maxf(2.0, float((rdv as Dictionary).get("width", 6.0)) / _mpp()))


func _place(f: Dictionary) -> void:
	var o: Vector2 = _v2(f.get("origin", [0, 0]))
	var rot: float = deg_to_rad(float(f.get("rotation", 0.0)))
	var pd: PoiDef = null
	var db: Node = ContentDB.instance
	if db != null:
		pd = db.call(&"get_def", &"poi", StringName(str(f.get("poi", "")))) as PoiDef
	var fp: Vector2 = Vector2(pd.footprint) if pd != null else Vector2(24, 24)
	var poly := PackedVector2Array([o, o + Vector2(fp.x, 0).rotated(rot), o + fp.rotated(rot), o + Vector2(0, fp.y).rotated(rot)])
	var c: Vector2 = o + (fp * 0.5).rotated(rot)
	_dot(c, 11.0, Color(0.05, 0.05, 0.05))
	_dot(c, 8.0, Color(0.85, 0.22, 0.16))
	_fill(poly, Color(0.55, 0.12, 0.1))


func _grid(cols: int, rs: float) -> void:
	var line_c := Color(0.0, 0.0, 0.0, 0.35)
	for k: int in range(1, cols):
		var x: float = wr.position.x + k * rs
		_segment(Vector2(x, wr.position.y), Vector2(x, wr.end.y), line_c, 1.0)
		_segment(Vector2(wr.position.x, x), Vector2(wr.end.x, x), line_c, 1.0)
	var scale: int = maxi(2, px / 512)
	for r: int in cols:
		for c: int in cols:
			var label: String = "%s%d" % [char(65 + c), r + 1]
			var at := Vector2i(int((c * rs) / _mpp()) + 6, int((r * rs) / _mpp()) + 6)
			_text(label, at, scale)


func _text(s: String, at: Vector2i, scale: int) -> void:
	var x: int = at.x
	for ch: String in s:
		var g: Array = GLYPHS.get(ch, [])
		img.fill_rect(Rect2i(x - scale, at.y - scale, 4 * scale + scale, 7 * scale), Color(0.0, 0.0, 0.0, 0.55))
		for row: int in g.size():
			for bit: int in 3:
				if (int(g[row]) >> (2 - bit)) & 1:
					img.fill_rect(Rect2i(x + bit * scale, at.y + row * scale, scale, scale), Color(1, 1, 1))
		x += 4 * scale


# --- Primitives --------------------------------------------------------------------------------

func _mpp() -> float:
	return wr.size.x / px


func _to_px(p: Vector2) -> Vector2:
	return (p - wr.position) / _mpp()


func _dot(p: Vector2, d_px: float, c: Color) -> void:
	var q: Vector2 = _to_px(p)
	var r: float = d_px * 0.5
	var x0: int = int(floor(q.x - r))
	var y0: int = int(floor(q.y - r))
	var x1: int = int(ceil(q.x + r))
	var y1: int = int(ceil(q.y + r))
	for y: int in range(maxi(0, y0), mini(px, y1)):
		for x: int in range(maxi(0, x0), mini(px, x1)):
			if Vector2(x + 0.5, y + 0.5).distance_to(q) <= r:
				_blend(x, y, c)


func _disc(p: Vector2, radius_m: float, c: Color) -> void:
	_dot(p, radius_m * 2.0 / _mpp(), c)


func _blend(x: int, y: int, c: Color) -> void:
	if c.a >= 0.999:
		img.set_pixel(x, y, c)
	else:
		img.set_pixel(x, y, img.get_pixel(x, y).lerp(Color(c.r, c.g, c.b), c.a))


func _segment(a: Vector2, b: Vector2, c: Color, w_px: float) -> void:
	var pa: Vector2 = _to_px(a)
	var pb: Vector2 = _to_px(b)
	var steps: int = maxi(1, int(ceil(pa.distance_to(pb) / 0.7)))
	var w: int = maxi(1, int(round(w_px)))
	for s: int in steps + 1:
		var q: Vector2 = pa.lerp(pb, float(s) / steps)
		var rect := Rect2i(int(q.x - w * 0.5), int(q.y - w * 0.5), w, w).intersection(Rect2i(0, 0, px, px))
		if rect.size.x > 0 and rect.size.y > 0:
			if c.a >= 0.999:
				img.fill_rect(rect, c)
			else:
				for y: int in range(rect.position.y, rect.end.y):
					for x: int in range(rect.position.x, rect.end.x):
						_blend(x, y, c)


func _stroke(line: Polyline2, c: Color, w_px: float) -> void:
	for k: int in line.points.size() - 1:
		_segment(line.points[k], line.points[k + 1], c, w_px)


func _dashed(line: Polyline2, c: Color, w_px: float) -> void:
	var s: float = 0.0
	var dash: float = _mpp() * 5.0
	while s < line.total_length:
		_segment(line.point_at(s), line.point_at(minf(s + dash, line.total_length)), c, w_px)
		s += dash * 2.0


func _fill(poly: PackedVector2Array, c: Color) -> void:
	if poly.size() < 3:
		return
	var pts := PackedVector2Array()
	for p: Vector2 in poly:
		pts.append(_to_px(p))
	var y0: int = px
	var y1: int = 0
	for p2: Vector2 in pts:
		y0 = mini(y0, int(floor(p2.y)))
		y1 = maxi(y1, int(ceil(p2.y)))
	for y: int in range(maxi(0, y0), mini(px, y1 + 1)):
		var yc: float = y + 0.5
		var xs: Array[float] = []
		for k: int in pts.size():
			var a: Vector2 = pts[k]
			var b: Vector2 = pts[(k + 1) % pts.size()]
			if (a.y <= yc and b.y > yc) or (b.y <= yc and a.y > yc):
				xs.append(a.x + (yc - a.y) / (b.y - a.y) * (b.x - a.x))
		xs.sort()
		for k2: int in range(0, xs.size() - 1, 2):
			var xa: int = clampi(int(round(xs[k2])), 0, px)
			var xb: int = clampi(int(round(xs[k2 + 1])), 0, px)
			if xb > xa:
				if c.a >= 0.999:
					img.fill_rect(Rect2i(xa, y, xb - xa, 1), c)
				else:
					for x: int in range(xa, xb):
						_blend(x, y, c)


func _outline(poly: PackedVector2Array, c: Color, w_px: float) -> void:
	for k: int in poly.size():
		_segment(poly[k], poly[(k + 1) % poly.size()], c, w_px)


static func _shrink(poly: PackedVector2Array, m: float) -> PackedVector2Array:
	var off: Array = Geometry2D.offset_polygon(poly, -m)
	return off[0] if not off.is_empty() else poly


static func _poly(arr: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p: Variant in arr:
		out.append(_v2(p))
	return out


static func _v2(a: Variant) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))
