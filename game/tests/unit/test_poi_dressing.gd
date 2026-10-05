extends GutTest
## Per-run dressing and room alternatives (ADR-0030, PoiDressing): a building's dressing follows the
## world seed and its placement (same seed, same building; a new run, a different-looking one), its
## stable piece ids and seats stay put, legacy saves keep the authored building (save v5 migration),
## and the validator walks every alternative.

const Dressing := preload("res://src/poi/poi_dressing.gd")
const Generator := preload("res://src/poi/building_generator.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")



func _def(raw_layout: Dictionary) -> PoiDef:
	var raw: Dictionary = {"id": "t", "name": "T", "tier": 1, "footprint": [16, 16]}
	raw.merge(raw_layout, true)
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


## Two rooms: the front room F with the way in, the back room B (the loot room) through a door.
func _two_rooms(extra: Dictionary = {}) -> Dictionary:
	var lay: Dictionary = {
		"levels": [{"level": 0, "plan": ["BBBB", "BBBB", "FFFF", "FFFF"], "rooms": {"B": {"name": "Back room", "type": "bedroom"}, "F": {"name": "Front room", "type": "living"}}}],
		"openings": [
			{"id": "front_door", "at": [1, 3], "side": "S", "type": "door", "state": "closed"},
			{"id": "inner_door", "at": [1, 2], "side": "N", "type": "door", "state": "closed"},
			{"id": "back_door", "at": [2, 0], "side": "N", "type": "door", "state": "locked_inside"}],
		"props": [{"id": "back_dresser", "prop": "dresser", "at": [3, 0], "against": "N"}],
		"route": [{"at": [1, 5]}, {"at": [1, 2]}, {"at": [1, 0]}, {"at": [2, 0]}, {"at": [2, -2]}],
		"loot_room": {"room": "B", "level": 0},
		"shortcuts": [{"opening": "back_door"}]}
	lay.merge(extra, true)
	return lay


func test_defaults_resolve_to_the_authored_building() -> void:
	var d: PoiDef = _def(_two_rooms({
		"alternatives": [{"id": "back", "options": [{"id": "bedroom"}, {"id": "study", "weight": 2,
			"rooms": [{"room": "B", "name": "Study", "type": "office", "wall": "wood_paneling_dark"}]}]}],
		"props": [
			{"id": "back_dresser", "prop": "dresser", "at": [3, 0], "against": "N", "alt": "back:bedroom"},
			{"id": "study_desk", "prop": "desk_small", "at": [0, 0], "against": "N", "alt": "back:study"}]}))
	var l: PoiLayout = PoiLayout.compile(d)
	assert_eq(l.props.size(), 1, "the default option's furniture only")
	assert_eq(str(l.props[0]["id"]), "back_dresser")
	assert_false(l.props[0].has("alt"), "alt tags are resolved away")
	assert_eq(str(l.room_def(0, "B").get("name")), "Back room")
	var study: PoiLayout = PoiLayout.compile(Dressing.resolve(d, {"back": "study"}))
	assert_eq(str(study.room_def(0, "B").get("type")), "office", "the study's purpose")
	assert_eq(str(study.props[0]["id"]), "study_desk")
	assert_eq(Dressing.resolve(d, {"back": "study"}).dressing["picks"], {"back": "study"})


func test_picks_are_weighted_and_deterministic() -> void:
	var d: PoiDef = _def(_two_rooms({"alternatives": [{"id": "back", "options": [{"id": "a", "weight": 1}, {"id": "b", "weight": 3}, {"id": "never", "weight": 0}]}]}))
	var counts: Dictionary = {}
	for i: int in 400:
		var p: Dictionary = Dressing.roll(d, Ids.hash64("seed%d" % i))
		counts[p["back"]] = int(counts.get(p["back"], 0)) + 1
		assert_eq(Dressing.roll(d, Ids.hash64("seed%d" % i)), p, "same seed, same pick")
	assert_false(counts.has("never"), "weight 0 is never picked")
	assert_between(int(counts.get("b", 0)), 240, 360, "b is three times as likely as a")


func test_dressing_seed_follows_the_world_seed_and_keeps_legacy() -> void:
	var id := &"pell_crossing/merrow"
	assert_eq(Dressing.dressing_seed(4471, id, Dressing.MODE_LEGACY), Ids.hash64("poi:" + String(id)), "legacy: the old builder seed")
	assert_eq(Dressing.dressing_seed(4471, id, Dressing.MODE_PER_RUN), Dressing.dressing_seed(4471, id, Dressing.MODE_PER_RUN))
	assert_ne(Dressing.dressing_seed(4471, id, Dressing.MODE_PER_RUN), Dressing.dressing_seed(4472, id, Dressing.MODE_PER_RUN))
	assert_ne(Dressing.dressing_seed(4471, id, Dressing.MODE_PER_RUN), Dressing.dressing_seed(4471, &"pell_crossing/other", Dressing.MODE_PER_RUN))


## What a dressed building looks like, for comparing runs: furniture conditions and what is
## missing, lights, picks, the run decals and the builder's scatter.
func _look(pd: PoiDef, mode: int, world_seed: int, id: StringName) -> String:
	var dressed: PoiDef = Dressing.resolve(pd, Dressing.roll(pd, Dressing.dressing_seed(world_seed, id, mode)) if mode == Dressing.MODE_PER_RUN else {},
		{"mode": mode, "seed": Dressing.dressing_seed(world_seed, id, mode)})
	var l: PoiLayout = PoiLayout.compile(dressed)
	var parts: Array = [dressed.dressing.get("picks", {}), l.lights.size()]
	for p: Dictionary in l.props:
		parts.append("%s:%s" % [p.get("prop"), p.get("variant", "")])
	parts.append(Dressing.run_decals(l))
	return JSON.stringify(parts)


func test_same_seed_same_building_new_run_different_building() -> void:
	var pd: PoiDef = Content.get_def(&"poi", &"okafor_farmhouse")
	var id := &"okafor_farm/house"
	var a: String = _look(pd, Dressing.MODE_PER_RUN, 4471, id)
	assert_eq(a, _look(pd, Dressing.MODE_PER_RUN, 4471, id), "same seed, same dressing")
	var differ: int = 0
	for ws: int in [1, 2, 3, 4, 5]:
		if _look(pd, Dressing.MODE_PER_RUN, ws, id) != a:
			differ += 1
	assert_eq(differ, 5, "every other run dresses it differently")
	assert_eq(_look(pd, Dressing.MODE_LEGACY, 1, id), _look(pd, Dressing.MODE_LEGACY, 2, id), "legacy dressing ignores the world seed")


func test_the_builder_scatter_follows_the_dressing() -> void:
	var pd: PoiDef = Content.get_def(&"poi", &"merrow_house")
	var id := &"test/merrow"
	var sig := func(ws: int, mode: int) -> String:
		var dressed: PoiDef = Dressing.resolve(pd, {}, {"mode": mode, "seed": Dressing.dressing_seed(ws, id, mode)})
		var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(dressed), id)
		var parts: PackedStringArray = []
		for c: Node in inst.get_children():
			if c is MultiMeshInstance3D:
				var mm: MultiMesh = (c as MultiMeshInstance3D).multimesh
				parts.append("%s:%d" % [c.name, mm.instance_count])
				if mm.instance_count > 0:
					parts.append(str(mm.get_instance_transform(mm.instance_count - 1).origin.snapped(Vector3.ONE * 0.01)))
			elif c is Decal:
				parts.append("decal:%s" % (c as Decal).position.snapped(Vector3.ONE * 0.01))
		inst.free()
		return ",".join(parts)
	var legacy: String = sig.call(4471, Dressing.MODE_LEGACY)
	var undressed: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), id)
	var parts0: PackedStringArray = []
	for c: Node in undressed.get_children():
		if c is MultiMeshInstance3D:
			var mm0: MultiMesh = (c as MultiMeshInstance3D).multimesh
			parts0.append("%s:%d" % [c.name, mm0.instance_count])
			if mm0.instance_count > 0:
				parts0.append(str(mm0.get_instance_transform(mm0.instance_count - 1).origin.snapped(Vector3.ONE * 0.01)))
		elif c is Decal:
			parts0.append("decal:%s" % (c as Decal).position.snapped(Vector3.ONE * 0.01))
	undressed.free()
	assert_eq(legacy, ",".join(parts0), "a legacy save builds exactly the building it was played in")
	var run_a: String = sig.call(4471, Dressing.MODE_PER_RUN)
	assert_eq(run_a, sig.call(4471, Dressing.MODE_PER_RUN), "same seed, same scatter")
	assert_ne(run_a, sig.call(1234, Dressing.MODE_PER_RUN), "a new run, new scatter, wear and decals")


func test_wear_keeps_stable_ids_seats_and_containers() -> void:
	for pid: StringName in [&"merrow_house", &"okafor_farmhouse", &"mile9_diner", &"pell_trailer"]:
		var pd: PoiDef = Content.get_def(&"poi", pid)
		var base: PoiLayout = PoiLayout.compile(pd)
		var base_ids: Dictionary = {}
		for p: Dictionary in base.props:
			if p.has("id"):
				base_ids[str(p["id"])] = true
		var base_seats: Dictionary = SleeperAnchors.assign(base)["by_sleeper"]
		for ws: int in 12:
			var dressed: PoiDef = Dressing.resolve(pd, {}, {"mode": Dressing.MODE_PER_RUN, "seed": Ids.hash64("wear%d" % ws)})
			var l: PoiLayout = PoiLayout.compile(dressed)
			var ids: Dictionary = {}
			for p2: Dictionary in l.props:
				if p2.has("id"):
					ids[str(p2["id"])] = true
			assert_eq(ids, base_ids, "%s: wear never removes a prop with an id (containers, trigger props)" % pid)
			var seats: Dictionary = SleeperAnchors.assign(l)["by_sleeper"]
			assert_eq(seats.keys(), base_seats.keys(), "%s: every seated sleeper keeps its seat" % pid)
			assert_eq(l.sleepers.size(), base.sleepers.size())
			assert_eq(l.traps.size(), base.traps.size())


func test_dress_for_pins_the_picks_of_a_run() -> void:
	var pd: PoiDef = _def(_two_rooms({"alternatives": [{"id": "back", "options": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "e"}]}]}))
	var session: GameSession = GameSession.create_new({"seed": 77})
	var first: PoiDef = PoiManager.dress_for(pd, &"town/lot", session)
	var pinned: Dictionary = session.world.poi_state(&"town/lot").get("picks", {})
	assert_eq(pinned, first.dressing["picks"], "the picks are pinned in the saved state")
	# Another seed would roll differently; the pinned picks win for this run.
	session.world_seed = 78
	for i: int in 5:
		session.world_seed = 78 + i
		assert_eq(PoiManager.dress_for(pd, &"town/lot", session).dressing["picks"], pinned, "the run keeps its rooms")
	session.world.poi_dressing = Dressing.MODE_LEGACY
	var legacy: PoiDef = PoiManager.dress_for(Content.get_def(&"poi", &"merrow_house"), &"pell_crossing/merrow", session)
	assert_eq(int(legacy.dressing["mode"]), Dressing.MODE_LEGACY)
	assert_eq(JSON.stringify(legacy.layout.get("props")), JSON.stringify(PoiLayout.compile(Content.get_def(&"poi", &"merrow_house")).def.layout.get("props")),
		"a legacy world builds the authored defaults")


# --- Save v5 ------------------------------------------------------------------------------------------

func test_v4_saves_keep_legacy_dressing() -> void:
	var v4: Dictionary = {"save_version": 4, "session": {"world": {"pois": {"pell_crossing/merrow": {"visited": true}}, "mounds": {}}}}
	var out: Dictionary = SaveSystem.migrate(v4)
	assert_eq(int(out["save_version"]), SaveSystem.CURRENT_VERSION)
	assert_eq(int(out["session"]["world"]["poi_dressing"]), Dressing.MODE_LEGACY, "an old run keeps the buildings it was played in")
	var w := WorldState.new()
	w.from_dict(out["session"]["world"])
	assert_eq(w.poi_dressing, Dressing.MODE_LEGACY)
	assert_true(bool(w.pois["pell_crossing/merrow"]["visited"]), "POI states are untouched")


func test_new_worlds_dress_per_run_and_round_trip() -> void:
	var s: GameSession = GameSession.create_new({"seed": 5})
	assert_eq(s.world.poi_dressing, Dressing.MODE_PER_RUN)
	var back: GameSession = GameSession.from_dict(JSON.parse_string(JSON.stringify(s.to_dict())))
	assert_eq(back.world.poi_dressing, Dressing.MODE_PER_RUN, "saved and loaded")
	assert_eq(SaveSystem.migrate({"save_version": SaveSystem.CURRENT_VERSION, "session": s.to_dict()})["session"]["world"]["poi_dressing"],
		Dressing.MODE_PER_RUN, "a v5 save is not touched")


# --- Alternatives validation --------------------------------------------------------------------------

func test_alternatives_structure_is_checked() -> void:
	var bad: PoiDef = _def(_two_rooms({
		"alternatives": [
			{"id": "back", "options": [{"id": "a"}]},
			{"id": "doors", "colour": "red", "options": [{"id": "x", "openings": [{"id": "nope", "state": "open"}]}, {"id": "y", "rooms": [{"room": "B", "storeys": 2}]}]}],
		"props": [{"id": "back_dresser", "prop": "dresser", "at": [3, 0], "against": "N", "alt": "back:missing"}]}))
	var v: PoiValidator = PoiValidator.validate(bad)
	var text: String = "\n".join(v.errors)
	assert_string_contains(text, "needs at least two options")
	assert_string_contains(text, "unknown key 'colour'")
	assert_string_contains(text, "opening 'nope' not found")
	assert_string_contains(text, "not 'storeys'")
	assert_string_contains(text, "alt 'back:missing' names no group:option")


func test_every_option_is_validated_against_the_base() -> void:
	# The barricaded option seals the only way in: the route breaks in that variant only.
	var d: PoiDef = _def(_two_rooms({"alternatives": [{"id": "front", "options": [{"id": "shut"},
		{"id": "nailed", "openings": [{"id": "front_door", "state": "barricaded"}]}]}]}))
	var v: PoiValidator = PoiValidator.validate(d)
	assert_gt(v.errors.size(), 0)
	assert_string_contains("\n".join(v.errors), "[alt front=nailed]")
	assert_eq(int(v.stats.get("variants", 0)), 2, "the base and the one other option")


func test_an_option_that_seals_the_shortcut_is_an_error() -> void:
	var d: PoiDef = _def(_two_rooms({"alternatives": [{"id": "exit", "options": [{"id": "bolt"},
		{"id": "boarded", "openings": [{"id": "back_door", "state": "barricaded"}]}]}]}))
	var v: PoiValidator = PoiValidator.validate(d)
	assert_string_contains("\n".join(v.errors), "shortcut 'back_door' can no longer be used from inside")


func test_combinations_cover_singles_and_sample_the_rest() -> void:
	var groups: Array = []
	for g: int in 5:
		groups.append({"id": "g%d" % g, "options": [{"id": "a"}, {"id": "b"}, {"id": "c"}]})
	var d: PoiDef = _def(_two_rooms({"alternatives": groups}))
	var combos: Array[Dictionary] = Dressing.combinations(d, 16)
	assert_eq(combos[0], Dressing.default_picks(d), "the base first")
	# 1 base + 5 groups x 2 other options, then a sample of 16 full combinations (3^5 = 243 > 16).
	assert_eq(combos.size(), 1 + 10 + 16)
	var keys: Dictionary = {}
	for c: Dictionary in combos:
		keys[JSON.stringify(c)] = true
	assert_eq(keys.size(), combos.size(), "no combination twice")
	var small: PoiDef = _def(_two_rooms({"alternatives": [{"id": "x", "options": [{"id": "a"}, {"id": "b"}]}, {"id": "y", "options": [{"id": "a"}, {"id": "b"}]}]}))
	assert_eq(Dressing.combinations(small, 16).size(), 4, "small sets are tried in full")


func test_retrofitted_buildings_have_real_alternatives() -> void:
	for pid: StringName in [&"merrow_house", &"mile9_diner", &"okafor_farmhouse", &"pell_trailer"]:
		var pd: PoiDef = Content.get_def(&"poi", pid)
		assert_true(Dressing.has_alternatives(pd), "%s has alternatives" % pid)
		var opts: int = 0
		for g: Dictionary in Dressing.groups(pd):
			opts += Dressing.options(g).size() - 1
		assert_gt(opts, 3, "%s: more than a token choice" % pid)
		var v: PoiValidator = PoiValidator.validate(pd)
		assert_eq(v.errors, PackedStringArray(), "%s: every alternative validates" % pid)
		assert_eq(v.warnings, PackedStringArray(), "%s: and warns about nothing" % pid)
