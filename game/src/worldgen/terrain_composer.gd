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
##
## World towns (ADR-0040, random worlds v2): a generated world lists its organic towns in world.json
## (`towns`, each a framework of frame lots at the world origin). Every region a town's bounds come
## near adds its streets as world roads (graded from the reference ground, no border fade), a pad
## per lot at the lot's own height `y` (yard ground, grass at YARD_VEG, giving way to the streets)
## and its paved square; a lot is placed by the region holding its frame's centre, and each region
## the town touches places the fixtures standing in it. Both sides of a border compute the same
## samples from world data alone, so a town may straddle borders. Worlds without `towns` (the main
## map, v1 worlds) compose exactly as before.
## VERSION 12 (ADR-0047): a world town paints `town` only on its streets (TOWN_VERGE past their
## shoulders) and square, no longer over its whole disc, and a yard's grass keeps off the largest
## authored footprint its lot may hold (VERSION 13: the yard grows over its whole frame and the
## house clears its own box at runtime). The main map's output did not change.
##
## Streaming (ADR-0038): the per-sample passes (macro and noise, water, roads, surface) can run in
## row bands, each on a Thread of its own writing its own arrays, merged in row order after the join
## (one PackedArray written from several threads can fork). Field rasterisation, cliffs and pads
## stay sequential. A compose looks at `cancel[0]` at each progress report and every CANCEL_ROWS
## rows and returns null once it is set. Every speed-up is output-identical, byte for byte
## (test_composer_golden.gd): saves keep digs, felled trees and POI state against composed regions,
## and the cache key hashes the inputs and VERSION, not this code.

## VERSION 13 (player report 4): every road (a generated world's and the main map's) keeps its grade
## under a cap by surface (ROAD_MAX_GRADE: a profile steeper than the land allows is cut and filled
## evenly round it) and meet the land in banks no steeper than a natural slope (BANK_*): the ground
## beside the road is pulled only as far as it stands steeper than the bank's slope, which varies
## along the road (rocky cuts steeper, fills gentler), with a rounded crest and toe and a little
## relief on the face, out to BANK_REACH m. They had a fixed 8 m blend: every cut and fill was one
## uniform plane as long as the road. A region's own roads still fade out at its border.
## VERSION 14 (TD-318): a world town's streets are profiled together (town_street_profiles): a street
## that meets an earlier one is pinned to its height there, so junctions have no crease; the
## generator (v14) sets each lot's height within LOT_STREET_STEP of its street's profile at the lot.
## VERSION 15 (TD-318 follow-ups): world roads are pinned to the world roads before them where they
## meet (world_road_profiles); the nearest road is the one whose EDGE is nearest (r_d), so a
## cul-de-sac's bulb is paved and graded across its whole circle where its street ends in it; and a
## road running onto a POI's or framework's pad ramps to its level (PAD_RAMP_*).
const VERSION: int = 15
## The steepest grade (rise over run) a generated world's road profile keeps, by surface.
const ROAD_MAX_GRADE: Dictionary = {"asphalt": 0.12, "gravel": 0.14, "dirt": 0.16}
## Road profiles are sampled every PROFILE_STEP m. A town street within JUNCTION_REACH m of an
## earlier one is pinned to it there, eased over JUNCTION_EASE m (TD-318).
const PROFILE_STEP: float = 4.0
const JUNCTION_REACH: float = 3.0
const JUNCTION_EASE: float = 32.0
const TOWN_ROAD_REACH: float = 60.0
## A road running onto a POI's or framework's pad ramps to its level at PAD_RAMP_GRADE (rise over
## run), over PAD_RAMP_MIN..PAD_RAMP_MAX m, its banks with it out to PAD_RAMP_SIDE m past its
## shoulder (VERSION 15).
const PAD_RAMP_GRADE: float = 0.08
const PAD_RAMP_MIN: float = 12.0
const PAD_RAMP_MAX: float = 60.0
const PAD_RAMP_SIDE: float = 10.0
## Banks beside a generated world's roads: the slope (rise over run) of a cut and of a fill, between
## the two values by a value noise along the road (BANK_CELL m across), a flat verge of up to
## BANK_VERGE m before the bank, the radius (m) of the rounding where the bank meets the land, the
## relief (m) on the face (BANK_BUMP_CELL m across) and how far from the shoulder a bank may reach.
const BANK_CUT: Vector2 = Vector2(0.6, 1.6)
const BANK_FILL: Vector2 = Vector2(0.45, 0.8)
const BANK_CELL: float = 23.0
const BANK_VERGE: float = 2.0
const BANK_ROUND: float = 1.5
## A low bank is gentler: below BANK_LOW m of height the slope eases towards BANK_SOFT, so a road or a
## pad a metre off the land blends in over a few metres instead of standing on a curb.
const BANK_SOFT: float = 0.3
const BANK_LOW: Vector2 = Vector2(1.0, 6.0)
const BANK_BUMP: float = 0.7
const BANK_BUMP_CELL: float = 6.5
const BANK_REACH: float = 26.0
## A water edge's profile: the ground falls EDGE_DROP below the water within EDGE_IN metres inside
## the edge and rises EDGE_RISE above it within EDGE_OUT outside. A slope through the water line
## keeps the shore off the 1 m sample grid; a step (VERSION 10: bed 0.35 m under, bank 0.22 m over,
## one sample apart) drew every river and lake edge as a 1 m staircase seen from near the water.
const EDGE_DROP: float = 0.35
const EDGE_IN: float = 1.5
const EDGE_RISE: float = 0.22
const EDGE_OUT: float = 1.0
const COARSE: float = 4.0
const MACRO_STEP: float = 8.0
const BORDER_FADE: float = 48.0
const DEFAULT_PALETTE: PackedStringArray = ["forest_floor", "moss_ground", "grass_ground", "dirt", "mud", "gravel", "asphalt_cracked", "sand"]
## Rows a band runs between two looks at the cancel flag (about 0.1 s of work at 1 m).
const CANCEL_ROWS: int = 64
## Cell size (m) of the surface pass's index of pads, paints, paths and clearings.
const BUCKET: float = 32.0
## World towns (ADR-0040): a lot pad's skirt (m), the vegetation a yard keeps (grass, 0..1), how far
## round a town's bounds a region looks for it (m), and how far beyond a street's paved corridor
## (half width + shoulder) a lot pad's skirt eases in (m): on the corridor it grades nothing, and the
## bank between a street and a yard spreads over the verge.
const LOT_SKIRT: float = 5.0
## VERSION 13: a world town's lot meets the land in a bank like a road's (BANK_*), its slope between
## these two by a value noise, out to LOT_BANK_REACH m from the frame, instead of a 5 m ramp.
const LOT_BANK: Vector2 = Vector2(0.4, 0.75)
const LOT_BANK_REACH: float = 14.0
## How far a framework's or a POI's pad banks reach (m; its `skirt` when that is longer).
const PAD_BANK_REACH: float = 18.0
## The vegetation a v1 framework's pad keeps (a main-map town such as Pell's Crossing: overgrown
## lots between its buildings, which clear their own boxes at runtime; VERSION 13, it was bare).
const FRAMEWORK_VEG: float = 0.75
const YARD_VEG: float = 0.85
const TOWN_REACH: float = 40.0
const LOT_ROAD_YIELD: float = 2.0
## A world town's streets paint `town` this far past their shoulders (m, plus up to 2 m of noise);
## the ground between the streets and the lots keeps the world's biome (ADR-0047).
const TOWN_VERGE: float = 3.0

## By path: new with ADR-0038, so this compiles before the editor registers its class name.
const Cache := preload("res://src/worldgen/region_cache.gd")
const Lots := preload("res://src/poi/lot_picker.gd")


## Everything that influences the output, hashed. Changing data or VERSION invalidates caches.
## The formula is v1's, so v1 caches stay valid; the files are read once per WorldDef and the
## hash is memoised there per region and spacing (ADR-0038).
static func input_hash(world: WorldDef, region_id: String, spacing: float) -> String:
	var key: String = "%s|%.3f" % [region_id, spacing]
	var memo: String = world.memo_hash(key)
	if memo != "":
		return memo
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(("v%d|%s|%s|%.3f" % [VERSION, world.id, region_id, spacing]).to_utf8_buffer())
	ctx.update(world.file_bytes(world.dir_path.path_join("world.json")))
	var rp: String = world.dir_path.path_join("regions").path_join(region_id).path_join("region.json")
	if FileAccess.file_exists(rp):
		ctx.update(world.file_bytes(rp))
		# Frameworks and standalone POIs shape the terrain too (pads, streets): hash their files.
		for f: Variant in world.region_data(region_id).get("features", []):
			if not f is Dictionary:
				continue
			var dep: String = ""
			match str(f.get("type", "")):
				"framework":
					dep = "res://data/pois/frameworks/%s.json" % f.get("framework", "")
				"poi":
					dep = "res://data/pois/buildings/%s.json" % f.get("poi", "")
			if dep != "" and FileAccess.file_exists(dep):
				ctx.update(world.file_bytes(dep))
	# A generated world's towns are frameworks of its own, written beside its world.json (ADR-0031).
	var gen_fw: String = world.dir_path.path_join("frameworks.json")
	if FileAccess.file_exists(gen_fw):
		ctx.update(world.file_bytes(gen_fw))
	# A town yard's grass keeps off the authored buildings its lot may hold (ADR-0047): their
	# footprints, tiers and zoning shape the vegetation mask.
	var authored: String = _town_authored_key(world)
	if authored != "":
		ctx.update(authored.to_utf8_buffer())
	var h: String = ctx.finish().hex_encode()
	world.set_memo_hash(key, h)
	return h


## The authored buildings a world's organic towns may hold, with what decides whether they fit a lot
## ("" without towns or content).
static func _town_authored_key(world: WorldDef) -> String:
	var db: Node = ContentDB.instance
	if world.towns.is_empty() or db == null:
		return ""
	var ids: Dictionary = {}
	for tw: Dictionary in world.towns:
		var fw: FrameworkDef = db.call(&"get_def", &"framework", StringName(str(tw["framework"]))) as FrameworkDef
		if fw != null:
			for id: Variant in fw.authored:
				ids[str(id)] = true
	var keys: Array = ids.keys()
	keys.sort()
	var parts := PackedStringArray()
	for id2: Variant in keys:
		var pd: PoiDef = db.call(&"get_def", &"poi", StringName(str(id2))) as PoiDef
		if pd != null:
			parts.append("%s:%d,%d:%d:%s" % [pd.id, pd.footprint.x, pd.footprint.y, pd.tier, ",".join(pd.zoning)])
	return "|".join(parts)


## Where a region's composed terrain is cached (RegionCache, ADR-0038).
static func cache_path(world: WorldDef, region_id: String, spacing: float) -> String:
	return Cache.path_for(world.id, region_id, spacing)


## Loads from the disk cache or composes (and caches) a region. `cancel` and `bands` as compose();
## a cancelled compose returns null and writes nothing.
static func get_or_compose(world: WorldDef, region_id: String, spacing: float = 1.0, progress: Callable = Callable(),
		cancel: Array = [false], bands: int = 1) -> RegionTerrain:
	# Without content loaded (a bare `-s` tool), frameworks and POIs can't be resolved: the result
	# lacks pads and streets. Cached under the real input hash, the game then loaded a town with
	# no ground graded for it, so such a compose is never read from or written to the cache.
	if ContentDB.instance == null:
		push_warning("TerrainComposer: no content loaded; composing %s without frameworks or POIs, uncached" % region_id)
		return compose(world, region_id, spacing, progress, cancel, bands)
	var h: String = input_hash(world, region_id, spacing)
	var path: String = cache_path(world, region_id, spacing)
	var rt: RegionTerrain = RegionTerrain.load_cached(path, h)
	if rt != null:
		(Cache.shared() as Cache).touch(path)
		return rt
	rt = compose(world, region_id, spacing, progress, cancel, bands)
	if rt != null:
		var err: Error = rt.save(path, h)
		if err != OK:
			push_warning("TerrainComposer: could not cache %s (%s)" % [path, error_string(err)])
		else:
			# Records the file and, after a detail write, trims the detail files to the budget.
			(Cache.shared() as Cache).wrote(path)
	return rt


## Composes a region. `cancel`: set cancel[0] = true from any thread to stop it (it returns null
## within about CANCEL_ROWS rows). `bands`: threads for the per-sample passes (1 = this thread
## only); the output is identical for any count.
## Street profiles of a world town ({street id: PackedFloat32Array, every PROFILE_STEP m}, TD-318):
## each street's reference ground smoothed and grade-capped as any world road's, then pinned to the
## streets before it in plan order wherever it meets one (a tee at its end, or a crossing), eased
## over JUNCTION_EASE m, so two streets meet at one height instead of in a crease. The generator
## reads the same profiles to set its lots' heights, so a yard meets its street flush.
## `streets`: the framework's roads [{id, points, surface}]; `fixed`: the world roads through or by
## the town (town_world_roads), profiled first and never pinned (the town's streets and lots meet
## them); h_fn(x, z) the reference ground.
static func town_street_profiles(streets: Array, h_fn: Callable, fixed: Array = []) -> Dictionary:
	var out: Dictionary = {}
	var lines: Array[Polyline2] = []
	var ids: PackedStringArray = []
	for fv: Variant in fixed:
		var fr: Dictionary = fv
		var fline: Polyline2 = fr["line"] if fr.has("line") else Polyline2.from_array(fr["points"])
		out[str(fr["id"])] = fr["profile"] if fr.has("profile") \
			else smoothed_profile(fline, h_fn, float(ROAD_MAX_GRADE.get(str(fr.get("surface", "")), 0.14)))
		lines.append(fline)
		ids.append(str(fr["id"]))
	for sv: Variant in streets:
		var st: Dictionary = sv
		if (st.get("points", []) as Array).size() < 2:
			continue
		var line: Polyline2 = Polyline2.from_array(st["points"])
		var prof: PackedFloat32Array = smoothed_profile(line, h_fn, float(ROAD_MAX_GRADE.get(str(st.get("surface", "")), 0.14)))
		# Where this street touches an earlier one: the arc of each local closest approach within
		# JUNCTION_REACH, pinned to the earlier street's height there.
		for j: int in lines.size():
			_pin_profile(prof, line, lines[j], out.get(ids[j], PackedFloat32Array()))
		lines.append(line)
		ids.append(str(st["id"]))
		out[str(st["id"])] = prof
	return out


## Pins `prof` (along `line`) to `oprof` (along `other`) wherever the two lines come within
## JUNCTION_REACH m (each local closest approach), eased over JUNCTION_EASE m along `line`.
static func _pin_profile(prof: PackedFloat32Array, line: Polyline2, other: Polyline2, oprof: PackedFloat32Array) -> void:
	if oprof.is_empty() or not line.bounds.grow(JUNCTION_REACH).intersects(other.bounds):
		return
	var n: int = prof.size()
	var near: Rect2 = other.bounds.grow(JUNCTION_REACH)
	var dist := PackedFloat32Array()
	dist.resize(n)
	for k: int in n:
		var p: Vector2 = line.point_at(k * PROFILE_STEP)
		dist[k] = other.closest(p).x if near.has_point(p) else 1.0e9
	for k2: int in n:
		var dk: float = dist[k2]
		if dk > JUNCTION_REACH or (k2 > 0 and dist[k2 - 1] < dk) or (k2 < n - 1 and dist[k2 + 1] <= dk):
			continue
		var at: Vector3 = other.closest(line.point_at(k2 * PROFILE_STEP))
		var delta: float = profile_at(oprof, at.y) - prof[k2]
		for k3: int in range(maxi(0, k2 - int(JUNCTION_EASE / PROFILE_STEP)), mini(n, k2 + int(JUNCTION_EASE / PROFILE_STEP) + 1)):
			var off: float = absf(float(k3 - k2)) * PROFILE_STEP
			if off < JUNCTION_EASE:
				prof[k3] += delta * (1.0 - smoothstep(0.0, JUNCTION_EASE, off))


## Every world road's profile ({id: PackedFloat32Array}, before bridges) on a world graded from
## world data alone: smoothed and grade-capped, then, in road order, pinned to every earlier road it
## meets, so two world roads meet at one height (TD-318 follow-up, VERSION 15). `roads`: WorldDef
## or generator roads [{id, line, surface}].
static func world_road_profiles(roads: Array, h_fn: Callable) -> Dictionary:
	var out: Dictionary = {}
	for i: int in roads.size():
		var r: Dictionary = roads[i]
		var line: Polyline2 = r["line"]
		var prof: PackedFloat32Array = smoothed_profile(line, h_fn, float(ROAD_MAX_GRADE.get(str(r.get("surface", "")), 0.14)))
		for j: int in i:
			_pin_profile(prof, line, roads[j]["line"], out[str(roads[j]["id"])])
		out[str(r["id"])] = prof
	return out


## The world roads that pass within TOWN_ROAD_REACH m of a town's disc ({id, line, surface}, by id),
## for town_street_profiles: the generator and the composer pick the same ones.
static func town_world_roads(roads: Array, center: Vector2, radius: float) -> Array:
	var out: Array = []
	for rv: Variant in roads:
		var r: Dictionary = rv
		var line: Polyline2 = r["line"]
		if line.bounds.grow(radius + TOWN_ROAD_REACH).has_point(center) and line.closest(center).x < radius + TOWN_ROAD_REACH:
			var e: Dictionary = {"id": str(r["id"]), "line": line, "surface": str(r.get("surface", ""))}
			if r.has("profile"):
				e["profile"] = r["profile"]
			out.append(e)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return str(a["id"]) < str(b["id"]))
	return out


## A road's centre-line heights every PROFILE_STEP m: h_fn sampled, smoothed (3 passes of a 9-sample
## moving average, ~36 m) and capped to grade g (_Build._limit_grade).
static func smoothed_profile(line: Polyline2, h_fn: Callable, g: float) -> PackedFloat32Array:
	var count: int = int(ceil(line.total_length / PROFILE_STEP)) + 1
	var prof := PackedFloat32Array()
	prof.resize(count)
	for k: int in count:
		var p: Vector2 = line.point_at(k * PROFILE_STEP)
		prof[k] = float(h_fn.call(p.x, p.y))
	for pass_i: int in 3:
		var cp: PackedFloat32Array = prof.duplicate()
		for k: int in count:
			var acc: float = 0.0
			for o: int in range(-4, 5):
				acc += cp[clampi(k + o, 0, count - 1)]
			prof[k] = acc / 9.0
	_Build._limit_grade(prof, PROFILE_STEP, g)
	return prof


## A profile's height at arc length s (linear between samples).
static func profile_at(prof: PackedFloat32Array, s: float) -> float:
	if prof.is_empty():
		return 0.0
	var f: float = clampf(s / PROFILE_STEP, 0.0, float(prof.size() - 1))
	var i: int = mini(int(f), prof.size() - 2) if prof.size() > 1 else 0
	return lerpf(prof[i], prof[mini(i + 1, prof.size() - 1)], f - float(i))


static func compose(world: WorldDef, region_id: String, spacing: float = 1.0, progress: Callable = Callable(),
		cancel: Array = [false], bands: int = 1) -> RegionTerrain:
	var b := _Build.new(world, region_id, spacing, progress)
	b.cancel = cancel if not cancel.is_empty() else [false]
	b.bands = maxi(1, bands)
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
	var cancel: Array = [false]
	var bands: int = 1
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
	# road fields (coarse). r_d is the distance to the nearest road's EDGE (centre line distance less
	# half its width; negative on it): the nearest road is the one whose edge is nearest, so a wide
	# road (a cul-de-sac's bulb) keeps its whole width where a narrow one ends in it, and the edge
	# distance stays continuous where two roads' cells meet. Readers add the road's half width back
	# (VERSION 15; it was the centre line's).
	var r_d: PackedFloat32Array
	var r_s: PackedFloat32Array
	var r_idx: PackedInt32Array
	var road_list: Array[Dictionary] = []
	# pads
	var pads: Array[Dictionary] = []
	var clearings: Array[Dictionary] = []
	var paints: Array[Dictionary] = []
	## Axis-aligned bounds of each pad (grown 1.5 m), for the pad test's early out.
	var _pad_boxes: Array[Rect2] = []
	var paths: Array[Dictionary] = []
	## World towns near this region (ADR-0040): [{id, fw: FrameworkDef}] in world.json order.
	var _towns: Array[Dictionary] = []
	var max_band: float = 0.0
	## The world detail noise every region shares (and blends to at its borders).
	var world_noise := FastNoiseLite.new()
	const WORLD_NOISE_AMP: float = 2.5
	## Levels of the region's local lakes by feature index. ("auto" levels sample this compose's
	## heights; written into the shared region data, they raced when two spacings of one region
	## composed at once, as a streamed world will.)
	var _lake_levels: Dictionary = {}
	## Step timings (ms), RegionTerrain.compose_ms.
	var _ms: Dictionary = {}
	var _tl: int = 0

	# Inputs of the band passes: set up on the calling thread before the bands start, read-only in
	# them. Per-column values are computed once with the exact expressions the loops used. A band's
	# loop calls no script function and no object method that it can avoid, and copies no shared
	# container per sample: each such call or copy takes a shared reference count (and, in debug
	# builds, ObjectDB's lock), which made four bands slower than one. So the helpers (_bl,
	# _add, _border_weight, Polyline2.closest) are inlined there with their exact arithmetic, and
	# per-road and per-item data are flat packed arrays with offsets rather than arrays of arrays.
	var _col_x := PackedFloat64Array()
	var _macro := PackedFloat32Array()
	var _mn: int = 0
	var _noises: Array[FastNoiseLite] = []
	var _amps := PackedFloat32Array()
	## The detail layer configured exactly like world_noise (a generated world's first layer): its
	## value is world_noise's, so it is not computed twice. -1: none.
	var _same_layer: int = -1
	# Per road (index into road_list), for the road and surface passes.
	var _r_half := PackedFloat64Array()
	var _r_sh := PackedFloat64Array()
	var _r_world := PackedByteArray()
	var _r_has := PackedByteArray()
	var _r_step := PackedFloat64Array()
	## Every road's profile in one array: road ri's starts at _r_prof_off[ri], _r_prof_n[ri] long.
	var _r_prof := PackedFloat32Array()
	var _r_prof_off := PackedInt32Array()
	var _r_prof_n := PackedInt32Array()
	## Road ri's bridge spans, [s0, s1] pairs: _r_span[_r_span_off[ri] .. _r_span_off[ri + 1]).
	var _r_span := PackedFloat64Array()
	var _r_span_off := PackedInt32Array()
	var _r_surf := PackedInt32Array()
	# Surface pass.
	var _s_kind := PackedInt32Array()
	var _s_map_index := PackedInt32Array()
	var _s_use_map: bool = false
	var _s_layers := PackedInt32Array()
	var _s_pn := FastNoiseLite.new()
	var _s_qn := FastNoiseLite.new()
	var _p1 := PackedFloat32Array()
	var _p2 := PackedFloat32Array()
	var _q1 := PackedFloat32Array()
	var _q2 := PackedFloat32Array()
	var _s_col_c := PackedInt32Array()
	var _s_col_f := PackedFloat64Array()
	var _s_col_b := PackedInt32Array()
	## The 32 m index. Per cell c, the items _bk_*_items[_bk_*_start[c] .. _bk_*_start[c + 1]).
	var _bk_n: int = 1
	var _bk_paint_start := PackedInt32Array()
	var _bk_paint_items := PackedInt32Array()
	var _bk_pad_start := PackedInt32Array()
	var _bk_pad_items := PackedInt32Array()
	var _bk_clear_start := PackedInt32Array()
	var _bk_clear_items := PackedInt32Array()
	## Paths: per cell c, entries e in _bk_path_start[c] .. [c + 1): path _bk_path_of[e], with its
	## segments near the cell _bk_path_segs[_bk_path_seg_start[e] .. _bk_path_seg_start[e + 1]).
	var _bk_path_start := PackedInt32Array()
	var _bk_path_of := PackedInt32Array()
	var _bk_path_seg_start := PackedInt32Array()
	var _bk_path_segs := PackedInt32Array()
	var _paint_boxes: Array[Rect2] = []
	var _paint_pos := PackedVector2Array()
	var _paint_blend := PackedFloat64Array()
	var _paint_r := PackedFloat64Array()
	var _paint_bi := PackedInt32Array()
	var _pad_origin := PackedVector2Array()
	var _pad_rot := PackedFloat64Array()
	var _pad_size := PackedVector2Array()
	var _pad_bi := PackedInt32Array()
	## Per pad: the vegetation it keeps (0 but in a world town's yards) and the palette layer it is
	## paved with (-1: none; a world town's square).
	var _pad_veg := PackedFloat64Array()
	var _pad_surf := PackedInt32Array()
	## Per road: 1 for a world town's street, 2 for a world road through a town's disc (both paint
	## `town` round them, the second only inside a disc); the biome index of `town`; the discs.
	var _r_town := PackedByteArray()
	var _s_town_bi: int = -1
	var _town_c := PackedVector2Array()
	var _town_r := PackedFloat64Array()
	var _cl_pos := PackedVector2Array()
	var _cl_r := PackedFloat64Array()
	## Every path's points in one array: path pi's start at _path_off[pi].
	var _path_pts := PackedVector2Array()
	var _path_off := PackedInt32Array()
	var _path_bounds: Array[Rect2] = []
	var _path_w := PackedFloat64Array()

	const K_CONIFER: int = 0
	const K_BIRCH: int = 1
	const K_MEADOW: int = 2
	const K_TOWN: int = 3
	const K_RIVERBANK: int = 4
	const K_ROCKY: int = 5
	const K_OTHER: int = 6
	## ADR-0041: an old burn (ash and char, regrowth) and a fen (peat, sphagnum, its pools).
	const K_BURN: int = 7
	const K_FEN: int = 8

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
		world_noise.seed = world.seed + 101
		world_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		world_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
		world_noise.fractal_octaves = 4
		world_noise.frequency = 0.012

	## The ground every region agrees on: macro elevation plus the shared world detail noise. A
	## generated world grades its world roads from it (WorldDef.road_grade "world", ADR-0031), so a
	## road crossing a region border has one profile on both sides.
	func _reference_ground(x: float, z: float) -> float:
		return world.macro_height(x, z) + world_noise.get_noise_2d(x, z) * WORLD_NOISE_AMP

	func _cancelled() -> bool:
		return bool(cancel[0]) if not cancel.is_empty() else false

	## Reports progress; false once the compose is cancelled.
	func _report(stage: String, t: float) -> bool:
		if _cancelled():
			return false
		if progress.is_valid():
			progress.call(stage, t)
		return not _cancelled()

	func _mark(step: String) -> void:
		var now: int = Time.get_ticks_usec()
		_ms[step] = float(now - _tl) / 1000.0
		_tl = now

	func run() -> RegionTerrain:
		if rect.size == Vector2.ZERO:
			push_error("TerrainComposer: unknown region %s" % region_id)
			return null
		_tl = Time.get_ticks_usec()
		var t_all: int = _tl
		rt = RegionTerrain.new()
		rt.region_id = region_id
		rt.rect = rect
		rt.spacing = sp
		rt.palette = PackedStringArray(region.get("palette", DEFAULT_PALETTE))
		for ix: int in n:
			_col_x.append(cx0 + ix * sp)
		if not _report("macro", 0.0):
			return null
		_macro_and_noise()
		_mark("macro_noise")
		if not _report("features", 0.3):
			return null
		_collect_features()
		_mark("collect")
		_hills_and_cliffs()
		_mark("hills_cliffs")
		_local_lakes_prepass()
		_mark("lakes_prepass")
		if not _report("water", 0.45):
			return null
		_water_fields()
		_mark("water_fields")
		_apply_water()
		_mark("apply_water")
		if not _report("roads", 0.6):
			return null
		_road_fields()
		_mark("road_fields")
		_apply_roads()
		_mark("apply_roads")
		if not _report("pads", 0.7):
			return null
		_apply_pads()
		_mark("pads")
		var hf := HeightField.new()
		hf.origin = rect.position
		hf.spacing = sp
		hf.width = n
		hf.depth = n
		hf.heights = h
		rt.height = hf
		if not _report("surface", 0.8):
			return null
		_surface_pass()
		_mark("surface")
		if _cancelled():
			return null
		_metadata()
		_mark("metadata")
		_ms["total"] = float(Time.get_ticks_usec() - t_all) / 1000.0
		rt.compose_ms = _ms
		if not _report("done", 1.0):
			return null
		return rt

	# --- Bands ------------------------------------------------------------------------------

	## Runs fn(r0, r1) -> Array over `rows` rows cut into `bands` bands, the first on this thread and
	## each other on a Thread of its own, and returns the bands' results in row order.
	func _run_bands(rows: int, fn: Callable) -> Array:
		var count: int = clampi(bands, 1, maxi(1, rows / 8))
		if count <= 1:
			return [fn.call(0, rows)]
		var threads: Array[Thread] = []
		for b: int in range(1, count):
			var th := Thread.new()
			threads.append(th if th.start(fn.bind(rows * b / count, rows * (b + 1) / count)) == OK else null)
		var out: Array = [fn.call(0, rows / count)]
		for b2: int in range(1, count):
			var th2: Thread = threads[b2 - 1]
			out.append(th2.wait_to_finish() if th2 != null else fn.call(rows * b2 / count, rows * (b2 + 1) / count))
		return out

	static func _concat_f32(parts: Array, k: int) -> PackedFloat32Array:
		if parts.size() == 1:
			return parts[0][k]
		var out := PackedFloat32Array()
		for p: Array in parts:
			out.append_array(p[k])
		return out

	static func _concat_bytes(parts: Array, k: int) -> PackedByteArray:
		if parts.size() == 1:
			return parts[0][k]
		var out := PackedByteArray()
		for p: Array in parts:
			out.append_array(p[k])
		return out

	# --- 1. Macro + detail noise ---------------------------------------------------------

	func _macro_and_noise() -> void:
		var mn: int = int(round(rect.size.x / MACRO_STEP)) + 1
		var ratio: float = sp / MACRO_STEP
		# The grid rows and columns the samples read with a non-zero weight. A coarse compose reads
		# every other one (16 m samples on the 8 m grid); the rest stay 0.0 and enter the bilinear
		# blend only times an exact 0, which leaves the result as it was.
		var need := PackedByteArray()
		need.resize(mn)
		for i: int in n:
			var g: float = i * ratio
			var m: int = mini(int(g), mn - 2)
			need[m] = 1
			if g - m != 0.0:
				need[m + 1] = 1
		_macro = PackedFloat32Array()
		_macro.resize(mn * mn)
		for iz: int in mn:
			if need[iz] == 0:
				continue
			for ix: int in mn:
				if need[ix] != 0:
					_macro[iz * mn + ix] = world.macro_height(cx0 + ix * MACRO_STEP, cz0 + iz * MACRO_STEP)
		_mn = mn
		var dcfg: Dictionary = region.get("detail_noise", {})
		var layers: Array = dcfg.get("layers", [{"frequency": dcfg.get("frequency", 0.012), "octaves": dcfg.get("octaves", 4), "amplitude": dcfg.get("amplitude", 2.5)}])
		_noises = []
		_amps = PackedFloat32Array()
		_same_layer = -1
		for li: int in layers.size():
			var lc: Dictionary = layers[li]
			var nz := FastNoiseLite.new()
			nz.seed = world.seed + 101 + li * 31
			nz.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
			nz.fractal_type = FastNoiseLite.FRACTAL_FBM
			nz.fractal_octaves = int(lc.get("octaves", 3))
			nz.frequency = float(lc.get("frequency", 0.01))
			_noises.append(nz)
			_amps.append(float(lc.get("amplitude", 1.0)))
			if _same_layer < 0 and nz.seed == world_noise.seed and nz.fractal_octaves == world_noise.fractal_octaves and nz.frequency == world_noise.frequency:
				_same_layer = li
		var parts: Array = _run_bands(n, _band_macro)
		h = _concat_f32(parts, 0)
		dnoise = _concat_f32(parts, 1)

	func _band_macro(z0: int, z1: int) -> Array:
		var nn: int = n
		var hb := PackedFloat32Array()
		hb.resize((z1 - z0) * nn)
		var db := PackedFloat32Array()
		db.resize((z1 - z0) * nn)
		var macro: PackedFloat32Array = _macro
		var mn: int = _mn
		var ratio: float = sp / MACRO_STEP
		var noises: Array[FastNoiseLite] = _noises
		var amps: PackedFloat32Array = _amps
		var nl: int = noises.size()
		var same: int = _same_layer
		# The first three layers in locals (regions have three), not fetched from the array per call.
		var nz0: FastNoiseLite = noises[0] if nl > 0 else null
		var nz1: FastNoiseLite = noises[1] if nl > 1 else null
		var nz2: FastNoiseLite = noises[2] if nl > 2 else null
		var a0: float = amps[0] if nl > 0 else 0.0
		var a1: float = amps[1] if nl > 1 else 0.0
		var a2: float = amps[2] if nl > 2 else 0.0
		var wn_noise: FastNoiseLite = world_noise
		var col_x: PackedFloat64Array = _col_x
		var cancel_flag: Array = cancel
		var z_0: float = cz0
		var spc: float = sp
		# Border samples use a world-level default (same in every region) so regions stitch.
		var world_amp: float = WORLD_NOISE_AMP
		# _border_weight's terms, as it read them (Rect2 is single precision).
		var bx0: float = rect.position.x
		var bx1: float = rect.end.x
		var bz0: float = rect.position.y
		var bz1: float = rect.end.y
		var col_m := PackedInt32Array()
		var col_f := PackedFloat64Array()
		for ix: int in nn:
			var gx: float = ix * ratio
			var mx: int = mini(int(gx), mn - 2)
			col_m.append(mx)
			col_f.append(gx - mx)
		for iz: int in range(z0, z1):
			if (iz - z0) % CANCEL_ROWS == CANCEL_ROWS - 1 and bool(cancel_flag[0]):
				break
			var gz: float = iz * ratio
			var mz: int = mini(int(gz), mn - 2)
			var fz: float = gz - mz
			var z: float = z_0 + iz * spc
			var row: int = (iz - z0) * nn
			var dz: float = minf(z - bz0, bz1 - z)
			for ix: int in nn:
				var fx: float = col_f[ix]
				var i: int = mz * mn + col_m[ix]
				var top: float = macro[i] + (macro[i + 1] - macro[i]) * fx
				var bot: float = macro[i + mn] + (macro[i + mn + 1] - macro[i + mn]) * fx
				var x: float = col_x[ix]
				var bw: float = clampf(minf(minf(x - bx0, bx1 - x), dz) / BORDER_FADE, 0.0, 1.0)
				var wn: float = wn_noise.get_noise_2d(x, z)
				var detail: float = 0.0
				if bw > 0.0:
					if nl > 0:
						detail += (wn if same == 0 else nz0.get_noise_2d(x, z)) * a0
					if nl > 1:
						detail += (wn if same == 1 else nz1.get_noise_2d(x, z)) * a1
					if nl > 2:
						detail += (wn if same == 2 else nz2.get_noise_2d(x, z)) * a2
					for li: int in range(3, nl):
						detail += (wn if li == same else noises[li].get_noise_2d(x, z)) * amps[li]
				var base_n: float = wn * world_amp
				var dv: float = lerpf(base_n, detail, bw)
				db[row + ix] = dv
				hb[row + ix] = top + (bot - top) * fz + dv
		return [hb, db]

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
		_collect_towns()

	## World towns whose bounds come near this region (ADR-0040): a pad per lot (its frame, turned
	## by -yaw as the composer turns pads; target the lot's `y`) and the square. Their streets join
	## the roads in _road_fields.
	func _collect_towns() -> void:
		if world.towns.is_empty():
			return
		var content: Node = _content()
		if content == null:
			return
		for tw: Dictionary in world.towns:
			if not (tw["bounds"] as Rect2).grow(TOWN_REACH).intersects(rect):
				continue
			var fw: FrameworkDef = content.get_def(&"framework", StringName(str(tw["framework"]))) as FrameworkDef
			if fw == null:
				push_warning("TerrainComposer: town %s: framework %s not registered" % [tw["id"], tw["framework"]])
				continue
			var tid: String = str(tw["id"])
			_towns.append({"id": tid, "fw": fw, "center": tw["center"], "radius": float(tw["radius"])})
			_town_c.append(tw["center"])
			_town_r.append(float(tw["radius"]))
			# `town` is painted on its streets (_band_surface) and its square; the lots are yards, and
			# the ground between them keeps the world's biome, so from above a town is streets and
			# yards in the meadows, not one brown disc (ADR-0047; town ambience and spawns key on
			# WorldDef.town_at).
			for lv: Variant in fw.lots:
				var l: Dictionary = lv
				if l.has("frame"):
					# A yard over the whole frame: the house the run stands there clears its own box
					# at runtime (VegetationManager._footprints, VERSION 13).
					pads.append(_frame_pad(l["frame"], float(l.get("y", 0.0)), "lot", String(fw.id), "%s/%s" % [tid, l.get("id", "")], "yard", YARD_VEG, ""))
			if fw.plaza.has("frame"):
				pads.append(_frame_pad(fw.plaza["frame"], float(fw.plaza.get("y", 0.0)), "plaza", String(fw.id), "%s/plaza" % tid, "town", 0.0, "asphalt"))

	## A world pad over a frame [cx, cz, w, d, yaw] (yaw as PoiManager.lot_xf turns a building: the
	## composer's rotation is -yaw, and the pad's corner is the frame's local (-w/2, -d/2)).
	static func _frame_pad(f: Array, y: float, kind: String, def_id: String, id: String, biome: String, veg: float, surface: String) -> Dictionary:
		var w: float = float(f[2])
		var d: float = float(f[3])
		var a: float = -deg_to_rad(float(f[4]))
		var c := Vector2(float(f[0]), float(f[1]))
		return {"kind": kind, "def": def_id, "id": id, "origin": c + Vector2(-w * 0.5, -d * 0.5).rotated(a), "rot": a, "size": Vector2(w, d),
			"skirt": LOT_SKIRT, "biome": biome, "keep_water": false, "freeboard": 0.0, "world": true, "target": y, "veg": veg, "surface": surface}

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
			"veg": FRAMEWORK_VEG if str(f["type"]) == "framework" else 0.0,
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
		var feats: Array = region.get("features", [])
		for fi: int in feats.size():
			var f: Dictionary = feats[fi]
			if str(f.get("type", "")) != "lake":
				continue
			if str(f.get("level", "auto")) == "auto":
				var c: Vector2 = _v2(f["ellipse"]) if f.has("ellipse") else _poly_centroid(f["polygon"])
				# A fen pool (ADR-0041) samples its own small ground (`probe` m a step) and stands
				# brim-full (`drop` under it); a lake sits 1.8 m under the ground 32 m round.
				var probe: float = float(f.get("probe", 4.0))
				var acc: float = 0.0
				for k: int in 9:
					var o := Vector2(cos(k * 0.7), sin(k * 0.7)) * float(k) * probe
					acc += _sample(c.x + o.x, c.y + o.y)
				_lake_levels[fi] = acc / 9.0 - float(f.get("drop", 1.8))
			else:
				_lake_levels[fi] = float(f["level"])

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
		var feats: Array = region.get("features", [])
		for fi: int in feats.size():
			var f: Dictionary = feats[fi]
			if str(f.get("type", "")) == "lake":
				var poly: PackedVector2Array = _lake_poly(f)
				_rasterize_lake_polygon(poly, float(_lake_levels[fi]), float(f.get("depth", 4.0)), float(f.get("shore", 12.0)), 50.0, 0.22)

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
		h = _concat_f32(_run_bands(n, _band_water), 0)

	func _band_water(z0: int, z1: int) -> Array:
		var nn: int = n
		var hb: PackedFloat32Array = h.slice(z0 * nn, z1 * nn)
		var dn: PackedFloat32Array = dnoise
		var fwd: PackedFloat32Array = fw_d
		var fwl: PackedFloat32Array = fw_lvl
		var fwvw: PackedFloat32Array = fw_vw
		var fwvs: PackedFloat32Array = fw_vs
		var wdd: PackedFloat32Array = w_d
		var wlv: PackedFloat32Array = w_lvl
		var wbk: PackedFloat32Array = w_bank
		var wdp: PackedFloat32Array = w_depth
		var fnn: int = fn_
		var cnn: int = cn
		var cancel_flag: Array = cancel
		var ratio: float = sp / cs
		var fratio: float = sp / FAR_STEP
		for iz: int in range(z0, z1):
			if (iz - z0) % CANCEL_ROWS == CANCEL_ROWS - 1 and bool(cancel_flag[0]):
				break
			var gz: float = iz * ratio
			var cz: int = mini(int(gz), cnn - 2)
			var fz: float = gz - cz
			var fgz: float = iz * fratio
			var fcz: int = mini(int(fgz), fnn - 2)
			var ffz: float = fgz - fcz
			var row: int = iz * nn
			var lrow: int = (iz - z0) * nn
			for ix: int in nn:
				var fgx: float = ix * fratio
				var fcx: int = mini(int(fgx), fnn - 2)
				var fi: int = fcz * fnn + fcx
				if fwd[fi] > fwvw[fi] + FAR_STEP * 1.5 and fwd[fi + fnn + 1] > fwvw[fi + fnn + 1] + FAR_STEP * 1.5:
					continue
				var hv: float = hb[lrow + ix]
				var ffx: float = fgx - fcx
				# fw_d bilinear on the 16 m grid (_bl's arithmetic, its "far" rule included)
				var fa: float = fwd[fi]
				var fb: float = fwd[fi + 1]
				var fc: float = fwd[fi + fnn]
				var fdd: float = fwd[fi + fnn + 1]
				var fd: float
				if fa > 1.0e8 or fb > 1.0e8 or fc > 1.0e8 or fdd > 1.0e8:
					fd = minf(minf(fa, fb), minf(fc, fdd))
				else:
					var ftop: float = fa + (fb - fa) * ffx
					fd = ftop + ((fc + (fdd - fc) * ffx) - ftop) * ffz
				if fd < 1.0e8:
					var vw: float = fwvw[fi]
					if fd < vw:
						# fw_lvl bilinear on the 16 m grid
						var la: float = fwl[fi]
						var lb: float = fwl[fi + 1]
						var lc: float = fwl[fi + fnn]
						var ld: float = fwl[fi + fnn + 1]
						var flvl: float
						if la > 1.0e8 or lb > 1.0e8 or lc > 1.0e8 or ld > 1.0e8:
							flvl = minf(minf(la, lb), minf(lc, ld))
						else:
							var ltop: float = la + (lb - la) * ffx
							flvl = ltop + ((lc + (ld - lc) * ffx) - ltop) * ffz
						var nd: float = dn[row + ix] * clampf(fd / 25.0, 0.15, 0.8)
						var cap: float = flvl + 0.5 + maxf(fd, 0.0) * fwvs[fi] + nd
						var wv: float = 1.0 - smoothstep(vw * 0.55, vw, fd)
						hv = lerpf(hv, minf(hv, cap), wv)
				var gx: float = ix * ratio
				var cx: int = mini(int(gx), cnn - 2)
				var ci: int = cz * cnn + cx
				if wdd[ci] < 1.0e8 or wdd[ci + cnn + 1] < 1.0e8:
					var fx: float = gx - cx
					# _bl(w_d, ci, fx, fz)
					var wa: float = wdd[ci]
					var wb: float = wdd[ci + 1]
					var wc: float = wdd[ci + cnn]
					var wdx: float = wdd[ci + cnn + 1]
					var d: float
					if wa > 1.0e8 or wb > 1.0e8 or wc > 1.0e8 or wdx > 1.0e8:
						d = minf(minf(wa, wb), minf(wc, wdx))
					else:
						var wtop: float = wa + (wb - wa) * fx
						d = wtop + ((wc + (wdx - wc) * fx) - wtop) * fz
					if d < 1.0e8:
						# _bl(w_lvl, ci, fx, fz)
						var va: float = wlv[ci]
						var vb: float = wlv[ci + 1]
						var vc: float = wlv[ci + cnn]
						var vd: float = wlv[ci + cnn + 1]
						var lvl: float
						if va > 1.0e8 or vb > 1.0e8 or vc > 1.0e8 or vd > 1.0e8:
							lvl = minf(minf(va, vb), minf(vc, vd))
						else:
							var vtop: float = va + (vb - va) * fx
							lvl = vtop + ((vc + (vd - vc) * fx) - vtop) * fz
						var bank: float = wbk[ci]
						if d < 0.0:
							var f: float = clampf(-d / maxf(3.0, bank * 0.9), 0.0, 1.0)
							var bed: float = lvl - EDGE_DROP * minf(-d / EDGE_IN, 1.0) - wdp[ci] * (f * f * (3.0 - 2.0 * f))
							hv = minf(hv, bed)
						elif d < bank:
							var t: float = smoothstep(0.0, bank, d)
							var shore_h: float = lvl + EDGE_RISE * minf(d / EDGE_OUT, 1.0) + d * 0.06
							hv = lerpf(shore_h, maxf(hv, shore_h), t)
				hb[lrow + ix] = hv
		return [hb]

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
		for wi: int in world.roads.size():
			var r: Dictionary = world.roads[wi]
			road_list.append({"id": r["id"], "line": r["line"], "width": r["width"], "shoulder": r["shoulder"],
				"surface": r["surface"], "bridges": r.get("bridges", []), "world": true, "markings": bool(r.get("markings", true)), "world_index": wi})
		for f: Dictionary in region.get("features", []):
			if str(f.get("type", "")) == "road":
				road_list.append({"id": str(f.get("id", "road")), "line": Polyline2.from_array(f["points"]),
					"width": float(f.get("width", 5.0)), "shoulder": float(f.get("shoulder", 1.5)),
					"surface": str(f.get("surface", "gravel")), "bridges": f.get("bridges", []), "world": false,
					"markings": bool(f.get("markings", true))})
			elif str(f.get("type", "")) == "framework":
				_framework_roads(f)
		# World towns' streets (ADR-0040): world roads, graded from the reference ground in every
		# region they cross (one profile, memoised under the town and street).
		for tw: Dictionary in _towns:
			var fw: FrameworkDef = tw["fw"]
			var fixed: Array = TerrainComposer.town_world_roads(_world_roads_profiled(), tw["center"], float(tw["radius"]))
			for rv: Variant in fw.roads:
				if not rv is Dictionary or ((rv as Dictionary).get("points", []) as Array).size() < 2:
					continue
				var rd: Dictionary = rv
				road_list.append({"id": "%s/%s" % [tw["id"], rd.get("id", "street")], "line": Polyline2.from_array(rd["points"]),
					"width": float(rd.get("width", 6.0)), "shoulder": float(rd.get("shoulder", 0.8)), "surface": str(rd.get("surface", "asphalt")),
					"bridges": [], "world": true, "markings": bool(rd.get("markings", false)), "profile_key": "town:%s:%s" % [tw["id"], rd.get("id", "")],
					"town": tw["id"], "street": str(rd.get("id", "")), "town_streets": fw.roads, "town_fixed": fixed})
		var count: int = cn * cn
		r_d = PackedFloat32Array()
		r_d.resize(count)
		r_d.fill(1.0e9)
		r_s = PackedFloat32Array()
		r_s.resize(count)
		r_idx = PackedInt32Array()
		r_idx.resize(count)
		r_idx.fill(-1)
		var near: Rect2 = rect.grow(cs)
		for ri: int in road_list.size():
			var r: Dictionary = road_list[ri]
			var line: Polyline2 = r["line"]
			var reach: float = float(r["width"]) * 0.5 + float(r["shoulder"]) + BANK_REACH + 2.0
			max_band = maxf(max_band, reach)
			if not line.bounds.grow(reach).intersects(rect):
				continue
			if bool(r["world"]) and world.road_grade == "world":
				# Graded from world data alone, a world road has one profile in every region it
				# crosses: built once per world (each region used to build the whole road).
				var key: Variant = r["profile_key"] if r.has("profile_key") else int(r["world_index"])
				var prof: Dictionary = world.road_profile(key, _profile_data.bind(r))
				r["profile"] = prof["profile"]
				r["step"] = prof["step"]
				r["spans"] = prof["spans"]
			else:
				_build_profile(r)
			for si: int in line.points.size() - 1:
				var a: Vector2 = line.points[si]
				var bpt: Vector2 = line.points[si + 1]
				var seg := Rect2(a, Vector2.ZERO).expand(bpt).grow(reach)
				# _for_coarse_box's own test, before a callable is made for a far segment.
				var hit: Rect2 = seg.intersection(near)
				if hit.size.x <= 0.0 or hit.size.y <= 0.0:
					continue
				var ab: Vector2 = bpt - a
				var l2: float = maxf(ab.length_squared(), 1e-6)
				var seg_len: float = sqrt(l2)
				var s0: float = line.lengths[si]
				var idx: int = ri
				var hw: float = float(r["width"]) * 0.5
				_for_coarse_box(seg, func(ci: int, x: float, z: float) -> void:
					var p := Vector2(x, z)
					var t: float = clampf((p - a).dot(ab) / l2, 0.0, 1.0)
					var dist: float = p.distance_to(a + ab * t) - hw
					if dist < r_d[ci]:
						r_d[ci] = dist
						r_s[ci] = s0 + seg_len * t
						r_idx[ci] = idx)
		# Per-road values for the road and surface passes, flat (see the band notes above).
		for ri2: int in road_list.size():
			var r2: Dictionary = road_list[ri2]
			var has: bool = r2.has("spans")
			_r_half.append(float(r2["width"]) * 0.5)
			_r_sh.append(float(r2["shoulder"]))
			_r_world.append(1 if bool(r2["world"]) else 0)
			_r_has.append(1 if has else 0)
			_r_step.append(float(r2["step"]) if has else 0.0)
			_r_prof_off.append(_r_prof.size())
			_r_span_off.append(_r_span.size())
			if has:
				var prof: PackedFloat32Array = r2["profile"]
				_r_prof.append_array(prof)
				_r_prof_n.append(prof.size())
				for span: Array in r2["spans"]:
					_r_span.append(float(span[0]))
					_r_span.append(float(span[1]))
			else:
				_r_prof_n.append(0)
		_r_span_off.append(_r_span.size())

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
		var prof: Dictionary = _profile_data(r)
		r["profile"] = prof["profile"]
		r["step"] = prof["step"]
		r["spans"] = prof["spans"]

	## world.roads with their pinned profiles (`profile`) on a world graded from world data alone.
	func _world_roads_profiled() -> Array:
		if world.road_grade != "world":
			return world.roads
		var profs: Dictionary = _world_profiles()
		var out: Array = []
		for r: Dictionary in world.roads:
			var e: Dictionary = r.duplicate()
			e["profile"] = profs.get(str(r["id"]), PackedFloat32Array())
			out.append(e)
		return out

	## Every world road's pinned profile (world_road_profiles), built once per world.
	func _world_profiles() -> Dictionary:
		var memo: Dictionary = world.road_profile("world:*", func() -> Dictionary:
			return {"profiles": TerrainComposer.world_road_profiles(world.roads, _reference_ground)})
		return memo["profiles"]

	## {profile, step, spans} of a road (see _build_profile).
	func _profile_data(r: Dictionary) -> Dictionary:
		var line: Polyline2 = r["line"]
		var step: float = PROFILE_STEP
		var by_world: bool = bool(r["world"]) and world.road_grade == "world"
		var prof: PackedFloat32Array
		if by_world and r.has("town_streets"):
			# A world town's street: its town's profiles, pinned at the junctions (TD-318),
			# built once per town.
			var town: Dictionary = world.road_profile("town:%s:*" % r["town"], func() -> Dictionary:
				return {"profiles": TerrainComposer.town_street_profiles(r["town_streets"], _reference_ground, r["town_fixed"])})
			prof = ((town["profiles"] as Dictionary).get(str(r["street"]), PackedFloat32Array()) as PackedFloat32Array).duplicate()
		elif by_world and r.has("world_index"):
			# A world road: pinned to the world roads before it where they meet (VERSION 15).
			prof = ((_world_profiles().get(str(r["id"]), PackedFloat32Array())) as PackedFloat32Array).duplicate()
		if prof.is_empty():
			prof = TerrainComposer.smoothed_profile(line, _reference_ground if by_world else _sample_or_macro,
				float(ROAD_MAX_GRADE.get(str(r.get("surface", "")), 0.14)))
		var count: int = prof.size()
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
		return {"profile": prof, "step": step, "spans": spans}

	## Keeps a profile's grade under `g` (rise over run), cutting and filling evenly: the mean of the
	## highest profile under the ground and the lowest over it whose grades stay under g (each is
	## g-Lipschitz, so their mean is too). Where the land is gentler than g it is the land itself.
	static func _limit_grade(prof: PackedFloat32Array, step: float, g: float) -> void:
		var count: int = prof.size()
		if count < 2:
			return
		var rise: float = g * step
		var lo: PackedFloat32Array = prof.duplicate()
		var hi: PackedFloat32Array = prof.duplicate()
		for k: int in range(1, count):
			lo[k] = minf(lo[k], lo[k - 1] + rise)
			hi[k] = maxf(hi[k], hi[k - 1] - rise)
		for k2: int in range(count - 2, -1, -1):
			lo[k2] = minf(lo[k2], lo[k2 + 1] + rise)
			hi[k2] = maxf(hi[k2], hi[k2 + 1] - rise)
		for k3: int in count:
			prof[k3] = (lo[k3] + hi[k3]) * 0.5

	func _water_level_near(p: Vector2) -> float:
		var best: float = -1.0e9
		for r: Dictionary in world.rivers:
			var line: Polyline2 = r["line"]
			var q: Vector3 = line.closest(p)
			if q.x < 60.0:
				best = maxf(best, line.value_at(r["level"], q.y))
		return best

	func _apply_roads() -> void:
		h = _concat_f32(_run_bands(n, _band_roads), 0)

	func _band_roads(z0: int, z1: int) -> Array:
		var nn: int = n
		var hb: PackedFloat32Array = h.slice(z0 * nn, z1 * nn)
		var ridx: PackedInt32Array = r_idx
		var rdd: PackedFloat32Array = r_d
		var rss: PackedFloat32Array = r_s
		var rhalf: PackedFloat64Array = _r_half
		var rsh: PackedFloat64Array = _r_sh
		var rhas: PackedByteArray = _r_has
		var rworld: PackedByteArray = _r_world
		var bank_seed: int = world.seed & 0xffffff
		var rstep: PackedFloat64Array = _r_step
		var rprof: PackedFloat32Array = _r_prof
		var rpoff: PackedInt32Array = _r_prof_off
		var rpn: PackedInt32Array = _r_prof_n
		var rspan: PackedFloat64Array = _r_span
		var rsoff: PackedInt32Array = _r_span_off
		var cnn: int = cn
		var x_0: float = cx0
		var z_0: float = cz0
		var spc: float = sp
		var cancel_flag: Array = cancel
		# _border_weight's terms, as it read them (Rect2 is single precision).
		var bx0: float = rect.position.x
		var bx1: float = rect.end.x
		var bz0: float = rect.position.y
		var bz1: float = rect.end.y
		var ratio: float = sp / cs
		for iz: int in range(z0, z1):
			if (iz - z0) % CANCEL_ROWS == CANCEL_ROWS - 1 and bool(cancel_flag[0]):
				break
			var gz: float = iz * ratio
			var cz: int = mini(int(gz), cnn - 2)
			var fz: float = gz - cz
			var lrow: int = (iz - z0) * nn
			var bz: float = z_0 + iz * spc
			var dz: float = minf(bz - bz0, bz1 - bz)
			for ix: int in nn:
				var gx: float = ix * ratio
				var cx: int = mini(int(gx), cnn - 2)
				var ci: int = cz * cnn + cx
				var ri: int = ridx[ci]
				if ri < 0:
					ri = ridx[ci + cnn + 1]
					if ri < 0:
						continue
				var fx: float = gx - cx
				var d: float
				var s: float
				var i00: int = ridx[ci]
				if i00 == ridx[ci + 1] and i00 == ridx[ci + cnn] and i00 == ridx[ci + cnn + 1]:
					# _bl(r_d, ci, fx, fz) and _bl(r_s, ci, fx, fz)
					var da: float = rdd[ci]
					var db: float = rdd[ci + 1]
					var dc: float = rdd[ci + cnn]
					var ddd: float = rdd[ci + cnn + 1]
					if da > 1.0e8 or db > 1.0e8 or dc > 1.0e8 or ddd > 1.0e8:
						d = minf(minf(da, db), minf(dc, ddd))
					else:
						var dtop: float = da + (db - da) * fx
						d = dtop + ((dc + (ddd - dc) * fx) - dtop) * fz
					var sa: float = rss[ci]
					var sb: float = rss[ci + 1]
					var sc: float = rss[ci + cnn]
					var sd: float = rss[ci + cnn + 1]
					if sa > 1.0e8 or sb > 1.0e8 or sc > 1.0e8 or sd > 1.0e8:
						s = minf(minf(sa, sb), minf(sc, sd))
					else:
						var stop: float = sa + (sb - sa) * fx
						s = stop + ((sc + (sd - sc) * fx) - stop) * fz
				else:
					# The corners belong to different roads. The road is the nearest corner's; the
					# distance to the nearest road is continuous across the line where two roads'
					# cells meet, so it stays bilinear; the arc is interpolated over that road's own
					# corners. (VERSION 13: both were the nearest corner's, constant over a 4 m cell,
					# which drew stairs along the wide banks where two streets' fields meet.)
					var nci: int = ci + (1 if fx > 0.5 else 0) + (cnn if fz > 0.5 else 0)
					if ridx[nci] >= 0:
						ri = ridx[nci]
					var ma: float = rdd[ci]
					var mb: float = rdd[ci + 1]
					var mc: float = rdd[ci + cnn]
					var md: float = rdd[ci + cnn + 1]
					if ma > 1.0e8 or mb > 1.0e8 or mc > 1.0e8 or md > 1.0e8:
						d = rdd[nci]
					else:
						var mtop: float = ma + (mb - ma) * fx
						d = mtop + ((mc + (md - mc) * fx) - mtop) * fz
					var w00: float = (1.0 - fx) * (1.0 - fz) if ridx[ci] == ri else 0.0
					var w10: float = fx * (1.0 - fz) if ridx[ci + 1] == ri else 0.0
					var w01: float = (1.0 - fx) * fz if ridx[ci + cnn] == ri else 0.0
					var w11: float = fx * fz if ridx[ci + cnn + 1] == ri else 0.0
					var wsum: float = w00 + w10 + w01 + w11
					if wsum > 1e-6:
						s = (rss[ci] * w00 + rss[ci + 1] * w10 + rss[ci + cnn] * w01 + rss[ci + cnn + 1] * w11) / wsum
					else:
						s = rss[nci]
				var half: float = rhalf[ri]
				d += half
				var sh: float = rsh[ri]
				var outer: float = half + sh + BANK_REACH
				if d > outer or rhas[ri] == 0:
					continue
				var skip: bool = false
				for j: int in range(rsoff[ri], rsoff[ri + 1], 2):
					if s > rspan[j] + 2.0 and s < rspan[j + 1] - 2.0:
						skip = true
						break
				if skip:
					continue
				var step: float = rstep[ri]
				var k: float = s / step
				var pn: int = rpn[ri]
				var po: int = rpoff[ri]
				var k0: int = clampi(int(k), 0, pn - 1)
				var k1: int = mini(k0 + 1, pn - 1)
				var target: float = lerpf(rprof[po + k0], rprof[po + k1], k - k0)
				target -= 0.06 * minf(1.0, (d / maxf(half, 0.5)) * (d / maxf(half, 0.5)))
				var inner: float = half + sh
				var hv: float = hb[lrow + ix]
				if d <= inner:
					var wb: float = 1.0
					if rworld[ri] == 0:
						wb = clampf(minf(minf(x_0 + ix * spc - bx0, bx1 - (x_0 + ix * spc)), dz) / BORDER_FADE, 0.0, 1.0)
					hb[lrow + ix] = lerpf(hv, target, wb)
					continue
				var bx2: float = x_0 + ix * spc
				# Value noise (inlined: no calls in a band's loop), BANK_CELL m across, for the
				# bank's slope, and BANK_BUMP_CELL m across for the verge and the face's relief.
				var gx2: float = bx2 / BANK_CELL
				var gz2: float = bz / BANK_CELL
				var vi: int = floori(gx2)
				var vj: int = floori(gz2)
				var vfx: float = gx2 - vi
				var vfz: float = gz2 - vj
				vfx = vfx * vfx * (3.0 - 2.0 * vfx)
				vfz = vfz * vfz * (3.0 - 2.0 * vfz)
				var v00: float = float(((vi * 73856093) ^ (vj * 19349663) ^ bank_seed) & 0xffff) / 65535.0
				var v10: float = float((((vi + 1) * 73856093) ^ (vj * 19349663) ^ bank_seed) & 0xffff) / 65535.0
				var v01: float = float(((vi * 73856093) ^ ((vj + 1) * 19349663) ^ bank_seed) & 0xffff) / 65535.0
				var v11: float = float((((vi + 1) * 73856093) ^ ((vj + 1) * 19349663) ^ bank_seed) & 0xffff) / 65535.0
				var nk: float = lerpf(lerpf(v00, v10, vfx), lerpf(v01, v11, vfx), vfz)
				var gx3: float = bx2 / BANK_BUMP_CELL
				var gz3: float = bz / BANK_BUMP_CELL
				var wi: int = floori(gx3)
				var wj: int = floori(gz3)
				var wfx: float = gx3 - wi
				var wfz: float = gz3 - wj
				wfx = wfx * wfx * (3.0 - 2.0 * wfx)
				wfz = wfz * wfz * (3.0 - 2.0 * wfz)
				var bs2: int = bank_seed ^ 0x5bd1e9
				var u00: float = float(((wi * 73856093) ^ (wj * 19349663) ^ bs2) & 0xffff) / 65535.0
				var u10: float = float((((wi + 1) * 73856093) ^ (wj * 19349663) ^ bs2) & 0xffff) / 65535.0
				var u01: float = float(((wi * 73856093) ^ ((wj + 1) * 19349663) ^ bs2) & 0xffff) / 65535.0
				var u11: float = float((((wi + 1) * 73856093) ^ ((wj + 1) * 19349663) ^ bs2) & 0xffff) / 65535.0
				var nb: float = lerpf(lerpf(u00, u10, wfx), lerpf(u01, u11, wfx), wfz)
				var dh: float = hv - target
				# A flat verge of at least 0.8 m before the bank: on the 4 m far LOD the bench then
				# keeps a vertex or two, and the road does not read as tilted into its bank.
				var e: float = maxf(0.0, d - inner - 0.8 - nb * BANK_VERGE)
				var k_s: float = lerpf(BANK_CUT.x, BANK_CUT.y, nk) if dh > 0.0 else lerpf(BANK_FILL.x, BANK_FILL.y, nk)
				var adh: float = absf(dh)
				k_s = lerpf(BANK_SOFT, k_s, smoothstep(BANK_LOW.x, BANK_LOW.y, adh))
				var allow: float = k_s * e
				# A smooth min of |dh| and the bank's allowance: the crest and toe round off over
				# BANK_ROUND m instead of meeting in a crease.
				var hk: float = maxf(BANK_ROUND - absf(adh - allow), 0.0) / BANK_ROUND
				var lim: float = minf(adh, allow) - hk * hk * BANK_ROUND * 0.25
				lim = maxf(lim, 0.0)
				# Relief on the face only, where the bank moved the land.
				var moved: float = clampf((adh - lim) / 1.5, 0.0, 1.0)
				var face: float = target + signf(dh) * lim + (nb - 0.5) * BANK_BUMP * moved
				var reach_w: float = 1.0 - smoothstep(BANK_REACH * 0.75, BANK_REACH, d - inner)
				if rworld[ri] == 0:
					# A region's own road fades out at its border, as before.
					reach_w *= clampf(minf(minf(bx2 - bx0, bx1 - bx2), dz) / BORDER_FADE, 0.0, 1.0)
				hb[lrow + ix] = lerpf(hv, face, reach_w)
		return [hb]

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
			# A world town's pad (ADR-0040) is graded to its own height from world data, everywhere
			# alike (no border fade), and gives way to the streets.
			var world_pad: bool = bool(pad.get("world", false))
			var target: float = float(pad.get("target", 0.0))
			if not world_pad:
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
				target = acc / cnt + 0.05
				if wet_cnt > 0:
					target = wet_lvl / wet_cnt + float(pad["freeboard"])
			pad["height"] = target
			var corners: Array[Vector2] = [o, o + Vector2(size.x, 0).rotated(rot), o + size.rotated(rot), o + Vector2(0, size.y).rotated(rot)]
			var bb := Rect2(corners[0], Vector2.ZERO)
			for c: Vector2 in corners:
				bb = bb.expand(c)
			# Roads that run onto a pad (not a lot's: its height is held to its street) ramp to it.
			var onto: Dictionary = {} if world_pad or keep_water else _roads_onto(o, size, rot, bb)
			var ramp_roads: bool = not onto.is_empty()
			bb = bb.grow(LOT_BANK_REACH if world_pad else (skirt if keep_water else maxf(skirt, PAD_RAMP_MAX if ramp_roads else PAD_BANK_REACH)))
			var bank_seed: int = (world.seed & 0xffffff) ^ 0x3c6ef3
			_for_box(bb, func(i: int, x: float, z: float) -> void:
				var lp: Vector2 = (Vector2(x, z) - o).rotated(-rot)
				var dx: float = maxf(maxf(-lp.x, lp.x - size.x), 0.0)
				var dz: float = maxf(maxf(-lp.y, lp.y - size.y), 0.0)
				var d: float = sqrt(dx * dx + dz * dz)
				if world_pad:
					# Only the bank here: the frames are graded last (below).
					if d > 0.0 and d < LOT_BANK_REACH:
						var dh: float = h[i] - target
						var adh: float = absf(dh)
						var k_s: float = lerpf(BANK_SOFT, lerpf(LOT_BANK.x, LOT_BANK.y, _vnoise(x, z, BANK_CELL, bank_seed)), smoothstep(BANK_LOW.x, BANK_LOW.y, adh))
						var allow: float = k_s * d
						var hk: float = maxf(BANK_ROUND - absf(adh - allow), 0.0) / BANK_ROUND
						var lim: float = maxf(minf(adh, allow) - hk * hk * BANK_ROUND * 0.25, 0.0)
						var fade: float = 1.0 - smoothstep(LOT_BANK_REACH * 0.7, LOT_BANK_REACH, d)
						h[i] = lerpf(h[i], target + signf(dh) * lim, fade * _yield_to_roads(x, z))
					return
				if not keep_water:
					# VERSION 13: a pad meets the land in a bank like a road's (on the main map too: Pell's
					# Crossing stood on one flat plate with 10 m planar ramps round it), out to
					# PAD_BANK_REACH m, and the pad itself is level to its edges as before.
					if d < PAD_BANK_REACH:
						var dh2: float = h[i] - target
						var adh2: float = absf(dh2)
						var allow2: float = lerpf(BANK_SOFT, lerpf(LOT_BANK.x, LOT_BANK.y, _vnoise(x, z, BANK_CELL, bank_seed)), smoothstep(BANK_LOW.x, BANK_LOW.y, adh2)) * d
						var hk2: float = maxf(BANK_ROUND - absf(adh2 - allow2), 0.0) / BANK_ROUND
						var lim2: float = maxf(minf(adh2, allow2) - hk2 * hk2 * BANK_ROUND * 0.25, 0.0)
						var fade2: float = 1.0 - smoothstep(PAD_BANK_REACH * 0.7, PAD_BANK_REACH, d)
						# Like a lot's, its bank gives way to the roads' level corridors (the roads are
						# graded first, and a bank across one tilted it: Pell's Crossing's corner); the
						# pad itself stays level over a road inside it (a campground's loop).
						h[i] = lerpf(h[i], target + signf(dh2) * lim2, fade2 * _border_weight(x, z) * (_yield_to_roads(x, z) if d > 0.0 else 1.0))
					# VERSION 15 (TD-318 follow-up): a road that runs onto the pad ramps to its level
					# over the last PAD_RAMP_GRADE of rise (12-60 m), its banks with it, instead of
					# meeting the pad's edge in a step (the banks above give way to the road, and the
					# road is graded before the pad: Pell's Crossing's west entry stood 3.7 m under it).
					if d > 0.0 and ramp_roads and d < PAD_RAMP_MAX:
						var rw: float = _road_reach(x, z, PAD_RAMP_SIDE, onto)
						if rw > 0.0:
							var rl: float = clampf(absf(h[i] - target) / PAD_RAMP_GRADE, PAD_RAMP_MIN, PAD_RAMP_MAX)
							h[i] = lerpf(h[i], target, rw * (1.0 - smoothstep(0.0, rl, d)) * _border_weight(x, z))
					return
				if d < skirt:
					var wgt: float = 1.0 - smoothstep(0.0, skirt, d)
					if keep_water:
						# Nothing in the water; the dry ground eases down to the bank over its last 2 m
						# rather than standing over the water as a step.
						wgt *= smoothstep(0.0, 2.0, _water_d(x, z))
					h[i] = lerpf(h[i], target, wgt * _border_weight(x, z)))
		# A world town's lots stand 1 m apart and their skirts reach over each other: each frame is
		# graded last, all of it at its own height (frames never overlap, so their order is moot; the
		# planner keeps every frame clear of the street corridors), and a building on it stands on
		# level ground to its corners (ADR-0040).
		for pad2: Dictionary in pads:
			if not bool(pad2.get("world", false)):
				continue
			var o2: Vector2 = pad2["origin"]
			var size2: Vector2 = pad2["size"]
			var rot2: float = pad2["rot"]
			var target2: float = pad2["height"]
			var bb2 := Rect2(o2, Vector2.ZERO)
			for c2: Vector2 in [o2 + Vector2(size2.x, 0).rotated(rot2), o2 + size2.rotated(rot2), o2 + Vector2(0, size2.y).rotated(rot2)]:
				bb2 = bb2.expand(c2)
			_for_box(bb2, func(i: int, x: float, z: float) -> void:
				var lp: Vector2 = (Vector2(x, z) - o2).rotated(-rot2)
				if lp.x >= 0.0 and lp.y >= 0.0 and lp.x <= size2.x and lp.y <= size2.y:
					h[i] = target2)

	## Smooth value noise in [0, 1], `cell` m across (the banks' variation; _band_roads inlines it).
	static func _vnoise(x: float, z: float, cell: float, sd: int) -> float:
		var gx: float = x / cell
		var gz: float = z / cell
		var i: int = floori(gx)
		var j: int = floori(gz)
		var fx: float = gx - i
		var fz: float = gz - j
		fx = fx * fx * (3.0 - 2.0 * fx)
		fz = fz * fz * (3.0 - 2.0 * fz)
		var v00: float = float(((i * 73856093) ^ (j * 19349663) ^ sd) & 0xffff) / 65535.0
		var v10: float = float((((i + 1) * 73856093) ^ (j * 19349663) ^ sd) & 0xffff) / 65535.0
		var v01: float = float(((i * 73856093) ^ ((j + 1) * 19349663) ^ sd) & 0xffff) / 65535.0
		var v11: float = float((((i + 1) * 73856093) ^ ((j + 1) * 19349663) ^ sd) & 0xffff) / 65535.0
		return lerpf(lerpf(v00, v10, fx), lerpf(v01, v11, fx), fz)

	## 1 on a road's paved corridor (half width + shoulder), easing to 0 `side` m beyond it; 0 off
	## the roads. Read from the road fields as _yield_to_roads reads them.
	func _road_reach(x: float, z: float, side: float, only: Dictionary) -> float:
		return 1.0 - _yield_to_roads_by(x, z, side, only)

	## The roads (road_list indices, as keys) that run onto a pad: their centre line comes within
	## 1 m of its rectangle (origin, size, rot). Roads only passing by are left alone (a ramp along a
	## pad's side would tilt them across).
	func _roads_onto(o: Vector2, size: Vector2, rot: float, box: Rect2) -> Dictionary:
		var out: Dictionary = {}
		var g: Rect2 = box.grow(2.0)
		for ri: int in road_list.size():
			var line: Polyline2 = road_list[ri]["line"]
			if not line.bounds.intersects(g):
				continue
			var s: float = 0.0
			while s <= line.total_length:
				var p: Vector2 = line.point_at(s)
				if g.has_point(p):
					var lp: Vector2 = (p - o).rotated(-rot)
					if lp.x > -1.0 and lp.y > -1.0 and lp.x < size.x + 1.0 and lp.y < size.y + 1.0:
						out[ri] = true
						break
				s += 2.0
		return out

	## How much a world town's pad skirt may grade a sample (ADR-0040): nothing on a road's paved
	## corridor (half width + shoulder), easing to all of it LOT_ROAD_YIELD m beyond, so a yard never
	## bumps a street. The road and its distance are read from the road fields as _band_roads reads them.
	func _yield_to_roads(x: float, z: float) -> float:
		return _yield_to_roads_by(x, z, LOT_ROAD_YIELD)

	func _yield_to_roads_by(x: float, z: float, ease: float, only: Dictionary = {}) -> float:
		var gx: float = clampf((x - cx0) / cs, 0.0, cn - 1.001)
		var gz: float = clampf((z - cz0) / cs, 0.0, cn - 1.001)
		var cx: int = mini(int(gx), cn - 2)
		var cz: int = mini(int(gz), cn - 2)
		var ci: int = cz * cn + cx
		var ri: int = r_idx[ci]
		if ri < 0:
			ri = r_idx[ci + cn + 1]
			if ri < 0:
				return 1.0
		var fx: float = gx - cx
		var fz: float = gz - cz
		# The distance to the nearest road is continuous even where the corners belong to different
		# roads: bilinear either way (VERSION 13; the nearest corner's stepped every 4 m).
		var d: float = _bl(r_d, ci, fx, fz)
		var i00: int = r_idx[ci]
		if not (i00 == r_idx[ci + 1] and i00 == r_idx[ci + cn] and i00 == r_idx[ci + cn + 1]):
			var nci: int = ci + (1 if fx > 0.5 else 0) + (cn if fz > 0.5 else 0)
			if r_idx[nci] >= 0:
				ri = r_idx[nci]
		if not only.is_empty() and not only.has(ri):
			return 1.0
		d += _r_half[ri]
		var inner: float = _r_half[ri] + _r_sh[ri]
		return smoothstep(inner, inner + ease, d)

	# --- 6. Surface: biome, splat, vegetation ---------------------------------------------------

	func _surface_pass() -> void:
		var biomes: PackedStringArray = [str(region.get("default_biome", "conifer_forest")), "riverbank", "rocky_slope", "town", "meadow", "birch_grove"]
		for p: Dictionary in paints:
			if not biomes.has(p["biome"]):
				biomes.append(p["biome"])
		for pad: Dictionary in pads:
			if not biomes.has(pad["biome"]):
				biomes.append(pad["biome"])
		# A generated world's biome map (ADR-0031): each cell's id maps to an index of `biomes`.
		var map_index := PackedInt32Array()
		var use_map: bool = world.has_biome_map()
		if use_map:
			for bid: String in world.biome_ids:
				if not biomes.has(bid):
					biomes.append(bid)
				map_index.append(biomes.find(bid))
		rt.biome_ids = biomes
		_s_map_index = map_index
		_s_use_map = use_map
		# The splat recipe of each biome (what the per-sample `match` on its name chose).
		_s_kind = PackedInt32Array()
		for bname: String in biomes:
			match bname:
				"conifer_forest":
					_s_kind.append(K_CONIFER)
				"birch_grove":
					_s_kind.append(K_BIRCH)
				"meadow", "yard":
					_s_kind.append(K_MEADOW)
				"town":
					_s_kind.append(K_TOWN)
				"riverbank":
					_s_kind.append(K_RIVERBANK)
				"rocky_slope":
					_s_kind.append(K_ROCKY)
				"burnt_forest":
					_s_kind.append(K_BURN)
				"fen":
					_s_kind.append(K_FEN)
				_:
					_s_kind.append(K_OTHER)
		# Paints and pads by bounding box first: a sample outside every box skips the exact tests
		# (same result, and most samples are outside most of them).
		_paint_boxes.clear()
		for pt0: Dictionary in paints:
			var reach: float = float(pt0["r"]) + float(pt0["blend"]) * 0.8 + 1.0
			_paint_boxes.append(Rect2((pt0["pos"] as Vector2) - Vector2(reach, reach), Vector2(reach, reach) * 2.0))
			_paint_pos.append(pt0["pos"])
			_paint_blend.append(float(pt0["blend"]))
			_paint_r.append(float(pt0["r"]))
			_paint_bi.append(biomes.find(pt0["biome"]))
		_pad_boxes.clear()
		for pad0: Dictionary in pads:
			var o0: Vector2 = pad0["origin"]
			var s0: Vector2 = pad0["size"]
			var r0: float = pad0["rot"]
			var bb0 := Rect2(o0, Vector2.ZERO)
			for c0: Vector2 in [Vector2(s0.x, 0.0), s0, Vector2(0.0, s0.y)]:
				bb0 = bb0.expand(o0 + c0.rotated(r0))
			_pad_boxes.append(bb0.grow(1.5))
			_pad_origin.append(o0)
			_pad_rot.append(float(pad0["rot"]))
			_pad_size.append(s0)
			_pad_bi.append(biomes.find(pad0["biome"]))
			_pad_veg.append(float(pad0.get("veg", 0.0)))
		var clear_boxes: Array[Rect2] = []
		for cl0: Dictionary in clearings:
			var cr: float = float(cl0["r"]) + 6.0
			clear_boxes.append(Rect2((cl0["pos"] as Vector2) - Vector2(cr, cr), Vector2(cr, cr) * 2.0))
			_cl_pos.append(cl0["pos"])
			_cl_r.append(float(cl0["r"]))
		var pal: PackedStringArray = rt.palette
		# forest_floor, moss_ground, grass_ground, dirt, mud, gravel, asphalt_cracked, sand, ash_char, peat
		_s_layers = PackedInt32Array([pal.find("forest_floor"), pal.find("moss_ground"), pal.find("grass_ground"), pal.find("dirt"),
			pal.find("mud"), pal.find("gravel"), pal.find("asphalt_cracked"), pal.find("sand"), pal.find("ash_char"), pal.find("peat")])
		_s_town_bi = biomes.find("town")
		for ri: int in road_list.size():
			var surface: String = str(road_list[ri]["surface"])
			_r_surf.append(_s_layers[6] if surface == "asphalt" else (_s_layers[5] if surface == "gravel" else _s_layers[3]))
			_r_town.append(_town_road(road_list[ri]))
		for pad1: Dictionary in pads:
			var psurf: String = str(pad1.get("surface", ""))
			_pad_surf.append(-1 if psurf == "" else (_s_layers[6] if psurf == "asphalt" else (_s_layers[5] if psurf == "gravel" else _s_layers[3])))
		for pth: Dictionary in paths:
			var pl: Polyline2 = pth["line"]
			_path_off.append(_path_pts.size())
			_path_pts.append_array(pl.points)
			_path_bounds.append(pl.bounds.grow(6.0))
			_path_w.append(float(pth["width"]))
		# The 32 m index: per cell, the paints, pads and clearings whose boxes reach it and the paths
		# with a segment near it, each in ascending order, so a sample tests the same items in the
		# same order as a walk over all of them did, less those that can't reach it.
		_bk_n = int(ceil(rect.size.x / BUCKET)) + 1
		var csr: Array = _bucket(_paint_boxes)
		_bk_paint_start = csr[0]
		_bk_paint_items = csr[1]
		csr = _bucket(_pad_boxes)
		_bk_pad_start = csr[0]
		_bk_pad_items = csr[1]
		csr = _bucket(clear_boxes)
		_bk_clear_start = csr[0]
		_bk_clear_items = csr[1]
		_bucket_paths()
		_s_pn.seed = world.seed + 202
		_s_pn.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		_s_pn.fractal_type = FastNoiseLite.FRACTAL_FBM
		_s_pn.fractal_octaves = 3
		_s_pn.frequency = 0.035
		# Biome-map edges wander by up to ~1.5 cells (two slow channels) so they read as stands and
		# clearings rather than the map's squares.
		if use_map:
			_s_qn.seed = world.seed + 303
			_s_qn.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
			_s_qn.fractal_type = FastNoiseLite.FRACTAL_FBM
			_s_qn.fractal_octaves = 3
			_s_qn.frequency = 0.0075
		# Patch noise on the coarse grid (two channels), bilinear per sample.
		var patch: Array = _run_bands(cn, _band_patch)
		_p1 = _concat_f32(patch, 0)
		_p2 = _concat_f32(patch, 1)
		_q1 = _concat_f32(patch, 2)
		_q2 = _concat_f32(patch, 3)
		if _cancelled():
			return
		var ratio: float = sp / cs
		for ix: int in n:
			var gx: float = ix * ratio
			var cx2: int = mini(int(gx), cn - 2)
			_s_col_c.append(cx2)
			_s_col_f.append(gx - cx2)
			_s_col_b.append(clampi(int(floor((_col_x[ix] - cx0) / BUCKET)), 0, _bk_n - 1))
		var parts: Array = _run_bands(n, _band_surface)
		rt.splat0 = _concat_bytes(parts, 0)
		rt.splat1 = _concat_bytes(parts, 1)
		rt.biome = _concat_bytes(parts, 2)
		rt.vegmask = _concat_bytes(parts, 3)

	## 1: a world town's own street; 2: a world road (the highway its main street is) whose line comes
	## into a town's disc; 0: any other road.
	func _town_road(r: Dictionary) -> int:
		if str(r.get("profile_key", "")).begins_with("town:"):
			return 1
		if not r.has("world_index"):
			return 0
		var bounds: Rect2 = (r["line"] as Polyline2).bounds
		for k: int in _town_c.size():
			var c: Vector2 = _town_c[k]
			var rr: float = _town_r[k]
			if bounds.intersects(Rect2(c - Vector2(rr, rr), Vector2(rr, rr) * 2.0)) and (r["line"] as Polyline2).closest(c).x < rr:
				return 2
		return 0

	## [start, items]: the indices of `boxes` (grown 1 m) that reach each index cell, ascending.
	func _bucket(boxes: Array[Rect2]) -> Array:
		var lists: Dictionary = {}
		var reach: Rect2 = rect.grow(BUCKET)
		for k: int in boxes.size():
			var b: Rect2 = boxes[k].grow(1.0)
			if not b.intersects(reach):
				continue
			for c: int in _cells_of(b):
				if not lists.has(c):
					lists[c] = []
				(lists[c] as Array).append(k)
		var cells: int = _bk_n * _bk_n
		var start := PackedInt32Array()
		start.resize(cells + 1)
		var items := PackedInt32Array()
		for c2: int in cells:
			start[c2] = items.size()
			if lists.has(c2):
				items.append_array(PackedInt32Array(lists[c2]))
		start[cells] = items.size()
		return [start, items]

	## The paths' index: per cell, each path (ascending) with a segment near the cell, and those
	## segments (ascending). A path paints within its half width + 1.9 m of its line and segments
	## are indexed out to half width + 4 m, so a sample's nearest segment of any path that paints it
	## is in its cell's list, and the distance over the listed segments is closest()'s distance.
	func _bucket_paths() -> void:
		var lists: Dictionary = {}
		var reach: Rect2 = rect.grow(BUCKET)
		for pi: int in paths.size():
			var pl: Polyline2 = paths[pi]["line"]
			var grow: float = _path_w[pi] * 0.5 + 4.0
			for si: int in pl.points.size() - 1:
				var sb: Rect2 = Rect2(pl.points[si], Vector2.ZERO).expand(pl.points[si + 1]).grow(grow)
				if not sb.intersects(reach):
					continue
				for c: int in _cells_of(sb):
					if not lists.has(c):
						lists[c] = {}
					var per: Dictionary = lists[c]
					if not per.has(pi):
						per[pi] = []
					(per[pi] as Array).append(si)
		var cells: int = _bk_n * _bk_n
		_bk_path_start.resize(cells + 1)
		for c2: int in cells:
			_bk_path_start[c2] = _bk_path_of.size()
			if not lists.has(c2):
				continue
			var per2: Dictionary = lists[c2]
			var keys: Array = per2.keys()
			keys.sort()
			for pi2: int in keys:
				_bk_path_of.append(pi2)
				_bk_path_seg_start.append(_bk_path_segs.size())
				_bk_path_segs.append_array(PackedInt32Array(per2[pi2]))
		_bk_path_start[cells] = _bk_path_of.size()
		_bk_path_seg_start.append(_bk_path_segs.size())

	## The index cells a world rect touches.
	func _cells_of(b: Rect2) -> PackedInt32Array:
		var x0: int = clampi(int(floor((b.position.x - cx0) / BUCKET)), 0, _bk_n - 1)
		var x1: int = clampi(int(floor((b.end.x - cx0) / BUCKET)), 0, _bk_n - 1)
		var z0: int = clampi(int(floor((b.position.y - cz0) / BUCKET)), 0, _bk_n - 1)
		var z1: int = clampi(int(floor((b.end.y - cz0) / BUCKET)), 0, _bk_n - 1)
		var out := PackedInt32Array()
		for bz: int in range(z0, z1 + 1):
			for bx: int in range(x0, x1 + 1):
				out.append(bz * _bk_n + bx)
		return out

	func _band_patch(r0: int, r1: int) -> Array:
		var cnn: int = cn
		var cnt: int = (r1 - r0) * cnn
		var a1 := PackedFloat32Array()
		a1.resize(cnt)
		var a2 := PackedFloat32Array()
		a2.resize(cnt)
		var b1 := PackedFloat32Array()
		var b2 := PackedFloat32Array()
		var use_map: bool = _s_use_map
		if use_map:
			b1.resize(cnt)
			b2.resize(cnt)
		var pn: FastNoiseLite = _s_pn
		var qn: FastNoiseLite = _s_qn
		var bstep: float = world.biome_step
		var x_0: float = cx0
		var z_0: float = cz0
		var step: float = cs
		var cancel_flag: Array = cancel
		for cz: int in range(r0, r1):
			if (cz - r0) % CANCEL_ROWS == CANCEL_ROWS - 1 and bool(cancel_flag[0]):
				break
			for cx: int in cnn:
				var x: float = x_0 + cx * step
				var z: float = z_0 + cz * step
				var k: int = (cz - r0) * cnn + cx
				a1[k] = pn.get_noise_2d(x, z) * 0.5 + 0.5
				a2[k] = pn.get_noise_2d(x + 913.0, z - 377.0) * 0.5 + 0.5
				if use_map:
					b1[k] = qn.get_noise_2d(x, z) * bstep * 1.5
					b2[k] = qn.get_noise_2d(x - 1711.0, z + 529.0) * bstep * 1.5
		return [a1, a2, b1, b2]

	func _band_surface(z0: int, z1: int) -> Array:
		var nn: int = n
		var cnn: int = cn
		var rows: int = z1 - z0
		var s0b := PackedByteArray()
		s0b.resize(rows * nn * 4)
		var s1b := PackedByteArray()
		s1b.resize(rows * nn * 4)
		var bio := PackedByteArray()
		bio.resize(rows * nn)
		var vgm := PackedByteArray()
		vgm.resize(rows * nn)
		var w := PackedFloat32Array()
		w.resize(8)
		var lay: PackedInt32Array = _s_layers
		var L_FOREST: int = lay[0]
		var L_MOSS: int = lay[1]
		var L_GRASS: int = lay[2]
		var L_DIRT: int = lay[3]
		var L_MUD: int = lay[4]
		var L_GRAVEL: int = lay[5]
		var L_SAND: int = lay[7]
		var L_ASH: int = lay[8]
		var L_PEAT: int = lay[9]
		var hh: PackedFloat32Array = h
		var p1: PackedFloat32Array = _p1
		var p2: PackedFloat32Array = _p2
		var q1: PackedFloat32Array = _q1
		var q2: PackedFloat32Array = _q2
		var wdd: PackedFloat32Array = w_d
		var wkind: PackedByteArray = w_kind
		var ridx: PackedInt32Array = r_idx
		var rdd: PackedFloat32Array = r_d
		var rhalf: PackedFloat64Array = _r_half
		var rsh: PackedFloat64Array = _r_sh
		var rsurf: PackedInt32Array = _r_surf
		var rtown: PackedByteArray = _r_town
		var town_bi: int = _s_town_bi
		var town_c: PackedVector2Array = _town_c
		var town_r: PackedFloat64Array = _town_r
		var col_c: PackedInt32Array = _s_col_c
		var col_f: PackedFloat64Array = _s_col_f
		var col_b: PackedInt32Array = _s_col_b
		var col_x: PackedFloat64Array = _col_x
		var kind: PackedInt32Array = _s_kind
		var use_map: bool = _s_use_map
		var map_index: PackedInt32Array = _s_map_index
		var wrp: Vector2 = world.world_rect().position
		var bstep: float = world.biome_step
		var bcols: int = world.biome_cols
		var brows: int = world.biome_rows
		var bcells: PackedByteArray = world.biome_cells
		var bk_n: int = _bk_n
		var pst: PackedInt32Array = _bk_paint_start
		var pit: PackedInt32Array = _bk_paint_items
		var pboxes: Array[Rect2] = _paint_boxes
		var ppos: PackedVector2Array = _paint_pos
		var pblend: PackedFloat64Array = _paint_blend
		var prad: PackedFloat64Array = _paint_r
		var pbi: PackedInt32Array = _paint_bi
		var dst: PackedInt32Array = _bk_pad_start
		var dit: PackedInt32Array = _bk_pad_items
		var dboxes: Array[Rect2] = _pad_boxes
		var dorg: PackedVector2Array = _pad_origin
		var drot: PackedFloat64Array = _pad_rot
		var dsize: PackedVector2Array = _pad_size
		var dbi: PackedInt32Array = _pad_bi
		var dveg: PackedFloat64Array = _pad_veg
		var dsurf: PackedInt32Array = _pad_surf
		var cst: PackedInt32Array = _bk_clear_start
		var cit: PackedInt32Array = _bk_clear_items
		var clpos: PackedVector2Array = _cl_pos
		var clr: PackedFloat64Array = _cl_r
		var hst: PackedInt32Array = _bk_path_start
		var hof: PackedInt32Array = _bk_path_of
		var hss: PackedInt32Array = _bk_path_seg_start
		var hsegs: PackedInt32Array = _bk_path_segs
		var hpts: PackedVector2Array = _path_pts
		var hoff: PackedInt32Array = _path_off
		var hbounds: Array[Rect2] = _path_bounds
		var hw: PackedFloat64Array = _path_w
		var cancel_flag: Array = cancel
		var ratio: float = sp / cs
		var spc: float = sp
		var z_0: float = cz0
		var b_default: int = 0
		for iz: int in range(z0, z1):
			if (iz - z0) % CANCEL_ROWS == CANCEL_ROWS - 1 and bool(cancel_flag[0]):
				break
			var gz: float = iz * ratio
			var cz2: int = mini(int(gz), cnn - 2)
			var fz: float = gz - cz2
			var z: float = z_0 + iz * spc
			var row: int = iz * nn
			var lrow: int = (iz - z0) * nn
			var brow: int = clampi(floori((z - z_0) / BUCKET), 0, bk_n - 1) * bk_n
			var hrow_u: int = maxi(iz - 1, 0) * nn
			var hrow_d: int = mini(iz + 1, nn - 1) * nn
			for ix: int in nn:
				var cx2: int = col_c[ix]
				var fx: float = col_f[ix]
				var ci: int = cz2 * cnn + cx2
				var x: float = col_x[ix]
				var li: int = lrow + ix
				var cell: int = brow + col_b[ix]
				# Patch noise, bilinear (_bl; its values are never the distance fields' 1e9 "far").
				var a: float = p1[ci]
				var top: float = a + (p1[ci + 1] - a) * fx
				var c: float = p1[ci + cnn]
				var n1: float = top + ((c + (p1[ci + cnn + 1] - c) * fx) - top) * fz
				a = p2[ci]
				top = a + (p2[ci + 1] - a) * fx
				c = p2[ci + cnn]
				var n2: float = top + ((c + (p2[ci + cnn + 1] - c) * fx) - top) * fz
				# Slope from neighbours.
				var hl: float = hh[row + maxi(ix - 1, 0)]
				var hr: float = hh[row + mini(ix + 1, nn - 1)]
				var hu: float = hh[hrow_u + ix]
				var hd: float = hh[hrow_d + ix]
				var grad: float = sqrt((hr - hl) * (hr - hl) + (hd - hu) * (hd - hu)) / (2.0 * spc)
				var slope: float = rad_to_deg(atan(grad))
				# Biome.
				var bi: int = b_default
				if use_map:
					a = q1[ci]
					top = a + (q1[ci + 1] - a) * fx
					c = q1[ci + cnn]
					var m1: float = top + ((c + (q1[ci + cnn + 1] - c) * fx) - top) * fz
					a = q2[ci]
					top = a + (q2[ci + 1] - a) * fx
					c = q2[ci + cnn]
					var m2: float = top + ((c + (q2[ci + cnn + 1] - c) * fx) - top) * fz
					var bx: int = clampi(floori((x + m1 - wrp.x) / bstep), 0, bcols - 1)
					var bz: int = clampi(floori((z + m2 - wrp.y) / bstep), 0, brows - 1)
					var mi: int = bcells[bz * bcols + bx]
					if mi < map_index.size():
						bi = map_index[mi]
				for j: int in range(pst[cell], pst[cell + 1]):
					var pidx: int = pit[j]
					if not pboxes[pidx].has_point(Vector2(x, z)):
						continue
					var dd: float = Vector2(x, z).distance_to(ppos[pidx]) + (n1 - 0.5) * pblend[pidx] * 1.6
					if dd < prad[pidx]:
						bi = pbi[pidx]
				# The nearest road and its distance (a world town's streets here, every road below).
				var ri: int = ridx[ci]
				if ri < 0:
					ri = ridx[ci + cnn + 1]
				var rd: float = 1.0e9
				if ri >= 0:
					# _bl(r_d, ci, fx, fz)
					var ra: float = rdd[ci]
					var rb: float = rdd[ci + 1]
					var rc: float = rdd[ci + cnn]
					var rdx: float = rdd[ci + cnn + 1]
					if ra > 1.0e8 or rb > 1.0e8 or rc > 1.0e8 or rdx > 1.0e8:
						rd = minf(minf(ra, rb), minf(rc, rdx))
					else:
						var rtop: float = ra + (rb - ra) * fx
						rd = rtop + ((rc + (rdx - rc) * fx) - rtop) * fz
					rd += rhalf[ri]
					# A world town's street and its verges are town ground (ADR-0047).
					var tk: int = rtown[ri]
					if tk > 0 and rd < rhalf[ri] + rsh[ri] + TOWN_VERGE + n2 * 2.0:
						if tk == 1:
							bi = town_bi
						else:
							for k5: int in town_c.size():
								if Vector2(x, z).distance_to(town_c[k5]) < town_r[k5]:
									bi = town_bi
									break
				var wd: float = 1.0e9
				var wk: int = 0
				if wdd[ci] < 60.0 or wdd[ci + cnn + 1] < 60.0:
					# _bl(w_d, ci, fx, fz)
					var wa: float = wdd[ci]
					var wb: float = wdd[ci + 1]
					var wc: float = wdd[ci + cnn]
					var wdx: float = wdd[ci + cnn + 1]
					if wa > 1.0e8 or wb > 1.0e8 or wc > 1.0e8 or wdx > 1.0e8:
						wd = minf(minf(wa, wb), minf(wc, wdx))
					else:
						var wtop: float = wa + (wb - wa) * fx
						wd = wtop + ((wc + (wdx - wc) * fx) - wtop) * fz
					wk = wkind[ci]
				# A fen keeps its own wet margins (ADR-0041); other ground turns riverbank by water.
				if wd < 14.0 + n2 * 10.0 and kind[bi] != K_FEN:
					bi = 1
				var pad_hit: int = -1
				for j2: int in range(dst[cell], dst[cell + 1]):
					var pi: int = dit[j2]
					if not dboxes[pi].has_point(Vector2(x, z)):
						continue
					var lp: Vector2 = (Vector2(x, z) - dorg[pi]).rotated(-drot[pi])
					var size: Vector2 = dsize[pi]
					if lp.x >= -1.0 and lp.y >= -1.0 and lp.x <= size.x + 1.0 and lp.y <= size.y + 1.0:
						pad_hit = pi
						break
				if pad_hit >= 0:
					bi = dbi[pad_hit]
				if slope > 34.0 + n1 * 6.0:
					bi = 2
				bio[li] = bi
				# Splat weights (_add inlined: a layer the palette lacks (-1) or a zero amount adds
				# nothing).
				w.fill(0.0)
				var am: float
				# An if chain, not `match` (which is slower and serialises threads).
				var kb: int = kind[bi]
				if kb == K_CONIFER:
					if L_FOREST >= 0:
						w[L_FOREST] += 1.0
					am = smoothstep(0.45, 0.75, n1) * 0.9
					if L_MOSS >= 0 and am > 0.0:
						w[L_MOSS] += am
					am = smoothstep(0.7, 0.9, n2) * 0.35
					if L_DIRT >= 0 and am > 0.0:
						w[L_DIRT] += am
				elif kb == K_BIRCH:
					if L_GRASS >= 0:
						w[L_GRASS] += 0.8
					am = smoothstep(0.4, 0.7, n1)
					if L_FOREST >= 0 and am > 0.0:
						w[L_FOREST] += am
					am = smoothstep(0.65, 0.85, n2) * 0.5
					if L_MOSS >= 0 and am > 0.0:
						w[L_MOSS] += am
				elif kb == K_MEADOW:
					if L_GRASS >= 0:
						w[L_GRASS] += 1.0
					am = smoothstep(0.68, 0.9, n2) * 0.45
					if L_DIRT >= 0 and am > 0.0:
						w[L_DIRT] += am
				elif kb == K_TOWN:
					if L_GRASS >= 0:
						w[L_GRASS] += 0.9
					am = smoothstep(0.55, 0.8, n1) * 0.6
					if L_DIRT >= 0 and am > 0.0:
						w[L_DIRT] += am
					am = smoothstep(0.7, 0.9, n2) * 0.5
					if L_GRAVEL >= 0 and am > 0.0:
						w[L_GRAVEL] += am
				elif kb == K_RIVERBANK:
					am = smoothstep(2.0, 12.0, wd)
					if L_GRASS >= 0 and am > 0.0:
						w[L_GRASS] += am
					am = 1.0 - smoothstep(1.0, 6.0 + n1 * 4.0, wd)
					if L_GRAVEL >= 0 and am > 0.0:
						w[L_GRAVEL] += am
					am = (1.0 - smoothstep(0.0, 9.0, absf(wd - 3.0))) * smoothstep(0.35, 0.6, n2)
					if L_MUD >= 0 and am > 0.0:
						w[L_MUD] += am
				elif kb == K_ROCKY:
					if L_GRAVEL >= 0:
						w[L_GRAVEL] += 0.8
					if L_DIRT >= 0:
						w[L_DIRT] += 0.5
					am = smoothstep(0.6, 0.8, n1) * 0.4
					if L_MOSS >= 0 and am > 0.0:
						w[L_MOSS] += am
				elif kb == K_BURN:
					# Ash and char, grass coming back in drifts, bare burnt soil between.
					if L_ASH >= 0:
						w[L_ASH] += 1.0
					elif L_DIRT >= 0:
						w[L_DIRT] += 1.0
					am = smoothstep(0.42, 0.78, n1) * 0.85
					if L_GRASS >= 0 and am > 0.0:
						w[L_GRASS] += am
					am = smoothstep(0.62, 0.88, n2) * 0.45
					if L_DIRT >= 0 and am > 0.0:
						w[L_DIRT] += am
				elif kb == K_FEN:
					# Peat, sphagnum carpets on the rises, sedge meadow, the pools' muddy margins.
					if L_PEAT >= 0:
						w[L_PEAT] += 1.0
					elif L_MUD >= 0:
						w[L_MUD] += 1.0
					am = smoothstep(0.42, 0.75, n1) * 0.85
					if L_MOSS >= 0 and am > 0.0:
						w[L_MOSS] += am
					am = smoothstep(0.55, 0.85, n2) * 0.55
					if L_GRASS >= 0 and am > 0.0:
						w[L_GRASS] += am
					am = (1.0 - smoothstep(0.5, 3.5 + n1 * 3.0, wd)) * 0.9
					if L_MUD >= 0 and am > 0.0:
						w[L_MUD] += am
				else:
					if L_FOREST >= 0:
						w[L_FOREST] += 1.0
				if wk == 2 and wd < 6.0 + n1 * 3.0 and kb != K_FEN:
					# Forest lakes and ponds have muddy, stony margins with the odd sandy cove: a sand
					# ring all the way round read as a beach, and from the trees as a bleached halo.
					var shore: float = 1.0 - smoothstep(-2.0, 6.0, wd)
					var cove: float = smoothstep(0.6, 0.78, n2)
					am = shore * 1.5 * cove
					if L_SAND >= 0 and am > 0.0:
						w[L_SAND] += am
					am = shore * 1.2 * (1.0 - cove) * (0.45 + 0.55 * smoothstep(0.3, 0.65, n1))
					if L_MUD >= 0 and am > 0.0:
						w[L_MUD] += am
					am = shore * 0.7 * (1.0 - cove)
					if L_GRAVEL >= 0 and am > 0.0:
						w[L_GRAVEL] += am
				if wd < 0.0 and kb == K_FEN:
					# A fen pool's bed is soft peat and muck.
					w.fill(0.0)
					if L_PEAT >= 0:
						w[L_PEAT] += 0.8
					if L_MUD >= 0:
						w[L_MUD] += 0.5
				elif wd < 0.0:
					w.fill(0.0)
					if L_MUD >= 0:
						w[L_MUD] += 0.7
					am = 0.5 + n2 * 0.5
					if L_GRAVEL >= 0 and am > 0.0:
						w[L_GRAVEL] += am
				# A paved pad (a world town's square) is its surface, under the roads.
				if pad_hit >= 0 and dsurf[pad_hit] >= 0:
					w.fill(0.0)
					w[dsurf[pad_hit]] += 2.0
				var veg: float = 1.0
				if wd < 2.0 and kb == K_FEN:
					# Cattails, bulrush and drowned snags stand in a fen's pools: the scatter keeps only
					# species that wade there (SpeciesDef.wade_depth, ADR-0041).
					veg = 0.55 if wd < -0.25 else 0.55 + 0.45 * smoothstep(-0.25, 2.0, wd)
				elif wd < 2.0:
					# Sedges and horsetail grow right down to the waterline (and a little into it);
					# thinning them over the last two metres left a bare ring round every shore.
					veg = 0.0 if wd < -0.25 else 0.4 + 0.6 * smoothstep(-0.25, 2.0, wd)
				# Roads.
				if ri >= 0:
					var half: float = rhalf[ri]
					var sh: float = rsh[ri]
					var on_road: float = 1.0 - smoothstep(half - 0.6 + n2 * 0.8, half + 0.4 + n2 * 0.8, rd)
					var on_sh: float = (1.0 - smoothstep(half + sh * 0.5, half + sh + 1.0, rd)) * (1.0 - on_road)
					if on_road > 0.0 or on_sh > 0.0:
						var surf: int = rsurf[ri]
						for k: int in 8:
							w[k] *= (1.0 - on_road) * (1.0 - on_sh * 0.6)
						am = on_road * 2.0
						if surf >= 0 and am > 0.0:
							w[surf] += am
						var shl: int = L_GRAVEL if surf != L_GRAVEL else L_DIRT
						am = on_sh * 1.2
						if shl >= 0 and am > 0.0:
							w[shl] += am
					veg = minf(veg, smoothstep(half + sh * 0.5, half + sh + 3.0, rd))
				# Paths: the distance to the nearest listed segment, with Polyline2.closest()'s
				# arithmetic (and its single-precision result, it returns it in a Vector3).
				for e: int in range(hst[cell], hst[cell + 1]):
					var ph: int = hof[e]
					if not hbounds[ph].has_point(Vector2(x, z)):
						continue
					var pp := Vector2(x, z)
					var best_d2: float = INF
					var off: int = hoff[ph]
					for q: int in range(hss[e], hss[e + 1]):
						var si: int = off + hsegs[q]
						var sa: Vector2 = hpts[si]
						var ab: Vector2 = hpts[si + 1] - sa
						var l2: float = ab.length_squared()
						var t: float = 0.0 if l2 <= 0.0 else clampf((pp - sa).dot(ab) / l2, 0.0, 1.0)
						var qq: Vector2 = sa + ab * t
						var d2: float = pp.distance_squared_to(qq)
						if d2 < best_d2:
							best_d2 = d2
					var pd: float = Vector2(sqrt(best_d2), 0.0).x
					var pw: float = hw[ph] * 0.5 + (n2 - 0.5) * 0.8
					if pd < pw + 1.5:
						var pk: float = 1.0 - smoothstep(pw - 0.4, pw + 1.2, pd)
						for k2: int in 8:
							w[k2] *= 1.0 - pk * 0.8
						am = pk * 1.5
						if L_DIRT >= 0 and am > 0.0:
							w[L_DIRT] += am
						veg = minf(veg, smoothstep(pw - 0.3, pw + 1.5, pd))
				if pad_hit >= 0:
					# Bare under a building's pad; a world town's yard keeps grass round its edges, where
					# no building stands (a generated one keeps 3 m from its lot's sides and back and its
					# setback from the front; a floor 0.15 m up hid no grass).
					# VERSION 13: a world town's yard keeps its plants over the whole frame; the house
					# that stands there (known only to the run) clears its own box at runtime
					# (VegetationManager._footprints), so the yard grows up to its walls.
					veg = minf(veg, dveg[pad_hit])
				for j3: int in range(cst[cell], cst[cell + 1]):
					var ck: int = cit[j3]
					var dc: float = Vector2(x, z).distance_to(clpos[ck])
					if dc < clr[ck] + 6.0:
						veg = minf(veg, smoothstep(clr[ck], clr[ck] + 6.0, dc))
				# Normalize + quantize.
				var total: float = 0.0
				for k3: int in 8:
					total += w[k3]
				if total <= 0.0:
					w[maxi(L_FOREST, 0)] = 1.0
					total = 1.0
				var o4: int = li * 4
				for k4: int in 4:
					s0b[o4 + k4] = roundi(w[k4] / total * 255.0)
					s1b[o4 + k4] = roundi(w[k4 + 4] / total * 255.0)
				vgm[li] = roundi(clampf(veg, 0.0, 1.0) * 255.0)
		return [s0b, s1b, bio, vgm]

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
			# Samples every 6 m of arc from the source, as ever, but only along the stretch near
			# this region (a long river's other samples can't land in its margin).
			var kmax: int = int(line.total_length / 6.0)
			while 6.0 * (kmax + 1) <= line.total_length:
				kmax += 1
			while kmax > 0 and 6.0 * kmax > line.total_length:
				kmax -= 1
			for k: int in _arc_ks(line, margin, 6.0, kmax):
				var s: float = k * 6.0
				var p: Vector2 = line.point_at(s)
				if margin.has_point(p):
					pts.append([p.x, p.y])
					widths.append(line.value_at(r["width"], s))
					levels.append(line.value_at(r["level"], s))
					arcs.append(s)
			if pts.size() > 1:
				rt.water.append({"kind": "river", "id": r["id"], "points": pts, "widths": widths, "levels": levels, "arcs": arcs})
		for l: Dictionary in world.lakes:
			if (l["bounds"] as Rect2).intersects(margin):
				rt.water.append({"kind": "lake", "id": l["id"], "level": l["level"], "polygon": _poly_to_array(l["polygon"])})
		var feats: Array = region.get("features", [])
		for fi: int in feats.size():
			var f: Dictionary = feats[fi]
			match str(f.get("type", "")):
				"lake":
					var poly: PackedVector2Array = _lake_poly(f)
					rt.water.append({"kind": "lake", "id": str(f.get("id", "lake")), "level": float(_lake_levels[fi]), "polygon": _poly_to_array(poly)})
				"spawn":
					var sp2: Vector2 = _v2(f["pos"])
					rt.spawns[str(f["id"])] = {"pos": [sp2.x, hf.sample(sp2.x, sp2.y), sp2.y], "yaw": float(f.get("yaw", 0.0)), "props": f.get("props", [])}
				"frontier":
					rt.frontiers.append(f)
		for pad: Dictionary in pads:
			if bool(pad.get("world", false)):
				continue
			var o: Vector2 = pad["origin"]
			rt.placements.append({"kind": pad["kind"], "def": pad["def"], "id": pad["id"], "origin": [o.x, float(pad.get("height", hf.sample(o.x, o.y))), o.y],
				"rotation": rad_to_deg(float(pad["rot"])), "size": [pad["size"].x, pad["size"].y]})
		# World towns (ADR-0040): a lot is placed by the region holding its frame's centre (one owner
		# each; origin the frame's centre at the lot's height, rotation -yaw as the composer turns),
		# and every region the town touches places the fixtures standing in its rect (`town`).
		for tw: Dictionary in _towns:
			var fw: FrameworkDef = tw["fw"]
			for lv: Variant in fw.lots:
				var l: Dictionary = lv
				if not l.has("frame"):
					continue
				var f: Array = l["frame"]
				if world.region_at(float(f[0]), float(f[1])) != region_id:
					continue
				rt.placements.append({"kind": "lot", "def": String(fw.id), "town": tw["id"], "lot": str(l.get("id", "")), "id": "%s/%s" % [tw["id"], l.get("id", "")],
					"origin": [float(f[0]), float(l.get("y", 0.0)), float(f[1])], "rotation": -float(f[4]), "size": [float(f[2]), float(f[3])]})
			rt.placements.append({"kind": "town", "def": String(fw.id), "id": tw["id"], "origin": [0.0, 0.0, 0.0], "rotation": 0.0,
				"rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y]})
		for r: Dictionary in road_list:
			var line: Polyline2 = r["line"]
			if not line.bounds.grow(16.0).intersects(margin) or not r.has("profile"):
				continue
			var pts: Array = []
			var prof: PackedFloat32Array = r["profile"]
			var step: float = float(r["step"])
			for k: int in _arc_ks(line, margin, step, prof.size() - 1):
				var p: Vector2 = line.point_at(k * step)
				if margin.has_point(p):
					pts.append([p.x, prof[k], p.y])
			rt.roads.append({"id": r["id"], "surface": r["surface"], "width": r["width"], "points": pts, "markings": r.get("markings", true)})
			for span: Array in r["spans"]:
				var a: Vector2 = line.point_at(float(span[0]))
				var bpt: Vector2 = line.point_at(float(span[1]))
				rt.bridges.append({"road": r["id"], "from": [a.x, float(span[2]), a.y], "to": [bpt.x, float(span[2]), bpt.y], "width": float(r["width"]) + 1.0})

	## The k in 0..kmax, ascending, whose arc length k * step can lie in `box`: those on segments
	## near it (grown 1 m against rounding), widened by one step each way. A point at arc s lies on
	## the segment holding s, so every k whose point is inside `box` is among them.
	static func _arc_ks(line: Polyline2, box: Rect2, step: float, kmax: int) -> PackedInt32Array:
		var out := PackedInt32Array()
		var pts: PackedVector2Array = line.points
		var nseg: int = pts.size() - 1
		if nseg < 1:
			for k: int in kmax + 1:
				out.append(k)
			return out
		var grown: Rect2 = box.grow(1.0)
		var last: int = -1
		for si: int in nseg:
			var sb: Rect2 = Rect2(pts[si], Vector2.ZERO).expand(pts[si + 1]).grow(1.0)
			if not sb.intersects(grown):
				continue
			var k0: int = maxi(int(floor(line.lengths[si] / step)) - 1, 0)
			var k1: int = kmax if si == nseg - 1 else mini(int(ceil(line.lengths[si + 1] / step)) + 1, kmax)
			for k: int in range(maxi(k0, last + 1), k1 + 1):
				out.append(k)
			last = maxi(last, k1)
		return out

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
