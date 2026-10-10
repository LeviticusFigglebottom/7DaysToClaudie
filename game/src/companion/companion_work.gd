class_name CompanionWork
extends RefCounted
## The companion's errands (ADR-0058 phase 2, Ezra Vane): gather, fetch and store. CompanionMind
## owns one and hands it the frame while the order is one of these and he has nobody to fight;
## `step` returns where he wants to go, and while he works at something (a pickup, a chop) the
## mind leaves the clip to it (`acting`).
##
## * **Gather** (`kind`: wood, stone, fibre; CompanionDef.gather): within gather.radius of `spot`
##   he picks up loose logs and dropped items of the kind, harvests bushes, stones and deadfall
##   that yield it and, for wood, fells small trees (species hp up to max_tree_hp) with his own
##   chop blows on the vegetation's collision (which only stands near the player: TD-304), all into
##   his own pack. When nothing he has room for is left (or the pack is full) he walks back to the
##   player and says so.
## * **Fetch** a target (`resolve`: a loose item or log by entity id, a plant, rock or tree by its
##   vegetation id): he walks there, takes it (a tree: fells it and takes a log), comes back and
##   hands it over, or drops it at the player's feet where it doesn't fit.
## * **Store**: he carries his pack to the nearest storage piece of the player's base and puts
##   what fits into it.
## Everything goes through the same commands as the player (world.pickup_*, container.put with the
## companion as `owner`, VegetationManager.harvest_into, take_damage on the vegetation).

## Seconds between looks round for the next gather target.
const SCAN: float = 0.5
## How near the player he hands over what he fetched (m).
const HAND_OVER: float = 2.6
## A plant he harvests by hand (the interaction ray's harvestables are up to this hp).
const PLANT_HP: float = 40.0
## Where his blows land on a trunk (m above its foot).
const CHOP_HEIGHT: float = 0.9

## The mind that owns this (held weakly: it holds us, and a strong ref both ways was a cycle
## that leaked him, his def and his pack at exit).
var mind: CompanionMind:
	get:
		return _mind_ref.get_ref() as CompanionMind if _mind_ref != null else null
var _mind_ref: WeakRef = null
var enemy: Enemy
var cdef: CompanionDef
## His own pack (CompanionDirector.inventory).
var inventory: Inventory = null
## "gather" | "fetch" | "store" | "" (none).
var task: String = ""
## The gather kind (a key of gather.kinds).
var kind: String = ""
## The gather centre.
var spot := Vector3.INF
## {what: log|item|plant|tree|storage, id, pos, node?, key?, inst?} (`id` alone until resolved).
var target: Dictionary = {}
## seek | go | act | wait | return
var phase: String = ""
## A fetch's haul to hand over: {item id: count}.
var fetched: Dictionary = {}
## A pickup or chop clip is playing: the mind leaves the animation alone.
var acting: bool = false
var _t: float = 0.0
## Going to a target: where he last made headway (2 m on) and the time on the way in all; give_up
## counts from the last headway, so a long way round is walked, a dead end is not (TD-308).
var _headway_at := Vector3.INF
var _go_total: float = 0.0
const HEADWAY: float = 2.0
const GO_MAX: float = 120.0
## A target this far off (m) is walked to on a coarse route (TD-299): past the NavTiles round the
## player he walked straight lines, into lakes and up cliffs. The route is a FlowField over the
## terrain (slope and water costs, as the Hum's) in ROUTE_CELL m cells covering him and the
## target, built once per target; within ROUTE_BEYOND the nav mesh (or the straight line) takes over.
const ROUTE_BEYOND: float = 45.0
const ROUTE_CELL: float = 6.0
const ROUTE_MAX_RADIUS: float = 320.0
var _route: FlowField = null
var _route_goal := Vector3.INF
var _cycle: float = 0.0
var _blow_at: float = -1.0
var _scan_t: float = 0.0
## Targets he gave up on (by id) this errand.
var _skip: Dictionary = {}
## What he says when he is back with the player (a gather's "full" or "done").
var _end_bark: String = ""


func _init(m: CompanionMind) -> void:
	_mind_ref = weakref(m)
	enemy = m.enemy
	cdef = m.cdef


func active() -> bool:
	return task != ""


func returning() -> bool:
	return phase == "return"


func clear() -> void:
	task = ""
	kind = ""
	spot = Vector3.INF
	target = {}
	phase = ""
	fetched = {}
	acting = false
	_skip.clear()
	_end_bark = ""


func start_gather(p_kind: String, at: Vector3) -> void:
	clear()
	task = "gather"
	kind = p_kind
	spot = at
	phase = "seek"


func start_fetch(t: Dictionary) -> void:
	clear()
	task = "fetch"
	target = t
	phase = "go"


func start_store(piece: Node3D) -> void:
	clear()
	task = "store"
	phase = "go"
	if piece != null:
		target = {"what": "storage", "node": piece, "id": String(piece.get(&"piece_id")), "pos": piece.global_position}


## A fight cut in: whatever he was doing with his hands starts over when it is done.
func interrupt() -> void:
	if phase == "act":
		phase = "go"
	acting = false


# --- The frame -------------------------------------------------------------------------------------

## Where he wants to go this frame (and does the work when he is there).
func step(delta: float, p: Player) -> Vector3:
	_t += delta
	match phase:
		"seek":
			return _seek(delta, p)
		"go":
			return _go(p)
		"act":
			_act(p)
			return Vector3.ZERO
		"wait":
			if _t >= CompanionDef.fnum(cdef.gather, "settle", 4.5):
				_after_fell()
			return Vector3.ZERO
		"return":
			return _return(p)
	return Vector3.ZERO


func _seek(delta: float, _p: Player) -> Vector3:
	_scan_t -= delta
	if _scan_t > 0.0:
		return Vector3.ZERO
	_scan_t = SCAN
	if full():
		_head_back("full")
		return Vector3.ZERO
	var t: Dictionary = _gather_target()
	if t.is_empty():
		_head_back("done")
		return Vector3.ZERO
	target = t
	_begin("go")
	return Vector3.ZERO


func _go(p: Player) -> Vector3:
	if not _resolved():
		if _t > CompanionDef.fnum(cdef.gather, "give_up", 25.0) * 0.4:
			_fail()
		return Vector3.ZERO
	if not _still_there():
		# taken by someone else meanwhile
		if task == "gather":
			_begin("seek")
		else:
			_fail()
		return Vector3.ZERO
	var to: Vector3 = _target_pos()
	var d: float = enemy._flat_dist(to)
	if d <= _reach():
		_begin_act()
		return Vector3.ZERO
	_go_total += enemy.get_physics_process_delta_time()
	var here: Vector3 = enemy.global_position
	if _headway_at == Vector3.INF or Vector2(here.x - _headway_at.x, here.z - _headway_at.z).length() > HEADWAY:
		_headway_at = here
		_t = 0.0
	if _t > CompanionDef.fnum(cdef.gather, "give_up", 25.0) or _go_total > GO_MAX:
		_fail()
		return Vector3.ZERO
	return _way(to) * enemy._speed(d > 10.0 and not carrying_logs())


## The way toward `to`: the coarse route while it is far, else the body's own (nav mesh, straight).
func _way(to: Vector3) -> Vector3:
	if enemy._flat_dist(to) <= ROUTE_BEYOND:
		return enemy._move_dir(to)
	if _route == null or Vector2(_route_goal.x - to.x, _route_goal.z - to.z).length() > 3.0:
		_route = route(enemy.global_position, to)
		_route_goal = to
	var dir: Vector3 = _route.direction_at(enemy.global_position) if _route != null else Vector3.ZERO
	return dir if dir != Vector3.ZERO else enemy._move_dir(to)


## A coarse route from `from` to `to` over the world's terrain and water (null without a world).
static func route(from: Vector3, to: Vector3) -> FlowField:
	var w: Node = Game.world
	if w == null or not w.has_method(&"height_at"):
		return null
	var mid: Vector3 = (from + to) * 0.5
	var half: float = Vector2(to.x - from.x, to.z - from.z).length() * 0.5
	var f := FlowField.new()
	f.setup(mid, minf(half + 40.0, ROUTE_MAX_RADIUS), ROUTE_CELL)
	var wsys: Variant = w.get(&"water")
	var water_fn: Callable = Callable(wsys, &"water_level_at") if wsys is Object and (wsys as Object).has_method(&"water_level_at") else Callable()
	f.build_terrain(Callable(w, &"height_at"), water_fn, 40.0)
	var targets: Array[Vector3] = [to]
	f.integrate(targets)
	return f


func _return(p: Player) -> Vector3:
	if p == null:
		_finish(null)
		return Vector3.ZERO
	var d: float = enemy._flat_dist(p.global_position)
	if d <= (HAND_OVER if task == "fetch" else CompanionDef.fnum(cdef.follow, "max", 6.0)):
		_finish(p)
		return Vector3.ZERO
	return _way(p.global_position) * enemy._speed(d > CompanionDef.fnum(cdef.follow, "run_beyond", 9.0) and not carrying_logs())


func _begin(ph: String) -> void:
	phase = ph
	_t = 0.0
	acting = false
	_headway_at = Vector3.INF
	_go_total = 0.0
	_route = null
	_route_goal = Vector3.INF


func _begin_act() -> void:
	_begin("act")
	acting = true
	enemy.velocity = Vector3.ZERO
	enemy._face(_target_pos())
	if str(target.get("what", "")) == "tree":
		# The Faller perk swings faster (ADR-0058 phase 3).
		var sp: float = maxf(0.2, mind.perk("chop_speed", 1.0))
		_cycle = enemy.visual.play_once(&"chop", sp, [&"attack_structure", &"attack_a"] as Array[StringName])
		if enemy.visual.anim == null:
			_cycle /= sp  # (the clipless stand-in's fixed beat)
		_cycle = maxf(_cycle, 0.4 / sp)
	else:
		_cycle = maxf(enemy.visual.play_once(&"pickup", 1.0, [] as Array[StringName]), 0.4)
	_blow_at = _cycle * (0.45 if str(target.get("what", "")) == "tree" else 0.5)


func _act(p: Player) -> void:
	if not _resolved() or not _still_there():
		acting = false
		if task == "gather":
			_begin("seek")
		else:
			_fail()
		return
	enemy._face(_target_pos())
	if _blow_at >= 0.0 and _t >= _blow_at:
		_blow_at = -1.0
		_do(p)
		if phase != "act":
			return
	if _t >= _cycle:
		if str(target.get("what", "")) == "tree":
			_begin_act()  # the next blow
		else:
			_after_act()


## The effect of the act at its moment: a pickup, a harvest, a blow, the put into storage.
func _do(_p: Player) -> void:
	var what: String = str(target.get("what", ""))
	match what:
		"log":
			var lg: Node3D = target["node"]
			var r: Dictionary = Game.execute(&"world.pickup_item", {"owner": String(mind.body_id()), "item": "log", "count": 1})
			if bool(r.get("ok", false)):
				Audio.play_3d(&"sfx/log_pickup", lg.global_position, {"volume_db": -4.0})
				lg.queue_free()
				_got(&"log", 1)
		"item":
			var drop: ItemDrop = target["node"]
			var r2: Dictionary = Game.execute(&"world.pickup_stack", {"owner": String(mind.body_id()), "stack": drop.stack})
			var took: int = int(r2.get("took", 0))
			if took > 0:
				_got(drop.stack.item_id, took)
				Audio.play_3d(&"sfx/pickup_generic", drop.global_position, {"volume_db": -10.0})
				if int(r2.get("left", 0)) <= 0:
					drop.queue_free()
				else:
					drop.stack.count = int(r2["left"])
		"plant":
			var veg: Node = _veg()
			var sp: SpeciesDef = Content.get_def(&"species", (target["inst"] as VegetationScatter.Instance).species) as SpeciesDef
			var before: Dictionary = {}
			for it: Variant in sp.yields.keys():
				before[it] = inventory.count_of(StringName(str(it)))
			veg.call(&"harvest_into", target["key"], target["inst"], {"owner": String(mind.body_id())})
			for it2: Variant in before:
				var n: int = inventory.count_of(StringName(str(it2))) - int(before[it2])
				if n > 0:
					_got(StringName(str(it2)), n)
		"tree":
			_blow()
		"storage":
			_put_away()


func _after_act() -> void:
	acting = false
	match task:
		"gather":
			_begin("seek")
		"fetch":
			_head_back("fetched")
		"store":
			mind.set_order("follow")


## One chop at the trunk: the vegetation's own damage path, through its collision body near the
## player and straight to the instance away from them (TD-304: bodies stand only near the
## player). Felled, he waits for it to land.
func _blow() -> void:
	var veg: Node = _veg()
	if veg == null:
		_felled()
		return
	var body: Node = veg.call(&"body_for", target["key"], target["inst"])
	var inst: VegetationScatter.Instance = target["inst"]
	var info := DamageInfo.make(0.0, &"slash", &"melee", mind.body_id())
	info.collider = body
	info.hit_pos = inst.pos + Vector3.UP * CHOP_HEIGHT
	info.source_pos = enemy.global_position
	var dir: Vector3 = (inst.pos - enemy.global_position) * Vector3(1, 0, 1)
	info.direction = dir.normalized() if dir.length() > 0.05 else Vector3.FORWARD
	info.tool_power = {"chop": CompanionDef.fnum(cdef.gather, "chop", 16.0) * mind.perk("chop_power", 1.0)}
	if body != null:
		veg.call(&"take_damage", info)
	elif veg.has_method(&"damage_instance"):
		veg.call(&"damage_instance", target["key"], inst, info)
	else:
		_felled()
		return
	if bool(veg.call(&"_is_removed", target["key"], inst.index)):
		_felled()


func _felled() -> void:
	target["felled_at"] = (target["inst"] as VegetationScatter.Instance).pos
	_begin("wait")


## The tree is down: gathering, he looks round again (its logs lie there); fetching, he takes the
## nearest of its logs.
func _after_fell() -> void:
	if task == "gather":
		_begin("seek")
		return
	var at: Vector3 = target.get("felled_at", enemy.global_position)
	var best: Node3D = null
	var best_d: float = 12.0
	for n: Node in enemy.get_tree().get_nodes_in_group(&"logs"):
		var l: Node3D = n as Node3D
		if l == null or l.is_queued_for_deletion():
			continue
		var d: float = Vector2(l.global_position.x - at.x, l.global_position.z - at.z).length()
		if d < best_d:
			best = l
			best_d = d
	if best == null:
		_fail()
		return
	target = {"what": "log", "node": best, "id": String(best.get(&"entity_id")), "pos": best.global_position}
	_begin("go")


func _put_away() -> void:
	var piece: Node = target["node"]
	var left: int = 0
	var ids: Array[StringName] = []
	for s: ItemStack in inventory.stacks:
		if not ids.has(s.item_id):
			ids.append(s.item_id)
	for id: StringName in ids:
		var r: Dictionary = Game.execute(&"container.put", {"owner": String(mind.body_id()), "container": piece,
			"item": String(id), "count": inventory.count_of(id)})
		left += int(r.get("left", inventory.count_of(id)))
	Audio.play_3d(&"sfx/pickup_generic", enemy.global_position, {"volume_db": -8.0})
	mind.bark("store_full" if left > 0 else "stored")


## Walks back to the player and says `bark` there (a fetch hands its haul over).
func _head_back(bark: String) -> void:
	_end_bark = bark
	_begin("return")


func _finish(p: Player) -> void:
	if task == "fetch" and p != null:
		var dir: Node = mind._director()
		for it: Variant in fetched.keys():
			var n: int = mini(int(fetched[it]), inventory.count_of(StringName(str(it))))
			for st: ItemStack in inventory.take(StringName(str(it)), n):
				if dir != null:
					dir.call(&"hand_over", st, p)
	if _end_bark != "":
		mind.bark(_end_bark)
	mind.set_order("follow")


## He can't do it: a fetch is called off (he says so and follows, bringing nothing); a gather
## target is skipped.
func _fail() -> void:
	acting = false
	if task == "gather":
		_skip[str(target.get("id", ""))] = true
		target = {}
		_begin("seek")
		return
	mind.bark("cant_reach")
	if task == "fetch" and not fetched.is_empty():
		_head_back("")
		return
	mind.set_order("follow")


func _got(item: StringName, n: int) -> void:
	if task == "fetch":
		fetched[String(item)] = int(fetched.get(String(item), 0)) + n


# --- Targets -----------------------------------------------------------------------------------------

## The nearest thing round the gather spot he has room for: loose logs and items of the kind first,
## then plants and stones, then (wood) small trees he can reach the trunk of.
func _gather_target() -> Dictionary:
	var items: PackedStringArray = cdef.gather_items(kind)
	var r: float = CompanionDef.fnum(cdef.gather, "radius", 30.0)
	var here: Vector3 = enemy.global_position
	var best: Dictionary = {}
	var best_d: float = INF
	for g: StringName in [&"logs", &"item_drops"]:
		for n: Node in enemy.get_tree().get_nodes_in_group(g):
			var b: Node3D = n as Node3D
			if b == null or b.is_queued_for_deletion():
				continue
			var item: StringName = &"log" if g == &"logs" else (b as ItemDrop).stack.item_id
			var id: String = String(b.get(&"entity_id"))
			if not items.has(String(item)) or not room(item) or _skip.has(id) or _flat(b.global_position, spot) > r:
				continue
			var d: float = _flat(here, b.global_position)
			if d < best_d:
				best_d = d
				best = {"what": "log" if g == &"logs" else "item", "node": b, "id": id, "pos": b.global_position}
	var veg: Node = _veg()
	if veg == null:
		return best
	var max_hp: float = CompanionDef.fnum(cdef.gather, "max_tree_hp", 90.0)
	for pair: Array in veg.call(&"instances_near", spot, r):
		var key: Vector2i = pair[0]
		var inst: VegetationScatter.Instance = pair[1]
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		if sp == null or sp.yields.is_empty():
			continue
		var id2: String = String(VegetationScatter.instance_id(key, inst.index))
		if _skip.has(id2):
			continue
		var tree: bool = sp.veg_kind == "tree"
		if tree:
			if not items.has("log") or not room(&"log") or sp.hp > max_hp:
				continue
		elif sp.hp > PLANT_HP or not _yields_room(sp, items):
			continue
		# Loose wood first; a tree costs him a while.
		var d2: float = _flat(here, inst.pos) + (12.0 if tree else 0.0)
		if d2 < best_d:
			best_d = d2
			best = {"what": "tree" if tree else "plant", "key": key, "inst": inst, "id": id2, "pos": inst.pos}
	return best


## Resolves a target arg ({entity: id} | {veg: id}) to {what, id, pos, node | key + inst}; {} when it
## is gone (picked up, harvested, felled, not loaded).
static func resolve(t: Dictionary) -> Dictionary:
	if t.has("entity"):
		var id: String = str(t["entity"])
		var tree: SceneTree = Engine.get_main_loop() as SceneTree
		for g: StringName in [&"logs", &"item_drops"]:
			for n: Node in tree.get_nodes_in_group(g):
				if String(n.get(&"entity_id")) == id and not n.is_queued_for_deletion():
					return {"what": "log" if g == &"logs" else "item", "node": n, "id": id, "pos": (n as Node3D).global_position}
		return {}
	if t.has("veg"):
		var veg: Node = Game.world.get(&"vegetation") if Game.world != null else null
		if veg == null:
			return {}
		var vid: String = str(t["veg"])
		var found: Array = veg.call(&"_find_instance", StringName(vid))
		if found.is_empty() or bool(veg.call(&"_is_removed", found[0], (found[1] as VegetationScatter.Instance).index)):
			return {}
		var inst: VegetationScatter.Instance = found[1]
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		if sp == null or sp.yields.is_empty():
			return {}
		return {"what": "tree" if sp.veg_kind == "tree" else "plant", "key": found[0], "inst": inst, "id": vid, "pos": inst.pos}
	return {}


## The arg that names a resolved target again ({entity} | {veg}).
static func arg_of(t: Dictionary) -> Dictionary:
	match str(t.get("what", "")):
		"log", "item":
			return {"entity": str(t.get("id", ""))}
		"plant", "tree":
			return {"veg": str(t.get("id", ""))}
	return {}


## Whether the target is resolved to something in the world (a loaded game resolves it lazily).
func _resolved() -> bool:
	if target.is_empty():
		if task == "store":
			var piece: Node3D = mind._director().call(&"nearest_storage", enemy.global_position) if mind._director() != null else null
			if piece != null:
				start_store(piece)
				return true
		return false
	if target.has("node") or target.has("inst"):
		return true
	var r: Dictionary = resolve(arg_of(target))
	if r.is_empty():
		return false
	target = r
	return true


func _still_there() -> bool:
	if target.has("node"):
		var n: Variant = target["node"]
		return is_instance_valid(n) and not (n as Node).is_queued_for_deletion()
	if target.has("inst"):
		var veg: Node = _veg()
		var inst: VegetationScatter.Instance = target["inst"]
		return veg != null and not bool(veg.call(&"_is_removed", target["key"], inst.index))
	return false


func _target_pos() -> Vector3:
	var n: Variant = target.get("node", null)
	if n != null and is_instance_valid(n):
		target["pos"] = (n as Node3D).global_position
	return target.get("pos", enemy.global_position)


## How close he stands to work at the target: a log anywhere along its 4 m, a trunk at arm's
## length plus the axe, a crate beside it.
func _reach() -> float:
	var r: float = CompanionDef.fnum(cdef.gather, "reach", 1.3)
	match str(target.get("what", "")):
		"log":
			return LogEntity.LENGTH * 0.5 + 0.3
		"tree":
			var inst: VegetationScatter.Instance = target["inst"]
			var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
			return r + (sp.trunk_radius * inst.scale if sp != null else 0.2)
		"storage":
			var piece: Variant = target.get("node")
			var sd: StructureDef = (piece as Node).get(&"def") as StructureDef if is_instance_valid(piece) else null
			return r + (maxf(sd.size.x, sd.size.z) * 0.5 if sd != null else 0.6)
	return r


func _veg() -> Node:
	return Game.world.get(&"vegetation") if Game.world != null else null


# --- His pack ------------------------------------------------------------------------------------------

func room(item: StringName) -> bool:
	return inventory != null and inventory.capacity_for(ItemStack.make(item, 1)) > 0


## No room for anything the gather kind brings in.
func full() -> bool:
	for it: String in cdef.gather_items(kind):
		if room(StringName(it)):
			return false
	return true


func _yields_room(sp: SpeciesDef, items: PackedStringArray) -> bool:
	for it: Variant in sp.yields.keys():
		if items.has(str(it)) and room(StringName(str(it))):
			return true
	return false


func carrying_logs() -> bool:
	return inventory != null and inventory.count_of(&"log") > 0


static func _flat(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


# --- Save ----------------------------------------------------------------------------------------------

## The errand for WorldState.companion.work ({} for none).
func to_dict() -> Dictionary:
	if task == "":
		return {}
	var d: Dictionary = {"task": task, "phase": "seek" if phase == "act" and task == "gather" else phase}
	if kind != "":
		d["kind"] = kind
	if spot != Vector3.INF:
		d["spot"] = [spot.x, spot.y, spot.z]
	if task == "fetch" and not target.is_empty():
		d["target"] = arg_of(target)
	if not fetched.is_empty():
		d["fetched"] = fetched.duplicate()
	if _end_bark != "":
		d["bark"] = _end_bark
	return d


## Picks a saved errand up again (targets resolve lazily: the world may still be streaming in).
func from_dict(d: Dictionary) -> void:
	clear()
	task = str(d.get("task", ""))
	if not task in ["gather", "fetch", "store"]:
		task = ""
		return
	kind = str(d.get("kind", ""))
	var s: Variant = d.get("spot", [])
	if s is Array and (s as Array).size() >= 3:
		spot = Vector3(float(s[0]), float(s[1]), float(s[2]))
	phase = str(d.get("phase", "seek" if task == "gather" else "go"))
	if phase in ["act", "wait"]:
		phase = "seek" if task == "gather" else "go"
	var t: Dictionary = d.get("target", {}) if d.get("target", {}) is Dictionary else {}
	if not t.is_empty():
		target = {"what": "log" if t.has("entity") else "plant", "id": str(t.get("entity", t.get("veg", "")))}
	fetched = (d.get("fetched", {}) as Dictionary).duplicate() if d.get("fetched", {}) is Dictionary else {}
	_end_bark = str(d.get("bark", ""))
	if task == "gather" and spot == Vector3.INF:
		spot = enemy.global_position
