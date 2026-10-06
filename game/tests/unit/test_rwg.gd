extends GutTest
## Random worlds (ADR-0031): settings, determinism, what the generator promises about its output
## (counts, no overlaps, connected towns, rivers that run downhill, a safe drop site), its time
## budget, and that its output loads and composes like any world.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")

## Generation budget for a 5 x 5 world (ADR-0031): measured ~1 s headless on one core.
const BUDGET_5X5_MS: int = 10000
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
	var s: RefCounted = _settings(42, {"size": 99, "terrain": "volcanic", "towns": "5"}, "highlands")
	var v: Dictionary = s.get(&"values")
	assert_eq(int(v["size"]), 7, "size clamped to its range")
	assert_eq(str(v["terrain"]), str(GenSettings.options()["terrain"]["default"]), "an unknown enum value falls back to the option's default")
	assert_eq(int(v["towns"]), 5, "strings from the command line are coerced")
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
	var g: RefCounted = _gen(77, {"size": 4, "towns": 3, "town_size": "villages"})
	var towns: Array = g.get(&"towns")
	assert_eq(towns.size(), 3, "three towns")
	for t: Dictionary in towns:
		assert_eq(str(t["kind"]), "village")
	var h: RefCounted = _gen(77, {"size": 4, "towns": 2, "town_size": "hamlets"})
	for t2: Dictionary in h.get(&"towns"):
		assert_eq(str(t2["kind"]), "hamlet")
	var lots_h: int = ((h.get(&"towns") as Array)[0]["plan"]["lots"] as Array).size()
	var lots_v: int = (towns[0]["plan"]["lots"] as Array).size()
	assert_gt(lots_v, lots_h, "a village has more lots than a hamlet")
	assert_eq((_gen(77, {"size": 3, "towns": 0}).get(&"towns") as Array).size(), 0, "no towns when none are asked for")
	var big: RefCounted = _gen(78, {"size": 5, "towns": 6, "town_size": "towns"})
	assert_eq((big.get(&"towns") as Array).size(), 6, "six towns fit a 5 x 5 world")


func test_places_never_overlap_each_other_water_or_roads() -> void:
	for seed: int in [5, 6, 9]:
		var g: RefCounted = _gen(seed, {"size": 4, "wilderness": 1.5})
		var built: Array = []
		var entries: Array = []
		for t: Dictionary in g.get(&"towns"):
			built.append(["town %s" % t["name"], t["poly"], false])
			entries.append_array(t["entries"])
		for p: Dictionary in g.get(&"places"):
			built.append(["place %s" % p["id"], p["poly"], bool(p["keep_water"])])
		assert_gt((g.get(&"places") as Array).size(), 5, "seed %d places something" % seed)
		for i: int in built.size():
			for j: int in range(i + 1, built.size()):
				assert_true(Geometry2D.intersect_polygons(built[i][1], built[j][1]).is_empty(), "seed %d: %s overlaps %s" % [seed, built[i][0], built[j][0]])
			if not bool(built[i][2]):
				assert_gt(float(g.call(&"water_clearance", built[i][1])), 0.0, "seed %d: %s is clear of the water" % [seed, built[i][0]])
			else:
				assert_lt(float(g.call(&"water_clearance", built[i][1])), 0.0, "seed %d: %s stands over its lake" % [seed, built[i][0]])
		# Roads keep off every building; a place's own drive or track ends at its front, so only the
		# through roads are checked against places.
		var roads: Array = g.get(&"roads")
		for k: int in roads.size():
			var cls: String = str(roads[k]["class"])
			for b: Array in built:
				if cls in ["track", "drive"] and str(b[0]).begins_with("place"):
					continue
				var clear: float = _road_gap(roads[k], b[1], entries)
				assert_gt(clear, -0.5, "seed %d: road %s (%s) runs through %s (%.1f m)" % [seed, roads[k]["id"], cls, b[0], clear])


## Clearance between a road's edge and a polygon; the stretch where a road meets a town's main
## street at its entry (by design, inside the pad edge) is left out.
static func _road_gap(rd: Dictionary, poly: PackedVector2Array, entries: Array) -> float:
	var line: Polyline2 = rd["line"]
	var best: float = INF
	var half: float = float(rd["width"]) * 0.5
	for q: Vector2 in line.points:
		var at_entry: bool = false
		for e: Vector2 in entries:
			if q.distance_to(e) < 20.0:
				at_entry = true
		if at_entry:
			continue
		var d: float = -1.0 if Geometry2D.is_point_in_polygon(q, poly) else Terrain._poly_distance(poly, q)
		best = minf(best, d - half)
	return best


func test_roads_connect_every_town() -> void:
	for seed: int in [11, 12]:
		var g: RefCounted = _gen(seed, {"size": 5, "towns": 5})
		var towns: Array = g.get(&"towns")
		var roads: Array = g.get(&"roads")
		assert_gt(towns.size(), 1)
		# Roads join where one's end meets another's line; a town joins the roads ending at its entries.
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
					for e: Vector2 in towns[t]["entries"]:
						if end.distance_to(e) < 5.0:
							_union(parent, a, roads.size() + t)
		var root: int = _find(parent, roads.size())
		for t2: int in towns.size():
			assert_eq(_find(parent, roads.size() + t2), root, "seed %d: %s is on the road network" % [seed, towns[t2]["name"]])


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
					in_lake = in_lake or Geometry2D.is_point_in_polygon(p, lk["polygon"])
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
			assert_gt(Terrain._poly_distance(t["poly"], p), 300.0, "seed %d: dropped away from %s" % [seed, t["name"]])
		assert_gt(float((g.get(&"terrain") as RefCounted).call(&"water_distance", p)), 30.0, "seed %d: dropped on dry ground" % seed)
		var near: Array = g.call(&"nearest_road", p)
		assert_lt(float(near[0]), 400.0, "seed %d: a road within reach" % seed)


func test_generation_time_5x5() -> void:
	var t0: int = Time.get_ticks_msec()
	var g: RefCounted = _gen(2026, {"size": 5})
	var ms: int = Time.get_ticks_msec() - t0
	gut.p("5 x 5 world generated in %d ms: %s" % [ms, g.get(&"timings")])
	assert_lt(ms, BUDGET_5X5_MS, "a 5 x 5 world generates within the budget")


# --- It loads like any world ---------------------------------------------------------------------

func test_output_loads_composes_and_registers_its_towns() -> void:
	var g: RefCounted = _gen(4040, {"size": 2, "towns": 1, "town_size": "hamlets"})
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
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(towns[0]["fw_id"]))) as FrameworkDef
	assert_not_null(fw, "the town is a registered framework")
	# Every lot holds a building (authored or generated), none is left empty.
	for res: Dictionary in Lots.resolve(fw, str(towns[0]["id"]), 99):
		assert_true(str(res["kind"]) in ["authored", "generated"], "lot %s holds a building (%s)" % [res["lot"]["id"], res["kind"]])
	# The town's region composes (coarsely, for speed) with the town's pad and streets.
	var rid: String = str(world.cells[str(towns[0]["cell"])])
	var rt: RegionTerrain = TerrainComposer.compose(world, rid, 8.0)
	assert_not_null(rt)
	var kinds: Array = []
	for pl: Dictionary in rt.placements:
		kinds.append(str(pl["kind"]))
	assert_has(kinds, "framework", "the town is placed")
	assert_gt(rt.roads.size(), 1, "its streets and roads are graded")
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
	(panel._wcontrols["towns"] as SpinBox).value = 1
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


# --- Town plans --------------------------------------------------------------------------------------

func test_town_plans_keep_lots_off_streets_and_each_other() -> void:
	const Towns := preload("res://src/worldgen/rwg/rwg_towns.gd")
	var cfg: Dictionary = GenSettings.tuning()["towns"]
	var layouts: Dictionary = {}
	for kind: String in ["hamlet", "village", "town"]:
		for seed: int in 24:
			var r := RandomNumberGenerator.new()
			r.seed = seed * 7919 + kind.length()
			var plan: Dictionary = Towns.plan(kind, cfg, r)
			layouts[str(plan["layout"])] = true
			var pad := Rect2(Vector2.ZERO, Vector2(float(plan["size"][0]), float(plan["size"][1])))
			var rects: Array[Rect2] = []
			for l: Dictionary in plan["lots"]:
				var a: Array = l["rect"]
				rects.append(Rect2(float(a[0]), float(a[1]), float(a[2]), float(a[3])))
			for i: int in rects.size():
				assert_true(pad.grow(0.01).encloses(rects[i]), "%s %d: lot %d inside the pad" % [kind, seed, i])
				for j: int in range(i + 1, rects.size()):
					assert_false(rects[i].grow(-0.05).intersects(rects[j].grow(-0.05)), "%s %d: lots %d and %d overlap" % [kind, seed, i, j])
				for rd: Dictionary in plan["roads"]:
					var pts: Array = rd["points"]
					for k: int in pts.size() - 1:
						var street := Rect2(Vector2(float(pts[k][0]), float(pts[k][1])), Vector2.ZERO).expand(Vector2(float(pts[k + 1][0]), float(pts[k + 1][1]))).grow(float(rd["width"]) * 0.5)
						assert_false(street.intersects(rects[i].grow(-0.05)), "%s %d: lot %d stands in a street" % [kind, seed, i])
			# Every lot holds a building of this world's pool.
			var fw := FrameworkDef.new()
			assert_eq(fw.parse({"id": "plan_test", "size": plan["size"], "tier_range": [1, 3], "lots": plan["lots"], "roads": plan["roads"], "fixtures": plan["fixtures"]},
				&"framework", "test"), PackedStringArray())
			for res: Dictionary in Lots.resolve(fw, "plan_test", seed):
				assert_true(str(res["kind"]) in ["authored", "generated"], "%s %d: lot %s (%s, %s) holds a building" % [kind, seed, res["lot"]["id"], res["lot"]["zoning"], res["size"]])
	assert_true(layouts.has("rows") and layouts.has("crossroads"), "both layouts occur")
