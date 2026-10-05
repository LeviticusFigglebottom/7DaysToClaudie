extends GutTest
## Bridges (ADR-0023, TD-036): the deck follows the road's curve in angled sections whose outer
## edges meet, abutments stand where the banks fall clear of the girders, piers are evenly spaced
## and those in the river turn to the current, and road paint stays off the curved deck.

const DECK: float = 20.0
const WIDTH: float = 9.0


class StubWorld:
	extends Node3D
	var bridges: Node = null
	var terrain: Node = null


## A road curving left on a 160 m radius, 96 m of it a span at DECK height.
func _curve(n: int = 49, length: float = 96.0, radius: float = 160.0) -> PackedVector3Array:
	var out := PackedVector3Array()
	for i: int in n:
		var a: float = length / radius * float(i) / float(n - 1)
		out.append(Vector3(sin(a) * radius, DECK, radius - cos(a) * radius))
	return out


## A valley 9 m deep with a river 18 m wide in the middle (x 40..58), flowing toward +z.
func _ground(x: float, _z: float) -> float:
	return DECK - 9.0 * sin(clampf(x / 96.0, 0.0, 1.0) * PI)


func _river(x: float, _z: float) -> Dictionary:
	if x > 40.0 and x < 58.0:
		return {"level": DECK - 6.5, "flow": Vector2(0.15, 1.0).normalized()}
	return {}


func _plan() -> Dictionary:
	return BridgeBuilder.plan(_curve(), WIDTH, _ground, _river)


func test_deck_sections_follow_the_curve() -> void:
	var path: PackedVector3Array = _curve()
	var p: Dictionary = _plan()
	var sections: Array = p["sections"]
	assert_gt(sections.size(), 8, "a 96 m span takes many sections")
	var cum := PackedFloat32Array([0.0])
	for i: int in range(1, path.size()):
		cum.append(cum[i - 1] + Vector2(path[i].x - path[i - 1].x, path[i].z - path[i - 1].z).length())
	for k: int in sections.size():
		var s: Dictionary = sections[k]
		var a: Vector3 = s["a"]
		var b: Vector3 = s["b"]
		assert_almost_eq(a.y, DECK, 0.001, "the deck is level")
		assert_lt(_off_path(path, (a + b) * 0.5), 0.15, "section %d's chord stays on the road's curve" % k)
		var len_k: float = Vector2(b.x - a.x, b.z - a.z).length()
		assert_between(len_k, BridgeBuilder.SECTION * 0.55, BridgeBuilder.SECTION * 1.2, "sections stay near the authored length")
		assert_almost_eq((s["xf"] as Transform3D).basis.x.normalized().dot(s["dir"]), 1.0, 1e-4, "section points along its chord")
		if k > 0:
			var prev: Dictionary = sections[k - 1]
			assert_almost_eq((prev["b"] as Vector3).distance_to(a), 0.0, 0.001, "sections chain end to end")
			var bend: float = absf((prev["dir"] as Vector3).signed_angle_to(s["dir"], Vector3.UP))
			assert_gt(bend, 0.001, "neighbouring sections are angled to each other")
			# The outer edges meet: each section reaches half the width x tan(bend / 2) past the joint.
			var need: float = WIDTH * 0.5 * tan(bend * 0.5)
			assert_true((s["ext"] as Vector2).x >= need and (prev["ext"] as Vector2).y >= need, "no gap on the outside of the bend at joint %d" % k)
			assert_almost_eq(float(s["length"]), len_k + (s["ext"] as Vector2).x + (s["ext"] as Vector2).y, 0.001)
	var first: Vector3 = (sections[0] as Dictionary)["a"]
	var last: Vector3 = (sections[-1] as Dictionary)["b"]
	assert_almost_eq(first.distance_to(path[0]), 0.0, 0.01)
	assert_almost_eq(last.distance_to(path[path.size() - 1]), 0.0, 0.01)


func _off_path(path: PackedVector3Array, p: Vector3) -> float:
	var best: float = INF
	for i: int in path.size() - 1:
		var a := Vector2(path[i].x, path[i].z)
		var ab := Vector2(path[i + 1].x, path[i + 1].z) - a
		var t: float = clampf((Vector2(p.x, p.z) - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		best = minf(best, (a + ab * t).distance_to(Vector2(p.x, p.z)))
	return best


func test_abutments_sit_where_the_banks_fall_away() -> void:
	var p: Dictionary = _plan()
	var seats: Vector2 = p["seats"]
	var clear: float = DECK - BridgeBuilder.DEPTH - BridgeBuilder.SEAT_CLEARANCE
	assert_gt(seats.x, 0.0, "the bank at the near end is too high for girders at the span end")
	assert_lt(seats.x, float(p["length"]) * 0.34)
	assert_gt(seats.y, float(p["length"]) * 0.66)
	var abuts: Array = p["abutments"]
	assert_eq(abuts.size(), 2)
	for a: Dictionary in abuts:
		var xf: Transform3D = a["xf"]
		assert_lt(_ground(xf.origin.x, xf.origin.z), clear + 0.1, "the seat clears the girders")
	# Each faces into the span.
	var mid: Vector3 = _curve()[24]
	for a: Dictionary in abuts:
		var xf: Transform3D = a["xf"]
		assert_gt(xf.basis.x.dot(mid - xf.origin), 0.0)
	# Approach sections over the fill, girder sections between the seats.
	var models: Dictionary = {}
	for s: Dictionary in p["sections"]:
		models[s["model"]] = int(models.get(s["model"], 0)) + 1
	assert_true(models.has(BridgeBuilder.APPROACH_MODEL) and models.has(BridgeBuilder.DECK_MODEL))
	# The far bank is still high 1.5 m in from the span end: no sliver of approach there.
	assert_almost_eq(float(p["length"]) - seats.y, BridgeBuilder.MIN_APPROACH, 0.01, "a short approach is lengthened")
	# Past a cliff edge the girders reach the span end instead.
	var cliff := func(x: float, _z: float) -> float: return DECK if x < 1.0 else DECK - 12.0
	var c: Dictionary = BridgeBuilder.plan(_curve(), WIDTH, cliff, _river)
	assert_almost_eq((c["seats"] as Vector2).x, 0.0, 0.001, "no approach walls hanging off a cliff")


func test_piers_are_evenly_spaced_and_turned_to_the_current() -> void:
	var p: Dictionary = _plan()
	var seats: Vector2 = p["seats"]
	var piers: Array = p["piers"]
	var expected: int = roundi((seats.y - seats.x) / BridgeBuilder.TARGET_SPAN) - 1
	assert_eq(piers.size(), expected)
	var spacing: float = (seats.y - seats.x) / float(piers.size() + 1)
	var prev: float = seats.x
	var wet: int = 0
	for q: Dictionary in piers:
		assert_almost_eq(float(q["s"]) - prev, spacing, 0.01, "even spans between the abutments")
		prev = q["s"]
		var xf: Transform3D = q["xf"]
		if bool(q["wet"]):
			wet += 1
			var flow := Vector3(0.15, 0.0, 1.0).normalized()
			assert_almost_eq(absf(xf.basis.z.normalized().dot(flow)), 1.0, 0.001, "a river pier's cutwaters face the current")
		else:
			assert_gte(_ground(xf.origin.x, xf.origin.z), float(_river(xf.origin.x, xf.origin.z).get("level", -INF)) + BridgeBuilder.FLOOD_RISE,
				"a bent stands on dry ground above the flood channel")
	assert_gt(wet, 0, "at least one pier stands in the river")
	assert_almost_eq(float(seats.y) - prev, spacing, 0.01)


func test_deck_path_follows_the_road_polyline() -> void:
	var road := PackedVector3Array()
	for i: int in 60:
		var a: float = float(i) * 0.03
		road.append(Vector3(sin(a) * 200.0, 5.0 + float(i) * 0.1, 200.0 - cos(a) * 200.0))
	var from: Vector3 = road[10] + Vector3(0.0, 3.0, 0.4)
	var to: Vector3 = road[40] + Vector3(0.3, 0.0, 0.0)
	to.y = from.y
	var path: PackedVector3Array = BridgeBuilder.deck_path(road, from, to)
	assert_gt(path.size(), 25, "the deck keeps every road point between its ends")
	for p: Vector3 in path:
		assert_almost_eq(p.y, from.y, 0.001)
	assert_lt(Vector2(path[0].x - from.x, path[0].z - from.z).length(), 0.5)
	assert_lt(Vector2(path[-1].x - to.x, path[-1].z - to.z).length(), 0.5)
	# Reversed ends give the same deck backwards.
	var back: PackedVector3Array = BridgeBuilder.deck_path(road, to, from)
	assert_almost_eq(back[0].distance_to(path[-1]), 0.0, 0.01)
	# Points that don't reach the span fall back to the chord.
	assert_eq(BridgeBuilder.deck_path(PackedVector3Array(), from, to).size(), 2)


func test_on_deck_and_no_paint_on_a_curved_deck() -> void:
	var bb := BridgeBuilder.new()
	add_child_autofree(bb)
	var path: PackedVector3Array = _curve()
	bb.spans.append({"from": path[0], "to": path[-1], "width": WIDTH, "path": path, "plan": _plan()})
	assert_true(bb.on_deck(path[24]), "the middle of the deck")
	assert_true(bb.on_deck(path[24] + Vector3(0.0, 0.0, WIDTH * 0.45)), "near the deck's edge on the curve")
	assert_false(bb.on_deck(path[24] + Vector3(0.0, 0.0, 15.0)), "off to the side")
	assert_false(bb.on_deck(path[0] - Vector3(12.0, 0.0, 0.0)), "before the span")
	# RoadMarkings asks the bridge builder, so paint follows the curve off the deck.
	var w := StubWorld.new()
	w.bridges = bb
	add_child_autofree(w)
	var rm := RoadMarkings.new()
	var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	rm._albedo = [ImageTexture.create_from_image(img)]
	rm._normal = [null]
	rm.world = w
	add_child_autofree(rm)
	var pts: Array = []
	# The road runs on 40 m past each end of the span along the same curve.
	for i: int in range(-20, 69):
		var a: float = 96.0 / 160.0 * float(i) / 48.0
		pts.append([sin(a) * 160.0, DECK, 160.0 - cos(a) * 160.0])
	rm._mark({"id": "curve", "surface": "asphalt", "width": 8.0, "points": pts})
	assert_gt(rm.count, 10, "the approaches are painted")
	for d: Decal in rm.get_children():
		assert_false(bb.on_deck(d.position, 0.0), "no decal on the deck at %s" % d.position)
	var nav: PackedVector3Array = bb.nav_faces_in_rect(Rect2(-10.0, -40.0, 120.0, 80.0))
	assert_eq(nav.size(), (_plan()["sections"] as Array).size() * 6, "one walkable quad per section")
