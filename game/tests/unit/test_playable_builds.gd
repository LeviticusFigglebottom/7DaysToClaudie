extends GutTest
## Playable builds (ADR-0036): the menu's startup notices, the pinned engine version kept in step
## with tools/versions.env, and a POI built with a validator run elsewhere (the load runs it on a
## worker thread) matching one built the old way.

const MainMenu := preload("res://src/app/main.gd")


func test_no_notice_for_a_full_build_on_the_pinned_engine() -> void:
	assert_eq(MainMenu.startup_notices(1.0, MainMenu.PINNED_GODOT).size(), 0)


func test_stand_ins_and_partial_builds_are_announced() -> void:
	var none: PackedStringArray = MainMenu.startup_notices(0.0, MainMenu.PINNED_GODOT)
	assert_eq(none.size(), 1)
	assert_true(none[0].begins_with("Placeholder world"))
	var part: PackedStringArray = MainMenu.startup_notices(0.4, MainMenu.PINNED_GODOT)
	assert_eq(part.size(), 1)
	assert_string_contains(part[0], "40%")


func test_another_engine_version_is_announced() -> void:
	var n: PackedStringArray = MainMenu.startup_notices(1.0, "4.7.1")
	assert_eq(n.size(), 1)
	assert_string_contains(n[0], "Godot 4.7.1")
	assert_string_contains(n[0], MainMenu.PINNED_GODOT)


func test_pinned_version_matches_versions_env() -> void:
	var path: String = ProjectSettings.globalize_path("res://").path_join("../tools/versions.env")
	var text: String = FileAccess.get_file_as_string(path)
	assert_ne(text, "", "tools/versions.env readable")
	var re := RegEx.create_from_string("(?m)^GODOT_VERSION=(\\S+)$")
	var m: RegExMatch = re.search(text)
	assert_not_null(m)
	if m != null:
		assert_eq(m.get_string(1), MainMenu.PINNED_GODOT)


func test_this_engine_is_the_pinned_one() -> void:
	assert_eq(MainMenu.engine_version(), MainMenu.PINNED_GODOT)


func test_a_precomputed_check_builds_the_same_building() -> void:
	var pd: PoiDef = Content.get_def(&"poi", &"larch_hollow_sawmill") as PoiDef
	assert_not_null(pd)
	if pd == null:
		return
	var a := PoiLayout.compile(pd)
	var v := PoiValidator.new()
	v.layout = a
	var task: int = WorkerThreadPool.add_task(v._run)
	WorkerThreadPool.wait_for_task_completion(task)
	var with_check: PoiInstance = PoiBuilder.build(a, &"test/precheck", v)
	var plain: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), &"test/precheck")
	assert_eq(_census(with_check), _census(plain))
	with_check.free()
	plain.free()


## Node count per class: the same building built twice has the same parts.
func _census(root: Node) -> Dictionary:
	var out: Dictionary = {}
	for n: Node in root.find_children("*", "", true, false):
		out[n.get_class()] = int(out.get(n.get_class(), 0)) + 1
	return out


# --- Run seeds and the map label (bugs found while writing docs/HOW_TO_PLAY.md) ---------------------

func test_a_text_run_seed_hashes_like_the_map_seed() -> void:
	assert_eq(NewGamePanel.run_seed_from_text(" 90210 "), 90210, "a whole number is itself")
	assert_eq(NewGamePanel.run_seed_from_text("-7"), -7)
	assert_eq(NewGamePanel.run_seed_from_text("larch"), Ids.hash31("larch"), "text hashes as the map seed does")
	assert_ne(NewGamePanel.run_seed_from_text("larch"), NewGamePanel.run_seed_from_text("pell"))
	assert_ne(NewGamePanel.run_seed_from_text("larch"), MainMenu.SLICE_DEMO_SEED, "never the old silent 4471")
	var fresh: int = NewGamePanel.run_seed_from_text("  ")
	assert_between(fresh, 100000, 999999, "an empty field rolls a fresh run")


func test_new_game_without_a_seed_is_fresh_except_the_slice_demo() -> void:
	assert_eq(MainMenu.cli_default_seed("slice", false), MainMenu.SLICE_DEMO_SEED, "the slice is the curated demo run")
	assert_eq(MainMenu.SLICE_DEMO_SEED, GameSession.create_new({}).world_seed, "the run smoke and the QA shots play")
	var seen: Dictionary = {}
	for i: int in 8:
		var s: int = MainMenu.cli_default_seed("survival", false)
		assert_between(s, 100000, 999999)
		seen[s] = true
		assert_between(MainMenu.cli_default_seed("slice", true), 100000, 999999, "a random world is never the demo run")
	assert_gt(seen.size(), 1, "survival rolls a fresh run each time")


func test_the_main_map_label_names_what_is_built() -> void:
	var j := JSON.new()
	assert_eq(j.parse(FileAccess.get_file_as_string("res://world/main_map/world.json")), OK)
	var built: int = 0
	for r: Variant in (j.data as Dictionary).get("regions", []):
		if str((r as Dictionary).get("status", "")) == "built":
			built += 1
			assert_string_contains(NewGamePanel.MAIN_MAP_LABEL, str((r as Dictionary)["name"]))
	assert_eq(built, 1, "one region built: the label says 1 x 1 km (update it when another is built)")
	assert_false(NewGamePanel.MAIN_MAP_LABEL.contains("7 x 7"), "the planned size is not what is built")
