class_name TerrainComposer
extends RefCounted
## Builds RegionTerrain from: world macro elevation + world rivers/lakes/roads + the region's local
## features (region.json). Deterministic; shared by the handcrafted main map and RWG (M3), which
## only differ in where world/region JSON comes from.
##
## Pipeline (see ADR-0007):
##   1. macro elevation on an 8 m grid -> bilinear to the fine grid; + world-level detail noise
##   2. hills / cliffs / local lakes (local features fade to zero within BORDER_FADE of the border
##      so neighbouring regions meet seamlessly)
##   3. water distance fields (rivers, lakes) on a 4 m grid -> valley caps, banks, channel beds
##   4. road distance fields -> smoothed centre-line profiles -> flatten (bridges skip water)
##   5. pads for frameworks/POIs (flatten to their mean height + skirt; "keep_water" pads sit a
##      "freeboard" above the lake or river they overlap, grade only dry ground and leave the water)
##   6. biome map, splat weights (8-layer palette), vegetation mask

const VERSION: int = 10
const COARSE: float = 4.0
const MACRO_STEP: float = 8.0
const BORDER_FADE: float = 48.0
const DEFAULT_PALETTE: PackedStringArray = ["forest_floor", "moss_ground", "grass_ground", "dirt", "mud", "gravel", "asphalt_cracked", "sand"]


## Everything that influences the output, hashed. Changing data or VERSION invalidates caches.
static func input_hash(world: WorldDef, region_id: String, spacing: float) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(("v%d|%s|%s|%.3f" % [VERSION, world.id, region_id, spacing]).to_utf8_buffer())
	ctx.update(FileAccess.get_file_as_bytes(world.dir_path.path_join("world.json")))
	var rp: String = world.dir_path.path_join("regions").path_join(region_id).path_join("region.json")
	if FileAccess.file_exists(rp):
		ctx.update(FileAccess.get_file_as_bytes(rp))
		# Frameworks and standalone POIs shape the terrain too (pads, streets): hash their files.
		var region: Variant = JSON.parse_string(FileAccess.get_file_as_string(rp))
		if region is Dictionary:
			for f: Variant in (region as Dictionary).get("features", []):
				if not f is Dictionary:
					continue
				var dep: String = ""
				match str(f.get("type", "")):
					"framework":
						dep = "res://data/pois/frameworks/%s.json" % f.get("framework", "")
					"poi":
						dep = "res://data/pois/buildings/%s.json" % f.get("poi", "")
				if dep != "" and FileAccess.file_exists(dep):
					ctx.update(FileAccess.get_file_as_bytes(dep))
	return ctx.finish().hex_encode()


## Loads from the disk cache or composes (and caches) a region.
static func get_or_compose(world: WorldDef, region_id: String, spacing: float = 1.0, progress: Callable = Callable()) -> RegionTerrain:
	# Without content loaded (a bare `-s` tool), frameworks and POIs can't be resolved: the result
	# lacks pads and streets. Cached under the real input hash, the game then loaded a town with
	# no ground graded for it, so such a compose is never read from or written to the cache.
	if ContentDB.instance == null:
		push_warning("TerrainComposer: no content loaded; composing %s without frameworks or POIs, uncached" % region_id)
		return compose(world, region_id, spacing, progress)
	var h: String = input_hash(world, region_id, spacing)
	var path: String = "user://cache/worlds/%s/%s_%d.bin" % [world.id, region_id, int(spacing * 100)]
	var rt: RegionTerrain = RegionTerrain.load_cached(path, h)
	if rt != null:
		return rt
	rt = compose(world, region_id, spacing, progress)
	if rt != null:
		var err: Error = rt.save(path, h)
		if err != OK:
			push_warning("TerrainComposer: could not cache %s (%s)" % [path, error_string(err)])
	return rt


static func compose(world: WorldDef, region_id: String, spacing: float = 1.0, progress: Callable = Callable()) -> RegionTerrain:
	var b := _Build.new(world, region_id, spacing, progress)
	return b.run()


# =============================================================================================

class _Build:
	var world: WorldDef
	var region_id: String
	var region: Dictionary
	var rect: Rect2
	var sp: float
	var n: int
	var h: PackedFloat32Array
	## Detail-noise component of h (re-added on flattened areas so they keep texture).
	var dnoise: PackedFloat32Array
	var progress: Callable
	var rt: RegionTerrain

	# coarse grid (step cs = max(COARSE, spacing))
	var cs: float
	var cn: int
	var cx0: float
	var cz0: float
	# water fields (coarse)
	var w_d: PackedFloat32Array
	var w_lvl: PackedFloat32Array
	var w_depth: PackedFloat32Array
	var w_bank: PackedFloat32Array
	var w_vw: PackedFloat32Array
	var w_vs: PackedFloat32Array
	var w_kind: PackedByteArray
	# valley field (16 m): distance + level for the wide cone caps around water
	const FAR_STEP: float = 16.0
	var fn_: int
	var fw_d: PackedFloat32Array
	var fw_lvl: PackedFloat32Array
	var fw_vw: PackedFloat32Array
	var fw_vs: PackedFloat32Array
	# road fields (coarse)
	var r_d: PackedFloat32Array
	var r_s: PackedFloat32Array
	var r_idx: PackedInt32Array
	var road_list: Array[Dictionary] = []
	# pads
	var pads: Array[Dictionary] = []
	var clearings: Array[Dictionary] = []
	var paints: Array[Dictionary] = []
	var paths: Array[Dictionary] = []
	var max_band: float = 0.0

	func _init(p_world: WorldDef, p_region_id: String, p_spacing: float, p_progress: Callable) -> void:
		world = p_world
		region_id = p_region_id
		sp = p_spacing
		progress = p_progress
		region = world.region_data(region_id)
		rect = world.region_rect(region_id)
		n = int(round(rect.size.x / sp)) + 1
		cs = maxf(COARSE, sp)
		cn = int(round(rect.size.x / cs)) + 1
		cx0 = rect.position.x
		cz0 = rect.position.y

	func _report(stage: String, t: float) -> void:
		if progress.is_valid():
			progress.call(stage, t)

	func run() -> RegionTerrain:
		if rect.size == Vector2.ZERO:
			push_error("TerrainComposer: unknown region %s" % region_id)
			return null
		rt = RegionTerrain.new()
		rt.region_id = region_id
		rt.rect = rect
		rt.spacing = sp
		rt.palette = PackedStringArray(region.get("palette", DEFAULT_PALETTE))
		_report("macro", 0.0)
		_macro_and_noise()
		_report("features", 0.3)
		_collect_features()
		_hills_and_cliffs()
		_local_lakes_prepass()
		_report("water", 0.45)
		_water_fields()
		_apply_water()
		_report("roads", 0.6)
		_road_fields()
		_apply_roads()
		_report("pads", 0.7)
		_apply_pads()
		var hf := HeightField.new()
		hf.origin = rect.position
		hf.spacing = sp
		hf.width = n
		hf.depth = n
		hf.heights = h
		rt.height = hf
		_report("surface", 0.8)
		_surface_pass()
		_metadata()
		_report("done", 1.0)
		return rt

	# --- 1. Macro + detail noise ---------------------------------------------------------

	func _macro_and_noise() -> void:
		var mn: int = int(round(rect.size.x / MACRO_STEP)) + 1
		var macro := PackedFloat32Array()
		macro.resize(mn * mn)
		for iz: int in mn:
			for ix: int in mn:
				macro[iz * mn + ix] = world.macro_height(cx0 + ix * MACRO_STEP, cz0 + iz * MACRO_STEP)
		var dcfg: Dictionary = region.get("detail_noise", {})
		var layers: Array = dcfg.get("layers", [{"frequency": dcfg.get("frequency", 0.012), "octaves": dcfg.get("octaves", 4), "amplitude": dcfg.get("amplitude", 2.5)}])
		var noises: Array[FastNoiseLite] = []
		var amps := PackedFloat32Array()
		for li: int in layers.size():
			var lc: Dictionary = layers[li]
			var nz := FastNoiseLite.new()
			nz.seed = world.seed + 101 + li * 31
			nz.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
			nz.fractal_type = FastNoiseLite.FRACTAL_FBM
			nz.fractal_octaves = int(lc.get("octaves", 3))
			nz.frequency = float(lc.get("frequency", 0.01))
			noises.append(nz)
			amps.append(float(lc.get("amplitude", 1.0)))
		# Border samples use a world-level default (same in every region) so regions stitch.
		var world_amp: float = 2.5
		var world_noise := FastNoiseLite.new()
		world_noise.seed = world.seed + 101
		world_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		world_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
		world_noise.fractal_octaves = 4
		world_noise.frequency = 0.012
		h.resize(n * n)
		dnoise.resize(n * n)
		var ratio: float = sp / MACRO_STEP
		var nl: int = noises.size()
		for iz: int in n:
			var gz: float = iz * ratio
			var mz: int = mini(int(gz), mn - 2)
			var fz: float = gz - mz
			var z: float = cz0 + iz * sp
			var row: int = iz * n
			for ix: int in n:
				var gx: float = ix * ratio
				var mx: int = mini(int(gx), mn - 2)
				var fx: float = gx - mx
				var i: int = mz * mn + mx
				var top: float = macro[i] + (macro[i + 1] - macro[i]) * fx
				var bot: float = macro[i + mn] + (macro[i + mn + 1] - macro[i + mn]) * fx
				var x: float = cx0 + ix * sp
				var bw: float = _border_weight(x, z)
				var detail: float = 0.0
				if bw > 0.0:
					for li: int in nl:
						detail += noises[li].get_noise_2d(x, z) * amps[li]
				var base_n: float = world_noise.get_noise_2d(x, z) * world_amp
				var dv: float = lerpf(base_n, detail, bw)
				dnoise[row + ix] = dv
				h[row + ix] = top + (bot - top) * fz + dv

	func _border_weight(x: float, z: float) -> float:
		var d: float = minf(minf(x - rect.position.x, rect.end.x - x), minf(z - rect.position.y, rect.end.y - z))
		return clampf(d / BORDER_FADE, 0.0, 1.0)

	# --- 2. Local features ----------------------------------------------------------------

	func _collect_features() -> void:
		for f: Dictionary in region.get("features", []):
			match str(f.get("type", "")):
				"framework", "poi":
					pads.append(_pad_for(f))
				"clearing":
					clearings.append({"pos": _v2(f["pos"]), "r": float(f.get("radius", 10.0))})
				"spawn":
					clearings.append({"pos": _v2(f["pos"]), "r": 8.0})
				"biome":
					paints.append({"biome": str(f["biome"]), "pos": _v2(f["circle"]), "r": float(f.get("radius", 100.0)), "blend": float(f.get("blend", 30.0))})
				"path":
					paths.append({"line": Polyline2.from_array(f["points"]), "width": float(f.get("width", 2.0)), "surface": str(f.get("surface", "dirt"))})

	func _pad_for(f: Dictionary) -> Dictionary:
		var size := Vector2(40, 40)
		var def_id: String = str(f.get("framework", f.get("poi", "")))
		var content: Node = _content()
		if content != null:
			if str(f.get("type")) == "framework":
				var fw: FrameworkDef = content.get_def(&"framework", StringName(def_id)) as FrameworkDef
				if fw != null:
					size = Vector2(fw.size)
			else:
				var pd: PoiDef = content.get_def(&"poi", StringName(def_id)) as PoiDef
				if pd != null:
					size = Vector2(pd.footprint)
		if f.has("size"):
			size = _v2(f["size"])
		return {"kind": str(f["type"]), "def": def_id, "id": str(f.get("id", def_id)), "origin": _v2(f["origin"]),
			"rot": deg_to_rad(float(f.get("rotation", 0.0))), "size": size, "skirt": float(f.get("skirt", 10.0)),
			"biome": str(f.get("biome", "town" if str(f["type"]) == "framework" else "meadow")),
			"keep_water": bool(f.get("keep_water", false)), "freeboard": float(f.get("freeboard", 0.6))}

	func _content() -> Node:
		return ContentDB.instance

	func _hills_and_cliffs() -> void:
		for f: Dictionary in region.get("features", []):
			var t: String = str(f.get("type", ""))
			if t == "hill":
				var c: Vector2 = _v2(f["pos"])
				var r: float = float(f.get("radius", 100.0))
				var ht: float = float(f.get("height", 10.0))
				_for_box(Rect2(c - Vector2(r, r), Vector2(r, r) * 2.0), func(i: int, x: float, z: float) -> void:
					var d: float = Vector2(x, z).distance_to(c) / r
					if d < 1.0:
						var k: float = 0.5 + 0.5 * cos(d * PI)
						h[i] += ht * k * _border_weight(x, z))
			elif t == "cliff":
				_apply_cliff(f)

	func _apply_cliff(f: Dictionary) -> void:
		var line: Polyline2 = Polyline2.from_array(f["points"])
		var ht2: float = float(f.get("height", 15.0))
		var face: float = float(f.get("face_width", 5.0))
		var fall: float = float(f.get("falloff", 60.0))
		var sign_k: float = 1.0 if str(f.get("side", "west")) in ["west", "north"] else -1.0
		var reach: float = fall + face + cs
		var sd_f := PackedFloat32Array()
		sd_f.resize(cn * cn)
		sd_f.fill(1.0e9)
		var arc_f := PackedFloat32Array()
		arc_f.resize(cn * cn)
		var absd := PackedFloat32Array()
		absd.resize(cn * cn)
		absd.fill(1.0e9)
		for si: int in line.points.size() - 1:
			var a: Vector2 = line.points[si]
			var bpt: Vector2 = line.points[si + 1]
			var ab: Vector2 = bpt - a
			var l2: float = maxf(ab.length_squared(), 1e-6)
			var seg_len: float = sqrt(l2)
			var s0: float = line.lengths[si]
			_for_coarse_box(Rect2(a, Vector2.ZERO).expand(bpt).grow(reach), func(ci: int, x: float, z: float) -> void:
				var p := Vector2(x, z)
				var tt: float = clampf((p - a).dot(ab) / l2, 0.0, 1.0)
				var dist: float = p.distance_to(a + ab * tt)
				if dist < absd[ci]:
					absd[ci] = dist
					sd_f[ci] = dist * (1.0 if ab.cross(p - a) >= 0.0 else -1.0) * sign_k
					arc_f[ci] = s0 + seg_len * tt)
		var bb: Rect2 = line.bounds.grow(reach)
		var ratio: float = sp / cs
		_for_box(bb, func(i: int, x: float, z: float) -> void:
			var gx: float = (x - cx0) / cs
			var gz: float = (z - cz0) / cs
			var cx: int = clampi(int(gx), 0, cn - 2)
			var cz: int = clampi(int(gz), 0, cn - 2)
			var ci: int = cz * cn + cx
			if absd[ci] > 1.0e8 and absd[ci + cn + 1] > 1.0e8:
				return
			var sd: float = _bl(sd_f, ci, gx - cx, gz - cz)
			if sd > 1.0e8:
				return
			var arc: float = arc_f[ci]
			var end_taper: float = smoothstep(0.0, 40.0, arc) * smoothstep(0.0, 40.0, line.total_length - arc)
			var rise: float = smoothstep(-face * 0.5, face * 0.5, sd)
			var back: float = 1.0 - smoothstep(fall * 0.4, fall, sd)
			h[i] += ht2 * rise * back * end_taper * _border_weight(x, z))

	## Local lakes: resolve "auto" levels before water fields are built.
	func _local_lakes_prepass() -> void:
		for f: Dictionary in region.get("features", []):
			if str(f.get("type", "")) != "lake":
				continue
			if str(f.get("level", "auto")) == "auto":
				var c: Vector2 = _v2(f["ellipse"]) if f.has("ellipse") else _poly_centroid(f["polygon"])
				var acc: float = 0.0
				for k: int in 9:
					var o := Vector2(cos(k * 0.7), sin(k * 0.7)) * float(k) * 4.0
					acc += _sample(c.x + o.x, c.y + o.y)
				f["_level"] = acc / 9.0 - 1.8
			else:
				f["_level"] = float(f["level"])

	# --- 3. Water ---------------------------------------------------------------------------

	func _water_fields() -> void:
		var count: int = cn * cn
		w_d = PackedFloat32Array()
		w_d.resize(count)
		w_d.fill(1.0e9)
		w_lvl = PackedFloat32Array()
		w_lvl.resize(count)
		w_depth = PackedFloat32Array()
		w_depth.resize(count)
		w_bank = PackedFloat32Array()
		w_bank.resize(count)
		w_vw = PackedFloat32Array()
		w_vw.resize(count)
		w_vs = PackedFloat32Array()
		w_vs.resize(count)
		w_kind = PackedByteArray()
		w_kind.resize(count)
		fn_ = int(round(rect.size.x / FAR_STEP)) + 1
		fw_d = PackedFloat32Array()
		fw_d.resize(fn_ * fn_)
		fw_d.fill(1.0e9)
		fw_lvl = PackedFloat32Array()
		fw_lvl.resize(fn_ * fn_)
		fw_vw = PackedFloat32Array()
		fw_vw.resize(fn_ * fn_)
		fw_vs = PackedFloat32Array()
		fw_vs.resize(fn_ * fn_)
		for r: Dictionary in world.rivers:
			_rasterize_river(r)
		for l: Dictionary in world.lakes:
			_rasterize_lake_polygon(l["polygon"], float(l["level"]), float(l["depth"]), float(l["shore"]), 160.0, 0.2)
		for f: Dictionary in region.get("features", []):
			if str(f.get("type", "")) == "lake":
				var poly: PackedVector2Array = _lake_poly(f)
				_rasterize_lake_polygon(poly, float(f["_level"]), float(f.get("depth", 4.0)), float(f.get("shore", 12.0)), 50.0, 0.22)

	func _rasterize_river(r: Dictionary) -> void:
		var line: Polyline2 = r["line"]
		var vw: float = float(r["valley_width"])
		var max_w: float = 0.0
		for wv: Variant in (r["width"] if r["width"] is Array else [r["width"]]):
			max_w = maxf(max_w, float(wv))
		var near_reach: float = max_w * 0.5 + float(r["bank"]) + 12.0
		var far_reach: float = max_w * 0.5 + vw + FAR_STEP
		if not line.bounds.grow(far_reach).intersects(rect):
			return
		var lvl_v: Variant = r["level"]
		var w_v: Variant = r["width"]
		var depth: float = float(r["depth"])
		var bank: float = float(r["bank"])
		var vs: float = float(r["valley_slope"])
		for si: int in line.points.size() - 1:
			var a: Vector2 = line.points[si]
			var bpt: Vector2 = line.points[si + 1]
			var ab: Vector2 = bpt - a
			var l2: float = maxf(ab.length_squared(), 1e-6)
			var seg_len: float = sqrt(l2)
			var s0: float = line.lengths[si]
			var base_box := Rect2(a, Vector2.ZERO).expand(bpt)
			if not base_box.grow(far_reach).intersects(rect):
				continue
			# Near band: exact channel/bank values at 4 m.
			_for_coarse_box(base_box.grow(near_reach), func(ci: int, x: float, z: float) -> void:
				var p := Vector2(x, z)
				var t: float = clampf((p - a).dot(ab) / l2, 0.0, 1.0)
				var sv: float = s0 + seg_len * t
				var d: float = p.distance_to(a + ab * t) - line.value_at(w_v, sv) * 0.5
				if d < w_d[ci]:
					w_d[ci] = d
					w_lvl[ci] = line.value_at(lvl_v, sv)
					w_depth[ci] = depth
					w_bank[ci] = bank
					w_vw[ci] = vw
					w_vs[ci] = vs
					w_kind[ci] = 1)
			# Valley: coarse cone-cap inputs at 16 m.
			_for_far_box(base_box.grow(far_reach), func(fi: int, x: float, z: float) -> void:
				var p := Vector2(x, z)
				var t: float = clampf((p - a).dot(ab) / l2, 0.0, 1.0)
				var sv: float = s0 + seg_len * t
				var d: float = p.distance_to(a + ab * t) - line.value_at(w_v, sv) * 0.5
				if d < fw_d[fi]:
					fw_d[fi] = d
					fw_lvl[fi] = line.value_at(lvl_v, sv)
					fw_vw[fi] = vw
					fw_vs[fi] = vs)

	func _rasterize_lake_polygon(poly: PackedVector2Array, level: float, depth: float, shore: float, valley: float, slope: float) -> void:
		var bb := Rect2(poly[0], Vector2.ZERO)
		for p: Vector2 in poly:
			bb = bb.expand(p)
		bb = bb.grow(shore + valley + 8.0)
		if not bb.intersects(rect):
			return
		_for_coarse_box(bb, func(ci: int, x: float, z: float) -> void:
			var p := Vector2(x, z)
			var d: float = _poly_edge_distance(poly, p)
			if Geometry2D.is_point_in_polygon(p, poly):
				d = -d
			if d < w_d[ci]:
				w_d[ci] = d
				w_lvl[ci] = level
				w_depth[ci] = depth
				w_bank[ci] = shore
				w_vw[ci] = valley
				w_vs[ci] = slope
				w_kind[ci] = 2)
		_for_far_box(bb, func(fi: int, x: float, z: float) -> void:
			var p := Vector2(x, z)
			var d: float = _poly_edge_distance(poly, p)
			if Geometry2D.is_point_in_polygon(p, poly):
				d = -d
			if d < fw_d[fi]:
				fw_d[fi] = d
				fw_lvl[fi] = level
				fw_vw[fi] = valley
				fw_vs[fi] = slope)

	func _apply_water() -> void:
		var ratio: float = sp / cs
		var fratio: float = sp / FAR_STEP
		for iz: int in n:
			var gz: float = iz * ratio
			var cz: int = mini(int(gz), cn - 2)
			var fz: float = gz - cz
			var fgz: float = iz * fratio
			var fcz: int = mini(int(fgz), fn_ - 2)
			var ffz: float = fgz - fcz
			var row: int = iz * n
			for ix: int in n:
				var fgx: float = ix * fratio
				var fcx: int = mini(int(fgx), fn_ - 2)
				var fi: int = fcz * fn_ + fcx
				if fw_d[fi] > fw_vw[fi] + FAR_STEP * 1.5 and fw_d[fi + fn_ + 1] > fw_vw[fi + fn_ + 1] + FAR_STEP * 1.5:
					continue
				var hv: float = h[row + ix]
				var fd: float = _blf(fw_d, fi, fgx - fcx, ffz)
				if fd < 1.0e8:
					var vw: float = fw_vw[fi]
					if fd < vw:
						var flvl: float = _blf(fw_lvl, fi, fgx - fcx, ffz)
						var nd: float = dnoise[row + ix] * clampf(fd / 25.0, 0.15, 0.8)
						var cap: float = flvl + 0.5 + maxf(fd, 0.0) * fw_vs[fi] + nd
						var wv: float = 1.0 - smoothstep(vw * 0.55, vw, fd)
						hv = lerpf(hv, minf(hv, cap), wv)
				var gx: float = ix * ratio
				var cx: int = mini(int(gx), cn - 2)
				var ci: int = cz * cn + cx
				if w_d[ci] < 1.0e8 or w_d[ci + cn + 1] < 1.0e8:
					var d: float = _bl(w_d, ci, gx - cx, fz)
					if d < 1.0e8:
						var lvl: float = _bl(w_lvl, ci, gx - cx, fz)
						var bank: float = w_bank[ci]
						if d < 0.0:
							var f: float = clampf(-d / maxf(3.0, bank * 0.9), 0.0, 1.0)
							var bed: float = lvl - 0.35 - w_depth[ci] * (f * f * (3.0 - 2.0 * f))
							hv = minf(hv, bed)
						elif d < bank:
							var t: float = smoothstep(0.0, bank, d)
							var shore_h: float = lvl + 0.22 + d * 0.06
							hv = lerpf(shore_h, maxf(hv, shore_h), t)
				h[row + ix] = hv

	func _blf(f: PackedFloat32Array, fi: int, fx: float, fz: float) -> float:
		var a: float = f[fi]
		var b: float = f[fi + 1]
		var c: float = f[fi + fn_]
		var d: float = f[fi + fn_ + 1]
		if a > 1.0e8 or b > 1.0e8 or c > 1.0e8 or d > 1.0e8:
			return minf(minf(a, b), minf(c, d))
		var top: float = a + (b - a) * fx
		var bot: float = c + (d - c) * fx
		return top + (bot - top) * fz

	func _for_far_box(box: Rect2, fn: Callable) -> void:
		var r: Rect2 = box.intersection(rect.grow(FAR_STEP))
		if r.size.x <= 0.0 or r.size.y <= 0.0:
			return
		var ix0: int = clampi(int(floor((r.position.x - cx0) / FAR_STEP)), 0, fn_ - 1)
		var ix1: int = clampi(int(ceil((r.end.x - cx0) / FAR_STEP)), 0, fn_ - 1)
		var iz0: int = clampi(int(floor((r.position.y - cz0) / FAR_STEP)), 0, fn_ - 1)
		var iz1: int = clampi(int(ceil((r.end.y - cz0) / FAR_STEP)), 0, fn_ - 1)
		for iz: int in range(iz0, iz1 + 1):
			var z: float = cz0 + iz * FAR_STEP
			for ix: int in range(ix0, ix1 + 1):
				fn.call(iz * fn_ + ix, cx0 + ix * FAR_STEP, z)

	# --- 4. Roads ---------------------------------------------------------------------------

	func _road_fields() -> void:
		for r: Dictionary in world.roads:
			road_list.append({"id": r["id"], "line": r["line"], "width": r["width"], "shoulder": r["shoulder"],
				"surface": r["surface"], "bridges": r.get("bridges", []), "world": true, "markings": bool(r.get("markings", true))})
		for f: Dictionary in region.get("features", []):
			if str(f.get("type", "")) == "road":
				road_list.append({"id": str(f.get("id", "road")), "line": Polyline2.from_array(f["points"]),
					"width": float(f.get("width", 5.0)), "shoulder": float(f.get("shoulder", 1.5)),
					"surface": str(f.get("surface", "gravel")), "bridges": f.get("bridges", []), "world": false,
					"markings": bool(f.get("markings", true))})
			elif str(f.get("type", "")) == "framework":
				_framework_roads(f)
		var count: int = cn * cn
		r_d = PackedFloat32Array()
		r_d.resize(count)
		r_d.fill(1.0e9)
		r_s = PackedFloat32Array()
		r_s.resize(count)
		r_idx = PackedInt32Array()
		r_idx.resize(count)
		r_idx.fill(-1)
		for ri: int in road_list.size():
			var r: Dictionary = road_list[ri]
			var line: Polyline2 = r["line"]
			var reach: float = float(r["width"]) * 0.5 + float(r["shoulder"]) + 10.0
			max_band = maxf(max_band, reach)
			if not line.bounds.grow(reach).intersects(rect):
				continue
			_build_profile(r)
			for si: int in line.points.size() - 1:
				var a: Vector2 = line.points[si]
				var bpt: Vector2 = line.points[si + 1]
				var seg := Rect2(a, Vector2.ZERO).expand(bpt).grow(reach)
				var ab: Vector2 = bpt - a
				var l2: float = maxf(ab.length_squared(), 1e-6)
				var seg_len: float = sqrt(l2)
				var s0: float = line.lengths[si]
				var idx: int = ri
				_for_coarse_box(seg, func(ci: int, x: float, z: float) -> void:
					var p := Vector2(x, z)
					var t: float = clampf((p - a).dot(ab) / l2, 0.0, 1.0)
					var dist: float = p.distance_to(a + ab * t)
					if dist < r_d[ci]:
						r_d[ci] = dist
						r_s[ci] = s0 + seg_len * t
						r_idx[ci] = idx)

	## Streets of a placed framework (FrameworkDef.roads, framework-local) become region roads.
	func _framework_roads(f: Dictionary) -> void:
		var content: Node = _content()
		if content == null:
			return
		var fw: FrameworkDef = content.get_def(&"framework", StringName(str(f.get("framework", "")))) as FrameworkDef
		if fw == null:
			return
		var o: Vector2 = _v2(f["origin"])
		var rot: float = deg_to_rad(float(f.get("rotation", 0.0)))
		var i: int = 0
		for r: Variant in fw.roads:
			if not r is Dictionary:
				continue
			var pts: Array = []
			for p: Variant in (r as Dictionary).get("points", []):
				var w: Vector2 = o + Vector2(float(p[0]), float(p[1])).rotated(rot)
				pts.append([w.x, w.y])
			if pts.size() < 2:
				continue
			road_list.append({"id": "%s_street%d" % [str(f.get("id", "fw")), i], "line": Polyline2.from_array(pts),
				"width": float(r.get("width", 6.0)), "shoulder": float(r.get("shoulder", 1.0)),
				"surface": str(r.get("surface", "asphalt")), "bridges": [], "world": false, "markings": bool(r.get("markings", true))})
			i += 1

	## Road height profile along the centre line: terrain sampled every 4 m, smoothed; bridge spans
	## are lifted to the deck height with ramps.
	func _build_profile(r: Dictionary) -> void:
		var line: Polyline2 = r["line"]
		var step: float = 4.0
		var count: int = int(ceil(line.total_length / step)) + 1
		var prof := PackedFloat32Array()
		prof.resize(count)
		for k: int in count:
			var p: Vector2 = line.point_at(k * step)
			prof[k] = _sample_or_macro(p.x, p.y)
		# Smooth (moving average, 3 passes ~ gaussian, window ~ 36 m).
		for pass_i: int in 3:
			var cp: PackedFloat32Array = prof.duplicate()
			for k: int in count:
				var acc: float = 0.0
				var wsum: float = 0.0
				for o: int in range(-4, 5):
					var j: int = clampi(k + o, 0, count - 1)
					acc += cp[j]
					wsum += 1.0
				prof[k] = acc / wsum
		var spans: Array = []
		for bdef: Variant in r["bridges"]:
			var bd: Dictionary = bdef
			var s0: float = line.closest(_v2(bd["from"])).y
			var s1: float = line.closest(_v2(bd["to"])).y
			if s1 < s0:
				var tmp: float = s0
				s0 = s1
				s1 = tmp
			var deck: float
			if str(bd.get("deck", "auto")) == "auto":
				var mid: Vector2 = line.point_at((s0 + s1) * 0.5)
				var water_lvl: float = _water_level_near(mid)
				deck = maxf(maxf(prof[int(s0 / step)], prof[mini(int(s1 / step), count - 1)]), water_lvl + 4.5)
			else:
				deck = float(bd["deck"])
			spans.append([s0, s1, deck])
			# Ramps 40 m each side up to the deck.
			for k: int in count:
				var s: float = k * step
				if s >= s0 and s <= s1:
					prof[k] = deck
				elif s > s0 - 40.0 and s < s0:
					prof[k] = lerpf(prof[k], deck, smoothstep(s0 - 40.0, s0, s))
				elif s > s1 and s < s1 + 40.0:
					prof[k] = lerpf(deck, prof[k], smoothstep(s1, s1 + 40.0, s))
		r["profile"] = prof
		r["step"] = step
		r["spans"] = spans

	func _water_level_near(p: Vector2) -> float:
		var best: float = -1.0e9
		for r: Dictionary in world.rivers:
			var line: Polyline2 = r["line"]
			var q: Vector3 = line.closest(p)
			if q.x < 60.0:
				best = maxf(best, line.value_at(r["level"], q.y))
		return best

	func _apply_roads() -> void:
		var ratio: float = sp / cs
		for iz: int in n:
			var gz: float = iz * ratio
			var cz: int = mini(int(gz), cn - 2)
			var fz: float = gz - cz
			var row: int = iz * n
			for ix: int in n:
				var gx: float = ix * ratio
				var cx: int = mini(int(gx), cn - 2)
				var ci: int = cz * cn + cx
				var ri: int = r_idx[ci]
				if ri < 0:
					ri = r_idx[ci + cn + 1]
					if ri < 0:
						continue
				var fx: float = gx - cx
				var d: float
				var s: float
				if r_idx[ci] == r_idx[ci + 1] and r_idx[ci] == r_idx[ci + cn] and r_idx[ci] == r_idx[ci + cn + 1]:
					d = _bl(r_d, ci, fx, fz)
					s = _bl(r_s, ci, fx, fz)
				else:
					var nci: int = ci + (1 if fx > 0.5 else 0) + (cn if fz > 0.5 else 0)
					if r_idx[nci] >= 0:
						ri = r_idx[nci]
					d = r_d[nci]
					s = r_s[nci]
				var r: Dictionary = road_list[ri]
				var half: float = float(r["width"]) * 0.5
				var outer: float = half + float(r["shoulder"]) + 8.0
				if d > outer or not r.has("spans"):
					continue
				var skip: bool = false
				for span: Array in r["spans"]:
					if s > float(span[0]) + 2.0 and s < float(span[1]) - 2.0:
						skip = true
						break
				if skip:
					continue
				var prof: PackedFloat32Array = r["profile"]
				var step: float = r["step"]
				var k: float = s / step
				var k0: int = clampi(int(k), 0, prof.size() - 1)
				var k1: int = mini(k0 + 1, prof.size() - 1)
				var target: float = lerpf(prof[k0], prof[k1], k - k0)
				target -= 0.06 * minf(1.0, (d / maxf(half, 0.5)) * (d / maxf(half, 0.5)))
				var inner: float = half + float(r["shoulder"])
				var wgt: float = 1.0 - smoothstep(inner, outer, d)
				if not bool(r["world"]):
					wgt *= _border_weight(cx0 + ix * sp, cz0 + iz * sp)
				h[row + ix] = lerpf(h[row + ix], target, wgt)

	# --- 5. Pads ----------------------------------------------------------------------------

	func _apply_pads() -> void:
		for pad: Dictionary in pads:
			var o: Vector2 = pad["origin"]
			var size: Vector2 = pad["size"]
			var rot: float = pad["rot"]
			var skirt: float = pad["skirt"]
			# A pad that keeps its water (a boathouse slip or a dock out over a lake, ADR-0024) grades
			# only the dry ground, and the lake or river under it keeps its bed instead of being filled
			# to the pad. Its height is the water's plus a freeboard, not the ground's mean: the POI's
			# docks, piles and boats are authored against the water, which an "auto" lake level moves.
			var keep_water: bool = pad["keep_water"]
			# Mean height over the pad.
			var acc: float = 0.0
			var cnt: int = 0
			var wet_lvl: float = 0.0
			var wet_cnt: int = 0
			for k: int in 25:
				var lp := Vector2((k % 5 + 0.5) / 5.0 * size.x, (k / 5 + 0.5) / 5.0 * size.y)
				var wp: Vector2 = o + lp.rotated(rot)
				acc += _sample(wp.x, wp.y)
				cnt += 1
				if keep_water and _water_d(wp.x, wp.y) < 0.0:
					wet_lvl += _water_field(w_lvl, wp.x, wp.y)
					wet_cnt += 1
			var target: float = acc / cnt + 0.05
			if wet_cnt > 0:
				target = wet_lvl / wet_cnt + float(pad["freeboard"])
			pad["height"] = target
			var corners: Array[Vector2] = [o, o + Vector2(size.x, 0).rotated(rot), o + size.rotated(rot), o + Vector2(0, size.y).rotated(rot)]
			var bb := Rect2(corners[0], Vector2.ZERO)
			for c: Vector2 in corners:
				bb = bb.expand(c)
			bb = bb.grow(skirt)
			_for_box(bb, func(i: int, x: float, z: float) -> void:
				var lp: Vector2 = (Vector2(x, z) - o).rotated(-rot)
				var dx: float = maxf(maxf(-lp.x, lp.x - size.x), 0.0)
				var dz: float = maxf(maxf(-lp.y, lp.y - size.y), 0.0)
				var d: float = sqrt(dx * dx + dz * dz)
				if d < skirt:
					var wgt: float = 1.0 - smoothstep(0.0, skirt, d)
					if keep_water:
						# Nothing in the water; the dry ground eases down to the bank over its last 2 m
						# rather than standing over the water as a step.
						wgt *= smoothstep(0.0, 2.0, _water_d(x, z))
					h[i] = lerpf(h[i], target, wgt * _border_weight(x, z)))

	# --- 6. Surface: biome, splat, vegetation ---------------------------------------------------

	func _surface_pass() -> void:
		var biomes: PackedStringArray = [str(region.get("default_biome", "conifer_forest")), "riverbank", "rocky_slope", "town", "meadow", "birch_grove"]
		for p: Dictionary in paints:
			if not biomes.has(p["biome"]):
				biomes.append(p["biome"])
		for pad: Dictionary in pads:
			if not biomes.has(pad["biome"]):
				biomes.append(pad["biome"])
		rt.biome_ids = biomes
		var pal: PackedStringArray = rt.palette
		var L_FOREST: int = pal.find("forest_floor")
		var L_MOSS: int = pal.find("moss_ground")
		var L_GRASS: int = pal.find("grass_ground")
		var L_DIRT: int = pal.find("dirt")
		var L_MUD: int = pal.find("mud")
		var L_GRAVEL: int = pal.find("gravel")
		var L_ASPHALT: int = pal.find("asphalt_cracked")
		var L_SAND: int = pal.find("sand")
		var count: int = n * n
		rt.splat0.resize(count * 4)
		rt.splat1.resize(count * 4)
		rt.biome.resize(count)
		rt.vegmask.resize(count)
		var pn := FastNoiseLite.new()
		pn.seed = world.seed + 202
		pn.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		pn.fractal_type = FastNoiseLite.FRACTAL_FBM
		pn.fractal_octaves = 3
		pn.frequency = 0.035
		# Patch noise on the coarse grid (two channels), bilinear per sample.
		var p1 := PackedFloat32Array()
		var p2 := PackedFloat32Array()
		p1.resize(cn * cn)
		p2.resize(cn * cn)
		for cz: int in cn:
			for cx: int in cn:
				var x: float = cx0 + cx * cs
				var z: float = cz0 + cz * cs
				p1[cz * cn + cx] = pn.get_noise_2d(x, z) * 0.5 + 0.5
				p2[cz * cn + cx] = pn.get_noise_2d(x + 913.0, z - 377.0) * 0.5 + 0.5
		var w := PackedFloat32Array()
		w.resize(8)
		var ratio: float = sp / cs
		var b_default: int = 0
		for iz: int in n:
			var gz: float = iz * ratio
			var cz2: int = mini(int(gz), cn - 2)
			var fz: float = gz - cz2
			var z: float = cz0 + iz * sp
			var row: int = iz * n
			for ix: int in n:
				var gx: float = ix * ratio
				var cx2: int = mini(int(gx), cn - 2)
				var fx: float = gx - cx2
				var ci: int = cz2 * cn + cx2
				var x: float = cx0 + ix * sp
				var i: int = row + ix
				var n1: float = _bl(p1, ci, fx, fz)
				var n2: float = _bl(p2, ci, fx, fz)
				# Slope from neighbours.
				var hl: float = h[row + maxi(ix - 1, 0)]
				var hr: float = h[row + mini(ix + 1, n - 1)]
				var hu: float = h[maxi(iz - 1, 0) * n + ix]
				var hd: float = h[mini(iz + 1, n - 1) * n + ix]
				var grad: float = sqrt((hr - hl) * (hr - hl) + (hd - hu) * (hd - hu)) / (2.0 * sp)
				var slope: float = rad_to_deg(atan(grad))
				# Biome.
				var bi: int = b_default
				for pidx: int in paints.size():
					var pt: Dictionary = paints[pidx]
					var dd: float = Vector2(x, z).distance_to(pt["pos"]) + (n1 - 0.5) * float(pt["blend"]) * 1.6
					if dd < float(pt["r"]):
						bi = biomes.find(pt["biome"])
				var wd: float = 1.0e9
				var wl: float = 0.0
				var wk: int = 0
				if w_d[ci] < 60.0 or w_d[ci + cn + 1] < 60.0:
					wd = _bl(w_d, ci, fx, fz)
					wl = _bl(w_lvl, ci, fx, fz)
					wk = w_kind[ci]
				if wd < 14.0 + n2 * 10.0:
					bi = 1
				var pad_hit: int = _pad_at(x, z)
				if pad_hit >= 0:
					bi = biomes.find(pads[pad_hit]["biome"])
				if slope > 34.0 + n1 * 6.0:
					bi = 2
				rt.biome[i] = bi
				# Splat weights.
				w.fill(0.0)
				var bname: String = biomes[bi]
				match bname:
					"conifer_forest":
						_add(w, L_FOREST, 1.0)
						_add(w, L_MOSS, smoothstep(0.45, 0.75, n1) * 0.9)
						_add(w, L_DIRT, smoothstep(0.7, 0.9, n2) * 0.35)
					"birch_grove":
						_add(w, L_GRASS, 0.8)
						_add(w, L_FOREST, smoothstep(0.4, 0.7, n1))
						_add(w, L_MOSS, smoothstep(0.65, 0.85, n2) * 0.5)
					"meadow":
						_add(w, L_GRASS, 1.0)
						_add(w, L_DIRT, smoothstep(0.68, 0.9, n2) * 0.45)
					"town":
						_add(w, L_GRASS, 0.9)
						_add(w, L_DIRT, smoothstep(0.55, 0.8, n1) * 0.6)
						_add(w, L_GRAVEL, smoothstep(0.7, 0.9, n2) * 0.5)
					"riverbank":
						_add(w, L_GRASS, smoothstep(2.0, 12.0, wd))
						_add(w, L_GRAVEL, 1.0 - smoothstep(1.0, 6.0 + n1 * 4.0, wd))
						_add(w, L_MUD, (1.0 - smoothstep(0.0, 9.0, absf(wd - 3.0))) * smoothstep(0.35, 0.6, n2))
					"rocky_slope":
						_add(w, L_GRAVEL, 0.8)
						_add(w, L_DIRT, 0.5)
						_add(w, L_MOSS, smoothstep(0.6, 0.8, n1) * 0.4)
					_:
						_add(w, L_FOREST, 1.0)
				if wk == 2 and wd < 6.0 + n1 * 3.0:
					# Forest lakes and ponds have muddy, stony margins with the odd sandy cove: a sand
					# ring all the way round read as a beach, and from the trees as a bleached halo.
					var shore: float = 1.0 - smoothstep(-2.0, 6.0, wd)
					var cove: float = smoothstep(0.6, 0.78, n2)
					_add(w, L_SAND, shore * 1.5 * cove)
					_add(w, L_MUD, shore * 1.2 * (1.0 - cove) * (0.45 + 0.55 * smoothstep(0.3, 0.65, n1)))
					_add(w, L_GRAVEL, shore * 0.7 * (1.0 - cove))
				if wd < 0.0:
					w.fill(0.0)
					_add(w, L_MUD, 0.7)
					_add(w, L_GRAVEL, 0.5 + n2 * 0.5)
				var veg: float = 1.0
				if wd < 2.0:
					# Sedges and horsetail grow right down to the waterline (and a little into it);
					# thinning them over the last two metres left a bare ring round every shore.
					veg = 0.0 if wd < -0.25 else 0.4 + 0.6 * smoothstep(-0.25, 2.0, wd)
				# Roads.
				var ri: int = r_idx[ci]
				if ri < 0:
					ri = r_idx[ci + cn + 1]
				if ri >= 0:
					var rd: float = _bl(r_d, ci, fx, fz)
					var r: Dictionary = road_list[ri]
					var half: float = float(r["width"]) * 0.5
					var sh: float = float(r["shoulder"])
					var on_road: float = 1.0 - smoothstep(half - 0.6 + n2 * 0.8, half + 0.4 + n2 * 0.8, rd)
					var on_sh: float = (1.0 - smoothstep(half + sh * 0.5, half + sh + 1.0, rd)) * (1.0 - on_road)
					if on_road > 0.0 or on_sh > 0.0:
						var surf: int = L_ASPHALT if str(r["surface"]) == "asphalt" else (L_GRAVEL if str(r["surface"]) == "gravel" else L_DIRT)
						for c: int in 8:
							w[c] *= (1.0 - on_road) * (1.0 - on_sh * 0.6)
						_add(w, surf, on_road * 2.0)
						_add(w, L_GRAVEL if surf != L_GRAVEL else L_DIRT, on_sh * 1.2)
					veg = minf(veg, smoothstep(half + sh * 0.5, half + sh + 3.0, rd))
				# Paths.
				for path: Dictionary in paths:
					var pl: Polyline2 = path["line"]
					if not pl.bounds.grow(6.0).has_point(Vector2(x, z)):
						continue
					var pd: float = pl.closest(Vector2(x, z)).x
					var pw: float = float(path["width"]) * 0.5 + (n2 - 0.5) * 0.8
					if pd < pw + 1.5:
						var pk: float = 1.0 - smoothstep(pw - 0.4, pw + 1.2, pd)
						for c: int in 8:
							w[c] *= 1.0 - pk * 0.8
						_add(w, L_DIRT, pk * 1.5)
						veg = minf(veg, smoothstep(pw - 0.3, pw + 1.5, pd))
				if pad_hit >= 0:
					veg = 0.0
				for cl: Dictionary in clearings:
					var dc: float = Vector2(x, z).distance_to(cl["pos"])
					if dc < float(cl["r"]) + 6.0:
						veg = minf(veg, smoothstep(float(cl["r"]), float(cl["r"]) + 6.0, dc))
				# Normalize + quantize.
				var total: float = 0.0
				for c: int in 8:
					total += w[c]
				if total <= 0.0:
					w[maxi(L_FOREST, 0)] = 1.0
					total = 1.0
				var o4: int = i * 4
				for c: int in 4:
					rt.splat0[o4 + c] = int(round(w[c] / total * 255.0))
					rt.splat1[o4 + c] = int(round(w[c + 4] / total * 255.0))
				rt.vegmask[i] = int(round(clampf(veg, 0.0, 1.0) * 255.0))

	func _pad_at(x: float, z: float) -> int:
		for pi: int in pads.size():
			var pad: Dictionary = pads[pi]
			var lp: Vector2 = (Vector2(x, z) - (pad["origin"] as Vector2)).rotated(-float(pad["rot"]))
			var size: Vector2 = pad["size"]
			if lp.x >= -1.0 and lp.y >= -1.0 and lp.x <= size.x + 1.0 and lp.y <= size.y + 1.0:
				return pi
		return -1

	static func _add(w: PackedFloat32Array, layer: int, amount: float) -> void:
		if layer >= 0 and amount > 0.0:
			w[layer] += amount

	# --- Metadata ----------------------------------------------------------------------------

	func _metadata() -> void:
		var hf: HeightField = rt.height
		var margin: Rect2 = rect.grow(64.0)
		for r: Dictionary in world.rivers:
			var line: Polyline2 = r["line"]
			if not line.bounds.grow(64.0).intersects(margin):
				continue
			var pts: Array = []
			var widths: Array = []
			var levels: Array = []
			var arcs: Array = []
			var s: float = 0.0
			while s <= line.total_length:
				var p: Vector2 = line.point_at(s)
				if margin.has_point(p):
					pts.append([p.x, p.y])
					widths.append(line.value_at(r["width"], s))
					levels.append(line.value_at(r["level"], s))
					arcs.append(s)
				s += 6.0
			if pts.size() > 1:
				rt.water.append({"kind": "river", "id": r["id"], "points": pts, "widths": widths, "levels": levels, "arcs": arcs})
		for l: Dictionary in world.lakes:
			if (l["bounds"] as Rect2).intersects(margin):
				rt.water.append({"kind": "lake", "id": l["id"], "level": l["level"], "polygon": _poly_to_array(l["polygon"])})
		for f: Dictionary in region.get("features", []):
			match str(f.get("type", "")):
				"lake":
					var poly: PackedVector2Array = _lake_poly(f)
					rt.water.append({"kind": "lake", "id": str(f.get("id", "lake")), "level": float(f["_level"]), "polygon": _poly_to_array(poly)})
				"spawn":
					var sp2: Vector2 = _v2(f["pos"])
					rt.spawns[str(f["id"])] = {"pos": [sp2.x, hf.sample(sp2.x, sp2.y), sp2.y], "yaw": float(f.get("yaw", 0.0)), "props": f.get("props", [])}
				"frontier":
					rt.frontiers.append(f)
		for pad: Dictionary in pads:
			var o: Vector2 = pad["origin"]
			rt.placements.append({"kind": pad["kind"], "def": pad["def"], "id": pad["id"], "origin": [o.x, float(pad.get("height", hf.sample(o.x, o.y))), o.y],
				"rotation": rad_to_deg(float(pad["rot"])), "size": [pad["size"].x, pad["size"].y]})
		for r: Dictionary in road_list:
			var line: Polyline2 = r["line"]
			if not line.bounds.grow(16.0).intersects(margin) or not r.has("profile"):
				continue
			var pts: Array = []
			var prof: PackedFloat32Array = r["profile"]
			for k: int in prof.size():
				var p: Vector2 = line.point_at(k * float(r["step"]))
				if margin.has_point(p):
					pts.append([p.x, prof[k], p.y])
			rt.roads.append({"id": r["id"], "surface": r["surface"], "width": r["width"], "points": pts, "markings": r.get("markings", true)})
			for span: Array in r["spans"]:
				var a: Vector2 = line.point_at(float(span[0]))
				var bpt: Vector2 = line.point_at(float(span[1]))
				rt.bridges.append({"road": r["id"], "from": [a.x, float(span[2]), a.y], "to": [bpt.x, float(span[2]), bpt.y], "width": float(r["width"]) + 1.0})

	# --- Helpers -----------------------------------------------------------------------------

	func _bl(f: PackedFloat32Array, ci: int, fx: float, fz: float) -> float:
		var a: float = f[ci]
		var b: float = f[ci + 1]
		var c: float = f[ci + cn]
		var d: float = f[ci + cn + 1]
		# Distance fields use 1e9 as "far": avoid smearing it into neighbours.
		if a > 1.0e8 or b > 1.0e8 or c > 1.0e8 or d > 1.0e8:
			return minf(minf(a, b), minf(c, d))
		var top: float = a + (b - a) * fx
		var bot: float = c + (d - c) * fx
		return top + (bot - top) * fz

	## Signed distance (m) from (x, z) to the nearest lake or river edge, negative in the water and
	## huge far from any (the coarse water field, bilinear, as _apply_water carved it).
	func _water_d(x: float, z: float) -> float:
		return _water_field(w_d, x, z)

	## A coarse water field (w_d, w_lvl) sampled bilinearly at (x, z).
	func _water_field(f: PackedFloat32Array, x: float, z: float) -> float:
		var gx: float = clampf((x - cx0) / cs, 0.0, cn - 1.001)
		var gz: float = clampf((z - cz0) / cs, 0.0, cn - 1.001)
		var cx: int = int(gx)
		var cz: int = int(gz)
		return _bl(f, cz * cn + cx, gx - cx, gz - cz)

	## Calls fn(index, x, z) for every fine sample inside `box` (world rect).
	func _for_box(box: Rect2, fn: Callable) -> void:
		var r: Rect2 = box.intersection(rect.grow(sp * 0.5))
		if r.size.x <= 0.0 or r.size.y <= 0.0:
			return
		var ix0: int = clampi(int(floor((r.position.x - cx0) / sp)), 0, n - 1)
		var ix1: int = clampi(int(ceil((r.end.x - cx0) / sp)), 0, n - 1)
		var iz0: int = clampi(int(floor((r.position.y - cz0) / sp)), 0, n - 1)
		var iz1: int = clampi(int(ceil((r.end.y - cz0) / sp)), 0, n - 1)
		for iz: int in range(iz0, iz1 + 1):
			var z: float = cz0 + iz * sp
			for ix: int in range(ix0, ix1 + 1):
				fn.call(iz * n + ix, cx0 + ix * sp, z)

	func _for_coarse_box(box: Rect2, fn: Callable) -> void:
		var r: Rect2 = box.intersection(rect.grow(cs))
		if r.size.x <= 0.0 or r.size.y <= 0.0:
			return
		var ix0: int = clampi(int(floor((r.position.x - cx0) / cs)), 0, cn - 1)
		var ix1: int = clampi(int(ceil((r.end.x - cx0) / cs)), 0, cn - 1)
		var iz0: int = clampi(int(floor((r.position.y - cz0) / cs)), 0, cn - 1)
		var iz1: int = clampi(int(ceil((r.end.y - cz0) / cs)), 0, cn - 1)
		for iz: int in range(iz0, iz1 + 1):
			var z: float = cz0 + iz * cs
			for ix: int in range(ix0, ix1 + 1):
				fn.call(iz * cn + ix, cx0 + ix * cs, z)

	## Bilinear sample of the work-in-progress heights.
	func _sample(x: float, z: float) -> float:
		var gx: float = clampf((x - cx0) / sp, 0.0, n - 1.001)
		var gz: float = clampf((z - cz0) / sp, 0.0, n - 1.001)
		var ix: int = int(gx)
		var iz: int = int(gz)
		var fx: float = gx - ix
		var fz: float = gz - iz
		var i: int = iz * n + ix
		var top: float = h[i] + (h[i + 1] - h[i]) * fx
		var bot: float = h[i + n] + (h[i + n + 1] - h[i + n]) * fx
		return top + (bot - top) * fz

	func _sample_or_macro(x: float, z: float) -> float:
		if rect.has_point(Vector2(x, z)):
			return _sample(x, z)
		return world.macro_height(x, z)

	static func _v2(a: Variant) -> Vector2:
		return Vector2(float(a[0]), float(a[1]))

	static func _to_poly(arr: Array) -> PackedVector2Array:
		var out := PackedVector2Array()
		for p: Variant in arr:
			out.append(Vector2(float(p[0]), float(p[1])))
		return out

	static func _poly_to_array(p: PackedVector2Array) -> Array:
		var out: Array = []
		for v: Vector2 in p:
			out.append([v.x, v.y])
		return out

	static func _poly_centroid(arr: Array) -> Vector2:
		var c := Vector2.ZERO
		for p: Variant in arr:
			c += Vector2(float(p[0]), float(p[1]))
		return c / maxf(1.0, arr.size())

	## Lake outline: polygon, or ellipse perturbed by low-frequency noise ("irregularity").
	func _lake_poly(f: Dictionary) -> PackedVector2Array:
		if not f.has("ellipse"):
			return _to_poly(f["polygon"])
		var e: Array = f["ellipse"]
		var irr: float = float(f.get("irregularity", 0.0))
		var nz := FastNoiseLite.new()
		nz.seed = world.seed + Ids.hash31(str(f.get("id", "lake")))
		nz.frequency = 1.6
		var c := Vector2(float(e[0]), float(e[1]))
		var rot: float = deg_to_rad(float(e[4])) if e.size() > 4 else 0.0
		var out := PackedVector2Array()
		for k: int in 48:
			var a: float = TAU * k / 48.0
			var m: float = 1.0 + irr * nz.get_noise_2d(cos(a), sin(a))
			out.append(c + Vector2(cos(a) * float(e[2]) * m, sin(a) * float(e[3]) * m).rotated(rot))
		return out

	## [cx, cz, rx, rz, rotation_deg] -> polygon (32 points).
	static func _ellipse_poly(e: Array) -> PackedVector2Array:
		var out := PackedVector2Array()
		var c := Vector2(float(e[0]), float(e[1]))
		var rot: float = deg_to_rad(float(e[4])) if e.size() > 4 else 0.0
		for k: int in 32:
			var a: float = TAU * k / 32.0
			out.append(c + Vector2(cos(a) * float(e[2]), sin(a) * float(e[3])).rotated(rot))
		return out

	static func _poly_edge_distance(poly: PackedVector2Array, p: Vector2) -> float:
		var best: float = INF
		for k: int in poly.size():
			var a: Vector2 = poly[k]
			var b: Vector2 = poly[(k + 1) % poly.size()]
			best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)))
		return best
