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
