extends GutTest
## Random worlds' `mine` site (TD-169, ADR-0044; generator v6): the Corvane Larkspur Adit dug into a
## hillside, once per world. The generator finds a slope near a road in a danger-3+ region, turns
## the plan so its buried levels run uphill under the ground, levels only the surface pad (the
## region feature's `size`) and brings a track along the contour to the hoist-house door. Composed,
## the ground stands over every buried ceiling beyond the pad (TD-164): flush at the pad's edge,
## where a drift comes out of the hill, and well over it further in.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")

const TMP: String = "user://test_rwg_mine"
const ADIT: String = "corvane_larkspur_adit"
## The adit's surface pad (world_gen.json pool entry `pad`).
const PAD := Vector2(24, 14)


func after_all() -> void:
	Worlds._remove(TMP)


func _gen(seed: int, size: int = 4) -> RefCounted:
	return Generator.generate(GenSettings.resolve(&"standard", {"size": size}, seed))


func _mines(g: RefCounted) -> Array:
	return (g.get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["site"]) == "mine")


## Every buried-level cell no ground-floor room covers: [local centre, ceiling above the origin].
static func _buried_cells() -> Array:
	var layout: PoiLayout = PoiLayout.compile(Content.get_def(&"poi", StringName(ADIT)) as PoiDef)
	var covered: Dictionary = {}
	for c0: Vector2i in layout.room_cells(0):
		covered[c0] = true
	var out: Array = []
	for li: int in layout.level_ids:
		if li >= 0 or not bool((layout.levels[li] as Dictionary).get("buried", false)):
			continue
		for c: Vector2i in layout.room_cells(li):
			if not covered.has(c):
				out.append([layout.origin + Vector2(c) + Vector2(0.5, 0.5), layout.level_y(li) + PoiLayout.STOREY - TerrainHoles.SLAB])
	return out


static func _pad_distance(lp: Vector2) -> float:
	return Vector2(maxf(maxf(-lp.x, lp.x - PAD.x), 0.0), maxf(maxf(-lp.y, lp.y - PAD.y), 0.0)).length()


func test_config_has_one_unique_mine_entry() -> void:
	assert_eq(GenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json is valid with the mine site")
	var mines: Array = (((GenSettings.tuning().get("wilderness", {}) as Dictionary).get("pool", []) as Array)
		.filter(func(e: Dictionary) -> bool: return str(e.get("site", "")) == "mine"))
	assert_eq(mines.size(), 1, "one mine entry")
	if mines.size() == 1:
		assert_eq(str(mines[0]["poi"]), ADIT)
		assert_true(bool(mines[0].get("unique", false)), "the adit is the story's one adit: unique")
		assert_eq(int(mines[0]["min_danger"]), 3, "tier 3, danger 3 and up")
		assert_eq(Vector2(float(mines[0]["pad"][0]), float(mines[0]["pad"][1])), PAD)


func test_the_adit_is_dug_into_a_slope_in_most_worlds() -> void:
	var placed: int = 0
	var seeds: Array[int] = [1, 2, 3, 4, 5, 6]
	for seed: int in seeds:
		var g: RefCounted = _gen(seed)
		var mines: Array = _mines(g)
		assert_lte(mines.size(), 1, "seed %d: one adit at most" % seed)
		if mines.is_empty():
			continue
		placed += 1
		var m: Dictionary = mines[0]
		assert_eq(str(m["def"]), ADIT)
		var regions: Dictionary = g.get(&"regions")
		assert_gte(int(regions[m["cell"]]["danger"]), 3, "seed %d: in a danger-3+ region" % seed)
		# Uphill along local +X: the ground over the far end of the levels stands well over the pad.
		var t: RefCounted = g.get(&"terrain")
		var a: float = deg_to_rad(float(m["rot"]))
		var o: Vector2 = m["origin"]
		var pad_mid: Vector2 = o + (PAD * 0.5).rotated(a)
		var far: Vector2 = o + Vector2(62.0, 7.0).rotated(a)
		var rise: float = float(t.call(&"height", far.x, far.y)) - float(t.call(&"height", pad_mid.x, pad_mid.y))
		assert_gt(rise, 6.0, "seed %d: the levels run into a hillside (%.1f m up)" % [seed, rise])
		# The region feature levels only the surface pad.
		var feat: Dictionary = {}
		for f: Dictionary in (g.call(&"region_json", str(m["cell"])) as Dictionary)["features"]:
			if str(f.get("id", "")) == str(m["id"]):
				feat = f
		assert_eq(feat.get("size", []), [PAD.x, PAD.y], "seed %d: the feature's size is the pad" % seed)
		# A track (or, where it would cut over the levels, a footpath) ends at the door.
		var door: Vector2 = m["access"]
		var reached: bool = false
		for rd: Dictionary in g.get(&"roads"):
			var pts: PackedVector2Array = rd["points"]
			if str(rd["name"]).begins_with(ADIT) and pts[pts.size() - 1].distance_to(door) < 0.5:
				reached = true
		for pt: Dictionary in g.get(&"paths"):
			var pts2: PackedVector2Array = pt["points"]
			if str(pt["id"]) == "%s_trail" % m["id"] and pts2[pts2.size() - 1].distance_to(door) < 0.5:
				reached = true
		assert_true(reached, "seed %d: a way in reaches the door" % seed)
	assert_gte(placed, 5, "the adit is placed in %d of %d default 4 x 4 worlds" % [placed, seeds.size()])


func test_buried_levels_stay_under_the_composed_ground() -> void:
	var cells: Array = _buried_cells()
	assert_gt(cells.size(), 300, "the adit's buried cells beyond its ground floor")
	for seed: int in [2, 3]:
		var g: RefCounted = _gen(seed)
		var mines: Array = _mines(g)
		assert_eq(mines.size(), 1, "seed %d places the adit" % seed)
		if mines.is_empty():
			continue
		var m: Dictionary = mines[0]
		var dir: String = TMP.path_join(str(g.get(&"world_id")))
		assert_eq(Worlds.write(g, dir), OK)
		Worlds.register_frameworks(dir)
		var world: WorldDef = WorldDef.load_from(dir)
		var rt: RegionTerrain = TerrainComposer.compose(world, str(world.cells[str(m["cell"])]), 4.0)
		for tw: Dictionary in g.get(&"towns"):
			Content.remove_runtime_def(&"framework", StringName(str(tw["fw_id"])))
		assert_not_null(rt)
		if rt == null:
			continue
		var pl: Dictionary = {}
		for p: Dictionary in rt.placements:
			if str(p.get("id", "")) == str(m["id"]):
				pl = p
		assert_false(pl.is_empty(), "seed %d: the adit is placed in its region" % seed)
		if pl.is_empty():
			continue
		assert_eq(pl["size"], [PAD.x, PAD.y])
		var o := Vector2(float(pl["origin"][0]), float(pl["origin"][2]))
		var pad_y: float = float(pl["origin"][1])
		var a: float = deg_to_rad(float(pl["rotation"]))
		var bad: PackedStringArray = []
		var near_min: float = INF
		var deep_min: float = INF
		for c: Array in cells:
			var lp: Vector2 = c[0]
			var d: float = _pad_distance(lp)
			if d <= 0.0:
				continue
			var wp: Vector2 = o + lp.rotated(a)
			var over: float = rt.height.sample(wp.x, wp.y) - (pad_y + float(c[1]))
			if d >= 16.0:
				deep_min = minf(deep_min, over)
				if over < 1.5:
					bad.append("cell %s: %.2f m of ground over its ceiling" % [lp, over])
			else:
				near_min = minf(near_min, over)
				if over < -0.05:
					bad.append("cell %s (%.1f m from the pad): its ceiling is %.2f m out of the ground" % [lp, d, -over])
		gut.p("seed %d: least ground over a ceiling %.2f m near the pad, %.2f m 16 m in" % [seed, near_min, deep_min])
		assert_eq(bad.size(), 0, "seed %d: %d buried cells break the surface: %s" % [seed, bad.size(), "; ".join(bad.slice(0, 6))])
