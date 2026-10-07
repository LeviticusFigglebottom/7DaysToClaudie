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
## stream; the town region's ground, roads and masks moved with it). Larch Hollow's were
## re-recorded when Ezra's camp was placed west of Larch Pond (ADR-0058: its pad), and
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
		"input": "e0c0ea104fa38282afffe188dad20da56f733f62c377eca299ceed2cd4b7d077",
		"height": "e248604a3a8de7f24a32543ec40bf9560ccefc552661a9c885263828e47dce2d",
		"splat0": "9eaa4a77bd78f034bfd9ff38f1d3aca6",
		"splat1": "a0e0f3e9d0ea61b64313f463af34b2c4",
		"biome": "7724250f9597cd3eb469e098b3580cbb",
		"vegmask": "e2c94c24b7980d9e7138cbb025da7bce",
		"water": "557e9069b493e19e7402548619659f8b",
		"roads": "3cd6abe5ddc37e6287223186137e5441",
		"bridges": "f97bf6a0088f3da534491ebf01e8e086",
		"placements": "6359dea63ad6dc11aa5ee3e72083268d",
		"other": "343d7ca5a31189c644d8aca5e9ee0028",
	},
	"larch@8": {
		"input": "afdfccb469a7ea408e9d2006e06eb3dd2b6c00f1a4e8d1d16b66766a1788d483",
		"height": "2bc10a81f1b49707261a58c7d495f0a3ade56606690d1b0efc7e4f80caf82a35",
		"splat0": "5af3e41b715d69b44160b1ec75ee5e61",
		"splat1": "71f4ef029e083c97ad7fdbac70c5e563",
		"biome": "00c074e8e4ab91a87a1bea29881e9d38",
		"vegmask": "d3437253c830a77214485e0a2384a503",
		"water": "43ffa565190e27f18b8b0f4c0013ec3a",
		"roads": "b18902326c95c025e50cca0eaa479f9f",
		"bridges": "10e8c17e881965fe5bc24d68509cbd54",
		"placements": "9b70d567d5d6cab238473683a3a2f4e2",
		"other": "0619089a625a0d5200fa83faa962ee3c",
	},
	"larch@1": {
		"input": "2264d429ccee2fa81bacba1f6a83571876faaf332ca5c4efd87ca1f190a79681",
		"height": "d3796a5996202fff75c0a023ce00b814da671798d1220690307a4fd1f65f0292",
		"splat0": "b1547471ef8d74630f9f335902e870b0",
		"splat1": "55b0189d93e9a60ec3392ca26604f9ad",
		"biome": "8b2ebfa6a883e1c944bf044b951f157a",
		"vegmask": "989d9a9c3a113b51d4af4aec666f8a0a",
		"water": "11ae9d82d419d86230b8edcb296f0984",
		"roads": "a708bdec066cd3e76cad905f6bf65e75",
		"bridges": "ef252ccce52545ebe035c7e9169fe945",
		"placements": "633a360b2db11afde4b68b1b4fea5501",
		"other": "9042e6121a94f2a29c717a3d15b2b03d",
	},
	"rwg@4": {
		"input": "3e9322dcb1d9d4cc8e6e25b516150ee858c68dc3bf14b40babf8560ed1590dee",
		"height": "e95616bb3bb5ebd3aa01b2168583231674fbb22cca258514ad4d308478250cef",
		"splat0": "08b2849cf65a8420fa1e34589243bf1e",
		"splat1": "c111b88e7e976ef14ad6054fd23ad1f2",
		"biome": "5e99f416ed32b7951d90e2fe0d4a6069",
		"vegmask": "9d508fd7f9a3c5edb4e76caa43343d46",
		"water": "49e108a32077cec749d37e86d197b32f",
		"roads": "dffeb26912dec0b02ad9e2694c9569ae",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "ab437bd9be24c97cc64fcbe83c0e3796",
		"other": "cec63ec5e9ea167c69260cbaf86a1d0a",
	},
	"rwg@8": {
		"input": "979c294688688f9b056c06370f21b53fe4bf7dd5064bc215d0788caf8b4345fe",
		"height": "3f2d20efcdaf08e5c5cee42f9c5b67515d723a04e870b959914d0d32160f4708",
		"splat0": "5cfb388da93427d5a97a53e37eeed064",
		"splat1": "960ad4f5cd5c5f6c28a80a7c1fed0e1d",
		"biome": "88206e088b975743fe235c342302dd6f",
		"vegmask": "207ee4a117c9b9f439b8f42cdb453f29",
		"water": "fd041168cd7a58fb4b7994caf5864ac8",
		"roads": "dffeb26912dec0b02ad9e2694c9569ae",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "c179b97cfc33b6d40b9709a7e0d72cc3",
		"other": "bcea77cbf3c997af1ab262307621ca3b",
	},
	"rwg@1": {
		"input": "da44dfa725a16acc865ec74c5f92d5a20ee77c5ce1c2f15cc78236c8fe7e9465",
		"height": "e744edba2d0696ad86381b15783ee1ffbb5b4e08a9372d836df2f6f3ac1ec06c",
		"splat0": "e786834259ab79b1d4c1b7d0fa00295c",
		"splat1": "1934dc9dd0d12e25a0d5f277d8e33016",
		"biome": "91feb6f8070d8d6ee3a82218656fd072",
		"vegmask": "c8e800c3928de822f65e7d9262fe61e4",
		"water": "0815ff0f2b7d71ee76189c656a648066",
		"roads": "dffeb26912dec0b02ad9e2694c9569ae",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "4f5cf254c61bed03f5fd3e653f4803ee",
		"other": "445eed2000fca209f9b0b52d17c5924b",
	},
	"rwg_drop@4": {
		"input": "d6523162b7dd060868ef5f73c4c7dc66cded8269657203c48f66de5f4ac8d51c",
		"height": "c176d0709f4d21b4aa95532b211d0af63be784541958436e0b00fea36a978488",
		"splat0": "5e0b93f23957c50754121ac1a52c2f04",
		"splat1": "4516aea033ac574140369ed02cdb8985",
		"biome": "1c6ad66f8a087571d27204d512eec86c",
		"vegmask": "5ae56c7dde25bccc12599228f46170d5",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "55e38ab4fee27a5046d2594c4af1adaf",
		"other": "5bc27312937ee0c0680239869cc69b16",
	},
	"rwg_drop@8": {
		"input": "8323c6cae43fc359632957529fa5da04209ea42a6a7d53a2636c6a58397cdc07",
		"height": "2627c13e991906fd2eec9fee5bfe187d9f52e2a8c5c6e5232a09a6a6a5e85399",
		"splat0": "5e80c496aff37e4da35832c26eb881cc",
		"splat1": "b56557e643b782752c0d4bccd7fc7fe3",
		"biome": "b194762f7ae3b4cf3de942ab720b9d08",
		"vegmask": "742ad0ae10522fcdfc1c6eecb7c3104f",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "f0db205ae7464b3a50176b11cd609325",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "55e38ab4fee27a5046d2594c4af1adaf",
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
