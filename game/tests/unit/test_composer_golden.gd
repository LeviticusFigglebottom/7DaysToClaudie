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
## (ADR-0048: the Ashen high camp joins the wilderness pool and moves the places drawn after it),
## and for VERSION 7 (TD-169: the `mine` site, placed last from its own stream so every other place
## stays; the adit lands in neither region, so only the world id in `placements` and the input
## hash moved), and for VERSION 8 (ADR-0058: Ezra Vane's `companion` camp, placed last from its own
## stream; the town region's ground, roads and masks moved with it), and for VERSION 9 (ADR-0053:
## the forest set pieces, `late` pool entries from their own streams; one reaches the town region,
## so pads, tracks and masks moved there, and the drop-site region's world id in `placements`), and
## for VERSION 11 (round 5 of the set pieces: none lands in either region, so only `placements`).
## Larch Hollow's were re-recorded when Ezra's camp was placed west of Larch Pond (ADR-0058: its
## pad), and when Waystation 9 was placed in it (ADR-0039: a clearing, its spawn and its drive;
## its 1 m variant, which only SLOW_TESTS=1 runs, a little later), and again when the Corvane
## Larkspur Adit was placed by the Larkspur cliffs (ADR-0044: its pad and its track);
## the generator versions leave them unchanged, the main map having no towns, generated posts or
## new biomes.
## Composer VERSION 12 (ADR-0047: a world town paints `town` on its streets only, and yard grass keeps
## off the authored footprints a lot may hold) re-recorded the random world's splat, biome and
## vegetation digests (its drop-site region reaches the town too) and every input hash (the
## version is hashed); Larch Hollow's outputs held, byte for byte, at 1, 4 and 8 m.
## Composer VERSION 13 with generator VERSION 12 (ADR-0059: valley caps in the macro grid, grade-capped
## roads with natural banks on every map, banked pads, yards over their whole frames, bigger towns
## with street networks, forest caves in random worlds; Larch Hollow's two authored grottos)
## re-recorded every digest, Larch Hollow's included, and Larch Hollow's again for Pell's Crossing's
## west end (a world-level town on the main map: Mill Street West and its lots reach into the region),
## and again when the Lift 3 wreck was placed east of the Tamsin (its pad; 1, 4 and 8 m).
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
		"input": "a0353e5282aea29036cb71e6caab44c38be51bf2fddf07ba16b975c61835acd8",
		"biome": "d10a0754b564f1e48a8578415db87927",
		"bridges": "1f0c533e9edd7d199eef56ffe59942b6",
		"height": "b4cdb1f3f29522c6693694a2f1952d8702f155cfb8f642e846705c6182bc884b",
		"other": "0944711917e3677272bf29b704033433",
		"placements": "c4c8321b82a746d60f492d87b0d1aefb",
		"roads": "b285bee2d48e194488975ced28ae327d",
		"splat0": "1a6e87e8bbc61a1d44309da3e0d88835",
		"splat1": "4d8d71b79008df5cc18b348e7694677d",
		"vegmask": "f274336df3d84ec7736c2d5ec4cd9380",
		"water": "557e9069b493e19e7402548619659f8b"
	},
	"larch@8": {
		"input": "201ae38e17aca7b6996d12cf14ea309c2e4f235a48dc90f3c750a01d9c1d5e79",
		"biome": "3cd0fcfdd57a6d57ab9ae1a95b21339d",
		"bridges": "259591cd5bc276b780c3fd267f0a9a6d",
		"height": "289cb366f7a53a577ac4df7c1cf41f3c5319244ad5ae3a4b562ee5638f1fab65",
		"other": "3cbefb49c6942cf9247f8e7e0270ccf2",
		"placements": "fc089e0cfca88c57a744d06e96e9368b",
		"roads": "d5d850bfe150d2b8d3d7631c9c82e129",
		"splat0": "38896272a18d8cfc32c16812cf946db9",
		"splat1": "45274c6e9fbb0a21cbdb648dcbd0f712",
		"vegmask": "8c7eedc67287a2f10b66f4658231987c",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a"
	},
	"larch@1": {
		"input": "ca8346fcdf9750f7e91adbef5930bb3273048b3aaad9d7c9311605c8e52c89a7",
		"biome": "931a7d963866420f685440cbfbedbda0",
		"bridges": "428b1b895c7baf5bf0dc14187b1f2176",
		"height": "a397ace96904a87987cb913eaf2bed42a31a3cac197af60bd69f15adbd3c34a7",
		"other": "41849af09489e5cb2692147029d58d76",
		"placements": "7a19635778b590f08fd5d6dd235d3f00",
		"roads": "da0f365d549eddace1e7509467c5f903",
		"splat0": "c7e3c6640fed98068802653c0473c51b",
		"splat1": "0016caedef2de525379f3df6c911461d",
		"vegmask": "990424d7c88272db1a2c48cd87b439da",
		"water": "11ae9d82d419d86230b8edcb296f0984"
	},
	"rwg@4": {
		"input": "13263c198deff4df175752845ae61f170cf1da242db6ee0201da77ed0f5bd941",
		"biome": "59b215d374c2472eec9acf664ea339a4",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "a1e73cf216adcdaa6cd510e43115cf98d7855a9c0ba1ff628a1c2e6c6190f646",
		"other": "843b397c22a45284092e175cebfbdee7",
		"placements": "bd8c00ced8fc2d64411f080dc5dc6b74",
		"roads": "e8df081293dce1782eebca3b617d3a0f",
		"splat0": "99ac32a84c01aa52f1e326697f1b01f4",
		"splat1": "3cee15c228d224aa2c7be9936710f581",
		"vegmask": "de80ad6dbee79a8f87ba9b297d609048",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@8": {
		"input": "d4278bb4ddde92c2e1e328a09de97ac448ca2c5a06d79defd41adc861648da36",
		"biome": "18f3d6146340bc426628f856157874ca",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "f52c23cf5a4c01f5b516bdfb054696b19f5cd09e2e88405490af6677925256a5",
		"other": "b2f7269e94d2e05e8dd16db583bc017e",
		"placements": "e8a5138e7ab2c6141a75b807ed7cae15",
		"roads": "e8df081293dce1782eebca3b617d3a0f",
		"splat0": "023234e9ee9cebb2897bada3406a3d34",
		"splat1": "752f21cfa6e86788f1ff82d42ae7db4a",
		"vegmask": "7ce26876e019f50f23d3391bae93d4b5",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@1": {
		"input": "f0d17cd8acae7a02f49177022aba0bc80baec73a114ff5754bdd1f8eaa166884",
		"biome": "57ba2dfb17839ef75e809221dd132066",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "b6400067ef975cfbfb8135e3f4611566da8fb22f95306b4b515b6b9ad2663df7",
		"other": "bb546e313f91e8b52ded71379f76f9c9",
		"placements": "6e7a1216a8f197ae5b746549a70a1ed3",
		"roads": "e8df081293dce1782eebca3b617d3a0f",
		"splat0": "96c368ce62443c6ce925d695c89d91f6",
		"splat1": "944ee5e91f463b081cb47d4ee8c208e2",
		"vegmask": "91f1eb0f7b7d1e8211f765cfe32f6f79",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg_drop@4": {
		"input": "d08b6cad138c9f1c16c306d448a980e2b8d9cc6a77f363495a44b2591035e0e6",
		"biome": "23afec1bed1b8777e5cdb7c1e14b3357",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "fe007424f9604e034d8542da20c23f6d9c2b6b9e76fa5c7daea8a4f5d9d02397",
		"other": "bd5dd8f87b34ef046099a6c509be10ef",
		"placements": "884b75752da8a65b692a0db6b26d8d6e",
		"roads": "998f3ba510836c93cb814af923f128ed",
		"splat0": "1c1d6f46f813373d787706ff505fd563",
		"splat1": "b201819613ac9aee4d8c5b0a162daf52",
		"vegmask": "0d194fce5318b50f780f3df4740bdc70",
		"water": "da6dc40f877b3f4b8c97f6d6f6bf3340"
	},
	"rwg_drop@8": {
		"input": "aaa6dd4e8c2f8cb6042e28018373ae1819040c00e9071174e1b2f88169512ba2",
		"biome": "f10b3334755a84d901d4fb11fbc14339",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "ccca23d04f334e9a5e9860d380d967dc6b40e773fb9dc0b6ced317f81d0d737a",
		"other": "5325eb8bd2048bedde87d89a064766fa",
		"placements": "9157d3b423910f0953bbf39280de1354",
		"roads": "998f3ba510836c93cb814af923f128ed",
		"splat0": "7f50231df9a5d63cf20e34e3817b9daf",
		"splat1": "8948a44b3e220888410e893e01191c59",
		"vegmask": "8271a317ed21c2a902a233363adbcd77",
		"water": "da6dc40f877b3f4b8c97f6d6f6bf3340"
	}
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


func test_version_is_13() -> void:
	assert_eq(TerrainComposer.VERSION, 13, "Phase 1 changed no output; VERSION 12 is ADR-0047's town paint, 13 ADR-0059's banks and yards")


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
