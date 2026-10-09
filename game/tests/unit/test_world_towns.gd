extends GutTest
## World-level organic towns (ADR-0040, random worlds v2 Phase 5): the generator plans its towns on
## the ground the composer grades, the composer applies a town in every region it touches with no
## seam at the borders, every lot is placed once at its own height, every lot holds a building that
## fits and keeps off the water, the roads and the other lots, PoiManager stands each building on
## its lot's frame, authored buildings are capped per world, and a v1 world (towns as region
## frameworks) still loads from its folder.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const LotPicker := preload("res://src/poi/lot_picker.gd")
const BuildingGen := preload("res://src/poi/building_generator.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")
const MapImage := preload("res://src/worldgen/rwg/rwg_map.gd")

const TMP: String = "user://test_world_towns"
const V1_FIXTURE: String = "res://tests/fixtures/rwg_v1/rwg_c01c87084fac"
const V1_ID: String = "rwg_c01c87084fac"

var _fw_ids: Array[StringName] = []


func after_all() -> void:
	for id: StringName in _fw_ids:
		Content.remove_runtime_def(&"framework", id)
	Worlds._remove(TMP)
	Worlds._remove(Worlds.dir_for(V1_ID))
	Worlds._remove("user://cache/worlds".path_join(V1_ID))


## Generates a world (with optional forced town sites) and writes its files to TMP/<world id>
## without the map; returns [generator, dir].
func _world(seed: int, overrides: Dictionary, sites: Array = []) -> Array:
	var g: RefCounted = Generator.new()
	g.set(&"settings", GenSettings.resolve(&"standard", overrides, seed))
	g.set(&"test_sites", sites)
	g.call(&"run")
	var dir: String = TMP.path_join(str(g.get(&"world_id")))
	Worlds._remove(dir)
	DirAccess.make_dir_recursive_absolute(dir.path_join("regions"))
	var wj: Dictionary = g.call(&"world_json")
	(wj["generator"] as Dictionary).erase("timings_ms")
	Worlds._write_json(dir.path_join("world.json"), wj)
	var ids: Dictionary = g.call(&"region_ids")
	for cell: Variant in ids:
		var rdir: String = dir.path_join("regions").path_join(str(ids[cell]))
		DirAccess.make_dir_recursive_absolute(rdir)
		Worlds._write_json(rdir.path_join("region.json"), g.call(&"region_json", str(cell)))
	Worlds._write_json(dir.path_join("frameworks.json"), g.call(&"frameworks_json"))
	for e: String in Worlds.register_frameworks(dir):
		push_warning("test_world_towns: %s" % e)
	for tw: Dictionary in g.get(&"towns"):
		_fw_ids.append(StringName(str(tw["fw_id"])))
	return [g, dir]


static func _frame_poly(f: Array) -> PackedVector2Array:
	return Generator.frame_poly(f)


static func _area(poly: PackedVector2Array) -> float:
	var a: float = 0.0
	for i: int in poly.size():
		a += poly[i].cross(poly[(i + 1) % poly.size()])
	return absf(a) * 0.5


# --- Seams ---------------------------------------------------------------------------------------

## A 2 x 2 world with a village forced onto the point where all four regions meet, composed at
## 4 m: every border column and row is the same height on both sides, every lot is placed by
## exactly one region (the one holding its frame's centre) at its own height, and every region the
## town touches places its fixtures.
func test_a_town_across_region_borders_has_no_seam() -> void:
	var made: Array = _world(5150, {"size": 2, "town_density": 0.0, "lakes": "none", "rivers": "none"}, [{"kind": "village", "center": Vector2(14.0, -9.0), "radius": 230.0}])
	var g: RefCounted = made[0]
	var world: WorldDef = WorldDef.load_from(made[1])
	assert_eq(world.towns.size(), 1, "the forced town is a world-level town")
	var tw: Dictionary = world.towns[0]
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(tw["framework"]))) as FrameworkDef
	assert_not_null(fw, "its framework is registered")
	if fw == null:
		return
	assert_eq(fw.layout, "organic")
	gut.p("forced village: %d lots, %d streets; warnings %s" % [fw.lots.size(), fw.roads.size(), g.get(&"warnings")])
	assert_gt(fw.lots.size(), 8, "the village has lots (%d)" % fw.lots.size())
	var rts: Dictionary = {}
	for rid: String in world.regions:
		rts[world.regions[rid]["cell"]] = TerrainComposer.compose(world, rid, 4.0)
	# Border columns (A|B) and rows (1|2): the same world samples on both sides.
	var worst: float = 0.0
	var pairs: Array = [["A1", "B1", true], ["A2", "B2", true], ["A1", "A2", false], ["B1", "B2", false]]
	for pr: Array in pairs:
		var a: RegionTerrain = rts[pr[0]]
		var b: RegionTerrain = rts[pr[1]]
		var n: int = a.height.width
		for k: int in n:
			var ha: float = a.height.heights[k * n + (n - 1)] if bool(pr[2]) else a.height.heights[(n - 1) * n + k]
			var hb: float = b.height.heights[k * n] if bool(pr[2]) else b.height.heights[k]
			worst = maxf(worst, absf(ha - hb))
	assert_lt(worst, 1.0e-4, "the borders meet: worst step %.6f m" % worst)
	# Every lot placed once, by the region holding its frame's centre, at its own height.
	var owners: Dictionary = {}
	var lots_in: Dictionary = {}
	var towns_in: int = 0
	for cell: String in rts:
		var rt: RegionTerrain = rts[cell]
		for pl: Dictionary in rt.placements:
			if str(pl["kind"]) == "lot":
				owners[str(pl["lot"])] = int(owners.get(str(pl["lot"]), 0)) + 1
				lots_in[str(pl["lot"])] = [cell, pl]
			elif str(pl["kind"]) == "town":
				towns_in += 1
	var cells: Dictionary = {}
	for lv: Variant in fw.lots:
		var l: Dictionary = lv
		assert_eq(int(owners.get(str(l["id"]), 0)), 1, "lot %s is placed exactly once" % l["id"])
		if not lots_in.has(str(l["id"])):
			continue
		var pl2: Dictionary = lots_in[str(l["id"])][1]
		cells[lots_in[str(l["id"])][0]] = true
		assert_eq(float(pl2["origin"][1]), float(l["y"]), "lot %s stands at its own height" % l["id"])
		assert_eq(world.region_at(float(l["frame"][0]), float(l["frame"][1])), str(world.cells[lots_in[str(l["id"])][0]]), "lot %s is placed by the region holding its centre" % l["id"])
		assert_almost_eq(float(pl2["rotation"]), -float(l["frame"][4]), 1.0e-6, "lot %s turns by -yaw" % l["id"])
	assert_gt(cells.size(), 1, "the town straddles borders (lots in %d regions)" % cells.size())
	assert_eq(towns_in, 4, "every region the town touches places its fixtures")
	# The pads stand at the lots' heights: the ground at a frame's centre is its y.
	var off: int = 0
	for lv2: Variant in fw.lots:
		var f: Array = lv2["frame"]
		var rt2: RegionTerrain = rts[str(lots_in[str(lv2["id"])][0])]
		if absf(rt2.height.sample(float(f[0]), float(f[1])) - float(lv2["y"])) > 0.05:
			off += 1
	assert_eq(off, 0, "every lot's ground is graded to its height (%d off)" % off)
	assert_not_null(g)


## The generator's reference ground is the composer's, sample for sample, and each lot's height is
## the mean of it over the lot's frame.
func test_lot_heights_come_from_the_composers_ground() -> void:
	var made: Array = _world(77, {"size": 3, "town_density": 3.0})
	var g: RefCounted = made[0]
	var world: WorldDef = WorldDef.load_from(made[1])
	var towns: Array = g.get(&"towns")
	assert_gt(towns.size(), 0, "the world has towns")
	var rid: String = str(world.cells["B2"])
	var b := TerrainComposer._Build.new(world, rid, 4.0, Callable())
	var ref: RefCounted = Generator.RefGround.new(g.get(&"terrain"), world.seed, world.cols)
	var r := RandomNumberGenerator.new()
	r.seed = 9
	var worst: float = 0.0
	for k: int in 200:
		var x: float = r.randf_range(-1536.0, 1536.0)
		var z: float = r.randf_range(-1536.0, 1536.0)
		worst = maxf(worst, absf(float(ref.call(&"h", x, z)) - b._reference_ground(x, z)))
	assert_eq(worst, 0.0, "the reference ground is the composer's to the bit")
	var clamped: int = 0
	for tw: Dictionary in towns:
		# The street profiles as the composer builds them (TD-318): the town's streets after the
		# world roads by it, from the world as written.
		var wt: Dictionary = {}
		for t2: Dictionary in world.towns:
			if str(t2["id"]) == str(tw["id"]):
				wt = t2
		assert_false(wt.is_empty(), "%s is in world.json" % tw["id"])
		var fixed: Array = TerrainComposer.town_world_roads(world.roads, wt["center"], float(wt["radius"]))
		var streets: Array = tw["plan"].get("roads", [])
		var profiles: Dictionary = TerrainComposer.town_street_profiles(streets, b._reference_ground, fixed)
		var lines: Dictionary = {}
		for fr: Dictionary in fixed:
			lines[str(fr["id"])] = fr["line"]
		for st: Dictionary in streets:
			lines[str(st["id"])] = Polyline2.from_array(st["points"])
		for l: Dictionary in tw["plan"]["lots"]:
			var poly: PackedVector2Array = _frame_poly(l["frame"])
			var acc: float = 0.0
			for k2: int in 25:
				var p: Vector2 = poly[3].lerp(poly[2], (k2 % 5) / 4.0).lerp(poly[0].lerp(poly[1], (k2 % 5) / 4.0), (k2 / 5) / 4.0)
				acc += b._reference_ground(p.x, p.y)
			var want: float = acc / 25.0
			var sid: String = str(l.get("street", ""))
			if lines.has(sid) and profiles.has(sid):
				var f: Array = l["frame"]
				var at: Vector3 = (lines[sid] as Polyline2).closest(Vector2(float(f[0]), float(f[1])))
				var sy: float = TerrainComposer.profile_at(profiles[sid], at.y)
				var c: float = clampf(want, sy - Generator.LOT_STREET_STEP, sy + Generator.LOT_STREET_STEP)
				if absf(c - want) > 0.011:
					clamped += 1
				want = c
			assert_almost_eq(float(l["y"]), want, 0.011, "%s/%s: y is the mean ground over its frame, within LOT_STREET_STEP of its street" % [tw["id"], l["id"]])
	gut.p("%d lots held to their street's height" % clamped)


# --- Lots and buildings ---------------------------------------------------------------------------

## Several worlds: every lot resolves (LotPicker) to a building that fits it; no lot overlaps
## another (of any town), a world road's corridor, a place or the water; and no authored building
## stands in more towns than the world-wide cap.
func test_every_lot_holds_a_building_and_keeps_clear() -> void:
	var cap: int = int(GenSettings.tuning()["towns"]["authored_max"])
	var bad: PackedStringArray = []
	var lots_seen: int = 0
	for case: Array in [[11, {"size": 4}], [12, {"size": 4, "town_size": "towns", "town_density": 4.0}], [13, {"size": 5, "terrain": "hilly", "town_density": 3.0}]]:
		var made: Array = _world(int(case[0]), case[1])
		var g: RefCounted = made[0]
		var label: String = "seed %d" % int(case[0])
		var frames: Array = []
		var authored: Dictionary = {}
		for tw: Dictionary in g.get(&"towns"):
			var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(tw["fw_id"]))) as FrameworkDef
			if fw == null:
				bad.append("%s: %s not registered" % [label, tw["fw_id"]])
				continue
			for res: Dictionary in LotPicker.resolve(fw, str(tw["id"]), 4242):
				lots_seen += 1
				var l: Dictionary = res["lot"]
				var size: Vector2i = LotPicker.lot_size(l)
				match str(res["kind"]):
					"authored":
						var pd: PoiDef = Content.get_def(&"poi", res["def_id"]) as PoiDef
						if pd.footprint.x > size.x or pd.footprint.y > size.y:
							bad.append("%s: %s/%s: %s does not fit %s" % [label, tw["id"], l["id"], pd.id, size])
						authored[String(pd.id)] = int(authored.get(String(pd.id), 0)) + 1
					"generated":
						var td: TemplateDef = Content.get_def(&"building_template", res["template"]) as TemplateDef
						if not BuildingGen.fits(td, size):
							bad.append("%s: %s/%s: template %s does not fit %s" % [label, tw["id"], l["id"], td.id, size])
					_:
						bad.append("%s: %s/%s (%s, %s) holds nothing" % [label, tw["id"], l["id"], ",".join(PackedStringArray(l["zoning"])), size])
				frames.append(["%s/%s" % [tw["id"], l["id"]], _frame_poly(l["frame"])])
		for pid: String in authored:
			if int(authored[pid]) > cap:
				bad.append("%s: %s stands in %d towns (cap %d)" % [label, pid, int(authored[pid]), cap])
		# Overlaps between lots of every town.
		for i: int in frames.size():
			for j: int in range(i + 1, frames.size()):
				if (frames[i][1][0] as Vector2).distance_to(frames[j][1][0]) > 120.0:
					continue
				var over: float = 0.0
				for part: PackedVector2Array in Geometry2D.intersect_polygons(frames[i][1], frames[j][1]):
					over += _area(part)
				if over >= 0.5:
					bad.append("%s: %s and %s overlap by %.1f m2" % [label, frames[i][0], frames[j][0], over])
		# The water, the world roads and the places.
		for fr: Array in frames:
			var poly: PackedVector2Array = fr[1]
			if float(g.call(&"water_clearance", poly)) < 10.0:
				bad.append("%s: %s is %.1f m from the water" % [label, fr[0], float(g.call(&"water_clearance", poly))])
			for rd: Dictionary in g.get(&"roads"):
				var need: float = float(rd["width"]) * 0.5 + float(rd["shoulder"])
				var line: Polyline2 = rd["line"]
				if not line.bounds.grow(need + 40.0).intersects(Generator._bounds(poly)):
					continue
				var d: float = INF
				for k: int in line.points.size() - 1:
					d = minf(d, Generator._seg_poly_distance(line.points[k], line.points[k + 1], poly))
				if d < need - 0.05:
					bad.append("%s: %s reaches %.2f m into road %s (%s)" % [label, fr[0], need - d, rd["id"], rd["class"]])
			for pl: Dictionary in g.get(&"places"):
				if not Geometry2D.intersect_polygons(poly, pl["poly"]).is_empty():
					bad.append("%s: %s overlaps place %s" % [label, fr[0], pl["id"]])
	gut.p("checked %d lots" % lots_seen)
	assert_gt(lots_seen, 100, "the worlds have lots to check")
	assert_eq(bad.size(), 0, "%d problems: %s" % [bad.size(), "; ".join(bad.slice(0, 10))])


## A town's composed region places its lots and fixtures through PoiManager's frame transform:
## the building's footprint centred in the frame, its front towards the street, at the lot's y.
func test_lot_local_xf_stands_the_building_in_its_frame() -> void:
	var lot: Dictionary = {"id": "lot_1", "frame": [100.0, -50.0, 22.0, 30.0, 37.5], "y": 84.37}
	var fp := Vector2i(14, 18)
	var xf: Transform3D = LotPicker.lot_local_xf(lot, fp)
	var centre: Vector3 = xf * Vector3(fp.x * 0.5, 0.0, fp.y * 0.5)
	assert_almost_eq(centre, Vector3(100.0, 84.37, -50.0), Vector3.ONE * 1.0e-4, "the footprint's middle is the frame's centre, at y")
	var front: Vector3 = xf.basis * Vector3(0.0, 0.0, 1.0)
	assert_almost_eq(Vector2(front.x, front.z), Vector2(sin(deg_to_rad(37.5)), cos(deg_to_rad(37.5))), Vector2.ONE * 1.0e-5, "its front points along (sin yaw, cos yaw)")
	# The same transform PoiManager gives a rect lot facing the same way (lot_xf, yaw 90 = east).
	var rect_lot: Dictionary = {"rect": [89.0, -65.0, 22.0, 30.0], "facing": "E"}
	var frame_lot: Dictionary = {"frame": [100.0, -50.0, 30.0, 22.0, 90.0]}
	assert_true(PoiManager.lot_xf(rect_lot, fp).is_equal_approx(LotPicker.lot_local_xf(frame_lot, fp)), "a frame facing east is lot_xf's east-facing rect lot")
	assert_eq(LotPicker.lot_size(frame_lot), Vector2i(30, 22), "a frame's size is its frontage and depth")


## PoiManager itself, on its boot path (placements queued, then built a few phases a frame): for a
## region's `town` placement it queues exactly the lots whose frames centre in that region, each
## building's footprint centred on its frame's centre at the lot's y (the composer's `lot`
## placement) and its front along the frame's yaw: the transform is lot_local_xf's.
func test_poi_manager_queues_each_frame_lot_on_its_frame() -> void:
	var made: Array = _world(5150, {"size": 2, "town_density": 0.0, "lakes": "none", "rivers": "none"}, [{"kind": "village", "center": Vector2(14.0, -9.0), "radius": 230.0}])
	var world: WorldDef = WorldDef.load_from(made[1])
	var tw: Dictionary = world.towns[0]
	var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(tw["framework"]))) as FrameworkDef
	assert_not_null(fw, "the town's framework is registered")
	if fw == null:
		return
	# The region holding most of its lots.
	var per_region: Dictionary = {}
	var rid: String = ""
	for l0: Dictionary in fw.lots:
		var r0: String = world.region_at(float(l0["frame"][0]), float(l0["frame"][1]))
		per_region[r0] = int(per_region.get(r0, 0)) + 1
		if rid == "" or int(per_region[r0]) > int(per_region[rid]):
			rid = r0
	var rt: RegionTerrain = TerrainComposer.compose(world, rid, 8.0)
	var town_pl: Dictionary = {}
	var lot_pls: Dictionary = {}
	for pl: Dictionary in rt.placements:
		if str(pl["kind"]) == "town":
			town_pl = pl
		elif str(pl["kind"]) == "lot":
			lot_pls[str(pl["id"])] = pl
	assert_false(town_pl.is_empty(), "the region places the town")
	assert_gt(lot_pls.size(), 2, "and some of its lots (%d)" % lot_pls.size())
	if town_pl.is_empty():
		return
	var yaw_of: Dictionary = {}
	for l: Dictionary in fw.lots:
		yaw_of["%s/%s" % [tw["id"], l["id"]]] = float(l["frame"][4])
	var pm := PoiManager.new()
	var host := Node.new()
	pm.world = host
	pm._queueing = true
	# The street fixtures need a world to stand on; the lots are what this checks.
	var fixtures: Array = fw.fixtures
	fw.fixtures = []
	pm._place_framework(town_pl)
	fw.fixtures = fixtures
	assert_eq(pm._placed.size(), lot_pls.size(), "one building queued per lot the region owns")
	for iid: Variant in pm._placed:
		var pl2: Dictionary = lot_pls.get(str(iid), {})
		assert_false(pl2.is_empty(), "%s is a lot of this region" % iid)
		if pl2.is_empty():
			continue
		var o: Array = pl2["origin"]
		assert_almost_eq(pm._placed[iid]["pos"] as Vector3, Vector3(float(o[0]), float(o[1]), float(o[2])), Vector3.ONE * 1.0e-3, "%s: the footprint centred on its frame, at its y" % iid)
	var fronts: int = 0
	for step: Array in pm._queue_builds:
		var job: Dictionary = (step[1] as Callable).get_bound_arguments()[0]
		var yaw: float = deg_to_rad(float(yaw_of.get(str(job["id"]), 0.0)))
		var front: Vector3 = (job["xf"] as Transform3D).basis * Vector3(0.0, 0.0, 1.0)
		assert_almost_eq(Vector2(front.x, front.z), Vector2(sin(yaw), cos(yaw)), Vector2.ONE * 1.0e-5, "%s faces along its frame's yaw" % job["id"])
		fronts += 1
	assert_eq(fronts, lot_pls.size(), "every queued build carries its transform")
	pm.free()
	host.free()


# --- Old worlds ------------------------------------------------------------------------------------

## A world made by generator v1 (towns as region framework features, rect lots) still loads and
## composes from its folder: its town placed by its region, its lots holding buildings.
func test_a_v1_world_still_loads_from_its_folder() -> void:
	var dir: String = Worlds.dir_for(V1_ID)
	Worlds._remove(dir)
	_copy_dir(V1_FIXTURE, dir)
	assert_true(FileAccess.file_exists(dir.path_join("world.json")), "the v1 world is in its folder")
	var gen: Dictionary = MapImage._read(dir.path_join("meta.json")).get("settings", {})
	var wl := WorldLoader.new()
	wl.load_random_world(gen, V1_ID, 8.0)
	assert_eq(wl.error, "", "it loads")
	assert_eq(wl.world_id, V1_ID, "from its own folder, not regenerated")
	assert_eq(int(wl.world.generator.get("version", 0)), 1, "made by generator v1")
	assert_true(wl.world.towns.is_empty(), "a v1 world has no world-level towns")
	var found: bool = false
	for rid: String in wl.detailed:
		for pl: Dictionary in (wl.detailed[rid] as RegionTerrain).placements:
			if str(pl["kind"]) == "framework" and str(pl["id"]) == "ivy_bend":
				found = true
				var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(pl["def"]))) as FrameworkDef
				assert_not_null(fw, "its town's framework is registered")
				if fw != null:
					_fw_ids.append(fw.id)
					assert_eq(fw.layout, "", "a v1 town is a rect-lot framework")
					for res: Dictionary in LotPicker.resolve(fw, "ivy_bend", 99):
						assert_true(str(res["kind"]) in ["authored", "generated"], "v1 lot %s holds a building" % res["lot"]["id"])
	assert_true(found, "the v1 town is placed by its region")


static func _copy_dir(from: String, to: String) -> void:
	DirAccess.make_dir_recursive_absolute(to)
	for f: String in DirAccess.get_files_at(from):
		DirAccess.copy_absolute(from.path_join(f), to.path_join(f))
	for d: String in DirAccess.get_directories_at(from):
		_copy_dir(from.path_join(d), to.path_join(d))

