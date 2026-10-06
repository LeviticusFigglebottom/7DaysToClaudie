class_name GameSession
extends RefCounted
## Root of all authoritative game state for one playthrough (ADR-0003).
## Presentation (nodes) reads from it and sends intents through Game.execute(); everything
## here is plain data so it can be saved, migrated and (later) replicated to co-op peers.

## "main_map" (the handcrafted Hollowmere Valley) or "random" (a generated world, ADR-0031).
var world_mode: StringName = &"main_map"
var world_id: StringName = &"hollowmere"
var world_seed: int = 0
## A random world's settings (WorldGenSettings.to_dict(): preset, map seed, values); {} on the main
## map. The world is a pure function of them, so a loaded run regenerates (or reads from cache)
## exactly the world it was played in.
var world_gen: Dictionary = {}
## The RwgGenerator VERSION that made a random world (0 on the main map, TD-140): its world id
## hashes it, so a run whose world folder is gone knows whether the current generator remakes it.
var generator_version: int = 0
## Where a random world's files come from: "shared" (user://worlds/random/<id>/, the generator's
## cache) or "slot" (restored from the save's own world bundle, save v7).
var world_files: StringName = &"shared"
## TerrainComposer.VERSION the run's world was composed with (0: before save v7 recorded it). A
## composer change that re-scatters vegetation invalidates saved per-instance vegetation records
## where it changed (SaveSystem.fix_composer_changes, TD-182).
var composer_version: int = 0
## Game mode preset id (data/config/game_modes.json): "survival", "slice", ...
var game_mode: StringName = &"survival"
## World settings (difficulty preset + customised options), saved with the session.
var rules: GameRules
var created_unix: int = 0
var play_seconds: float = 0.0
var clock: WorldClock
var ids: IdAllocator
var rng: RngStreams
var players: Dictionary = {}
var local_player_id: StringName = &"p:1"
var world: WorldState
var horde: HordeMemory
var heat: HeatMap
var weather: WeatherState
var stats: Dictionary = {"zombies_killed": 0, "hums_survived": 0, "trees_felled": 0, "pois_cleared": 0}


static func create_new(options: Dictionary = {}) -> GameSession:
	var s := GameSession.new()
	s.world_mode = StringName(str(options.get("world_mode", "main_map")))
	s.world_id = StringName(str(options.get("world_id", "hollowmere")))
	s.world_seed = int(options.get("seed", 4471))
	s._set_world_gen(options.get("world_gen", {}))
	s.game_mode = StringName(str(options.get("game_mode", "survival")))
	s.created_unix = int(Time.get_unix_time_from_system())
	s.composer_version = int((load("res://src/worldgen/terrain_composer.gd") as GDScript).get_script_constant_map().get("VERSION", 0))
	s.rules = GameRules.resolve(s.mode_config().get("rules", {}), StringName(str(options.get("preset", "survivor"))), options.get("rules", {}))
	s._init_systems()
	var mode: Dictionary = s.mode_config()
	s.clock.set_time(int(mode.get("start_day", 1)), float(mode.get("start_hour", 7.5)))
	var p := PlayerState.new()
	p.id = s.local_player_id
	s.players[p.id] = p
	return s


## A random world's settings: normalised through WorldGenSettings, the mode set and the id derived
## (by script path: the session compiles before the editor registers the generator's classes).
func _set_world_gen(gen: Variant) -> void:
	if not gen is Dictionary or (gen as Dictionary).is_empty():
		world_gen = {}
		return
	var settings: RefCounted = (load("res://src/worldgen/rwg/world_gen_settings.gd") as GDScript).call(&"from_dict", gen)
	world_gen = settings.call(&"to_dict")
	world_mode = &"random"
	var gen_script: GDScript = load("res://src/worldgen/rwg/rwg_generator.gd") as GDScript
	world_id = StringName(str(gen_script.call(&"world_id_for", settings)))
	generator_version = int(gen_script.get_script_constant_map().get("VERSION", 0))


func is_random_world() -> bool:
	return world_mode == &"random" and not world_gen.is_empty()


func _init_systems() -> void:
	if rules == null:
		rules = GameRules.resolve(mode_config().get("rules", {}), &"survivor", {})
	clock = WorldClock.new()
	var horde_cfg: Dictionary = Content.config(&"horde").duplicate()
	horde_cfg["first_day"] = rules.integer("hum_first_day")
	horde_cfg["interval_days"] = rules.integer("hum_every_days")
	horde_cfg["variance_days"] = rules.integer("hum_variance_days")
	horde_cfg["seed"] = world_seed
	var clock_cfg: Dictionary = Content.config(&"world_clock").duplicate(true)
	clock_cfg["day_length_minutes"] = rules.integer("day_length_minutes")
	var seasons: Dictionary = clock_cfg.get("seasons", {})
	seasons["start"] = rules.choice("start_season")
	clock_cfg["seasons"] = seasons
	clock.configure(clock_cfg, horde_cfg)
	ids = IdAllocator.new()
	rng = RngStreams.new(world_seed)
	world = WorldState.new()
	horde = HordeMemory.new()
	heat = HeatMap.new()
	heat.configure(Content.config(&"heat"))
	weather = WeatherState.new()


func mode_config() -> Dictionary:
	return (Content.config(&"game_modes").get("modes", {}) as Dictionary).get(String(game_mode), {})


func local_player() -> PlayerState:
	return players.get(local_player_id)


func days_survived() -> int:
	return maxi(0, clock.day() - 1)


## How hard the world pushes back (7 Days' gamestage): player level plus days survived, both
## scaled by the world settings. Drives spawn composition, Hum size and loot quality.
func gamestage(p: PlayerState = null) -> int:
	if p == null:
		p = local_player()
	var level: int = p.progression.level if p != null else 1
	var gs: float = (float(level) + float(days_survived()) * rules.num("gamestage_days_weight")) * rules.num("gamestage_bonus")
	return maxi(1, int(round(gs)))


func to_dict() -> Dictionary:
	var ps: Dictionary = {}
	for pid: StringName in players:
		ps[String(pid)] = (players[pid] as PlayerState).to_dict()
	return {
		"world_mode": String(world_mode), "world_id": String(world_id), "seed": str(world_seed), "world_gen": world_gen,
		"game_mode": String(game_mode), "rules": rules.to_dict(), "created": created_unix, "play_seconds": play_seconds,
		"clock": clock.to_dict(), "ids": ids.to_dict(), "rng": rng.to_dict(), "players": ps,
		"local_player": String(local_player_id), "world": world.to_dict(), "horde": horde.to_dict(),
		"heat": heat.to_dict(), "weather": weather.to_dict(), "stats": stats,
		"generator_version": generator_version, "world_files": String(world_files), "composer_version": composer_version,
	}


static func from_dict(d: Dictionary) -> GameSession:
	var s := GameSession.new()
	s.world_mode = StringName(str(d.get("world_mode", "main_map")))
	s.world_id = StringName(str(d.get("world_id", "hollowmere")))
	s.world_seed = int(str(d.get("seed", "0")))
	s._set_world_gen(d.get("world_gen", {}))
	# The saved id wins: it names the generated world on disk this run was played in, even if the
	# generator has changed since (RwgWorlds reads that world before it regenerates anything).
	s.world_id = StringName(str(d.get("world_id", s.world_id)))
	s.generator_version = int(d.get("generator_version", s.generator_version if s.is_random_world() else 0))
	s.world_files = StringName(str(d.get("world_files", "shared")))
	s.composer_version = int(d.get("composer_version", 0))
	s.game_mode = StringName(str(d.get("game_mode", "survival")))
	s.created_unix = int(d.get("created", 0))
	s.play_seconds = float(d.get("play_seconds", 0.0))
	s.rules = GameRules.from_dict(d.get("rules", {}), s.mode_config().get("rules", {}))
	s._init_systems()
	s.clock.from_dict(d.get("clock", {}))
	s.ids.from_dict(d.get("ids", {}))
	s.rng.from_dict(d.get("rng", {}))
	s.local_player_id = StringName(str(d.get("local_player", "p:1")))
	for pid: Variant in (d.get("players", {}) as Dictionary).keys():
		var p := PlayerState.new()
		p.from_dict(d["players"][pid])
		s.players[p.id] = p
	s.world.from_dict(d.get("world", {}))
	s.horde.from_dict(d.get("horde", {}))
	s.heat.from_dict(d.get("heat", {}))
	s.weather.from_dict(d.get("weather", {}))
	s.stats.merge(d.get("stats", {}), true)
	return s
