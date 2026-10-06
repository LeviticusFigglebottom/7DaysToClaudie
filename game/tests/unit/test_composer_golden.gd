extends GutTest
## The composer's golden output (ADR-0038, RWG v2 Phase 1). Saves keep terrain digs, felled trees
## and POI state against composed regions, and the disk cache keys them by an input hash that does
## not hash the composer's code (only TerrainComposer.VERSION): any change in output for the same
## inputs silently breaks old runs. So every speed-up must give byte-identical regions.
##
## Larch Hollow (the handcrafted map's built region) and a town region of a fixed random world
## (seed 2026, size 3), and its drop-site region, are composed at 4 m and 8 m and digested: the
## height hash, md5 of the splat, biome and vegetation arrays, and the JSON of the metadata (water,
## roads, bridges, placements and the rest). The digests were recorded from the composer at VERSION
## 11 before Phase 1 changed it. Row bands (one thread or four) give the same digests.
## `SLOW_TESTS=1` also runs the 1 m variant, with one band and with four.
## The random world's digests were re-recorded for generator VERSION 2 (ADR-0040: organic towns,
## world-level, which the composer applies where world.json lists `towns`), VERSION 3 (a trader
## post by each town: its drive, clearing, spawn and level yard) and VERSION 4 (ADR-0041: burnt
## forest and fen in the biome map, fen pools, per-region palettes); Larch Hollow's are unchanged by
## all three, the main map having no towns, generated posts or new biomes.
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
		"input": "8038d2ee3d01ca60be7bbafaf5737b3a9ef4d9178e92fd6b32a4e41ebf40ce32",
		"height": "7220663adc7250c7b7381bd617ed12d014d6812923b81d8f8076d33a7e66d3bb",
		"splat0": "5fd56baf9f69cf62d8f63e6be2f8962a",
		"splat1": "37a99a9f9dcc7d62dfdfcade4b1906db",
		"biome": "4d99e6e9413edd2fba5696c53f448f9a",
		"vegmask": "ecb43b8b7b0b60cda77cab4b9073b498",
		"water": "49e108a32077cec749d37e86d197b32f",
		"roads": "cc4b00bf48bfdfdc316b1f250868d3ba",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "3d00b6ee0ba1f8ee0ea9dcc1490499c0",
		"other": "cec63ec5e9ea167c69260cbaf86a1d0a",
	},
	"rwg@8": {
		"input": "0e8c7df8fe5664c4586b7e2b43dd50000acbc21f4dd7b22148d5bd8c16c406c3",
		"height": "2f7d36aead7da92530b5ae47e0105a99aae2f7d5762df8176a037266a29a3cf7",
		"splat0": "4fddae23e5fcb06f2aa6bfff99792190",
		"splat1": "a536675b7eebfbffcb9090991ac33de7",
		"biome": "d295da1b2b67c3e37bfafa8d66aa02bb",
		"vegmask": "6b3f62ecd4d7c564fb8429061d5b1046",
		"water": "fd041168cd7a58fb4b7994caf5864ac8",
		"roads": "cc4b00bf48bfdfdc316b1f250868d3ba",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "1db8a5ede7f36eaa94c0477c06580a86",
		"other": "bcea77cbf3c997af1ab262307621ca3b",
	},
	"rwg@1": {
		"input": "336763623f4fe8810b8b556dc3acaa1760e0f4653fd14edcfd02784e83fbba9b",
		"height": "9473dd8a07b20704aaadd4aa8e4d4935b446e5b58af7187fe4c3f3e2e2f95f2f",
		"splat0": "6100006459cd77fff625d8c499b7a8b4",
		"splat1": "28efa08636f65234730f9a157b2f1f17",
		"biome": "055a8eaa13dca3032e6d661b098adb19",
		"vegmask": "3a3086a11c51e56bf12505afc7db0129",
		"water": "0815ff0f2b7d71ee76189c656a648066",
		"roads": "cc4b00bf48bfdfdc316b1f250868d3ba",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "72957aef98cf0e02920bbfb6449a0c72",
		"other": "445eed2000fca209f9b0b52d17c5924b",
	},
	"rwg_drop@4": {
		"input": "c9b6d44861607982eacb46a7ac0e7ae770a141c6fc1e0acf536ca1cf30105f4d",
		"height": "e21d829f4c990396975d266ae667d21f0f3983716b536fae1ed0547e5c26e288",
		"splat0": "a87293932a39ed2c16d72ff0bb1b0db6",
		"splat1": "3a60f2b87c46c5fb63b33f22312d982c",
		"biome": "3bece53d7155dba28ae362667a72a89e",
		"vegmask": "e91cd1874f221bb32012bd0b472258d5",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "121d8bb05e0b353639e114a9f6ed4190",
		"other": "5bc27312937ee0c0680239869cc69b16",
	},
	"rwg_drop@8": {
		"input": "ba34a862f2fcdfc5901ff28794fe1ef694f2fd2b52993af5bd869ea7d4817da2",
		"height": "b94eff6b741c8ec2b92d3207afb0ecdefda1f815dea7ace100db97492ab7d2c5",
		"splat0": "7985c90c27a397b83d8a40fe67714738",
		"splat1": "4d2eeff49561c079ec0c003f1e919c83",
		"biome": "e5e539d7aff7fd609a1eb1bd9879e488",
		"vegmask": "6fc1f8fd6c2d0bc9333bed5d9163567e",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "5715ef71158e3bbc869bc7e8007fd405",
		"other": "e424e63a3b750e476a6e84d0385281dd",
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
	# The drop site's region: its clearing, spawn, trail and a river.
	var drop_cell: String = str((g.get(&"drop") as Dictionary).get("cell", "A1"))
	_rwg_drop_region = str(ids[drop_cell])
	# And a region of the first town (world roads, its lots and streets, its places): its own when the
	# drop site is elsewhere, else another one its lots reach (generator v2's towns straddle borders).
	var towns: Array = g.get(&"towns")
	if not towns.is_empty():
		var cell: String = str(towns[0]["cell"])
		if cell == drop_cell:
			for l: Dictionary in towns[0]["plan"]["lots"]:
				var lc: String = str(g.call(&"cell_at", Vector2(float(l["frame"][0]), float(l["frame"][1]))))
				if lc != drop_cell:
					cell = lc
					break
		_rwg_region = str(ids[cell])


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
