extends GutTest
## A stair's head respects the opening across it (TD-274): PoiValidator's stair move between a
## flight's foot and its landing crosses the head edge on the level above as a door edge is crossed.
## A closed gate opens, a bolted one (`locked_inside`) opens only from the side it was authored on,
## a locked one needs its key. Tunnel 2 Trestle's embankment stair is bolted from the deck.


## A trestle in small: a tool shed on the ground, a deck (D, level 1) reached only by a flight in the
## yard rising north from (1, 5) to a landing at (1, 1) on the deck, through `gate` on the deck's
## south wall.
func _def(gate: Dictionary, route_to_deck: bool = true) -> PoiDef:
	var g: Dictionary = {"id": "gate", "at": [1, 1], "side": "S", "type": "door", "level": 1, "model": "door_plank"}
	g.merge(gate, true)
	var route: Array = [{"at": [1, 7]}, {"at": [1, 9]}]
	if route_to_deck:
		route.append({"at": [1, 0], "level": 1})
	var raw: Dictionary = {"id": "t_stair_gate", "name": "T", "tier": 1, "footprint": [10, 16], "origin": [3, 3],
		"style": {"roof": {"type": "none"}},
		"levels": [
			{"level": 0, "plan": ["...", "...", "...", "...", "...", "...", "...", "...", "SSS", "SSS"], "rooms": {"S": {}}},
			{"level": 1, "plan": ["DDD", "DDD", "...", "...", "...", "...", "...", "...", "...", "..."], "rooms": {"D": {}}}],
		"openings": [{"id": "shed_door", "at": [1, 8], "side": "N", "type": "door", "state": "open"}, g],
		"stairs": [{"level": 0, "at": [1, 5], "dir": "N"}],
		"pickups": [{"id": "gate_key", "item": "w4_trestle_niche_key", "at": [1, 9]}],
		"route": route}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	return d


func _unreachable(v: PoiValidator) -> bool:
	for e: String in v.errors:
		if e.contains("unreachable from the previous one"):
			return true
	return false


func _has(nbrs: Array, li: int, c: Vector2i) -> bool:
	for n: Variant in nbrs:
		if n is Array and int(n[0]) == li and n[1] == c:
			return true
	return false


func test_a_closed_gate_at_the_head_opens() -> void:
	var v: PoiValidator = PoiValidator.validate(_def({"state": "closed"}))
	assert_false(_unreachable(v), "up the stair through a closed gate: %s" % [v.errors])
	for e: String in v.errors:
		assert_false(e.contains("stair"), e)


func test_a_gate_bolted_from_the_deck_stops_the_climb() -> void:
	var v: PoiValidator = PoiValidator.validate(_def({"state": "locked_inside"}))
	assert_true(_unreachable(v), "the deck can't be reached up the stair: %s" % [v.errors])
	var foot: Array = v.call(&"_neighbors", 0, Vector2i(1, 5), {})
	assert_false(_has(foot, 1, Vector2i(1, 1)), "no climb from the foot")
	# From the deck the bolt is drawn: down the stair.
	var landing: Array = v.call(&"_neighbors", 1, Vector2i(1, 1), {})
	assert_true(_has(landing, 0, Vector2i(1, 5)), "down from the landing")


func test_a_gate_bolted_from_the_stair_side_opens_going_up() -> void:
	# Authored on the head's side (the well, level 1 (1, 2)) facing N: it opens from the stair.
	var v: PoiValidator = PoiValidator.validate(_def({"at": [1, 2], "side": "N", "state": "locked_inside"}))
	assert_false(_unreachable(v), "bolted on the stair side: %s" % [v.errors])
	var landing: Array = v.call(&"_neighbors", 1, Vector2i(1, 1), {})
	assert_false(_has(landing, 0, Vector2i(1, 5)), "but not from the deck down")


func test_a_locked_gate_needs_its_key() -> void:
	var v: PoiValidator = PoiValidator.validate(_def({"state": "locked", "key": "w4_trestle_niche_key"}))
	assert_false(_unreachable(v), "the key lies in the shed first: %s" % [v.errors])
	var foot: Array = v.call(&"_neighbors", 0, Vector2i(1, 5), {})
	assert_false(_has(foot, 1, Vector2i(1, 1)), "no climb without the key")
	foot = v.call(&"_neighbors", 0, Vector2i(1, 5), {"w4_trestle_niche_key": true})
	assert_true(_has(foot, 1, Vector2i(1, 1)), "the key opens it")


func test_a_barricaded_gate_is_shut_both_ways() -> void:
	var v: PoiValidator = PoiValidator.validate(_def({"state": "barricaded"}, false))
	var foot: Array = v.call(&"_neighbors", 0, Vector2i(1, 5), {})
	assert_false(_has(foot, 1, Vector2i(1, 1)), "not up")
	var landing: Array = v.call(&"_neighbors", 1, Vector2i(1, 1), {})
	assert_false(_has(landing, 0, Vector2i(1, 5)), "not down")
