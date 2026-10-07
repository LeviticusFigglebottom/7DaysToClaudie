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
## Waystation trading (ADR-0039): trader posts, their shops, contracts and safe zones.
var traders: Node = null
var ashen: Node = null
var farming: Node = null
## Forest encounters (ADR-0054): campsites, wrecks and caches scattered between the towns.
var encounters: Node = null
## Ezra Vane, the companion (ADR-0058).
var companion: Node = null
var is_ready: bool = false
## True when this random world streams its regions (ADR-0038): only the first area is composed at
## 1 m at load, the RegionStreamer brings in the rest, and buildings come by distance. The default
## for random worlds (TD-137: without it every building of every town is built at load).
var streaming: bool = false


## Whether a random world streams. On by default; a tool turns it off with the new-game option
## "stream": false (`--no-stream` in smoke and tour) or HOLLOWMERE_STREAM=0, which also wins for
## loads (a load's options carry no "stream"). The main map never streams.
static func wants_streaming() -> bool:
	var env: String = OS.get_environment("HOLLOWMERE_STREAM")
	if env == "0" or env == "1":
		return env == "1"
	return bool(Game.pending_options.get("stream", true))


## Framework lots resolved by the world loader (WorldLoader.lots), read by the POI manager.
var poi_lots: Dictionary = {}
## Every building of the world as data (WorldLoader.registry, RWG v2 Phase 3).
var poi_registry: PoiRegistry = null
## Where the player will stand when the boot ends (the warm-up camera's spot): a streamed world
## builds the buildings around it during the boot.
var boot_focus := Vector3.ZERO
var sleeping: bool = false

var _loader: WorldLoader
var _load_task: int = -1
var _spawn_settle: int = 0
## The main-thread half of the load (ADR-0036): [label, Callable, name] steps, run a few a frame
## within BOOT_BUDGET_MS so the window keeps answering the OS (one long frame here made Windows
## flag the game as not responding).
const BOOT_BUDGET_MS: float = 40.0
## Share of the loading bar the worker thread's half fills; the boot steps fill the rest to 0.95.
const WORKER_SHARE: float = 0.7
## The boot's steps (StepRunner); null when not booting.
var _boot: StepRunner = null
var _held: Dictionary = {}
var _load_meter: LoadMeter = LoadMeter.new()


func _ready() -> void:
	Game.world = self
	# Process after the world's systems: a boot step that lets a system tick (_boot_release) then
	# measures exactly that system's first frame (LoadMeter), not the next one's too.
	process_priority = 1000
	session = Game.session
	if session == null:
		session = Game.new_session({"game_mode": "survival"})
	ui = GameUI.new()
	ui.name = "UI"
	add_child(ui)
	ui.show_loading("Entering the Cordon…", 0.0)
	# The modules' scripts compile on loader threads while the world loads: compiling one (and
	# the classes it uses) on the main thread when its boot step comes took 120-170 ms each for
	# PoiManager, WildlifeManager and TraderManager on a first load (TD-197).
	for m: Array in MODULES:
		if ResourceLoader.exists(str(m[1])):
			ResourceLoader.load_threaded_request(str(m[1]))
	_loader = WorldLoader.new()
	_loader.resolve_lots = true
	_loader.world_seed = session.world_seed
	var dir: String = MAIN_WORLD_DIR
	if session.is_random_world():
		# A random world (ADR-0031): generated (or read from its cache) on the same worker thread.
		var gen: Dictionary = session.world_gen.duplicate(true)
		var saved_id: String = String(session.world_id)
		streaming = wants_streaming()
		_loader.stream = streaming
		_loader.warm_models = DisplayServer.get_name() != "headless"
		Log.info("world", "random world %s: %s" % [saved_id if saved_id != "" else "(new)", "streamed (ADR-0038)" if streaming else "built whole (streaming off)"])
		if streaming and not bool(Game.pending_options.get("is_new_game", false)):
			_loader.spawn_hint = session.local_player().position
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
	_load_step()
	# The sky's light for the Hollowed's eyes (Stimuli.detection_range scales sight by it). It was
	# never fed: perception saw every night at full daylight with the night sight range.
	if is_ready and env != null and Stimuli.current != null:
		Stimuli.current.ambient_light = env.ambient_light_level()
	# Sampled after this frame's steps: the label shown now names the step the next frame runs,
	# and the meter attributes the coming frame to it (GameWorld processes last, see _ready).
	if not is_ready or _load_meter.trailing():
		_load_meter.frame(ui.loading_text() if ui != null and not is_ready else "")


func _load_step() -> void:
	if _load_task >= 0:
		var st: Array = _loader.status()
		ui.show_loading(str(st[0]), float(st[1]) * WORKER_SHARE, _loading_map_texture(), _loader.marks())
		if WorkerThreadPool.is_task_completed(_load_task):
			WorkerThreadPool.wait_for_task_completion(_load_task)
			_load_task = -1
			if _loader.error != "":
				ui.show_loading("Failed: %s" % _loader.error, 1.0)
				return
			_on_world_loaded()
		return
	if _boot != null:
		_run_boot_steps()
		return
	if not _awaiting.is_empty():
		_poll_await()
		return
	if not is_ready and player != null:
		ui.show_loading("Finding your feet…", 0.95)
		if terrain.is_ready_around(player.global_position, 1):
			_spawn_settle += 1
			if _spawn_settle > 3:
				_finish_spawn()


## True while the main-thread half of the load runs (modules may queue work with boot_steps()).
func is_booting() -> bool:
	return _boot != null


## The random world's map for the loading screen, read once its file exists (null otherwise).
var _map_tex: Texture2D = null
func _loading_map_texture() -> Texture2D:
	var path: String = _loader.map_file() if _map_tex == null else ""
	if path != "" and FileAccess.file_exists(path):
		var img := Image.load_from_file(ProjectSettings.globalize_path(path))
		if img != null and not img.is_empty():
			_map_tex = ImageTexture.create_from_image(img)
	return _map_tex


## Runs boot steps within the frame's budget, then shows the next one's label.
func _run_boot_steps() -> void:
	_turn_warm_camera()
	_boot.run_frame()
	if _boot.is_idle():
		_boot = null
		_release_processing()
		return
	ui.show_loading(_boot.current_label(), WORKER_SHARE + (0.95 - WORKER_SHARE) * _boot.progress())


func _on_boot_step(step_name: String, usec: int, _finished: bool) -> void:
	_load_meter.step(step_name, usec)
	_hold_processing()


## The worker thread is done: queue the scene-tree half of the load as boot steps (see _boot).
func _on_world_loaded() -> void:
	world_def = _loader.world
	poi_lots = _loader.lots
	poi_registry = _loader.registry
	if _loader.world_id != "":
		session.world_id = StringName(_loader.world_id)
	# Before the vegetation reads its felled trees: records a newer composer re-scattered (TD-182).
	SaveSystem.fix_composer_changes(session, world_def, TerrainComposer.VERSION)
	_boot = StepRunner.new()
	_boot.budget_ms = BOOT_BUDGET_MS
	_boot.step_ran.connect(_on_boot_step)
	_boot.add_all([
		["Laying the ground…", _boot_terrain, "terrain"],
		["Reading the old survey…", func() -> void: terrain.load_from(session.world), "terrain edits"],
		["Hanging the sky…", _boot_environment, "environment"],
		["Winding the clocks…", _boot_clock, "clock"],
	])
	for m: Array in MODULES:
		_boot.add([str(m[2]), _spawn_module.bind(m[0], m[1]), str(m[0])])
	_boot.add(["Waking up…", _spawn_player, "player"])
	_boot.add(["Waking up…", _boot_hooks, "hooks"])
	_boot.add(["Waking up…", _boot_release, "release"])
	# Show the first step's label for a frame before running it: the frame it runs in is then
	# measured (and reported by LoadMeter) under its own name, not the worker's last stage.
	ui.show_loading(_boot.current_label(), WORKER_SHARE)


## Systems added by a boot step don't tick until the whole world exists: before the split they
## were all created in one frame, and their _process code may assume the player and its
## neighbours are there. Their previous process modes are restored when the boot ends.
func _hold_processing() -> void:
	for c: Node in get_children():
		# The warm-up camera is freed when the player arrives: never held, nothing to release.
		if c != ui and c != _warm_camera and not _held.has(c):
			_held[c] = c.process_mode
			c.process_mode = Node.PROCESS_MODE_DISABLED


func _release_processing() -> void:
	for c: Node in _held:
		if is_instance_valid(c) and int(_held[c]) >= 0:
			c.process_mode = _held[c]
	_held.clear()


## The last boot steps: one per held system, each letting it tick and then giving it a frame of
## its own. All of them starting in one frame cost ~0.5 s (their first _process: streaming,
## scatter, sleepers); one at a time spreads that out, and LoadMeter names the slow one.
func _boot_release() -> void:
	var steps: Array = []
	for c: Node in _held:
		var node: Node = c
		var ticked: Array = [false]
		# First call: let it tick and end the frame; the next frame is its first. Second call (the
		# frame after, once it has ticked): done.
		steps.append(["Waking up… (%s)" % node.name, func() -> bool:
			if ticked[0]:
				return true
			ticked[0] = true
			if is_instance_valid(node) and int(_held.get(node, -1)) >= 0:
				node.process_mode = _held[node]
				# Kept, marked released, so _hold_processing doesn't hold it again.
				_held[node] = -1
			return false, "release %s" % node.name])
	_insert_boot_steps(steps)


func _boot_terrain() -> void:
	stimuli = Stimuli.new()
	stimuli.name = "Stimuli"
	stimuli.heat = session.heat
	add_child(stimuli)
	terrain = TerrainManager.new()
	terrain.name = "Terrain"
	terrain.defer_far_tiles = true
	terrain.prebuilt_bloom = _loader.bloom_tiles
	# Buildings come by distance (ADR-0038 §8): a cellar is cut once its building stands.
	terrain.gate_holes = streaming and _loader.registry != null
	terrain.remesh_far_tiles = streaming
	add_child(terrain)
	terrain.setup(world_def, _loader.detailed.duplicate(), _loader.coarse)
	# The terrain owns the regions now (they detach in a streamed world: nothing else may hold them).
	_loader.detailed = {}
	_insert_boot_steps(terrain.boot_steps())
	if streaming:
		terrain.start_streaming(Content.config(&"streaming"))
	_add_warm_camera()


# --- Pipeline warm-up (TD-003) ----------------------------------------------------------------

## A camera at the spawn while the world boots, so the renderer draws it behind the loading
## screen as each system adds its meshes. Without one nothing 3D was drawn until the player's
## camera arrived, and that first frame compiled every pipeline the view needed at once: 16.5 s
## (151 surface pipelines) in the owner's Windows build, the "not responding" freeze. Turning a
## fifth of a circle a frame, it shows every direction the player may face within five frames.
var _warm_camera: Camera3D = null
const WARM_TURN: float = TAU / 5.0


func _add_warm_camera() -> void:
	var at: Vector3
	if bool(Game.pending_options.get("is_new_game", false)):
		at = _find_spawn("drop_site").get("pos", Vector3.ZERO)
	else:
		at = session.local_player().position
	boot_focus = at
	_warm_camera = Camera3D.new()
	_warm_camera.name = "WarmCamera"
	_warm_camera.fov = 100.0
	_warm_camera.far = 2000.0
	add_child(_warm_camera)
	_warm_camera.global_position = at + Vector3.UP * 1.7
	_warm_camera.make_current()


func _turn_warm_camera() -> void:
	if _warm_camera != null and is_instance_valid(_warm_camera):
		_warm_camera.rotation = Vector3(-0.15, _warm_camera.rotation.y + WARM_TURN, 0.0)


func _drop_warm_camera() -> void:
	if _warm_camera != null and is_instance_valid(_warm_camera):
		# Out of the tree now, not at the end of the frame: the hold after this step would
		# otherwise catch it as a system and queue a release step for a freed node.
		remove_child(_warm_camera)
		_warm_camera.queue_free()
	_warm_camera = null


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
	["farming", "res://src/building/farm_manager.gd", "Raising what you built…"],
	["base_tech", "res://src/building/base_tech_manager.gd", "Raising what you built…"],
	["pois", "res://src/poi/poi_manager.gd", "Raising the town…"],
	["ai", "res://src/ai/ai_director.gd", "Stirring the Hollowed…"],
	["nests", "res://src/world/bloom/bloom_nests.gd", "Stirring the Hollowed…"],
	["ambience", "res://src/audio/ambience_director.gd", "Listening…"],
	["supply_drops", "res://src/world/supply_drops.gd", "Listening…"],
	["directives", "res://src/progression/directive_tracker.gd", "Listening…"],
	["wildlife", "res://src/wildlife/wildlife_manager.gd", "Waking the woods…"],
	["traders", "res://src/trade/trader_manager.gd", "Manning the Waystation…"],
	["ashen", "res://src/ai/ashen/ashen_director.gd", "Watching the treeline…"],
	["encounters", "res://src/world/encounters/encounters.gd", "Leaving things in the woods…"],
	["companion", "res://src/companion/companion_director.gd", "Watching the treeline…"],
]


func _spawn_module(prop: String, script: String) -> void:
	if not ResourceLoader.exists(script):
		return
	# Requested in _ready (load_threaded_get waits if it is still compiling).
	var requested: bool = ResourceLoader.load_threaded_get_status(script) != ResourceLoader.THREAD_LOAD_INVALID_RESOURCE
	var gds: GDScript = (ResourceLoader.load_threaded_get(script) if requested else load(script)) as GDScript
	var node: Node = gds.new()
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
	_boot.insert_next(more)


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
	_drop_warm_camera()
	player.camera.make_current()
	player.bind_state(p)
	player.input_enabled = false
	# Still until _finish_spawn: the ground's collision arrives while "Finding your feet" waits.
	player.freeze(true)
	player.died.connect(_on_player_died)
	# Bound to the id, not the state: a lambda capturing `p` would form a reference cycle
	# (state -> progression -> connection -> lambda -> state) and leak the whole player.
	p.progression.leveled_up.connect(_on_player_leveled.bind(p.id))
	terrain.focus = player
	# Meshed on worker threads ("Finding your feet" waits for the chunks around the player): the
	# synchronous version meshed all 169 near chunks in this step, ~0.45 s of one frame.
	terrain.update_streaming(player.global_position)
	if stimuli != null:
		stimuli.recenter(player.global_position)


func _on_player_leveled(level: int, player_id: StringName) -> void:
	Events.player_leveled.emit(player_id, level)


## Where a new game starts (the "drop_site" spawn), attached or not: every caller asks here
## (directives, respawn, supply drops) so a streamed world answers the same as a loaded one.
func drop_site() -> Vector3:
	return _find_spawn("drop_site").get("pos", Vector3.ZERO)


func _find_spawn(id: String) -> Dictionary:
	# The terrain's regions, then the coarse ones (their metadata has the spawns too; the player is
	# grounded on the real terrain when placed). Not the loader's: in a streamed world it would
	# keep every first-area region in memory after it detaches.
	var all: Array = terrain.regions.values() + terrain.coarse.values()
	for rt: RegionTerrain in all:
		if rt.spawns.has(id):
			var s: Dictionary = rt.spawns[id]
			var a: Array = s["pos"]
			return {"pos": Vector3(float(a[0]), float(a[1]), float(a[2])), "yaw": float(s.get("yaw", 0.0)), "props": s.get("props", [])}
	return {"pos": Vector3(0, terrain.height_at(0, 0), 0), "yaw": 0.0}


## Set dressing named by the drop-site spawn feature (the Remand supply canister). It is pure
## data, rebuilt on every load rather than saved. A prop id resolves through its PropDef when one
## exists, otherwise to the generated item model `items/<id>`.
## [body, height above the ground] of the drop-site props: a streamed world may place them over
## the region's coarse ground (a load far from the drop site), so they settle again when the
## region's 1 m terrain attaches.
var _spawn_props: Array = []


func _reground_spawn_props(_rid: String) -> void:
	for e: Array in _spawn_props:
		var body: Node3D = e[0]
		if is_instance_valid(body):
			var p: Vector3 = body.global_position
			body.global_position = Vector3(p.x, terrain.height_at(p.x, p.z) + float(e[1]), p.z)


func _place_spawn_props() -> void:
	if streaming and not terrain.region_attached.is_connected(_reground_spawn_props):
		terrain.region_attached.connect(_reground_spawn_props)
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
		_spawn_props.append([body, float(off[1])])
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


## Jolt refuses bodies past physics/jolt_physics_3d/limits/max_bodies, and the player's, added
## last, was among them in a random world built whole (22,995 collision objects against 10,240):
## the player could look but never move, and the arms swung off with its free-fall velocity
## (player report 3). Warn well before the limit so content growth shows up in the logs.
func _check_body_budget() -> void:
	var cap: int = int(ProjectSettings.get_setting("physics/jolt_physics_3d/limits/max_bodies", 10240))
	var n: int = find_children("*", "CollisionObject3D", true, false).size()
	if n > cap * 3 / 4:
		Log.warn("world", "%d collision objects at spawn, %d%% of Jolt's max_bodies (%d)" % [n, n * 100 / cap, cap])


func _finish_spawn() -> void:
	# Drop the player onto the ground (terrain collision now exists). A save made in a POI cellar
	# keeps the player on the cellar floor: height_at() is the surface above it (TD-026).
	var pos: Vector3 = player.global_position
	var ground: float = terrain.ground_below(pos)
	if pos.y < ground + 0.2 or pos.y > ground + 30.0:
		player.global_position = Vector3(pos.x, ground + 0.4, pos.z)
	player.freeze(false)
	_place_spawn_props()
	_check_body_budget()
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
	await_area(pos, func() -> void:
		player.global_position = pos + Vector3.UP * 0.5
		# freeze(false) also clears the fall built up before (velocity and the fall-damage speed).
		player.freeze(false)
		terrain.update_streaming(player.global_position, true)
		player.input_enabled = true
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		Events.player_spawned.emit(p.id))


## Runs `then` once the ground at `pos` exists (ADR-0038): at once in a world that doesn't
## stream; in a streamed one, behind a blocking "Finding your feet…" overlay while the region
## there is composed and attached and its near chunks meshed (a respawn or a teleport far from
## where the player was). The player is frozen meanwhile.
func await_area(pos: Vector3, then: Callable) -> void:
	if terrain.streamer == null or (terrain.streamer.is_area_ready(pos, 64.0) and terrain.is_ready_around(pos, 1)):
		then.call()
		return
	player.input_enabled = false
	# Still while the land forms: no gravity, no fall speed to land on (player report 3).
	player.freeze(true)
	terrain.streamer.request_now(pos)
	_awaiting = {"pos": pos, "then": then}
	ui.show_loading("Finding your feet…", 0.95)


## The area await_area is waiting for ({} = none).
var _awaiting: Dictionary = {}


func _poll_await() -> void:
	var pos: Vector3 = _awaiting["pos"]
	# Keep the player at the spot (nothing to stand on yet) while the land forms.
	player.global_position = Vector3(pos.x, maxf(player.global_position.y, terrain.height_at(pos.x, pos.z) + 2.0), pos.z)
	player.velocity = Vector3.ZERO
	terrain.update_streaming(pos)
	if not terrain.streamer.is_area_ready(pos, 64.0) or not terrain.is_ready_around(pos, 1):
		return
	var then: Callable = _awaiting["then"]
	_awaiting = {}
	terrain.streamer.clear_request()
	ui.hide_loading()
	player.freeze(false)
	then.call()
