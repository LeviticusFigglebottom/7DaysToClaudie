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


func test_chunk_keys_with_colons_use_safe_file_names() -> void:
	var s: GameSession = _make_session()
	s.world.chunk_blobs["t:-3_5"] = PackedByteArray([9, 8, 7])
	s.world.chunk_blobs["v:1_-2_0"] = PackedByteArray([1])
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	for f: String in DirAccess.get_files_at(SaveSystem.slot_dir(SLOT).path_join("chunks")):
		assert_false(f.contains(":"), "no ':' in %s (Windows can't store it)" % f)
	var loaded: GameSession = SaveSystem.load_session(SLOT)
	assert_eq(loaded.world.chunk_blobs.get("t:-3_5"), PackedByteArray([9, 8, 7]), "key restored with its ':'")
	assert_eq(loaded.world.chunk_blobs.get("v:1_-2_0"), PackedByteArray([1]))


func test_damaged_save_falls_back_to_the_previous_one() -> void:
	var s: GameSession = _make_session()
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	# Simulate a swap interrupted after the old save was moved aside and the new one was lost.
	var dir: String = SaveSystem.slot_dir(SLOT)
	assert_eq(DirAccess.rename_absolute(dir, dir + ".old"), OK)
	DirAccess.make_dir_recursive_absolute(dir)
	var f := FileAccess.open(dir.path_join("session.json"), FileAccess.WRITE)
	f.store_string("{ truncated")
	f.close()
	assert_true(SaveSystem.slot_exists(SLOT))
	var loaded: GameSession = SaveSystem.load_session(SLOT)
	assert_not_null(loaded, "the previous save loads")
	assert_eq(loaded.clock.day(), s.clock.day())
	assert_eq(SaveSystem.last_error, "")
	SaveSystem.delete_slot(SLOT)
	assert_false(DirAccess.dir_exists_absolute(dir + ".old"), "deleting a slot takes its backup too")


func test_unreadable_save_reports_why() -> void:
	var dir: String = SaveSystem.slot_dir(SLOT)
	DirAccess.make_dir_recursive_absolute(dir)
	var f := FileAccess.open(dir.path_join("session.json"), FileAccess.WRITE)
	f.store_string("not json")
	f.close()
	assert_null(SaveSystem.load_session(SLOT))
	assert_ne(SaveSystem.last_error, "")
	assert_push_error_count(1, "the damaged slot is logged")


func test_new_runs_get_their_own_slot() -> void:
	var a: String = SaveSystem.new_run_slot()
	assert_true(a.begins_with("run"))
	var s: GameSession = _make_session()
	assert_eq(SaveSystem.save_session(s, a), OK)
	var b: String = SaveSystem.new_run_slot()
	assert_ne(a, b, "a second run never reuses the first run's slot")
	SaveSystem.delete_slot(a)


func test_no_saving_while_dead() -> void:
	var prev: GameSession = Game.session
	var s: GameSession = _make_session()
	Game.session = s
	Game.current_slot = SLOT
	s.local_player().stats.alive = false
	assert_false(Game.save_game(), "a dead player's state is not saved")
	assert_false(SaveSystem.slot_exists(SLOT))
	s.local_player().stats.alive = true
	assert_true(Game.save_game())
	Game.session = prev
