class_name BaseTechManager
extends Node
## Base traps and electricity in the world (ADR-0052): runs the power.* and trap.* commands, ticks
## the generators (fuel, heat, noise) with game time, solves who has power whenever anything
## changes (BaseTech.solve), draws the wires, and credits trap kills. The pieces themselves are
## ordinary structures (BuildingManager builds, saves, damages and dismantles them); their state is
## WorldState.base_tech, written here and by their BaseTechNodes as it changes, so it saves with
## the world and needs no save_into. A GameWorld module (one line in MODULES).
##
## Commands (ADR-0003; reach-checked against the piece):
##   power.fuel    {player, piece}        -> {ok, fuel}             a gas can into a generator
##   power.toggle  {player, piece}        -> {ok, on}               start / stop, switch on / off
##   power.wire    {player, from, to}     -> {ok, spools, length}   a wire between two power pieces
##   power.unwire  {player, piece, to?}   -> {ok, cut, spools}      cut one wire on a piece: the one to `to`, else its newest
##   power.load    {player, piece}        -> {ok, loaded, ammo}     nails into a sentry
##   trap.rearm    {player, piece}        -> {ok}                   lift a sprung deadfall's log

const COMMANDS: Array[StringName] = [&"power.fuel", &"power.toggle", &"power.wire", &"power.unwire", &"power.load", &"trap.rearm"]
## Metres beyond the piece's own size a player can work it from.
const REACH: float = 3.5
## Damage causes of player-built traps and sentries (DamageInfo.cause): kills with them are credited.
const KILL_CAUSES: Array[StringName] = [&"base_trap", &"sentry"]

## The running manager, for the pieces' nodes (null outside a world).
static var current: BaseTechManager = null

var world: Node
## The BuildingManager whose pieces carry the tech (tests set it directly).
var building: Node
## Derived each solve, never saved: piece id (String) -> true for consumers with power, and each
## running generator's load (0..1).
var powered: Dictionary = {}
var loads: Dictionary = {}
## Derived each solve: piece id (String) -> true for every power piece on a network with a running
## generator (whether or not that piece is switched on or fits in its watts), for the prompts.
var live_grid: Dictionary = {}
var _accum: float = 0.0
var _noise_t: float = 0.0
## A wire being run: player id -> the piece it starts at (presentation; the command validates).
var _wire_from: Dictionary = {}
var _wires: MeshInstance3D = null
## The wire being run, drawn from its start to where the local player aims (TD-246).
var _preview: MeshInstance3D = null
var _preview_mat: StandardMaterial3D = null


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null
	if world == null:
		return
	for c: StringName in COMMANDS:
		Game.unregister_command(c)


func setup_world(w: Node) -> void:
	world = w
	building = w.get(&"building")
	register_commands()
	if w.get(&"clock_driver") != null:
		w.clock_driver.game_minutes_passed.connect(advance)
	_prune()
	refresh_grid()


## Commands and world events (setup_world; tests that run a manager without a world call it too).
func register_commands() -> void:
	for c: StringName in COMMANDS:
		Game.register_command(c, Callable(self, "_cmd_" + String(c).get_slice(".", 1)))
	if not Events.structure_placed.is_connected(_on_structure_placed):
		Events.structure_placed.connect(_on_structure_placed)
		Events.structure_destroyed.connect(_on_structure_destroyed)
		Events.enemy_killed.connect(_on_enemy_killed)


# --- State ---------------------------------------------------------------------------------------

## A piece's state, made (and stored) the first time it is needed; {} for a piece that is no tech.
static func state_of(piece: StructurePiece) -> Dictionary:
	if piece == null or not BaseTech.handles(piece.def) or Game.session == null:
		return {}
	var ws: Dictionary = BaseTech.world_state()
	var bucket: Dictionary = ws["power"] if BaseTech.is_power(piece.def) else ws["traps"]
	var key: String = String(piece.piece_id)
	var st: Variant = bucket.get(key)
	if not (st is Dictionary) or not _fits(st as Dictionary, piece.def):
		bucket[key] = BaseTech.new_state(piece.def)
	return bucket[key]


## The state for reading only (prompts, visuals): never writes the world.
static func peek(piece: StructurePiece) -> Dictionary:
	if piece == null or Game.session == null:
		return BaseTech.new_state(piece.def) if piece != null else {}
	var ws: Dictionary = Game.session.world.base_tech
	var bucket: Variant = ws.get("power" if BaseTech.is_power(piece.def) else "traps")
	var st: Variant = (bucket as Dictionary).get(String(piece.piece_id)) if bucket is Dictionary else null
	return st if st is Dictionary and _fits(st as Dictionary, piece.def) else BaseTech.new_state(piece.def)


## A saved state still has the keys its def needs (a def that changed role starts over).
static func _fits(st: Dictionary, def: StructureDef) -> bool:
	for k: String in BaseTech.new_state(def):
		if not st.has(k):
			return false
	return true


func _pieces() -> Dictionary:
	return building.get(&"pieces") if building != null else {}


func _on_structure_placed(id: StringName, def_id: StringName, _pos: Vector3) -> void:
	var def: StructureDef = Content.structure(def_id)
	if not BaseTech.handles(def) or Game.session == null:
		return
	var ws: Dictionary = BaseTech.world_state()
	var bucket: Dictionary = ws["power"] if BaseTech.is_power(def) else ws["traps"]
	if not bucket.has(String(id)):
		bucket[String(id)] = BaseTech.new_state(def)
	if BaseTech.is_power(def):
		refresh_grid()


func _on_structure_destroyed(id: StringName, def_id: StringName, _pos: Vector3) -> void:
	if Game.session == null:
		return
	var ws: Dictionary = BaseTech.world_state()
	(ws["traps"] as Dictionary).erase(String(id))
	(ws["power"] as Dictionary).erase(String(id))
	# Its wires go with it (the copper is lost in the wreck).
	var wires: Array = ws["wires"]
	for w: Array in BaseTech.wires_of(wires, String(id)):
		wires.erase(w)
	for pid: Variant in _wire_from.keys():
		if _wire_from[pid] == String(id):
			_wire_from.erase(pid)
	if BaseTech.is_power(Content.structure(def_id)):
		refresh_grid.call_deferred()


## A Hollow killed by a player-built trap or sentry: the directive event and the XP.
func _on_enemy_killed(_eid: StringName, enemy_id: StringName, _pos: Vector3, killer: Dictionary) -> void:
	if not KILL_CAUSES.has(StringName(str(killer.get("cause", "")))):
		return
	var piece: StructurePiece = _pieces().get(StringName(str(killer.get("source", ""))))
	if piece == null or not is_instance_valid(piece):
		return
	Events.trap_killed.emit(piece.piece_id, piece.def.id, enemy_id)
	var p: PlayerState = Game.local_player() if Game.session != null else null
	if p != null:
		p.progression.award("trap_kill")


## Drops states and wires whose structure is gone (a save from a world where it burned).
func _prune() -> void:
	if Game.session == null:
		return
	var ws: Dictionary = BaseTech.world_state()
	var structures: Dictionary = Game.session.world.structures
	var live := func(k: Variant) -> bool:
		return structures.has(str(k)) or _pieces().has(StringName(str(k)))
	for bucket: String in ["traps", "power"]:
		for k: Variant in (ws[bucket] as Dictionary).keys():
			if not live.call(k):
				(ws[bucket] as Dictionary).erase(k)
	var wires: Array = ws["wires"]
	for w: Variant in wires.duplicate():
		if not (w is Array) or (w as Array).size() < 2 or not live.call((w as Array)[0]) or not live.call((w as Array)[1]):
			wires.erase(w)


# --- The grid -------------------------------------------------------------------------------------

## Re-solves who has power, updates every powered piece's node and redraws the wires.
func refresh_grid() -> void:
	if Game.session == null or building == null:
		return
	var nodes: Dictionary = {}
	var pieces: Dictionary = _pieces()
	for id: StringName in pieces:
		var piece: StructurePiece = pieces[id]
		if is_instance_valid(piece) and BaseTech.is_power(piece.def):
			nodes[String(id)] = {"def": piece.def, "st": state_of(piece)}
	var res: Dictionary = BaseTech.solve(nodes, BaseTech.world_state()["wires"])
	powered = res["powered"]
	loads = res["load"]
	live_grid = {}
	for net: Array in res["networks"]:
		var runs: bool = false
		for id0: String in net:
			if BaseTech.running(nodes[id0]["def"], nodes[id0]["st"]):
				runs = true
				break
		if runs:
			for id1: String in net:
				live_grid[id1] = true
	for id: String in nodes:
		var piece2: StructurePiece = pieces.get(StringName(id))
		if piece2 != null and piece2.tech != null:
			piece2.tech.refresh()
	_draw_wires()


## Whether a consumer has power now, or a generator runs.
func has_power(piece: StructurePiece) -> bool:
	if piece == null:
		return false
	if BaseTech.power_kind(piece.def) == "generator":
		return BaseTech.running(piece.def, peek(piece))
	return powered.has(String(piece.piece_id))


static func is_powered(piece: StructurePiece) -> bool:
	return current != null and current.has_power(piece)


## Whether the piece is wired (directly or through others) to a running generator.
static func on_live_grid(piece: StructurePiece) -> bool:
	return current != null and piece != null and current.live_grid.has(String(piece.piece_id))


## Where a wire meets a piece.
static func anchor(piece: StructurePiece) -> Vector3:
	var h: float = piece.def.size.y * (0.85 if BaseTech.power_kind(piece.def) == "generator" else 0.7)
	return piece.global_position + Vector3.UP * h


func _draw_wires() -> void:
	if _wires == null:
		_wires = MeshInstance3D.new()
		_wires.name = "Wires"
		_wires.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(_wires)
	var pieces: Dictionary = _pieces()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n: int = 0
	for w: Array in BaseTech.world_state()["wires"]:
		var a: StructurePiece = pieces.get(StringName(str(w[0])))
		var b: StructurePiece = pieces.get(StringName(str(w[1])))
		if a == null or b == null or not a.is_inside_tree() or not b.is_inside_tree():
			continue
		_wire_tube(st, anchor(a), anchor(b))
		n += 1
	if n == 0:
		_wires.mesh = null
		return
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.08, 0.08, 0.07)
	mat.roughness = 0.6
	st.set_material(mat)
	_wires.mesh = st.commit()


# --- The wire being run (TD-246) -----------------------------------------------------------------

## The local player's run: [start piece, where the free end is] or [] when no wire is being run.
func running_wire(player: Player) -> Array:
	if player == null or player.state == null:
		return []
	var from: String = str(_wire_from.get(String(player.state.id), ""))
	var from_piece: StructurePiece = _pieces().get(StringName(from)) if from != "" else null
	if from_piece == null or not is_instance_valid(from_piece) or not from_piece.is_inside_tree():
		return []
	var target: StructurePiece = player.interaction.target as StructurePiece if player.interaction != null else null
	var aim_piece: Variant = anchor(target) if target != null and is_instance_valid(target) and target != from_piece and BaseTech.is_power(target.def) else null
	var hit: Variant = player.interaction.last_hit.get("position") if player.interaction != null else null
	var cam: Camera3D = player.camera
	return [from_piece, run_end(aim_piece, hit, cam.global_position, -cam.global_transform.basis.z)]


## Where the free end of a run hangs: on the power piece aimed at, else where the look ray hits
## (within reach), else in the hand, an arm's length ahead and a little low. Pure.
static func run_end(aim_piece: Variant, hit: Variant, cam_pos: Vector3, cam_fwd: Vector3) -> Vector3:
	if aim_piece is Vector3:
		return aim_piece
	if hit is Vector3:
		return hit
	return cam_pos + cam_fwd.normalized() * 0.9 + Vector3.DOWN * 0.35


## The line under the prompt while running a wire: "Wire 8 m · 1 spool" (or too long). Pure.
static func run_label(length: float, spools: int, max_length: float) -> String:
	if spools <= 0:
		return "Wire %d m · too long (%d m at most)" % [roundi(length), roundi(max_length)]
	return "Wire %d m · %d spool%s" % [roundi(length), spools, "" if spools == 1 else "s"]


## The run's line for `player`, "" when no wire is being run.
static func run_hint(player: Player) -> String:
	if current == null:
		return ""
	var run: Array = current.running_wire(player)
	if run.is_empty():
		return ""
	var length: float = anchor(run[0]).distance_to(run[1])
	return run_label(length, BaseTech.wire_spools(length), float(BaseTech.power_cfg("wire").get("max_length", 14.0)))


func _update_preview() -> void:
	var p: Player = Game.world.get(&"player") as Player if Game.world != null else null
	var run: Array = running_wire(p)
	if run.is_empty():
		if _preview != null:
			_preview.visible = false
		return
	if _preview == null:
		_preview = MeshInstance3D.new()
		_preview.name = "WirePreview"
		_preview.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_preview_mat = StandardMaterial3D.new()
		_preview_mat.roughness = 0.6
		add_child(_preview)
	var a: Vector3 = anchor(run[0])
	var b: Vector3 = run[1]
	# Too long for one run: the wire shows it, rust red, before the prompt says so.
	_preview_mat.albedo_color = Color(0.08, 0.08, 0.07) if BaseTech.wire_spools(a.distance_to(b)) > 0 else Color(0.55, 0.12, 0.08)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_wire_tube(st, a, b)
	st.set_material(_preview_mat)
	_preview.mesh = st.commit()
	_preview.visible = true


## A sagging wire from a to b as a thin square tube.
static func _wire_tube(st: SurfaceTool, a: Vector3, b: Vector3) -> void:
	const SEGS: int = 10
	const R: float = 0.012
	var length: float = a.distance_to(b)
	var sag: float = 0.04 * length
	var pts: Array[Vector3] = []
	for i: int in SEGS + 1:
		var t: float = float(i) / SEGS
		pts.append(a.lerp(b, t) + Vector3.DOWN * sag * 4.0 * t * (1.0 - t))
	for i: int in SEGS:
		var p0: Vector3 = pts[i]
		var p1: Vector3 = pts[i + 1]
		var dir: Vector3 = (p1 - p0).normalized()
		var side: Vector3 = dir.cross(Vector3.UP)
		if side.length() < 0.01:
			side = Vector3.RIGHT
		side = side.normalized() * R
		var up: Vector3 = side.cross(dir).normalized() * R
		var ring: Array[Vector3] = [side, up, -side, -up]
		for k: int in 4:
			var o0: Vector3 = ring[k]
			var o1: Vector3 = ring[(k + 1) % 4]
			var nrm: Vector3 = (o0 + o1).normalized()
			st.set_normal(nrm)
			st.add_vertex(p0 + o0)
			st.add_vertex(p1 + o0)
			st.add_vertex(p1 + o1)
			st.add_vertex(p0 + o0)
			st.add_vertex(p1 + o1)
			st.add_vertex(p0 + o1)


# --- Ticking -------------------------------------------------------------------------------------

## Game minutes passed: every tick_minutes, generators burn fuel and heat the map.
func advance(minutes: float) -> void:
	_accum += minutes
	var step: float = float((BaseTech.cfg().get("power", {}) as Dictionary).get("tick_minutes", 2.0))
	if _accum < step:
		return
	var m: float = _accum
	_accum = 0.0
	tick(m)


func tick(minutes: float) -> void:
	if Game.session == null or building == null:
		return
	var rules: GameRules = Game.session.rules
	var rate: float = rules.num("power_fuel_use") if rules != null and rules.values.has("power_fuel_use") else 1.0
	var pieces: Dictionary = _pieces()
	var dry: bool = false
	for id: StringName in pieces:
		var piece: StructurePiece = pieces[id]
		if not is_instance_valid(piece) or BaseTech.power_kind(piece.def) != "generator":
			continue
		var st: Dictionary = state_of(piece)
		if not BaseTech.running(piece.def, st):
			continue
		var load: float = float(loads.get(String(id), 0.0))
		if Stimuli.current != null and Stimuli.current.heat != null:
			Stimuli.current.heat.add(piece.global_position, BaseTech.heat(minutes, load))
		# Ezra's Lineman perk keeps a generator near him tuned (ADR-0058 phase 3).
		var crew: Node = world.get(&"companion") if world != null else null
		var tuned: float = float(crew.call(&"fuel_factor", piece.global_position)) if crew != null and crew.has_method(&"fuel_factor") else 1.0
		var before: float = float(st.get("fuel", 0.0))
		if BaseTech.burn(st, minutes, load, rate * tuned):
			dry = true
			_fuel_line(piece, "dry_text", "The generator sputters out.")
		elif BaseTech.fuel_low(before, float(st.get("fuel", 0.0))):
			_fuel_line(piece, "low_text", "The generator's running low on fuel.")
	if dry:
		refresh_grid()


## Running generators are heard (Stimuli): the Hollowed come to see what is making the noise.
func _process(delta: float) -> void:
	_update_preview()
	_noise_t += delta
	var g: Dictionary = BaseTech.power_cfg("generator")
	if _noise_t < float(g.get("noise_interval", 3.0)) or Stimuli.current == null or building == null:
		return
	_noise_t = 0.0
	var pieces: Dictionary = _pieces()
	for id: StringName in pieces:
		var piece: StructurePiece = pieces[id]
		if is_instance_valid(piece) and BaseTech.power_kind(piece.def) == "generator" and BaseTech.running(piece.def, peek(piece)):
			Stimuli.current.emit_sound(piece.global_position + Vector3.UP * 0.5, float(g.get("noise", 18.0)), &"generator", id)


## A generator's fuel line (mid-game audit M3: it ran its can dry with no word): queued as a
## warning (StatusFeed), and only within the generator's warn_radius of the player. There is no
## base ownership in the game (every piece is the player's), so "his base" can't decide it: a
## generator across the map that dies is told when he comes back and finds it, not mid-fight
## somewhere else; within the radius he would hear the engine change anyway.
func _fuel_line(piece: StructurePiece, key: String, fallback: String) -> void:
	var g: Dictionary = BaseTech.power_cfg("generator")
	if not _near_player(piece.global_position, float(g.get("warn_radius", 60.0))):
		return
	Events.status_message_queued.emit(str(g.get(key, fallback)), &"warning", StatusFeed.PRIORITY_WARNING)


static func _near_player(pos: Vector3, r: float) -> bool:
	var pl: Node3D = Game.world.get(&"player") if Game.world != null else null
	return pl == null or pl.global_position.distance_to(pos) <= r


# --- Commands ------------------------------------------------------------------------------------

static func _fail(why: String, say: String = "", kind: StringName = &"info") -> Dictionary:
	if say != "":
		Events.player_status_message.emit(say, kind)
	return {"ok": false, "error": why}


func _player(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null


## The tech piece `key` names, if the player is alive and close enough to work it.
func _piece(p: PlayerState, args: Dictionary, key: String = "piece") -> StructurePiece:
	if p == null or not p.stats.alive or building == null:
		return null
	var piece: StructurePiece = _pieces().get(StringName(str(args.get(key, ""))))
	if piece == null or not is_instance_valid(piece) or not BaseTech.handles(piece.def):
		return null
	if not _within_reach(p, piece):
		return null
	return piece


func _within_reach(p: PlayerState, piece: StructurePiece) -> bool:
	var node: Node3D = world.player_node(p.id) if world != null and world.has_method(&"player_node") else null
	return node == null or node.global_position.distance_to(piece.global_position) <= REACH + maxf(piece.def.size.x, piece.def.size.z)


## Hands an item to the player, at their feet when it doesn't fit.
func _give(p: PlayerState, item: StringName, n: int, at: Vector3) -> void:
	var left: int = p.inventory.add_item(item, n)
	if left > 0 and world != null:
		ItemDrop.spawn(world, ItemStack.make(item, left), at + Vector3.UP * 0.6)


func _refresh(piece: StructurePiece) -> void:
	if piece != null and is_instance_valid(piece) and piece.tech != null:
		piece.tech.refresh()


func _cmd_fuel(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or BaseTech.power_kind(piece.def) != "generator":
		return _fail("no generator")
	var item := StringName(str(BaseTech.power_cfg("generator").get("fuel_item", "gas_can")))
	if not p.inventory.has(item):
		return _fail("no fuel", "You need a gas can.", &"warning")
	var st: Dictionary = state_of(piece)
	var tank: float = BaseTech.tank_hours()
	if float(st.get("fuel", 0.0)) > tank - BaseTech.can_hours() * 0.5:
		return _fail("full", "The tank is full.")
	p.inventory.remove(item, 1)
	st["fuel"] = minf(tank, float(st.get("fuel", 0.0)) + BaseTech.can_hours())
	var ret: String = str(BaseTech.power_cfg("generator").get("returns", ""))
	if ret != "":
		_give(p, StringName(ret), 1, piece.global_position)
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/footstep_water", piece.global_position, {"volume_db": -8.0, "pitch": 1.4})
	refresh_grid()
	return {"ok": true, "fuel": st["fuel"]}


func _cmd_toggle(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or not BaseTech.is_power(piece.def):
		return _fail("no power piece")
	var st: Dictionary = state_of(piece)
	var on: bool = not bool(st.get("on", false))
	if on and BaseTech.power_kind(piece.def) == "generator" and float(st.get("fuel", 0.0)) <= 0.0:
		return _fail("no fuel", "The tank is dry: pour in a gas can first.", &"warning")
	st["on"] = on
	Audio.play_3d(&"sfx/power_switch", piece.global_position + Vector3.UP, {"volume_db": -6.0})
	refresh_grid()
	if on and BaseTech.power_kind(piece.def) != "generator" and not has_power(piece):
		if live_grid.has(String(piece.piece_id)):
			Events.player_status_message.emit("Switched on, but the generator can't carry it too: switch something else off.", &"info")
		else:
			Events.player_status_message.emit("Switched on, but there's no power: wire it to a running generator.", &"info")
	return {"ok": true, "on": on}


func _cmd_wire(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null or not p.stats.alive or building == null:
		return _fail("no player")
	var a: StructurePiece = _pieces().get(StringName(str(args.get("from", ""))))
	var b: StructurePiece = _pieces().get(StringName(str(args.get("to", ""))))
	if a == null or b == null or a == b or not BaseTech.is_power(a.def) or not BaseTech.is_power(b.def):
		return _fail("not two power pieces")
	if not _within_reach(p, a) and not _within_reach(p, b):
		return _fail("too far away")
	var wires: Array = BaseTech.world_state()["wires"]
	if BaseTech.has_wire(wires, String(a.piece_id), String(b.piece_id)):
		return _fail("already wired", "Those two are already wired together.")
	var length: float = anchor(a).distance_to(anchor(b))
	var spools: int = BaseTech.wire_spools(length)
	if spools <= 0:
		return _fail("too long", "Too far for one run of wire (%d m at most)." % int(BaseTech.power_cfg("wire").get("max_length", 14.0)), &"warning")
	var item := StringName(str(BaseTech.power_cfg("wire").get("item", "copper_wire")))
	if p.inventory.count_of(item) < spools:
		return _fail("no wire", "That run takes %d wire spool%s." % [spools, "" if spools == 1 else "s"], &"warning")
	p.inventory.remove(item, spools)
	wires.append([String(a.piece_id), String(b.piece_id), spools])
	_wire_from.erase(String(p.id))
	p.progression.award("wire_power")
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/power_switch", b.global_position + Vector3.UP, {"volume_db": -8.0})
	refresh_grid()
	return {"ok": true, "spools": spools, "length": length}


func _cmd_unwire(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or not BaseTech.is_power(piece.def):
		return _fail("no power piece")
	var wires: Array = BaseTech.world_state()["wires"]
	# One wire at a time (TD-246: cutting a piece's wires cut them all, a whole base's grid at once).
	var cut: Array = one_wire(BaseTech.wires_of(wires, String(piece.piece_id)), String(piece.piece_id), str(args.get("to", "")))
	if cut.is_empty():
		return _fail("no wires")
	var spools: int = 0
	for w: Array in cut:
		wires.erase(w)
		spools += int(w[2]) if w.size() > 2 else 1
	_give(p, StringName(str(BaseTech.power_cfg("wire").get("item", "copper_wire"))), spools, piece.global_position)
	Events.inventory_changed.emit(p.id)
	refresh_grid()
	return {"ok": true, "cut": cut.size(), "spools": spools}


func _cmd_load(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or BaseTech.power_kind(piece.def) != "turret":
		return _fail("no sentry")
	var t: Dictionary = BaseTech.power_cfg("turret")
	var item := StringName(str(t.get("ammo_item", "nails")))
	var st: Dictionary = state_of(piece)
	var room: int = int(t.get("magazine", 120)) - int(st.get("ammo", 0))
	var n: int = mini(room, p.inventory.count_of(item))
	if room <= 0:
		return _fail("full", "It's fully loaded.")
	if n <= 0:
		return _fail("no ammo", "It shoots nails: you have none.", &"warning")
	p.inventory.remove(item, n)
	st["ammo"] = int(st.get("ammo", 0)) + n
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/gun_reload", piece.global_position + Vector3.UP, {"volume_db": -6.0})
	_refresh(piece)
	return {"ok": true, "loaded": n, "ammo": st["ammo"]}


func _cmd_rearm(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or BaseTech.trap_kind(piece.def) != "deadfall":
		return _fail("no deadfall")
	var st: Dictionary = state_of(piece)
	if bool(st.get("armed", false)):
		return _fail("armed", "It's already set.")
	st["armed"] = true
	Audio.play_3d(&"sfx/deadfall_rearm", piece.global_position + Vector3.UP, {"volume_db": -4.0})
	_refresh(piece)
	return {"ok": true}


# --- Interaction (StructurePiece hands its prompts here) -------------------------------------------

static func _wire_item() -> StringName:
	return StringName(str(BaseTech.power_cfg("wire").get("item", "copper_wire")))


## What pressing interact does now: [command, args, prompt]; command &"" = only a status line.
static func action(piece: StructurePiece, player: Player) -> Array:
	var p: PlayerState = player.state
	var args: Dictionary = {"player": String(p.id), "piece": String(piece.piece_id)}
	var st: Dictionary = peek(piece)
	var nm: String = piece.def.display_name
	match BaseTech.trap_kind(piece.def):
		"deadfall":
			if bool(st.get("armed", true)):
				return [&"", args, "%s (set: keep out from under it)" % nm]
			return [&"trap.rearm", args, "Lift the deadfall log"]
		"spike_pit":
			var frac: float = piece.hp / maxf(1.0, piece.max_hp())
			var dull: bool = frac < float(BaseTech.trap_cfg("spike_pit").get("dull_below", 0.35))
			return [&"", args, "%s · stakes %d%%%s" % [nm, int(frac * 100.0), " (dull: mend with a hammer)" if dull else ""]]
		"tripwire":
			return [&"", args, "%s (strung)" % nm]
	var on: bool = bool(st.get("on", false))
	var live: bool = is_powered(piece)
	var grid: bool = on_live_grid(piece)
	match BaseTech.power_kind(piece.def):
		"generator":
			var fuel: float = float(st.get("fuel", 0.0))
			var can := StringName(str(BaseTech.power_cfg("generator").get("fuel_item", "gas_can")))
			if fuel <= 0.0:
				if p.inventory.has(can):
					return [&"power.fuel", args, "Fuel the generator (%s)" % Content.item(can).display_name.to_lower()]
				return [&"", args, "Generator (empty: it runs on gas cans)"]
			if not on:
				return [&"power.toggle", args, "Start the generator · fuel %s" % BaseTech.hours_text(fuel)]
			var load: float = float(current.loads.get(String(piece.piece_id), 0.0)) if current != null else 0.0
			return [&"power.toggle", args, "Stop the generator · fuel %s · load %d%%%s" % [BaseTech.hours_text(fuel), int(load * 100.0),
				_tuned_text(piece.global_position)]]
		"turret":
			var t: Dictionary = BaseTech.power_cfg("turret")
			var ammo: int = int(st.get("ammo", 0))
			var mag: int = int(t.get("magazine", 120))
			var item := StringName(str(t.get("ammo_item", "nails")))
			if ammo < mag and p.inventory.has(item):
				return [&"power.load", args, "Load %s (%d / %d)" % [Content.item(item).display_name.to_lower(), ammo, mag]]
			return [&"power.toggle", args, "Switch the sentry %s · %d %s%s" % ["off" if on else "on", ammo, Content.item(item).display_name.to_lower(), _no_power(on, live, grid)]]
	return [&"power.toggle", args, "Switch the %s %s%s" % [nm.to_lower(), "off" if on else "on", _no_power(on, live, grid)]]


## Why a consumer is dark, said with its real switch state (mid-game audit M2: an unpowered light
## that is switched on read "Switch the work light off (no power)", which sounded like the switch
## was inverted). The verb stays what pressing does: a new consumer is switched on, so it lights
## the moment it is wired; switching it off first is how you keep it dark.
## `grid`: wired to a running generator (on_live_grid).
static func _no_power(on: bool, live: bool, grid: bool) -> String:
	if live:
		return ""
	if on:
		return " (it's on, but the generator can't carry it too)" if grid else " (it's on, but there's no power: wire it to a running generator)"
	return "" if grid else " (no power: wire it to a running generator)"


## " · Ezra keeps it tuned" while his Lineman perk cuts this running generator's fuel (TD-310):
## the saving shows where the player reads the fuel.
static func _tuned_text(at: Vector3) -> String:
	var w: Node = current.world if current != null else null
	var crew: Node = w.get(&"companion") if w != null else null
	if crew == null or not crew.has_method(&"fuel_factor") or float(crew.call(&"fuel_factor", at)) >= 1.0:
		return ""
	var cd: Variant = crew.get(&"cdef")
	var nm: String = (cd as ContentDef).display_name.split(" ")[0] if cd is ContentDef and (cd as ContentDef).display_name != "" else "Ezra"
	return " · %s keeps it tuned" % nm


static func prompt(piece: StructurePiece, player: Player) -> String:
	return str(action(piece, player)[2])


static func act(piece: StructurePiece, player: Player) -> void:
	var a: Array = action(piece, player)
	if a[0] != &"":
		Game.execute(a[0], a[1])
	else:
		Events.player_status_message.emit(str(a[2]), &"info")


## The second action (hold the cancel key): with a wire spool, run a wire from this piece or
## connect the one being run; otherwise cut a piece's wires, or top up a running generator.
## [command, args, prompt]; command &"wire_start" / &"wire_cancel" only change who is running a wire.
static func alt_action(piece: StructurePiece, player: Player) -> Array:
	var p: PlayerState = player.state
	var args: Dictionary = {"player": String(p.id), "piece": String(piece.piece_id)}
	if not BaseTech.is_power(piece.def):
		return [&"", args, ""]
	var from: String = str(current._wire_from.get(String(p.id), "")) if current != null else ""
	var from_piece: StructurePiece = current._pieces().get(StringName(from)) if current != null and from != "" else null
	if p.inventory.has(_wire_item()):
		if from_piece == piece:
			return [&"wire_cancel", args, "stop running the wire"]
		if from_piece != null and is_instance_valid(from_piece):
			var length: float = anchor(from_piece).distance_to(anchor(piece))
			var spools: int = BaseTech.wire_spools(length)
			if spools <= 0:
				return [&"", args, "too far from the %s (%d m)" % [from_piece.def.display_name.to_lower(), int(length)]]
			return [&"power.wire", {"player": String(p.id), "from": from, "to": String(piece.piece_id)},
				"connect the wire from the %s (%d m, %d spool%s)" % [from_piece.def.display_name.to_lower(), int(round(length)), spools, "" if spools == 1 else "s"]]
		return [&"wire_start", args, "run a wire from here"]
	var wires: Array = BaseTech.wires_of(Game.session.world.base_tech.get("wires", []), String(piece.piece_id)) if Game.session != null else []
	if BaseTech.power_kind(piece.def) == "generator":
		var can := StringName(str(BaseTech.power_cfg("generator").get("fuel_item", "gas_can")))
		var fuel: float = float(peek(piece).get("fuel", 0.0))
		if fuel > 0.0 and p.inventory.has(can) and fuel <= BaseTech.tank_hours() - BaseTech.can_hours() * 0.5:
			return [&"power.fuel", args, "pour in a gas can"]
	if not wires.is_empty():
		var other: String = wire_other(wires.back(), String(piece.piece_id))
		var other_piece: StructurePiece = current._pieces().get(StringName(other)) if current != null else null
		var nm: String = other_piece.def.display_name.to_lower() if other_piece != null and is_instance_valid(other_piece) else "next piece"
		var more: String = "" if wires.size() == 1 else " (%d wires)" % wires.size()
		return [&"power.unwire", args.merged({"to": other}), "cut the wire to the %s%s" % [nm, more]]
	return [&"", args, ""]


static func alt_prompt(piece: StructurePiece, player: Player) -> String:
	return str(alt_action(piece, player)[2])


## The wire to cut from `piece_wires` (the wires on piece `id`): the one to `to`, else the newest.
## [] or [wire]. Pure.
static func one_wire(piece_wires: Array, id: String, to: String) -> Array:
	if piece_wires.is_empty():
		return []
	if to == "":
		return [piece_wires.back()]
	for w: Array in piece_wires:
		if wire_other(w, id) == to:
			return [w]
	return []


## The piece at the other end of wire `w` from `id`.
static func wire_other(w: Array, id: String) -> String:
	return str(w[1]) if str(w[0]) == id else str(w[0])


static func alt_act(piece: StructurePiece, player: Player) -> void:
	var a: Array = alt_action(piece, player)
	match a[0]:
		&"":
			return
		&"wire_start":
			if current != null:
				current._wire_from[String(player.state.id)] = String(piece.piece_id)
				Events.player_status_message.emit("Running a wire from the %s: hold [X] on the piece to connect." % piece.def.display_name.to_lower(), &"info")
		&"wire_cancel":
			if current != null:
				current._wire_from.erase(String(player.state.id))
		_:
			Game.execute(a[0], a[1])
