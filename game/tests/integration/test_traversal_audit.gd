extends GutTest
## TraversalAudit (ADR-0051): the player's capsule walked through a built POI finds a wardrobe
## parked in a doorway, lets a barrel the player vaults through as a warning, passes a clear room,
## and every shipped POI's route and the doorways it crosses are free of props.

const Runner := preload("res://src/tools/cli/traversal_audit_runner.gd")


func _def(props: Array) -> PoiDef:
	var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"route": [{"at": [1, 4]}, {"at": [1, 0]}],
		"props": props}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	return d


func _audit(props: Array) -> Array[Dictionary]:
	return await Runner.audit_one(self, _def(props), "t_audit")


func test_a_clear_room_passes() -> void:
	var found: Array[Dictionary] = await _audit([])
	assert_eq(found.size(), 0, "nothing in the way: %s" % [found])


func test_a_wardrobe_in_the_doorway_is_an_error() -> void:
	var found: Array[Dictionary] = await _audit([{"prop": "wardrobe", "pos": [1.5, 2.45]}])
	var hit: Dictionary = {}
	for f: Dictionary in found:
		if f["kind"] == "doorway" and str(f.get("opening", "")) == "front":
			hit = f
	assert_false(hit.is_empty(), "the doorway is reported: %s" % [found])
	assert_string_contains(str(hit.get("what", "")), "wardrobe", "named by its prop id")
	assert_eq(str(hit.get("severity", "")), "error", "the route goes through it")


func test_a_barrel_the_player_vaults_is_a_warning() -> void:
	var found: Array[Dictionary] = await _audit([{"prop": "barrel_metal", "pos": [1.5, 2.45]}])
	assert_gt(found.size(), 0, "the barrel is in the way")
	for f: Dictionary in found:
		assert_eq(str(f["severity"]), "warn", "vaultable: %s" % TraversalAudit.line("t", f))
		assert_string_contains(str(f["what"]), "vault")


func test_a_raised_floor_without_a_step_is_reported() -> void:
	var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.6},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"route": [{"at": [1, 4]}, {"at": [1, 0]}]}
	var d2 := PoiDef.new()
	d2.parse(raw, &"poi", "test")
	var found: Array[Dictionary] = await Runner.audit_one(self, d2, "t_audit_sill")
	var steps: Array = found.filter(func(f: Dictionary) -> bool: return str(f["what"]).begins_with("step"))
	assert_eq(steps.size(), 1, "the 0.6 m sill: %s" % [found])


func test_shipped_pois_keep_their_routes_and_doorways_clear() -> void:
	# Raised sills without steps ("step ...") belong to the entrance-steps work (TD-229) and are
	# only counted here; any other error is a prop, trap rig or wall in the player's way.
	var bad: PackedStringArray = []
	var steps: int = 0
	for v: Variant in Content.all(&"poi"):
		var pd := v as PoiDef
		for f: Dictionary in await Runner.audit_one(self, pd, String(pd.id)):
			if str(f["severity"]) != "error":
				continue
			if str(f["what"]).begins_with("step"):
				steps += 1
			else:
				bad.append(TraversalAudit.line(String(pd.id), f))
	gut.p("raised sills without a step on the route: %d" % steps)
	assert_eq(bad, PackedStringArray(), "nothing blocks a route or a doorway on it")
