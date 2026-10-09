extends GutTest
## TraversalAudit (ADR-0051), with the player's capsule walked through a built POI:
## * a clear room passes;
## * a wardrobe parked in a doorway is an error, a barrel the player vaults only a warning;
## * a raised sill past what the player climbs is an error, and so is a window sill out of a
##   vault's reach of where the player stands (the route cue's crate counts);
## * a door leaf that opens into a prop on the route is an error, a rag pile under it a warning;
## * a loot room whose containers the player can't stand within reach of is an error;
## * a loot room in pitch dark (no outside opening, no light kept burning) is an error;
## * no shipped POI has anything of the kind on its route or the doorways the route crosses.

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


func test_a_barrel_the_player_vaults_is_an_error_unless_route_ok() -> void:
	# Vaultable, yet on the intended route: the way should read without a climb (poi_walk's bot
	# doesn't vault it either). An author's route_ok makes it a warning.
	for ok: bool in [false, true]:
		var barrel: Dictionary = {"prop": "barrel_metal", "pos": [1.5, 2.45]}
		if ok:
			barrel["route_ok"] = true
		var found: Array[Dictionary] = await _audit([barrel])
		var way: Array = found.filter(func(f: Dictionary) -> bool: return str(f["kind"]) in ["doorway", "route"])
		assert_gt(way.size(), 0, "the barrel is in the way: %s" % [found])
		for f: Dictionary in way:
			assert_eq(str(f["severity"]), "warn" if ok else "error", "route_ok %s: %s" % [ok, TraversalAudit.line("t", f)])
			assert_string_contains(str(f["what"]), "vault")


func test_a_raised_floor_without_a_step_is_reported() -> void:
	for h: float in [0.6, 1.5]:
		var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
			"style": {"floor_height": h},
			"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
			# A hole knocked in the wall: doors get steps built up to them (PoiBuilder.stoops).
			"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "breach"}],
			"route": [{"at": [1, 4]}, {"at": [1, 0]}]}
		var d2 := PoiDef.new()
		d2.parse(raw, &"poi", "test")
		var found: Array[Dictionary] = await Runner.audit_one(self, d2, "t_audit_sill")
		var steps: Array = found.filter(func(f: Dictionary) -> bool: return str(f["what"]).begins_with("step"))
		assert_eq(steps.size(), 1, "the %.1f m sill: %s" % [h, found])
		if steps.size() == 1:
			# Up to 1.3 m the player climbs it with Jump; higher it closes the way.
			assert_eq(str(steps[0]["severity"]), "warn" if h <= 1.3 else "error", "%.1f m" % h)


func test_a_high_window_needs_its_crate() -> void:
	# The only way in is a window 1.5 m over the yard (floor 0.6 m up, sill 0.9 m over the floor):
	# out of a vault's reach from the ground, but the route cue's crate stands under it.
	for cue: Variant in [null, "none"]:
		var win: Dictionary = {"id": "win", "at": [1, 2], "side": "S", "type": "window", "state": "broken"}
		if cue != null:
			win["cue"] = cue
		var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
			"style": {"floor_height": 0.6},
			"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
			"openings": [win],
			"route": [{"at": [1, 4]}, {"at": [1, 0]}]}
		var d := PoiDef.new()
		d.parse(raw, &"poi", "test")
		var found: Array[Dictionary] = await Runner.audit_one(self, d, "t_audit_window")
		var sills: Array = found.filter(func(f: Dictionary) -> bool: return str(f["kind"]) == "window")
		if cue == null:
			assert_eq(sills.size(), 0, "the crate under it: %s" % [found])
		else:
			assert_eq(sills.size(), 1, "no crate, no way in: %s" % [found])


func test_a_leaf_opening_into_a_prop_is_an_error() -> void:
	# The door (closed: the route opens it) swings into the room; milk cans stand on both jamb
	# lines inside, where the open leaf lies, whichever jamb it hangs on.
	var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "closed"}],
		"route": [{"at": [1, 4]}, {"at": [1, 0]}],
		"props": [{"prop": "farm_milk_can", "pos": [1.12, 2.45]}, {"prop": "farm_milk_can", "pos": [1.88, 2.45]}]}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	var found: Array[Dictionary] = await Runner.audit_one(self, d, "t_audit_swing")
	var swings: Array = found.filter(func(f: Dictionary) -> bool: return str(f["kind"]) == "swing")
	assert_eq(swings.size(), 1, "the leaf: %s" % [found])
	if swings.size() == 1:
		assert_string_contains(str(swings[0]["what"]), "farm_milk_can")
		assert_eq(str(swings[0]["severity"]), "error", "the route opens that door")
	# A rag pile the leaf sweeps over: a warning.
	raw["props"] = [{"prop": "clothes_pile", "pos": [1.5, 2.3]}]
	var d2 := PoiDef.new()
	d2.parse(raw, &"poi", "test")
	var found2: Array[Dictionary] = await Runner.audit_one(self, d2, "t_audit_swing_low")
	for f: Dictionary in found2:
		if str(f["kind"]) == "swing":
			assert_eq(str(f["severity"]), "warn", "floor clutter: %s" % TraversalAudit.line("t", f))


## A loot room `L` (3 x 4, door on its south side) with a crate against its north wall; `props`
## more, `lights` and `windows` (openings) as given. The route stops inside the door.
func _loot_def(props: Array, lights: Array = [], extra_openings: Array = []) -> PoiDef:
	var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["LLL", "LLL", "LLL", "LLL"], "rooms": {"L": {"type": "storage"}}}],
		"openings": [{"id": "front", "at": [1, 3], "side": "S", "type": "door", "state": "open"}] + extra_openings,
		"route": [{"at": [1, 5]}, {"at": [1, 3]}],
		"loot_room": {"room": "L", "level": 0},
		"lights": lights,
		"props": [{"id": "stash", "prop": "crate_wood", "at": [1, 0], "against": "N", "container": "out_ashen_bundle"}] + props}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	return d


func test_a_loot_room_out_of_reach_is_an_error() -> void:
	var lamp: Array = [{"at": [1, 1], "keep": true}]
	var found: Array[Dictionary] = await Runner.audit_one(self, _loot_def([], lamp), "t_audit_loot")
	assert_eq(found.filter(func(f: Dictionary) -> bool: return str(f["kind"]) == "loot").size(), 0, "in reach: %s" % [found])
	# A stall partition across the room, 0.36 m from either wall: the crate is behind it.
	var fenced: Array[Dictionary] = await Runner.audit_one(self, _loot_def([{"prop": "farm_stall_partition", "pos": [1.5, 1.9]}], lamp), "t_audit_loot2")
	var loot: Array = fenced.filter(func(f: Dictionary) -> bool: return str(f["kind"]) == "loot")
	assert_eq(loot.size(), 1, "fenced off: %s" % [fenced])
	if loot.size() == 1:
		assert_string_contains(str(loot[0]["what"]), "stash")
		assert_eq(str(loot[0]["severity"]), "error")


func test_a_dark_loot_room_is_an_error() -> void:
	# The yard -> a hall with a window (daylight) -> a store room (the hall's light through the
	# door the route opens) -> the loot room, two doorways from any daylight: dark unless a light
	# burns in it every run.
	var cases: Array = [
		[[], "error"],
		[[{"at": [1, 0]}], "error"],
		[[{"at": [1, 0], "keep": true}], ""],
	]
	for c: Array in cases:
		var raw: Dictionary = {"id": "t_audit", "name": "T", "tier": 1, "footprint": [12, 12],
			"style": {"floor_height": 0.0},
			"levels": [{"level": 0, "plan": ["LLL", "MMM", "HHH"],
				"rooms": {"L": {"type": "storage"}, "M": {"type": "storage"}, "H": {"type": "hallway"}}}],
			"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"},
				{"id": "store", "at": [1, 1], "side": "S", "type": "door", "state": "closed"},
				{"id": "inner", "at": [1, 0], "side": "S", "type": "door", "state": "closed"},
				{"id": "hall_window", "at": [0, 2], "side": "W", "type": "window", "state": "closed"}],
			"route": [{"at": [1, 4]}, {"at": [1, 0]}],
			"loot_room": {"room": "L", "level": 0},
			"lights": c[0],
			"props": [{"id": "stash", "prop": "crate_wood", "at": [2, 0], "against": "N", "container": "out_ashen_bundle"}]}
		var d := PoiDef.new()
		assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
		var v := PoiValidator.new()
		v.layout = PoiLayout.compile(d)
		v.call(&"_run")
		var dark: Array[Dictionary] = TraversalAudit.dark_route(v.layout, v)
		var sev: Array = dark.map(func(f: Dictionary) -> String: return str(f["severity"]))
		if str(c[1]) == "":
			assert_eq(dark.size(), 0, "a kept lamp lights it: %s" % [dark])
		else:
			assert_eq(sev, [c[1]], "lights %s: %s" % [c[0], dark])


func test_shipped_pois_keep_their_routes_and_doorways_clear() -> void:
	# An error is a prop, trap rig, wall or sill the player can't get past on the route; what the
	# player vaults, off-route doorways and props authored route_ok are warnings (TD-230).
	var bad: PackedStringArray = []
	var warns: int = 0
	for v: Variant in Content.all(&"poi"):
		var pd := v as PoiDef
		for f: Dictionary in await Runner.audit_one(self, pd, String(pd.id)):
			if str(f["severity"]) == "error":
				bad.append(TraversalAudit.line(String(pd.id), f))
			else:
				warns += 1
	gut.p("traversal warnings (TD-230): %d" % warns)
	assert_eq(bad, PackedStringArray(), "nothing blocks a route or a doorway on it")
