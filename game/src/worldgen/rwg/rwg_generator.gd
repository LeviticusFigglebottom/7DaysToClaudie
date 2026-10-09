class_name RwgGenerator
extends RefCounted
## The random world generator (ADR-0031; organic towns ADR-0040, DESIGN §10.2). A pure function of
## (map seed, resolved WorldGenSettings, VERSION) that writes the same structure as the handcrafted
## map: a world.json (macro grid, rivers, lakes, roads, biome map, region roster and, since VERSION
## 2, the world-level towns) and one region.json feature list per region in the vocabulary of
## docs/REGIONS.md, plus the towns as frameworks. Composing, vegetation, water, POI placement and
## streaming then work unchanged.
##
## Stages: land (Terrain: shape, lakes, hydrology, valleys, rivers) -> town sites by size class from
## the town density (low, level, dry ground; a gently smoothed core) -> the road network through
## the town centres (a spanning tree plus loops and exits off the map, routed by Roads with a valley
## term; every town gets a main street through its centre, stubbed out past its edge where the
## network gives it none, and a town a cross street) -> each town planned on a worker thread
## (RwgTownPlanner: streets grown over the land, lots by frontage, zoning by rings, fixtures) and
## settled against its neighbours and the map's edge -> the drop site and its trail -> danger by
## distance from it, and each town's tier range -> the biome map -> places (roadside, lake shore,
## summit, waterside, forest, remote; farmsteads) with their drives, tracks and trails -> bridges ->
## Bloom patches far from the start -> regions -> each lot's pad height from the final ground ->
## authored buildings capped world-wide (LotPicker.assign_authored).
## Every stage draws from its own derived stream, so a change in one does not reshuffle the others.
## Run it on a worker thread (`progress` is called with (stage, 0..1)); content comes from
## ContentDB.instance.
##
## Towns are world-level features (plan §3): a town's lots are frames in world XZ (frameworks.json,
## `layout: "organic"`, placed at the origin with no rotation), and world.json `towns` lists each
## with its bounds, so the composer applies it in every region it touches, graded from world data
## alone (its streets from the reference ground, each lot's pad at the height `y` computed here from
## the same ground), and a town may straddle region borders.

## New ADR-0031/0040 scripts by path, so this compiles before the editor registers their class names.
const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")
const Roads := preload("res://src/worldgen/rwg/rwg_roads.gd")
const Planner := preload("res://src/worldgen/rwg/rwg_town_planner.gd")
const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")
const Grid := preload("res://src/worldgen/spatial_grid.gd")
const LotPicker := preload("res://src/poi/lot_picker.gd")

## Bump when the output for a given seed and settings changes: it is part of every world's id, so
## saves made with an older generator regenerate their world as it was (cached) or as now (TD-082).
## 2: organic world-level towns (ADR-0040), town density, place caps per 16 km², the drop site away
## from region borders, a valley term in the router, RwgStreets.point_in for polygon tests.
## 3: a trader post by each town (session 2's `trader:program_relay:<n>` spawns, ADR-0039).
## 4: burnt forest (fire scars) and fen (low wet ground, with pools) in the biome map (ADR-0041).
## 5: wilderness pool entries may be `unique` (one per world whatever its size: the field lab).
## 6: the Ashen high camp joins the wilderness pool (ADR-0048), so worlds cached at 5 regenerate.
## 7: `mine` sites (TD-169): the Corvane adit dug into a hillside, its buried levels under the
## ground, placed last from their own stream (every other place stays where it was).
## 8: the `companion` site (ADR-0058): Ezra Vane's camp, once, in a ring round the drop site, after
## the mines from its own stream, with no way in (every other place stays where it was).
## 9: the forest set pieces (ADR-0053) join the wilderness pool as `late` entries, each from its own
## stream after the farmsteads.
## 10: (session 3's caves.)
## 11: round 5 of the wilderness set pieces (ADR-0053): more `late` entries (the treehouse holdout,
## the fish hatchery, the hot springs bathhouse); the places before them stay where they were.
## 12: the lake and river valley caps are cut into the macro grid (RwgTerrain._valley_caps), so
## roads, streets and lots are graded from the ground the composer makes (player report 4); only a
## town's core turns meadow in the biome map (birch round it, the forest past its lots).
## 13: the lift's crash site (`crash` site, the hub's lift3_crash_site): once, 600-1600 m out from
## the drop site toward the nearest map edge (where the lift came in over), its nose to the drop;
## placed last from its own stream, so every other place stays where it was.
## 14: a town lot's height stays within LOT_STREET_STEP of its street's profile where it meets it
## (TerrainComposer.town_street_profiles, composer 14): no lip between a yard and its street (TD-318).
## 15: the world roads a town's lots and streets meet are the composer's pinned ones (composer 15);
## world.json lists the places levelled from world data (`pads`), which the world roads pin to (TD-320);
## 16: a roadside place's pad stands at its road's level where its drive leaves it (`level_at`,
## composer 16; TD-320).
## 17: road shape (TD-139): a routed road's hooks (turns back over 120 degrees) are cut even up a
## steep pitch, and a track or trail off a road starts where it leaves the road's cells, not beside it.
const VERSION: int = 17
## Biome map ids by cell value (world.json `biome_map.ids`); append only.
const BIOMES: PackedStringArray = ["conifer_forest", "birch_grove", "meadow", "rocky_slope", "burnt_forest", "fen"]
const KINDS: PackedStringArray = ["hamlet", "village", "town"]

var settings: GenSettings
var tun: Dictionary
## The town planner's tuning (data/config/town_planner.json).
var ptun: Dictionary
var names: Dictionary
var terrain := Terrain.new()
var router := Roads.new()
var world_id: String = ""
var size: int = 4
## {id, name, kind, fw_id, center: Vector2, radius, core, cell, tier: [lo, hi], plan (the planner's
##  output, lots settled), authored: PackedStringArray, bounds: Rect2}
var towns: Array[Dictionary] = []
## {id, kind: "poi" | "framework", def, origin: Vector2, rot, size: Vector2, poly, biome, skirt,
##  keep_water, access: Vector2, site, cell, pad: Vector2 (a mine's levelled surface part; ZERO: all)}
var places: Array[Dictionary] = []
## Trader posts (session 2's TraderManager, ADR-0039): {id, pos, yaw, cell, poly, safe, town}.
var posts: Array[Dictionary] = []
## {id, name, class, points: PackedVector2Array, width, shoulder, surface, markings, bridges}
var roads: Array[Dictionary] = []
## {id, points: PackedVector2Array, width, surface}
var paths: Array[Dictionary] = []
## {pos: Vector2, yaw: degrees, cell}
var drop: Dictionary = {}
## {id, at: Vector2, radius, strength, edge, cell}
var blooms: Array[Dictionary] = []
## Forest caves (ADR-0056): {id, cell, style, mouth: Vector2}, region `cave` features.
var caves: Array[Dictionary] = []
## cell -> {cell, id, name, biome, danger, rect}
var regions: Dictionary = {}
var biome_cols: int = 0
var biome_step: float = 64.0
var biome_cells := PackedByteArray()
## Water distance per macro cell (m, chamfer), for quick site tests.
var water_dist := PackedFloat32Array()
var timings: Dictionary = {}
## Milliseconds of the steps inside the stages (ADR-0038's measurements; not written to the world).
var sub_timings: Dictionary = {}
var warnings: PackedStringArray = []
var progress: Callable = Callable()
## Test hook: town sites to use instead of searching for them ([{kind, center: Vector2, radius}];
## the seam test puts a town across region borders). Empty in play.
var test_sites: Array = []

var _t0: int = 0
var _t_sub: int = 0
var _last_report: int = 0
## Spatial indexes, 256 m cells (ADR-0038): road segments and road vertices as Grid.pack(road,
## part), places by index, river segments, the towns' lot frames and street segments. They narrow
## nearest_road, road_clearance, _hits_built and the water distance to what can be near; every exact
## test stays.
var _seg_grid := Grid.new(256.0)
var _pt_grid := Grid.new(256.0)
var _place_grid := Grid.new(256.0)
var _river_grid := Grid.new(256.0)
var _river_widths: Array = []
var _lot_grid := Grid.new(256.0)
var _lot_polys: Array[PackedVector2Array] = []
## Each lot frame grown by tuning.towns.clearance.lots (what places keep off), and its town index.
var _lot_grown: Array[PackedVector2Array] = []
var _lot_town := PackedInt32Array()
var _street_grid := Grid.new(256.0)
## Every town street: {line: Polyline2, need: half width + shoulder, town}.
var _streets: Array[Dictionary] = []
## The widest road's half width plus shoulder (road_clearance's reach).
var _max_half: float = 0.0
## The composer's reference ground over the current macro grid (RefGround).
var _ref: RefGround = null
## How many roads there were when the towns were planned (later ones, tracks and drives to places,
## are checked against the lots once more).
var _roads_at_plan: int = 0
## Per POI def with buried levels: one sample per 2 m block of their cells outside the ground floor,
## [local centre: Vector2, ceiling above the floor: float] (the `mine` site's cover check).
var _buried_samples: Dictionary = {}
## The reference ground after every other place's levelling, for the mines' cover (dropped after run).
var _mine_ref: RefGround = null


## The ground the composer grades world roads and world pads from (TerrainComposer's
## `_reference_ground`): world.json's macro grid exactly as the composer reads it back (0.1 m steps,
## through JSON, float32, bicubic) plus the shared world detail noise. Read-only once made, so the
## planner's threads share it.
class RefGround extends RefCounted:
	## TerrainComposer._Build.WORLD_NOISE_AMP.
	const AMP: float = 2.5
	var wd := WorldDef.new()
	var noise := FastNoiseLite.new()

	func _init(t: RefCounted, world_seed: int, cols: int) -> void:
		var n: int = t.get(&"n")
		var hs: PackedFloat32Array = t.get(&"h")
		var rows: Array = []
		for j: int in n:
			var row: Array = []
			for i: int in n:
				row.append(snappedf(hs[j * n + i], 0.1))
			rows.append(row)
		# Written and read back as world.json is, so every value is the composer's to the last bit.
		var back: Variant = JSON.parse_string(JSON.stringify(rows, "", false))
		wd._parse({"seed": world_seed, "region_size": 1024.0, "cols": cols, "rows": cols, "macro": {"step": float(t.get(&"step")), "corner_heights": back,
			"noise": {"frequency": 0.001, "octaves": 1, "amplitude": 0.0, "ridged_amplitude": 0.0, "mountain_boost": 0.0}}})
		noise.seed = world_seed + 101
		noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		noise.fractal_type = FastNoiseLite.FRACTAL_FBM
		noise.fractal_octaves = 4
		noise.frequency = 0.012

	func h(x: float, z: float) -> float:
		return wd.macro_height(x, z) + noise.get_noise_2d(x, z) * AMP

	## The land's shape without the detail noise: what the planner plans streets and lots over. The
	## noise (2.5 m, 10-80 m across) is texture the composer smooths out of every street's profile
	## and grades out of every pad; on it, a 12 m step of a street or a lot's relief read as steep
	## ground at random, and towns came out half grown.
	func m(x: float, z: float) -> float:
		return wd.macro_height(x, z)


static func world_id_for(s: GenSettings) -> String:
	return world_id_for_version(s, VERSION)


## The id generator version `version` gave these settings' world.
static func world_id_for_version(s: GenSettings, version: int) -> String:
	return "rwg_%s" % ("%x" % (Ids.hash64("v%d|%s" % [version, s.key()]) & 0xffffffffffff)).lpad(12, "0")


## Which generator version made world `world_id` from these settings (the id hashes it); 0 when
## none up to this one did (a world id from somewhere else). Save v7 records it (TD-140).
static func version_of(world_id: String, s: GenSettings) -> int:
	for v: int in range(VERSION, 0, -1):
		if world_id_for_version(s, v) == world_id:
			return v
	return 0


## Runs the generator. Returns the generator (an RwgGenerator) with everything it made.
static func generate(s: GenSettings, p_progress: Callable = Callable()) -> RefCounted:
	var g: RefCounted = (load("res://src/worldgen/rwg/rwg_generator.gd") as GDScript).new()
	g.set(&"settings", s)
	g.set(&"progress", p_progress)
	g.call(&"run")
	return g


func rng(key: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.derive_seed(settings.seed, "rwg:" + key)
	return r


func _stage(name: String, t: float) -> void:
	var now: int = Time.get_ticks_msec()
	if _t0 > 0:
		timings[name] = now - _t0
	_t0 = now
	_t_sub = now
	if progress.is_valid():
		progress.call(name, t)


## Progress inside a stage: `stage` (the one under way) at fraction f of its span t0..t1, at most
## every 50 ms, so the loading bar keeps moving through the long stages (ADR-0038).
func _sub(stage: String, t0: float, t1: float, f: float) -> void:
	if not progress.is_valid():
		return
	var now: int = Time.get_ticks_msec()
	if now - _last_report < 50:
		return
	_last_report = now
	progress.call(stage, lerpf(t0, t1, clampf(f, 0.0, 1.0)))


## Records how long the step since the last mark took.
func _mark(step: String) -> void:
	var now: int = Time.get_ticks_msec()
	sub_timings[step] = now - _t_sub
	_t_sub = now


func run() -> void:
	tun = GenSettings.tuning()
	ptun = Planner.default_tuning()
	names = GenSettings.names()
	size = settings.integer("size")
	world_id = world_id_for(settings)
	var t_all: int = Time.get_ticks_msec()
	_t0 = t_all
	_t_sub = t_all
	if progress.is_valid():
		progress.call("Raising the land", 0.0)
	terrain.build(settings, tun, names, func(f: float) -> void: _sub("Raising the land", 0.0, 0.3, f))
	for k: String in terrain.timings:
		sub_timings["land/" + k] = terrain.timings[k]
	_stage("Raising the land", 0.3)
	_regions()
	_water_distance()
	_index_water()
	_mark("water_distance")
	_town_sites()
	_mark("town_sites")
	_stage("Choosing town sites", 0.34)
	router.setup(terrain, tun.get("roads", {}))
	_mark("router_setup")
	_road_network()
	_mark("road_network")
	_main_streets()
	_mark("main_streets")
	_stage("Building roads", 0.48)
	_plan_towns()
	_mark("town_plans")
	_settle_towns()
	_mark("town_settle")
	_stage("Laying out towns", 0.62)
	_drop_site()
	_mark("drop_site")
	_danger()
	_biome_map()
	_mark("biome_map")
	_stage("Planting forests", 0.7)
	_trader_posts()
	_mark("traders")
	_places()
	_clear_lots_off_roads()
	_mark("places")
	_stage("Placing camps and cabins", 0.85)
	_bridges()
	_mark("bridges")
	_bloom()
	_mark("bloom")
	_name_regions()
	_finalize_town_heights()
	_mark("town_heights")
	_caves()
	_mark("caves")
	_assign_authored()
	_mark("authored")
	_stage("Mapping", 1.0)
	timings["total"] = Time.get_ticks_msec() - t_all
	# Drop what only generation needed (the planner's closures hold the reference ground).
	_ref = null
	_mine_ref = null


# --- Regions ---------------------------------------------------------------------------------------

func _regions() -> void:
	for r: int in size:
		for c: int in size:
			var cell: String = "%s%d" % [char(65 + c), r + 1]
			var rect := Rect2(Vector2(-size * 512.0 + c * 1024.0, -size * 512.0 + r * 1024.0), Vector2(1024.0, 1024.0))
			regions[cell] = {"cell": cell, "id": "", "name": "", "biome": "conifer_forest", "danger": 1, "rect": rect}


func cell_at(p: Vector2) -> String:
	var c: int = int(floor((p.x + size * 512.0) / 1024.0))
	var r: int = int(floor((p.y + size * 512.0) / 1024.0))
	if c < 0 or r < 0 or c >= size or r >= size:
		return ""
	return "%s%d" % [char(65 + c), r + 1]


## True when the whole polygon, grown by `margin`, lies inside one region (local features fade out
## within 48 m of a region border; a pad there would not be graded).
func inside_one_region(poly: PackedVector2Array, margin: float) -> bool:
	var cell: String = cell_at(poly[0])
	if cell == "":
		return false
	var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(-margin)
	for p: Vector2 in poly:
		if not rect.has_point(p):
			return false
	return true


## Chamfer distance (m) from every macro cell to the nearest lake or river cell.
func _water_distance() -> void:
	var n: int = terrain.n
	water_dist.resize(n * n)
	for c: int in n * n:
		water_dist[c] = 0.0 if terrain.lake_of[c] >= 0 or terrain.river_of[c] >= 0 else 1.0e9
	var s: float = terrain.step
	var sd: float = s * 1.4142
	for j: int in n:
		for i: int in n:
			var k: int = j * n + i
			var v: float = water_dist[k]
			if i > 0:
				v = minf(v, water_dist[k - 1] + s)
			if j > 0:
				v = minf(v, water_dist[k - n] + s)
				if i > 0:
					v = minf(v, water_dist[k - n - 1] + sd)
				if i < n - 1:
					v = minf(v, water_dist[k - n + 1] + sd)
			water_dist[k] = v
	for j2: int in range(n - 1, -1, -1):
		for i2: int in range(n - 1, -1, -1):
			var k2: int = j2 * n + i2
			var v2: float = water_dist[k2]
			if i2 < n - 1:
				v2 = minf(v2, water_dist[k2 + 1] + s)
			if j2 < n - 1:
				v2 = minf(v2, water_dist[k2 + n] + s)
				if i2 < n - 1:
					v2 = minf(v2, water_dist[k2 + n + 1] + sd)
				if i2 > 0:
					v2 = minf(v2, water_dist[k2 + n - 1] + sd)
			water_dist[k2] = v2


func water_at(p: Vector2) -> float:
	return water_dist[terrain.cell(p.x, p.y)]


## River segments in a grid, so the exact water distance looks only at the stretches near a point.
func _index_water() -> void:
	for ri: int in terrain.rivers.size():
		var line: Polyline2 = terrain.rivers[ri]["line"]
		_river_widths.append(Array(terrain.rivers[ri]["widths"]))
		for k: int in line.points.size() - 1:
			_river_grid.insert(Grid.pack(ri, k), Rect2(line.points[k], Vector2.ZERO).expand(line.points[k + 1]).grow(1.0))


## Distance (m) from p to the nearest river's edge or lake shore, negative in the water, as
## Terrain.water_distance measures it, through the river index; 400 when no water is within 300 m.
func water_exact(p: Vector2) -> float:
	var best: float = 400.0
	var ids: PackedInt64Array = _river_grid.query(Rect2(p - Vector2(300.0, 300.0), Vector2(600.0, 600.0)))
	var k: int = 0
	while k < ids.size():
		var ri: int = ids[k] >> Grid.PART_BITS
		var segs := PackedInt32Array()
		while k < ids.size() and (ids[k] >> Grid.PART_BITS) == ri:
			segs.append(ids[k] & Grid.PART_MASK)
			k += 1
		var line: Polyline2 = terrain.rivers[ri]["line"]
		var q: Vector3 = line.closest_in(p, segs)
		best = minf(best, q.x - line.value_at(_river_widths[ri], q.y) * 0.5)
	for l: Dictionary in terrain.lakes:
		if (l["center"] as Vector2).distance_to(p) > float(l["radius"]) * 1.6 + 300.0:
			continue
		var poly: PackedVector2Array = l["polygon"]
		var d: float = Terrain._poly_distance(poly, p)
		best = minf(best, -d if Streets.point_in(p, poly) else d)
	return best


## The planner's water callable: exact near the water, a safe lower bound from the chamfer field
## far from it (the planner only compares water distances with a few metres).
func water_fn(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var coarse: float = water_at(p)
	if coarse > 160.0:
		return coarse * 0.9 - 40.0
	return water_exact(p)


## Exact clearance (m) from a polygon to the water: rivers' banks and lakes' shores (negative when
## it touches). Quick-rejects with the chamfer field.
func water_clearance(poly: PackedVector2Array) -> float:
	var best: float = INF
	for p: Vector2 in _dense(poly, 16.0):
		if water_at(p) > 220.0:
			continue
		best = minf(best, water_exact(p))
	return best


static func _dense(poly: PackedVector2Array, spacing: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for k: int in poly.size():
		var a: Vector2 = poly[k]
		var b: Vector2 = poly[(k + 1) % poly.size()]
		var steps: int = maxi(1, int(ceil(a.distance_to(b) / spacing)))
		for s: int in steps:
			out.append(a.lerp(b, float(s) / steps))
	var c := Vector2.ZERO
	for p: Vector2 in poly:
		c += p
	out.append(c / poly.size())
	return out


static func rect_poly(origin: Vector2, sz: Vector2, rot_deg: float) -> PackedVector2Array:
	var a: float = deg_to_rad(rot_deg)
	return PackedVector2Array([origin, origin + Vector2(sz.x, 0.0).rotated(a), origin + sz.rotated(a), origin + Vector2(0.0, sz.y).rotated(a)])


## The corners of a lot frame [cx, cz, w, d, yaw] (lot_xf convention: front, local +Z, along
## (sin yaw, cos yaw)): front-left, front-right, back-right, back-left.
static func frame_poly(f: Array) -> PackedVector2Array:
	var c := Vector2(float(f[0]), float(f[1]))
	var yaw: float = deg_to_rad(float(f[4]))
	var az := Vector2(sin(yaw), cos(yaw))
	var ax := Vector2(az.y, -az.x)
	var hx: Vector2 = ax * float(f[2]) * 0.5
	var hz: Vector2 = az * float(f[3]) * 0.5
	return PackedVector2Array([c - hx + hz, c + hx + hz, c + hx - hz, c - hx - hz])


# --- Town sites (plan §3.3) ----------------------------------------------------------------------

## Town sites by size class: the count from the town density (towns per 16 km²), the classes from
## the town-size mix (big first: they need the most room), each on the best of a few hundred
## candidates: dry, level in its core and its disc, low against a kilometre around it (valleys),
## water a walk away, away from the map's edge, and its disc 300 m clear of every other town's.
func _town_sites() -> void:
	var tcfg: Dictionary = tun.get("towns", {})
	var kinds_cfg: Dictionary = ptun.get("kinds", {})
	var density: float = settings.num("town_density")
	var r := rng("towns")
	var want: int = int(floor(density * size * size / 16.0 + r.randf()))
	if density > 0.0:
		want = maxi(want, 1)
	if not test_sites.is_empty():
		want = test_sites.size()
	if want <= 0 or kinds_cfg.is_empty():
		return
	var mix: Dictionary = (tcfg.get("mix", {}) as Dictionary).get(settings.choice("town_size"), {"village": 1.0})
	var kinds: Array[String] = []
	for k: int in want:
		kinds.append(_weighted(mix, r))
	kinds.sort_custom(func(a: String, b: String) -> bool: return KINDS.find(a) > KINDS.find(b))
	var pool: Array = (names.get("towns", []) as Array).duplicate()
	var spacing: float = float(tcfg.get("spacing", 300.0))
	var edge: float = float(tcfg.get("edge", 120.0))
	var tries: int = int(tcfg.get("candidates", 240))
	var core_max: float = float(tcfg.get("core_relief", 15.0))
	var disc_max: float = float(tcfg.get("disc_relief", 45.0))
	var wr: Array = tcfg.get("water", [60.0, 80.0, 300.0])
	var sc: Dictionary = tcfg.get("score", {})
	var smooth_k: float = float(tcfg.get("core_smoothing", 0.5))
	var half: float = size * 512.0
	if not test_sites.is_empty():
		kinds.clear()
		for ts: Variant in test_sites:
			kinds.append(str(ts["kind"]))
	# A while loop: a class with no room on this land retries one class smaller at the end.
	var ki: int = -1
	while ki + 1 < kinds.size():
		ki += 1
		var kind: String = kinds[ki]
		_sub("Choosing town sites", 0.3, 0.34, float(ki) / kinds.size())
		if not test_sites.is_empty():
			var tc: Vector2 = test_sites[ki]["center"]
			var tname: String = str(pool.pop_front()) if not pool.is_empty() else "Town %d" % (ki + 1)
			towns.append({"id": _slug(tname), "name": tname, "kind": kind, "fw_id": "%s_%s" % [world_id, _slug(tname)], "center": tc,
				"radius": float(test_sites[ki]["radius"]), "core": minf(float((kinds_cfg.get(kind, {}) as Dictionary).get("core", 80.0)), float(test_sites[ki]["radius"]) * 0.6),
				"cell": cell_at(tc), "tier": [1, 2], "plan": {}, "authored": PackedStringArray(), "bounds": Rect2(tc, Vector2.ZERO)})
			continue
		var kd: Dictionary = kinds_cfg.get(kind, {})
		var rr: Array = kd.get("radius", [200.0, 250.0])
		var radius: float = minf(r.randf_range(float(rr[0]), float(rr[1])), half - edge - 40.0)
		var core: float = minf(float(kd.get("core", 80.0)), radius * 0.6)
		var lim: float = half - radius - edge
		if lim <= 0.0 or radius < float(rr[0]) * 0.6:
			warnings.append("no room for a %s" % kind)
			continue
		var best: Dictionary = {}
		var best_score: float = INF
		# The disc's mean slope may not pass the class's limit; where nothing passes, the limit
		# relaxes to the least steep disc seen (plus a little) and the search runs again.
		var max_slope: float = float((tcfg.get("max_slope", {}) as Dictionary).get(kind, 0.09))
		var steep_best: float = INF
		for round_i: int in 2:
			if round_i == 1:
				if not best.is_empty() or steep_best == INF:
					break
				# Nothing level enough: once more, a little steeper than the least steep disc seen.
				max_slope = steep_best + 0.01
				steep_best = INF
			for attempt: int in tries:
				var c := Vector2(r.randf_range(-lim, lim), r.randf_range(-lim, lim))
				var jitter: float = r.randf()
				var clear: bool = true
				for other: Dictionary in towns:
					if (other["center"] as Vector2).distance_to(c) < radius + float(other["radius"]) + spacing:
						clear = false
						break
				if not clear:
					continue
				var wd: float = water_at(c)
				if wd < float(wr[0]) + 60.0:
					wd = water_exact(c)
				if wd < float(wr[0]):
					continue
				var core_st: Vector3 = _relief(c, core)
				if core_st.y - core_st.x > core_max:
					continue
				var disc_st: Vector3 = _relief(c, radius)
				if disc_st.y - disc_st.x > disc_max:
					continue
				# Mean slope over the core (9 samples) and over the disc (the core's and two rings): the
				# planner's streets climb at most 0.11, so a town on a valley side stays half grown.
				var slope: float = 0.0
				var disc_slope: float = 0.0
				for k2: int in 25:
					var q: Vector2 = c
					if k2 > 0:
						q += Vector2.from_angle(k2 * TAU / 8.0) * (core * 0.6 if k2 <= 8 else (radius * 0.55 if k2 <= 16 else radius * 0.9))
					var sl: float = terrain.slope(q.x, q.y)
					if k2 <= 8:
						slope += sl / 9.0
					disc_slope += sl / 25.0
				if disc_slope > max_slope:
					steep_best = minf(steep_best, disc_slope)
					continue
				var hood: float = 0.0
				for k3: int in 24:
					var q3: Vector2 = c + (Vector2.from_angle(k3 * TAU / 16.0) * 500.0 if k3 < 16 else Vector2.from_angle((k3 - 16) * TAU / 8.0) * 250.0)
					hood += terrain.height(q3.x, q3.y) / 24.0
				var rel: float = terrain.height(c.x, c.y) - hood
				var water_term: float = -float(sc.get("water", 6.0)) if wd >= float(wr[1]) and wd <= float(wr[2]) else 0.0
				var edge_d: float = half - maxf(absf(c.x), absf(c.y)) - radius
				var score: float = float(sc.get("slope", 120.0)) * slope + float(sc.get("disc_slope", 150.0)) * disc_slope + float(sc.get("valley", 0.25)) * rel + water_term \
					+ float(sc.get("central", 4.0)) * c.length() / half + float(sc.get("edge", 0.02)) * maxf(0.0, 300.0 - edge_d) + float(sc.get("jitter", 3.0)) * jitter
				if score < best_score:
					best_score = score
					best = {"center": c}
		if best.is_empty():
			warnings.append("no room for a %s" % kind)
			# Bigger towns (VERSION 12) need wider level land; rather than lose the town, try one
			# class smaller once the others are placed.
			if KINDS.find(kind) > 0 and test_sites.is_empty():
				kinds.append(KINDS[KINDS.find(kind) - 1])
			continue
		var ti: int = towns.size()
		var name: String = str(pool.pop_at(r.randi() % pool.size())) if not pool.is_empty() else "Town %d" % (ti + 1)
		var tid: String = _slug(name)
		var c2: Vector2 = best["center"]
		_smooth_core(c2, core, smooth_k)
		towns.append({"id": tid, "name": name, "kind": kind, "fw_id": "%s_%s" % [world_id, tid], "center": c2, "radius": snappedf(radius, 0.1),
			"core": core, "cell": cell_at(c2), "tier": [1, 2], "plan": {}, "authored": PackedStringArray(), "bounds": Rect2(c2, Vector2.ZERO)})


## (min, max, 0) of the ground at c and on two rings (half the radius and the radius).
func _relief(c: Vector2, radius: float) -> Vector3:
	var lo: float = terrain.height(c.x, c.y)
	var hi: float = lo
	for k: int in 16:
		var q: Vector2 = c + Vector2.from_angle(k * TAU / 8.0) * radius * (0.5 if k < 8 else 1.0)
		var v: float = terrain.height(q.x, q.y)
		lo = minf(lo, v)
		hi = maxf(hi, v)
	return Vector3(lo, hi, 0.0)


## Eases the macro grid within 0.8 of the core radius `k` of the way towards its mean there (plan
## §3.2: no flat town pad; a gentler core for the shops and the square). Water and its banks stay.
func _smooth_core(c: Vector2, core: float, k: float) -> void:
	if k <= 0.0:
		return
	var rad: float = core * 0.8
	var n: int = terrain.n
	var i0: int = clampi(int(floor((c.x - rad - terrain.x0) / terrain.step)), 0, n - 1)
	var i1: int = clampi(int(ceil((c.x + rad - terrain.x0) / terrain.step)), 0, n - 1)
	var j0: int = clampi(int(floor((c.y - rad - terrain.z0) / terrain.step)), 0, n - 1)
	var j1: int = clampi(int(ceil((c.y + rad - terrain.z0) / terrain.step)), 0, n - 1)
	var acc: float = 0.0
	var cnt: int = 0
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			if terrain.pos(j * n + i).distance_to(c) <= rad:
				acc += terrain.h[j * n + i]
				cnt += 1
	if cnt == 0:
		return
	var mean: float = acc / cnt
	for j2: int in range(j0, j1 + 1):
		for i2: int in range(i0, i1 + 1):
			var cell: int = j2 * n + i2
			var d: float = terrain.pos(cell).distance_to(c)
			if d > rad or water_dist[cell] < 64.0:
				continue
			terrain.h[cell] = lerpf(terrain.h[cell], mean, k * (1.0 - smoothstep(rad * 0.5, rad, d)))


static func _weighted(w: Dictionary, r: RandomNumberGenerator) -> String:
	var total: float = 0.0
	for k: Variant in w:
		total += float(w[k])
	var x: float = r.randf() * total
	var last: String = ""
	for k2: Variant in w:
		last = str(k2)
		x -= float(w[k2])
		if x < 0.0:
			return last
	return last


static func _slug(s: String) -> String:
	var out: String = ""
	for ch: String in s.to_lower():
		out += ch if ((ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9")) else "_"
	while out.contains("__"):
		out = out.replace("__", "_")
	return out.strip_edges().trim_suffix("_").trim_prefix("_")


# --- Roads (plan §3.4) -----------------------------------------------------------------------------

## The network through the town centres: a spanning tree between them (by distance) plus loops by
## road density, then exits off the map from the biggest towns. Towns are not obstacles: the main
## street of a town is the world road through its centre (_main_streets).
func _road_network() -> void:
	var rcfg: Dictionary = tun.get("roads", {})
	var r := rng("roads")
	var density: String = settings.choice("roads")
	var edges: Array = []
	for i: int in towns.size():
		for j: int in range(i + 1, towns.size()):
			edges.append([(towns[i]["center"] as Vector2).distance_to(towns[j]["center"]), i, j])
	edges.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]) or (float(a[0]) == float(b[0]) and int(a[1]) * 1000 + int(a[2]) < int(b[1]) * 1000 + int(b[2])))
	var parent: Array[int] = []
	for i2: int in towns.size():
		parent.append(i2)
	var chosen: Array = []
	var rest: Array = []
	for e: Array in edges:
		var ra: int = _find(parent, int(e[1]))
		var rb: int = _find(parent, int(e[2]))
		if ra != rb:
			parent[ra] = rb
			chosen.append(e)
		else:
			rest.append(e)
	var extra: int = int((rcfg.get("extra", {}) as Dictionary).get(density, 1)) * maxi(1, int(round(size * size / 16.0)))
	var longest: float = 0.0
	for e2: Array in chosen:
		longest = maxf(longest, float(e2[0]))
	for e3: Array in rest:
		if extra <= 0:
			break
		if float(e3[0]) < maxf(longest * 1.5, 1800.0):
			chosen.append(e3)
			extra -= 1
	for ci: int in chosen.size():
		var e4: Array = chosen[ci]
		_sub("Building roads", 0.34, 0.48, 0.7 * ci / chosen.size())
		var ta: Dictionary = towns[int(e4[1])]
		var tb: Dictionary = towns[int(e4[2])]
		var big: bool = str(ta["kind"]) != "hamlet" and str(tb["kind"]) != "hamlet"
		_connect(ta, tb, "highway" if big else "county", "%s to %s" % [ta["name"], tb["name"]])
	# Roads off the map: from the biggest towns' centres, the cheapest way to any edge.
	var exits: int = int((rcfg.get("exits", {}) as Dictionary).get(density, 1)) * maxi(1, int(round(size / 4.0)))
	var order: Array = []
	for i3: int in towns.size():
		order.append([KINDS.find(str(towns[i3]["kind"])), i3])
	order.sort_custom(func(a: Array, b: Array) -> bool: return int(a[0]) > int(b[0]) or (int(a[0]) == int(b[0]) and int(a[1]) < int(b[1])))
	for o: Array in order:
		if exits <= 0:
			break
		var tw: Dictionary = towns[int(o[1])]
		var from: Vector2 = tw["center"]
		var best_to := Vector2.INF
		var best_cost: float = INF
		for to: Vector2 in _edge_points(from):
			var pts: PackedVector2Array = router.route(from, to, 700.0, 0.9)
			if pts.is_empty():
				continue
			if router.last_cost < best_cost:
				best_cost = router.last_cost
				best_to = to
		if best_to == Vector2.INF:
			continue
		var pieces: Array[Dictionary] = router.route_pieces(from, best_to, 700.0, 0.9)
		var added: bool = false
		for pc: Dictionary in pieces:
			var mid: PackedVector2Array = pc["points"]
			if not bool(pc["start_exact"]):
				mid[0] = _snap_to_road(mid[0])
			if not bool(pc["end_exact"]):
				mid[mid.size() - 1] = _snap_to_road(mid[mid.size() - 1])
			mid = _leave_roads(mid, bool(pc["start_exact"]), bool(pc["end_exact"]))
			if not _along_roads(mid):
				added = _add_road(mid, "highway", "%s road" % tw["name"], bool(pc["end_exact"])) or added
		if added:
			exits -= 1
	if towns.is_empty():
		# No towns: one county road across the map still gives the land a way through.
		var a := Vector2(-size * 512.0, r.randf_range(-size * 300.0, size * 300.0))
		var b := Vector2(size * 512.0, r.randf_range(-size * 300.0, size * 300.0))
		_add_road(router.route(a + Vector2(16, 0), b - Vector2(16, 0), 900.0), "county", "Old county road", true)


static func _find(parent: Array[int], i: int) -> int:
	while parent[i] != i:
		parent[i] = parent[parent[i]]
		i = parent[i]
	return i


## The nearest point of each map edge to p (8 m inside it).
func _edge_points(p: Vector2) -> Array[Vector2]:
	var e: float = size * 512.0 - 8.0
	return [Vector2(-e, p.y), Vector2(e, p.y), Vector2(p.x, -e), Vector2(p.x, e)]


## A road between two town centres, joining roads already built at T-junctions where it meets them.
func _connect(ta: Dictionary, tb: Dictionary, cls: String, name: String) -> void:
	var pieces: Array[Dictionary] = router.route_pieces(ta["center"], tb["center"], 900.0, 0.9 if cls == "highway" else 0.7)
	if pieces.is_empty():
		warnings.append("no road from %s to %s" % [ta["name"], tb["name"]])
		return
	for pc: Dictionary in pieces:
		var mid: PackedVector2Array = pc["points"]
		if not bool(pc["start_exact"]):
			mid[0] = _snap_to_road(mid[0])
		if not bool(pc["end_exact"]):
			mid[mid.size() - 1] = _snap_to_road(mid[mid.size() - 1])
		mid = _leave_roads(mid, bool(pc["start_exact"]), bool(pc["end_exact"]))
		if not _along_roads(mid):
			_add_road(mid, cls, name, false)


## The nearest point on a road already built (a junction), or p itself when none is near.
func _snap_to_road(p: Vector2) -> Vector2:
	var nr: Array = nearest_road(p)
	return nr[1] if float(nr[0]) < terrain.step * 1.5 else p


## A route piece snapped onto a road at either end starts (or ends) where it leaves that road,
## not after running beside it on the road's cheap cells (_leave_road; TD-139).
func _leave_roads(pts: PackedVector2Array, start_exact: bool, end_exact: bool) -> PackedVector2Array:
	if not start_exact:
		var nr: Array = nearest_road(pts[0])
		if float(nr[0]) < 1.0:
			pts = _leave_road(pts, int(nr[2]))
	if not end_exact and pts.size() >= 2:
		var nr2: Array = nearest_road(pts[pts.size() - 1])
		if float(nr2[0]) < 1.0:
			pts.reverse()
			pts = _leave_road(pts, int(nr2[2]))
			pts.reverse()
	return pts


## True when a route piece only runs along roads already built (within 6 m all the way). Routes
## start and end at town centres, where roads already meet, so route_pieces hands back stretches of
## a road the route steps onto, and connectors between two roads that share cells: a second road on
## top of the first that grades the ground with its own profile.
func _along_roads(pts: PackedVector2Array) -> bool:
	for k: int in pts.size() - 1:
		var n: int = maxi(1, int(ceil(pts[k].distance_to(pts[k + 1]) / 8.0)))
		for s: int in n + (1 if k == pts.size() - 2 else 0):
			if float(nearest_road(pts[k].lerp(pts[k + 1], float(s) / n))[0]) > 6.0:
				return false
	return true


func _add_road(pts: PackedVector2Array, cls: String, name: String, off_map: bool) -> bool:
	if pts.size() < 2:
		return false
	var spec: Dictionary = (tun.get("roads", {}) as Dictionary).get(cls, {"surface": "gravel", "width": 5.0, "shoulder": 1.5})
	if off_map:
		var last: Vector2 = pts[pts.size() - 1]
		if absf(last.x) > size * 512.0 - 20.0 or absf(last.y) > size * 512.0 - 20.0:
			var out: Vector2 = (last - pts[pts.size() - 2]).normalized()
			pts.append(last + out * 60.0)
	router.mark(pts, roads.size())
	roads.append({"id": "road_%d" % roads.size(), "name": name, "class": cls, "points": pts, "width": float(spec["width"]),
		"shoulder": float(spec["shoulder"]), "surface": str(spec["surface"]), "markings": cls == "highway", "bridges": [],
		"line": Polyline2.from_array(Terrain._arr(pts))})
	_index_road(roads.size() - 1)
	return true


## Adds a road's segments and vertices to the spatial indexes.
func _index_road(i: int) -> void:
	var rd: Dictionary = roads[i]
	var line: Polyline2 = rd["line"]
	_max_half = maxf(_max_half, float(rd["width"]) * 0.5 + float(rd["shoulder"]))
	for k: int in line.points.size():
		_pt_grid.insert(Grid.pack(i, k), Rect2(line.points[k], Vector2.ZERO).grow(1.0))
		if k + 1 < line.points.size():
			_seg_grid.insert(Grid.pack(i, k), Rect2(line.points[k], Vector2.ZERO).expand(line.points[k + 1]).grow(1.0))


## Rebuilds the road indexes and ids after roads were merged (_main_streets).
func _reindex_roads() -> void:
	_seg_grid = Grid.new(256.0)
	_pt_grid = Grid.new(256.0)
	_max_half = 0.0
	for i: int in roads.size():
		roads[i]["id"] = "road_%d" % i
		roads[i]["line"] = Polyline2.from_array(Terrain._arr(roads[i]["points"]))
		_index_road(i)


# --- Main streets (plan §3.2 step 3) ---------------------------------------------------------------

## Every town's main street is a world road through its centre: the two roads that end there and
## meet straightest become one road through it; a lone road carries on through the centre as a
## stub out past the town along the lowest ground; a town no road reached gets a county road
## through it along its valley; and a town (the biggest class) whose network gives it one road
## through its core gets a county road across it.
func _main_streets() -> void:
	var tcfg: Dictionary = tun.get("towns", {})
	var stub_len: float = float(tcfg.get("stub", 150.0))
	for ti: int in towns.size():
		var tw: Dictionary = towns[ti]
		_sub("Building roads", 0.34, 0.48, 0.7 + 0.3 * ti / towns.size())
		var c: Vector2 = tw["center"]
		var ground := Streets.Ground.new({"height": _ground_fn(), "water": water_fn}, c, float(tw["radius"]) + stub_len + 240.0)
		var reach: float = float(tw["radius"]) + stub_len
		var ends: Array = _ends_at(c)
		var best: Array = []
		var best_dot: float = INF
		for a: int in ends.size():
			for b: int in range(a + 1, ends.size()):
				var dd: float = (ends[a][2] as Vector2).dot(ends[b][2])
				if dd < best_dot:
					best_dot = dd
					best = [ends[a], ends[b]]
		# Two roads leaving the same way would make a hairpin through the centre: the first carries on
		# as a stub instead (the other meets it there).
		if not best.is_empty() and best_dot < -0.3:
			_merge_through(best[0], best[1])
		elif not ends.is_empty():
			var e: Array = ends[0]
			var away := Vector2.ZERO
			for e2: Array in ends:
				away += e2[2]
			var stub: PackedVector2Array = _stub(ground, c, -(away.normalized() if away.length() > 0.01 else (e[2] as Vector2)), reach, 70.0)
			if stub.size() >= 2:
				_extend_through(e, stub)
		elif _roads_near(c, float(tw["radius"]) * 0.3) == 0:
			var axis: PackedVector2Array = _through_road(ground, c, reach, Vector2.ZERO)
			if axis.size() >= 2:
				_add_road(axis, "county", "%s road" % tw["name"], false)
		if str(tw["kind"]) == "town" and _roads_near(c, float(tw["core"]) * 0.5) < 2:
			var cross: PackedVector2Array = _through_road(ground, c, reach, _cross_axis(c), CROSS_SPREAD)
			if cross.size() >= 2:
				_add_road(cross, "county", "%s cross road" % tw["name"], false)
		_leave_through(c)
	_reindex_roads()


## A road still ending at a town centre beside the road through it (both came in from the same
## side, so they were not merged) runs 6-20 m beside it into the centre: a fork with a sliver of
## ground between (TD-139). It ends where it leaves the through road instead (_leave_road), and a
## piece that never leaves it goes. With no road through the centre the first ending there leads.
func _leave_through(c: Vector2) -> void:
	var ends: Array = _ends_at(c)
	if ends.is_empty():
		return
	var through: int = -1
	var best: float = 1.0
	for ri: int in roads.size():
		if ends.any(func(e: Array) -> bool: return int(e[0]) == ri):
			continue
		var d: float = (roads[ri]["line"] as Polyline2).closest(c).x
		if d < best:
			best = d
			through = ri
	if through < 0:
		if ends.size() < 2:
			return
		through = int(ends[0][0])
		ends = ends.slice(1)
	var gone: Array[int] = []
	for e: Array in ends:
		var ri2: int = int(e[0])
		var pts: PackedVector2Array = (roads[ri2]["points"] as PackedVector2Array).duplicate()
		if not bool(e[1]):
			pts.reverse()
		var left: PackedVector2Array = _leave_road(pts, through)
		var beside: bool = _within(pts, roads[through]["line"], LEAVE_ROAD)
		if not beside and left.size() == pts.size() and left[1] == pts[1]:
			continue
		if not bool(e[1]):
			left.reverse()
		var old_line: Polyline2 = roads[ri2]["line"]
		if beside:
			gone.append(ri2)
		else:
			roads[ri2]["points"] = left
			roads[ri2]["line"] = Polyline2.from_array(Terrain._arr(left))
		# A road that met the trimmed stretch meets the through road (or what is left) instead.
		var keep: Polyline2 = null if beside else roads[ri2]["line"]
		var main: Polyline2 = roads[through]["line"]
		for rj: int in roads.size():
			if rj == ri2 or rj == through or gone.has(rj):
				continue
			var pj: PackedVector2Array = roads[rj]["points"]
			for k: int in [0, pj.size() - 1]:
				if old_line.closest(pj[k]).x > 1.5 or (keep != null and keep.closest(pj[k]).x < 1.5):
					continue
				var qa: Vector3 = main.closest(pj[k])
				var qb: Vector3 = keep.closest(pj[k]) if keep != null else Vector3(INF, 0, 0)
				pj[k] = main.point_at(qa.y) if qa.x <= qb.x else keep.point_at(qb.y)
			roads[rj]["points"] = pj
			roads[rj]["line"] = Polyline2.from_array(Terrain._arr(pj))
	gone.sort()
	for k2: int in range(gone.size() - 1, -1, -1):
		roads.remove_at(gone[k2])
	if not gone.is_empty():
		_reindex_roads()


## True when every point along pts (every 4 m) lies within `reach` of `line`.
static func _within(pts: PackedVector2Array, line: Polyline2, reach: float) -> bool:
	for k: int in pts.size() - 1:
		var n: int = maxi(1, int(ceil(pts[k].distance_to(pts[k + 1]) / 4.0)))
		for st: int in n + 1:
			if line.closest(pts[k].lerp(pts[k + 1], float(st) / n)).x > reach:
				return false
	return true


## The land the towns are planned over: the composer's macro ground (RefGround.m; built on demand,
## the planner and the stubs share it). Lot heights come from the full reference ground
## (_finalize_town_heights).
func _ground_fn() -> Callable:
	if _ref == null:
		_ref = RefGround.new(terrain, settings.seed & 0x7fffffff, size)
	return _ref.m


## Roads with an end at c: [[road index, at its start, direction out of c along it]].
func _ends_at(c: Vector2) -> Array:
	var out: Array = []
	for ri: int in roads.size():
		var pts: PackedVector2Array = roads[ri]["points"]
		var line: Polyline2 = roads[ri]["line"]
		if pts[0].distance_to(c) < 1.0:
			out.append([ri, true, (line.point_at(minf(40.0, line.total_length)) - c).normalized()])
		elif pts[pts.size() - 1].distance_to(c) < 1.0:
			out.append([ri, false, (line.point_at(maxf(0.0, line.total_length - 40.0)) - c).normalized()])
	return out


## How many roads pass within r of p.
func _roads_near(p: Vector2, r: float) -> int:
	var n: int = 0
	for rd: Dictionary in roads:
		if (rd["line"] as Polyline2).closest(p).x < r:
			n += 1
	return n


## The axis for a town's cross road: of 16 headings, the one whose two ends keep farthest from
## every road leaving c (each leg's direction 40 m out). A perpendicular to the main street's
## tangent ran back along one leg where the street bends at the centre (TD-139).
func _cross_axis(c: Vector2) -> Vector2:
	var legs: Array[Vector2] = []
	for rd: Dictionary in roads:
		var line: Polyline2 = rd["line"]
		var q: Vector3 = line.closest(c)
		if q.x > 30.0:
			continue
		for s: float in [q.y - 40.0, q.y + 40.0]:
			if s > 0.0 and s < line.total_length:
				legs.append((line.point_at(s) - c).normalized())
	var best := Vector2.RIGHT
	var best_gap: float = -INF
	for k: int in 16:
		var u: Vector2 = Vector2.from_angle(k * PI / 16.0)
		var gap: float = INF
		for leg: Vector2 in legs:
			gap = minf(gap, minf(absf(u.angle_to(leg)), absf((-u).angle_to(leg))))
		if gap > best_gap + 0.001:
			best_gap = gap
			best = u
	return best


## Joins two roads that end at a town centre into one road through it (the first keeps its place
## and takes the higher class; the second goes).
func _merge_through(ea: Array, eb: Array) -> void:
	var a: int = int(ea[0])
	var b: int = int(eb[0])
	var pa: PackedVector2Array = (roads[a]["points"] as PackedVector2Array).duplicate()
	if bool(ea[1]):
		pa.reverse()
	var pb: PackedVector2Array = (roads[b]["points"] as PackedVector2Array).duplicate()
	if not bool(eb[1]):
		pb.reverse()
	pa.append_array(pb.slice(1))
	var cls: String = str(roads[a]["class"])
	if str(roads[b]["class"]) == "highway" and cls != "highway":
		_set_class(a, "highway")
	roads[a]["points"] = pa
	roads[a]["line"] = Polyline2.from_array(Terrain._arr(pa))
	roads.remove_at(b)


## Carries a road that ends at a town centre on through it with `stub` (which starts there).
func _extend_through(e: Array, stub: PackedVector2Array) -> void:
	var a: int = int(e[0])
	var pa: PackedVector2Array = (roads[a]["points"] as PackedVector2Array).duplicate()
	if bool(e[1]):
		pa.reverse()
	pa.append_array(stub.slice(1))
	roads[a]["points"] = pa
	roads[a]["line"] = Polyline2.from_array(Terrain._arr(pa))


func _set_class(i: int, cls: String) -> void:
	var spec: Dictionary = (tun.get("roads", {}) as Dictionary).get(cls, {"surface": "gravel", "width": 5.0, "shoulder": 1.5})
	roads[i]["class"] = cls
	roads[i]["width"] = float(spec["width"])
	roads[i]["shoulder"] = float(spec["shoulder"])
	roads[i]["surface"] = str(spec["surface"])
	roads[i]["markings"] = cls == "highway"


## A road from c out `length` m, within `spread` degrees of `dir`, along whichever heading keeps
## gentle, low and dry, routed on the town's 8 m ground (RwgStreets.route_fine). Of the four best
## headings the route that winds least wins (a route forced up a slope zigzags). Empty when none goes.
func _stub(g: Streets.Ground, c: Vector2, dir: Vector2, length: float, spread: float) -> PackedVector2Array:
	var half: float = size * 512.0 - 40.0
	var cands: Array = []
	var h0: float = g.h(c)
	for k: int in 9:
		var turn: float = deg_to_rad((k - 4) * spread / 4.0)
		var u: Vector2 = dir.normalized().rotated(turn)
		var score: float = absf(turn) * 2.0
		var prev: float = h0
		var steepest: float = 0.0
		for f: int in range(1, 9):
			var q: Vector2 = c + u * length * f / 8.0
			var hq: float = g.h(q)
			steepest = maxf(steepest, absf(hq - prev) / (length / 8.0))
			score += maxf(0.0, hq - h0) * 0.02
			prev = hq
			if g.water(q) < 15.0:
				score += 400.0
			if absf(q.x) > half or absf(q.y) > half:
				score += 800.0
		cands.append([score + steepest * 60.0, u])
	cands.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var best := PackedVector2Array()
	var best_wind: float = INF
	for ci: int in mini(4, cands.size()):
		var u2: Vector2 = cands[ci][1]
		var to: Vector2 = c + u2 * length
		to = Vector2(clampf(to.x, -half, half), clampf(to.y, -half, half))
		var pts: PackedVector2Array = _despike(Streets.route_fine(g, c, to, {"grade_ok": 0.06, "grade_max": 0.13, "water": 14.0, "margin": 100.0, "tol": 10.0}))
		if pts.size() < 2:
			continue
		var run: float = 0.0
		for k2: int in pts.size() - 1:
			run += pts[k2].distance_to(pts[k2 + 1])
		var wind: float = run / maxf(1.0, c.distance_to(to))
		if wind < best_wind:
			best_wind = wind
			best = pts
		if wind < 1.15:
			break
	return best


## Drops the points where a route doubles back on itself (turns by more than 120 degrees): a grid
## search's hook round a cell or two, simplified, is a spike a few metres long in the road.
static func _despike(pts: PackedVector2Array) -> PackedVector2Array:
	var i: int = 1
	while i < pts.size() - 1:
		if (pts[i] - pts[i - 1]).normalized().dot((pts[i + 1] - pts[i]).normalized()) < -0.5:
			pts.remove_at(i)
			i = maxi(1, i - 1)
		else:
			i += 1
	return pts


## A road through c both ways: out along `axis` (or the town's lowest axis when ZERO) and back
## out the other side, as one line through c.
func _through_road(g: Streets.Ground, c: Vector2, length: float, axis: Vector2, spread: float = 50.0) -> PackedVector2Array:
	var dir: Vector2 = axis
	if dir == Vector2.ZERO:
		var best: float = INF
		for k: int in 8:
			var u: Vector2 = Vector2.from_angle(k * PI / 8.0)
			var s: float = 0.0
			for f: float in [-1.0, -0.5, 0.5, 1.0]:
				var q: Vector2 = c + u * length * f
				s += g.h(q) + (400.0 if g.water(q) < 15.0 else 0.0)
			if s < best:
				best = s
				dir = u
	var a: PackedVector2Array = _stub(g, c, dir, length, spread)
	var b: PackedVector2Array = _stub(g, c, -dir, length, spread)
	if a.size() < 2 or b.size() < 2:
		return a if a.size() >= 2 else b
	a.reverse()
	a.append_array(b.slice(1))
	return a


# --- Town plans (plan §3.2 step 4) -----------------------------------------------------------------

## Plans every town (RwgTownPlanner) on the reference ground the composer will grade, with the
## world roads near it as its arterials, the towns spread over a few threads (the planner is pure,
## and the ground, the water and the roads are only read while it runs).
func _plan_towns() -> void:
	if towns.is_empty():
		return
	var height: Callable = _ground_fn()
	var outskirts: float = float((ptun.get("lots", {}) as Dictionary).get("outskirts", 400.0))
	var jobs: Array = []
	for tw: Dictionary in towns:
		var site: Dictionary = {"id": tw["id"], "kind": tw["kind"], "center": tw["center"], "radius": tw["radius"], "name": tw["name"]}
		jobs.append([site, _arterials_for(tw["center"], float(tw["radius"]) + outskirts + 60.0), Ids.derive_seed(settings.seed, "rwg:town:%s" % tw["id"])])
	var world: Dictionary = {"height": height, "water": water_fn}
	var count: int = mini(clampi(OS.get_processor_count() - 1, 1, 4), jobs.size())
	var results: Array = []
	var threads: Array[Thread] = []
	for k: int in range(1, count):
		var th := Thread.new()
		if th.start(_plan_batch.bind(jobs, k, count, world)) == OK:
			threads.append(th)
		else:
			results.append_array(_plan_batch(jobs, k, count, world))
	results.append_array(_plan_batch(jobs, 0, count, world, true))
	for th2: Thread in threads:
		results.append_array(th2.wait_to_finish())
	for res: Array in results:
		towns[int(res[0])]["plan"] = res[1]


## Plans jobs k, k + stride, ... ([index, plan] each). `report`: this is the generator's own thread.
func _plan_batch(jobs: Array, k: int, stride: int, world: Dictionary, report: bool = false) -> Array:
	var out: Array = []
	for i: int in range(k, jobs.size(), stride):
		var job: Array = jobs[i]
		out.append([i, Planner.plan(job[0], world, job[1], ptun, int(job[2]))])
		if report:
			_sub("Laying out towns", 0.48, 0.62, float(i + 1) / jobs.size())
	return out


## The world roads within `reach` of c as the planner's arterials, nearest first (the main street).
func _arterials_for(c: Vector2, reach: float) -> Array:
	var near: Array = []
	for ri: int in roads.size():
		var d: float = (roads[ri]["line"] as Polyline2).closest(c).x
		if d < reach:
			near.append([d, ri])
	near.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]) or (float(a[0]) == float(b[0]) and int(a[1]) < int(b[1])))
	var out: Array = []
	for nr: Array in near:
		var rd: Dictionary = roads[int(nr[1])]
		out.append({"id": rd["id"], "points": Terrain._arr(rd["points"]), "width": rd["width"], "shoulder": rd["shoulder"],
			"surface": rd["surface"], "markings": rd["markings"]})
	return out


## Towns against each other and the map: a lot must stand inside the map, clear of every other
## town's streets and of the lots of the towns planned before it (the outskirts of two towns can
## meet along a road between them); a fixture must not stand in another town's lot. Then the lots,
## the square and the streets go into the indexes places, the drop site and the Bloom keep off,
## and the router keeps tracks out of the lots.
func _settle_towns() -> void:
	var half: float = size * 512.0 - 12.0
	var inside := Rect2(-half, -half, half * 2.0, half * 2.0)
	var ccfg: Dictionary = (tun.get("towns", {}) as Dictionary).get("clearance", {})
	var lot_gap: float = float(ccfg.get("lots", 12.0))
	var street_gap: float = float(ccfg.get("streets", 8.0))
	# Every town's streets first: a lot is tested against all of them.
	for ti: int in towns.size():
		for rd: Variant in (towns[ti]["plan"] as Dictionary).get("roads", []):
			var line: Polyline2 = Polyline2.from_array((rd as Dictionary)["points"])
			var si: int = _streets.size()
			var need: float = float(rd["width"]) * 0.5 + float(rd.get("shoulder", 0.5))
			_streets.append({"line": line, "need": need, "town": ti})
			for k: int in line.points.size() - 1:
				_street_grid.insert(Grid.pack(si, k), Rect2(line.points[k], Vector2.ZERO).expand(line.points[k + 1]).grow(need + street_gap + 1.0))
	for ti2: int in towns.size():
		var tw: Dictionary = towns[ti2]
		var plan: Dictionary = tw["plan"]
		var kept: Array = []
		for lv: Variant in plan.get("lots", []):
			var l: Dictionary = lv
			var poly: PackedVector2Array = frame_poly(l["frame"])
			var ok: bool = true
			for p: Vector2 in poly:
				if not inside.has_point(p):
					ok = false
			if ok and (_frame_hits_lots(poly, ti2, 1.0) or _frame_hits_streets(poly, ti2)):
				ok = false
			if ok:
				kept.append(l)
				_add_lot(poly, ti2, lot_gap)
		if kept.size() < (plan.get("lots", []) as Array).size():
			warnings.append("%s: %d lots left out (the map edge or a neighbour)" % [tw["name"], (plan["lots"] as Array).size() - kept.size()])
		plan["lots"] = kept
		if not (plan.get("plaza", {}) as Dictionary).is_empty():
			_add_lot(frame_poly(plan["plaza"]["frame"]), ti2, lot_gap)
	for ti3: int in towns.size():
		var plan2: Dictionary = towns[ti3]["plan"]
		var fx_kept: Array = []
		for fv: Variant in plan2.get("fixtures", []):
			var p2 := Vector2(float(fv["pos"][0]), float(fv["pos"][1]))
			var in_lot: bool = absf(p2.x) > half or absf(p2.y) > half
			for id: int in _lot_grid.query(Rect2(p2, Vector2.ZERO).grow(1.0)):
				if _lot_town[id] != ti3 and Streets.point_in(p2, _lot_polys[id]):
					in_lot = true
					break
			if not in_lot:
				fx_kept.append(fv)
		plan2["fixtures"] = fx_kept
		towns[ti3]["bounds"] = _town_bounds(plan2)
	# Tracks and trails keep out of the lots: the router's 32 m cells near a frame are closed (a route
	# runs between cell centres, so the frames grow by about half a cell).
	for poly2: PackedVector2Array in _lot_polys:
		router.block_polygon(poly2, 18.0)
	_roads_at_plan = roads.size()


func _add_lot(poly: PackedVector2Array, town: int, gap: float) -> void:
	var id: int = _lot_polys.size()
	_lot_polys.append(poly)
	_lot_town.append(town)
	var g: Array = Geometry2D.offset_polygon(poly, gap)
	_lot_grown.append(g[0] if not g.is_empty() else poly)
	_lot_grid.insert(id, _bounds(poly).grow(gap + 1.0))


## A frame within `gap` of another town's lot already kept.
func _frame_hits_lots(poly: PackedVector2Array, town: int, gap: float) -> bool:
	var bb: Rect2 = _bounds(poly).grow(gap)
	var grown := PackedVector2Array()
	for id: int in _lot_grid.query(bb):
		if _lot_town[id] == town or not _bounds(_lot_polys[id]).intersects(bb):
			continue
		if grown.is_empty():
			var off: Array = Geometry2D.offset_polygon(poly, gap)
			grown = off[0] if not off.is_empty() else poly
		if not Geometry2D.intersect_polygons(grown, _lot_polys[id]).is_empty():
			return true
	return false


## A frame reaching into another town's street corridor (half width + shoulder + 0.4 m).
func _frame_hits_streets(poly: PackedVector2Array, town: int) -> bool:
	for sid: int in _street_grid.query(_bounds(poly).grow(1.0)):
		var st: Dictionary = _streets[sid >> Grid.PART_BITS]
		if int(st["town"]) == town:
			continue
		var line: Polyline2 = st["line"]
		var k: int = sid & Grid.PART_MASK
		if _seg_poly_distance(line.points[k], line.points[k + 1], poly) < float(st["need"]) + 0.4:
			return true
	return false


## Distance between segment a-b and a polygon (0 when they touch or overlap).
static func _seg_poly_distance(a: Vector2, b: Vector2, poly: PackedVector2Array) -> float:
	if Streets.point_in(a, poly) or Streets.point_in(b, poly):
		return 0.0
	var best: float = INF
	for k: int in poly.size():
		var c: Vector2 = poly[k]
		var d: Vector2 = poly[(k + 1) % poly.size()]
		if Geometry2D.segment_intersects_segment(a, b, c, d) != null:
			return 0.0
		var pts: PackedVector2Array = Geometry2D.get_closest_points_between_segments(a, b, c, d)
		best = minf(best, pts[0].distance_to(pts[1]))
	return best


## A town's bounds: its lots' parcels and frames, its streets (with their width), its square and
## its fixtures, grown 4 m (what the composer looks for near each region, ADR-0040).
func _town_bounds(plan: Dictionary) -> Rect2:
	var c: Array = plan.get("center", [0.0, 0.0])
	var bb := Rect2(Vector2(float(c[0]), float(c[1])), Vector2.ZERO)
	for lv: Variant in plan.get("lots", []):
		for p: Vector2 in frame_poly(lv["frame"]):
			bb = bb.expand(p)
		for q: Variant in lv.get("poly", []):
			bb = bb.expand(Vector2(float(q[0]), float(q[1])))
	for rd: Variant in plan.get("roads", []):
		var line: Polyline2 = Polyline2.from_array(rd["points"])
		bb = bb.merge(line.bounds.grow(float(rd["width"]) * 0.5 + float(rd.get("shoulder", 0.5))))
	if not (plan.get("plaza", {}) as Dictionary).is_empty():
		for p2: Vector2 in frame_poly(plan["plaza"]["frame"]):
			bb = bb.expand(p2)
	for fv: Variant in plan.get("fixtures", []):
		bb = bb.expand(Vector2(float(fv["pos"][0]), float(fv["pos"][1])))
	return bb.grow(4.0)


## A road added after the towns were planned (a track or a drive to a place) that still comes into a
## lot's frame takes the lot away (the outskirts' farms, out along the roads): a frame is graded
## level to its edges, which would cut the road.
func _clear_lots_off_roads() -> void:
	if _roads_at_plan >= roads.size() or towns.is_empty():
		return
	for tw: Dictionary in towns:
		var plan: Dictionary = tw["plan"]
		var kept: Array = []
		for lv: Variant in plan.get("lots", []):
			var poly: PackedVector2Array = frame_poly(lv["frame"])
			var bb: Rect2 = _bounds(poly)
			var hit: bool = false
			for ri: int in range(_roads_at_plan, roads.size()):
				var rd: Dictionary = roads[ri]
				var line: Polyline2 = rd["line"]
				var need: float = float(rd["width"]) * 0.5 + float(rd["shoulder"]) + 0.4
				if not line.bounds.grow(need + 1.0).intersects(bb):
					continue
				for k: int in line.points.size() - 1:
					if _seg_poly_distance(line.points[k], line.points[k + 1], poly) < need:
						hit = true
						break
				if hit:
					break
			if not hit:
				kept.append(lv)
		if kept.size() < (plan.get("lots", []) as Array).size():
			warnings.append("%s: %d lots gave way to a track" % [tw["name"], (plan["lots"] as Array).size() - kept.size()])
			plan["lots"] = kept


## True when p lies within `gap` of a town's lots or square.
func _near_lots(p: Vector2, gap: float) -> bool:
	for id: int in _lot_grid.query(Rect2(p, Vector2.ZERO).grow(gap + 1.0)):
		var poly: PackedVector2Array = _lot_polys[id]
		if Streets.point_in(p, poly) or Terrain._poly_distance(poly, p) < gap:
			return true
	return false


## Distance from p to the nearest town's disc (0 inside one; INF without towns).
func _town_distance(p: Vector2) -> float:
	var best: float = INF
	for tw: Dictionary in towns:
		best = minf(best, maxf(0.0, (tw["center"] as Vector2).distance_to(p) - float(tw["radius"])))
	return best


## nearest_road and road_clearance as v1 had them (see ADR-0038's spatial indexes).
## The nearest point on any road to p: [distance, point, road index, arc]. `clear_of_towns`: only
## points at least 30 m outside every town (a track must not start on a town's street).
## Searched through the spatial indexes in growing squares around p until the nearest found lies
## inside the square (no road outside can then be nearer). The scan over every road takes the
## nearest, the lowest road index first among equals, whenever one lies within 4000 m, and so does
## this; farther (or with no road near), the scan runs as it always has.
func nearest_road(p: Vector2, classes: PackedStringArray = [], clear_of_towns: bool = false) -> Array:
	for r: float in [256.0, 1024.0, 4097.0]:
		var square := Rect2(p - Vector2(r, r), Vector2(r, r) * 2.0)
		var best: Array = _nearest_vertex_in(p, classes, square) if clear_of_towns else _nearest_segment_in(p, classes, square)
		if int(best[2]) >= 0 and float(best[0]) < r - 1.0:
			if clear_of_towns or float(best[0]) <= 4000.0:
				return best
			break
	return _nearest_road_scan(p, classes, clear_of_towns)


## nearest_road among the road segments indexed in `square`, roads in ascending order and each
## through closest() over its listed segments.
func _nearest_segment_in(p: Vector2, classes: PackedStringArray, square: Rect2) -> Array:
	var best: Array = [INF, p, -1, 0.0]
	var ids: PackedInt64Array = _seg_grid.query(square)
	var k: int = 0
	while k < ids.size():
		var i: int = ids[k] >> Grid.PART_BITS
		var segs := PackedInt32Array()
		while k < ids.size() and (ids[k] >> Grid.PART_BITS) == i:
			segs.append(ids[k] & Grid.PART_MASK)
			k += 1
		if not classes.is_empty() and not classes.has(str(roads[i]["class"])):
			continue
		var line: Polyline2 = roads[i]["line"]
		var q: Vector3 = line.closest_in(p, segs)
		if q.x < float(best[0]):
			best = [q.x, line.point_at(q.y), i, q.y]
	return best


## nearest_road(clear_of_towns) among the road vertices indexed in `square`, in (road, vertex)
## order as the scan visits them.
func _nearest_vertex_in(p: Vector2, classes: PackedStringArray, square: Rect2) -> Array:
	var best: Array = [INF, p, -1, 0.0]
	for id: int in _pt_grid.query(square):
		var i: int = id >> Grid.PART_BITS
		if not classes.is_empty() and not classes.has(str(roads[i]["class"])):
			continue
		var line: Polyline2 = roads[i]["line"]
		var k: int = id & Grid.PART_MASK
		var q2: Vector2 = line.points[k]
		var d: float = q2.distance_to(p)
		if d >= float(best[0]) or _near_town(q2, 30.0):
			continue
		best = [d, q2, i, line.lengths[k]]
	return best


## nearest_road as a scan over every road (what the index stands in for).
func _nearest_road_scan(p: Vector2, classes: PackedStringArray, clear_of_towns: bool) -> Array:
	var best: Array = [INF, p, -1, 0.0]
	for i: int in roads.size():
		if not classes.is_empty() and not classes.has(str(roads[i]["class"])):
			continue
		var line: Polyline2 = roads[i]["line"]
		if not clear_of_towns:
			if line.bounds.grow(minf(float(best[0]), 4000.0)).has_point(p) or float(best[0]) == INF:
				var q: Vector3 = line.closest(p)
				if q.x < float(best[0]):
					best = [q.x, line.point_at(q.y), i, q.y]
			continue
		for k: int in line.points.size():
			var q2: Vector2 = line.points[k]
			var d: float = q2.distance_to(p)
			if d >= float(best[0]) or _near_town(q2, 30.0):
				continue
			best = [d, q2, i, line.lengths[k]]
	return best


## Within `gap` of a town: inside its disc grown by `gap`, or that near one of its lots (the farms
## out along its roads).
func _near_town(p: Vector2, gap: float) -> bool:
	for tw: Dictionary in towns:
		if (tw["center"] as Vector2).distance_to(p) < float(tw["radius"]) + gap:
			return true
	return _near_lots(p, gap)


## Clearance (m) between a polygon and every road's edge (shoulder included). Only road vertices
## within the widest road's reach + 60 m of the polygon's box can count: those come from the
## vertex index, and each road's own reach is tested exactly as the scan over every road did.
func road_clearance(poly: PackedVector2Array, skip: int = -1) -> float:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	var best: float = INF
	var cur: int = -1
	var half: float = 0.0
	var near: bool = false
	var box := Rect2()
	var line: Polyline2 = null
	for id: int in _pt_grid.query(bb.grow(_max_half + 61.0)):
		var i: int = id >> Grid.PART_BITS
		if i != cur:
			cur = i
			var rd: Dictionary = roads[i]
			line = rd["line"]
			half = float(rd["width"]) * 0.5 + float(rd["shoulder"])
			near = i != skip and line.bounds.grow(half + 60.0).intersects(bb.grow(60.0))
			box = bb.grow(half + 60.0)
		if not near:
			continue
		var q: Vector2 = line.points[id & Grid.PART_MASK]
		if not box.has_point(q):
			continue
		var d: float = 0.0 if Streets.point_in(q, poly) else Terrain._poly_distance(poly, q)
		best = minf(best, d - half)
	return best


# --- Drop site -------------------------------------------------------------------------------------

## Where a new player lands: away from towns and places, near (not on) a road, on gentle dry ground,
## about a day's walk from a town, and at least 300 m from a region border (a streamed world
## composes the land round the drop site first). Fallbacks, in tiers: 200 m from a border; then
## 120 m, the towns 0.8 as far and the road up to 1.8 as far; then 60 m, 0.65 and 2.3 (a small
## map's few roads mostly run through its towns, which are wide).
func _drop_site() -> void:
	var dcfg: Dictionary = tun.get("drop_site", {})
	var r := rng("drop")
	var town_d: float = float(dcfg.get("town_distance", 380.0))
	var rd: Array = dcfg.get("road_distance", [40, 220])
	var margins: Array = dcfg.get("border", [300.0, 200.0, 120.0, 60.0])
	var best: Dictionary = {}
	for mi: int in margins.size():
		var margin: float = float(margins[mi])
		var town_k: float = [1.0, 1.0, 0.8, 0.65][mini(mi, 3)]
		var road_k: float = [1.0, 1.4, 1.8, 2.3][mini(mi, 3)]
		var best_score: float = INF
		for attempt: int in 600:
			var p := Vector2(r.randf_range(-size * 512.0 + 90.0, size * 512.0 - 90.0), r.randf_range(-size * 512.0 + 90.0, size * 512.0 - 90.0))
			var jitter: float = r.randf()
			if not inside_one_region(PackedVector2Array([p - Vector2(24, 24), p + Vector2(24, 24)]), margin):
				continue
			if water_at(p) < 70.0 or terrain.slope(p.x, p.y) > 0.12:
				continue
			var near_town: float = _town_distance(p)
			if near_town < town_d * town_k or _near_lots(p, 120.0):
				continue
			var nr: Array = nearest_road(p)
			var road_d: float = float(nr[0])
			if not roads.is_empty() and (road_d < float(rd[0]) or road_d > float(rd[1]) * road_k):
				continue
			if water_exact(p) < 50.0:
				continue
			# Close enough to walk to a town on the first day, central rather than at the edge.
			var score: float = (absf(near_town - 750.0) / 100.0 if near_town < INF else 0.0) + p.length() / (size * 512.0) * 4.0 + terrain.slope(p.x, p.y) * 30.0 + jitter * 2.0
			if score < best_score:
				best_score = score
				best = {"pos": p, "road": nr}
		if not best.is_empty():
			if mi > 0:
				warnings.append("drop site %d m from a region border" % int(margin))
			break
	if best.is_empty():
		# Fallback: the flattest dry spot near the middle.
		var p2 := Vector2.ZERO
		for k: int in 400:
			var q := Vector2(r.randf_range(-size * 300.0, size * 300.0), r.randf_range(-size * 300.0, size * 300.0))
			if water_at(q) > 70.0 and terrain.slope(q.x, q.y) < 0.15 and not _near_lots(q, 60.0) and _town_distance(q) > (60.0 if k < 300 else 0.0) \
					and inside_one_region(PackedVector2Array([q - Vector2(24, 24), q + Vector2(24, 24)]), 60.0):
				p2 = q
				break
		best = {"pos": p2, "road": nearest_road(p2)}
		warnings.append("drop site placed by fallback")
	var pos: Vector2 = best["pos"]
	var target: Vector2 = (best["road"] as Array)[1] if int((best["road"] as Array)[2]) >= 0 else pos + Vector2(40, 0)
	var v: Vector2 = (target - pos).normalized()
	drop = {"pos": pos, "yaw": snappedf(rad_to_deg(atan2(-v.x, -v.y)), 1.0), "cell": cell_at(pos)}
	if int((best["road"] as Array)[2]) >= 0:
		var trail: PackedVector2Array = router.route(pos, target, 300.0)
		if trail.size() >= 2:
			paths.append({"id": "drop_trail", "points": trail, "width": 2.2, "surface": "dirt"})


## Region danger (1-5) by distance from the drop site; a town's tier range by its centre's danger.
func _danger() -> void:
	var p: Vector2 = drop.get("pos", Vector2.ZERO)
	var far: float = 0.0
	for cell: String in regions:
		far = maxf(far, ((regions[cell]["rect"] as Rect2).get_center()).distance_to(p))
	for cell2: String in regions:
		var d: float = ((regions[cell2]["rect"] as Rect2).get_center()).distance_to(p)
		regions[cell2]["danger"] = clampi(1 + int(round(d / maxf(1.0, far) * 4.0)), 1, 5)
	regions[drop.get("cell", "A1")]["danger"] = 1
	for tw: Dictionary in towns:
		var dg: int = int(regions[tw["cell"]]["danger"])
		tw["tier"] = [1, 2] if dg <= 2 else [1, 3]


# --- Biomes ------------------------------------------------------------------------------------------

func _biome_map() -> void:
	biome_step = float(tun.get("biome_step", 64.0))
	biome_cols = int(round(size * 1024.0 / biome_step))
	biome_cells.resize(biome_cols * biome_cols)
	var nb: int = BIOMES.size()
	var w: Array[float] = [settings.num("conifer"), settings.num("birch"), settings.num("meadow"), settings.num("rocky")]
	if w[0] + w[1] + w[2] + w[3] <= 0.0:
		w[0] = 1.0
	var noises: Array[FastNoiseLite] = []
	for k: int in 4:
		var nz := FastNoiseLite.new()
		nz.seed = Ids.derive_seed(settings.seed, "rwg:biome%d" % k) & 0x7fffffff
		nz.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		nz.fractal_type = FastNoiseLite.FRACTAL_FBM
		nz.fractal_octaves = 3
		nz.frequency = 1.0 / 650.0
		noises.append(nz)
	# Fens (ADR-0041): the flattest, lowest, wettest ground, in patches.
	var fcfg: Dictionary = tun.get("fen", {})
	var fen_w: float = settings.num("fen")
	var fen_low: Array = fcfg.get("low", [0.12, 0.4])
	var fen_slope: float = float(fcfg.get("max_slope", 0.075))
	var fen_water: float = float(fcfg.get("water", 420.0))
	var fen_valley: float = float(fcfg.get("valley", 8.0))
	var fen_clear: float = float(fcfg.get("town_clear", 80.0))
	var fen_drop: float = float(fcfg.get("drop_clear", 220.0))
	var fen_noise := FastNoiseLite.new()
	fen_noise.seed = Ids.derive_seed(settings.seed, "rwg:fen") & 0x7fffffff
	fen_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	fen_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	fen_noise.fractal_octaves = 3
	fen_noise.frequency = 1.0 / float(fcfg.get("patch", 380.0))
	var drop_p: Vector2 = drop.get("pos", Vector2(1.0e9, 1.0e9))
	var hmin: float = INF
	var hmax: float = -INF
	for v: float in terrain.h:
		hmin = minf(hmin, v)
		hmax = maxf(hmax, v)
	var raw := PackedByteArray()
	raw.resize(biome_cols * biome_cols)
	for j: int in biome_cols:
		_sub("Planting forests", 0.62, 0.7, 0.7 * j / biome_cols)
		for i: int in biome_cols:
			var p := Vector2(-size * 512.0 + (i + 0.5) * biome_step, -size * 512.0 + (j + 0.5) * biome_step)
			var hp: float = terrain.height(p.x, p.y)
			var e: float = (hp - hmin) / maxf(1.0, hmax - hmin)
			var s: float = terrain.slope(p.x, p.y)
			var wd: float = water_at(p)
			var wet: float = 1.0 - smoothstep(0.0, 260.0, wd)
			# town_ring: a town's disc and its fringe (no fen there). Only the core is cleared to meadow
			# (the square, the shops); round it second-growth birch, and past the lots the world's own
			# forest, so the trees come up to the yards (player report 4: a town read as a cleared
			# patch in the forest when its whole disc and 90 m round it turned meadow).
			var town_ring: float = 0.0
			var town_core: float = 0.0
			var town_edge: float = 0.0
			for tw: Dictionary in towns:
				var d: float = (tw["center"] as Vector2).distance_to(p)
				var tr: float = float(tw["radius"])
				var core: float = float(tw.get("core", tr * 0.4))
				town_ring = maxf(town_ring, 1.0 - smoothstep(tr * 0.7, tr + 90.0, d))
				town_core = maxf(town_core, 1.0 - smoothstep(core * 0.5, core * 1.1, d))
				town_edge = maxf(town_edge, (1.0 - smoothstep(tr * 0.8, tr + 40.0, d)) * smoothstep(core * 0.6, core * 1.2, d))
			var nc: float = noises[0].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nbr: float = noises[1].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nm: float = noises[2].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var nr: float = noises[3].get_noise_2d(p.x, p.y) * 0.5 + 0.5
			var sc: Array[float] = [
				w[0] * (0.55 + 0.6 * nc),
				w[1] * (0.3 + 0.85 * nbr) * (0.8 + 0.6 * wet) + town_edge * (0.35 + w[1]) * nbr,
				w[2] * (0.25 + 0.95 * nm) * (1.25 - 0.9 * smoothstep(0.05, 0.22, s)) * (1.0 - 0.6 * e) + town_core * (0.6 + w[2]),
				# Bare rock on the heights and the steepest ground only: the composer already turns
				# slopes past ~35 degrees to rock, and highlands should keep their forested sides.
				w[3] * (smoothstep(0.62, 0.97, e) * 1.5 + smoothstep(0.32, 0.65, s) * 0.8 + 0.1 * nr),
			]
			var bi: int = 0
			for k2: int in range(1, 4):
				if sc[k2] > sc[bi]:
					bi = k2
			# A fen takes the lowest, flattest ground near water, whatever grew there, and keeps off
			# towns and the drop site: level, low (on the map and against the ground 400 m round)
			# and damp, broken into patches by its own noise.
			if fen_w > 0.0 and s < fen_slope and wd < fen_water and town_ring <= 0.0 and drop_p.distance_to(p) > fen_drop \
					and _town_distance(p) > fen_clear:
				var around: float = 0.0
				for q: int in 6:
					var o := Vector2(cos(q * TAU / 6.0), sin(q * TAU / 6.0)) * 400.0
					around += terrain.height(p.x + o.x, p.y + o.y)
				var valley: float = smoothstep(0.0, fen_valley, around / 6.0 - hp)
				var low: float = 1.0 - smoothstep(float(fen_low[0]), float(fen_low[1]) + 0.12 * fen_w, e)
				var flat: float = 1.0 - smoothstep(fen_slope * 0.4, fen_slope, s)
				var damp: float = 1.0 - smoothstep(fen_water * 0.3, fen_water, wd)
				var nf: float = fen_noise.get_noise_2d(p.x, p.y) * 0.5 + 0.5
				var f: float = maxf(low, valley * 0.85) * flat * damp * (0.35 + 1.1 * nf) * (0.55 + 1.1 * fen_w)
				if f > 0.5:
					bi = 5
			raw[j * biome_cols + i] = bi
	# One majority pass: no lone cells.
	for j2: int in biome_cols:
		for i2: int in biome_cols:
			var counts: Array[int] = []
			counts.resize(nb)
			counts.fill(0)
			for dj: int in range(-1, 2):
				for di: int in range(-1, 2):
					var ii: int = clampi(i2 + di, 0, biome_cols - 1)
					var jj: int = clampi(j2 + dj, 0, biome_cols - 1)
					counts[raw[jj * biome_cols + ii]] += 1
			var own: int = raw[j2 * biome_cols + i2]
			var top: int = own
			for k3: int in nb:
				if counts[k3] > counts[top]:
					top = k3
			biome_cells[j2 * biome_cols + i2] = top if counts[own] <= 2 else own
	# Fire scars after the majority pass: their ragged edges and unburnt islands are the point.
	if settings.num("burn") > 0.0:
		_fire_scars()
	_sub("Planting forests", 0.62, 0.7, 0.95)
	# Each region's dominant biome (its default and summary), counted over the cells whose centres
	# lie in it: only cells near it are tested (one of slack each way), not the whole map's.
	for cell: String in regions:
		var rect: Rect2 = regions[cell]["rect"]
		var counts2: Array[int] = []
		counts2.resize(nb)
		counts2.fill(0)
		var i0: int = clampi(floori((rect.position.x + size * 512.0) / biome_step) - 1, 0, biome_cols - 1)
		var i1: int = clampi(ceili((rect.end.x + size * 512.0) / biome_step) + 1, 0, biome_cols - 1)
		var j0: int = clampi(floori((rect.position.y + size * 512.0) / biome_step) - 1, 0, biome_cols - 1)
		var j1: int = clampi(ceili((rect.end.y + size * 512.0) / biome_step) + 1, 0, biome_cols - 1)
		for j3: int in range(j0, j1 + 1):
			for i3: int in range(i0, i1 + 1):
				var p2 := Vector2(-size * 512.0 + (i3 + 0.5) * biome_step, -size * 512.0 + (j3 + 0.5) * biome_step)
				if rect.has_point(p2):
					counts2[biome_cells[j3 * biome_cols + i3]] += 1
		var top2: int = 0
		for k4: int in nb:
			if counts2[k4] > counts2[top2]:
				top2 = k4
		regions[cell]["biome"] = BIOMES[top2]


## Fire scars (ADR-0041): fires lit in the forest burn outwards over the 64 m biome grid (a cheapest-
## first spread: downwind and uphill run fastest, meadow and rock slow it, noise makes the fingers)
## until each reaches its size, a few hundred metres to a couple of kilometres across. Rivers, lakes,
## roads, fens, towns and the drop site stop it, as firebreaks do; it crosses ridges. Burnt forest
## replaces the forest and the rock it took, meadows stay meadow (grass grows back), and islands the
## fire skipped stay green.
func _fire_scars() -> void:
	var bcfg: Dictionary = tun.get("burn", {})
	var r := rng("burn")
	var n: int = biome_cols
	var want: int = int(floor(settings.num("burn") * size * size / 16.0 * float(bcfg.get("per_16km2", 3.0)) + r.randf()))
	if want <= 0:
		return
	var sizes: Array = bcfg.get("cells", [45, 650])
	# On a small map a big fire would be most of it: no scar past `max_share` of the map, and the
	# burns together past twice that.
	var cap: int = int(float(bcfg.get("max_share", 0.09)) * n * n)
	var total: int = 0
	var water_gap: float = float(bcfg.get("water", 48.0))
	var road_gap: float = float(bcfg.get("road", 48.0))
	var town_clear: float = float(bcfg.get("town_clear", 120.0))
	var drop_clear: float = float(bcfg.get("drop_clear", 260.0))
	var islands: float = float(bcfg.get("islands", 0.72))
	var drop_p: Vector2 = drop.get("pos", Vector2(1.0e9, 1.0e9))
	# Firebreaks per cell (computed once, lazily: most of the map is never reached).
	var brk := PackedByteArray()
	brk.resize(n * n)
	brk.fill(255)
	var nz := FastNoiseLite.new()
	nz.seed = Ids.derive_seed(settings.seed, "rwg:burn") & 0x7fffffff
	nz.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	nz.fractal_octaves = 2
	nz.frequency = 1.0 / 190.0
	var burnt := PackedByteArray()
	burnt.resize(n * n)
	for s_i: int in want:
		# Ignition: a forest cell far from the start, on dry ground.
		var start: int = -1
		for attempt: int in 60:
			var k0: int = r.randi_range(0, n * n - 1)
			var b0: int = biome_cells[k0]
			if b0 != 0 and b0 != 1:
				continue
			if burnt[k0] != 0 or _firebreak(k0, brk, water_gap, road_gap, town_clear, drop_clear, drop_p):
				continue
			start = k0
			break
		if start < 0:
			continue
		var target: int = mini(int(lerpf(float(sizes[0]), float(sizes[1]), pow(r.randf(), 1.7))), cap)
		if total + target > cap * 2:
			break
		var wind := Vector2.from_angle(r.randf() * TAU)
		var cost := PackedFloat32Array()
		cost.resize(n * n)
		cost.fill(INF)
		# The frontier holds each cell once (its cost is lowered in place), so a pop scans only the
		# fire's edge.
		var front := PackedInt32Array([start])
		var in_front := PackedByteArray()
		in_front.resize(n * n)
		in_front[start] = 1
		cost[start] = 0.0
		var done := PackedByteArray()
		done.resize(n * n)
		var count: int = 0
		while not front.is_empty() and count < target:
			var bi_f: int = 0
			for q: int in range(1, front.size()):
				if cost[front[q]] < cost[front[bi_f]]:
					bi_f = q
			var k: int = front[bi_f]
			front.remove_at(bi_f)
			in_front[k] = 0
			done[k] = 1
			count += 1
			total += 1
			burnt[k] = 1
			var ci: int = k % n
			var cj: int = k / n
			var pc := Vector2(-size * 512.0 + (ci + 0.5) * biome_step, -size * 512.0 + (cj + 0.5) * biome_step)
			var hc: float = terrain.height(pc.x, pc.y)
			for dj: int in range(-1, 2):
				for di: int in range(-1, 2):
					if di == 0 and dj == 0:
						continue
					var ni: int = ci + di
					var nj: int = cj + dj
					if ni < 0 or nj < 0 or ni >= n or nj >= n:
						continue
					var kn: int = nj * n + ni
					if done[kn] != 0 or _firebreak(kn, brk, water_gap, road_gap, town_clear, drop_clear, drop_p):
						continue
					var pn := Vector2(-size * 512.0 + (ni + 0.5) * biome_step, -size * 512.0 + (nj + 0.5) * biome_step)
					var dir := Vector2(di, dj).normalized()
					var step_len: float = Vector2(di, dj).length()
					var fuel: float = 1.0
					match biome_cells[kn]:
						2:
							fuel = 2.6
						3:
							fuel = 1.8
					var up: float = clampf((terrain.height(pn.x, pn.y) - hc) / (biome_step * 0.25), -1.0, 1.0)
					var c: float = step_len * fuel * (0.45 + 1.3 * (nz.get_noise_2d(pn.x, pn.y) * 0.5 + 0.5)) \
						* (1.0 - 0.4 * dir.dot(wind)) * (1.0 - 0.3 * up)
					if cost[k] + c < cost[kn]:
						cost[kn] = cost[k] + c
						if in_front[kn] == 0:
							in_front[kn] = 1
							front.append(kn)
	for k2: int in n * n:
		if burnt[k2] == 0:
			continue
		var b: int = biome_cells[k2]
		if b != 0 and b != 1 and b != 3:
			continue
		var pi := Vector2(-size * 512.0 + (k2 % n + 0.5) * biome_step, -size * 512.0 + (k2 / n + 0.5) * biome_step)
		# Islands the fire skipped (wet hollows, a change of wind) stay green.
		if nz.get_noise_2d(pi.x * 2.3 + 917.0, pi.y * 2.3 - 411.0) * 0.5 + 0.5 > islands:
			continue
		biome_cells[k2] = 4


## True where fire stops: water, a road, a fen, a town or the drop site's surroundings (memoised per
## cell in `brk`, 255 = not yet known).
func _firebreak(k: int, brk: PackedByteArray, water_gap: float, road_gap: float, town_clear: float, drop_clear: float,
		drop_p: Vector2) -> bool:
	if brk[k] != 255:
		return brk[k] == 1
	var p := Vector2(-size * 512.0 + (k % biome_cols + 0.5) * biome_step, -size * 512.0 + (k / biome_cols + 0.5) * biome_step)
	var stop: bool = biome_cells[k] == 5 or water_at(p) < water_gap or drop_p.distance_to(p) < drop_clear \
		or _town_distance(p) < town_clear or float(nearest_road(p)[0]) < road_gap
	brk[k] = 1 if stop else 0
	return stop


func biome_at(p: Vector2) -> String:
	var i: int = clampi(int(floor((p.x + size * 512.0) / biome_step)), 0, biome_cols - 1)
	var j: int = clampi(int(floor((p.y + size * 512.0) / biome_step)), 0, biome_cols - 1)
	return BIOMES[biome_cells[j * biome_cols + i]]


## The splat layers a region of this world needs (ADR-0041), or [] for the composer's default eight.
## A region with burnt forest or fen gets ash_char / peat in place of the default layers it can best
## spare: sand (lake coves fall back to mud and gravel), then asphalt where no paved road, drive or
## town comes near, else moss (forest moss patches fall back to the floor). Slots keep their order so
## the other layers keep their splat channels.
func region_palette(cell: String) -> PackedStringArray:
	var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(biome_step * 2.0)
	var has := {}
	var i0: int = clampi(floori((rect.position.x + size * 512.0) / biome_step), 0, biome_cols - 1)
	var i1: int = clampi(floori((rect.end.x + size * 512.0) / biome_step), 0, biome_cols - 1)
	var j0: int = clampi(floori((rect.position.y + size * 512.0) / biome_step), 0, biome_cols - 1)
	var j1: int = clampi(floori((rect.end.y + size * 512.0) / biome_step), 0, biome_cols - 1)
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			has[biome_cells[j * biome_cols + i]] = true
	var extra: PackedStringArray = []
	if has.has(4):
		extra.append("ash_char")
	if has.has(5):
		extra.append("peat")
	if extra.is_empty():
		return PackedStringArray()
	var pal: PackedStringArray = TerrainComposer.DEFAULT_PALETTE.duplicate()
	var spare: PackedStringArray = ["sand"]
	spare.append("moss_ground" if _paved_near(rect) else "asphalt_cracked")
	for k: int in extra.size():
		pal[pal.find(spare[k])] = extra[k]
	return pal


## True if a paved road (highway, drive), a town or a trader post comes into `rect`.
func _paved_near(rect: Rect2) -> bool:
	for rd: Dictionary in roads:
		if str(rd.get("surface", "")) == "asphalt" and (rd["line"] as Polyline2).bounds.grow(12.0).intersects(rect):
			return true
	for tw: Dictionary in towns:
		if (tw.get("bounds", Rect2()) as Rect2).grow(40.0).intersects(rect):
			return true
	for pt: Dictionary in posts:
		if _bounds(pt["poly"]).grow(20.0).intersects(rect):
			return true
	return false


## The fen's pools in a region (ADR-0041): small irregular local lakes (region `lake` features),
## brim-full (`drop`: the water stands that far under the ground round it), about a metre deep, so
## the player wades rather than swims. Placed per fen cell from a stream of the map seed and the
## cell, inside the fen and the region (local features fade out near borders), on level ground and
## clear of rivers and lakes, roads and paths, town lots and streets, places, trader posts and the
## drop site, and of each other.
func fen_pools(cell: String) -> Array:
	var out: Array = []
	var pcfg: Dictionary = (tun.get("fen", {}) as Dictionary).get("pools", {})
	var chance: float = float(pcfg.get("chance", 0.55))
	var per: Array = pcfg.get("per_cell", [1, 3])
	var radius: Array = pcfg.get("radius", [5.0, 15.0])
	var inner: Rect2 = (regions[cell]["rect"] as Rect2).grow(-float(pcfg.get("border", 72.0)))
	var drop_p: Vector2 = drop.get("pos", Vector2(1.0e9, 1.0e9))
	var i0: int = clampi(floori((inner.position.x + size * 512.0) / biome_step), 0, biome_cols - 1)
	var i1: int = clampi(floori((inner.end.x + size * 512.0) / biome_step), 0, biome_cols - 1)
	var j0: int = clampi(floori((inner.position.y + size * 512.0) / biome_step), 0, biome_cols - 1)
	var j1: int = clampi(floori((inner.end.y + size * 512.0) / biome_step), 0, biome_cols - 1)
	var placed: Array[Vector3] = []
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			if biome_cells[j * biome_cols + i] != 5:
				continue
			var r := RandomNumberGenerator.new()
			r.seed = Ids.derive_seed(settings.seed, "rwg:fen_pool:%d_%d" % [i, j])
			if r.randf() > chance:
				continue
			var c := Vector2(-size * 512.0 + (i + 0.5) * biome_step, -size * 512.0 + (j + 0.5) * biome_step)
			for q: int in r.randi_range(int(per[0]), int(per[1])):
				var pc: Vector2 = c + Vector2(r.randf_range(-0.4, 0.4), r.randf_range(-0.4, 0.4)) * biome_step
				var rx: float = r.randf_range(float(radius[0]), float(radius[1]))
				var rz: float = rx * r.randf_range(0.5, 0.95)
				var rot: float = r.randf_range(0.0, 180.0)
				if not inner.grow(-rx).has_point(pc) or terrain.slope(pc.x, pc.y) > float(pcfg.get("max_slope", 0.05)):
					continue
				# Inside the fen all round, not on its edge.
				var inside: bool = true
				for o: Vector2 in [Vector2(rx + 10.0, 0.0), Vector2(-rx - 10.0, 0.0), Vector2(0.0, rx + 10.0), Vector2(0.0, -rx - 10.0)]:
					if biome_at(pc + o) != "fen":
						inside = false
				if not inside:
					continue
				var clear: bool = drop_p.distance_to(pc) > rx + 60.0 and water_exact(pc) > rx + 14.0
				for pq: Vector3 in placed:
					if Vector2(pq.x, pq.y).distance_to(pc) < pq.z + rx + 6.0:
						clear = false
				if not clear:
					continue
				var poly: PackedVector2Array = rect_poly(pc - Vector2(rx, rz), Vector2(rx, rz) * 2.0, 0.0)
				if road_clearance(poly) < 10.0 or _hits_built(poly, 8.0) or _near_path(pc, rx + 8.0):
					continue
				placed.append(Vector3(pc.x, pc.y, rx))
				out.append({"type": "lake", "id": "fen_%s_%d" % [cell.to_lower(), out.size()],
					"ellipse": [snappedf(pc.x, 0.1), snappedf(pc.y, 0.1), snappedf(rx, 0.1), snappedf(rz, 0.1), snappedf(rot, 1.0)],
					"irregularity": float(pcfg.get("irregularity", 0.3)), "level": "auto", "drop": float(pcfg.get("drop", 0.28)),
					"probe": snappedf(maxf(1.0, rz * 0.12), 0.1), "depth": float(pcfg.get("depth", 0.65)), "shore": float(pcfg.get("shore", 4.0))})
	return out


## True if a footpath passes within `gap` of p.
func _near_path(p: Vector2, gap: float) -> bool:
	for pt: Dictionary in paths:
		var pts: PackedVector2Array = pt["points"]
		for k: int in pts.size() - 1:
			if p.distance_to(Geometry2D.get_closest_point_to_segment(p, pts[k], pts[k + 1])) < gap:
				return true
	return false


# --- Places --------------------------------------------------------------------------------------

## The authored wilderness places by site, each pool entry's count from its density per region and
## capped at `max` per 16 km² of map (so a 16 x 16 world holds sixteen times a 4 x 4's).
func _places() -> void:
	var wcfg: Dictionary = tun.get("wilderness", {})
	var density: float = settings.num("wilderness")
	var r := rng("places")
	var db: Node = ContentDB.instance
	var max_danger: int = 1
	for cell: String in regions:
		max_danger = maxi(max_danger, int(regions[cell]["danger"]))
	var area16: float = size * size / 16.0
	var order: Array[String] = ["roadside", "lake_shore", "summit", "waterside", "remote", "forest"]
	var pool: Array = wcfg.get("pool", [])
	for oi: int in order.size():
		var site: String = order[oi]
		_sub("Placing camps and cabins", 0.7, 0.85, float(oi) / order.size())
		for e: Variant in pool:
			var pe: Dictionary = e
			if str(pe.get("site", "")) != site or int(pe.get("min_danger", 1)) > max_danger or bool(pe.get("late", false)):
				continue
			var pd: PoiDef = db.call(&"get_def", &"poi", StringName(str(pe.get("poi", "")))) as PoiDef if db != null else null
			if pd == null:
				continue
			for k: int in _pool_count(pe, r, density, area16):
				_place_one(pe, Vector2(pd.footprint), r, wcfg)
	var farm: Dictionary = wcfg.get("farmsteads", {})
	var fw: FrameworkDef = db.call(&"get_def", &"framework", StringName(str(farm.get("framework", "")))) as FrameworkDef if db != null and not farm.is_empty() else null
	if fw != null and int(farm.get("min_danger", 1)) <= max_danger:
		var fcap: int = maxi(1, int(ceil(float(farm.get("max", 1)) * area16 - 0.001)))
		var fcount: int = mini(fcap, int(floor(float(farm.get("per_region", 0.1)) * size * size * density + r.randf())))
		for k2: int in fcount:
			var fe: Dictionary = farm.duplicate()
			fe["site"] = "farm"
			fe["access"] = "track"
			_place_one(fe, Vector2(fw.size), r, wcfg)
	# Places added after a world format shipped (`late`: the forest set pieces, generator v9), each
	# from its own stream after the farmsteads: every place before them draws exactly as it did.
	for e3: Variant in pool:
		var le: Dictionary = e3
		if not bool(le.get("late", false)) or str(le.get("site", "")) == "mine" or int(le.get("min_danger", 1)) > max_danger:
			continue
		var lpd: PoiDef = db.call(&"get_def", &"poi", StringName(str(le.get("poi", "")))) as PoiDef if db != null else null
		if lpd == null:
			continue
		var rl := rng("places:late:%s" % lpd.id)
		for k4: int in _pool_count(le, rl, density, area16):
			_place_one(le, Vector2(lpd.footprint), rl, wcfg)
	# Mines last, each from its own stream: no other place's pad reshapes the hill over their levels
	# after the cover is checked, and the places before them draw exactly as they did (generator v5).
	for e2: Variant in pool:
		var me: Dictionary = e2
		if str(me.get("site", "")) != "mine" or int(me.get("min_danger", 1)) > max_danger:
			continue
		var mpd: PoiDef = db.call(&"get_def", &"poi", StringName(str(me.get("poi", "")))) as PoiDef if db != null else null
		if mpd == null:
			continue
		var rm := rng("places:mine:%s" % mpd.id)
		var mcount: int = _pool_count(me, rm, density, area16)
		# The ground as the composer will read it, every other place's levelling done.
		if mcount > 0 and _mine_ref == null:
			_mine_ref = RefGround.new(terrain, settings.seed & 0x7fffffff, size)
		for k3: int in mcount:
			if not _place_one(me, Vector2(mpd.footprint), rm, wcfg):
				warnings.append("no hillside for %s" % mpd.id)
	# The companion's camp (ADR-0058) after everything, from its own stream: in a ring round the drop
	# site (the pool entry's `ring`, m), off the roads, nothing leading to it.
	for e3: Variant in pool:
		var ce: Dictionary = e3
		if str(ce.get("site", "")) != "companion" or int(ce.get("min_danger", 1)) > max_danger:
			continue
		var cpd: PoiDef = db.call(&"get_def", &"poi", StringName(str(ce.get("poi", "")))) as PoiDef if db != null else null
		if cpd == null:
			continue
		var rc := rng("places:companion:%s" % cpd.id)
		for k4: int in _pool_count(ce, rc, density, area16):
			if not _place_one(ce, Vector2(cpd.footprint), rc, wcfg):
				warnings.append("no spot for %s" % cpd.id)
	# The lift's crash site (VERSION 13) last of all, from its own stream.
	for e5: Variant in pool:
		var xe: Dictionary = e5
		if str(xe.get("site", "")) != "crash" or int(xe.get("min_danger", 1)) > max_danger:
			continue
		var xpd: PoiDef = db.call(&"get_def", &"poi", StringName(str(xe.get("poi", "")))) as PoiDef if db != null else null
		if xpd == null:
			continue
		var rx := rng("places:crash:%s" % xpd.id)
		for k5: int in _pool_count(xe, rx, density, area16):
			if not _place_one(xe, Vector2(xpd.footprint), rx, wcfg):
				warnings.append("no spot for %s" % xpd.id)


## How many of a pool entry a world gets: its density per region times the map's regions (one more
## by chance for the fraction), at most its `max` per 16 km².
func _pool_count(pe: Dictionary, r: RandomNumberGenerator, density: float, area16: float) -> int:
	var expected: float = float(pe.get("per_region", 0.1)) * size * size * density
	var cap: int = maxi(1, int(ceil(float(pe.get("max", 2)) * area16 - 0.001)))
	# A place the story knows as one (the premise's old field lab) stands once in any world;
	# the rest repeat with the map's area, as 7 Days' named places do.
	if bool(pe.get("unique", false)):
		cap = 1
	return mini(cap, int(floor(expected + r.randf())))


## Tries to place one place of a pool entry: candidates for its site, the first that fits (false:
## none did).
func _place_one(pe: Dictionary, fp: Vector2, r: RandomNumberGenerator, wcfg: Dictionary) -> bool:
	var site: String = str(pe.get("site", "forest"))
	var is_fw: bool = pe.has("framework")
	var def_id: String = str(pe.get("framework", pe.get("poi", "")))
	var keep_water: bool = bool(pe.get("keep_water", false))
	var min_danger: int = int(pe.get("min_danger", 1))
	var spacing: float = float(wcfg.get("spacing", 160.0))
	var max_relief: float = float(wcfg.get("max_relief", 7.0))
	var margin: float = float(tun.get("region_margin", 72.0)) - 8.0
	var mcfg: Dictionary = wcfg.get("mine", {})
	var pad: Vector2 = Vector2.ZERO
	if site == "mine":
		var pa: Array = pe.get("pad", [fp.x, fp.y])
		pad = Vector2(float(pa[0]), float(pa[1]))
	for attempt: int in 90:
		var ra: Array = pe.get("ring", [300.0, 900.0])
		var cand: Dictionary = _candidate(site, fp, r, pad.x, mcfg, min_danger, Vector2(float(ra[0]), float(ra[1])))
		if cand.is_empty():
			continue
		var origin: Vector2 = cand["origin"]
		var rot: float = cand["rot"]
		var poly: PackedVector2Array = rect_poly(origin, fp, rot)
		var centre: Vector2 = origin + (fp * 0.5).rotated(deg_to_rad(rot))
		var cell: String = cell_at(centre)
		if cell == "" or int(regions[cell]["danger"]) < min_danger or not inside_one_region(poly, margin):
			continue
		if (drop.get("pos", Vector2(1e9, 1e9)) as Vector2).distance_to(centre) < float((tun.get("drop_site", {}) as Dictionary).get("poi_distance", 160.0)) + fp.length() * 0.5:
			continue
		if _hits_built(poly, spacing * 0.5):
			continue
		var road_gap: float = road_clearance(poly)
		if road_gap < (4.0 if site == "roadside" else 18.0):
			continue
		if site == "mine":
			# Only the pad is levelled (by the composer); the hill over the levels stays as it is.
			if water_clearance(poly) < 14.0 or is_nan(_mine_pad_height(def_id, origin, rot, pad, mcfg)):
				continue
		elif not keep_water:
			if water_clearance(poly) < 14.0:
				continue
			var st: Dictionary = terrain.stats_in(poly)
			if float(st["max"]) - float(st["min"]) > max_relief:
				continue
			terrain.flatten(poly, float(st["mean"]), 26.0)
		var pid: String = "%s_%d" % [def_id, places.size()]
		var fwd: Vector2 = Vector2(0.0, 1.0).rotated(deg_to_rad(rot))
		var access: Vector2 = origin + Vector2(fp.x * 0.5, fp.y).rotated(deg_to_rad(rot)) + fwd * 3.0
		if pe.has("door"):
			var da: Array = pe["door"]
			access = origin + Vector2(float(da[0]), float(da[1])).rotated(deg_to_rad(rot))
		if site == "mine":
			# The track comes along the hillside to the door, from a point out on the contour (local Z),
			# so neither the router's 32 m cells nor its grading cut over the levels under the hill.
			var side: float = -1.0 if (access - origin).rotated(-deg_to_rad(rot)).y < fp.y * 0.5 else 1.0
			cand["approach"] = access + Vector2(0.0, float(mcfg.get("approach", 24.0)) * side).rotated(deg_to_rad(rot))
			cand["keep_off"] = rect_poly(origin + Vector2(pad.x, 0.0).rotated(deg_to_rad(rot)), Vector2(fp.x - pad.x, fp.y), rot)
		var place: Dictionary = {"id": pid, "kind": "framework" if is_fw else "poi", "def": def_id, "origin": origin, "rot": rot, "size": fp,
			"poly": poly, "biome": str(pe.get("biome", "meadow")), "skirt": float(pe.get("skirt", 10.0)), "keep_water": keep_water,
			"access": access, "site": site, "cell": cell, "center": centre, "pad": pad}
		if cand.has("road_point"):
			# A roadside place stands at its road's level where its drive leaves it (TD-320).
			place["level_at"] = cand["road_point"]
		places.append(place)
		_place_grid.insert(places.size() - 1, _bounds(poly).grow(1.0))
		router.block_polygon(poly, 6.0)
		_access(place, str(pe.get("access", "trail")), cand)
		return true
	return false


## A candidate frame {origin, rot} for a site, or {} (the caller tries again). `pad_len`, `mcfg`,
## `min_danger`: a mine's pad length along local X, tuning.wilderness.mine and its least danger.
func _candidate(site: String, fp: Vector2, r: RandomNumberGenerator, pad_len: float = 0.0, mcfg: Dictionary = {}, min_danger: int = 1,
		ring: Vector2 = Vector2(300.0, 900.0)) -> Dictionary:
	var lim: float = size * 512.0 - 100.0
	match site:
		"companion":
			# Out in the wilds within a walk of the drop site (ADR-0058): a ring round it.
			var dp: Vector2 = drop.get("pos", Vector2.ZERO)
			var at: Vector2 = dp + Vector2.from_angle(r.randf() * TAU) * r.randf_range(ring.x, ring.y)
			if absf(at.x) > lim or absf(at.y) > lim or water_at(at) < 30.0:
				return {}
			var rot5: float = 15.0 * float(r.randi() % 24)
			return {"origin": at - (fp * 0.5).rotated(deg_to_rad(rot5)), "rot": rot5}
		"crash":
			# The lift came in over the nearest map edge and went down short of the drop: a point
			# `ring` m out from the drop site toward that edge (a little either side), its nose (the
			# plan's -Z) to the drop and its swath trailing back the way it came.
			var dp6: Vector2 = drop.get("pos", Vector2.ZERO)
			var half6: float = size * 512.0
			var edges: Array[Vector2] = [Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1)]
			var dists: Array[float] = [dp6.x + half6, half6 - dp6.x, dp6.y + half6, half6 - dp6.y]
			var out6: Vector2 = edges[dists.find(dists.min())]
			# Most tries toward that edge; the rest from anywhere round (a drop site hard by the edge
			# leaves no room out that way).
			var spread6: float = 35.0 if r.randf() < 0.6 else 180.0
			var at6: Vector2 = dp6 + out6.rotated(deg_to_rad(r.randf_range(-spread6, spread6))) * r.randf_range(ring.x, ring.y)
			if absf(at6.x) > lim or absf(at6.y) > lim or water_at(at6) < 40.0:
				return {}
			var to_drop: Vector2 = (dp6 - at6).normalized()
			var rot6: float = snappedf(rad_to_deg(to_drop.angle()) + 90.0, 0.1)
			return {"origin": at6 - (fp * 0.5).rotated(deg_to_rad(rot6)), "rot": rot6}
		"mine":
			# A hillside: of a few dry points steep enough, the one where the ground rises most from
			# the pad's middle to 20 m into the hill. Local +X runs uphill (the plan's levels run on
			# along +X past the pad), so the pad is at the foot and the levels go into the hill.
			var min_slope: float = float(mcfg.get("slope", 0.12))
			var margin_m: float = float(tun.get("region_margin", 72.0)) - 8.0
			var best_m: Dictionary = {}
			var best_ms: float = INF
			for k4: int in 24:
				var p4 := Vector2(r.randf_range(-lim, lim), r.randf_range(-lim, lim))
				var c4: String = cell_at(p4)
				if c4 == "" or int(regions[c4]["danger"]) < min_danger or water_at(p4) < 40.0:
					continue
				var st: float = terrain.step
				var grad := Vector2(terrain.height(p4.x + st, p4.y) - terrain.height(p4.x - st, p4.y),
					terrain.height(p4.x, p4.y + st) - terrain.height(p4.x, p4.y - st)) / (2.0 * st)
				if grad.length() < min_slope:
					continue
				var up: Vector2 = grad.normalized()
				var rot4: float = snappedf(rad_to_deg(atan2(up.y, up.x)), 0.1)
				var origin4: Vector2 = p4 - Vector2(pad_len, fp.y * 0.5).rotated(deg_to_rad(rot4))
				if not inside_one_region(rect_poly(origin4, fp, rot4), margin_m):
					continue
				# Within reach of a road, so the miners' track can come to it (`access` gives up
				# beyond 900 m, TD-179).
				var nr4: Array = nearest_road(p4, ["highway", "county", "track"], true)
				if int(nr4[2]) < 0 or float(nr4[0]) > float(mcfg.get("road", 800.0)):
					continue
				var mid: Vector2 = p4 - up * pad_len * 0.5
				var ms: float = terrain.height(mid.x, mid.y) - terrain.height(p4.x + up.x * 20.0, p4.y + up.y * 20.0)
				if ms < best_ms:
					best_ms = ms
					best_m = {"origin": origin4, "rot": rot4}
			return best_m
		"roadside":
			var cands: Array[int] = []
			for i: int in roads.size():
				if str(roads[i]["class"]) in ["highway", "county"]:
					cands.append(i)
			if cands.is_empty():
				return {}
			var rd: Dictionary = roads[cands[r.randi() % cands.size()]]
			var line: Polyline2 = rd["line"]
			if line.total_length < 300.0:
				return {}
			var s: float = r.randf_range(120.0, line.total_length - 120.0)
			var p: Vector2 = line.point_at(s)
			var tg: Vector2 = line.tangent_at(s)
			# A straight stretch only: the drive and the frontage must line up with the road.
			if tg.dot(line.tangent_at(s - 30.0)) < 0.97 or tg.dot(line.tangent_at(s + 30.0)) < 0.97:
				return {}
			var nrm := Vector2(-tg.y, tg.x) * (1.0 if r.randf() < 0.5 else -1.0)
			var gap: float = float(rd["width"]) * 0.5 + float(rd["shoulder"]) + 9.0
			var front: Vector2 = p + nrm * gap
			# The building's front (+Z) faces the road: local +Z maps to -nrm.
			var rot: float = rad_to_deg(atan2(nrm.x, -nrm.y))
			var origin: Vector2 = front - Vector2(fp.x * 0.5, fp.y).rotated(deg_to_rad(rot))
			return {"origin": origin, "rot": snappedf(rot, 0.1), "road": rd, "road_point": p + nrm * (float(rd["width"]) * 0.5)}
		"lake_shore":
			if terrain.lakes.is_empty():
				return {}
			var lk: Dictionary = terrain.lakes[r.randi() % terrain.lakes.size()]
			var poly: PackedVector2Array = lk["polygon"]
			var k: int = r.randi() % poly.size()
			var sp: Vector2 = poly[k]
			var outward: Vector2 = (sp - (lk["center"] as Vector2)).normalized()
			# Back to the water, front to the land; the back third stands on piles over the lake.
			var rot2: float = rad_to_deg(atan2(-outward.x, outward.y))
			var back_mid: Vector2 = sp - outward * fp.y * 0.32
			var origin2: Vector2 = back_mid - Vector2(fp.x * 0.5, 0.0).rotated(deg_to_rad(rot2))
			return {"origin": origin2, "rot": snappedf(rot2, 0.1)}
		_:
			var best: Dictionary = {}
			var best_score: float = INF
			for k2: int in 14:
				var p2 := Vector2(r.randf_range(-lim, lim), r.randf_range(-lim, lim))
				var score: float = 0.0
				var wd: float = water_at(p2)
				var e: float = terrain.height(p2.x, p2.y)
				var biome: String = biome_at(p2)
				match site:
					"summit":
						score = -e + terrain.slope(p2.x, p2.y) * 300.0
					"waterside":
						if wd < 60.0 or wd > 200.0:
							continue
						score = wd + terrain.slope(p2.x, p2.y) * 300.0
					"forest":
						if biome != "conifer_forest" and biome != "birch_grove":
							continue
						score = terrain.slope(p2.x, p2.y) * 300.0 + r.randf() * 20.0
					"remote":
						score = -(drop.get("pos", Vector2.ZERO) as Vector2).distance_to(p2) * 0.05 - e * 0.2 + terrain.slope(p2.x, p2.y) * 200.0
					"farm":
						if biome != "meadow" and biome != "birch_grove":
							score += 30.0
						score += terrain.slope(p2.x, p2.y) * 400.0 + r.randf() * 10.0
				if score < best_score:
					best_score = score
					best = {"p": p2}
			if best.is_empty():
				return {}
			var rot3: float = 15.0 * float(r.randi() % 24)
			var origin3: Vector2 = (best["p"] as Vector2) - (fp * 0.5).rotated(deg_to_rad(rot3))
			return {"origin": origin3, "rot": rot3}
	return {}


## True when a polygon (grown by `gap`) touches a town's lots (grown tuning.towns.clearance.lots)
## or street corridors (grown clearance.streets), another place, or the drop site's clearing. Only
## what the spatial indexes return near the grown polygon is tested exactly.
func _hits_built(poly: PackedVector2Array, gap: float) -> bool:
	var grown: PackedVector2Array = poly
	var off: Array = Geometry2D.offset_polygon(poly, gap)
	if not off.is_empty():
		grown = off[0]
	var gb: Rect2 = _bounds(grown).grow(1.0)
	for id: int in _lot_grid.query(gb):
		if not Geometry2D.intersect_polygons(grown, _lot_grown[id]).is_empty():
			return true
	var street_gap: float = float(((tun.get("towns", {}) as Dictionary).get("clearance", {}) as Dictionary).get("streets", 8.0))
	for sid: int in _street_grid.query(gb):
		var st: Dictionary = _streets[sid >> Grid.PART_BITS]
		var line: Polyline2 = st["line"]
		var k: int = sid & Grid.PART_MASK
		if _seg_poly_distance(line.points[k], line.points[k + 1], grown) < float(st["need"]) + street_gap:
			return true
	for id2: int in _place_grid.query(gb):
		if not Geometry2D.intersect_polygons(grown, places[id2]["poly"]).is_empty():
			return true
	for pt: Dictionary in posts:
		if gb.intersects(_bounds(pt["safe"])) and not Geometry2D.intersect_polygons(grown, pt["safe"]).is_empty():
			return true
	return false


static func _bounds(poly: PackedVector2Array) -> Rect2:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	return bb


## The height a mine's pad will be levelled to (the composer's: the mean of 5 x 5 samples, + 5 cm),
## or NAN when the site does not fit: the ground varies more than pad_relief over the pad, or the
## reference ground over a buried cell beyond the pad is less than `portal` (at the pad's edge) to
## `cover` (`taper` m in) above that level's ceiling (TD-164). Buried cells under the pad must not
## rise above it (the adit's drift meets the pad flush). The composer's pad skirt eases the ground
## near the pad down to it, and the region's detail noise comes on top; the margins leave room.
func _mine_pad_height(def_id: String, origin: Vector2, rot: float, pad: Vector2, mcfg: Dictionary) -> float:
	var a: float = deg_to_rad(rot)
	var lo: float = INF
	var hi: float = -INF
	var acc: float = 0.0
	for k: int in 25:
		var wp: Vector2 = origin + Vector2((k % 5 + 0.5) / 5.0 * pad.x, (k / 5 + 0.5) / 5.0 * pad.y).rotated(a)
		var g: float = _mine_ref.h(wp.x, wp.y)
		lo = minf(lo, g)
		hi = maxf(hi, g)
		acc += g
	if hi - lo > float(mcfg.get("pad_relief", 9.0)):
		return NAN
	var pad_y: float = acc / 25.0 + 0.05
	# A drift comes out of the hill at the pad, as an adit's portal does: the cover grows from
	# `portal` at the pad's edge to `cover` `taper` metres in.
	var cover: float = float(mcfg.get("cover", 4.0))
	var portal: float = float(mcfg.get("portal", 1.5))
	var taper: float = float(mcfg.get("taper", 16.0))
	for s: Array in buried_samples(def_id):
		var lp: Vector2 = s[0]
		var ceil_off: float = s[1]
		if lp.x >= 0.0 and lp.y >= 0.0 and lp.x <= pad.x and lp.y <= pad.y:
			if ceil_off > 0.01:
				return NAN
			continue
		var wp2: Vector2 = origin + lp.rotated(a)
		var d: float = Vector2(maxf(maxf(-lp.x, lp.x - pad.x), 0.0), maxf(maxf(-lp.y, lp.y - pad.y), 0.0)).length()
		if _mine_ref.h(wp2.x, wp2.y) < pad_y + ceil_off + lerpf(portal, cover, smoothstep(0.0, taper, d)):
			return NAN
	return pad_y


## One sample per 2 m block of a POI's buried-level cells that no ground-floor room covers (those
## run on under the ground): [local centre, the highest ceiling there above the POI's origin]
## (TerrainHoles.add_poi's buried holes: a level's floor plus a storey less the slab). Cached.
func buried_samples(def_id: String) -> Array:
	if _buried_samples.has(def_id):
		return _buried_samples[def_id]
	var out: Array = []
	var db: Node = ContentDB.instance
	var pd: PoiDef = db.call(&"get_def", &"poi", StringName(def_id)) as PoiDef if db != null else null
	if pd != null:
		var layout: PoiLayout = PoiLayout.compile(pd)
		var covered: Dictionary = {}
		for c0: Vector2i in layout.room_cells(0):
			covered[c0] = true
		var blocks: Dictionary = {}
		for li: int in layout.level_ids:
			if li >= 0 or not bool((layout.levels[li] as Dictionary).get("buried", false)):
				continue
			var ceil_off: float = layout.level_y(li) + PoiLayout.STOREY - TerrainHoles.SLAB
			for c: Vector2i in layout.room_cells(li):
				if covered.has(c):
					continue
				var key := Vector2i(c.x >> 1, c.y >> 1)
				if not blocks.has(key) or float(blocks[key][1]) < ceil_off:
					blocks[key] = [layout.origin + Vector2(c) + Vector2(0.5, 0.5), ceil_off]
		var keys: Array = blocks.keys()
		keys.sort()
		for key2: Variant in keys:
			out.append(blocks[key2])
	_buried_samples[def_id] = out
	return out


## The way to a place: a short asphalt drive off the road it fronts, a dirt track or a footpath
## from the nearest road to its front.
func _access(place: Dictionary, kind: String, cand: Dictionary) -> void:
	if kind == "none":
		return  # found, not reached by a path (the companion's camp, ADR-0058)
	var to: Vector2 = place["access"]
	if kind == "drive" and cand.has("road_point"):
		var from: Vector2 = cand["road_point"]
		var pts := PackedVector2Array([from, from.lerp(to, 0.5), to + (to - from).normalized() * 2.0])
		_add_road(pts, "drive", "%s drive" % place["def"], false)
		return
	# A mine's way in arrives along the hillside (`approach`, then the door), never over its levels.
	var via: Vector2 = cand.get("approach", to)
	var nr: Array = nearest_road(via, ["highway", "county", "track"] if kind == "track" else [], true)
	# Far from any road a place is reached cross-country: a trail kilometres long reads as a
	# scribble across the map.
	if int(nr[2]) < 0 or float(nr[0]) > (900.0 if kind == "track" else 700.0):
		return
	var start: Vector2 = nr[1]
	var route: PackedVector2Array = _leave_road(router.route(start, via, 500.0, 0.6, 1.5 if kind == "trail" else 1.25), int(nr[2]))
	if route.size() < 2:
		return
	var graded: bool = true
	if via != to:
		# A track's grading would cut into the hill over the levels: where the smoothed route comes
		# that close it is a footpath instead (painted, not graded).
		var keep_off: PackedVector2Array = cand["keep_off"]
		for k2: int in route.size() - 1:
			if _seg_poly_distance(route[k2], route[k2 + 1], keep_off) < 12.0:
				graded = false
				break
		route.append(to)
	# A track that would have to wind up a slope (half as long again as the straight line) is a
	# footpath instead: switchbacks of dirt road read as scribble.
	var length: float = 0.0
	for k: int in route.size() - 1:
		length += route[k].distance_to(route[k + 1])
	if kind == "track" and graded and length < start.distance_to(to) * 1.5:
		_add_road(route, "track", "%s track" % place["def"], false)
	else:
		paths.append({"id": "%s_trail" % place["id"], "points": route, "width": 1.6, "surface": "dirt"})


## A route from a vertex of road `ri` keeps to that road's cells (cheap to reuse) before it turns
## off, 6-20 m beside the road: a second road along the first (TD-139). It starts where it leaves
## instead: from the road's nearest point to the first point of the route over LEAVE_ROAD m out.
func _leave_road(route: PackedVector2Array, ri: int) -> PackedVector2Array:
	if route.size() < 2 or ri < 0:
		return route
	var line: Polyline2 = roads[ri]["line"]
	var walked: float = 0.0
	for k: int in route.size() - 1:
		var seg: float = route[k].distance_to(route[k + 1])
		var n: int = maxi(1, int(ceil(seg / 4.0)))
		for st: int in range(1, n + 1):
			var q: Vector2 = route[k].lerp(route[k + 1], float(st) / n)
			var on: Vector3 = line.closest(q)
			if on.x <= LEAVE_ROAD:
				continue
			if walked + seg * st / n < 16.0:
				return route  # it turns off at once
			var out := PackedVector2Array([line.point_at(on.y), q])
			if q.distance_to(route[k + 1]) > 1.0:
				out.append(route[k + 1])
			out.append_array(route.slice(k + 2))
			# Where the route had run on along the road and turned back, the new start is a hook.
			return _despike(out)
		walked += seg
	return route


# --- Trader posts ----------------------------------------------------------------------------------

## The trader def every generated post uses (session 2's data/traders/program_relay.json): it posts
## Waystation 9's contracts and shares its standing.
const TRADER_DEF: String = "program_relay"
## A post's yard in its own frame, local +Z toward the road it fronts: a ring of barriers from x -14
## to 14 and z -15 to 21, sign included (TraderPost).
const POST_MIN := Vector2(-14.0, -15.0)
const POST_MAX := Vector2(14.0, 21.0)
## Its gate, on local +Z.
const POST_GATE: float = 12.8


## One trader post by each town, at least `spacing` metres apart, on a highway or county road where
## it leaves the town. Each post is a `trader:<def>:<n>` spawn facing that road, with a clearing and
## a drive to its gate (TraderManager builds the post from the spawn). Its safe zone keeps lots,
## streets and wilderness places out: the guards shoot whatever Hollowed wake inside it.
func _trader_posts() -> void:
	var tcfg: Dictionary = tun.get("traders", {})
	var spacing: float = float(tcfg.get("spacing", 600.0))
	var safe: float = float(tcfg.get("safe_radius", 40.0))
	var r := rng("traders")
	for tw: Dictionary in towns:
		var c: Vector2 = tw["center"]
		var best: Dictionary = {}
		# Just outside the town, farther out where a bend, a slope, water or the town's outer lots
		# leave no room at the first ring.
		# (Bigger towns, VERSION 12, farm out further along their roads: up to past the outskirts.)
		for extra: float in [30.0, 70.0, 120.0, 190.0, 280.0, 380.0, 480.0]:
			var ring: float = float(tw["radius"]) + safe + extra
			for i: int in roads.size():
				if not str(roads[i]["class"]) in ["highway", "county"]:
					continue
				var line: Polyline2 = roads[i]["line"]
				var prev: float = c.distance_to(line.point_at(0.0)) - ring
				var s: float = 0.0
				while s + 6.0 <= line.total_length:
					s += 6.0
					var d: float = c.distance_to(line.point_at(s)) - ring
					if prev * d <= 0.0:
						for side: float in [1.0, -1.0]:
							var cand: Dictionary = _post_candidate(i, s, side, safe)
							if not cand.is_empty():
								cand["score"] = float(cand["score"]) + r.randf()
								if best.is_empty() or float(cand["score"]) < float(best["score"]):
									best = cand
					prev = d
			if not best.is_empty():
				break
		if best.is_empty():
			# No crossing of those rings fits (a bigger town's farms along its roads, a bend, the
			# map's edge): anywhere along a highway, county road or track out to 900 m past the
			# town, nearest and on the bigger roads best.
			var lo: float = float(tw["radius"]) + safe + 30.0
			for i2: int in roads.size():
				var cls2: String = str(roads[i2]["class"])
				if not cls2 in ["highway", "county", "track"]:
					continue
				var line2: Polyline2 = roads[i2]["line"]
				var s2: float = 0.0
				while s2 + 12.0 <= line2.total_length:
					s2 += 12.0
					var d2: float = c.distance_to(line2.point_at(s2))
					if d2 < lo or d2 > lo + 900.0:
						continue
					for side2: float in [1.0, -1.0]:
						var cand2: Dictionary = _post_candidate(i2, s2, side2, safe)
						if not cand2.is_empty():
							cand2["score"] = float(cand2["score"]) + (d2 - lo) * 0.02 + (8.0 if cls2 == "track" else 0.0) + r.randf()
							if best.is_empty() or float(cand2["score"]) < float(best["score"]):
								best = cand2
		if best.is_empty():
			warnings.append("no trader post by %s" % tw["name"])
			continue
		var pos: Vector2 = best["pos"]
		var crowded: bool = false
		for pt: Dictionary in posts:
			if (pt["pos"] as Vector2).distance_to(pos) < spacing:
				crowded = true
				break
		if crowded:
			continue
		var poly: PackedVector2Array = best["poly"]
		terrain.flatten(poly, float(best["ground"]), 18.0)
		router.block_polygon(poly, 6.0)
		var from: Vector2 = best["road_point"]
		var gate: Vector2 = best["gate"]
		_add_road(PackedVector2Array([from, from.lerp(gate, 0.5), gate + (gate - from).normalized() * 2.0]), "drive", "%s trader drive" % tw["name"], false)
		posts.append({"id": "trader:%s:%d" % [TRADER_DEF, posts.size()], "pos": pos, "yaw": best["yaw"], "cell": cell_at(pos),
			"poly": poly, "safe": best["safe"], "town": tw["id"]})


## A post beside road `ri` at arc `s`, on the `side` (+1 left, -1 right) of its travel: {pos, yaw,
## poly, safe, gate, road_point, ground, score}, or {} where it doesn't fit (a bend, steep or wet
## ground, a region border, or lots, streets, places or the drop site inside its safe zone).
func _post_candidate(ri: int, s: float, side: float, safe: float) -> Dictionary:
	var rd: Dictionary = roads[ri]
	var line: Polyline2 = rd["line"]
	if s < 40.0 or s > line.total_length - 40.0:
		return {}
	var tg: Vector2 = line.tangent_at(s)
	# A straight stretch only: the drive and the yard's front must line up with the road.
	if tg.dot(line.tangent_at(s - 30.0)) < 0.97 or tg.dot(line.tangent_at(s + 30.0)) < 0.97:
		return {}
	var nrm := Vector2(-tg.y, tg.x) * side
	var edge: float = float(rd["width"]) * 0.5 + float(rd["shoulder"])
	# The sign (local z 21) stands 6 m back from the shoulder.
	var pos: Vector2 = line.point_at(s) + nrm * (edge + POST_MAX.y + 6.0)
	# Local +Z faces the road: (sin yaw, cos yaw) = -nrm, so Basis(UP, yaw) turns the post to it.
	var front: Vector2 = -nrm
	var yaw: float = snappedf(rad_to_deg(atan2(front.x, front.y)), 0.1)
	var ax := Vector2(front.y, -front.x)
	var poly := PackedVector2Array()
	for k: Vector2 in [Vector2(POST_MIN.x, POST_MIN.y), Vector2(POST_MAX.x, POST_MIN.y), Vector2(POST_MAX.x, POST_MAX.y), Vector2(POST_MIN.x, POST_MAX.y)]:
		poly.append(pos + ax * k.x + front * k.y)
	var safe_poly := PackedVector2Array()
	for k2: int in 12:
		safe_poly.append(pos + Vector2.from_angle(TAU * k2 / 12.0) * safe)
	var margin: float = float(tun.get("region_margin", 72.0)) - 8.0
	if cell_at(pos) == "" or not inside_one_region(poly, margin):
		return {}
	if water_clearance(poly) < 14.0 or (drop.get("pos", Vector2(1e9, 1e9)) as Vector2).distance_to(pos) < safe + 40.0:
		return {}
	if _hits_built(safe_poly, 0.0) or road_clearance(poly, ri) < 4.0:
		return {}
	var st: Dictionary = terrain.stats_in(poly)
	var relief: float = float(st["max"]) - float(st["min"])
	if relief > float((tun.get("traders", {}) as Dictionary).get("max_relief", 6.0)):
		return {}
	return {"pos": pos, "yaw": yaw, "poly": poly, "safe": safe_poly, "gate": pos + front * POST_GATE,
		"road_point": line.point_at(s) + nrm * float(rd["width"]) * 0.5, "ground": float(st["mean"]), "score": relief}


# --- Bridges ---------------------------------------------------------------------------------------

## Every road crossing a river gets a bridge span over its channel and banks.
func _bridges() -> void:
	for rd: Dictionary in roads:
		var line: Polyline2 = rd["line"]
		for rv: Dictionary in terrain.rivers:
			var rl: Polyline2 = rv["line"]
			if not line.bounds.grow(20.0).intersects(rl.bounds.grow(20.0)):
				continue
			var spans: Array = []
			for k: int in line.points.size() - 1:
				var a: Vector2 = line.points[k]
				var b: Vector2 = line.points[k + 1]
				if not rl.bounds.grow(4.0).has_point(a) and not rl.bounds.grow(4.0).has_point(b):
					continue
				var qa: Vector3 = rl.closest(a)
				var qb: Vector3 = rl.closest(b)
				if qa.x > 40.0 and qb.x > 40.0:
					continue
				if signf(qa.z) == signf(qb.z):
					continue
				var tt: float = qa.x / maxf(0.001, qa.x + qb.x)
				var x: Vector2 = a.lerp(b, tt)
				var s_road: float = line.lengths[k] + a.distance_to(b) * tt
				var q: Vector3 = rl.closest(x)
				var half_w: float = rl.value_at(Array(rv["widths"]), q.y) * 0.5
				var sin_a: float = absf(line.tangent_at(s_road).cross(rl.tangent_at(q.y)))
				var reach: float = (half_w + float(rv["bank"]) + 4.0) / maxf(0.4, sin_a) + 6.0
				var dup: bool = false
				for sp: Array in spans:
					if absf(float(sp[0]) - s_road) < 60.0:
						dup = true
				if dup:
					continue
				spans.append([s_road, reach])
			for sp2: Array in spans:
				var s0: float = maxf(0.0, float(sp2[0]) - float(sp2[1]))
				var s1: float = minf(line.total_length, float(sp2[0]) + float(sp2[1]))
				var p0: Vector2 = line.point_at(s0)
				var p1: Vector2 = line.point_at(s1)
				(rd["bridges"] as Array).append({"from": [snappedf(p0.x, 0.1), snappedf(p0.y, 0.1)], "to": [snappedf(p1.x, 0.1), snappedf(p1.y, 0.1)], "deck": "auto"})


# --- The Bloom -----------------------------------------------------------------------------------

func _bloom() -> void:
	var bcfg: Dictionary = tun.get("bloom", {})
	var per: Array = bcfg.get("per_danger", [0, 0, 0.6, 1.2, 2.0])
	var rr: Array = bcfg.get("radius", [40, 110])
	var r := rng("bloom")
	for cell: String in regions:
		var dg: int = int(regions[cell]["danger"])
		var want: int = int(floor(float(per[clampi(dg - 1, 0, per.size() - 1)]) + r.randf()))
		var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(-120.0)
		for k: int in want:
			for attempt: int in 30:
				var p := Vector2(r.randf_range(rect.position.x, rect.end.x), r.randf_range(rect.position.y, rect.end.y))
				var b: String = biome_at(p)
				# The Bloom takes the forest, and pools in the fens (ADR-0041).
				if b != "conifer_forest" and b != "birch_grove" and b != "fen":
					continue
				if water_at(p) < 40.0 or float(nearest_road(p)[0]) < 40.0:
					continue
				if _town_distance(p) < 120.0 or _near_lots(p, 60.0):
					continue
				var clear: bool = true
				for pl: Dictionary in places:
					if (pl["center"] as Vector2).distance_to(p) < 60.0:
						clear = false
				if not clear:
					continue
				blooms.append({"id": "bloom_%s_%d" % [cell.to_lower(), k], "at": p, "radius": snappedf(r.randf_range(float(rr[0]), float(rr[1])), 1.0),
					"strength": snappedf(clampf(0.45 + 0.15 * (dg - 3) + r.randf() * 0.25, 0.3, 1.0), 0.01), "edge": snappedf(r.randf_range(0.45, 0.75), 0.01), "cell": cell})
				break


# --- Caves -----------------------------------------------------------------------------------------

## Forest caves (ADR-0056, docs/CAVES_PLAN.md WS-E): a few grottos and rock shelters per region in
## its steep forest and rocky ground, off roads, towns, places and the drop site. Last, from its own
## stream, and they change nothing else (a cave is carved into the volume at load; the heights
## stay), so every other place stays where it was. Each is checked here with the real planner over
## the composer's reference ground. The game plans it again from the composed region (the mouth
## settles within `search` m, the shape from CaveSites.shape_seed(world id, cave id)) and leaves out
## one that no longer fits.
func _caves() -> void:
	var ccfg: Dictionary = tun.get("caves", {})
	var per: float = float(ccfg.get("per_region", 0.0)) * settings.num("wilderness")
	if per <= 0.0:
		return
	var r := rng("caves")
	var ground: RefGround = _ref if _ref != null else RefGround.new(terrain, settings.seed & 0x7fffffff, size)
	var height_fn: Callable = ground.h
	var db: Node = ContentDB.instance
	var cfg: Dictionary = db.call(&"config", &"caves") if db != null else CavePlan.DEFAULTS
	var styles: Dictionary = ccfg.get("styles", {"grotto": 1.0})
	var biomes: Array = ccfg.get("biomes", ["conifer_forest", "birch_grove", "rocky_slope", "burnt_forest"])
	var clear: Dictionary = ccfg.get("clearance", {})
	var cmax: int = int(ccfg.get("max_per_region", 2))
	var inset: float = float(ccfg.get("inset", 96.0))
	var tries: int = int(ccfg.get("tries", 24))
	var search: float = float(ccfg.get("search", 12.0))
	var style_cfg: Dictionary = cfg.get("styles", {})
	var cells: Array = regions.keys()
	cells.sort()
	for cell: String in cells:
		var want: int = mini(cmax, int(floor(per + r.randf())))
		var rect: Rect2 = (regions[cell]["rect"] as Rect2).grow(-inset)
		var made: int = 0
		for attempt: int in tries:
			if made >= want:
				break
			# Drawn every attempt whatever happens next, so one try's luck never shifts the next's.
			var near := Vector2(r.randf_range(rect.position.x, rect.end.x), r.randf_range(rect.position.y, rect.end.y))
			var pick: float = r.randf()
			var style: String = _pick_style(styles, pick)
			if not biomes.has(biome_at(near)) or not _cave_clear(near, clear):
				continue
			var slope: float = float((style_cfg.get(style, {}) as Dictionary).get("min_slope_deg", cfg.get("min_slope_deg", 18.0)))
			var got: Dictionary = CaveSites.settle_mouth(height_fn, near, NAN, search, {"min_slope_deg": slope})
			if got.is_empty():
				continue
			var mp: Vector3 = got["pos"]
			# Snapped as region.json will hold it, so the plan checked is the one the game makes.
			var m := Vector2(snappedf(mp.x, 0.1), snappedf(mp.z, 0.1))
			if not biomes.has(biome_at(m)) or not _cave_clear(m, clear):
				continue
			var id: String = "cave_%s_%d" % [cell.to_lower(), made]
			var spec: Dictionary = {"id": id, "style": style, "mouth": [m.x, m.y], "heading": "uphill", "search": search,
				"region_id": str(regions[cell]["id"]), "region_rect": regions[cell]["rect"]}
			# The shape the game will give it (CaveSites.from_region: per world and cave id).
			if not CavePlan.build(spec, CaveSites.shape_seed(world_id, id), height_fn, cfg).ok:
				continue
			caves.append({"id": id, "cell": cell, "style": style, "mouth": m})
			made += 1


## A style by weight (tuning.caves.styles), `pick` in 0..1; keys in sorted order so the draw is stable.
static func _pick_style(styles: Dictionary, pick: float) -> String:
	var keys: Array = styles.keys()
	keys.sort()
	var total: float = 0.0
	for k: String in keys:
		total += float(styles[k])
	var acc: float = 0.0
	for k2: String in keys:
		acc += float(styles[k2]) / maxf(total, 1e-6)
		if pick <= acc:
			return k2
	return str(keys[keys.size() - 1]) if not keys.is_empty() else "grotto"


## Whether a cave mouth at p keeps off what it must (tuning.caves.clearance, m): water, towns and
## their lots, roads, the drop site, places, trader posts and the other caves.
func _cave_clear(p: Vector2, c: Dictionary) -> bool:
	if water_at(p) < float(c.get("water", 30.0)) or _town_distance(p) < float(c.get("town", 150.0)) or _near_lots(p, float(c.get("lots", 60.0))):
		return false
	if not roads.is_empty() and float(nearest_road(p)[0]) < float(c.get("road", 40.0)):
		return false
	if not drop.is_empty() and (drop["pos"] as Vector2).distance_to(p) < float(c.get("drop", 200.0)):
		return false
	var place_gap: float = float(c.get("place", 80.0))
	for pl: Dictionary in places:
		if (pl["center"] as Vector2).distance_to(p) < place_gap:
			return false
	for pt: Dictionary in posts:
		if (pt["pos"] as Vector2).distance_to(p) < place_gap:
			return false
	for cv: Dictionary in caves:
		if (cv["mouth"] as Vector2).distance_to(p) < float(c.get("cave", 200.0)):
			return false
	return true


# --- Names -----------------------------------------------------------------------------------------

func _name_regions() -> void:
	var r := rng("names")
	var words: Array = (names.get("region_words", ["Grey"]) as Array).duplicate()
	var kinds: Array = names.get("regions", ["Woods"])
	var used: Dictionary = {}
	for cell: String in regions:
		var nm: String = ""
		for tw: Dictionary in towns:
			if str(tw["cell"]) == cell:
				nm = str(tw["name"])
		if nm == "":
			for k: int in 20:
				var cand: String = "%s %s" % [words[r.randi() % words.size()], kinds[r.randi() % kinds.size()]]
				if not used.has(cand):
					nm = cand
					break
		used[nm] = true
		regions[cell]["name"] = nm
		regions[cell]["id"] = "%s_%s" % [cell.to_lower(), _slug(nm)]


# --- Town heights and authored buildings ------------------------------------------------------------

## Each lot's pad height `y` (and the square's): the mean of the reference ground over its frame (5 x 5
## samples, as the frame is written) on the final macro grid, which the composer grades it to in
## every region the lot touches, and where PoiManager stands its building (plan §3.2 step 8).
func _finalize_town_heights() -> void:
	if towns.is_empty():
		return
	_ref = RefGround.new(terrain, settings.seed & 0x7fffffff, size)
	for tw: Dictionary in towns:
		var plan: Dictionary = tw["plan"]
		var streets: Array = plan.get("roads", [])
		# The world roads through or by it, as the composer will pick them (by its written points).
		var world_roads: Array = _world_roads_profiled()
		var cw: Array = Terrain._arr(PackedVector2Array([tw["center"]]))[0]
		var fixed: Array = TerrainComposer.town_world_roads(world_roads, Vector2(float(cw[0]), float(cw[1])), float(tw["radius"]))
		var profiles: Dictionary = TerrainComposer.town_street_profiles(streets, _ref.h, fixed)
		var lines: Dictionary = {}
		for fr: Dictionary in fixed:
			lines[str(fr["id"])] = fr["line"]
		for rv: Variant in streets:
			if (rv as Dictionary).has("points") and ((rv as Dictionary)["points"] as Array).size() >= 2:
				lines[str(rv["id"])] = Polyline2.from_array(rv["points"])
		for lv: Variant in plan.get("lots", []):
			var l: Dictionary = lv
			var y: float = _frame_height(l["frame"])
			# Within LOT_STREET_STEP of its street where the lot meets it (TD-318): the yard meets
			# the street flush and any difference with the ground is graded out behind it.
			var sid: String = str(l.get("street", ""))
			if lines.has(sid) and profiles.has(sid):
				var f: Array = l["frame"]
				var at: Vector3 = (lines[sid] as Polyline2).closest(Vector2(float(f[0]), float(f[1])))
				var sy: float = TerrainComposer.profile_at(profiles[sid], at.y)
				y = snappedf(clampf(y, sy - LOT_STREET_STEP, sy + LOT_STREET_STEP), 0.01)
			l["y"] = y
		if not (plan.get("plaza", {}) as Dictionary).is_empty():
			plan["plaza"]["y"] = _frame_height(plan["plaza"]["frame"])


## The places the composer levels from world data, as written ({id, origin, rotation, size}): every
## place on a pad of its whole footprint (not a mine's part pad, not one over water), TD-320.
func _world_pads() -> Array:
	var out: Array = []
	for pl: Dictionary in places:
		if bool(pl["keep_water"]) or (pl.get("pad", Vector2.ZERO) as Vector2) != Vector2.ZERO:
			continue
		var e: Dictionary = {"id": pl["id"], "origin": Terrain._arr(PackedVector2Array([pl["origin"]]))[0], "rotation": pl["rot"],
			"size": [(pl["size"] as Vector2).x, (pl["size"] as Vector2).y]}
		if pl.has("level_at"):
			e["level_at"] = Terrain._arr(PackedVector2Array([pl["level_at"]]))[0]
		out.append(e)
	return out


## _world_pads as WorldDef reads them.
func _world_pads_read() -> Array:
	var out: Array = []
	for pd: Dictionary in _world_pads():
		var e: Dictionary = {"id": pd["id"], "origin": Vector2(float(pd["origin"][0]), float(pd["origin"][1])), "rot": deg_to_rad(float(pd["rotation"])),
			"size": Vector2(float(pd["size"][0]), float(pd["size"][1]))}
		if pd.has("level_at"):
			e["level_at"] = Vector2(float(pd["level_at"][0]), float(pd["level_at"][1]))
		out.append(e)
	return out


## The world roads as the composer reads them (by their written points), each with its pinned
## profile (TerrainComposer.world_road_profiles), built once.
var _world_profiled: Array = []


func _world_roads_profiled() -> Array:
	if not _world_profiled.is_empty():
		return _world_profiled
	var rs: Array = []
	for rd: Dictionary in roads:
		rs.append({"id": rd["id"], "line": Polyline2.from_array(Terrain._arr(rd["points"])), "surface": rd["surface"], "width": float(rd["width"])})
	var profs: Dictionary = TerrainComposer.world_road_profiles(rs, _ref.h, _world_pads_read())
	for e: Dictionary in rs:
		e["profile"] = profs[str(e["id"])]
	_world_profiled = rs
	return rs


## How far a lot's yard may stand above or below its street where it meets it (m, TD-318).
const LOT_STREET_STEP: float = 0.3
## How far from its road a track or trail has left it (m, _leave_road; TD-139).
const LEAVE_ROAD: float = 20.0
## How far a town's cross road may turn off its axis (degrees, _cross_axis; TD-139).
const CROSS_SPREAD: float = 25.0


func _frame_height(f: Array) -> float:
	var c := Vector2(float(f[0]), float(f[1]))
	var yaw: float = deg_to_rad(float(f[4]))
	var az := Vector2(sin(yaw), cos(yaw))
	var ax := Vector2(az.y, -az.x)
	var acc: float = 0.0
	for k: int in 25:
		var p: Vector2 = c + ax * (((k % 5) / 4.0 - 0.5) * float(f[2])) + az * (((k / 5) / 4.0 - 0.5) * float(f[3]))
		acc += _ref.h(p.x, p.y)
	return snappedf(acc / 25.0, 0.01)


## Caps the authored buildings world-wide (plan §3.11: at most tuning.towns.authored_max towns hold
## each one) and makes sure every lot holds something: a civic lot only takes an authored civic
## building, so a town keeps as many pure civic lots as it has civic buildings that fit them all,
## and the rest take shops too.
func _assign_authored() -> void:
	if towns.is_empty():
		return
	var fws: Array = []
	for tw: Dictionary in towns:
		fws.append({"id": tw["id"], "tier_range": tw["tier"], "lots": (tw["plan"] as Dictionary).get("lots", [])})
	var cap: int = int((tun.get("towns", {}) as Dictionary).get("authored_max", 3))
	var given: Dictionary = LotPicker.assign_authored(fws, settings.seed, cap)
	var db: Node = ContentDB.instance
	for tw2: Dictionary in towns:
		var allowed: PackedStringArray = given.get(str(tw2["id"]), PackedStringArray())
		tw2["authored"] = allowed
		var lots: Array = (tw2["plan"] as Dictionary).get("lots", [])
		var pure: Array = []
		var smallest := Vector2i(1 << 20, 1 << 20)
		for lv: Variant in lots:
			if Array(lv["zoning"]) == ["civic"]:
				pure.append(lv)
				var s: Vector2i = LotPicker.lot_size(lv)
				smallest = Vector2i(mini(smallest.x, s.x), mini(smallest.y, s.y))
		if pure.is_empty():
			continue
		var fit_all: int = 0
		if db != null:
			for pid: String in allowed:
				var pd: PoiDef = db.call(&"get_def", &"poi", StringName(pid)) as PoiDef
				var tr: Array = tw2["tier"]
				if pd != null and Array(pd.zoning) == ["civic"] and pd.tier >= int(tr[0]) and pd.tier <= int(tr[1]) \
						and pd.footprint.x <= smallest.x and pd.footprint.y <= smallest.y:
					fit_all += 1
		for i: int in range(fit_all, pure.size()):
			(pure[i] as Dictionary)["zoning"] = ["civic", "commercial"]


# --- Output --------------------------------------------------------------------------------------

func world_name() -> String:
	var biggest: String = ""
	for tw: Dictionary in towns:
		biggest = str(tw["name"])
		break
	return ("%s County" % biggest) if biggest != "" else "The Unmapped Country"


func world_json() -> Dictionary:
	var rows: Array = []
	for j: int in terrain.n:
		var row: Array = []
		for i: int in terrain.n:
			row.append(snappedf(terrain.h[j * terrain.n + i], 0.1))
		rows.append(row)
	var bm_rows: Array = []
	for j2: int in biome_cols:
		var s: String = ""
		for i2: int in biome_cols:
			s += str(biome_cells[j2 * biome_cols + i2])
		bm_rows.append(s)
	var rivers: Array = []
	for rv: Dictionary in terrain.rivers:
		rivers.append({"id": rv["id"], "name": rv["name"], "points": Terrain._arr(rv["control"]), "width": _rounded(rv["widths"], 0.1),
			"depth": rv["depth"], "bank": rv["bank"], "level": _rounded(rv["levels"], 0.01), "valley_width": rv["valley_width"], "valley_slope": rv["valley_slope"]})
	var lakes: Array = []
	for l: Dictionary in terrain.lakes:
		lakes.append({"id": l["id"], "name": l["name"], "level": l["level"], "depth": l["depth"], "shore": l["shore"], "polygon": Terrain._arr(l["polygon"])})
	var road_out: Array = []
	for rd: Dictionary in roads:
		road_out.append({"id": rd["id"], "name": rd["name"], "class": rd["class"], "surface": rd["surface"], "width": rd["width"],
			"shoulder": rd["shoulder"], "points": Terrain._arr(rd["points"]), "bridges": rd["bridges"], "markings": rd["markings"]})
	var reg: Array = []
	for cell: String in regions:
		var rg: Dictionary = regions[cell]
		reg.append({"cell": cell, "id": rg["id"], "name": rg["name"], "biome": rg["biome"], "danger": rg["danger"], "status": "built",
			"summary": _region_summary(cell)})
	var town_out: Array = []
	var summary: Array = []
	for tw: Dictionary in towns:
		var c: Array = Terrain._arr(PackedVector2Array([tw["center"]]))[0]
		var b: Rect2 = tw["bounds"]
		town_out.append({"id": tw["id"], "name": tw["name"], "kind": tw["kind"], "framework": tw["fw_id"], "origin": [0.0, 0.0], "rotation": 0.0,
			"center": c, "radius": tw["radius"], "bounds": [snappedf(b.position.x, 0.1), snappedf(b.position.y, 0.1), ceilf(b.size.x), ceilf(b.size.y)]})
		summary.append({"id": tw["id"], "name": tw["name"], "kind": tw["kind"], "framework": tw["fw_id"], "region": regions[tw["cell"]]["id"],
			"center": c, "radius": tw["radius"], "lots": ((tw["plan"] as Dictionary).get("lots", []) as Array).size()})
	var post_out: Array = []
	for pt: Dictionary in posts:
		post_out.append({"id": pt["id"], "pos": Terrain._arr(PackedVector2Array([pt["pos"]]))[0], "yaw": pt["yaw"], "town": pt["town"],
			"region": regions[pt["cell"]]["id"]})
	var place_out: Array = []
	for pl: Dictionary in places:
		place_out.append({"id": pl["id"], "kind": pl["kind"], "def": pl["def"], "site": pl["site"], "region": regions[pl["cell"]]["id"],
			"polygon": Terrain._arr(pl["poly"])})
	return {
		"_doc": "A random world (ADR-0031, ADR-0040), generated by RwgGenerator v%d. Same schema as game/world/main_map/world.json (docs/REGIONS.md), plus world-level towns." % VERSION,
		"id": world_id, "name": world_name(), "seed": settings.seed & 0x7fffffff, "region_size": 1024, "cols": size, "rows": size, "sea_level": 0.0,
		"road_grade": "world",
		"generator": {"version": VERSION, "settings": settings.to_dict(), "key": settings.key(), "towns": summary, "places": place_out, "traders": post_out,
			"drop_site": Terrain._arr(PackedVector2Array([drop.get("pos", Vector2.ZERO)]))[0], "timings_ms": timings, "warnings": Array(warnings)},
		"macro": {"step": terrain.step, "corner_heights": rows, "noise": {"frequency": 0.001, "octaves": 1, "amplitude": 0.0, "ridged_amplitude": 0.0, "mountain_boost": 0.0}},
		"biome_map": {"ids": Array(BIOMES), "step": biome_step, "cols": biome_cols, "rows": biome_cols, "rows_data": bm_rows},
		"rivers": rivers, "lakes": lakes, "roads": road_out, "regions": reg, "towns": town_out, "pads": _world_pads(),
	}


## Float32 values as an Array of float64s on a grid step (float32 noise stays out of the JSON).
static func _rounded(values: PackedFloat32Array, step_v: float) -> Array:
	var out: Array = []
	for v: float in values:
		out.append(snappedf(v, step_v))
	return out


func _region_summary(cell: String) -> String:
	var parts: PackedStringArray = []
	for tw: Dictionary in towns:
		if str(tw["cell"]) == cell:
			parts.append("the %s of %s" % [tw["kind"], tw["name"]])
	var n_places: int = 0
	for pl: Dictionary in places:
		if str(pl["cell"]) == cell:
			n_places += 1
	if n_places > 0:
		parts.append("%d place%s off the roads" % [n_places, "" if n_places == 1 else "s"])
	for pt: Dictionary in posts:
		if str(pt["cell"]) == cell:
			parts.append("a trader post")
	if str(drop.get("cell", "")) == cell:
		parts.append("the drop site")
	return ("%s, %s." % [str(regions[cell]["biome"]).replace("_", " ").capitalize(), ", ".join(parts)]) if not parts.is_empty() else "%s." % str(regions[cell]["biome"]).replace("_", " ").capitalize()


## A region's features: its places, the paths crossing it, the drop site and the Bloom. Towns are
## world-level (world.json `towns`), not region features, since VERSION 2.
func region_json(cell: String) -> Dictionary:
	var rg: Dictionary = regions[cell]
	var rect: Rect2 = rg["rect"]
	var feats: Array = []
	var rough: float = settings.num("roughness")
	for pl: Dictionary in places:
		if str(pl["cell"]) != cell:
			continue
		var f: Dictionary = {"type": pl["kind"], "id": pl["id"], "origin": Terrain._arr(PackedVector2Array([pl["origin"]]))[0], "rotation": pl["rot"],
			"biome": pl["biome"], "skirt": pl["skirt"]}
		f[pl["kind"]] = pl["def"]
		# A mine's pad is its surface part; its footprint runs on under the hill (ADR-0044).
		if (pl.get("pad", Vector2.ZERO) as Vector2) != Vector2.ZERO:
			f["size"] = [pl["pad"].x, pl["pad"].y]
		if bool(pl["keep_water"]):
			f["keep_water"] = true
			f["freeboard"] = 0.6
		feats.append(f)
	# Paths are painted per region: a trail crossing a border is listed in both, each painting its side.
	for pt: Dictionary in paths:
		var line_pts: PackedVector2Array = pt["points"]
		var bb := Rect2(line_pts[0], Vector2.ZERO)
		for p: Vector2 in line_pts:
			bb = bb.expand(p)
		if bb.grow(8.0).intersects(rect):
			feats.append({"type": "path", "id": pt["id"], "surface": pt["surface"], "width": pt["width"], "points": Terrain._arr(line_pts)})
	if str(drop.get("cell", "")) == cell:
		var dp: Array = Terrain._arr(PackedVector2Array([drop["pos"]]))[0]
		feats.append({"type": "clearing", "pos": dp, "radius": 16})
		feats.append({"type": "spawn", "id": "drop_site", "pos": dp, "yaw": drop["yaw"],
			"props": [{"prop": "supply_canister", "offset": [2.0, 0.0, 1.0], "rot": 30}]})
	for pt: Dictionary in posts:
		if str(pt["cell"]) == cell:
			var pp: Array = Terrain._arr(PackedVector2Array([pt["pos"]]))[0]
			feats.append({"type": "clearing", "pos": pp, "radius": 24})
			feats.append({"type": "spawn", "id": pt["id"], "pos": pp, "yaw": pt["yaw"]})
	for bl: Dictionary in blooms:
		if str(bl["cell"]) == cell:
			feats.append({"type": "bloom", "id": bl["id"], "at": Terrain._arr(PackedVector2Array([bl["at"]]))[0], "radius": bl["radius"],
				"strength": bl["strength"], "edge": bl["edge"]})
	for cv: Dictionary in caves:
		if str(cv["cell"]) == cell:
			feats.append({"type": "cave", "id": cv["id"], "style": cv["style"], "mouth": Terrain._arr(PackedVector2Array([cv["mouth"]]))[0],
				"heading": "uphill", "search": float((tun.get("caves", {}) as Dictionary).get("search", 12.0))})
	# The fen's pools, and the splat layers burnt forest and fen need (ADR-0041).
	feats.append_array(fen_pools(cell))
	var out: Dictionary = {
		"_doc": "Generated region (ADR-0031) of %s; regenerated from its world's seed and settings, never edited." % world_id,
		"id": rg["id"], "cell": cell, "name": rg["name"], "default_biome": rg["biome"],
		"detail_noise": {"layers": [{"frequency": 0.012, "octaves": 4, "amplitude": 2.5}, {"frequency": 0.03, "octaves": 3, "amplitude": snappedf(0.5 + 0.9 * rough, 0.01)},
			{"frequency": 0.075, "octaves": 2, "amplitude": 0.3}]},
		"features": feats,
	}
	var pal: PackedStringArray = region_palette(cell)
	if not pal.is_empty():
		out["palette"] = Array(pal)
	return out


## The towns as frameworks (FrameworkDef, `layout: "organic"`, ADR-0040): the planner's framework
## keys (RwgTownPlanner.to_framework), the tier range by danger, and the authored buildings this
## town may hold.
func frameworks_json() -> Dictionary:
	var defs: Array = []
	for tw: Dictionary in towns:
		var fw: Dictionary = Planner.to_framework(tw["plan"], tw["fw_id"], tw["name"])
		fw["tier_range"] = tw["tier"]
		fw["authored"] = Array(tw["authored"])
		defs.append(fw)
	return {"_doc": "Generated towns of %s (ADR-0031, ADR-0040): organic frameworks whose frame lots pick or generate their buildings (ADR-0030)." % world_id, "defs": defs}


## Region ids by cell (after run()).
func region_ids() -> Dictionary:
	var out: Dictionary = {}
	for cell: String in regions:
		out[cell] = regions[cell]["id"]
	return out
