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
var bridges: Node = null
var road_markings: Node = null
var vegetation: Node = null
var pois: Node = null
var building: Node = null
var ai: Node = null
var loose: Node = null
var ambience: Node = null
var supply_drops: Node = null
var directives: Node = null
var wildlife: Node = null
var is_ready: bool = false
## Framework lots resolved by the world loader (WorldLoader.lots), read by the POI manager.
var poi_lots: Dictionary = {}
var sleeping: bool = false

var _loader: WorldLoader
var _load_task: int = -1
var _spawn_settle: int = 0
## The main-thread half of the load (ADR-0036): [label, Callable, name] steps, run a few a frame
## within BOOT_BUDGET_MS so the window keeps answering the OS (one long frame here made Windows
## flag the game as not responding). _boot_i = -1: not booting.
const BOOT_BUDGET_MS: float = 40.0
## Share of the loading bar the worker thread's half fills; the boot steps fill the rest to 0.95.
const WORKER_SHARE: float = 0.7
var _boot: Array = []
var _boot_i: int = -1
var _held: Dictionary = {}
var _load_meter: LoadMeter = LoadMeter.new()


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
	_loader.resolve_lots = true
	_loader.world_seed = session.world_seed
	var dir: String = MAIN_WORLD_DIR
	if session.is_random_world():
		# A random world (ADR-0031): generated (or read from its cache) on the same worker thread.
		var gen: Dictionary = session.world_gen.duplicate(true)
		var saved_id: String = String(session.world_id)
		_load_task = WorkerThreadPool.add_task(func() -> void: _loader.load_random_world(gen, saved_id), true, "world load")
		return
	_load_task = WorkerThreadPool.add_task(func() -> void: _loader.load_world(dir), true, "world load")


func _exit_tree() -> void:
	if _load_task >= 0:
		WorkerThreadPool.wait_for_task_completion(_load_task)
		_load_task = -1
	if Game.world == self:
		Game.world = null


func _process(_delta: float) -> void:
	if not is_ready or _load_meter.trailing():
		_load_meter.frame(ui.loading_text() if ui != null else "")
	if _load_task >= 0:
		var st: Array = _loader.status()
		ui.show_loading(str(st[0]), float(st[1]) * WORKER_SHARE)
		if WorkerThreadPool.is_task_completed(_load_task):
			WorkerThreadPool.wait_for_task_completion(_load_task)
			_load_task = -1
			if _loader.error != "":
				ui.show_loading("Failed: %s" % _loader.error, 1.0)
				return
			_on_world_loaded()
		return
	if _boot_i >= 0:
		_run_boot_steps()
		return
	if not is_ready and player != null:
		ui.show_loading("Finding your feet…", 0.95)
		if terrain.is_ready_around(player.global_position, 1):
			_spawn_settle += 1
			if _spawn_settle > 3:
				_finish_spawn()


## True while the main-thread half of the load runs (modules may queue work with boot_steps()).
func is_booting() -> bool:
	return _boot_i >= 0


## Runs boot steps until this frame's budget is spent (always at least one, so a step that alone
## overruns still progresses), then shows the next one's label.
func _run_boot_steps() -> void:
	var t0: int = Time.get_ticks_usec()
	while _boot_i < _boot.size():
		var step: Array = _boot[_boot_i]
		var s0: int = Time.get_ticks_usec()
		# A step that returns false is waiting on a worker thread: it runs again next frame.
		var done: Variant = (step[1] as Callable).call()
		_load_meter.step(str(step[2]), Time.get_ticks_usec() - s0)
		_hold_processing()
		if done is bool and not done:
			break
		_boot_i += 1
		if float(Time.get_ticks_usec() - t0) / 1000.0 >= BOOT_BUDGET_MS:
			break
	if _boot_i >= _boot.size():
		_boot_i = -1
		_boot.clear()
		_release_processing()
		return
	var p: float = WORKER_SHARE + (0.95 - WORKER_SHARE) * float(_boot_i) / float(_boot.size())
	ui.show_loading(str(_boot[_boot_i][0]), p)


## The worker thread is done: queue the scene-tree half of the load as boot steps (see _boot).
func _on_world_loaded() -> void:
	world_def = _loader.world
	poi_lots = _loader.lots
	if _loader.world_id != "":
		session.world_id = StringName(_loader.world_id)
	_boot = [
		["Laying the ground…", _boot_terrain, "terrain"],
		["Reading the old survey…", func() -> void: terrain.load_from(session.world), "terrain edits"],
		["Hanging the sky…", _boot_environment, "environment"],
		["Winding the clocks…", _boot_clock, "clock"],
	]
	for m: Array in MODULES:
		_boot.append([str(m[2]), _spawn_module.bind(m[0], m[1]), str(m[0])])
	_boot.append(["Waking up…", _spawn_player, "player"])
	_boot.append(["Waking up…", _boot_hooks, "hooks"])
	_boot_i = 0
	# Show the first step's label for a frame before running it: the frame it runs in is then
	# measured (and reported by LoadMeter) under its own name, not the worker's last stage.
	ui.show_loading(str(_boot[0][0]), WORKER_SHARE)


## Systems added by a boot step don't tick until the whole world exists: before the split they
## were all created in one frame, and their _process code may assume the player and its
## neighbours are there. Their previous process modes are restored when the boot ends.
func _hold_processing() -> void:
	for c: Node in get_children():
		if c != ui and not _held.has(c):
			_held[c] = c.process_mode
			c.process_mode = Node.PROCESS_MODE_DISABLED


func _release_processing() -> void:
	for c: Node in _held:
		if is_instance_valid(c):
			c.process_mode = _held[c]
	_held.clear()


func _boot_terrain() -> void:
	stimuli = Stimuli.new()
	stimuli.name = "Stimuli"
	stimuli.heat = session.heat
	add_child(stimuli)
	terrain = TerrainManager.new()
	terrain.name = "Terrain"
	terrain.defer_far_tiles = true
	terrain.prebuilt_bloom = _loader.bloom_field
	add_child(terrain)
	terrain.setup(world_def, _loader.detailed, _loader.coarse)
	_insert_boot_steps(terrain.boot_steps())


func _boot_environment() -> void:
	env = EnvironmentController.new()
	env.name = "Environment"
	env.clock = session.clock
	env.weather = session.weather
	add_child(env)


func _boot_clock() -> void:
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


func _boot_hooks() -> void:
	Events.game_saving.connect(_on_game_saving)
	if DebugTools.enabled():
		var dbg := DebugOverlay.new()
		dbg.name = "Debug"
		add_child(dbg)
		dbg.setup(self)


## Optional modules: instantiated if their scripts exist (lets systems land incrementally), one
## boot step each: [property, script, loading-screen label].
const MODULES: Array = [
	["water", "res://src/world/water/water_system.gd", "Filling the rivers…"],
	["bridges", "res://src/world/bridges.gd", "Filling the rivers…"],
	["road_markings", "res://src/world/road_markings.gd", "Painting the roads…"],
	["vegetation", "res://src/world/vegetation/vegetation_manager.gd", "Growing the forest…"],
	["loose", "res://src/world/loose_items.gd", "Scattering what was dropped…"],
	["building", "res://src/building/building_manager.gd", "Raising what you built…"],
	["pois", "res://src/poi/poi_manager.gd", "Raising the town…"],
	["ai", "res://src/ai/ai_director.gd", "Stirring the Hollowed…"],
	["ambience", "res://src/audio/ambience_director.gd", "Listening…"],
	["supply_drops", "res://src/world/supply_drops.gd", "Listening…"],
	["directives", "res://src/progression/directive_tracker.gd", "Listening…"],
	["wildlife", "res://src/wildlife/wildlife_manager.gd", "Waking the woods…"],
]


func _spawn_module(prop: String, script: String) -> void:
	if not ResourceLoader.exists(script):
		return
	var node: Node = (load(script) as GDScript).new()
	node.name = prop.capitalize()
	set(prop, node)
	add_child(node)
	if node.has_method(&"setup_world"):
		node.call(&"setup_world", self)
	# A module with more main-thread work than one frame should take queues it as further steps,
	# run right after its own (before the modules that follow it, which may expect the work done).
	if node.has_method(&"boot_steps"):
		_insert_boot_steps(node.call(&"boot_steps"))


## Queues steps to run right after the current one (only called from a boot step).
func _insert_boot_steps(more: Array) -> void:
	for i: int in more.size():
		_boot.insert(_boot_i + 1 + i, more[i])


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
	# Bound to the id, not the state: a lambda capturing `p` would form a reference cycle
	# (state -> progression -> connection -> lambda -> state) and leak the whole player.
	p.progression.leveled_up.connect(_on_player_leveled.bind(p.id))
	terrain.focus = player
	terrain.update_streaming(player.global_position, true)
	if stimuli != null:
		stimuli.recenter(player.global_position)


func _on_player_leveled(level: int, player_id: StringName) -> void:
	Events.player_leveled.emit(player_id, level)


func _find_spawn(id: String) -> Dictionary:
	for rid: String in _loader.detailed:
		var rt: RegionTerrain = _loader.detailed[rid]
		if rt.spawns.has(id):
			var s: Dictionary = rt.spawns[id]
			var a: Array = s["pos"]
			return {"pos": Vector3(float(a[0]), float(a[1]), float(a[2])), "yaw": float(s.get("yaw", 0.0)), "props": s.get("props", [])}
	return {"pos": Vector3(0, terrain.height_at(0, 0), 0), "yaw": 0.0}


## Set dressing named by the drop-site spawn feature (the Remand supply canister). It is pure
## data, rebuilt on every load rather than saved. A prop id resolves through its PropDef when one
## exists, otherwise to the generated item model `items/<id>`.
func _place_spawn_props() -> void:
	var spawn: Dictionary = _find_spawn("drop_site")
	var base: Vector3 = spawn.get("pos", Vector3.ZERO)
	for v: Variant in spawn.get("props", []):
		var d: Dictionary = v
		var id := StringName(str(d.get("prop", "")))
		var model: String = "items/%s" % id
		if Content.has_def(&"prop", id):
			model = (Content.get_def(&"prop", id) as PropDef).model_for("worn")
		var off: Array = d.get("offset", [0.0, 0.0, 0.0])
		var at := Vector3(base.x + float(off[0]), 0.0, base.z + float(off[2]))
		at.y = terrain.height_at(at.x, at.z) + float(off[1])
		var body := StaticBody3D.new()
		body.name = "SpawnProp_%s" % id
		add_child(body)
		body.global_transform = Transform3D(Basis(Vector3.UP, deg_to_rad(float(d.get("rot", 0.0)))), at)
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(model, "box")
		body.add_child(mi)
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		var aabb: AABB = mi.mesh.get_aabb()
		box.size = aabb.size
		shape.shape = box
		shape.position = aabb.get_center()
		body.add_child(shape)


func _give_start_kit(p: PlayerState) -> void:
	var kit: Dictionary = Content.config(&"player").get("start_kit", {})
	for k: Variant in kit.keys():
		p.inventory.add_item(StringName(str(k)), int(kit[k]))
	p.toolbelt[0] = &"lighter"


func _finish_spawn() -> void:
	# Drop the player onto the ground (terrain collision now exists). A save made in a POI cellar
	# keeps the player on the cellar floor: height_at() is the surface above it (TD-026).
	var pos: Vector3 = player.global_position
	var ground: float = terrain.ground_below(pos)
	if pos.y < ground + 0.2 or pos.y > ground + 30.0:
		player.global_position = Vector3(pos.x, ground + 0.4, pos.z)
	_place_spawn_props()
	_load_meter.spawned()
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
	# Pause is handled by GameUI, which keeps receiving input while the tree is paused.
	if event.is_action_pressed(&"quicksave"):
		if not sleeping:
			Game.save_game()
	elif event.is_action_pressed(&"quickload"):
		if SaveSystem.slot_exists(Game.current_slot) and player != null and player.state.stats.alive:
			Game.load_game(Game.current_slot)
	elif event.is_action_pressed(&"screenshot"):
		var path: String = "user://screenshot_%d.png" % Time.get_unix_time_from_system()
		get_viewport().get_texture().get_image().save_png(path)
		Events.player_status_message.emit("Screenshot saved.", &"info")


func player_node(_player_id: StringName) -> Player:
	return player


func height_at(x: float, z: float) -> float:
	return terrain.height_at(x, z) if terrain != null else 0.0


## The ground under a point: a POI cellar's floor when the point is down in one, else the terrain
## height (TerrainManager.ground_below). For fell-through-the-world checks and for settling
## things where they are; height_at() stays the surface above a cellar.
func ground_below(pos: Vector3) -> float:
	return terrain.ground_below(pos) if terrain != null else 0.0


# --- Survival ----------------------------------------------------------------------------------

func _on_game_minutes(minutes: float) -> void:
	if stimuli != null:
		stimuli.apply_weather(session.weather.params())
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
	if Game.autosave():
		Events.player_status_message.emit("Rested. Progress saved.", &"info")


func _on_player_died(cause: String) -> void:
	var p: PlayerState = player.state
	p.deaths += 1
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var penalty: String = session.rules.choice("death_penalty")
	var note: String = _apply_death_penalty(p, penalty)
	if penalty == "permadeath":
		# One life: the run is over and its save goes with it.
		SaveSystem.delete_slot(Game.current_slot)
		if ui.has_method(&"show_death"):
			ui.call(&"show_death", cause, note, true)
		return
	if ui.has_method(&"show_death"):
		ui.call(&"show_death", cause, note, false)
	else:
		get_tree().create_timer(4.0).timeout.connect(respawn)


## World setting death_penalty. Returns the line shown on the death screen.
func _apply_death_penalty(p: PlayerState, penalty: String) -> String:
	match penalty:
		"none":
			return "You keep everything you carried."
		"xp_loss":
			p.progression.xp = int(p.progression.xp * 0.5)
			return "Half your progress toward the next level is lost."
		"permadeath":
			return "Your run is over."
	# drop_pack keeps what is on the toolbelt; drop_all leaves everything where you fell.
	var keep: Dictionary = {}
	if penalty == "drop_pack":
		for id: StringName in p.toolbelt:
			if id != &"":
				keep[id] = true
	var pack: Array = []
	for st: ItemStack in p.inventory.stacks:
		if st.def() != null and not st.def().has_tag("no_drop") and not keep.has(st.item_id):
			pack.append(st)
	for st: ItemStack in pack:
		p.inventory.take_from(st, st.count)
		ItemDrop.spawn(loose if loose != null else self, st, player.global_position + Vector3(randf_range(-0.6, 0.6), 0.8, randf_range(-0.6, 0.6)))
	return "Your pack lies where you fell." if penalty == "drop_pack" else "Everything you carried lies where you fell."


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
