extends GutTest
## Random worlds (ADR-0031; generator v2 with organic towns, ADR-0040): settings, determinism, what
## the generator promises about its output (town counts by density, no overlaps, connected towns,
## rivers that run downhill, a safe drop site away from region borders), its time budget (sizes 5
## and 10), and that its output loads and composes like any world. test_world_towns.gd covers the
## towns themselves (seams, lot heights, buildings, the v1 world fixture).

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")
const Streets := preload("res://src/worldgen/rwg/rwg_streets.gd")

## Generation budget for a 5 x 5 world (ADR-0031): measured ~1 s headless on one core (v1), ~3 s
## with organic towns (v2).
const BUDGET_5X5_MS: int = 10000
## A 10 x 10 world (size forced past the New Game cap, as rwg_preview --force-size measures it):
## ~10 s headless on the busy shared container (v2; the plan's budget for 16 x 16 is 20 s).
const BUDGET_10X10_MS: int = 40000
const TMP: String = "user://test_rwg"


func _settings(seed: int, overrides: Dictionary = {}, preset: String = "standard") -> RefCounted:
	return GenSettings.resolve(StringName(preset), overrides, seed)


func _gen(seed: int, overrides: Dictionary = {}, preset: String = "standard") -> RefCounted:
	return Generator.generate(_settings(seed, overrides, preset))


func _all_json(g: RefCounted) -> String:
	var wj: Dictionary = g.call(&"world_json")
	# Timings differ between runs; everything else must not.
	(wj["generator"] as Dictionary).erase("timings_ms")
	var parts: PackedStringArray = [JSON.stringify(wj, "", false), JSON.stringify(g.call(&"frameworks_json"), "", false)]
	var ids: Dictionary = g.call(&"region_ids")
	for cell: Variant in ids:
		parts.append(JSON.stringify(g.call(&"region_json", str(cell)), "", false))
	return "\n".join(parts)


func after_all() -> void:
	Worlds._remove(TMP)


# --- Settings --------------------------------------------------------------------------------

func test_config_is_valid() -> void:
	assert_eq(GenSettings.schema_errors(Content), PackedStringArray(), "world_gen.json has no schema errors")


func test_settings_resolve_clamp_and_round_trip() -> void:
	var s: RefCounted = _settings(42, {"size": 99, "terrain": "volcanic", "town_density": "2.5"}, "highlands")
	var v: Dictionary = s.get(&"values")
	assert_eq(int(v["size"]), 10, "size clamped to its range (10 since streaming; 16 waits for Bloom tiles)")
	assert_eq(str(v["terrain"]), str(GenSettings.options()["terrain"]["default"]), "an unknown enum value falls back to the option's default")
	assert_eq(float(v["town_density"]), 2.5, "strings from the command line are coerced")
	var back: RefCounted = GenSettings.from_dict(s.call(&"to_dict"))
	assert_eq(str(back.call(&"key")), str(s.call(&"key")), "to_dict/from_dict keeps the world")
	assert_eq(Generator.world_id_for(back), Generator.world_id_for(s))
	assert_ne(Generator.world_id_for(_settings(43)), Generator.world_id_for(_settings(42)), "the seed is part of the id")


# --- Determinism -----------------------------------------------------------------------------

func test_same_seed_same_world_other_seed_other_world() -> void:
	var a: String = _all_json(_gen(1234, {"size": 3}))
	var b: String = _all_json(_gen(1234, {"size": 3}))
	var c: String = _all_json(_gen(1235, {"size": 3}))
	assert_eq(a.md5_text(), b.md5_text(), "same seed and settings give the same world, byte for byte")
	assert_ne(a.md5_text(), c.md5_text(), "another seed gives another world")
	var d: String = _all_json(_gen(1234, {"size": 3, "lakes": "many"}))
	assert_ne(a.md5_text(), d.md5_text(), "the settings shape the world")


# --- What the generator promises --------------------------------------------------------------

func test_town_count_and_size_follow_the_settings() -> void:
	# 3 towns per 16 km² on a 4 x 4 world: three villages (floor(3 + a draw under 1)).
	var g: RefCounted = _gen(77, {"size": 4, "town_density": 3.0, "town_size": "villages"})
	var towns: Array = g.get(&"towns")
	assert_eq(towns.size(), 3, "three towns")
	for t: Dictionary in towns:
		assert_eq(str(t["kind"]), "village")
	var h: RefCounted = _gen(77, {"size": 4, "town_density": 2.0, "town_size": "hamlets"})
	assert_eq((h.get(&"towns") as Array).size(), 2, "two hamlets")
	for t2: Dictionary in h.get(&"towns"):
		assert_eq(str(t2["kind"]), "hamlet")
	var lots_h: int = ((h.get(&"towns") as Array)[0]["plan"]["lots"] as Array).size()
	var lots_v: int = (towns[0]["plan"]["lots"] as Array).size()
	assert_gt(lots_v, lots_h, "a village has more lots than a hamlet")
	assert_eq((_gen(77, {"size": 3, "town_density": 0.0}).get(&"towns") as Array).size(), 0, "no towns when none are asked for")
	assert_eq((_gen(77, {"size": 2, "town_density": 0.25, "town_size": "hamlets"}).get(&"towns") as Array).size(), 1, "any density above zero makes a town")
	var big: RefCounted = _gen(78, {"size": 5, "town_density": 4.0, "town_size": "towns"})
	var nb: int = (big.get(&"towns") as Array).size()
	var no_room: int = 0
	for w: String in big.get(&"warnings"):
		if w.begins_with("no room"):
			no_room += 1
	assert_eq(nb + no_room, 6, "6.25 towns per 5 x 5 world: six sites tried (%d placed, %d without room)" % [nb, no_room])
	assert_gt(nb, 3, "most big towns fit a 5 x 5 world")
	for t3: Dictionary in big.get(&"towns"):
		assert_true(str(t3["kind"]) in ["village", "town"], "the 'towns' mix makes villages and towns")


func test_places_never_overlap_each_other_water_or_roads() -> void:
	for seed: int in [5, 6, 9]:
		var g: RefCounted = _gen(seed, {"size": 4, "wilderness": 1.5})
		var built: Array = []
		for t: Dictionary in g.get(&"towns"):
			for l: Dictionary in t["plan"]["lots"]:
				built.append(["lot %s/%s" % [t["id"], l["id"]], Generator.frame_poly(l["frame"]), false])
		for p: Dictionary in g.get(&"places"):
			built.append(["place %s" % p["id"], p["poly"], bool(p["keep_water"])])
		assert_gt((g.get(&"places") as Array).size(), 5, "seed %d places something" % seed)
		var bad: PackedStringArray = []
		for i: int in built.size():
			var bi: Rect2 = Generator._bounds(built[i][1])
			for j: int in range(i + 1, built.size()):
				if bi.grow(1.0).intersects(Generator._bounds(built[j][1])) and not Geometry2D.intersect_polygons(built[i][1], built[j][1]).is_empty():
					var over: float = 0.0
					for part: PackedVector2Array in Geometry2D.intersect_polygons(built[i][1], built[j][1]):
						over += absf(_area(part))
					if over > 0.5 or str(built[i][0]).begins_with("place") or str(built[j][0]).begins_with("place"):
						bad.append("%s overlaps %s" % [built[i][0], built[j][0]])
			if str(built[i][0]).begins_with("place"):
				if not bool(built[i][2]) and float(g.call(&"water_clearance", built[i][1])) <= 0.0:
					bad.append("%s is in the water" % built[i][0])
				elif bool(built[i][2]) and float(g.call(&"water_clearance", built[i][1])) >= 0.0:
					bad.append("%s does not stand over its lake" % built[i][0])
		# Roads keep off every building; a place's own drive or track ends at its front, so only the
		# through roads are checked against places.
		var roads: Array = g.get(&"roads")
		for k: int in roads.size():
			var cls: String = str(roads[k]["class"])
			for b: Array in built:
				if cls in ["track", "drive"] and str(b[0]).begins_with("place"):
					continue
				var clear: float = _road_gap(roads[k], b[1])
				if clear <= -0.5:
					bad.append("road %s (%s) runs through %s (%.1f m)" % [roads[k]["id"], cls, b[0], clear])
		assert_eq(bad.size(), 0, "seed %d: %d problems: %s" % [seed, bad.size(), "; ".join(bad.slice(0, 8))])


## Clearance between a road's edge (half width + shoulder) and a polygon, over its segments.
static func _road_gap(rd: Dictionary, poly: PackedVector2Array) -> float:
	var line: Polyline2 = rd["line"]
	var need: float = float(rd["width"]) * 0.5 + float(rd["shoulder"])
	if not line.bounds.grow(need + 2.0).intersects(Generator._bounds(poly)):
		return INF
	var best: float = INF
	for k: int in line.points.size() - 1:
		best = minf(best, Generator._seg_poly_distance(line.points[k], line.points[k + 1], poly))
	return best - need


static func _area(poly: PackedVector2Array) -> float:
	var a: float = 0.0
	for i: int in poly.size():
		a += poly[i].cross(poly[(i + 1) % poly.size()])
	return a * 0.5


func test_roads_connect_every_town() -> void:
	for seed: int in [11, 12]:
		var g: RefCounted = _gen(seed, {"size": 5, "town_density": 3.0})
		var towns: Array = g.get(&"towns")
		var roads: Array = g.get(&"roads")
		assert_gt(towns.size(), 1)
		# Roads join where one's end meets another's line; a town is on the road through its centre
		# (its main street, ADR-0040).
		var parent: Array[int] = []
		for i: int in roads.size() + towns.size():
			parent.append(i)
		for a: int in roads.size():
			var pts: PackedVector2Array = roads[a]["points"]
			for end: Vector2 in [pts[0], pts[pts.size() - 1]]:
				for b: int in roads.size():
					if a != b and (roads[b]["line"] as Polyline2).closest(end).x < 14.0:
						_union(parent, a, b)
			for t: int in towns.size():
				if (roads[a]["line"] as Polyline2).closest(towns[t]["center"]).x < 2.0:
					_union(parent, a, roads.size() + t)
		var root: int = _find(parent, roads.size())
		for t2: int in towns.size():
			assert_eq(_find(parent, roads.size() + t2), root, "seed %d: %s is on the road network" % [seed, towns[t2]["name"]])
			var through: int = 0
			for rd: Dictionary in roads:
				var line: Polyline2 = rd["line"]
				var q: Vector3 = line.closest(towns[t2]["center"])
				if q.x < 2.0 and q.y > 20.0 and q.y < line.total_length - 20.0:
					through += 1
			assert_gt(through, 0, "seed %d: a main street runs through %s's centre" % [seed, towns[t2]["name"]])


static func _find(parent: Array[int], i: int) -> int:
	while parent[i] != i:
		i = parent[i]
	return i


static func _union(parent: Array[int], a: int, b: int) -> void:
	parent[_find(parent, a)] = _find(parent, b)


func test_rivers_run_downhill_to_a_mouth() -> void:
	var count: int = 0
	for seed: int in [3, 4, 21]:
		var g: RefCounted = _gen(seed, {"size": 4, "rivers": "many", "terrain": "hilly"})
		var t: RefCounted = g.get(&"terrain")
		for rv: Dictionary in t.get(&"rivers"):
			count += 1
			var lv: PackedFloat32Array = rv["levels"]
			for k: int in range(1, lv.size()):
				assert_true(lv[k] <= lv[k - 1] + 0.001, "seed %d %s falls along its length (%.2f then %.2f)" % [seed, rv["id"], lv[k - 1], lv[k]])
			assert_true(str(rv["mouth"]) in ["edge", "lake", "river"])
			if str(rv["mouth"]) == "lake":
				var last: Vector2 = (rv["control"] as PackedVector2Array)[(rv["control"] as PackedVector2Array).size() - 1]
				assert_lt(float(t.call(&"water_distance", last)), 0.0, "seed %d %s ends in its lake" % [seed, rv["id"]])
			# The land beside the water stands above it (no river on a levee).
			var line: Polyline2 = rv["line"]
			var s: float = 0.0
			while s < line.total_length:
				var p: Vector2 = line.point_at(s)
				# Where a river runs into its lake, the ground under it is the lake bed.
				var in_lake: bool = false
				for lk: Dictionary in t.get(&"lakes"):
					in_lake = in_lake or Streets.point_in(p, lk["polygon"])
				if not in_lake:
					assert_true(float(t.call(&"height", p.x, p.y)) >= line.value_at(Array(lv), s) - 3.5, "seed %d %s: ground at %s stays near or above the water" % [seed, rv["id"], p])
				s += 120.0
	assert_gt(count, 2, "'many' rivers on hilly land makes rivers")


func test_drop_site_is_safe() -> void:
	for seed: int in [31, 32, 33]:
		var g: RefCounted = _gen(seed, {"size": 4})
		var drop: Dictionary = g.get(&"drop")
		assert_false(drop.is_empty(), "seed %d has a drop site" % seed)
		var p: Vector2 = drop["pos"]
		for t: Dictionary in g.get(&"towns"):
			# 380 m from a town's disc, 0.65 of that in the last fallback tier.
			assert_gt((t["center"] as Vector2).distance_to(p) - float(t["radius"]), 240.0, "seed %d: dropped away from %s" % [seed, t["name"]])
			for l: Dictionary in t["plan"]["lots"]:
				assert_gt(Terrain._poly_distance(Generator.frame_poly(l["frame"]), p), 100.0, "seed %d: dropped away from %s's farms" % [seed, t["name"]])
		# A streamed world shapes the land round the drop site first: 300 m from a region border.
		var rect: Rect2 = (g.get(&"regions") as Dictionary)[str(drop["cell"])]["rect"]
		var border: float = minf(minf(p.x - rect.position.x, rect.end.x - p.x), minf(p.y - rect.position.y, rect.end.y - p.y))
		var fell_back: bool = false
		for w: String in g.get(&"warnings"):
			fell_back = fell_back or w.begins_with("drop site")
		if not fell_back:
			assert_gt(border, 300.0 - 24.0, "seed %d: the drop site is %.0f m from a region border" % [seed, border])
		assert_gt(float((g.get(&"terrain") as RefCounted).call(&"water_distance", p)), 30.0, "seed %d: dropped on dry ground" % seed)
		var near: Array = g.call(&"nearest_road", p)
		assert_lt(float(near[0]), 400.0, "seed %d: a road within reach" % seed)


func test_generation_time_5x5() -> void:
	var t0: int = Time.get_ticks_msec()
	var g: RefCounted = _gen(2026, {"size": 5})
	var ms: int = Time.get_ticks_msec() - t0
	gut.p("5 x 5 world generated in %d ms: %s" % [ms, g.get(&"timings")])
	assert_lt(ms, BUDGET_5X5_MS, "a 5 x 5 world generates within the budget")


## Phase 4's sizes: a 10 x 10 world (the size forced past the New Game cap in memory, as
## rwg_preview --force-size does) generates, deterministically, with towns and places in
## proportion, cell names past G and two-digit rows. 16 x 16 runs with SLOW_TESTS=1.
func test_generation_scales_to_10x10() -> void:
	var sizes: Array[int] = [10]
	if OS.get_environment("SLOW_TESTS") == "1":
		sizes.append(16)
	for sz: int in sizes:
		var s: RefCounted = _settings(1010)
		(s.get(&"values") as Dictionary)["size"] = sz
		var t0: int = Time.get_ticks_msec()
		var g: RefCounted = Generator.generate(s)
		var ms: int = Time.get_ticks_msec() - t0
		gut.p("%d x %d world generated in %d ms: %s; %s" % [sz, sz, ms, g.get(&"timings"), g.get(&"sub_timings")])
		var towns: int = (g.get(&"towns") as Array).size()
		var places: int = (g.get(&"places") as Array).size()
		assert_gt(towns, int(sz * sz / 16.0 * 2.0 * 0.6), "%d x %d: towns by density (%d)" % [sz, sz, towns])
		assert_gt(places, sz * sz / 4, "%d x %d: places by the per-16 km² caps (%d)" % [sz, sz, places])
		# Named places repeat with the area, but a `unique` one (the field lab) stands once at most.
		var labs: int = (g.get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["def"]) == "corvane_field_lab").size()
		assert_lte(labs, 1, "%d x %d: the field lab is unique (%d)" % [sz, sz, labs])
		assert_eq(labs, 1, "%d x %d: and a world this big has one" % [sz, sz])
		var adits: int = (g.get(&"places") as Array).filter(func(p: Dictionary) -> bool: return str(p["site"]) == "mine").size()
		assert_eq(adits, 1, "%d x %d: one Corvane adit, dug into a hillside (TD-169)" % [sz, sz])
		var ids: Dictionary = g.call(&"region_ids")
		assert_eq(ids.size(), sz * sz)
		assert_true(ids.has("%s%d" % [char(64 + sz), sz]), "the last cell is %s%d" % [char(64 + sz), sz])
		if sz == 10:
			assert_lt(ms, BUDGET_10X10_MS, "a 10 x 10 world generates within the budget")
			var again: RefCounted = Generator.generate(s)
			assert_eq(_all_json(again).md5_text(), _all_json(g).md5_text(), "the same 10 x 10 world twice, byte for byte (towns planned on threads)")


# --- It loads like any world ---------------------------------------------------------------------

func test_output_loads_composes_and_registers_its_towns() -> void:
	var g: RefCounted = _gen(4040, {"size": 2, "town_density": 4.0, "town_size": "hamlets"})
	var dir: String = TMP.path_join(str(g.get(&"world_id")))
	assert_eq(Worlds.write(g, dir), OK)
	assert_true(FileAccess.file_exists(dir.path_join("map.png")), "the map is drawn")
	assert_eq(Worlds.register_frameworks(dir), PackedStringArray(), "its towns parse and validate as frameworks")
	var world: WorldDef = WorldDef.load_from(dir)
	assert_eq(world.cols, 2)
	assert_eq(world.road_grade, "world")
	assert_true(world.has_biome_map())
	var t: RefCounted = g.get(&"terrain")
	var hs: PackedFloat32Array = t.get(&"h")
	var n: int = t.get(&"n")
	assert_almost_eq(world.macro_height(float(t.get(&"x0")) + 5 * 32.0, float(t.get(&"z0")) + 7 * 32.0), float(snappedf(hs[7 * n + 5], 0.1)), 0.11, "the macro grid is the generator's land")
	var towns: Array = g.get(&"towns")
	assert_eq(towns.size(), 1)
	assert_eq(world.towns.size(), 1, "the town is a world-level town (ADR-0040)")
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(towns[0]["fw_id"]))) as FrameworkDef
	assert_not_null(fw, "the town is a registered framework")
	assert_eq(fw.layout, "organic")
	# Every lot holds a building (authored or generated), none is left empty.
	for res: Dictionary in Lots.resolve(fw, str(towns[0]["id"]), 99):
		assert_true(str(res["kind"]) in ["authored", "generated"], "lot %s holds a building (%s)" % [res["lot"]["id"], res["kind"]])
	# The town's region composes (coarsely, for speed) with the town's lots and streets.
	var rid: String = str(world.cells[str(towns[0]["cell"])])
	var rt: RegionTerrain = TerrainComposer.compose(world, rid, 8.0)
	assert_not_null(rt)
	var kinds: Array = []
	for pl: Dictionary in rt.placements:
		kinds.append(str(pl["kind"]))
	assert_has(kinds, "town", "the town's fixtures are placed")
	assert_has(kinds, "lot", "its lots are placed")
	assert_true(rt.biome_ids.has("yard"), "its lots are yards")
	assert_gt(rt.roads.size(), 1, "its streets and roads are graded")
	for r2: Variant in world.regions:
		for f: Variant in world.region_data(str(r2)).get("features", []):
			assert_ne(str((f as Dictionary).get("framework", "")), String(fw.id), "no region lists the town as a feature")
	# Leave content as it was for the tests after this one.
	Content.remove_runtime_def(&"framework", fw.id)


func test_saves_record_the_world() -> void:
	var gen: Dictionary = _settings(555, {"size": 3}).call(&"to_dict")
	var s: GameSession = GameSession.create_new({"world_gen": gen, "seed": 9})
	assert_true(s.is_random_world())
	assert_eq(String(s.world_mode), "random")
	assert_true(String(s.world_id).begins_with("rwg_"))
	var back: GameSession = GameSession.from_dict(s.to_dict())
	assert_eq(back.world_gen, s.world_gen, "the settings survive a save")
	assert_eq(back.world_id, s.world_id)
	assert_eq(back.world_seed, 9, "the run seed stays the run's")
	var main: GameSession = GameSession.create_new({})
	assert_false(main.is_random_world(), "a new game is on the main map by default")
	var old: Dictionary = SaveSystem.migrate({"save_version": 5, "session": {"world_mode": "main_map"}})
	assert_eq(old["session"]["world_gen"], {}, "a v5 save is on the main map")


# --- The New Game screen ---------------------------------------------------------------------------

func test_new_game_world_tab_generates_a_preview() -> void:
	var panel := NewGamePanel.new()
	panel.start_random = true
	add_child_autofree(panel)
	await get_tree().process_frame
	assert_eq(panel._tabs.current_tab, 1, "the Random World button opens the World tab")
	assert_eq(panel._map.selected, 1, "with a random world chosen")
	(panel._wcontrols["size"] as SpinBox).value = 2
	(panel._wcontrols["town_density"] as SpinBox).value = 4.0
	panel._wseed.text = "8080"
	var settings: RefCounted = panel.world_settings()
	assert_eq(int((settings.get(&"values") as Dictionary)["size"]), 2, "the controls set the world's settings")
	assert_eq(int(settings.get(&"seed")), 8080, "and its map seed")
	panel._generate_preview()
	var t0: int = Time.get_ticks_msec()
	while panel._task >= 0 and Time.get_ticks_msec() - t0 < 120000:
		await get_tree().process_frame
	assert_not_null(panel._preview.texture, "the map preview is shown")
	assert_string_contains(panel._preview_status.text, "Towns:", "with a summary of the world")
	Worlds._remove(Worlds.dir_for(Generator.world_id_for(settings)))
