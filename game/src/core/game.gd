extends Node
## Session lifecycle, authority and the command bus (autoload `Game`).
##
## Multiplayer-ready seam (ADR-0003): every state-mutating player intent (craft, consume,
## place a structure, take loot, ...) goes through `Game.execute(&"domain.verb", args)`.
## In single-player the local machine is the authority and handlers run immediately; in a
## future co-op build a client forwards the same command to the host over RPC and applies the
## replicated result. Handlers must only depend on (session state + args) — never on UI state.

signal session_changed()
signal command_executed(command: StringName, args: Dictionary, result: Dictionary)

const MAIN_SCENE: String = "res://src/app/main.tscn"
const GAME_WORLD_SCENE: String = "res://src/app/game_world.tscn"

## The active playthrough (null in menus).
var session: GameSession = null
## The in-game world root (GameWorld), registered by itself on ready.
var world: Node = null
## "offline" | "host" | "client" — only "client" lacks authority.
var network_role: StringName = &"offline"
var current_slot: String = "slot1"
## Options for the next world entry (e.g. {"skip_intro": true}); consumed by GameWorld.
var pending_options: Dictionary = {}

var _commands: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func _process(delta: float) -> void:
	if session != null and world != null and not get_tree().paused:
		session.play_seconds += delta


func is_authority() -> bool:
	return network_role != &"client"


func has_session() -> bool:
	return session != null


func local_player() -> PlayerState:
	return session.local_player() if session != null else null


# --- Lifecycle -----------------------------------------------------------------------------

## Creates a fresh session. options: world_mode, seed, game_mode, world_id.
func new_session(options: Dictionary = {}) -> GameSession:
	session = GameSession.create_new(options)
	session_changed.emit()
	return session


func start_new_game(options: Dictionary = {}) -> void:
	new_session(options)
	current_slot = str(options.get("slot", "slot1"))
	pending_options = options.duplicate()
	pending_options["is_new_game"] = true
	_change_scene(GAME_WORLD_SCENE)


func load_game(slot: String) -> bool:
	var loaded: GameSession = SaveSystem.load_session(slot)
	if loaded == null:
		Events.player_status_message.emit("Could not load '%s'." % slot, &"error")
		return false
	session = loaded
	current_slot = slot
	pending_options = {"is_new_game": false}
	session_changed.emit()
	_change_scene(GAME_WORLD_SCENE)
	Events.game_loaded.emit(slot)
	return true


## Saves the active session. Live systems flush their state into the session on game_saving.
func save_game(slot: String = "") -> bool:
	if session == null:
		return false
	var s: String = slot if slot != "" else current_slot
	Events.game_saving.emit(s)
	var err: Error = SaveSystem.save_session(session, s)
	var ok: bool = err == OK
	if ok:
		Log.info(&"save", "saved slot '%s' (day %d)" % [s, session.clock.day()])
	else:
		Log.error(&"save", "saving slot '%s' failed: %s" % [s, error_string(err)])
	Events.game_saved.emit(s, ok)
	return ok


func quit_to_menu() -> void:
	Events.session_ending.emit()
	session = null
	world = null
	session_changed.emit()
	get_tree().paused = false
	_change_scene(MAIN_SCENE)


func _change_scene(path: String) -> void:
	get_tree().paused = false
	var err: Error = get_tree().change_scene_to_file(path)
	if err != OK:
		Log.error(&"game", "failed to change scene to %s: %s" % [path, error_string(err)])


# --- Command bus ---------------------------------------------------------------------------

## Registers a handler: func(args: Dictionary) -> Dictionary (must contain "ok": bool).
func register_command(command: StringName, handler: Callable) -> void:
	if _commands.has(command):
		Log.warn(&"game", "command %s re-registered" % command)
	_commands[command] = handler


func unregister_command(command: StringName) -> void:
	_commands.erase(command)


func has_command(command: StringName) -> bool:
	return _commands.has(command)


## Executes a command as the authority. Returns the handler's result dictionary.
func execute(command: StringName, args: Dictionary = {}) -> Dictionary:
	if not is_authority():
		# Future co-op: rpc_id(1, "_remote_execute", command, args) and await replication.
		return {"ok": false, "error": "not authority"}
	var handler: Callable = _commands.get(command, Callable())
	if not handler.is_valid():
		Log.warn(&"game", "unknown command %s" % command)
		return {"ok": false, "error": "unknown command %s" % command}
	var result: Variant = handler.call(args)
	var out: Dictionary = result if result is Dictionary else {"ok": bool(result)}
	command_executed.emit(command, args, out)
	return out
