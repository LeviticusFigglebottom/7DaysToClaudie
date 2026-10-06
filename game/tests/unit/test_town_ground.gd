extends GutTest
## A world town's ground (TD-136, TerrainComposer VERSION 12): `town` is painted on its streets (and
## the highway through it) and its square only, not over its whole disc; the ground between streets
## and yards keeps the world's biome; town ambience and spawns key on WorldDef.town_at instead; and a
## yard's grass keeps off the largest authored building its lot may hold.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const LotPicker := preload("res://src/poi/lot_picker.gd")

const TMP: String = "user://test_town_ground"
const CENTER := Vector2(470.0, 520.0)
const RADIUS: float = 230.0

var _fw_ids: Array[StringName] = []
var _world: WorldDef
var _fw: FrameworkDef
var _rt: RegionTerrain


func before_all() -> void:
	var g: RefCounted = Generator.new()
	g.set(&"settings", GenSettings.resolve(&"standard", {"size": 2, "town_density": 0.0, "lakes": "none", "rivers": "none"}, 6161))
	g.set(&"test_sites", [{"kind": "village", "center": CENTER, "radius": RADIUS}])
	g.call(&"run")
	var dir: String = TMP.path_join(str(g.get(&"world_id")))
	Worlds._remove(TMP)
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
		push_warning("test_town_ground: %s" % e)
	for tw: Dictionary in g.get(&"towns"):
		_fw_ids.append(StringName(str(tw["fw_id"])))
	_world = WorldDef.load_from(dir)
	if _world.towns.is_empty():
		return
	_fw = Content.get_def(&"framework", StringName(str(_world.towns[0]["framework"]))) as FrameworkDef
	_rt = TerrainComposer.compose(_world, _world.region_at(CENTER.x, CENTER.y), 4.0)


func after_all() -> void:
	for id: StringName in _fw_ids:
		Content.remove_runtime_def(&"framework", id)
	Worlds._remove(TMP)


## Distance from p to the nearest of the town's streets less its half width and shoulder (m).
func _street_gap(p: Vector2) -> float:
	var best: float = INF
	for rv: Variant in _fw.roads:
		var rd: Dictionary = rv
		var line := Polyline2.from_array(rd["points"])
		best = minf(best, line.closest(p).x - float(rd.get("width", 6.0)) * 0.5 - float(rd.get("shoulder", 0.8)))
	for r: Dictionary in _world.roads:
		best = minf(best, (r["line"] as Polyline2).closest(p).x - float(r["width"]) * 0.5 - float(r["shoulder"]))
	return best


## Whether p lies within `grow` m of any lot's frame or the square.
func _in_frame(p: Vector2, grow: float) -> bool:
	var frames: Array = []
	for lv: Variant in _fw.lots:
		frames.append((lv as Dictionary)["frame"])
	if _fw.plaza.has("frame"):
		frames.append(_fw.plaza["frame"])
	for f: Array in frames:
		var lp: Vector2 = (p - Vector2(float(f[0]), float(f[1]))).rotated(deg_to_rad(float(f[4])))
		if absf(lp.x) <= float(f[2]) * 0.5 + grow and absf(lp.y) <= float(f[3]) * 0.5 + grow:
			return true
	return false


func test_town_is_painted_on_streets_not_the_whole_disc() -> void:
	assert_not_null(_rt, "the town's region composes")
	if _rt == null:
		return
	var on_street: int = 0
	var on_street_town: int = 0
	var between: int = 0
	var between_town: int = 0
	var disc: int = 0
	var disc_town: int = 0
	var step: float = 6.0
	var x: float = CENTER.x - RADIUS
	while x <= CENTER.x + RADIUS:
		var z: float = CENTER.y - RADIUS
		while z <= CENTER.y + RADIUS:
			var p := Vector2(x, z)
			z += step
			if p.distance_to(CENTER) > RADIUS * 0.9 or not _rt.rect.has_point(p):
				continue
			var b: String = _rt.biome_at(p.x, p.y)
			disc += 1
			disc_town += 1 if b == "town" else 0
			var gap: float = _street_gap(p)
			if gap < 1.0 and not _in_frame(p, 1.0):
				on_street += 1
				on_street_town += 1 if b == "town" else 0
			elif gap > 9.0 and not _in_frame(p, 3.0):
				between += 1
				between_town += 1 if b == "town" else 0
		x += step
	gut.p("disc %d samples, %d town; streets %d (%d town); between %d (%d town)" % [disc, disc_town, on_street, on_street_town, between, between_town])
	assert_gt(on_street, 20, "the disc holds streets")
	assert_gt(float(on_street_town) / maxf(1.0, on_street), 0.85, "the streets are town ground")
	assert_gt(between, 20, "the disc holds ground between streets and lots")
	assert_eq(between_town, 0, "the ground between the streets and the lots keeps the world's biome")
	assert_lt(float(disc_town) / maxf(1.0, disc), 0.6, "the disc is not one brown town paint")


func test_yard_grass_keeps_off_the_largest_authored_footprint() -> void:
	assert_not_null(_rt)
	if _rt == null:
		return
	var clipped: int = 0
	var under: int = 0
	var grass: int = 0
	for lv: Variant in _fw.lots:
		var l: Dictionary = lv
		var f: Array = l["frame"]
		var c := Vector2(float(f[0]), float(f[1]))
		if not _rt.rect.grow(-8.0).has_point(c):
			continue
		var core: Vector2i = LotPicker.max_authored_footprint(_fw, l)
		if core.x > 0:
			clipped += 1
		# Sample the frame on a 1 m grid.
		var w: float = float(f[2])
		var d: float = float(f[3])
		var yaw: float = -deg_to_rad(float(f[4]))
		for i: int in int(w):
			for j: int in int(d):
				var lp := Vector2(i + 0.5 - w * 0.5, j + 0.5 - d * 0.5)
				var p: Vector2 = c + lp.rotated(yaw)
				var v: float = _rt.veg_at(p.x, p.y)
				# The nearest 4 m sample may sit up to 2.9 m away: test well inside.
				if core.x > 0 and absf(lp.x) < core.x * 0.5 - 3.0 and absf(lp.y) < core.y * 0.5 - 3.0:
					if v > 0.0:
						under += 1
				elif v > 0.0:
					grass += 1
	gut.p("%d lots may hold an authored building; %d grass samples in yards" % [clipped, grass])
	assert_gt(clipped, 0, "some lot may hold an authored building")
	assert_eq(under, 0, "no yard grass under a footprint")
	assert_gt(grass, 0, "yards keep their grass round the buildings")


func test_town_at_and_behaviour_biome() -> void:
	assert_false(_world.towns.is_empty(), "the world has its town")
	if _world.towns.is_empty():
		return
	var tid: String = str(_world.towns[0]["id"])
	assert_eq(_world.town_at(CENTER.x, CENTER.y), tid, "the centre is in the town")
	assert_eq(_world.town_at(-700.0, -700.0), "", "far away is not")
	assert_eq(_world.behaviour_biome("meadow", CENTER.x, CENTER.y), "town", "a meadow inside the town spawns and sounds as town")
	assert_eq(_world.behaviour_biome("yard", CENTER.x, CENTER.y), "yard", "yards stay yards")
	assert_eq(_world.behaviour_biome("conifer_forest", -700.0, -700.0), "conifer_forest", "outside it the composed biome holds")
	var main: WorldDef = WorldDef.load_from("res://world/main_map")
	assert_eq(main.behaviour_biome("meadow", 0.0, 0.0), "meadow", "the main map has no organic towns")
	assert_eq(main.behaviour_biome("town", 0.0, 0.0), "town")
