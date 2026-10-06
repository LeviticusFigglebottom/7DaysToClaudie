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
		"input": "8748d38b30154e0d8f36b3e56a84d3d494750050b4790f22fa45eed2007ec5b9",
		"height": "0eaa8506c0ba2d3484781a920c3d58d080738b9bbd24dd5049779a7212d63783",
		"splat0": "b57140b9a4a248a8823629c9ae0181ca",
		"splat1": "19391a95713fd102f71d144d72dba05a",
		"biome": "7a1829b798445e721a980decdc403ccc",
		"vegmask": "76aa2381a2cbafff797251da8246ba98",
		"water": "e06b515a4cb727b37aecd8d9b9021e5c",
		"roads": "9e82e825c0312e5c65fc8edbe883d8f1",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "8f4011cac26aa26f76b8f481a81d7949",
		"other": "cdea7f25fbe2a5d7db76f5471a367e8b",
	},
	"rwg@8": {
		"input": "c79355e26825833a1949e28f4b612bb22d27557e6a4c9b618d27552044fec75c",
		"height": "9f0d511eee35a49c7efdd8195af376c67a6712bf7b1eb5a9d776476341bd9cc6",
		"splat0": "e2f1238a5db9a70e67d9a14df759fe79",
		"splat1": "6c424b2a6dc95535b4b448ddc710896d",
		"biome": "d15bf6cdbf7dc917b8c71338dccdfd18",
		"vegmask": "f18870f87931440c349cec4645cd222f",
		"water": "e06b515a4cb727b37aecd8d9b9021e5c",
		"roads": "9e82e825c0312e5c65fc8edbe883d8f1",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "8df202996e49f7aea2660e8c467c55d3",
		"other": "db456385e78c1ef69a9e46930f6a7afb",
	},
	"rwg@1": {
		"input": "574a5b8d9074a6baeb8264d0f550a0df4f83fafe8375b29d2b30ea388b63d379",
		"height": "25eedd51f00f08b54fc9f90bbef8ce8a6df18f2686f5a8e37b764797fbcbdd91",
		"splat0": "1136992f426ddc8627f9063f05247d56",
		"splat1": "dc4ef3215278fddfbda34c6216d78f86",
		"biome": "e76f894ea096b19e194d1935e27f3eec",
		"vegmask": "75d7e00fb1c0d9afa12c9792011b6a0d",
		"water": "e06b515a4cb727b37aecd8d9b9021e5c",
		"roads": "9e82e825c0312e5c65fc8edbe883d8f1",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "59f756cb79614ed2137bd5c34503ee19",
		"other": "be2cb6d869865cd65c1e45d6db34b512",
	},
	"rwg_drop@4": {
		"input": "41fb9df0ed6c18a123b9f7c542c1d659576182046b7befa4373881842c4bdf53",
		"height": "d6d973d4cb88199d886ab4b17658b8ac96a6e0d67ad4017eda2ef6979c5c95f8",
		"splat0": "e730d222f93b7762a60efa7792f53d3e",
		"splat1": "da47f68660bef05e23e84e3434ff6104",
		"biome": "1eb5c6c01866c964a329a9ecccfcd0b1",
		"vegmask": "b82b334d48abfe0c2f6708729381e727",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "692b73e2614d0630e436ef6b4d64f966",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "077354b28eb149eca57bc6578cee4b26",
		"other": "27aec2506dedd3b08659cf99db183294",
	},
	"rwg_drop@8": {
		"input": "ff5adab1d331202dee12ea484c037202da5345547b281ad2160e797933ce0c3c",
		"height": "aac5c29fa4ab97b821f201177c03a55ae3cf05f06c3b151113fc0f1a1dd40503",
		"splat0": "db6248abb9a635711c764a621a188397",
		"splat1": "520ea23af1d69e2143a5a881b07113ca",
		"biome": "c4c1336a67ed16574c87afb69b55f4c5",
		"vegmask": "27056da36569c8511a609b99f7294472",
		"water": "d751713988987e9331980363e24189ce",
		"roads": "692b73e2614d0630e436ef6b4d64f966",
		"bridges": "d751713988987e9331980363e24189ce",
		"placements": "077354b28eb149eca57bc6578cee4b26",
		"other": "de1e72e4a08456d49a175449afabfc18",
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
