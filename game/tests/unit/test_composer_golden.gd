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
## forest and fen in the biome map, fen pools, per-region palettes), and again when the Corvane Field
## Lab joined the wilderness pool (ADR-0046: a new entry draws from the places stream and so moves the
## places after it, their pads, tracks and vegetation masks). Larch Hollow's were
## re-recorded when Waystation 9 was placed in it (ADR-0039: a clearing, its spawn and its drive);
## the generator versions leave them unchanged, the main map having no towns, generated posts or
## new biomes.
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
		"input": "9945857a16cffc9394ac1667de7644ec418c2233b9115dd8e421879b74d3e3f4",
		"height": "3118b8dc6a4c57459b5caa001d3bdbd07b247f027e5c0b2521387cbdb0956be4",
		"splat0": "166dc12e4d0cdeb0405a999e1da80552",
		"splat1": "a0e0f3e9d0ea61b64313f463af34b2c4",
		"biome": "6c883f031ffa52c00826e72dfa908c54",
		"vegmask": "14a18c72f9b7c96582837c7836e606b9",
		"water": "557e9069b493e19e7402548619659f8b",
		"roads": "3cd6abe5ddc37e6287223186137e5441",
		"bridges": "f97bf6a0088f3da534491ebf01e8e086",
		"placements": "5db5e17fff58e7d5c1b10c4718be4364",
		"other": "343d7ca5a31189c644d8aca5e9ee0028",
	},
	"larch@8": {
		"input": "cf53ed68087c6800ecfae744be2fa3dc365513ea38d654157e8bcd3f62f45ce5",
		"height": "c8c7b635fbb8bf8f35f964228b90db3636ec5cfe244e4be50cd710fd6d8de4b9",
		"splat0": "61288ee19ae1fa32ce1ee446acf2f753",
		"splat1": "71f4ef029e083c97ad7fdbac70c5e563",
		"biome": "5fc178c6cfe7f40e9da4f522d6103c8a",
		"vegmask": "dd48ddaabc8b0945ed8943fb27f4dbfe",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a",
		"roads": "b18902326c95c025e50cca0eaa479f9f",
		"bridges": "10e8c17e881965fe5bc24d68509cbd54",
		"placements": "2a4dee192c9e6bab95bef493eb2e1af7",
		"other": "0619089a625a0d5200fa83faa962ee3c",
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
		"input": "50c1dffe2a7549d4d992b04d73e7398dff3dfc6922586375f416a8cafe923b03",
		"height": "a3f403f848325b1a1ac53870645f41dc3f58c1926830f486c333375fe360f1d8",
		"splat0": "f38e64842bf50943ac0f59f6c65343f6",
		"splat1": "6516361fff888d53383d86388f6881ce",
		"biome": "2d3c3f5d688e720d97472a23102188d0",
		"vegmask": "6652deffe6d28e7629a843f861143079",
		"water": "49e108a32077cec749d37e86d197b32f",
		"roads": "769d0793d5f34a5fe20bc332862e79e3",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "8a022c03cd2d05b034ee5f9227ef2f7f",
		"other": "cec63ec5e9ea167c69260cbaf86a1d0a",
	},
	"rwg@8": {
		"input": "e8947bb80fb8e98d8d0311ffb90644e225a91aa3e3cbd2e5243dcfab93378392",
		"height": "aaa598ed617dc791436e6e0fb60fdfddd8d9c710ab7a8fc5c80a1562254d4071",
		"splat0": "da4bd626d8a9c987ff0f4068211101dc",
		"splat1": "948a79245e54a783bdf46e12989ba630",
		"biome": "e0d99bf09eb560d100ace94bc11aafa4",
		"vegmask": "d4a9ec05c924fc566eaa08dd6ea446f8",
		"water": "fd041168cd7a58fb4b7994caf5864ac8",
		"roads": "769d0793d5f34a5fe20bc332862e79e3",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "8b6248fa512f0ccd653151e3cbcdc706",
		"other": "bcea77cbf3c997af1ab262307621ca3b",
	},
	"rwg@1": {
		"input": "1ed6ba3eb7752d1ba8415ed99a9a2242d30acbcef06a329fcb69e4b7acbfac77",
		"height": "3ff9acf55cf2c423877cd5c919337834aa44704ccfc39f27f4eee42444a2cfa9",
		"splat0": "28b5db0f6ab043b6aeb4cfcfe8a218f2",
		"splat1": "520eb68cacda5e9dfe903b792ffdb8f0",
		"biome": "a163b9755939c953c97d8253d0fcc639",
		"vegmask": "38fcd6d0d3b2a948011f7fb06eff1f80",
		"water": "0815ff0f2b7d71ee76189c656a648066",
		"roads": "769d0793d5f34a5fe20bc332862e79e3",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "5cfcffc0773e02f88a25791dfa371767",
		"other": "445eed2000fca209f9b0b52d17c5924b",
	},
	"rwg_drop@4": {
		"input": "81897cf3dad4609898f2af702644f1a59ed4f5d7a66c48d43139247865c5fe1a",
		"height": "c176d0709f4d21b4aa95532b211d0af63be784541958436e0b00fea36a978488",
		"splat0": "144426b092fa259c16e5e3c4feec3c92",
		"splat1": "cd96ce9c0ef56f67e700f707c69f4763",
		"biome": "1eb5c6c01866c964a329a9ecccfcd0b1",
		"vegmask": "b35af689f1fd056fc754dd7e46479733",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "720d072d6298b80f3357a058221385f5",
		"other": "5bc27312937ee0c0680239869cc69b16",
	},
	"rwg_drop@8": {
		"input": "f430e957b12bd3b0f3562bb997729d83913bba06fe8ddf8e6caf479d9a6cba19",
		"height": "2627c13e991906fd2eec9fee5bfe187d9f52e2a8c5c6e5232a09a6a6a5e85399",
		"splat0": "db6fc63a4179d47f2e4f021de6b6ed7f",
		"splat1": "56d7ba6832a117a9f0640062acafb0c4",
		"biome": "c4c1336a67ed16574c87afb69b55f4c5",
		"vegmask": "606e1b7e116d6344a5bba2305161a628",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "720d072d6298b80f3357a058221385f5",
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
