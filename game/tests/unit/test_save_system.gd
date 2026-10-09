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


func test_v1_saves_keep_stumps_and_drop_harvested_plants() -> void:
	var trees: Dictionary = {
		"3_4": {"12": {"state": "stump", "day": 2}, "301": {"state": "harvested", "day": 3, "regrow": 0.0}},
		"5_5": {"700": {"state": "harvested", "day": 1, "regrow": 2.0}},
	}
	var out: Dictionary = SaveSystem.migrate({"save_version": 1, "session": {"world": {"trees": trees}}})
	assert_eq(int(out["save_version"]), SaveSystem.CURRENT_VERSION)
	var got: Dictionary = out["session"]["world"]["trees"]
	assert_eq(got.keys(), ["3_4"], "chunks left with nothing are dropped")
	assert_eq((got["3_4"] as Dictionary).keys(), ["12"], "felled trees keep their stumps")


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


func test_a_lone_backup_still_lists() -> void:
	var s: GameSession = _make_session()
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var dir: String = SaveSystem.slot_dir(SLOT)
	assert_eq(DirAccess.rename_absolute(dir, dir + ".old"), OK, "only the backup is left")
	var mine: Array = SaveSystem.list_slots().filter(func(m: Dictionary) -> bool: return m.get("slot") == SLOT)
	assert_eq(mine.size(), 1, "listed under its own name")
	assert_not_null(SaveSystem.load_session(SLOT), "and loadable")


# --- Save v7: the generator version and the world bundle (RWG v2 §5) ---------------------------

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")


func _gen(seed: int) -> Dictionary:
	var s: RefCounted = GenSettings.from_dict({"seed": seed, "values": {"size": 2}})
	return s.call(&"to_dict")


func test_v6_random_save_gets_its_generator_version_from_its_id() -> void:
	var gen: Dictionary = _gen(4242)
	var settings: RefCounted = GenSettings.from_dict(gen)
	var old_id: String = Generator.world_id_for_version(settings, 2)
	var out: Dictionary = SaveSystem.migrate({"save_version": 6, "session": {"world_mode": "random", "world_gen": gen, "world_id": old_id,
		"world": {"traders": {"t": {"stock": 1}}, "ashen": {"camps": {"a1": {"alive": 3}}}}, "players": {"p:1": {"contracts": [{"id": "c1"}]}}}})
	assert_eq(int(out["save_version"]), 7)
	assert_eq(int(out["session"]["generator_version"]), 2, "the version whose hash is the id")
	assert_eq(out["session"]["world_files"], "shared")
	assert_eq(out["session"]["world"]["traders"], {"t": {"stock": 1}}, "traders carry through")
	assert_eq(out["session"]["world"]["ashen"], {"camps": {"a1": {"alive": 3}}}, "a key the migration doesn't know (the Ashen, ADR-0048) carries through")
	assert_eq(out["session"]["players"]["p:1"]["contracts"], [{"id": "c1"}], "contracts carry through")
	var odd: Dictionary = SaveSystem.migrate({"save_version": 6, "session": {"world_mode": "random", "world_gen": gen, "world_id": "rwg_000000000000"}})
	assert_eq(int(odd["session"]["generator_version"]), 1, "an id no version makes counts as generator 1")


func test_v6_main_map_save_only_changes_version() -> void:
	var out: Dictionary = SaveSystem.migrate({"save_version": 6, "session": {"world_mode": "main_map", "world_gen": {}}})
	assert_eq(int(out["save_version"]), 7)
	assert_false(out["session"].has("generator_version"))
	assert_eq(SaveSystem.migrate({"save_version": 8, "session": {}}), {}, "a v8 save is refused")
	assert_push_error_count(1, "and reported")


func test_a_new_random_run_records_the_generator_version() -> void:
	var s: GameSession = GameSession.create_new({"world_gen": _gen(77), "seed": 1})
	assert_eq(s.generator_version, Generator.VERSION)
	assert_eq(GameSession.from_dict(s.to_dict()).generator_version, Generator.VERSION)
	assert_eq(GameSession.create_new({}).generator_version, 0, "none on the main map")


func test_the_bundle_restores_a_deleted_world_folder_byte_for_byte() -> void:
	var s: GameSession = GameSession.create_new({"world_gen": _gen(31337), "seed": 1})
	var dir: String = SaveSystem.WORLDS_ROOT.path_join(String(s.world_id))
	SaveSystem._remove_recursive(dir)
	# A stand-in world folder: the bundle copies files, whatever they hold.
	DirAccess.make_dir_recursive_absolute(dir.path_join("regions/r0"))
	var files: Dictionary = {"world.json": "{\"w\": 1}", "frameworks.json": "{}", "meta.json": "{\"key\": 1}", "regions/r0/region.json": "{\"r\": 0}", "map.png": "png"}
	for rel: String in files:
		var f := FileAccess.open(dir.path_join(rel), FileAccess.WRITE)
		f.store_string(files[rel])
		f.close()
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	var zip: String = SaveSystem.slot_dir(SLOT).path_join(SaveSystem.bundle_name(String(s.world_id)))
	assert_true(FileAccess.file_exists(zip), "the slot has its world bundle")
	# A second save carries the bundle over even with the folder gone.
	SaveSystem._remove_recursive(dir)
	assert_eq(SaveSystem.save_session(s, SLOT), OK)
	assert_true(FileAccess.file_exists(zip), "carried from the previous save")
	var meta: Dictionary = SaveSystem.list_slots().filter(func(m: Dictionary) -> bool: return m.get("slot") == SLOT)[0]
	assert_eq(SaveSystem.world_warning(meta), "", "no warning: the bundle has the world")
	var loaded: GameSession = SaveSystem.load_session(SLOT)
	assert_not_null(loaded)
	assert_eq(loaded.world_files, &"slot", "restored from the slot")
	for rel2: String in files:
		if rel2 == "map.png":
			assert_false(FileAccess.file_exists(dir.path_join(rel2)), "the map is not bundled")
			continue
		assert_eq(FileAccess.get_file_as_string(dir.path_join(rel2)), files[rel2], "%s restored" % rel2)
	SaveSystem._remove_recursive(dir)
	SaveSystem.delete_slot(SLOT)
	assert_ne(SaveSystem.world_warning(meta), "", "folder and bundle both gone: the menu warns")


class FakeWorldDef:
	extends RefCounted
	var towns: Array[Dictionary] = [{"id": "t", "center": Vector2(500, 500), "radius": 200.0, "bounds": Rect2(300, 300, 400, 400)}]


func test_a_pre_12_random_run_drops_town_vegetation_records() -> void:
	# TD-182: composer 12 re-scattered towns' vegetation; their per-index records point elsewhere.
	var s: GameSession = GameSession.create_new({"world_gen": _gen(5), "seed": 1})
	s.composer_version = 11
	s.world.set_tree_state(Ids.chunk_key(7, 7), 3, {"state": "stump", "day": 1})    # 448..512: in the town
	s.world.set_tree_state(Ids.chunk_key(0, 0), 5, {"state": "stump", "day": 1})    # far away
	s.world.set_tree_state(Ids.chunk_key(2, 7), 1, {"state": "stump", "day": 1})    # 128..192 x: outside the disc
	var n: int = SaveSystem.fix_composer_changes(s, FakeWorldDef.new(), 12)
	assert_eq(n, 1)
	assert_false(s.world.trees.has(Ids.chunk_key(7, 7)), "the town chunk's records are dropped")
	assert_true(s.world.trees.has(Ids.chunk_key(0, 0)))
	assert_true(s.world.trees.has(Ids.chunk_key(2, 7)))
	assert_eq(s.composer_version, 12, "recorded")
	assert_eq(SaveSystem.fix_composer_changes(s, FakeWorldDef.new(), 12), 0, "once only")
	var main: GameSession = GameSession.create_new({})
	main.composer_version = 0
	main.world.set_tree_state(Ids.chunk_key(7, 7), 3, {"state": "stump", "day": 1})
	assert_eq(SaveSystem.fix_composer_changes(main, FakeWorldDef.new(), 12), 0, "the main map is unchanged")
	assert_eq(GameSession.from_dict(s.to_dict()).composer_version, 12, "saved")


class FakeRoadWorldDef:
	extends RefCounted
	var towns: Array[Dictionary] = []
	var roads: Array[Dictionary] = [{"id": "r", "line": Polyline2.from_array([[0.0, 1000.0], [2000.0, 1000.0]])}]


func test_crossing_composer_13_drops_records_by_changed_roads() -> void:
	# Composer 13 (player report 4): a generated world's roads bank into the land, which moves the
	# scatter beside them; records there point elsewhere. The main map's roads did not change.
	var s: GameSession = GameSession.create_new({"world_gen": _gen(5), "seed": 1})
	s.composer_version = 12
	s.world.set_tree_state(Ids.chunk_key(10, 15), 3, {"state": "stump", "day": 1})    # z 960..1024: on the road
	s.world.set_tree_state(Ids.chunk_key(10, 2), 5, {"state": "stump", "day": 1})     # z 128..192: far from it
	assert_eq(SaveSystem.fix_composer_changes(s, FakeRoadWorldDef.new(), 13), 1)
	assert_false(s.world.trees.has(Ids.chunk_key(10, 15)), "the chunk by the road is dropped")
	assert_true(s.world.trees.has(Ids.chunk_key(10, 2)), "a chunk far from it is kept")
	assert_eq(s.composer_version, 13)
	var main: GameSession = GameSession.create_new({})
	main.composer_version = 12
	main.world.set_tree_state(Ids.chunk_key(10, 15), 3, {"state": "stump", "day": 1})
	assert_eq(SaveSystem.fix_composer_changes(main, FakeRoadWorldDef.new(), 13), 0, "the main map's roads are graded as before")
