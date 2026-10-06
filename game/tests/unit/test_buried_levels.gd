extends GutTest
## Buried underground levels (ADR-0044): a POI level marked "buried" runs on under the ground beyond
## the building. Only its cells under a ground-floor room cut the terrain surface; the rest get a
## floor-only hole per level, so the surface stays whole over a mine level or a cave while the
## fell-through-the-world checks (ground_below) still find its floor.

const PAD_Y: float = 5.0


## A 2 x 2 office over a mine level 8 cells long (cells 2..7 run on under the ground), and a cave
## level below that, all of it beyond the office.
func _def(buried: bool) -> PoiDef:
	var raw: Dictionary = {
		"id": "t_adit", "name": "Test Adit", "tier": 1, "footprint": [12, 6], "origin": [1, 1],
		"style": {"floor_height": 0.2, "roof": {"type": "flat"}},
		"levels": [
			{"level": 0, "plan": ["OO", "OO"], "rooms": {"O": {"type": "office"}}},
			{"level": -1, "buried": buried, "plan": ["DDDDDDDD", "DDDDDDDD"], "rooms": {"D": {"type": "cellar"}}},
			{"level": -2, "buried": buried, "plan": ["  CCCCCC", "  CCCCCC"], "rooms": {"C": {"type": "cellar"}}}],
		"openings": [{"id": "front", "at": [0, 1], "side": "S", "type": "door", "state": "open"}],
		"route": [{"at": [0, 3]}, {"at": [0, 0]}],
	}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func _holes(buried: bool) -> TerrainHoles:
	var th := TerrainHoles.new()
	th.add_poi(_def(buried), &"test/adit", Transform3D(Basis.IDENTITY, Vector3(0, PAD_Y, 0)))
	return th


## World XZ centre of a plan cell (origin offset [1, 1], no rotation).
func _c(cx: int, cz: int) -> Vector2:
	return Vector2(1.5 + cx, 1.5 + cz)


func test_only_the_cells_under_the_building_cut_the_surface() -> void:
	var th: TerrainHoles = _holes(true)
	var under := _c(1, 1)
	var beyond := _c(5, 0)
	assert_true(th.contains(under.x, under.y), "the shaft under the office is cut")
	assert_false(th.contains(beyond.x, beyond.y), "the ground stays whole over the drift")
	assert_true(th.has_buried())
	var plain: TerrainHoles = _holes(false)
	assert_true(plain.contains(beyond.x, beyond.y), "an ordinary cellar level is cut wherever it runs")
	assert_false(plain.has_buried())


func test_buried_floors_are_found_level_by_level() -> void:
	var th: TerrainHoles = _holes(true)
	var l := PoiLayout.compile(_def(true))
	var f1: float = PAD_Y + l.level_y(-1)
	var f2: float = PAD_Y + l.level_y(-2)
	var p := _c(5, 1)
	assert_almost_eq(th.buried_floor(p.x, p.y, f1 + 1.0), f1, 1e-4, "standing in the drift")
	assert_almost_eq(th.buried_floor(p.x, p.y, f2 + 1.0), f2, 1e-4, "standing in the cave below it")
	assert_almost_eq(th.buried_floor(p.x, p.y, f2 - 3.0), f2, 1e-4, "fallen through: back onto the lowest floor")
	assert_true(is_nan(th.buried_floor(p.x, p.y, PAD_Y + 1.0)), "up on the ground: not underground")
	var drift_only := _c(1, 0)
	assert_true(is_nan(th.buried_floor(drift_only.x, drift_only.y, f1 + 1.0)), "under the office is the ordinary cut, not a buried floor")
	var off := Vector2(30.0, 30.0)
	assert_true(is_nan(th.buried_floor(off.x, off.y, f1)), "nothing buried out there")
