extends GutTest
## Trailer shot defs (data/trailer): every shot parses and covers its recording with camera keys,
## the recorded length is the cut's plus the tail, the camera path passes through its keys and
## eases in and out, and malformed shots are refused with a reason.

const CUT_IDS: PackedStringArray = ["dawn_drone", "lift3_wreck", "birch_walk", "fen_dusk", "hot_springs", "pell_crane",
	"pharmacy_torch", "tether_map", "fell_tree", "log_carry", "shelter_timelapse", "craft_bow", "boil_water", "ezra_ladder",
	"treeline_night", "keener_sprint", "ashen_camp", "hum_tether", "horde_overhead", "combat_club", "combat_bow",
	"rammer_breach", "collapse", "dawn_shelter"]


func _parse(d: Dictionary) -> Array:
	var def := TrailerShotDef.new()
	var errs: PackedStringArray = def.parse(d, &"trailer_shot", "test.json")
	return [def, errs]


func _shot(extra: Dictionary = {}) -> Dictionary:
	var d: Dictionary = {"id": "t", "anchor": [0, 0], "dur": 2.0, "camera": {"keys": [
		{"t": 0.0, "pos": [0, 10, 10], "look": [0, 0, 0], "fov": 50},
		{"t": 1.0, "pos": [10, 10, 0], "look": [0, 0, 0], "fov": 60},
		{"t": 2.5, "pos": [0, 20, -10], "look": [0, 0, 0], "fov": 70}]}}
	d.merge(extra, true)
	return d


func test_every_shot_is_a_clip_of_the_cut_and_valid() -> void:
	var shots: Array = Content.all(&"trailer_shot")
	assert_gte(shots.size(), 3, "the first three shots")
	for s: TrailerShotDef in shots:
		assert_true(CUT_IDS.has(String(s.id)), "%s is a clip id of the cut" % s.id)
		assert_gte(float(s.keys[-1]["t"]), s.dur + s.tail - 0.001, "%s: the camera covers the recording" % s.id)
		assert_true(Content.has_def(&"weather", s.weather), "%s weather" % s.id)


func test_frames_cover_dur_plus_tail() -> void:
	var r: Array = _parse(_shot())
	assert_eq((r[1] as PackedStringArray).size(), 0, str(r[1]))
	var s: TrailerShotDef = r[0]
	assert_eq(s.frame_count(30), 75, "2 s + 0.5 s tail at 30 fps")


func test_camera_passes_through_keys_and_eases() -> void:
	var s: TrailerShotDef = _parse(_shot({"camera": {"ease": "linear", "keys": [
		{"t": 0.0, "pos": [0, 10, 10], "look": [0, 0, 0], "fov": 50},
		{"t": 1.0, "pos": [10, 10, 0], "look": [0, 0, 0], "fov": 60},
		{"t": 2.5, "pos": [0, 20, -10], "look": [0, 0, 0], "fov": 70}]}}))[0]
	assert_almost_eq((s.camera_at(0.0)["pos"] as Vector3).distance_to(Vector3(0, 10, 10)), 0.0, 0.001)
	assert_almost_eq((s.camera_at(1.0)["pos"] as Vector3).distance_to(Vector3(10, 10, 0)), 0.0, 0.001)
	assert_almost_eq((s.camera_at(2.5)["pos"] as Vector3).distance_to(Vector3(0, 20, -10)), 0.0, 0.001)
	assert_almost_eq(float(s.camera_at(1.0)["fov"]), 60.0, 0.001)
	var eased: TrailerShotDef = _parse(_shot())[0]
	var p0: Vector3 = eased.camera_at(0.0)["pos"]
	var early: float = (eased.camera_at(0.1)["pos"] as Vector3).distance_to(p0)
	var mid: float = (eased.camera_at(1.3)["pos"] as Vector3).distance_to(eased.camera_at(1.2)["pos"])
	assert_lt(early, mid, "in_out starts slowly")


func test_malformed_shots_are_refused() -> void:
	var cases: Dictionary = {
		"short path": _shot({"camera": {"keys": [{"t": 0.0, "pos": [0, 1, 0], "look": [0, 0, 1]}, {"t": 1.0, "pos": [0, 2, 0], "look": [0, 0, 1]}]}}),
		"keys out of order": _shot({"camera": {"keys": [{"t": 0.0, "pos": [0, 1, 0], "look": [0, 0, 1]}, {"t": 3.0, "pos": [0, 2, 0], "look": [0, 0, 1]}, {"t": 2.0, "pos": [0, 3, 0], "look": [0, 0, 1]}]}}),
		"bad action": _shot({"actions": [{"t": 0.5, "do": "explode"}]}),
		"action before the lead": _shot({"lead": 1.0, "actions": [{"t": -2.0, "do": "hum"}]}),
		"unknown field": _shot({"camra": {}}),
		"no anchor": _shot({"anchor": 5}),
	}
	for name: String in cases:
		assert_gt((_parse(cases[name])[1] as PackedStringArray).size(), 0, name)


func test_unknown_enemy_and_weather_fail_validation() -> void:
	var s: TrailerShotDef = _parse(_shot({"weather": "hail", "actions": [{"t": 0.0, "do": "spawn", "enemy": "dragon"}]}))[0]
	var out: PackedStringArray = []
	s._validate(Content, out)
	assert_eq(out.size(), 2, str(out))
