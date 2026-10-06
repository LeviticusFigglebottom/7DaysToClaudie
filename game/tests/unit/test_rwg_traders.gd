extends GutTest
## Trader posts in random worlds (ADR-0039's hook, RwgGenerator VERSION 3): one by each town, on a
## highway or county road just outside it, at least the spacing apart. Each is a
## "trader:program_relay:<n>" spawn facing its road, with a clearing and a drive to its gate, and
## nothing built inside its safe zone (the guards shoot whatever Hollowed wake there).

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")

const SEEDS: Array[int] = [7, 1234]

var _worlds: Array[RefCounted] = []


func before_all() -> void:
	for seed: int in SEEDS:
		_worlds.append(Generator.generate(GenSettings.resolve(&"standard", {"size": 4}, seed)))


func test_each_town_gets_a_post_far_enough_from_the_others() -> void:
	for g: RefCounted in _worlds:
		var posts: Array = g.get(&"posts")
		var towns: Array = g.get(&"towns")
		assert_eq(posts.size(), towns.size(), "one post per town on these maps")
		for i: int in posts.size():
			assert_true(str(posts[i]["id"]).begins_with("trader:%s:" % Generator.TRADER_DEF))
			for j: int in range(i + 1, posts.size()):
				assert_gt((posts[i]["pos"] as Vector2).distance_to(posts[j]["pos"]), 600.0, "posts at least 600 m apart")


func test_a_post_faces_its_road_with_a_drive_to_its_gate() -> void:
	for g: RefCounted in _worlds:
		for pt: Dictionary in g.get(&"posts"):
			var pos: Vector2 = pt["pos"]
			var yaw: float = deg_to_rad(float(pt["yaw"]))
			# Basis(UP, yaw) turns the post's front, local +Z, to (sin yaw, cos yaw).
			var front := Vector2(sin(yaw), cos(yaw))
			var gate: Vector2 = pos + front * Generator.POST_GATE
			var drive: Dictionary = {}
			for rd: Dictionary in g.get(&"roads"):
				var pts: PackedVector2Array = rd["points"]
				if str(rd["class"]) == "drive" and pts[pts.size() - 1].distance_to(gate) < 3.0:
					drive = rd
			assert_false(drive.is_empty(), "%s has a drive ending at its gate" % pt["id"])
			if drive.is_empty():
				continue
			var from: Vector2 = (drive["points"] as PackedVector2Array)[0]
			assert_gt((from - pos).normalized().dot(front), 0.9, "the drive comes in from the road in front of %s" % pt["id"])


func test_nothing_is_built_in_a_post_safe_zone() -> void:
	for g: RefCounted in _worlds:
		for pt: Dictionary in g.get(&"posts"):
			var pos: Vector2 = pt["pos"]
			assert_false(g.call(&"_near_lots", pos, 40.0), "no town lot within the safe zone of %s" % pt["id"])
			for pl: Dictionary in g.get(&"places"):
				assert_true(Geometry2D.intersect_polygons(pl["poly"], pt["safe"]).is_empty(), "%s keeps out of the safe zone of %s" % [pl["id"], pt["id"]])
			assert_true(g.call(&"inside_one_region", pt["poly"], 0.0), "%s stands inside one region" % pt["id"])
			assert_gt(float(g.call(&"water_clearance", pt["poly"])), 13.99, "%s stands on dry ground" % pt["id"])


func test_the_post_region_lists_its_spawn_and_clearing() -> void:
	for g: RefCounted in _worlds:
		var ids: Dictionary = g.call(&"region_ids")
		for pt: Dictionary in g.get(&"posts"):
			var rj: Dictionary = g.call(&"region_json", str(pt["cell"]))
			var spawn: Dictionary = {}
			var clearing: Dictionary = {}
			for f: Dictionary in rj["features"]:
				var at: Vector2 = Vector2(float(f.get("pos", [0, 0])[0]), float(f.get("pos", [0, 0])[1])) if f.has("pos") else Vector2.INF
				if str(f.get("type", "")) == "spawn" and str(f.get("id", "")) == str(pt["id"]):
					spawn = f
				elif str(f.get("type", "")) == "clearing" and at.distance_to(pt["pos"]) < 0.2:
					clearing = f
			assert_false(spawn.is_empty(), "%s's region %s lists its spawn" % [pt["id"], ids[pt["cell"]]])
			assert_almost_eq(float(spawn.get("yaw", INF)), float(pt["yaw"]), 0.01)
			assert_eq(int(clearing.get("radius", 0)), 24, "and a clearing of 24 m round it")
			var wj: Dictionary = g.call(&"world_json")
			var listed: Array = ((wj["generator"] as Dictionary).get("traders", []) as Array).filter(func(t: Dictionary) -> bool: return str(t["id"]) == str(pt["id"]))
			assert_eq(listed.size(), 1, "world.json's generator lists %s for the map" % pt["id"])


func test_posts_are_deterministic() -> void:
	var again: RefCounted = Generator.generate(GenSettings.resolve(&"standard", {"size": 4}, SEEDS[0]))
	var a: Array = _worlds[0].get(&"posts")
	var b: Array = again.get(&"posts")
	assert_eq(b.size(), a.size())
	for i: int in mini(a.size(), b.size()):
		assert_eq(str(b[i]["id"]), str(a[i]["id"]))
		assert_eq(b[i]["pos"], a[i]["pos"])
		assert_eq(b[i]["yaw"], a[i]["yaw"])
