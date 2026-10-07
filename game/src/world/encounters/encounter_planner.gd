class_name EncounterPlanner
extends RefCounted
## Where a region's forest encounters stand (ADR-0054): pure data from the world seed, the
## region's composed terrain (biome map, vegetation mask, heights, roads, water, placements) and
## data/encounters + data/config/encounters.json. No scene tree: safe on a worker thread (content
## through ContentDB.instance), and the same inputs give the same sites in the same order.
##
## The world is cut into `cell` m squares (a global grid, so a site's id names its cell and stays
## the same whichever region or world size reads it); a cell belongs to the region holding its
## centre. Each cell rolls once against `per_km2` x the `encounter_density` world setting x its
## area; a cell that rolls tries up to `tries` spots (its own random stream: one cell's result never
## moves another's) until one passes: the spot's biome weight (config `biomes`) as a second roll,
## the vegetation mask (no roads, water, pads or clearings), then a def drawn by weight at that
## biome and that def's slope, road band, building, water and spawn distances, its region cap and
## the spacing from the sites already planned. So the density is `per_km2` per km² of land with
## biome weight 1 (forest), less on thinner ground, none in towns and yards.

## Defaults for data/config/encounters.json keys.
const DEFAULTS: Dictionary = {"per_km2": 10.0, "cell": 128.0, "tries": 8, "inset": 16.0, "edge": 24.0, "spacing": 90.0,
	"min_veg": 0.35, "spawn_clear": 80.0, "biomes": {}}
## Side of the lookup grid for road and water segments (m).
const INDEX_CELL: float = 32.0


## The sites of region `rt` (any spacing; 1 m for play): [{id, kind, def, pos: Vector3, yaw, region,
## seed, trunk (anchor trees: the trunk's radius, else 0)}], in cell order. `density` is the
## encounter_density world setting (0 = none). `height_fn(x, z)` answers the ground (default: the
## region's own heights). `defs`: EncounterDefs to draw from (default: every one loaded).
static func plan_region(rt: RegionTerrain, world_seed: int, density: float, cfg: Dictionary = {}, height_fn: Callable = Callable(),
		defs: Array = []) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if rt == null or density <= 0.0:
		return out
	var c: Dictionary = DEFAULTS.duplicate()
	c.merge(cfg, true)
	if defs.is_empty() and ContentDB.instance != null:
		defs = ContentDB.instance.call(&"all", &"encounter")
	if defs.is_empty():
		return out
	if not height_fn.is_valid():
		height_fn = rt.height.sample
	var ctx := _Ctx.new(rt, c, height_fn, world_seed)
	var cell: float = float(c["cell"])
	var chance: float = clampf(float(c["per_km2"]) * density * cell * cell / 1.0e6, 0.0, 1.0)
	var tries: int = int(c["tries"])
	var inset: float = float(c["inset"])
	var biome_w: Dictionary = c["biomes"]
	var counts: Dictionary = {}
	var cx0: int = floori(rt.rect.position.x / cell)
	var cz0: int = floori(rt.rect.position.y / cell)
	var cx1: int = floori(rt.rect.end.x / cell)
	var cz1: int = floori(rt.rect.end.y / cell)
	for cz: int in range(cz0, cz1 + 1):
		for cx: int in range(cx0, cx1 + 1):
			var centre := Vector2((cx + 0.5) * cell, (cz + 0.5) * cell)
			if not rt.rect.has_point(centre):
				continue
			var key: String = "%d_%d" % [cx, cz]
			var rng := RandomNumberGenerator.new()
			rng.seed = Ids.derive_seed(world_seed, "enc:" + key)
			if rng.randf() >= chance:
				continue
			for t: int in tries:
				# The same draws every try, whatever passes (stable streams).
				var jx: float = rng.randf()
				var jz: float = rng.randf()
				var r_biome: float = rng.randf()
				var r_def: float = rng.randf()
				var r_yaw: float = rng.randf()
				var r_band: float = rng.randf()
				var r_seed: int = rng.randi()
				var p := Vector2(cx * cell + inset + jx * (cell - 2.0 * inset), cz * cell + inset + jz * (cell - 2.0 * inset))
				var site: Dictionary = ctx.try_spot(p, r_biome, r_def, r_yaw, r_band, defs, biome_w, counts, out)
				if site.is_empty():
					continue
				site["id"] = StringName("enc:" + key)
				site["region"] = StringName(rt.region_id)
				site["seed"] = Ids.derive_seed(world_seed, "enc_site:%s:%d" % [key, r_seed])
				counts[site["def"]] = int(counts.get(site["def"], 0)) + 1
				out.append(site)
				break
	return out


## The keys handed to a registered kind's on_place (Encounters.register_kind): the site without
## the planner's extras.
static func public_site(site: Dictionary) -> Dictionary:
	return {"id": site["id"], "kind": site["kind"], "def": site["def"], "pos": site["pos"], "yaw": site["yaw"],
		"region": site["region"], "seed": site["seed"]}


## Per-region lookups, built once per plan.
class _Ctx:
	extends RefCounted
	var rt: RegionTerrain
	var cfg: Dictionary
	var height_fn: Callable
	var world_seed: int
	var inner: Rect2
	## Vector2i -> [[ax, az, bx, bz, half_width, surface], ...]
	var roads: Dictionary = {}
	var water: Dictionary = {}
	var lakes: Array[PackedVector2Array] = []
	## [[centre: Vector2, half: Vector2, yaw]]
	var boxes: Array = []
	var spawns: Array[Vector2] = []
	## Chunk -> tree layer of the vegetation scatter ([[x, z, trunk r]]), for anchored sites.
	var _trees: Dictionary = {}

	func _init(p_rt: RegionTerrain, p_cfg: Dictionary, p_height: Callable, p_seed: int) -> void:
		rt = p_rt
		cfg = p_cfg
		height_fn = p_height
		world_seed = p_seed
		inner = rt.rect.grow(-float(cfg["edge"]))
		for r: Dictionary in rt.roads:
			var pts: Array = r.get("points", [])
			var hw: float = float(r.get("width", 6.0)) * 0.5
			for i: int in range(1, pts.size()):
				_index(roads, Vector2(float(pts[i - 1][0]), float(pts[i - 1][2])), Vector2(float(pts[i][0]), float(pts[i][2])), hw, str(r.get("surface", "")))
		for w: Dictionary in rt.water:
			if w.has("polygon"):
				var poly := PackedVector2Array()
				for q: Variant in w["polygon"]:
					poly.append(Vector2(float(q[0]), float(q[1])))
				lakes.append(poly)
				for i2: int in poly.size():
					_index(water, poly[i2], poly[(i2 + 1) % poly.size()], 0.0, "lake")
			elif w.has("points"):
				var wp: Array = w["points"]
				var widths: Array = w.get("widths", [])
				for i3: int in range(1, wp.size()):
					var hw2: float = float(widths[i3]) * 0.5 if i3 < widths.size() else 4.0
					_index(water, Vector2(float(wp[i3 - 1][0]), float(wp[i3 - 1][1])), Vector2(float(wp[i3][0]), float(wp[i3][1])), hw2, "river")
		for pl: Dictionary in rt.placements:
			var k: String = str(pl.get("kind", ""))
			if k == "town" or not pl.has("size"):
				continue
			var size := Vector2(float(pl["size"][0]), float(pl["size"][1]))
			var o: Array = pl["origin"]
			var yaw: float = -deg_to_rad(float(pl.get("rotation", 0.0)))
			var centre := Vector2(float(o[0]), float(o[2]))
			if k != "lot":
				# Pads and frameworks: origin at a corner, turned about it (PoiRegistry.placement_xf).
				centre += (size * 0.5).rotated(-yaw)
			boxes.append([centre, size * 0.5, yaw])
		for sp: Variant in rt.spawns.values():
			var a: Array = (sp as Dictionary).get("pos", [0, 0, 0])
			spawns.append(Vector2(float(a[0]), float(a[2])))

	func _index(grid: Dictionary, a: Vector2, b: Vector2, hw: float, tag: String) -> void:
		var lo: Vector2 = a.min(b) - Vector2(hw, hw)
		var hi: Vector2 = a.max(b) + Vector2(hw, hw)
		for gz: int in range(floori(lo.y / INDEX_CELL), floori(hi.y / INDEX_CELL) + 1):
			for gx: int in range(floori(lo.x / INDEX_CELL), floori(hi.x / INDEX_CELL) + 1):
				var k := Vector2i(gx, gz)
				if not grid.has(k):
					grid[k] = []
				(grid[k] as Array).append([a.x, a.y, b.x, b.y, hw, tag])

	## Distance from p to the nearest segment edge within `reach` (INF beyond), and its closest point
	## and direction: [distance, Vector2 point, Vector2 dir, half width].
	func nearest(grid: Dictionary, p: Vector2, reach: float, surfaces: PackedStringArray = []) -> Array:
		var best: Array = [INF, p, Vector2.RIGHT, 0.0]
		for gz: int in range(floori((p.y - reach) / INDEX_CELL), floori((p.y + reach) / INDEX_CELL) + 1):
			for gx: int in range(floori((p.x - reach) / INDEX_CELL), floori((p.x + reach) / INDEX_CELL) + 1):
				for s: Array in grid.get(Vector2i(gx, gz), []):
					if not surfaces.is_empty() and not surfaces.has(str(s[5])):
						continue
					var a := Vector2(float(s[0]), float(s[1]))
					var b := Vector2(float(s[2]), float(s[3]))
					var q: Vector2 = Geometry2D.get_closest_point_to_segment(p, a, b)
					var d: float = maxf(0.0, p.distance_to(q) - float(s[4]))
					if d < float(best[0]):
						best = [d, q, (b - a).normalized() if b != a else Vector2.RIGHT, float(s[4])]
		return best

	func water_distance(p: Vector2, reach: float) -> float:
		for poly: PackedVector2Array in lakes:
			if Geometry2D.is_point_in_polygon(p, poly):
				return 0.0
		return float(nearest(water, p, reach)[0])

	func building_distance(p: Vector2) -> float:
		var best: float = INF
		for b: Array in boxes:
			var local: Vector2 = (p - (b[0] as Vector2)).rotated(float(b[2]))
			var half: Vector2 = b[1]
			var q := Vector2(maxf(absf(local.x) - half.x, 0.0), maxf(absf(local.y) - half.y, 0.0))
			best = minf(best, q.length())
		return best

	## Steepest ground over a disc of `r` m (degrees): eight rim samples against the centre.
	func slope_over(p: Vector2, r: float) -> float:
		var h0: float = float(height_fn.call(p.x, p.y))
		var worst: float = 0.0
		var rr: float = maxf(r, 1.5)
		for i: int in 8:
			var a: float = TAU * float(i) / 8.0
			var h: float = float(height_fn.call(p.x + cos(a) * rr, p.y + sin(a) * rr))
			worst = maxf(worst, absf(h - h0) / rr)
		return rad_to_deg(atan(worst))

	## True when the vegetation mask allows growth over the disc (no road, water, pad or clearing).
	func veg_ok(p: Vector2, r: float, min_veg: float) -> bool:
		if rt.veg_at(p.x, p.y) < min_veg:
			return false
		for i: int in 8:
			var a: float = TAU * float(i) / 8.0
			if rt.veg_at(p.x + cos(a) * r, p.y + sin(a) * r) < min_veg * 0.5:
				return false
		return true

	func try_spot(p: Vector2, r_biome: float, r_def: float, r_yaw: float, r_band: float, defs: Array, biome_w: Dictionary,
			counts: Dictionary, placed: Array[Dictionary]) -> Dictionary:
		if not inner.has_point(p):
			return {}
		var biome: String = rt.biome_at(p.x, p.y)
		if r_biome >= float(biome_w.get(biome, 0.0)):
			return {}
		var min_veg: float = float(cfg["min_veg"])
		if rt.veg_at(p.x, p.y) < min_veg:
			return {}
		# The def: drawn by weight at this biome, among those under their region cap (and, for a def
		# that snaps to a road, only with a road within reach of the spot).
		var total: float = 0.0
		var pool: Array = []
		var road_near: int = -1
		for d: EncounterDef in defs:
			var w: float = d.weight_in(biome)
			if w <= 0.0 or (d.max_per_region > 0 and int(counts.get(d.id, 0)) >= d.max_per_region):
				continue
			if d.snap == "road":
				if road_near < 0:
					road_near = 1 if float(nearest(roads, p, float(cfg["cell"]))[0]) < INF else 0
				if road_near == 0:
					continue
			pool.append([d, w])
			total += w
		if pool.is_empty():
			return {}
		var def: EncounterDef = null
		var acc: float = 0.0
		for e: Array in pool:
			acc += float(e[1]) / total
			if r_def <= acc:
				def = e[0]
				break
		if def == null:
			def = pool.back()[0]
		var yaw: float = r_yaw * TAU
		var trunk: float = 0.0
		if def.snap == "road":
			var hit: Array = nearest(roads, p, float(cfg["cell"]), def.road_surfaces)
			if float(hit[0]) == INF:
				return {}
			var dir: Vector2 = hit[2]
			var side: Vector2 = Vector2(-dir.y, dir.x) * (1.0 if r_band < 0.5 else -1.0)
			var off: float = float(hit[3]) + lerpf(def.road.x, def.road.y, fposmod(r_band * 2.0, 1.0))
			p = (hit[1] as Vector2) + side * off
			# Along the road, nosed a little off it (a wreck run into the ditch).
			yaw = -atan2(dir.y, dir.x) + PI * 0.5 + (r_yaw - 0.5) * 0.9 + (PI if r_yaw > 0.5 else 0.0)
			if not inner.has_point(p):
				return {}
		if def.anchor == "tree":
			var tree: Vector3 = _nearest_tree(p, 12.0)
			if tree.z <= 0.0:
				return {}
			p = Vector2(tree.x, tree.y)
			trunk = tree.z
		if not veg_ok(p, def.radius, min_veg if def.snap == "" else 0.0):
			return {}
		if slope_over(p, def.radius) > def.slope_max:
			return {}
		var road_d: float = float(nearest(roads, p, minf(def.road.y, 300.0) + 8.0, def.road_surfaces)[0])
		if road_d < def.road.x or (def.road.y < 1.0e8 and road_d > def.road.y):
			return {}
		# Any road at all keeps clear of the footprint (a stand never straddles a track).
		if def.road_surfaces.size() > 0 and float(nearest(roads, p, def.radius + 1.0)[0]) < minf(def.road.x, def.radius):
			return {}
		if building_distance(p) < def.min_building:
			return {}
		if def.min_water > 0.0 and water_distance(p, def.min_water + 8.0) < def.min_water:
			return {}
		for s: Vector2 in spawns:
			if s.distance_to(p) < float(cfg["spawn_clear"]):
				return {}
		var spacing: float = float(cfg["spacing"])
		for o: Dictionary in placed:
			var op: Vector3 = o["pos"]
			if Vector2(op.x, op.z).distance_to(p) < spacing:
				return {}
		return {"kind": def.ekind, "def": def.id, "pos": Vector3(p.x, float(height_fn.call(p.x, p.y)), p.y), "yaw": wrapf(yaw, -PI, PI),
			"trunk": trunk}

	## The nearest standing tree trunk to p within r (Vector3(x, z, trunk radius); z <= 0: none),
	## from the vegetation scatter's tree layer (the same instances the forest shows).
	func _nearest_tree(p: Vector2, r: float) -> Vector3:
		var best := Vector3(0, 0, 0)
		var best_d: float = r
		var c0 := Vector2i(floori((p.x - r) / VegetationScatter.CHUNK), floori((p.y - r) / VegetationScatter.CHUNK))
		var c1 := Vector2i(floori((p.x + r) / VegetationScatter.CHUNK), floori((p.y + r) / VegetationScatter.CHUNK))
		for cz: int in range(c0.y, c1.y + 1):
			for cx: int in range(c0.x, c1.x + 1):
				for t: Vector3 in _chunk_trees(Vector2i(cx, cz)):
					var d: float = Vector2(t.x, t.y).distance_to(p)
					if d < best_d:
						best_d = d
						best = t
		return best

	func _chunk_trees(key: Vector2i) -> Array:
		if _trees.has(key):
			return _trees[key]
		var out: Array = []
		var db: Node = ContentDB.instance
		var layers: Dictionary = VegetationScatter.scatter_chunk(key, rt, world_seed, height_fn, Callable(), 1)
		for inst: VegetationScatter.Instance in layers.get("tree", []):
			var sp: SpeciesDef = db.call(&"get_def", &"species", inst.species) as SpeciesDef if db != null else null
			if sp == null or not sp.collides:
				continue
			out.append(Vector3(inst.pos.x, inst.pos.z, maxf(0.15, sp.trunk_radius * inst.scale)))
		_trees[key] = out
		return out
