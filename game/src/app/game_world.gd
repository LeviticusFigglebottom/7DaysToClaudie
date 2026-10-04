class_name GameWorld
extends Node3D
## In-game root. Loads the world on a worker thread behind a loading screen, then wires every
## world system together, spawns the player and hooks save/load. Systems are children and are
## reachable as typed properties (Game.world.terrain, .building, .ai, ...).

signal world_ready()

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const MAIN_WORLD_DIR: String = "res://world/main_map"

var session: GameSession
var world_def: WorldDef
var terrain: TerrainManager
var env: EnvironmentController
var clock_driver: WorldClockDriver
var stimuli: Stimuli
var actions: PlayerActions
var player: Player
var ui: GameUI
## Optional systems (registered by their modules as they come online).
var water: Node = null
var vegetation: Node = null
var pois: Node = null
var building: Node = null
var ai: Node = null
var loose: Node = null
var ambience: Node = null
var is_ready: bool = false
var sleeping: bool = false

var _loader: WorldLoader
var _load_task: int = -1
var _spawn_settle: int = 0


func _ready() -> void:
	Game.world = self
	session = Game.session
	if session == null:
		session = Game.new_session({"game_mode": "survival"})
	ui = GameUI.new()
	ui.name = "UI"
	add_child(ui)
	ui.show_loading("Entering the Cordon…", 0.0)
	_loader = WorldLoader.new()
	var dir: String = MAIN_WORLD_DIR
	_load_task = WorkerThreadPool.add_task(func() -> void: _loader.load_world(dir), true, "world load")


func _exit_tree() -> void:
	if _load_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_load_task)
		_load_task = -1
	if Game.world == self:
		Game.world = null


func _process(_delta: float) -> void:
	if _load_task >= 0:
		ui.show_loading(_loader.stage, _loader.progress)
		if WorkerThreadPool.is_task_completed(_load_task):
			WorkerThreadPool.wait_for_task_completion(_load_task)
			_load_task = -1
			if _loader.error != "":
				ui.show_loading("Failed: %s" % _loader.error, 1.0)
				return
			_on_world_loaded()
		return
	if not is_ready and player != null:
		ui.show_loading("Finding your feet…", 0.95)
		if terrain.is_ready_around(player.global_position, 1):
			_spawn_settle += 1
			if _spawn_settle > 3:
				_finish_spawn()


func _on_world_loaded() -> void:
	world_def = _loader.world
	stimuli = Stimuli.new()
	stimuli.name = "Stimuli"
	stimuli.heat = session.heat
	add_child(stimuli)
	terrain = TerrainManager.new()
	terrain.name = "Terrain"
	add_child(terrain)
	terrain.setup(world_def, _loader.detailed, _loader.coarse)
	terrain.load_from(session.world)
	env = EnvironmentController.new()
	env.name = "Environment"
	env.clock = session.clock
	env.weather = session.weather
	add_child(env)
	clock_driver = WorldClockDriver.new()
	clock_driver.name = "Clock"
	clock_driver.session = session
	clock_driver.weather = session.weather
	add_child(clock_driver)
	actions = PlayerActions.new()
	actions.name = "Actions"
	actions.world = self
	add_child(actions)
	clock_driver.game_minutes_passed.connect(_on_game_minutes)
	_spawn_modules()
	_spawn_player()
	Events.game_saving.connect(_on_game_saving)
	if DebugTools.enabled():
		var dbg := DebugOverlay.new()
		dbg.name = "Debug"
		add_child(dbg)
		dbg.setup(self)


## Optional modules: instantiated if their scripts exist (lets systems land incrementally).
func _spawn_modules() -> void:
	var mods: Array = [
		["water", "res://src/world/water/water_system.gd"],
		["vegetation", "res://src/world/vegetation/vegetation_manager.gd"],
		["loose", "res://src/world/loose_items.gd"],
		["building", "res://src/building/building_manager.gd"],
		["pois", "res://src/poi/poi_manager.gd"],
		["ai", "res://src/ai/ai_director.gd"],
		["ambience", "res://src/audio/ambience_director.gd"],
	]
	for m: Array in mods:
		if ResourceLoader.exists(m[1]):
			var node: Node = (load(m[1]) as GDScript).new()
			node.name = str(m[0]).capitalize()
			set(m[0], node)
			add_child(node)
			if node.has_method(&"setup_world"):
				node.call(&"setup_world", self)


func _spawn_player() -> void:
	var p: PlayerState = session.local_player()
	var is_new: bool = bool(Game.pending_options.get("is_new_game", false))
	if is_new:
		var spawn: Dictionary = _find_spawn("drop_site")
		var pos: Vector3 = spawn.get("pos", Vector3.ZERO)
		p.position = pos + Vector3.UP * 2.0
		p.yaw = deg_to_rad(float(spawn.get("yaw", 0.0)))
		p.spawn_point = pos
		_give_start_kit(p)
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	add_child(player)
	player.bind_state(p)
	player.input_enabled = false
	player.died.connect(_on_player_died)
	terrain.focus = player
	terrain.update_streaming(player.global_position, true)
	if stimuli != null:
		stimuli.recenter(player.global_position)


func _find_spawn(id: String) -> Dictionary:
	for rid: String in _loader.detailed:
		var rt: RegionTerrain = _loader.detailed[rid]
		if rt.spawns.has(id):
			var s: Dictionary = rt.spawns[id]
			var a: Array = s["pos"]
			return {"pos": Vector3(float(a[0]), float(a[1]), float(a[2])), "yaw": float(s.get("yaw", 0.0)), "props": s.get("props", [])}
	return {"pos": Vector3(0, terrain.height_at(0, 0), 0), "yaw": 0.0}


func _give_start_kit(p: PlayerState) -> void:
	var kit: Dictionary = Content.config(&"player").get("start_kit", {})
	for k: Variant in kit.keys():
		p.inventory.add_item(StringName(str(k)), int(kit[k]))
	p.toolbelt[0] = &"lighter"


func _finish_spawn() -> void:
	# Drop the player onto the ground (terrain collision now exists).
	var pos: Vector3 = player.global_position
	var ground: float = terrain.height_at(pos.x, pos.z)
	if pos.y < ground + 0.2 or pos.y > ground + 30.0:
		player.global_position = Vector3(pos.x, ground + 0.4, pos.z)
	player.input_enabled = true
	is_ready = true
	ui.hide_loading()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	Events.session_started.emit(bool(Game.pending_options.get("is_new_game", false)))
	Events.player_spawned.emit(player.state.id)
	world_ready.emit()


func _on_game_saving(_slot: String) -> void:
	if player != null:
		player.write_state()
	if terrain != null:
		terrain.save_into(session.world)
	for sys: Node in [vegetation, loose, building, pois, ai]:
		if sys != null and sys.has_method(&"save_into"):
			sys.call(&"save_into", session)


func _unhandled_input(event: InputEvent) -> void:
	if not is_ready:
		return
	if event.is_action_pressed(&"pause"):
		ui.toggle_pause()
	elif event.is_action_pressed(&"quicksave"):
		Game.save_game("quicksave")
	elif event.is_action_pressed(&"quickload"):
		if SaveSystem.slot_exists("quicksave"):
			Game.load_game("quicksave")
	elif event.is_action_pressed(&"screenshot"):
		var path: String = "user://screenshot_%d.png" % Time.get_unix_time_from_system()
		get_viewport().get_texture().get_image().save_png(path)
		Events.player_status_message.emit("Screenshot saved.", &"info")


func player_node(_player_id: StringName) -> Player:
	return player


func height_at(x: float, z: float) -> float:
	return terrain.height_at(x, z) if terrain != null else 0.0


# --- Survival ----------------------------------------------------------------------------------

func _on_game_minutes(minutes: float) -> void:
	var p: PlayerState = session.local_player()
	if p == null or player == null or not is_ready or DebugTools.is_on(&"no_hunger"):
		return
	p.stats.tick_game(minutes, survival_env(player.global_position))


## Environment the body feels at a position (SurvivalStats.tick_game env contract).
func survival_env(pos: Vector3) -> Dictionary:
	var w: Dictionary = session.weather.params()
	var climate: Dictionary = Content.config(&"survival").get("climate", {})
	var band: Array = climate.get(session.clock.season(), [5.0, 15.0])
	# Coldest around 03:00, warmest around 15:00.
	var daily: float = 0.5 + 0.5 * sin((session.clock.hour_f() - 9.0) / 24.0 * TAU)
	var ambient: float = lerpf(float(band[0]), float(band[1]), daily) + float(w.get("temperature_offset", 0.0))
	var rt: RegionTerrain = terrain.region_terrain_at(pos.x, pos.z) if terrain != null else null
	if rt != null:
		var b: BiomeDef = Content.get_def(&"biome", StringName(rt.biome_at(pos.x, pos.z))) as BiomeDef
		if b != null:
			ambient += b.temperature_offset
	ambient -= maxf(0.0, pos.y - 80.0) * 0.0065
	var sheltered: bool = false
	if building != null and building.has_method(&"is_sheltered"):
		sheltered = building.call(&"is_sheltered", pos)
	if not sheltered and pois != null and pois.has_method(&"is_indoors"):
		sheltered = pois.call(&"is_indoors", pos)
	var fire: float = float(building.call(&"warmth_at", pos)) if building != null and building.has_method(&"warmth_at") else 0.0
	var exertion: float = 0.0
	if player != null:
		exertion = clampf(player.horizontal_speed() / 6.0, 0.0, 1.0) if not sleeping else 0.0
	return {"ambient_c": ambient, "wind": float(w.get("wind", 0.2)), "raining": float(w.get("rain", 0.0)) > 0.3 and not sheltered,
		"sheltered": sheltered, "fire_warmth": fire, "sleeping": sleeping, "exertion": exertion}


# --- Sleep, death, respawn ----------------------------------------------------------------------

## Sleep at a bed/shelter: sets the respawn point, skips to dawn (or naps 2 h by day), saves.
func try_sleep(p: Player, bed: Node3D) -> void:
	if sleeping or p == null:
		return
	if session.clock.is_horde_active():
		Events.player_status_message.emit("The Hum is too loud to sleep through.", &"warning")
		return
	if ai != null and ai.has_method(&"hostiles_near") and int(ai.call(&"hostiles_near", p.global_position, 25.0)) > 0:
		Events.player_status_message.emit("You can't sleep with Hollowed this close.", &"warning")
		return
	var h: float = session.clock.hour_f()
	var hours: float = fposmod(6.0 - h, 24.0) if (h >= 19.0 or h < 5.0) else 2.0
	var until_hum: float = session.clock.hours_until_horde()
	if until_hum > 0.0 and until_hum < hours + 1.0:
		hours = maxf(0.25, until_hum - 1.0)
	p.state.spawn_point = bed.global_position + Vector3.UP * 0.6
	p.state.has_spawn_point = true
	sleeping = true
	p.input_enabled = false
	if ui.has_method(&"show_sleep"):
		ui.call(&"show_sleep", true)
	var slept: float = hours
	clock_driver.fast_forward(hours, clampf(hours * 0.5, 2.0, 5.0), func() -> void: _on_woke(slept))


func _on_woke(hours: float) -> void:
	sleeping = false
	if player != null and player.state.stats.alive:
		player.input_enabled = true
	if ui.has_method(&"show_sleep"):
		ui.call(&"show_sleep", false)
	Events.player_slept.emit(player.state.id, hours)
	Game.save_game("autosave")
	Events.player_status_message.emit("Rested. Progress saved.", &"info")


func _on_player_died(cause: String) -> void:
	var p: PlayerState = player.state
	p.deaths += 1
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	# Everything carried stays where you fell, in a pack you can walk back to.
	var pack: Array = []
	for st: ItemStack in p.inventory.stacks:
		if st.def() != null and not st.def().has_tag("no_drop"):
			pack.append(st)
	for st: ItemStack in pack:
		p.inventory.take_from(st, st.count)
		ItemDrop.spawn(loose if loose != null else self, st, player.global_position + Vector3(randf_range(-0.6, 0.6), 0.8, randf_range(-0.6, 0.6)))
	if ui.has_method(&"show_death"):
		ui.call(&"show_death", cause)
	else:
		get_tree().create_timer(4.0).timeout.connect(respawn)


func respawn() -> void:
	var p: PlayerState = player.state
	var pos: Vector3 = p.spawn_point if p.has_spawn_point else _find_spawn("drop_site").get("pos", Vector3.ZERO)
	p.stats.revive(50.0)
	player.global_position = pos + Vector3.UP * 0.5
	player.velocity = Vector3.ZERO
	terrain.update_streaming(player.global_position, true)
	player.input_enabled = true
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	Events.player_spawned.emit(p.id)
