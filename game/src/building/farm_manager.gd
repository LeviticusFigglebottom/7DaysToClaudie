class_name FarmManager
extends Node
## Gardens and rain catchers in the world (ADR-0049): runs the farm.* commands, ticks every bed and
## catcher with game time and the weather (Farming), and keeps their pieces' FarmVisuals current.
## The pieces themselves are ordinary structures (BuildingManager builds, saves, damages and
## dismantles them); their farm state is WorldState.farms[piece id], written here as it changes,
## so it saves with the world and needs no save_into.
##
## Commands (ADR-0003; reach-checked against the piece):
##   farm.plant       {player, piece, seed?}  -> {ok, plot, crop}     a seed into the first empty plot
##   farm.water       {player, piece, item?}  -> {ok, water}          a bottle or bucket on the bed
##   farm.harvest     {player, piece}         -> {ok, items, plots}   every ripe plot
##   farm.clear       {player, piece}         -> {ok, cleared}        pull dead plants
##   farm.draw_water  {player, piece}         -> {ok, filled}         fill carried bottles / buckets
##   farm.drink       {player, piece}         -> {ok}                 a mouthful of rain water

const COMMANDS: Array[StringName] = [&"farm.plant", &"farm.water", &"farm.harvest", &"farm.clear", &"farm.draw_water",
	&"farm.drink"]
## Metres beyond the piece's own size a player can work it from.
const REACH: float = 3.5

var world: Node
## The BuildingManager whose pieces carry the farms (tests set it directly).
var building: Node
var _accum: float = 0.0


func setup_world(w: Node) -> void:
	world = w
	building = w.get(&"building")
	for c: StringName in COMMANDS:
		Game.register_command(c, Callable(self, "_cmd_" + String(c).get_slice(".", 1)))
	Events.structure_placed.connect(_on_structure_placed)
	Events.structure_destroyed.connect(_on_structure_destroyed)
	if w.get(&"clock_driver") != null:
		w.clock_driver.game_minutes_passed.connect(advance)
	_prune()


func _exit_tree() -> void:
	if world == null:
		return
	for c: StringName in COMMANDS:
		Game.unregister_command(c)


# --- State ---------------------------------------------------------------------------------------

## The farm state of a piece, made (and stored) the first time it is worked; {} for a piece that is
## no farm.
static func state_of(piece: StructurePiece) -> Dictionary:
	if piece == null or not Farming.is_farm(piece.def) or Game.session == null:
		return {}
	var farms: Dictionary = Game.session.world.farms
	var key: String = String(piece.piece_id)
	var st: Variant = farms.get(key)
	if not (st is Dictionary) or not _fits(st as Dictionary, piece.def):
		farms[key] = Farming.new_state(piece.def)
	return farms[key]


## The state for reading only (prompts, visuals): never writes the world.
static func peek(piece: StructurePiece) -> Dictionary:
	if piece == null or Game.session == null:
		return {}
	var st: Variant = Game.session.world.farms.get(String(piece.piece_id))
	return st if st is Dictionary and _fits(st as Dictionary, piece.def) else Farming.new_state(piece.def)


## A saved state still matches its def (a def changed between versions starts it over).
static func _fits(st: Dictionary, def: StructureDef) -> bool:
	if Farming.plots_of(def) > 0:
		return st.get("kind") == "bed" and (st.get("plots", []) as Array).size() == Farming.plots_of(def)
	return st.get("kind") == "catcher"


func _on_structure_placed(id: StringName, def_id: StringName, _pos: Vector3) -> void:
	var def: StructureDef = Content.structure(def_id)
	if Farming.is_farm(def) and Game.session != null and not Game.session.world.farms.has(String(id)):
		Game.session.world.farms[String(id)] = Farming.new_state(def)


func _on_structure_destroyed(id: StringName, _def_id: StringName, _pos: Vector3) -> void:
	if Game.session != null:
		Game.session.world.farms.erase(String(id))


## Drops farm states whose structure is gone (a save from a world where it burned).
func _prune() -> void:
	if Game.session == null:
		return
	var structures: Dictionary = Game.session.world.structures
	for k: Variant in Game.session.world.farms.keys():
		if not structures.has(k) and (building == null or not (building.get(&"pieces") as Dictionary).has(StringName(str(k)))):
			Game.session.world.farms.erase(k)


# --- Ticking -------------------------------------------------------------------------------------

## Game minutes passed: every tick_minutes, beds grow and dry and catchers fill.
func advance(minutes: float) -> void:
	_accum += minutes
	var step: float = float(Farming.cfg().get("tick_minutes", 10.0))
	if _accum < step:
		return
	var m: float = _accum
	_accum = 0.0
	tick(m)


func tick(minutes: float) -> void:
	if Game.session == null or building == null:
		return
	var pieces: Dictionary = building.get(&"pieces")
	var w: Dictionary = Game.session.weather.params() if Game.session.weather != null else {}
	for k: Variant in Game.session.world.farms.keys():
		var piece: StructurePiece = pieces.get(StringName(str(k)))
		if piece == null or not is_instance_valid(piece):
			continue
		var st: Dictionary = state_of(piece)
		var env: Dictionary = env_at(piece, w)
		var changed: bool
		if st.get("kind") == "bed":
			changed = Farming.tick_bed(st, minutes, env)
		else:
			changed = Farming.tick_catcher(st, minutes, env, Farming.catcher_capacity(piece.def))
		if changed:
			_refresh(piece)


## What the weather does at a piece: the air temperature, and rain and snow unless it has a roof.
func env_at(piece: StructurePiece, w: Dictionary) -> Dictionary:
	var pos: Vector3 = piece.global_position
	var ambient: float = 12.0
	if world != null and world.has_method(&"survival_env"):
		ambient = float((world.call(&"survival_env", pos) as Dictionary).get("ambient_c", 12.0))
	var open_sky: bool = true
	if building != null and building.has_method(&"is_sheltered") and piece.is_inside_tree():
		open_sky = not bool(building.call(&"is_sheltered", pos + Vector3.UP * piece.def.size.y))
	var pois: Node = world.get(&"pois") if world != null else null
	if open_sky and pois != null and pois.has_method(&"is_indoors"):
		open_sky = not bool(pois.call(&"is_indoors", pos + Vector3.UP))
	var rules: GameRules = Game.session.rules if Game.session != null else null
	return {"ambient_c": ambient, "rain": float(w.get("rain", 0.0)) if open_sky else 0.0,
		"snow": float(w.get("snow", 0.0)) if open_sky else 0.0,
		"season": Game.session.clock.season() if Game.session != null else "spring",
		"growth": rules.num("crop_growth") if rules != null and rules.values.has("crop_growth") else 1.0}


func _refresh(piece: StructurePiece) -> void:
	if piece != null and is_instance_valid(piece) and piece.farm_visual != null:
		piece.farm_visual.refresh()


# --- Commands ------------------------------------------------------------------------------------

static func _fail(why: String) -> Dictionary:
	return {"ok": false, "error": why}


func _player(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null


## The farm piece a command names, if the player is alive and close enough to work it.
func _piece(p: PlayerState, args: Dictionary) -> StructurePiece:
	if p == null or not p.stats.alive or building == null:
		return null
	var piece: StructurePiece = (building.get(&"pieces") as Dictionary).get(StringName(str(args.get("piece", ""))))
	if piece == null or not Farming.is_farm(piece.def):
		return null
	var node: Node3D = world.player_node(p.id) if world != null and world.has_method(&"player_node") else null
	if node != null and node.global_position.distance_to(piece.global_position) > REACH + maxf(piece.def.size.x, piece.def.size.z):
		return null
	return piece


## Hands an item to the player, at their feet when it doesn't fit.
func _give(p: PlayerState, item: StringName, n: int, at: Vector3) -> void:
	var left: int = p.inventory.add_item(item, n)
	if left > 0 and world != null:
		ItemDrop.spawn(world, ItemStack.make(item, left), at + Vector3.UP * 0.6)


func _cmd_plant(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return _fail("no garden bed")
	var seed: StringName = StringName(str(args["seed"])) if args.has("seed") else Farming.seed_choice(p)
	var c: CropDef = Farming.crop_for_seed(seed)
	if c == null or not p.inventory.has(seed):
		Events.player_status_message.emit("You have nothing to plant.", &"warning")
		return _fail("no seed")
	var st: Dictionary = state_of(piece)
	var plots: Array = st["plots"]
	var at: int = -1
	for i: int in plots.size():
		if Farming.is_empty_plot(plots[i]):
			at = i
			break
	if at < 0:
		Events.player_status_message.emit("The bed is full.", &"info")
		return _fail("full")
	if Farming.season_mult(c, Game.session.clock.season()) <= 0.0:
		Events.player_status_message.emit("Nothing will grow in the frozen ground until spring.", &"warning")
		return _fail("out of season")
	p.inventory.remove(seed, 1)
	Farming.plant(plots[at], c)
	p.progression.award("plant_crop")
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/foliage_rustle", piece.global_position, {"volume_db": -6.0})
	_refresh(piece)
	return {"ok": true, "plot": at, "crop": String(c.id)}


func _cmd_water(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return _fail("no garden bed")
	var item: StringName = StringName(str(args["item"])) if args.has("item") else Farming.water_choice(p)
	var src: Dictionary = Farming.water_source(item)
	if src.is_empty() or not p.inventory.has(item):
		Events.player_status_message.emit("You need water: a filled bottle or bucket.", &"warning")
		return _fail("no water")
	var st: Dictionary = state_of(piece)
	var cap: float = Farming.soil_capacity()
	if float(st.get("water", 0.0)) >= cap - 0.05:
		Events.player_status_message.emit("The soil is already soaked.", &"info")
		return _fail("soaked")
	p.inventory.remove(item, 1)
	var ret: String = str(src.get("returns", ""))
	if ret != "":
		_give(p, StringName(ret), 1, piece.global_position)
	st["water"] = minf(cap, float(st.get("water", 0.0)) + float(src.get("amount", 0.5)))
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/footstep_water", piece.global_position, {"volume_db": -4.0})
	_refresh(piece)
	return {"ok": true, "water": st["water"]}


func _cmd_harvest(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return _fail("no garden bed")
	var st: Dictionary = state_of(piece)
	var rng: RandomNumberGenerator = Game.session.rng.stream("farm")
	var got: Dictionary = {}
	var n: int = 0
	for plot: Dictionary in st["plots"]:
		if not Farming.is_ripe(plot):
			continue
		var c: CropDef = Farming.crop(plot["crop"])
		var items: Dictionary = {}
		for d: Dictionary in [c.produce, c.seed_return]:
			for k: Variant in d.keys():
				var r: Array = d[k]
				var count: int = rng.randi_range(int(r[0]), int(r[1]))
				if count > 0:
					items[String(k)] = int(items.get(String(k), 0)) + count
		for k: String in items:
			_give(p, StringName(k), int(items[k]), piece.global_position)
			got[k] = int(got.get(k, 0)) + int(items[k])
		if c.regrow_stage >= 0:
			plot["grown"] = Farming.regrow_days(c)
		else:
			plot.clear()
		n += 1
		p.progression.award("harvest_crop")
		Events.crop_harvested.emit(p.id, c.id, items)
	if n == 0:
		Events.player_status_message.emit("Nothing here is ripe yet.", &"info")
		return _fail("nothing ripe")
	var lines: PackedStringArray = []
	for k: String in got:
		var d: ItemDef = Content.item(StringName(k))
		lines.append("%d %s" % [int(got[k]), d.display_name if d != null else k])
	Events.player_status_message.emit("Harvested %s." % ", ".join(lines), &"info")
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/foliage_rustle", piece.global_position, {"volume_db": -3.0})
	_refresh(piece)
	return {"ok": true, "items": got, "plots": n}


func _cmd_clear(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return _fail("no garden bed")
	var n: int = 0
	for plot: Dictionary in state_of(piece)["plots"]:
		if Farming.is_dead(plot):
			plot.clear()
			n += 1
	if n == 0:
		return _fail("nothing dead")
	# What's left of them is still fibre.
	_give(p, &"plant_fiber", n, piece.global_position)
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/foliage_rustle", piece.global_position, {"volume_db": -6.0})
	_refresh(piece)
	return {"ok": true, "cleared": n}


func _cmd_draw_water(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.catcher_capacity(piece.def) <= 0.0:
		return _fail("no rain catcher")
	var st: Dictionary = state_of(piece)
	var conts: Array = Farming.fillable(p)
	if conts.is_empty():
		Events.player_status_message.emit("You need an empty bottle or bucket.", &"warning")
		return _fail("nothing to fill")
	var filled: int = 0
	var full_pack: bool = false
	for e: Array in conts:
		var empty: StringName = e[0]
		var full: StringName = e[1]
		var units: float = float(e[2])
		while p.inventory.has(empty) and float(st["water"]) >= units - 0.001:
			p.inventory.remove(empty, 1)
			if p.inventory.add_item(full, 1) > 0:
				p.inventory.add_item(empty, 1)
				full_pack = true
				break
			st["water"] = maxf(0.0, float(st["water"]) - units)
			filled += 1
	if filled == 0:
		Events.player_status_message.emit("No room to carry it full." if full_pack else "Not enough water in it yet.", &"warning")
		return _fail("no room" if full_pack else "not enough water")
	Events.player_status_message.emit("Filled %d. Rain water is murky: boil it before you drink it." % filled, &"info")
	Events.inventory_changed.emit(p.id)
	Audio.play_3d(&"sfx/footstep_water", piece.global_position, {"volume_db": -4.0})
	_refresh(piece)
	return {"ok": true, "filled": filled}


func _cmd_drink(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var piece: StructurePiece = _piece(p, args)
	if piece == null or Farming.catcher_capacity(piece.def) <= 0.0:
		return _fail("no rain catcher")
	var st: Dictionary = state_of(piece)
	if float(st.get("water", 0.0)) < 1.0:
		Events.player_status_message.emit("It's dry.", &"info")
		return _fail("empty")
	if p.stats.hydration >= 99.0:
		Events.player_status_message.emit("You're not thirsty.", &"info")
		return _fail("not thirsty")
	var fx: Dictionary = ((Farming.cfg().get("catcher", {}) as Dictionary).get("drink", {"hydration": 18.0}) as Dictionary).duplicate()
	fx["health"] = float(fx.get("health", 0.0)) * (1.0 - clampf(p.progression.modifier("food_poison_resist"), 0.0, 0.9))
	var tmp := ItemDef.new()
	tmp.consume = fx
	p.stats.consume(tmp)
	st["water"] = maxf(0.0, float(st["water"]) - 1.0)
	Audio.play_2d(&"sfx/drink_gulp", -4.0, &"SFX")
	_refresh(piece)
	return {"ok": true, "effects": fx}


# --- Raiders (ADR-0048 phase 2, TD-211) -----------------------------------------------------------

## Ashen raiders at a bed (AshenDirector calls it): with `loot`, every ripe plot is taken (cut back
## to regrow, or cleared, as a harvest would); every other living plant loses `trample` health and
## dies at none. Writes WorldState.farms like the commands; returns {looted: {crop id: plots},
## trampled: plants}.
static func raid_bed(piece: StructurePiece, loot: bool, trample: float) -> Dictionary:
	var looted: Dictionary = {}
	var trampled: int = 0
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return {"looted": looted, "trampled": trampled}
	for plot: Dictionary in state_of(piece)["plots"]:
		if Farming.is_empty_plot(plot) or Farming.is_dead(plot):
			continue
		var c: CropDef = Farming.crop(plot["crop"])
		if loot and c != null and Farming.is_ripe(plot):
			looted[String(c.id)] = int(looted.get(String(c.id), 0)) + 1
			if c.regrow_stage >= 0:
				plot["grown"] = Farming.regrow_days(c)
			else:
				plot.clear()
		elif trample > 0.0:
			plot["health"] = maxf(0.0, float(plot.get("health", 1.0)) - trample)
			if float(plot["health"]) <= 0.0:
				plot["dead"] = true
			trampled += 1
	if not looted.is_empty() or trampled > 0:
		if is_instance_valid(piece) and piece.farm_visual != null:
			piece.farm_visual.refresh()
	return {"looted": looted, "trampled": trampled}


# --- Interaction (StructurePiece hands its prompts here) -------------------------------------------

## What pressing interact on a farm piece does now: [command, args, prompt]; command &"" = only a
## status line.
static func action(piece: StructurePiece, player: Player) -> Array:
	var p: PlayerState = player.state
	var args: Dictionary = {"player": String(p.id), "piece": String(piece.piece_id)}
	var st: Dictionary = peek(piece)
	if Farming.plots_of(piece.def) > 0:
		var ripe: PackedStringArray = []
		var dead: int = 0
		var empty: int = 0
		for plot: Dictionary in st["plots"]:
			if Farming.is_ripe(plot):
				var c: CropDef = Farming.crop(plot["crop"])
				if not ripe.has(c.display_name.to_lower()):
					ripe.append(c.display_name.to_lower())
			elif Farming.is_dead(plot):
				dead += 1
			elif Farming.is_empty_plot(plot):
				empty += 1
		if not ripe.is_empty():
			return [&"farm.harvest", args, "Harvest %s" % ", ".join(ripe)]
		if dead > 0:
			return [&"farm.clear", args, "Pull up %d dead plant%s" % [dead, "" if dead == 1 else "s"]]
		var seed: StringName = Farming.seed_choice(p)
		if empty > 0 and seed != &"":
			return [&"farm.plant", args.merged({"seed": String(seed)}), "Plant %s (%d left)" % [Content.item(seed).display_name.to_lower(), p.inventory.count_of(seed)]]
		var water: StringName = Farming.water_choice(p)
		if water != &"" and float(st.get("water", 0.0)) < Farming.soil_capacity() - 0.05:
			return [&"farm.water", args.merged({"item": String(water)}), "Water the bed (%s)" % Content.item(water).display_name.to_lower()]
		return [&"", args, bed_status(st)]
	var units: int = int(float(st.get("water", 0.0)))
	var cap: int = int(Farming.catcher_capacity(piece.def))
	if not Farming.fillable(p).is_empty() and units >= 1:
		return [&"farm.draw_water", args, "Fill bottles and buckets (%d / %d)" % [units, cap]]
	if units >= 1:
		return [&"farm.drink", args, "Drink rain water (%d / %d)" % [units, cap]]
	return [&"", args, "%s (dry: it fills when it rains)" % piece.def.display_name]


static func prompt(piece: StructurePiece, player: Player) -> String:
	return str(action(piece, player)[2])


static func act(piece: StructurePiece, player: Player) -> void:
	var a: Array = action(piece, player)
	if a[0] != &"":
		Game.execute(a[0], a[1])
	else:
		Events.player_status_message.emit(str(a[2]), &"info")


## The second action (hold the cancel key): water a bed when interact would do something else, or
## drink from a catcher when interact fills.
static func alt_action(piece: StructurePiece, player: Player) -> Array:
	var p: PlayerState = player.state
	var args: Dictionary = {"player": String(p.id), "piece": String(piece.piece_id)}
	var main: StringName = action(piece, player)[0]
	var st: Dictionary = peek(piece)
	if Farming.plots_of(piece.def) > 0:
		var water: StringName = Farming.water_choice(p)
		if main != &"farm.water" and water != &"" and float(st.get("water", 0.0)) < Farming.soil_capacity() - 0.05:
			return [&"farm.water", args.merged({"item": String(water)}), "water the bed"]
		return [&"", args, ""]
	if main == &"farm.draw_water":
		return [&"farm.drink", args, "drink from it"]
	return [&"", args, ""]


static func alt_prompt(piece: StructurePiece, player: Player) -> String:
	return str(alt_action(piece, player)[2])


static func alt_act(piece: StructurePiece, player: Player) -> void:
	var a: Array = alt_action(piece, player)
	if a[0] != &"":
		Game.execute(a[0], a[1])


## The bed's status for the line under its prompt (TD-217): while the prompt offers an action
## (harvest, clear, plant, water) the status would be hidden; when the prompt is the status there is
## nothing to add. "" for anything but a bed.
static func status_hint(piece: StructurePiece, player: Player) -> String:
	if piece == null or Farming.plots_of(piece.def) <= 0:
		return ""
	return hint_for(action(piece, player)[0], peek(piece))


## Pure: the status line for a bed in `st` when interact would run `command`.
static func hint_for(command: StringName, st: Dictionary) -> String:
	return bed_status(st) if command != &"" else ""


## "Garden bed · potatoes 40%, carrots wilting · soil dry".
static func bed_status(st: Dictionary) -> String:
	var parts: PackedStringArray = []
	for plot: Dictionary in st.get("plots", []):
		if Farming.is_empty_plot(plot):
			continue
		var c: CropDef = Farming.crop(plot["crop"])
		var nm: String = c.display_name.to_lower() if c != null else str(plot["crop"])
		if Farming.is_wilted(plot):
			parts.append("%s wilting" % nm)
		else:
			parts.append("%s %d%%" % [nm, int(Farming.progress(plot) * 100.0)])
	var w: float = float(st.get("water", 0.0)) / Farming.soil_capacity()
	var soil: String = "soil dry" if w <= 0.01 else ("soil damp" if w < 0.5 else "soil wet")
	if parts.is_empty():
		return "Garden bed (empty: plant seeds here) · %s" % soil
	return "Garden bed · %s · %s" % [", ".join(parts), soil]
