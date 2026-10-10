extends GutTest
## Map markers for what the player built (player report 5): shelters (a lean-to, a bedroll: where
## you sleep, save or wake) are marked on the maps by data, and a layer can be turned off.

var _saved: Dictionary


func before_each() -> void:
	_saved = Settings.map_layers.duplicate()


func after_each() -> void:
	Settings.map_layers = _saved


func _ws(defs: Array) -> WorldState:
	var ws := WorldState.new()
	for i: int in defs.size():
		ws.structures["s%d" % i] = {"def": defs[i], "pos": [float(i) * 10.0, 0.0, 5.0], "rot": [0, 0, 0, 1]}
	return ws


func test_the_shipped_layers_are_sound() -> void:
	assert_eq(MapMarkers.problems(), PackedStringArray(), "every layer names tags some structure provides")
	var ids: Array = MapMarkers.layers().map(func(l: Dictionary) -> String: return str(l["id"]))
	assert_has(ids, "shelter")


func test_shelters_are_marked_and_nothing_else() -> void:
	var ws: WorldState = _ws(["lean_to", "bedroll", "workbench", "log_piece", "storage_crate"])
	var marks: Array[Dictionary] = MapMarkers.marks(MapMarkers.placed(ws), MapMarkers.layers(), ["shelter"])
	var defs: Array = marks.map(func(m: Dictionary) -> StringName: return m["def"])
	assert_eq(defs.size(), 2, "the lean-to and the bedroll")
	assert_has(defs, &"lean_to")
	assert_has(defs, &"bedroll")
	assert_eq((marks[0]["pos"] as Vector3), Vector3(0.0, 0.0, 5.0), "where it was placed")


func test_a_layer_turned_off_hides_its_marks() -> void:
	var ws: WorldState = _ws(["lean_to"])
	assert_eq(MapMarkers.marks(MapMarkers.placed(ws), MapMarkers.layers(), []).size(), 0)
	Settings.map_layers["shelter"] = false
	assert_eq(MapMarkers.marks(MapMarkers.placed(ws), MapMarkers.layers()).size(), 0, "the saved choice")
	Settings.map_layers.erase("shelter")
	assert_eq(MapMarkers.marks(MapMarkers.placed(ws), MapMarkers.layers()).size(), 1, "on by default")


func test_a_layer_matches_tags_exactly_or_by_prefix() -> void:
	var layers: Array = [{"id": "work", "provides": ["station:"]}, {"id": "rest", "provides": ["sleep"]}]
	assert_eq(str(MapMarkers.layer_for(PackedStringArray(["station:forge"]), layers).get("id", "")), "work")
	assert_eq(str(MapMarkers.layer_for(PackedStringArray(["sleep", "save_point"]), layers).get("id", "")), "rest")
	assert_true(MapMarkers.layer_for(PackedStringArray(["storage:20"]), layers).is_empty())


func test_a_bad_layer_is_reported() -> void:
	var bad: PackedStringArray = MapMarkers.problems({"layers": [{"id": "x", "label": "X", "provides": ["no_such_tag"]}, {"id": "", "provides": []}]})
	assert_eq(bad.size(), 3, "an unknown tag, a missing id and a missing label: %s" % [bad])
