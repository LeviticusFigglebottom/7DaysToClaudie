extends GutTest
## The composer's golden output (ADR-0038, RWG v2 Phase 1). Saves keep terrain digs, felled trees
## and POI state against composed regions, and the disk cache keys them by an input hash that does
## not hash the composer's code (only TerrainComposer.VERSION): any change in output for the same
## inputs silently breaks old runs. So every speed-up must give byte-identical regions.
##
## Larch Hollow (the handcrafted map's built region) and the town region of a fixed random world
## (seed 2026, size 3), and its drop-site region, are composed at 4 m and 8 m and digested: the
## height hash, md5 of the splat, biome and vegetation arrays, and the JSON of the metadata (water,
## roads, bridges, placements and the rest). The digests were recorded from the composer at VERSION
## 11 before Phase 1 changed it. Row bands (one thread or four) give the same digests.
## `SLOW_TESTS=1` also runs the 1 m variant, with one band and with four.
## The random world's digests were re-recorded for generator VERSION 2 (ADR-0040: organic towns,
## world-level, which the composer applies where world.json lists `towns`); Larch Hollow's are
## unchanged, the main map having no towns.
##
## When a digest differs: if the inputs changed on purpose (region.json, a framework or POI the
## region places, world_gen.json, the generator), the recorded input hash differs too and the
## digests must be re-recorded (run with GOLDEN_PRINT=1 to print them); if the input hash matches,
## the composer's output changed and that change must be undone or come with a VERSION bump.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")

const TMP: String = "user://test_composer_golden"
const MAIN_MAP: String = "res://world/main_map"
const LARCH: String = "d6_larch_hollow"
const RWG_SEED: int = 2026
const RWG_SIZE: int = 3
const DIGEST_KEYS: PackedStringArray = ["height", "splat0", "splat1", "biome", "vegmask", "water", "roads", "bridges", "placements", "other"]

## Recorded from the VERSION 11 composer before Phase 1 (see the header). "input" is the region's
## input hash at that spacing, to tell changed inputs from a changed composer.
const GOLDEN: Dictionary = {
	"larch@4": {
		"input": "54ae7a7df64fafb5d6394ccee010f54ba0ed548733580c06e5a6a786968fc4e8",
		"height": "186327d2896500f5791cba8a7d5631df88bc7c64614494405c6b0effc4777882",
		"splat0": "2d09afced42733fc9f72dcc058ce4e8d",
		"splat1": "5227d9078a3b81325cf3cd2b13ddbd5b",
		"biome": "6c883f031ffa52c00826e72dfa908c54",
		"vegmask": "e4ee8a66dacfdc806c7af6a6f075570f",
		"water": "557e9069b493e19e7402548619659f8b",
		"roads": "1589f8d00de3c447c0854bcf5ec64778",
		"bridges": "f97bf6a0088f3da534491ebf01e8e086",
		"placements": "5db5e17fff58e7d5c1b10c4718be4364",
		"other": "ed9cc80bc633117e93e2656877d48744",
	},
	"larch@8": {
		"input": "c495f4ee3be2d5babb8a027b0eb09edab7f05f71b20608a5832cee6d4ea78f42",
		"height": "3b691c89e3863f1e97151d5f09ade601007f88aaf8fa47638fcfad14a43f2694",
		"splat0": "9b0656ece7ac6d94a88996a796ec3121",
		"splat1": "b73cc7bc1b24466c1e3b14eeab40ade2",
		"biome": "5fc178c6cfe7f40e9da4f522d6103c8a",
		"vegmask": "a445f5690db1b1070a384b431b8df07f",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a",
		"roads": "d5c40e8a39e6bfeaecee395e6c034a19",
		"bridges": "10e8c17e881965fe5bc24d68509cbd54",
		"placements": "2a4dee192c9e6bab95bef493eb2e1af7",
		"other": "2159e3c6cd82fe9a12597972cd9df77f",
	},
	"larch@1": {
		"input": "fc909f3c3f5121150c10178203c76978f28de7aa7f13c6c2b46db36640a0f0ac",
		"height": "f4b09537e497acaeed6c2848dd924e1d8c97bd64675e76232ab3d80fa28a7a00",
		"splat0": "e85611a28a7cfc04a085d2a4aca58362",
		"splat1": "0f6f285da9546642e1117d42c7782c1c",
		"biome": "cf50ca7386778c3a8f2f0220a1be7d3b",
		"vegmask": "c2a2cfae1a83e751f66829cdf19592f7",
		"water": "11ae9d82d419d86230b8edcb296f0984",
		"roads": "d239de547af92ca3b957e1e3add667ce",
		"bridges": "ef252ccce52545ebe035c7e9169fe945",
		"placements": "95351af500c47a2bffd8eb285214c734",
		"other": "1351cdaa2b2e1e2441abf2bc1ab94843",
	},
	"rwg@4": {
		"input": "b37c42711ab80a290dbcea9ef278f20a895bea78141ebc34affc05340010875d",
		"height": "d6d973d4cb88199d886ab4b17658b8ac96a6e0d67ad4017eda2ef6979c5c95f8",
		"splat0": "1d90149ec8c8253ee7de0f9b44dab68c",
		"splat1": "40ca0393c6977791d2372428e4ff40f3",
		"biome": "1eb5c6c01866c964a329a9ecccfcd0b1",
		"vegmask": "d12a482b773fbd316d6a312d95070f6f",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "692b73e2614d0630e436ef6b4d64f966",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "077354b28eb149eca57bc6578cee4b26",
		"other": "e27b28fdf003836f2d66c19e8682c841",
	},
	"rwg@8": {
		"input": "21a5315f36730a4a8564837f181e8e9af6b089adadd14e2a6d07044069cdd5b0",
		"height": "aac5c29fa4ab97b821f201177c03a55ae3cf05f06c3b151113fc0f1a1dd40503",
		"splat0": "0ec226709d7aeaeaa6fc3acae5983c53",
		"splat1": "80060b7d539c8628d960d48b78512d90",
		"biome": "c4c1336a67ed16574c87afb69b55f4c5",
		"vegmask": "1fe2c1f0fb3859e398dc0d958bc822f8",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "692b73e2614d0630e436ef6b4d64f966",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "077354b28eb149eca57bc6578cee4b26",
		"other": "1768c8543beaa1f380acfabdbb30b44a",
	},
	"rwg@1": {
		"input": "31654a77d3cd49832f7131752de740c0f639b52c08eb561b96d82dfd15b4eae3",
		"height": "a839a351ad5a7973b0a9d67b3423e4996b00fcbd7f5df71027a92053fbc12148",
		"splat0": "d060157ca03510f8b3360b5add5a2182",
		"splat1": "3fe38d0980a1834c506cfc5119387fae",
		"biome": "561f81885fbc374de8b60ad4ad44097d",
		"vegmask": "b93d0f77d02980872ae4cd118767e02e",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "692b73e2614d0630e436ef6b4d64f966",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "077354b28eb149eca57bc6578cee4b26",
		"other": "67b6ee660bde2070759e5f30e8ba6359",
	},
	"rwg_drop@4": {
		"input": "62fcdfaa9d5c3f2672e0d63f598120822c86ca00d804c010dbbdfbd0a27d7c8c",
		"height": "37718bfdcb559616689d587239191d873d7b07c7b498ef1d8be5447c950a468e",
		"splat0": "1302bd2189a039ab811624d5136bf5cb",
		"splat1": "bb2839c357afc97d70e80ffecc9458a4",
		"biome": "9994f8f29387c5fb8e842e475f1018aa",
		"vegmask": "17c3fd782109ef0233cbb8fe2b9adf1d",
		"water": "646da548e4581b18bc1605655c50b049",
		"roads": "d751713988987e9331980363e24189ce",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "4f1e53c44567c3d0c5e23e9fa602ca96",
		"other": "a70ca807c8122f946b6959fdb7848198",
	},
	"rwg_drop@8": {
		"input": "ff3f225618808d106182d78678ab6cc1200ad94d5753a4ca6af126f414b28aac",
		"height": "15cf61fe74754265e18d249dac81a3e30d8b88f153fc94243af0f4a3e55252c3",
		"splat0": "5bdd15325abca0736ec62ac7ecb33ce5",
		"splat1": "d9048c66455e267f190d61d7e5a79cff",
		"biome": "b896f595496e5b2e691735360287a44f",
		"vegmask": "1d9c859cf05b1abdbd596ab94135256e",
		"water": "646da548e4581b18bc1605655c50b049",
		"roads": "d751713988987e9331980363e24189ce",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "08c45a9a1db6e417a5d8711fea6686a4",
		"other": "d8746ff32d27b03113ff4f7b8b24b56f",
	},
}

var _main: WorldDef
var _rwg: WorldDef
var _rwg_region: String = ""
var _rwg_drop_region: String = ""
var _fw_ids: Array[StringName] = []


func before_all() -> void:
	_main = WorldDef.load_from(MAIN_MAP)
	var s: RefCounted = GenSettings.resolve(&"standard", {"size": RWG_SIZE}, RWG_SEED)
	var g: RefCounted = Generator.generate(s)
	var dir: String = TMP.path_join(str(g.get(&"world_id")))
	Worlds._remove(TMP)
	DirAccess.make_dir_recursive_absolute(dir.path_join("regions"))
	# The world's files without the map; the timings are left out so the input hash is stable.
	var wj: Dictionary = g.call(&"world_json")
	(wj["generator"] as Dictionary).erase("timings_ms")
	Worlds._write_json(dir.path_join("world.json"), wj)
	var ids: Dictionary = g.call(&"region_ids")
	for cell: Variant in ids:
		var rdir: String = dir.path_join("regions").path_join(str(ids[cell]))
		DirAccess.make_dir_recursive_absolute(rdir)
		Worlds._write_json(rdir.path_join("region.json"), g.call(&"region_json", str(cell)))
	Worlds._write_json(dir.path_join("frameworks.json"), g.call(&"frameworks_json"))
	for e: String in Worlds.register_frameworks(dir):
		push_warning("test_composer_golden: %s" % e)
	for tw: Dictionary in g.get(&"towns"):
		_fw_ids.append(StringName(str(tw["fw_id"])))
	_rwg = WorldDef.load_from(dir)
	# The first town's region: world roads, the town's pad and streets, and its places.
	var towns: Array = g.get(&"towns")
	if not towns.is_empty():
		_rwg_region = str(ids[str(towns[0]["cell"])])
	# And the drop site's region: its clearing, spawn, trail and a river.
	_rwg_drop_region = str(ids[str((g.get(&"drop") as Dictionary).get("cell", "A1"))])


func after_all() -> void:
	for id: StringName in _fw_ids:
		Content.remove_runtime_def(&"framework", id)
	Worlds._remove(TMP)


## Digests of everything a composed region holds.
static func digest(rt: RegionTerrain) -> Dictionary:
	var other: Dictionary = {"spawns": rt.spawns, "frontiers": rt.frontiers, "biome_ids": Array(rt.biome_ids),
		"palette": Array(rt.palette), "rect": [rt.rect.position.x, rt.rect.position.y, rt.rect.size.x, rt.rect.size.y],
		"spacing": rt.spacing, "samples": [rt.height.width, rt.height.depth]}
	return {
		"height": rt.height.content_hash(),
		"splat0": _md5(rt.splat0), "splat1": _md5(rt.splat1), "biome": _md5(rt.biome), "vegmask": _md5(rt.vegmask),
		"water": _json_md5(rt.water), "roads": _json_md5(rt.roads), "bridges": _json_md5(rt.bridges),
		"placements": _json_md5(rt.placements), "other": _json_md5(other),
	}


static func _md5(b: PackedByteArray) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	ctx.update(b)
	return ctx.finish().hex_encode()


static func _json_md5(v: Variant) -> String:
	return JSON.stringify(v, "", true, true).md5_text()


func _check(key: String, world: WorldDef, rid: String, spacing: float, rt: RegionTerrain) -> void:
	assert_not_null(rt, "%s composes" % key)
	if rt == null:
		return
	var got: Dictionary = digest(rt)
	var input: String = TerrainComposer.input_hash(world, rid, spacing)
	if OS.get_environment("GOLDEN_PRINT") == "1":
		got["input"] = input
		print("GOLDEN \"%s\": %s," % [key, JSON.stringify(got, "", true)])
	var want: Dictionary = GOLDEN.get(key, {})
	assert_false(want.is_empty(), "%s has recorded digests" % key)
	if want.is_empty():
		return
	var differs: PackedStringArray = []
	for k: String in DIGEST_KEYS:
		if str(got[k]) != str(want.get(k, "")):
			differs.append(k)
	if differs.is_empty():
		if input != str(want.get("input", "")):
			gut.p("%s: the inputs changed since recording, the output did not" % key)
		pass_test("%s is byte-identical to the golden output" % key)
		return
	var why: String = "the inputs changed since the digests were recorded (re-record if intended)" if input != str(want.get("input", "")) \
		else "the composer's output changed for the same inputs"
	fail_test("%s differs in %s: %s" % [key, ", ".join(differs), why])


func test_version_is_still_11() -> void:
	assert_eq(TerrainComposer.VERSION, 11, "Phase 1 changes no output, so VERSION stays 11 and v1 caches stay valid")


func test_larch_hollow_at_4_and_8_m() -> void:
	for sp: float in [4.0, 8.0]:
		_check("larch@%d" % int(sp), _main, LARCH, sp, TerrainComposer.compose(_main, LARCH, sp))


func test_random_world_town_region_at_4_and_8_m() -> void:
	assert_ne(_rwg_region, "", "the fixed random world has a town")
	for sp: float in [4.0, 8.0]:
		_check("rwg@%d" % int(sp), _rwg, _rwg_region, sp, TerrainComposer.compose(_rwg, _rwg_region, sp))


func test_random_world_drop_site_region_at_4_and_8_m() -> void:
	assert_ne(_rwg_drop_region, _rwg_region, "the drop site is in another region")
	for sp: float in [4.0, 8.0]:
		_check("rwg_drop@%d" % int(sp), _rwg, _rwg_drop_region, sp, TerrainComposer.compose(_rwg, _rwg_drop_region, sp))


func test_four_bands_give_the_golden_output() -> void:
	for sp: float in [4.0, 8.0]:
		_check("larch@%d" % int(sp), _main, LARCH, sp, TerrainComposer.compose(_main, LARCH, sp, Callable(), [false], 4))
		_check("rwg@%d" % int(sp), _rwg, _rwg_region, sp, TerrainComposer.compose(_rwg, _rwg_region, sp, Callable(), [false], 4))
	# An odd count leaves bands of unequal height.
	_check("rwg_drop@4", _rwg, _rwg_drop_region, 4.0, TerrainComposer.compose(_rwg, _rwg_drop_region, 4.0, Callable(), [false], 3))


func test_a_cancelled_compose_returns_null() -> void:
	assert_null(TerrainComposer.compose(_main, LARCH, 8.0, Callable(), [true]), "cancelled before it starts")
	# Cancelled from the progress callback partway (as a streaming job is from another thread).
	var cancel: Array = [false]
	var stages: Array = []
	var stop := func(stage: String, _t: float) -> void:
		stages.append(stage)
		if stage == "roads":
			cancel[0] = true
	assert_null(TerrainComposer.compose(_rwg, _rwg_region, 8.0, stop, cancel, 2), "cancelled at the roads stage")
	assert_eq(stages, ["macro", "features", "water", "roads"], "and no stage after it ran")
	# A cancelled compose is not cached, and the next one composes in full.
	assert_not_null(TerrainComposer.compose(_rwg, _rwg_region, 8.0, Callable(), [false], 2))


func test_one_metre_when_slow_tests_are_on() -> void:
	if OS.get_environment("SLOW_TESTS") != "1":
		pass_test("1 m variant skipped (set SLOW_TESTS=1)")
		return
	_check("larch@1", _main, LARCH, 1.0, TerrainComposer.compose(_main, LARCH, 1.0))
	_check("rwg@1", _rwg, _rwg_region, 1.0, TerrainComposer.compose(_rwg, _rwg_region, 1.0))
	_check("larch@1", _main, LARCH, 1.0, TerrainComposer.compose(_main, LARCH, 1.0, Callable(), [false], 4))
	_check("rwg@1", _rwg, _rwg_region, 1.0, TerrainComposer.compose(_rwg, _rwg_region, 1.0, Callable(), [false], 4))
