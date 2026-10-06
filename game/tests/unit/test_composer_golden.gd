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
## places after it, their pads, tracks and vegetation masks), and for VERSION 5 (`unique` pool
## entries; the field lab's placement record carries the key, so only `placements` moved), for
## composer VERSION 12 (ADR-0047: town ground only on streets and lots) and for generator VERSION 6
## (ADR-0048: the Ashen high camp joins the wilderness pool and moves the places drawn after it). Larch
## Hollow's were
## re-recorded when Waystation 9 was placed in it (ADR-0039: a clearing, its spawn and its drive;
## its 1 m variant, which only SLOW_TESTS=1 runs, a little later), and again when the Corvane
## Larkspur Adit was placed by the Larkspur cliffs (ADR-0044: its pad and its track);
## the generator versions leave them unchanged, the main map having no towns, generated posts or
## new biomes.
## Composer VERSION 12 (ADR-0047: a world town paints `town` on its streets only, and yard grass keeps
## off the authored footprints a lot may hold) re-recorded the random world's splat, biome and
## vegetation digests (its drop-site region reaches the town too) and every input hash (the
## version is hashed); Larch Hollow's outputs held, byte for byte, at 1, 4 and 8 m.
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

## Recorded from the VERSION 11 composer before Phase 1, re-recorded for VERSION 12 (see the header). "input" is the region's
## input hash at that spacing, to tell changed inputs from a changed composer.
const GOLDEN: Dictionary = {
	"larch@4": {
		"input": "4f993b6d5aeeea3718aa7fe6066b1ecc7e6efc82afb2883d5c40ffe5cad2bf2c",
		"height": "d02d26e81d142f13334430a59a777d48751f494f876d140a5f7090841ff5aa3b",
		"splat0": "d12f5b596a18cdddd81dd54ef5c36f92",
		"splat1": "a0e0f3e9d0ea61b64313f463af34b2c4",
		"biome": "0bf70616a8131ec34824936773207351",
		"vegmask": "ac4235cfb94e2a91035f0ea29717ea64",
		"water": "557e9069b493e19e7402548619659f8b",
		"roads": "3cd6abe5ddc37e6287223186137e5441",
		"bridges": "f97bf6a0088f3da534491ebf01e8e086",
		"placements": "413798e46bb23f59be1a78485122900b",
		"other": "343d7ca5a31189c644d8aca5e9ee0028",
	},
	"larch@8": {
		"input": "b27fdcd16fd701851d70d1dd737a8152be3aa6763348e9d66e708a702c37b3b4",
		"height": "9e83fffe70ac6033922bc32628cf233346ec3a2c98f760e7043cb1e9dedef150",
		"splat0": "8ee58b4216332e9f737a5152274f2fb2",
		"splat1": "71f4ef029e083c97ad7fdbac70c5e563",
		"biome": "9b5ac13f49b57e97a4f025df3881f248",
		"vegmask": "cba4af32842677631da2cfa501e5ba50",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a",
		"roads": "b18902326c95c025e50cca0eaa479f9f",
		"bridges": "10e8c17e881965fe5bc24d68509cbd54",
		"placements": "f9288305e6c6ae5a696487ad03a71a53",
		"other": "0619089a625a0d5200fa83faa962ee3c",
	},
	"larch@1": {
		"input": "2ab4b08b3d4f7d5f26f68c1d29e575918bb0d76cf0d6b184758d563dbe61a916",
		"height": "7440c2c539d199bcd29cfbee12a1ec392fa97e8d2b0240dcd226eb383a27e7b4",
		"splat0": "9676745eb0d6b01bbe11c9e83b16549f",
		"splat1": "55b0189d93e9a60ec3392ca26604f9ad",
		"biome": "25de7db4ac719b2a1663ff7b3c8df7c5",
		"vegmask": "ff3457c9b4e422dfd9387aeaa3f9188f",
		"water": "11ae9d82d419d86230b8edcb296f0984",
		"roads": "a708bdec066cd3e76cad905f6bf65e75",
		"bridges": "ef252ccce52545ebe035c7e9169fe945",
		"placements": "32d37a62871d59b73bb3623eae8c3d07",
		"other": "9042e6121a94f2a29c717a3d15b2b03d",
	},
	"rwg@4": {
		"input": "cce0b066d486162cffb1f13859fa51fac2886b2c33c86cf5c25d02f44f5d2f7d",
		"height": "a925f207a617d445c264139a7e702b7f47621981d21b80dd0cc54b9aeaf36e07",
		"splat0": "098406c5f2209022b523a6bf0ebf9578",
		"splat1": "c111b88e7e976ef14ad6054fd23ad1f2",
		"biome": "86cfa0dcc648fb86e785064ec34f706f",
		"vegmask": "9c0c1a73f255730405073b6c4459f120",
		"water": "49e108a32077cec749d37e86d197b32f",
		"roads": "f4c1afcbb64546909bd550a88f36c5df",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "4b5a617b117f64d5658ed29216ad17c6",
		"other": "cec63ec5e9ea167c69260cbaf86a1d0a",
	},
	"rwg@8": {
		"input": "f8d9a36fb69195039ed4b3c1cc193fa70537218a184b6929f775b84f27dcf9b1",
		"height": "3ea48f014b854e99a746b0b189b297b1a77d89d25e0d08fd8e194ff064a3225a",
		"splat0": "ade598dee9008932ac84bee08c1d3820",
		"splat1": "960ad4f5cd5c5f6c28a80a7c1fed0e1d",
		"biome": "787269a12fe85a987683ae8e7f7ba80b",
		"vegmask": "22408f0bfcbdb3d430c54636ae7257de",
		"water": "fd041168cd7a58fb4b7994caf5864ac8",
		"roads": "f4c1afcbb64546909bd550a88f36c5df",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "c3f0e385b5d45c33dda77cff1fae10ce",
		"other": "bcea77cbf3c997af1ab262307621ca3b",
	},
	"rwg@1": {
		"input": "254898fc81abbae2da8146d8d2a8d8ad8abc4068846fe466904659664be1874c",
		"height": "1c91067f75bb040f4161a8f75033efa3e9b5f872cda278cbdf24f8f51d558fc1",
		"splat0": "7a7816b3f63c535ca2486d211fd8216b",
		"splat1": "36f65ccea354d1e388a30d7c0b7759bc",
		"biome": "425370b0f0f5d07061fcb5fdec9ac055",
		"vegmask": "900620724046ce9aa24c95cdfb6a6820",
		"water": "0815ff0f2b7d71ee76189c656a648066",
		"roads": "f4c1afcbb64546909bd550a88f36c5df",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "88b3a46888f85828e724db95bf34ef28",
		"other": "445eed2000fca209f9b0b52d17c5924b",
	},
	"rwg_drop@4": {
		"input": "d7accfcec52c15f996a5dfdcf05d7ff2f50ea4d0ce8d7e27935381f14d806586",
		"height": "c176d0709f4d21b4aa95532b211d0af63be784541958436e0b00fea36a978488",
		"splat0": "5e0b93f23957c50754121ac1a52c2f04",
		"splat1": "4516aea033ac574140369ed02cdb8985",
		"biome": "1c6ad66f8a087571d27204d512eec86c",
		"vegmask": "5ae56c7dde25bccc12599228f46170d5",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "a32c5da75d2704360f703bcb1b321a1c",
		"other": "5bc27312937ee0c0680239869cc69b16",
	},
	"rwg_drop@8": {
		"input": "a2607890ad1a655ab426f2035d5e450d03f5c1bd103949bbf11b7125ab5575bb",
		"height": "2627c13e991906fd2eec9fee5bfe187d9f52e2a8c5c6e5232a09a6a6a5e85399",
		"splat0": "5e80c496aff37e4da35832c26eb881cc",
		"splat1": "b56557e643b782752c0d4bccd7fc7fe3",
		"biome": "b194762f7ae3b4cf3de942ab720b9d08",
		"vegmask": "742ad0ae10522fcdfc1c6eecb7c3104f",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "a32c5da75d2704360f703bcb1b321a1c",
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


func test_version_is_12() -> void:
	assert_eq(TerrainComposer.VERSION, 12, "Phase 1 changed no output; VERSION 12 is ADR-0047's town paint (the main map's output held)")


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
