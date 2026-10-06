extends Node
## The work of rwg_preview.gd, loaded once the autoloads exist: resolves the settings, generates
## the world (or reads it from user://worlds/random/), writes its map PNG and prints a summary.
## `--memory` draws the map straight from the generator without writing the world; `--fresh`
## removes the cached world (and its composed terrain) first, so the run times a full
## generation; `--compose` also shapes every region into the terrain cache, as the game's first
## load would (QA renders then start without that wait).

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const MapImage := preload("res://src/worldgen/rwg/rwg_map.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var overrides: Dictionary = {}
	for i: int in a.size() - 1:
		if a[i] == "--set" and a[i + 1].contains("="):
			var kv: PackedStringArray = a[i + 1].split("=", true, 1)
			overrides[kv[0]] = kv[1]
	if _arg(a, "--size", "") != "":
		overrides["size"] = _arg(a, "--size", "4")
	var settings: RefCounted = GenSettings.resolve(StringName(_arg(a, "--preset", "standard")), overrides, int(_arg(a, "--seed", "1")))
	var out: String = _arg(a, "--out", ProjectSettings.globalize_path("res://").path_join("../build/rwg_preview/map.png"))
	var px: int = int(_arg(a, "--px", "1024"))
	DirAccess.make_dir_recursive_absolute(out.get_base_dir())
	var wid: String = Generator.world_id_for(settings)
	if a.has("--fresh"):
		Worlds._remove(Worlds.dir_for(wid))
		Worlds._remove("user://cache/worlds".path_join(wid))
	print("[rwg] %s (%s), world %s" % [settings.call(&"summary"), settings.get(&"preset"), wid])
	var t0: int = Time.get_ticks_msec()
	# --memory: generate and draw without writing the world to user://worlds (nothing cached or pruned).
	if a.has("--memory"):
		var g: RefCounted = Generator.generate(settings)
		var regions: Array = []
		var ids: Dictionary = g.call(&"region_ids")
		for cell: Variant in ids:
			regions.append(g.call(&"region_json", str(cell)))
		var wj: Dictionary = g.call(&"world_json")
		var m: RefCounted = MapImage.new()
		(m.call(&"render", wj, regions, g.call(&"frameworks_json"), px) as Image).save_png(out)
		print("[rwg] generated in memory in %d ms: %d towns, %d places, %d rivers, %d lakes, %d roads; timings %s; warnings %s -> %s" % [Time.get_ticks_msec() - t0,
			(g.get(&"towns") as Array).size(), (g.get(&"places") as Array).size(), (wj["rivers"] as Array).size(), (wj["lakes"] as Array).size(),
			(wj["roads"] as Array).size(), g.get(&"timings"), g.get(&"warnings"), out])
		get_tree().quit(0)
		return
	var res: Dictionary = Worlds.ensure(settings, func(stage: String, t: float) -> void: print("  [%3d%%] %s (%d ms)" % [int(t * 100), stage, Time.get_ticks_msec() - t0]), a.has("--compose"))
	if not bool(res.get("ok", false)):
		printerr("[rwg] FAILED: %s" % res.get("error", ""))
		get_tree().quit(1)
		return
	print("[rwg] %s in %d ms -> %s" % ["generated" if bool(res["generated"]) else "read from cache", int(res["ms"]), ProjectSettings.globalize_path(str(res["dir"]))])
	var img: Image = MapImage.render_dir(str(res["dir"]), px)
	# --crop x,z,metres: a square of the map around a world point (QA of a town's plan).
	var crop: String = _arg(a, "--crop", "")
	if crop != "":
		var cv: PackedStringArray = crop.split(",")
		var half_m: float = float(settings.call(&"integer", "size")) * 512.0
		var mpp: float = half_m * 2.0 / px
		var cx: int = int((float(cv[0]) + half_m) / mpp)
		var cz: int = int((float(cv[1]) + half_m) / mpp)
		var hs: int = int(float(cv[2]) * 0.5 / mpp)
		img = img.get_region(Rect2i(cx - hs, cz - hs, hs * 2, hs * 2).intersection(Rect2i(0, 0, px, px)))
	img.save_png(out)
	var world: Dictionary = MapImage._read(str(res["dir"]).path_join("world.json"))
	var gen: Dictionary = world.get("generator", {})
	var lots: int = 0
	for tw: Variant in gen.get("towns", []):
		lots += int((tw as Dictionary).get("lots", 0))
		print("  town  %-16s %-8s %3d lots  %s" % [str(tw["name"]), str(tw["kind"]), int(tw["lots"]), str(tw["region"])])
	var by_def: Dictionary = {}
	for pl: Variant in gen.get("places", []):
		by_def[str(pl["def"])] = int(by_def.get(str(pl["def"]), 0)) + 1
	for d: Variant in by_def:
		print("  place %-24s x%d" % [d, int(by_def[d])])
	var classes: Dictionary = {}
	var bridges: int = 0
	for rd: Variant in world.get("roads", []):
		classes[str(rd["class"])] = int(classes.get(str(rd["class"]), 0)) + 1
		bridges += (rd["bridges"] as Array).size()
	print("[rwg] %d towns (%d lots), %d places, %d rivers, %d lakes, roads %s, %d bridges; drop site %s" % [(gen.get("towns", []) as Array).size(), lots,
		(gen.get("places", []) as Array).size(), (world.get("rivers", []) as Array).size(), (world.get("lakes", []) as Array).size(), classes, bridges, gen.get("drop_site", [])])
	for w: Variant in gen.get("warnings", []):
		print("[rwg] warning: %s" % w)
	print("[rwg] timings %s" % gen.get("timings_ms", {}))
	if a.has("--compose"):
		var t1: int = Time.get_ticks_msec()
		var wl := WorldLoader.new()
		wl.load_world(str(res["dir"]))
		print("[rwg] composed %d regions in %d ms (%s)" % [wl.detailed.size(), Time.get_ticks_msec() - t1, wl.error if wl.error != "" else "ok"])
	print("[rwg] map -> %s" % out)
	get_tree().quit(0)


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default
