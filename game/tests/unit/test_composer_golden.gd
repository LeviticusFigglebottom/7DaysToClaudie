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
		"biome": "3e42f30d7537598857d72146d3331c86",
		"bridges": "1f0c533e9edd7d199eef56ffe59942b6",
		"height": "ac548940736dd9a37405dd3ce85a69bdb810f97250b6c5fbe7b80b99c045d743",
		"input": "093fb5c1516d3275c9c38841e0dad20e4288f4b20dd203d89d77bc8c913e03ab",
		"other": "84e51cfda745fea8a7d5370868731670",
		"placements": "10fdb25c0c5551ac9945f5d3b0c3c4b6",
		"roads": "1786358cb60fd5f1e7352b77247a095e",
		"splat0": "4fa8d5b923221aaacb4457aed40b2d37",
		"splat1": "8501cacd882eb80a18ee419045da8ef1",
		"vegmask": "2b0d60d408b305a3c9f0be6d041b2182",
		"water": "557e9069b493e19e7402548619659f8b"
	},
	"larch@8": {
		"biome": "f87a741cfa84ee9ade261feed33d1e72",
		"bridges": "259591cd5bc276b780c3fd267f0a9a6d",
		"height": "48a66073712742f44a0a51735756c0da61b3b51c742bb6550672e9869bbb4551",
		"input": "bfca83ac32cc298cbf6fe0f813216df798ebd37e1385a1174fc769933d54f037",
		"other": "06e2c0ba7f50dc80174ec52b304f5dff",
		"placements": "1ac7c2aed165d3215ca6eebbe0b9a9a1",
		"roads": "92d31bac40768b560b2cafe205bad4c5",
		"splat0": "36e42fed635dfb802eb0ed88c1baad72",
		"splat1": "64186d528b2c0f873268b44e891e03e0",
		"vegmask": "cfde862a92b383675e61a51947ae8de6",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a"
	},
	"larch@1": {
		"biome": "df4126c541dc9a43752c31e63214e967",
		"bridges": "428b1b895c7baf5bf0dc14187b1f2176",
		"height": "923753d0c2b41c14ec646f37a60e38dba4da1acbe7d8d65660227355a936287f",
		"input": "ca7c36a7f0db628883616ee55f62f287d465e109f38f106771cb18cc55cd978f",
		"other": "fe5db9c3321433ec164d5b3876385b7f",
		"placements": "ce5b38764945ba90256b7ad8aaca2480",
		"roads": "4c543157e6a842d4a3722a73dca1c92b",
		"splat0": "d5d84a681458ec04999692f266ba82f3",
		"splat1": "89f1585a309e72b546125701f19036cc",
		"vegmask": "3e727b9e729df563b4e908de0705fdc7",
		"water": "11ae9d82d419d86230b8edcb296f0984"
	},
	"rwg@4": {
		"biome": "9f930897e87286dbd9f3aca36785ecc1",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "ac6f55c225955bf36edbeed52a21e7f5cc1911f9ce1b805445f8341444d381ea",
		"input": "5a3bbc3d582cb93663787ceb47e4eac85eca818637caa8907e863f938751e80d",
		"other": "843b397c22a45284092e175cebfbdee7",
		"placements": "5d1920e6c959f83c2be2c4277ee96470",
		"roads": "00d3b078f11c213e8298c8f8f36e2f10",
		"splat0": "0e3357c80fb32d475c9506de83c85845",
		"splat1": "7ecab5727b938fc79f24f84ecbcb1190",
		"vegmask": "1cc3ff4f041c6b11f055b14c90a6da4d",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@8": {
		"biome": "725baf113eeb5d4757bdcce975b61a79",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "b9f76a6b87b1c649de6a43f9e2f17bbfe728536b826cff4e58de7e4b918e7448",
		"input": "e3bf2295e9f693a718f3b8cbe3d4834eb88634f2cb99874288932693ca10e572",
		"other": "b2f7269e94d2e05e8dd16db583bc017e",
		"placements": "5d1920e6c959f83c2be2c4277ee96470",
		"roads": "00d3b078f11c213e8298c8f8f36e2f10",
		"splat0": "0ceae78361bd947a50939cccba02fc6a",
		"splat1": "bf5b7150120051dcb7d1db0309bcc493",
		"vegmask": "136be54fc22f10b0aeb64ce52311b0fe",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@1": {
		"biome": "e718c95985f82e283a0a1ddb64e868ab",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "175a05688b401badbf202443ca96db132e4c6f060e094fbb6f0a689f7e4dd6a0",
		"input": "fb3f4e88d7a34b381641dc148921ebaae4f865d16333ecbe28d52f0323e08766",
		"other": "bb546e313f91e8b52ded71379f76f9c9",
		"placements": "5d1920e6c959f83c2be2c4277ee96470",
		"roads": "00d3b078f11c213e8298c8f8f36e2f10",
		"splat0": "d78d3d1c7adcd17073ee13f94841048b",
		"splat1": "c67caf5c81a8976e00ee46097e877066",
		"vegmask": "3258bff7fa99aabda8dff067af3dd807",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg_drop@4": {
		"biome": "26c78a4460212fa4f279b08ac00d99b8",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "bf701a4e0b5c21fec27c1d6e4c9d3156be48a640ac6e91e0119200b65844167a",
		"input": "55fc60d20b10fd67bc2fe3543797fd76fb9e3e62ec91d4c7317d9f21bb2f1b44",
		"other": "30e8d30c7fbaa89b5ae3aeef26729e26",
		"placements": "8d23fe603d520296e6a3c93b1e7519b1",
		"roads": "0cd169ac380249eef6de628310844609",
		"splat0": "cbbf2a046e83f09005e52d11732fdadf",
		"splat1": "00d894d0e81ad8ee22e058a9c9761e40",
		"vegmask": "f8d56a7e6a1e7c2e6e80c5443c0133f2",
		"water": "d751713988987e9331980363e24189ce"
	},
	"rwg_drop@8": {
		"biome": "f3885544829784e20ba52428b4d01839",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "0eb2ecbcfb28e2b037f00e28b03f07fb51044e68e2f35d68a7307287da49f769",
		"input": "bb32553cd2ab9b3c6ce96998d34ff06fc50253bb9f1037353524ff9ad7c872f8",
		"other": "bca8f66b572aff7b224170a084da3942",
		"placements": "8d23fe603d520296e6a3c93b1e7519b1",
		"roads": "0cd169ac380249eef6de628310844609",
		"splat0": "33d7ee55842794be659352ee1649a79e",
		"splat1": "6ecc1c879e751ddc3456c5b3d028ff9f",
		"vegmask": "da04f12061242ec20aa84762da65c1b8",
		"water": "d751713988987e9331980363e24189ce"
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


func test_version_is_17() -> void:
	assert_eq(TerrainComposer.VERSION, 17, "Phase 1 changed no output; VERSION 12 is ADR-0047's town paint, 13 ADR-0059's banks and yards, 14 TD-318's street junctions, 15 world road junctions and bulbs, 16 roadside places at their road's level, 17 bridge ramps at the grade cap")


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
