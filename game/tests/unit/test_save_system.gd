extends GutTest

const SLOT: String = "unit_test_slot"


func after_each() -> void:
	SaveSystem.delete_slot(SLOT)


## JSON has a single number type, so compare both sides after a JSON pass.
static func _norm(d: Dictionary) -> String:
	return JSON.stringify(JSON.parse_string(JSON.stringify(d)), "", true)


func _make_session() -> GameSession:
	var s: GameSession = GameSession.create_new({"seed": 1234, "game_mode": "slice"})
	var p: PlayerState = s.local_player()
	p.position = Vector3(12.5, 40.25, -3.0)
	p.inventory.add_item(&"stone_axe", 1, 2)
	p.inventory.add_item(&"stick", 7)
	p.stats.add_wound(0.2, 10.0)
	p.progression.add_xp(900)
	s.clock.advance_minutes(777.0)
	s.ids.next("z")
	s.rng.stream("loot").randi()
	s.world.structures["s:000001"] = {"def": "log_piece", "pos": [1, 2, 3], "rot": [0, 0, 0, 1], "hp": 300.0}
	s.world.set_tree_state("3_4", 17, {"state": "stump", "day": 1})
	s.world.chunk_blobs["3_4"] = PackedByteArray([1, 2, 3, 250])
	s.horde.record_night({"spawned": [5, 5, 5, 5, 5, 5, 5, 5], "killed": [5, 1, 1, 1, 1, 1, 1, 1], "breaches": [0, 1, 1, 1, 1, 1, 1, 1], "causes": {"melee": 12}, "clear_time": 0.5})
	s.heat.add(Vector3(10, 0, 10), 22.0)
	return s


func test_round_trip_preserves_everything() -> void:
	var s: GameSession = _make_session()
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var loaded: GameSession = SaveSystem.load_session(SLOT)
	assert_not_null(loaded)
	assert_eq(_norm(loaded.to_dict()), _norm(s.to_dict()))
	assert_eq(loaded.world.chunk_blobs.get("3_4"), PackedByteArray([1, 2, 3, 250]))


func test_overwrite_is_atomic_and_listed() -> void:
	var s: GameSession = _make_session()
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	s.clock.advance_minutes(1440.0)
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var slots: Array[Dictionary] = SaveSystem.list_slots()
	var mine: Array = slots.filter(func(m: Dictionary) -> bool: return m.get("slot") == SLOT)
	assert_eq(mine.size(), 1)
	assert_eq(int(mine[0]["day"]), s.clock.day())
	assert_false(DirAccess.dir_exists_absolute(SaveSystem.slot_dir(SLOT) + ".tmp"))
	assert_false(DirAccess.dir_exists_absolute(SaveSystem.slot_dir(SLOT) + ".old"))


func test_migration_chain_runs_in_order() -> void:
	var steps: Dictionary = {
		0: func(d: Dictionary) -> Dictionary: d["session"]["renamed"] = d["session"].get("old_name", ""); return d,
		1: func(d: Dictionary) -> Dictionary: d["session"]["v2_flag"] = true; return d,
	}
	var out: Dictionary = SaveSystem.migrate({"save_version": 0, "session": {"old_name": "x"}}, 2, steps)
	assert_eq(int(out["save_version"]), 2)
	assert_eq(out["session"]["renamed"], "x")
	assert_true(out["session"]["v2_flag"])


func test_migration_refuses_newer_or_gapped_saves() -> void:
	assert_eq(SaveSystem.migrate({"save_version": 99, "session": {}}, 1, {0: func(d: Dictionary) -> Dictionary: return d}), {})
	assert_eq(SaveSystem.migrate({"save_version": 0, "session": {}}, 2, {0: func(d: Dictionary) -> Dictionary: return d}), {})
	assert_push_error_count(2, "newer + gapped saves are reported")


func test_unknown_items_are_dropped_not_fatal() -> void:
	var s: GameSession = _make_session()
	var d: Dictionary = s.to_dict()
	d["players"]["p:1"]["inventory"]["stacks"].append({"id": "item_removed_in_patch", "n": 3})
	var restored: GameSession = GameSession.from_dict(JSON.parse_string(JSON.stringify(d)))
	assert_eq(restored.local_player().inventory.count_of(&"item_removed_in_patch"), 0)
	assert_eq(restored.local_player().inventory.count_of(&"stick"), 7)
