extends GutTest
## The composed-region disk cache (ADR-0038): RegionTerrain.save writes beside the file and
## renames it over, so a reader never sees half a file; load_cached treats any short, truncated or
## damaged file as a miss (never an engine error); a leftover temporary file is ignored; and the LRU
## index trims detail (1 m) files to a budget, least recently used first across worlds, never a
## coarse (16 m) file and never the file just written.

const Cache := preload("res://src/worldgen/region_cache.gd")
const ROOT: String = "user://test_region_cache"


func before_each() -> void:
	_remove(ROOT)
	DirAccess.make_dir_recursive_absolute(ROOT)


func after_all() -> void:
	_remove(ROOT)


## A small synthetic region (256 m at 8 m: 33 x 33 samples) with a lake, a pad and a path.
func _region() -> RegionTerrain:
	var w := WorldDef.new()
	w.id = "region_cache_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.macro_noise_cfg = {"amplitude": 0.0, "ridged_amplitude": 0.0}
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var c: Vector2 = w.region_rect("t").get_center()
	w._region_cache["t"] = {"default_biome": "meadow", "features": [
		{"type": "lake", "id": "l", "ellipse": [c.x + 30.0, c.y, 25.0, 20.0, 0.0], "level": -1.0, "depth": 3.0, "shore": 8.0},
		{"type": "poi", "id": "p", "poi": "larch_pond_boathouse", "origin": [c.x - 60.0, c.y - 10.0], "rotation": 15, "size": [20, 16]},
		{"type": "path", "id": "trail", "points": [[c.x - 100.0, c.y + 50.0], [c.x, c.y + 40.0], [c.x + 90.0, c.y + 70.0]], "width": 2.0}]}
	return TerrainComposer.compose(w, "t", 8.0)


func _same(a: RegionTerrain, b: RegionTerrain) -> bool:
	return a.height.content_hash() == b.height.content_hash() and a.splat0 == b.splat0 and a.splat1 == b.splat1 \
		and a.biome == b.biome and a.vegmask == b.vegmask and JSON.stringify(a.placements) == JSON.stringify(b.placements)


func test_save_renames_into_place_and_round_trips() -> void:
	var rt: RegionTerrain = _region()
	var path: String = ROOT.path_join("w/t_800.bin")
	assert_eq(rt.save(path, "hash-1"), OK)
	var back: RegionTerrain = RegionTerrain.load_cached(path, "hash-1")
	assert_not_null(back, "the saved region loads")
	assert_true(back != null and _same(rt, back), "and is the region that was saved")
	assert_null(RegionTerrain.load_cached(path, "hash-2"), "another input hash is a miss")
	for f: String in DirAccess.get_files_at(path.get_base_dir()):
		assert_false(f.ends_with(".tmp"), "no temporary file is left behind (%s)" % f)
	# Saving over an existing file replaces it.
	assert_eq(rt.save(path, "hash-2"), OK)
	assert_not_null(RegionTerrain.load_cached(path, "hash-2"))


func test_a_truncated_or_damaged_file_is_a_miss() -> void:
	var rt: RegionTerrain = _region()
	var path: String = ROOT.path_join("w/t_800.bin")
	rt.save(path, "h")
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
	assert_gt(bytes.size(), 200)
	var bad: String = ROOT.path_join("w/bad_800.bin")
	for cut: int in [0, 3, 4, 7, 9, 60, bytes.size() / 3, bytes.size() / 2, bytes.size() - 17, bytes.size() - 1]:
		_write(bad, bytes.slice(0, cut))
		assert_null(RegionTerrain.load_cached(bad, "h"), "a file cut at %d of %d bytes is a miss" % [cut, bytes.size()])
	# The meta block garbled, then the compressed arrays.
	var garbled: PackedByteArray = bytes.duplicate()
	for i: int in range(12, 40):
		garbled[i] = 0x7b
	_write(bad, garbled)
	assert_null(RegionTerrain.load_cached(bad, "h"), "a damaged header is a miss")
	garbled = bytes.duplicate()
	for i: int in range(bytes.size() - 400, bytes.size() - 8):
		garbled[i] = garbled[i] ^ 0x5a
	_write(bad, garbled)
	assert_null(RegionTerrain.load_cached(bad, "h"), "damaged arrays are a miss")
	_write(bad, "not a region at all".to_utf8_buffer())
	assert_null(RegionTerrain.load_cached(bad, "h"), "a foreign file is a miss")


func test_a_leftover_temporary_file_is_ignored() -> void:
	var rt: RegionTerrain = _region()
	var path: String = ROOT.path_join("w/t_800.bin")
	rt.save(path, "h")
	# What a crash mid-write leaves: half a file under the temporary names.
	var half: PackedByteArray = FileAccess.get_file_as_bytes(path).slice(0, 100)
	_write(path + ".tmp", half)
	_write("%s.%d_%d.tmp" % [path, OS.get_process_id(), OS.get_thread_caller_id()], half)
	var back: RegionTerrain = RegionTerrain.load_cached(path, "h")
	assert_true(back != null and _same(rt, back), "the region still loads from its own file")
	assert_eq(rt.save(path, "h2"), OK, "and saves over the leftovers")
	assert_not_null(RegionTerrain.load_cached(path, "h2"))


func test_detail_and_coarse_files_by_name() -> void:
	assert_true(Cache.is_detail("d6_larch_hollow_100.bin"), "1 m is detail")
	assert_true(Cache.is_detail("user://cache/worlds/x/a1_b_c_400.bin"), "so is 4 m")
	assert_false(Cache.is_detail("d6_larch_hollow_1600.bin"), "16 m is coarse")
	assert_false(Cache.is_detail("index.json"))
	assert_eq(Cache.path_for("w1", "a1_x", 1.0), "user://cache/worlds/w1/a1_x_100.bin", "v1's cache path")


func test_the_lru_trims_detail_files_oldest_first_and_keeps_coarse_ones() -> void:
	var cache: RefCounted = Cache.new()
	cache.set(&"root", ROOT)
	var kb := 1024
	# Two worlds; "saved" stands for a world a save names. Uses at increasing times.
	var files: Array = [["fresh/a1_100.bin", 300, 1000], ["saved/b1_100.bin", 300, 1001], ["saved/b2_100.bin", 300, 1002],
		["fresh/a2_100.bin", 300, 1003], ["saved/b1_1600.bin", 30, 900], ["fresh/a1_1600.bin", 30, 901]]
	for f: Array in files:
		var p: String = ROOT.path_join(str(f[0]))
		_write(p, _bytes(int(f[1]) * kb))
		cache.call(&"wrote", p, PackedStringArray(), int(f[2]))
	# b1 was used again since: it is no longer the oldest.
	cache.call(&"touch", ROOT.path_join("saved/b1_100.bin"), 2000)
	var removed: PackedStringArray = cache.call(&"trim", 650 * kb, PackedStringArray())
	assert_eq(removed, PackedStringArray([ROOT.path_join("fresh/a1_100.bin"), ROOT.path_join("saved/b2_100.bin")]),
		"the least recently used detail files go first, across worlds, until the rest fit")
	for f2: String in ["saved/b1_100.bin", "fresh/a2_100.bin", "saved/b1_1600.bin", "fresh/a1_1600.bin"]:
		assert_true(FileAccess.file_exists(ROOT.path_join(f2)), "%s stays" % f2)
	# Even with no budget at all, coarse files stay, and so does a kept path.
	removed = cache.call(&"trim", 0, PackedStringArray([ROOT.path_join("fresh/a2_100.bin")]))
	assert_eq(removed, PackedStringArray([ROOT.path_join("saved/b1_100.bin")]))
	assert_true(FileAccess.file_exists(ROOT.path_join("fresh/a2_100.bin")), "a kept file stays")
	assert_true(FileAccess.file_exists(ROOT.path_join("saved/b1_1600.bin")) and FileAccess.file_exists(ROOT.path_join("fresh/a1_1600.bin")),
		"coarse files are never evicted (RwgWorlds.prune removes them with their world, keeping saved worlds)")
	var st: Dictionary = cache.call(&"stats")
	assert_eq(int(st["detail_files"]), 1)
	assert_eq(int(st["coarse_files"]), 2)


func test_a_write_trims_to_the_budget_but_never_itself() -> void:
	var cache: RefCounted = Cache.new()
	cache.set(&"root", ROOT)
	cache.set(&"budget_mb", 1)
	var older: String = ROOT.path_join("w/a_100.bin")
	_write(older, _bytes(700 * 1024))
	cache.call(&"wrote", older, PackedStringArray(), 100)
	var newer: String = ROOT.path_join("w/b_100.bin")
	_write(newer, _bytes(700 * 1024))
	var removed: PackedStringArray = cache.call(&"wrote", newer, PackedStringArray(), 200)
	assert_eq(removed, PackedStringArray([older]), "over 1 MB, the older detail file goes")
	assert_true(FileAccess.file_exists(newer), "the file just written stays even when alone over budget")


func test_the_index_is_kept_and_rebuilt_from_the_folders() -> void:
	var cache: RefCounted = Cache.new()
	cache.set(&"root", ROOT)
	var p: String = ROOT.path_join("w/a_100.bin")
	_write(p, _bytes(5000))
	cache.call(&"wrote", p, PackedStringArray(), 123)
	assert_true(FileAccess.file_exists(ROOT.path_join("index.json")), "index.json is written")
	var again: RefCounted = Cache.new()
	again.set(&"root", ROOT)
	assert_eq(int((again.call(&"stats") as Dictionary)["detail_bytes"]), 5000, "a new instance reads it back")
	# A file the index doesn't know (another process wrote it) and an unreadable index.
	_write(ROOT.path_join("v/b_1600.bin"), _bytes(300))
	_write(ROOT.path_join("index.json"), "{not json".to_utf8_buffer())
	var third: RefCounted = Cache.new()
	third.set(&"root", ROOT)
	var st: Dictionary = third.call(&"stats")
	assert_eq(int(st["detail_bytes"]), 5000, "rebuilt from the folders")
	assert_eq(int(st["coarse_bytes"]), 300)
	assert_eq(int(st["worlds"]), 2)


static func _bytes(n: int) -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(n)
	return b


static func _write(path: String, data: PackedByteArray) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_buffer(data)
	f.close()


static func _remove(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return
	for f: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(f))
	for d: String in DirAccess.get_directories_at(path):
		_remove(path.path_join(d))
	DirAccess.remove_absolute(path)
