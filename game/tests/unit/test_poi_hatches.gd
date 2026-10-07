extends GutTest
## Ladder hatches have no floor (TD-224): the validator's route graph drops whoever steps onto one
## to the ladder's foot, and a doorway opening straight onto one is an error.


func _def(openings: Array) -> PoiDef:
	var raw: Dictionary = {"id": "t_hatch", "name": "T", "tier": 1, "footprint": [12, 12],
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBC", "BBC", "BBC"], "rooms": {"B": {}, "C": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}] + openings,
		"ladders": [{"level": 0, "at": [1, 0], "side": "N", "hatch": true}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}, {"at": [0, 1], "level": 1}]}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	return d


func test_stepping_onto_a_hatch_drops_to_the_ladder_foot() -> void:
	var v: PoiValidator = PoiValidator.validate(_def([]))
	assert_eq(v.call(&"_land", 1, Vector2i(1, 0)), [0, Vector2i(1, 0)], "the hatch cell")
	assert_eq(v.call(&"_land", 1, Vector2i(0, 0)), [1, Vector2i(0, 0)], "the floor beside it")


func test_a_door_onto_a_hatch_is_an_error() -> void:
	# C's door at (2, 0) west opens onto the hatch at (1, 0) on level 1.
	var v: PoiValidator = PoiValidator.validate(_def([{"id": "c_door", "at": [2, 0], "side": "W", "type": "door", "state": "open", "level": 1}]))
	var found: bool = false
	for e: String in v.errors:
		found = found or (e.contains("c_door") and e.contains("ladder hatch"))
	assert_true(found, "reported: %s" % [v.errors])
	var v2: PoiValidator = PoiValidator.validate(_def([{"id": "c_door", "at": [2, 2], "side": "W", "type": "door", "state": "open", "level": 1}]))
	for e2: String in v2.errors:
		assert_false(e2.contains("ladder hatch"), "a door away from the hatch: %s" % e2)
