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
		"biome": "7f67ee84edfe913d73903431f7843522",
		"bridges": "1f0c533e9edd7d199eef56ffe59942b6",
		"height": "fa0382dffec496dc9a6f13a9ed229fdf8b7e1f4eb122d68b39bd549b05010116",
		"input": "af418ac53901bd66ed7447b51b892dd2b5d6eabce7222aa06fee4c015e971ac8",
		"other": "0944711917e3677272bf29b704033433",
		"placements": "3c6c87a5bc023e347ea01b7b4965d83d",
		"roads": "f1d7396403b99bcf48d844e5c085ba8f",
		"splat0": "f3e95d7fbd01ce4cce1eecee40fedded",
		"splat1": "0ea8f4128bd58ef0212506b9fa022788",
		"vegmask": "dde2a91f25e7aff90055a91a7a73acad",
		"water": "557e9069b493e19e7402548619659f8b"
	},
	"larch@8": {
		"biome": "457906b117b2d6ceb4e07af1ac06dacd",
		"bridges": "259591cd5bc276b780c3fd267f0a9a6d",
		"height": "f9d38c99afdba01d2ac95e67df6a5afaa846506a68a7d728d45afb63915c5bc1",
		"input": "a4e198581301b2da959b3cf8532692b8e2f3cec471a4a46fc2ebeb7ac99a6977",
		"other": "3cbefb49c6942cf9247f8e7e0270ccf2",
		"placements": "5d8d0f5191d2528ac4acbbf8ba41e551",
		"roads": "e1eb88a14ec982a0914ecf8a64f02ee1",
		"splat0": "a2573510338c9ef6f6bc2e72639057f8",
		"splat1": "c7d388d6eac5874d78cb280323a1c1e5",
		"vegmask": "a1ce47ce0c695a2549e3378ef31c1710",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a"
	},
	"larch@1": {
		"biome": "3d47fad879193ecb4df134d0c5ec5436",
		"bridges": "428b1b895c7baf5bf0dc14187b1f2176",
		"height": "4af647fc59a66d077e8dc7174c163cdd6a0a6ae03dbd72282a1de9dc53f68464",
		"input": "8e31944e9c49bd1fa4d7666c4dc58aef860d4cea9b7aa8ca048f638b0b53ccd4",
		"other": "41849af09489e5cb2692147029d58d76",
		"placements": "bea32a60ae46d802f60494d512d92342",
		"roads": "b89ddc154644722a3a3536c7deb66d83",
		"splat0": "29b49d15bac06587b241109dbb423b8d",
		"splat1": "a66bbc1218bf90218729c37bfeef9dfa",
		"vegmask": "908e5ade6d44cbe140a24162e597a741",
		"water": "11ae9d82d419d86230b8edcb296f0984"
	},
	"rwg@4": {
		"biome": "423f701a2ad6a1eeae4150f595500be8",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "3605c88963e082092bc11b65f22bfae48aca09bb0bcf44f7ad04dfc004737b7f",
		"input": "2e5e34764dd2db7d524e1e5fbe20520e42acb28e33d1f42dface4139d378bf43",
		"other": "843b397c22a45284092e175cebfbdee7",
		"placements": "6ccb724030d27a906effd70dedfd14eb",
		"roads": "f731ba27bafe2d99a6e7d78cb4dbdd7c",
		"splat0": "c1302a02295bb64ccc8c78656d903eca",
		"splat1": "c3609448e8d6a7079a0b6310211db7fe",
		"vegmask": "468a6f2c7521431ebaaaad16f0a7b1b8",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@8": {
		"biome": "85ed8304d70982bc2fc3bc2bde33e4c5",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "9c4c1e6de323e1616c3d4677fd84b775161d07dfa88017bf35f28eb93c86f174",
		"input": "b389517f598101acd802ca326109a3487d354ea32a1f3aea2c5fa6c0f450d817",
		"other": "b2f7269e94d2e05e8dd16db583bc017e",
		"placements": "6ccb724030d27a906effd70dedfd14eb",
		"roads": "f731ba27bafe2d99a6e7d78cb4dbdd7c",
		"splat0": "fd5f2dac79ce34ab99fafa2c0bc34e90",
		"splat1": "160cf580bda9aa2a61e588408fa05c8b",
		"vegmask": "bc8e7c02e1102950cd7eedeaeff41dc2",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg@1": {
		"biome": "9d4fcb92087cd8ac8fe391f5723809bb",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "4b3f2b2bea0960950c6d1a6c66ecfa295bf7fdadfd55c93d7ac3cccb0562d513",
		"input": "433552f32b6e38e8c6b03be23f0aa7491ea8a176319f9298413087c9e0e6096b",
		"other": "bb546e313f91e8b52ded71379f76f9c9",
		"placements": "6ccb724030d27a906effd70dedfd14eb",
		"roads": "f731ba27bafe2d99a6e7d78cb4dbdd7c",
		"splat0": "57bacae396a25455d79da647f0b6e073",
		"splat1": "071c3e563e08f9d276c9e6bc66673eaf",
		"vegmask": "b6be024eb79ece0fb93f2331854e6398",
		"water": "646da548e4581b18bc1605655c50b049"
	},
	"rwg_drop@4": {
		"biome": "8a6e68d5177b478ed44b3818a3fc3944",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "9ba64507a36f981c0a13b5244b0fe0b8c7a7d1e7d48a883e88afa3ee2bf98a73",
		"input": "3a8bd7c8bb7ab54e0aa4844bc6c0bb4e80ceb770cd63edc95dac9ea42ea7625e",
		"other": "bd5dd8f87b34ef046099a6c509be10ef",
		"placements": "305896f858d96269340d2636f9333d67",
		"roads": "a9428c19054647de40763bb1a32b6cf4",
		"splat0": "410f28b0fb2c6c8271ef5eae2b6b8717",
		"splat1": "b201819613ac9aee4d8c5b0a162daf52",
		"vegmask": "49078bf68aed8c4c14737892a1447675",
		"water": "da6dc40f877b3f4b8c97f6d6f6bf3340"
	},
	"rwg_drop@8": {
		"biome": "3ea92f3174b1b2d540bf6a390d41c512",
		"bridges": "d751713988987e9331980363e24189ce",
		"height": "0a4d9a4e39933e7439b1dbc68282f5b4c8a10e87c286ab959e573223ea729642",
		"input": "e5a069b06f30ec2d95e504e3f2797bd85eb0fe66e86ae67050455bf51c27f442",
		"other": "5325eb8bd2048bedde87d89a064766fa",
		"placements": "305896f858d96269340d2636f9333d67",
		"roads": "a9428c19054647de40763bb1a32b6cf4",
		"splat0": "7f3df6ae7473e98299a42d7733a16256",
		"splat1": "8948a44b3e220888410e893e01191c59",
		"vegmask": "5cd031debfed54144ab5304f227f8e3d",
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


func test_version_is_15() -> void:
	assert_eq(TerrainComposer.VERSION, 15, "Phase 1 changed no output; VERSION 12 is ADR-0047's town paint, 13 ADR-0059's banks and yards, 14 TD-318's street junctions, 15 world road junctions and bulbs")


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
