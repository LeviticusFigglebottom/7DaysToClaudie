extends Node
## The work of list_encounters.gd, loaded once the autoloads exist (see its header). A random world
## (--world-seed) is generated into user://encounter_cli/ (never the game's world cache, which a
## generation there would prune), its frameworks registered, and its regions composed at --spacing
## (default 1 m, the play spacing; coarser is faster and close, not identical).

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const TMP: String = "user://encounter_cli"


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var spacing: float = float(_arg(a, "--spacing", "1.0"))
	var density: float = float(_arg(a, "--density", "1.0"))
	var world_path: String = _arg(a, "--world", "res://world/main_map")
	var seed_v: int = 0
	if _arg(a, "--world-seed", "") != "":
		seed_v = int(_arg(a, "--world-seed", "1"))
		var overrides: Dictionary = {}
		for kv: String in _arg(a, "--world-set", "size=3").split(",", false):
			var p: PackedStringArray = kv.split("=", true, 1)
			if p.size() == 2:
				overrides[p[0]] = p[1]
		var s: RefCounted = GenSettings.resolve(&"standard", overrides, seed_v)
		var g: RefCounted = Generator.generate(s)
		world_path = TMP.path_join(Generator.world_id_for(s))
		if Worlds.write(g, world_path) != OK:
			printerr("[encounters] could not write %s" % world_path)
			get_tree().quit(1)
			return
	if FileAccess.file_exists(world_path.path_join("frameworks.json")):
		for e: String in Worlds.register_frameworks(world_path):
			push_warning("list_encounters: %s" % e)
	var world: WorldDef = WorldDef.load_from(world_path)
	if world == null:
		get_tree().quit(1)
		return
	if seed_v == 0:
		# The main map's runs use the session's seed; its world.json seed is the default.
		seed_v = int(_arg(a, "--seed", str(world.seed)))
	var ids: Array = []
	if a.has("--all"):
		for rid: String in world.regions:
			if world.is_region_built(rid):
				ids.append(rid)
		ids.sort()
	else:
		ids = [_arg(a, "--region", "d6_larch_hollow" if world_path.begins_with("res://world/main_map") else _first_built(world))]
	var cfg: Dictionary = Content.config(&"encounters")
	var tally: Dictionary = {}
	var total: int = 0
	var area: float = 0.0
	print("[encounters] world %s seed %d density %.2f spacing %s m" % [world_path, seed_v, density, spacing])
	for rid: String in ids:
		var rt: RegionTerrain = TerrainComposer.get_or_compose(world, rid, spacing)
		if rt == null:
			printerr("[encounters] %s did not compose" % rid)
			continue
		var t0: int = Time.get_ticks_usec()
		var sites: Array[Dictionary] = EncounterPlanner.plan_region(rt, seed_v, density, cfg)
		var ms: float = float(Time.get_ticks_usec() - t0) / 1000.0
		area += rt.rect.get_area() / 1.0e6
		print("[encounters] %s: %d sites in %.0f ms" % [rid, sites.size(), ms])
		for s: Dictionary in sites:
			var p: Vector3 = s["pos"]
			print("  %-14s %-20s %-6s at (%7.1f, %6.1f, %7.1f) yaw %4.0f  %s%s" % [s["id"], s["def"], s["kind"], p.x, p.y, p.z,
				rad_to_deg(float(s["yaw"])), rt.biome_at(p.x, p.z), "  trunk %.2f" % float(s["trunk"]) if float(s["trunk"]) > 0.0 else ""])
			tally[s["def"]] = int(tally.get(s["def"], 0)) + 1
			total += 1
	var keys: Array = tally.keys()
	keys.sort()
	var parts: PackedStringArray = []
	for k: Variant in keys:
		parts.append("%s %d" % [k, tally[k]])
	print("[encounters] %d sites over %.2f km² (%.1f per km²): %s" % [total, area, total / maxf(area, 0.001), ", ".join(parts)])
	get_tree().quit(0)


static func _first_built(world: WorldDef) -> String:
	var ids: Array = world.regions.keys()
	ids.sort()
	for rid: String in ids:
		if world.is_region_built(rid):
			return rid
	return str(ids[0]) if not ids.is_empty() else ""


static func _arg(a: PackedStringArray, key: String, default: String) -> String:
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else default
