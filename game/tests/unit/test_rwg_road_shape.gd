extends GutTest
## Road shape in random worlds (TD-139, RwgGenerator 17-18): a routed road's hooks are cut even up a
## steep pitch, and a track off a road starts where it leaves the road, not beside it.

const Terrain := preload("res://src/worldgen/rwg/rwg_terrain.gd")
const Roads := preload("res://src/worldgen/rwg/rwg_roads.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")


## A 32 x 32 macro grid at 32 m rising 0.5 m a metre eastward: too steep for a graded cut anywhere.
func _router() -> Roads:
	var t := Terrain.new()
	t.n = 32
	t.step = 32.0
	t.h.resize(t.n * t.n)
	t.lake_of.resize(t.n * t.n)
	t.lake_of.fill(-1)
	t.river_of.resize(t.n * t.n)
	t.river_of.fill(-1)
	for c: int in t.n * t.n:
		t.h[c] = t.pos(c).x * 0.5
	var r := Roads.new()
	r.setup(t, {})
	return r


static func _sharpest(pts: PackedVector2Array) -> float:
	var worst: float = 1.0
	for i: int in range(1, pts.size() - 1):
		worst = minf(worst, (pts[i] - pts[i - 1]).normalized().dot((pts[i + 1] - pts[i]).normalized()))
	return worst


func test_a_hook_goes_even_up_a_steep_pitch() -> void:
	var r := _router()
	# East 200 m, back 60 m, east again: every corner cut climbs at 0.5, so only the hook pass cuts.
	var hook := PackedVector2Array([Vector2(100, 100), Vector2(300, 100), Vector2(240, 110), Vector2(400, 110)])
	var out: PackedVector2Array = r.relax(hook.duplicate(), 0.5)
	assert_false(out.has(Vector2(300, 100)), "the spike is gone: %s" % out)
	assert_gt(_sharpest(out), -0.5, "no turn back over 120 degrees")
	assert_eq(out[0], hook[0], "the ends stay")
	assert_eq(out[out.size() - 1], hook[hook.size() - 1])


func test_a_hook_round_a_blocked_cell_stays() -> void:
	var r := _router()
	r.blocked[r.t.cell(170, 105)] = 1
	var hook := PackedVector2Array([Vector2(100, 100), Vector2(300, 100), Vector2(240, 110), Vector2(400, 110)])
	var out: PackedVector2Array = r.relax(hook.duplicate(), 0.5)
	assert_true(out.has(Vector2(300, 100)), "the cut would cross a blocked cell: %s" % out)


func test_a_track_starts_where_it_leaves_its_road() -> void:
	var g: RefCounted = Generator.new()
	var road := PackedVector2Array([Vector2(0, 0), Vector2(400, 0)])
	g.roads.append({"points": road, "line": Polyline2.from_array([[0.0, 0.0], [400.0, 0.0]])})
	# Off the road's vertex, 12 m beside it for 120 m, then away north.
	var route := PackedVector2Array([Vector2(0, 0), Vector2(20, 12), Vector2(140, 12), Vector2(160, 80), Vector2(160, 300)])
	var out: PackedVector2Array = g.call(&"_leave_road", route, 0)
	assert_lt(out[0].distance_to(Vector2(out[0].x, 0)), 0.01, "it starts on the road")
	assert_gt(out[0].x, 130.0, "where it turns off, not 120 m back")
	assert_eq(out[out.size() - 1], route[route.size() - 1], "and still reaches the place")
	for k: int in out.size() - 1:
		for s: int in 9:
			var q: Vector2 = out[k].lerp(out[k + 1], s / 8.0)
			assert_false(absf(q.y) > 6.0 and absf(q.y) < 20.0 and q.x < 130.0, "never beside the road (%s)" % q)


func test_a_track_that_turns_off_at_once_is_kept() -> void:
	var g: RefCounted = Generator.new()
	g.roads.append({"points": PackedVector2Array([Vector2(0, 0), Vector2(400, 0)]), "line": Polyline2.from_array([[0.0, 0.0], [400.0, 0.0]])})
	var route := PackedVector2Array([Vector2(100, 0), Vector2(100, 200)])
	assert_eq(g.call(&"_leave_road", route, 0), route)


static func _road(pts: Array) -> Dictionary:
	var arr: Array = []
	for p: Vector2 in pts:
		arr.append([p.x, p.y])
	return {"points": PackedVector2Array(pts), "line": Polyline2.from_array(arr)}


## Generator 18: a road's end left 13 m beside another (a main street moved through a centre after
## it was laid) starts where it leaves that road instead.
func test_a_road_end_beside_another_starts_where_it_leaves_it() -> void:
	var g: RefCounted = Generator.new()
	g.roads.append(_road([Vector2(-200, 0), Vector2(400, 0)]))
	g.roads.append(_road([Vector2(10, 13), Vector2(150, 13), Vector2(170, 80), Vector2(170, 400)]))
	g.call(&"_leave_beside")
	var pts: PackedVector2Array = g.roads[1]["points"]
	assert_lt(absf(pts[0].y), 0.01, "it starts on the other road: %s" % pts)
	assert_gt(pts[0].x, 140.0, "where it turns off, not 140 m back")
	assert_eq(pts[pts.size() - 1], Vector2(170, 400), "its far end stays")
	assert_eq(g.roads[0]["points"], PackedVector2Array([Vector2(-200, 0), Vector2(400, 0)]), "the road it ran beside stays")


func test_two_road_ends_side_by_side_stay() -> void:
	var g: RefCounted = Generator.new()
	g.roads.append(_road([Vector2(0, 0), Vector2(400, 0)]))
	g.roads.append(_road([Vector2(10, 13), Vector2(150, 13), Vector2(170, 80), Vector2(170, 400)]))
	g.call(&"_leave_beside")
	assert_eq(g.roads[0]["points"][0], Vector2(0, 0), "neither cuts the other")
	assert_eq(g.roads[1]["points"][0], Vector2(10, 13))


func test_a_road_end_beside_another_stays_when_a_road_meets_the_stretch() -> void:
	var g: RefCounted = Generator.new()
	g.roads.append(_road([Vector2(-200, 0), Vector2(400, 0)]))
	g.roads.append(_road([Vector2(10, 13), Vector2(150, 13), Vector2(170, 80), Vector2(170, 400)]))
	# A track ends on the stretch the trim would cut (on its line, as a junction is snapped).
	var line: Polyline2 = g.roads[1]["line"]
	var q: Vector2 = line.point_at(line.closest(Vector2(80, 13)).y)
	g.roads.append(_road([q, Vector2(80, 300)]))
	g.call(&"_leave_beside")
	assert_eq(g.roads[1]["points"][0], Vector2(10, 13), "kept: the track would be left hanging")


## Generator 19: a main street's leg is cut where it enters the town's disc (_cut_out) and routed
## again from there; a leg ending just past the disc keeps its corner.
func test_a_leg_is_cut_where_it_enters_the_disc() -> void:
	var leg := PackedVector2Array([Vector2(0, 0), Vector2(100, 0), Vector2(100, 300)])
	var cut: Array = Generator._cut_out(leg, 150.0)
	assert_eq(cut.size(), 2)
	assert_eq(cut[0], Vector2(100, 50), "150 m along the leg")
	assert_eq(cut[1], PackedVector2Array([Vector2(100, 50), Vector2(100, 300)]), "and the rest from there")
	assert_eq(Generator._cut_out(leg, 370.0), [], "under 40 m left past the cut: no cut")
	assert_eq(Generator._cut_out(leg, 500.0), [], "shorter than the cut")
