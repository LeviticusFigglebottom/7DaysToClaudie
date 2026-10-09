class_name TraderManager
extends Node3D
## Waystation trading (ADR-0039), the live half: raises a TraderPost wherever a region has a
## `trader:<def>` spawn feature, keeps its safe zone (no Hollowed spawn in it, and the guards shoot
## any that walk in), runs its shop and its contracts board through commands, and follows each
## player's contracts in the world: a building cleared and its loot room searched, a Program cache
## placed in a building and carried out, a cache held against waves. What the board and the shop
## offer is deterministic (Contracts); what was bought, sold, taken and done is saved
## (WorldState.traders, PlayerState.contracts).

const COMMANDS: Array[StringName] = [&"trade.buy", &"trade.sell", &"contract.accept", &"contract.turn_in",
	&"contract.abandon", &"contract.start_defend"]
## How close a player has to stand to the counter or the board to trade.
const REACH: float = 6.0
## A fetch cache is set down once its building is built and the player is this close.
const PLACE_RANGE: float = 70.0
## A defence: the cache shows within this range; the player must stay within HOLD_RANGE of it
## (LEAVE_GRACE seconds outside fails the run); waves come from this ring around it.
const CACHE_RANGE: float = 120.0
const HOLD_RANGE: float = 30.0
const LEAVE_GRACE: float = 8.0
const WAVE_RING: Vector2 = Vector2(50.0, 65.0)
const TICK: float = 0.5

var world: Node
## post id -> {id: post id, def: TraderDef, pos: Vector3, yaw: float (degrees), node: TraderPost}
var posts: Dictionary = {}
## contract id -> {node: Node3D (the cache), t: seconds held, next_wave: seconds, wave: n,
##   outside: seconds outside, enemies: [entity ids]}
var _runs: Dictionary = {}
## contract id -> cache node shown for a defence not yet started
var _caches: Dictionary = {}
var _tick: float = 0.0
var screen: Control
## () -> Array: the buildings contracts choose from; PoiManager.all_buildings() when unset (tests
## and QA shots stand in their own).
var buildings_source: Callable = Callable()


func setup_world(w: Node) -> void:
	world = w
	for c: StringName in COMMANDS:
		Game.register_command(c, Callable(self, "_cmd_" + String(c).replace(".", "_")))
	Events.poi_cleared.connect(_on_poi_cleared)
	Events.container_looted.connect(_on_container_looted)
	Events.item_picked_up.connect(_on_item_picked_up)
	Events.player_died.connect(_on_player_died)
	# Posts come and go with their region (RWG v2 streaming, ADR-0038 §7): built for the regions
	# attached now (every region of a world that doesn't stream), then on each attach; freed on
	# detach. Everything authoritative (stock, contracts) lives in the session, so a post rebuilt
	# on re-attach is the same post.
	var terrain: Node = w.get(&"terrain")
	if terrain != null:
		var rids: Array = (terrain.get(&"regions") as Dictionary).keys()
		rids.sort()
		for rid: Variant in rids:
			_on_region_attached(str(rid))
		if terrain.has_signal(&"region_attached"):
			terrain.connect(&"region_attached", _on_region_attached)
			terrain.connect(&"region_detached", _on_region_detached)


## region id -> [post ids] raised from its spawns
var _by_region: Dictionary = {}


func _on_region_attached(rid: String) -> void:
	var terrain: Node = world.get(&"terrain") if world != null else null
	if terrain == null or not (terrain.get(&"regions") as Dictionary).has(rid):
		return
	var rt: RegionTerrain = terrain.regions[rid]
	var ids: Array = rt.spawns.keys()
	ids.sort()
	for sid: Variant in ids:
		if not str(sid).begins_with("trader:"):
			continue
		var s: Dictionary = rt.spawns[sid]
		var td: TraderDef = Content.get_def(&"trader", StringName(str(sid).get_slice(":", 1))) as TraderDef
		if td == null:
			Log.warn("trade", "spawn %s names no trader def" % sid)
			continue
		var a: Array = s["pos"]
		var post_id: String = str(sid)
		var built: Array = _by_region.get(rid, [])
		if built.has(post_id):
			continue
		built.append(post_id)
		_by_region[rid] = built
		var at := Vector3(float(a[0]), float(a[1]), float(a[2]))
		var yaw: float = float(s.get("yaw", 0.0))
		var dress: bool = not in_building(rt.placements, td, at)
		var streamer: Variant = terrain.get(&"streamer")
		if streamer != null:
			(streamer.get(&"steps")).call(&"add", ["Manning the Waystation…", add_post.bind(post_id, td, at, yaw, true, dress), "trader %s" % post_id])
		else:
			add_post(post_id, td, at, yaw, true, dress)


func _on_region_detached(rid: String) -> void:
	var terrain: Node = world.get(&"terrain") if world != null else null
	var streamer: Variant = terrain.get(&"streamer") if terrain != null else null
	for post_id: Variant in _by_region.get(rid, []):
		if streamer != null:
			(streamer.get(&"steps")).call(&"cancel", "trader %s" % post_id, true)
		var e: Dictionary = posts.get(post_id, {})
		if e.get("node") != null and is_instance_valid(e["node"]):
			(e["node"] as Node).queue_free()
		posts.erase(post_id)
	_by_region.erase(rid)


func _exit_tree() -> void:
	for c: StringName in COMMANDS:
		Game.unregister_command(c)


## Whether a post's spawn stands inside a placement of the building its def is built into
## (TraderDef.in_poi; RegionTerrain.placements entries). Warns when it is off the building's anchor:
## the counter would not stand at the post's hatch.
static func in_building(placements: Array, td: TraderDef, at: Vector3) -> bool:
	if td.in_poi.is_empty():
		return false
	var want := StringName(str(td.in_poi.get("poi", "")))
	var pd: PoiDef = Content.get_def(&"poi", want) as PoiDef
	if pd == null:
		return false
	for pl: Variant in placements:
		var p: Dictionary = pl
		if str(p.get("kind", "")) != "poi" or StringName(str(p.get("def", ""))) != want:
			continue
		var o: Array = p["origin"]
		var xf := Transform3D(Basis(Vector3.UP, -deg_to_rad(float(p.get("rotation", 0.0)))), Vector3(float(o[0]), float(o[1]), float(o[2])))
		var local: Vector3 = xf.affine_inverse() * at
		if local.x < 0.0 or local.z < 0.0 or local.x > float(pd.footprint.x) or local.z > float(pd.footprint.y):
			continue
		var a: Array = td.in_poi["anchor"]
		var off: float = Vector2(local.x, local.z).distance_to(Vector2(float(a[0]), float(a[1])))
		if off > 0.5:
			Log.warn("trade", "%s spawn is %.1f m off its anchor in %s (%s): its counter won't stand at the hatch" % [td.id, off, want, p.get("id", "")])
		return true
	return false


## Raises a post (also used by tests and QA shots). `yaw` in degrees: the post's +Z faces it.
## `dress` false: the post stands in its building (in_building) and raises no set dressing.
func add_post(post_id: String, td: TraderDef, pos: Vector3, yaw: float, build: bool = true, dress: bool = true) -> void:
	var entry: Dictionary = {"id": post_id, "def": td, "pos": pos, "yaw": yaw, "node": null}
	posts[post_id] = entry
	Log.info("trade", "%s raised at (%.0f, %.0f), facing %.0f°" % [post_id, pos.x, pos.z, yaw])
	if build:
		var node := TraderPost.new()
		node.name = "Post_%s" % post_id.replace(":", "_")
		node.manager = self
		node.post_id = post_id
		node.def = td
		node.dress = dress
		add_child(node)
		node.global_transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw)), pos)
		node.build(world)
		entry["node"] = node


## The post a trader def stands at: the one nearest `near` for a def placed more than once (the
## Program's relay camps).
func post_of(trader_id: StringName, near: Vector3 = Vector3.ZERO) -> Dictionary:
	var best: Dictionary = {}
	var best_d: float = INF
	var ids: Array = posts.keys()
	ids.sort()
	for pid: Variant in ids:
		if (posts[pid]["def"] as TraderDef).id != trader_id:
			continue
		var d: float = (posts[pid]["pos"] as Vector3).distance_to(near)
		if d < best_d:
			best = posts[pid]
			best_d = d
	return best


## Whether a point is inside a post's safe zone (AIDirector.spawn_point_ok asks).
func is_safe(pos: Vector3) -> bool:
	for pid: Variant in posts.keys():
		var e: Dictionary = posts[pid]
		var c: Vector3 = e["pos"]
		if Vector2(pos.x - c.x, pos.z - c.z).length() <= (e["def"] as TraderDef).safe_radius:
			return true
	return false


# --- Shop -----------------------------------------------------------------------------------------

## The shop's stock now (rolled for the current restock period, then changed by trade). A def with
## `stock_per_post` (the relay camps) keeps a stock per post (TD-146): `post_id` names it, or the
## post nearest the local player when it is "".
func stock_of(trader_id: StringName, post_id: String = "") -> Dictionary:
	var td: TraderDef = Content.get_def(&"trader", trader_id) as TraderDef
	if td == null:
		return {}
	if td.stock_per_post and post_id == "":
		var lp: PlayerState = Game.session.local_player()
		post_id = str(post_of(td.id, _player_pos(lp) if lp != null else Vector3.ZERO).get("id", ""))
	var key: String = stock_key(td, post_id)
	var p: int = Contracts.period(td, Game.session.clock.day())
	var all: Dictionary = Game.session.world.traders
	# Saves from before per-post stock keyed every camp's shelves by the def id: a post with no
	# entry of its own starts from that one (no save version bump).
	if key != String(td.id) and not all.has(key) and all.has(String(td.id)):
		all[key] = (all[String(td.id)] as Dictionary).duplicate(true)
	var st: Dictionary = all.get(key, {})
	if int(st.get("period", -1)) != p:
		st = {"period": p, "stock": Contracts.roll_stock(td, p, Game.session.world_seed, key)}
		all[key] = st
	return st["stock"]


## The key a post's stock is saved under in WorldState.traders: its post id for a def with
## `stock_per_post`, else the def id (one shop however many times the def is placed).
static func stock_key(td: TraderDef, post_id: String) -> String:
	return post_id if td.stock_per_post and post_id != "" else String(td.id)


## Whose standing a post reads and whose contracts it counts: the giver of its contracts (a Program
## relay camp answers to Waystation 9).
static func rep_key(td: TraderDef) -> StringName:
	return StringName(td.contracts_from[0]) if not td.contracts_from.is_empty() else td.id


## A player's reputation tier at a trader.
func rep_tier(p: PlayerState, td: TraderDef) -> int:
	return td.rep_tier(p.contracts.reputation(rep_key(td)))


func _cmd_trade_buy(args: Dictionary) -> Dictionary:
	var ctx: Dictionary = _trade_ctx(args)
	if ctx.has("error"):
		return _fail(ctx["error"])
	var p: PlayerState = ctx["player"]
	var td: TraderDef = ctx["trader"]
	var item := StringName(str(args.get("item", "")))
	var n: int = maxi(1, int(args.get("count", 1)))
	var stock: Dictionary = stock_of(td.id, str((ctx["post"] as Dictionary).get("id", "")))
	var e: Dictionary = stock.get(String(item), {})
	if e.is_empty() or int(e["count"]) <= 0:
		return _fail("out of stock")
	var tier: int = rep_tier(p, td)
	if int(e.get("rep_tier", 0)) > tier:
		return _fail("not trusted with that yet")
	n = mini(n, int(e["count"]))
	var idef: ItemDef = Content.item(item)
	var price: int = td.buy_price(idef, tier) * n
	if p.inventory.count_of(&"scrip") < price:
		return _fail("not enough scrip")
	p.inventory.remove(&"scrip", price)
	var left: int = p.inventory.add_item(item, n)
	if left > 0:
		_drop(p, item, left)
	e["count"] = int(e["count"]) - n
	if int(e["count"]) <= 0:
		stock.erase(String(item))
	Events.inventory_changed.emit(p.id)
	Events.trade_made.emit(p.id, td.id, item, n, -price)
	return {"ok": true, "count": n, "scrip": price}


func _cmd_trade_sell(args: Dictionary) -> Dictionary:
	var ctx: Dictionary = _trade_ctx(args)
	if ctx.has("error"):
		return _fail(ctx["error"])
	var p: PlayerState = ctx["player"]
	var td: TraderDef = ctx["trader"]
	var item := StringName(str(args.get("item", "")))
	var idef: ItemDef = Content.item(item)
	if idef == null:
		return _fail("unknown item")
	var each: int = td.sell_price(idef)
	if each <= 0:
		return _fail("the Program doesn't buy that")
	var n: int = mini(maxi(1, int(args.get("count", 1))), p.inventory.count_of(item))
	if n <= 0:
		return _fail("you have none")
	p.inventory.remove(item, n)
	var left: int = p.inventory.add_item(&"scrip", each * n)
	if left > 0:
		_drop(p, &"scrip", left)
	# What the post buys it sells on, to anyone.
	var stock: Dictionary = stock_of(td.id, str((ctx["post"] as Dictionary).get("id", "")))
	var e: Dictionary = stock.get(String(item), {"count": 0, "rep_tier": 0})
	e["count"] = int(e["count"]) + n
	stock[String(item)] = e
	Events.inventory_changed.emit(p.id)
	Events.trade_made.emit(p.id, td.id, item, -n, each * n)
	return {"ok": true, "count": n, "scrip": each * n}


## The player and trader of a trade command, checked: alive and within reach of the post.
func _trade_ctx(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null or not p.stats.alive:
		return {"error": "no player"}
	var td: TraderDef = Content.get_def(&"trader", StringName(str(args.get("trader", "")))) as TraderDef
	if td == null:
		return {"error": "no such trader"}
	var post: Dictionary = post_of(td.id, _player_pos(p))
	if post.is_empty():
		return {"error": "no such post"}
	if not bool(args.get("remote", false)) and _player_pos(p).distance_to(post["pos"]) > td.safe_radius:
		return {"error": "too far from the post"}
	return {"player": p, "trader": td, "post": post}


# --- Contracts board ------------------------------------------------------------------------------

## What the board shows a player today (offers they have taken are left out).
func board_offers(p: PlayerState, td: TraderDef) -> Array[Dictionary]:
	var post: Dictionary = post_of(td.id, _player_pos(p))
	var day: int = Game.session.clock.day()
	var out: Array[Dictionary] = []
	for o: Dictionary in Contracts.offers(td, day, Game.session.world_seed, buildings(), post.get("pos", Vector3.ZERO),
			rep_tier(p, td), Game.session.world.pois, p.contracts.busy_targets(), p.contracts.done):
		if not p.contracts.has_taken(str(o["id"]), day):
			out.append(o)
	return out


## Every building in the world (TD-118: PoiManager places them all at boot; once buildings stream,
## this must come from the PoiRegistry, never from what happens to be built near the player).
func buildings() -> Array:
	if buildings_source.is_valid():
		return buildings_source.call()
	var pois: Node = world.get(&"pois") if world != null else null
	return pois.call(&"all_buildings") if pois != null and pois.has_method(&"all_buildings") else []


func _cmd_contract_accept(args: Dictionary) -> Dictionary:
	var ctx: Dictionary = _trade_ctx(args)
	if ctx.has("error"):
		return _fail(ctx["error"])
	var p: PlayerState = ctx["player"]
	var td: TraderDef = ctx["trader"]
	if p.contracts.count_for(rep_key(td)) >= td.max_active:
		return _fail("finish one first (%d at most)" % td.max_active)
	var oid: String = str(args.get("offer", ""))
	var offer: Dictionary = {}
	for o: Dictionary in board_offers(p, td):
		if str(o["id"]) == oid:
			offer = o
	if offer.is_empty():
		return _fail("that offer is gone")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(offer["def"]))) as QuestDef
	var day: int = Game.session.clock.day()
	var cid: String = "k:%s:%d:%s" % [td.id, day, oid.get_slice(":", 3)]
	var c: Dictionary = {"id": cid, "def": String(qd.id), "giver": qd.giver, "target": offer["target"],
		"name": offer["name"], "pos": offer["pos"], "tier": offer["tier"], "state": ContractLog.ACTIVE, "day": day,
		"type": qd.quest_type}
	if qd.expires_days > 0:
		c["due"] = day + qd.expires_days
	if qd.quest_type == "defend":
		var bp: Array = offer["pos"]
		var spot: Vector3 = Contracts.defend_spot(Vector3(float(bp[0]), float(bp[1]), float(bp[2])),
			"%d:%s" % [Game.session.world_seed, cid], _spot_ok)
		if world != null and world.has_method(&"height_at"):
			spot.y = float(world.call(&"height_at", spot.x, spot.z))
		c["spot"] = [spot.x, spot.y, spot.z]
	p.contracts.mark_taken(oid, day)
	p.contracts.active.append(c)
	Events.contract_accepted.emit(p.id, cid, qd.id)
	Events.player_status_message.emit("Contract taken: %s — %s." % [qd.display_name, c["name"]], &"info")
	return {"ok": true, "contract": cid}


func _cmd_contract_turn_in(args: Dictionary) -> Dictionary:
	var ctx: Dictionary = _trade_ctx(args)
	if ctx.has("error"):
		return _fail(ctx["error"])
	var p: PlayerState = ctx["player"]
	var td: TraderDef = ctx["trader"]
	var c: Dictionary = p.contracts.get_contract(str(args.get("contract", "")))
	if c.is_empty() or not td.contracts_from.has(str(c.get("giver", ""))):
		return _fail("no such contract here")
	if str(c["state"]) != ContractLog.READY:
		return _fail("not done yet")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	if qd.quest_type == "fetch":
		if not p.inventory.remove(StringName(qd.item), 1):
			return _fail("bring the %s" % ("cache" if qd.place else Content.item(StringName(qd.item)).display_name.to_lower()))
	var paid: Dictionary = {}
	for k: Variant in qd.rewards.keys():
		var n: int = int(qd.rewards[k])
		match str(k):
			"xp":
				p.progression.add_xp(n)
			"reputation":
				p.contracts.add_rep(StringName(str(c["giver"])), n)
			_:
				var left: int = p.inventory.add_item(StringName(str(k)), n)
				if left > 0:
					_drop(p, StringName(str(k)), left)
		paid[str(k)] = n
	p.contracts.remove(str(c["id"]))
	p.contracts.done[String(qd.id)] = int(p.contracts.done.get(String(qd.id), 0)) + 1
	Events.inventory_changed.emit(p.id)
	Events.contract_completed.emit(p.id, str(c["id"]), qd.id, int(c.get("tier", qd.tier)))
	Events.player_status_message.emit("Contract done: %s. %d scrip." % [qd.display_name, int(paid.get("scrip", 0))], &"info")
	return {"ok": true, "rewards": paid}


func _cmd_contract_abandon(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null:
		return _fail("no player")
	var cid: String = str(args.get("contract", ""))
	var c: Dictionary = p.contracts.get_contract(cid)
	if c.is_empty():
		return _fail("no such contract")
	_end_run(cid)
	p.contracts.remove(cid)
	# Walking away from a job costs standing (TD-146).
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c.get("def", "")))) as QuestDef
	var cost: int = qd.abandon_rep if qd != null else 0
	if cost > 0:
		p.contracts.add_rep(StringName(str(c.get("giver", ""))), -cost)
		Events.player_status_message.emit("Contract dropped: %s. -%d standing." % [qd.display_name, cost], &"warning")
	return {"ok": true, "rep": -cost}


## Starts holding a defence's cache: the player must be at it.
func _cmd_contract_start_defend(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null or not p.stats.alive:
		return _fail("no player")
	var c: Dictionary = p.contracts.get_contract(str(args.get("contract", "")))
	if c.is_empty() or str(c.get("type", "")) != "defend" or str(c["state"]) != ContractLog.ACTIVE:
		return _fail("nothing to hold")
	if _runs.has(str(c["id"])):
		return _fail("already holding it")
	var spot: Vector3 = _vec(c["spot"])
	if not bool(args.get("remote", false)) and _player_pos(p).distance_to(spot) > 6.0:
		return _fail("get to the cache")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	# Never into the Hum (TD-142): not while it is out, nor when it would come before the uplink is done.
	var clock: WorldClock = Game.session.clock
	var hold_h: float = qd.duration * clock.minutes_per_real_second() / 60.0
	if clock.is_horde_active() or clock.hours_until_horde() < hold_h + 0.5:
		return _fail("not with the Hum coming")
	_runs[str(c["id"])] = {"t": 0.0, "next_wave": 3.0, "wave": 0, "outside": 0.0, "enemies": [], "player": String(p.id),
		"duration": qd.duration}
	c["running"] = true
	Events.player_status_message.emit("The uplink is running. Hold the cache for %d seconds." % int(qd.duration), &"warning")
	if Audio != null:
		Audio.play_3d(&"sfx/trap_alarm_siren", spot + Vector3.UP, {"volume_db": -8.0, "max_distance": 200.0})
	return {"ok": true}


# --- Following contracts in the world -------------------------------------------------------------

func _process(delta: float) -> void:
	if Game.session == null:
		return
	_tick += delta
	if _tick < TICK:
		return
	var dt: float = _tick
	_tick = 0.0
	_guards(dt)
	for pid: Variant in Game.session.players.keys():
		var p: PlayerState = Game.session.players[pid]
		expire_contracts(p)
		for c: Variant in p.contracts.active:
			_follow(p, c, dt)


# --- Expiry (TD-146) ------------------------------------------------------------------------------

## The day at whose dawn an open contract fails, or 0 when it never does. Taken at accept (`due`);
## a contract saved before expiry existed takes it from its def and the day it was accepted.
static func due_day(c: Dictionary) -> int:
	if c.has("due"):
		return int(c["due"])
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c.get("def", "")))) as QuestDef
	if qd == null or qd.expires_days <= 0:
		return 0
	return int(c.get("day", 1)) + qd.expires_days


## Fails every open contract of a player whose dawn has come: it leaves the books, its target is
## free for the board again, and the giver docks `fail_rep` standing. A contract done and waiting to
## be reported never fails, nor a defence being held right now.
func expire_contracts(p: PlayerState) -> void:
	var clock: WorldClock = Game.session.clock
	var day: int = clock.day()
	for c: Variant in p.contracts.active.duplicate():
		var cd: Dictionary = c
		var due: int = due_day(cd)
		if due <= 0 or str(cd.get("state", "")) != ContractLog.ACTIVE or _runs.has(str(cd.get("id", ""))):
			continue
		if day > due or (day == due and clock.hour_f() >= clock.sunrise_hour):
			_fail_contract(p, cd)


func _fail_contract(p: PlayerState, c: Dictionary) -> void:
	var cid: String = str(c.get("id", ""))
	_end_run(cid)
	p.contracts.remove(cid)
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c.get("def", "")))) as QuestDef
	var cost: int = qd.fail_rep if qd != null else 0
	if cost > 0:
		p.contracts.add_rep(StringName(str(c.get("giver", ""))), -cost)
	Events.player_status_message.emit("Contract failed: %s — %s ran out of time. -%d standing." % [
		qd.display_name if qd != null else "Contract", str(c.get("name", "")), cost], &"warning")


func _follow(p: PlayerState, c: Dictionary, dt: float) -> void:
	match str(c.get("type", "")):
		"clear":
			if str(c["state"]) == ContractLog.ACTIVE and _clear_done(c):
				_mark_ready(p, c)
		"fetch":
			var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
			if qd != null and not qd.place:
				_follow_recovery(p, c, qd)
			elif not bool(c.get("placed", false)):
				_place_cache(c, p)
			else:
				_follow_beacon(c, p)
		"defend":
			_follow_defence(p, c, dt)


## A building is cleared when every sleeper in it is down (PoiInstance marks it) and, when it has
## a loot room, its loot room has been searched.
func _clear_done(c: Dictionary) -> bool:
	var st: Dictionary = Game.session.world.pois.get(str(c["target"]), {})
	if not bool(st.get("cleared", false)):
		return false
	return bool(c.get("looted", false)) or not Contracts.has_loot_room(_target_def(c))


func _target_def(c: Dictionary) -> StringName:
	for b: Variant in buildings():
		if str((b as Dictionary).get("id", "")) == str(c["target"]):
			return StringName(str((b as Dictionary).get("def", "")))
	return &""


func _mark_ready(p: PlayerState, c: Dictionary) -> void:
	c["state"] = ContractLog.READY
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	var td: TraderDef = Content.get_def(&"trader", StringName(str(c["giver"]))) as TraderDef
	Events.player_status_message.emit("%s done. Report to %s." % [qd.display_name if qd != null else "Contract",
		td.display_name if td != null else "the Waystation"], &"info")


func _on_poi_cleared(instance_id: StringName) -> void:
	for pid: Variant in Game.session.players.keys():
		var p: PlayerState = Game.session.players[pid]
		for c: Variant in p.contracts.active:
			var cd: Dictionary = c
			if str(cd.get("type", "")) == "clear" and str(cd["target"]) == String(instance_id) and _clear_done(cd):
				_mark_ready(p, cd)


## A container of the target's loot room searched counts it searched, wherever the player reached
## it from (TD-145): the container id (`c:<building>:<prop key>`) names the prop, and the
## building's layout says where it stands. Only a prop the layout can't name falls back to where
## the player stands.
func _on_container_looted(player_id: StringName, container_id: StringName, _tier: int) -> void:
	var p: PlayerState = Game.session.players.get(player_id)
	if p == null:
		return
	for c: Variant in p.contracts.active:
		var cd: Dictionary = c
		var prefix: String = "c:%s:" % cd["target"]
		if str(cd.get("type", "")) != "clear" or not String(container_id).begins_with(prefix):
			continue
		var target := StringName(str(cd["target"]))
		var in_room: int = Contracts.prop_in_loot_room(_target_layout(target), String(container_id).substr(prefix.length()))
		if in_room == 1 or (in_room == -1 and _in_loot_room(target, _player_pos(p))):
			cd["looted"] = true
			if str(cd["state"]) == ContractLog.ACTIVE and _clear_done(cd):
				_mark_ready(p, cd)


## A building's layout: its PoiInstance's when built (always so when one of its containers was just
## searched), else compiled from its def.
func _target_layout(instance_id: StringName) -> PoiLayout:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois != null and pois.get(&"instances") is Dictionary:
		var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(instance_id) as PoiInstance
		if inst != null:
			return inst.layout
	var pd: PoiDef = Content.get_def(&"poi", _target_def({"target": String(instance_id)})) as PoiDef
	return PoiLayout.compile(pd) if pd != null else null


func _in_loot_room(instance_id: StringName, pos: Vector3) -> bool:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois == null:
		return false
	var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(instance_id) as PoiInstance
	if inst == null or inst.layout.loot_room.is_empty():
		return false
	var loc: Array = inst.locate(pos)
	if loc.size() < 2:
		return false
	var lr: Dictionary = inst.layout.loot_room
	return int(loc[0]) == int(lr.get("level", 0)) and inst.layout.room_at(int(loc[0]), loc[1]) == str(lr.get("room", ""))


## Sets a fetch contract's cache down in its building once the building stands and the player is
## near: on its authored spot or a free floor cell of its loot room (Contracts.cache_spot, TD-144).
## It is a loose item from then on (saved with the world's loose items), with a Program beacon
## blinking over it while the contract is open.
func _place_cache(c: Dictionary, p: PlayerState) -> void:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois == null:
		return
	var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(StringName(str(c["target"]))) as PoiInstance
	if inst == null or _player_pos(p).distance_to(_vec(c["pos"])) > PLACE_RANGE:
		return
	var spot: Dictionary = Contracts.cache_spot(inst.layout, "%d:%s" % [Game.session.world_seed, c["id"]])
	if spot.is_empty():
		return
	var at: Vector3 = inst.global_transform * ((spot["pos"] as Vector3) + Vector3.UP * 0.3)
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	ItemDrop.spawn(world, ItemStack.make(StringName(qd.item), 1), at, StringName("cache_%s" % str(c["id"]).replace(":", "_")))
	c["placed"] = true
	c["cache_at"] = [at.x, at.y, at.z]


## contract id -> the beacon blinking over its cache
var _beacons: Dictionary = {}


## A Program beacon over a placed cache while the contract is open and the player is near, so it
## can be found in a dark room; gone once it is picked up.
func _follow_beacon(c: Dictionary, p: PlayerState) -> void:
	var cid: String = str(c["id"])
	var want: bool = bool(c.get("placed", false)) and str(c["state"]) == ContractLog.ACTIVE \
		and _player_pos(p).distance_to(_vec(c.get("cache_at", c["pos"]))) < CACHE_RANGE
	if want and not _beacons.has(cid):
		var b := CacheBeacon.new()
		add_child(b)
		b.global_position = _vec(c["cache_at"]) + Vector3.UP * 0.25
		_beacons[cid] = b
	elif not want and _beacons.has(cid):
		_drop_beacon(cid)


func _drop_beacon(cid: String) -> void:
	if _beacons.has(cid):
		var b: Node = _beacons[cid]
		if is_instance_valid(b):
			b.queue_free()
		_beacons.erase(cid)


## A small amber lamp that pulses (the Program's cache beacon).
class CacheBeacon:
	extends Node3D
	var _light: OmniLight3D
	var _t: float = 0.0

	func _ready() -> void:
		_light = OmniLight3D.new()
		_light.light_color = Color(1.0, 0.62, 0.2)
		_light.omni_range = 3.5
		_light.light_energy = 0.0
		_light.shadow_enabled = false
		add_child(_light)

	func _process(delta: float) -> void:
		_t += delta
		_light.light_energy = 1.4 * maxf(0.0, sin(_t * 4.0)) if fmod(_t, 2.0) < 0.8 else 0.0


## A fetch whose building already holds the item (the field lab's Bloom core, TD-179): ready while
## the player carries one, wherever it came from, and back to open if they drop or sell it.
func _follow_recovery(p: PlayerState, c: Dictionary, qd: QuestDef) -> void:
	var has: bool = p.inventory.count_of(StringName(qd.item)) > 0
	if has and str(c["state"]) == ContractLog.ACTIVE:
		_mark_ready(p, c)
	elif not has and str(c["state"]) == ContractLog.READY:
		c["state"] = ContractLog.ACTIVE


func _on_item_picked_up(owner_id: StringName, item_id: StringName, _count: int) -> void:
	var p: PlayerState = Game.session.players.get(owner_id)
	if p == null:
		return
	for c: Variant in p.contracts.active:
		var cd: Dictionary = c
		if str(cd.get("type", "")) != "fetch" or not bool(cd.get("placed", false)) or str(cd["state"]) != ContractLog.ACTIVE:
			continue
		var qd: QuestDef = Content.get_def(&"quest", StringName(str(cd["def"]))) as QuestDef
		if qd == null:
			continue
		if StringName(qd.item) == item_id and _player_pos(p).distance_to(_vec(cd.get("cache_at", cd["pos"]))) < 12.0:
			_mark_ready(p, cd)
			return


# --- Defence --------------------------------------------------------------------------------------

func _follow_defence(p: PlayerState, c: Dictionary, dt: float) -> void:
	var cid: String = str(c["id"])
	if str(c["state"]) != ContractLog.ACTIVE:
		_end_run(cid)
		return
	var spot: Vector3 = _vec(c["spot"])
	var near: bool = _player_pos(p).distance_to(spot) < CACHE_RANGE
	if near and not _caches.has(cid):
		_caches[cid] = _make_cache(cid, spot)
	elif not near and _caches.has(cid) and not _runs.has(cid):
		(_caches[cid] as Node).queue_free()
		_caches.erase(cid)
	if not _runs.has(cid):
		return
	var run: Dictionary = _runs[cid]
	run["t"] = float(run["t"]) + dt
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	if _player_pos(p).distance_to(spot) > HOLD_RANGE:
		run["outside"] = float(run["outside"]) + dt
		if float(run["outside"]) > LEAVE_GRACE:
			Events.player_status_message.emit("You left the cache. The uplink dropped — start it again.", &"warning")
			_end_run(cid)
			c.erase("running")
			return
	else:
		run["outside"] = 0.0
	if int(run["wave"]) < qd.waves and float(run["t"]) >= float(run["next_wave"]):
		_wave(c, qd, run, spot)
		run["wave"] = int(run["wave"]) + 1
		run["next_wave"] = float(run["next_wave"]) + qd.duration / float(qd.waves + 1)
	if float(run["t"]) >= qd.duration:
		_end_run(cid)
		c.erase("running")
		_mark_ready(p, c)


func _wave(c: Dictionary, qd: QuestDef, run: Dictionary, spot: Vector3) -> void:
	var ai: Node = world.get(&"ai") if world != null else null
	if ai == null or not ai.has_method(&"spawn"):
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("wave:%d:%s:%d" % [Game.session.world_seed, c["id"], int(run["wave"])])
	var gs: int = Game.session.gamestage(Game.session.players.get(StringName(str(run.get("player", "")))))
	var n: int = wave_count(qd, gs, rng)
	var ang: float = rng.randf() * TAU
	for i: int in n:
		var at: Vector3 = _wave_point(ai, spot, ang + rng.randf_range(-0.5, 0.5), rng)
		# No fixed tier (TD-142): the AI director rolls it from the gamestage, and holds back types the
		# gamestage hasn't reached, as it does for heat responses.
		var e: Node = ai.call(&"spawn", _pick_enemy(qd, rng), at, {"target": spot})
		if e != null:
			(run["enemies"] as Array).append(e.get(&"entity_id"))


func _wave_point(ai: Node, spot: Vector3, ang: float, rng: RandomNumberGenerator) -> Vector3:
	var fallback := Vector3.INF
	for attempt: int in 10:
		var r: float = rng.randf_range(WAVE_RING.x, WAVE_RING.y)
		var a: float = ang + float(attempt) * 0.6
		var p := Vector3(spot.x + cos(a) * r, 0.0, spot.z + sin(a) * r)
		p.y = float(world.call(&"height_at", p.x, p.z)) if world.has_method(&"height_at") else spot.y
		if fallback == Vector3.INF:
			fallback = p
		if bool(ai.call(&"spawn_point_ok", p)):
			return p
	return fallback


## Hollowed in one wave: the def's band, plus `wave_growth` per gamestage point (TD-142).
static func wave_count(qd: QuestDef, gamestage: int, rng: RandomNumberGenerator) -> int:
	var n: int = rng.randi_range(int(qd.wave_size[0]), int(qd.wave_size[qd.wave_size.size() - 1]))
	return n + int(floor(float(gamestage) * qd.wave_growth))


static func _pick_enemy(qd: QuestDef, rng: RandomNumberGenerator) -> StringName:
	var keys: Array = qd.enemies.keys()
	keys.sort()
	var total: float = 0.0
	for k: Variant in keys:
		total += float(qd.enemies[k])
	var r: float = rng.randf() * total
	for k: Variant in keys:
		r -= float(qd.enemies[k])
		if r <= 0.0:
			return StringName(str(k))
	return StringName(str(keys[keys.size() - 1]))


func _end_run(cid: String) -> void:
	_drop_beacon(cid)
	_runs.erase(cid)
	if _caches.has(cid):
		(_caches[cid] as Node).queue_free()
		_caches.erase(cid)


func _make_cache(cid: String, spot: Vector3) -> Node3D:
	var cache := DefendCache.new()
	cache.manager = self
	cache.contract_id = cid
	add_child(cache)
	cache.global_position = spot
	return cache


func is_running(cid: String) -> bool:
	return _runs.has(cid)


func run_progress(cid: String) -> float:
	if not _runs.has(cid):
		return 0.0
	var r: Dictionary = _runs[cid]
	return clampf(float(r["t"]) / maxf(1.0, float(r["duration"])), 0.0, 1.0)


func _on_player_died(player_id: StringName, _cause: String) -> void:
	var p: PlayerState = Game.session.players.get(player_id)
	if p == null:
		return
	for c: Variant in p.contracts.active:
		var cid: String = str((c as Dictionary).get("id", ""))
		if _runs.has(cid):
			_end_run(cid)
			(c as Dictionary).erase("running")


## A defence spot: inside the map, dry, not steep, outside buildings and every safe zone.
func _spot_ok(p: Vector3) -> bool:
	if world == null:
		return true
	var terrain: Node = world.get(&"terrain")
	if terrain != null and terrain.call(&"region_terrain_at", p.x, p.z) == null:
		return false
	if is_safe(p):
		return false
	var wsys: Node = world.get(&"water")
	if wsys != null and wsys.has_method(&"depth_at") and float(wsys.call(&"depth_at", p)) > 0.1:
		return false
	if world.has_method(&"height_at"):
		var e: float = 1.5
		var hx: float = float(world.call(&"height_at", p.x + e, p.z)) - float(world.call(&"height_at", p.x - e, p.z))
		var hz: float = float(world.call(&"height_at", p.x, p.z + e)) - float(world.call(&"height_at", p.x, p.z - e))
		if Vector2(hx, hz).length() / (2.0 * e) > 0.35:
			return false
	var pois: Node = world.get(&"pois")
	if pois != null and pois.has_method(&"poi_at") and pois.call(&"poi_at", p + Vector3.UP) != null:
		return false
	return true


# --- Guards ---------------------------------------------------------------------------------------

## The Program's guards keep the post clear: any Hollowed (or Ashen) inside a safe zone takes fire
## from the nearest guard tower, with a muzzle flash and a tracer from its deck (TD-143); a post
## without towers fires from above its centre. Wanderers and investigators heading into a zone
## are turned to its edge instead, so they skirt the wire rather than walk in and die.
func _guards(dt: float) -> void:
	var ai: Node = world.get(&"ai") if world != null else null
	if ai == null or not ai.has_method(&"enemies_in_radius"):
		return
	for pid: Variant in posts.keys():
		var e: Dictionary = posts[pid]
		var td: TraderDef = e["def"]
		var centre: Vector3 = e["pos"]
		for en: Enemy in ai.call(&"enemies_in_radius", centre, td.safe_radius + AVOID_MARGIN):
			if not is_instance_valid(en) or en.is_queued_for_deletion() or not en.is_alive() or en.ally != null:
				continue
			var flat: float = Vector2(en.global_position.x - centre.x, en.global_position.z - centre.z).length()
			if flat > td.safe_radius:
				_steer_off(en, centre, td.safe_radius)
				continue
			var d := DamageInfo.make(td.guard_dps * dt, &"ballistic", &"firearm", StringName("guard:%s" % pid))
			d.source_pos = _gun_for(e, en.global_position)
			d.hit_pos = en.global_position + Vector3.UP * 1.2
			d.direction = (d.hit_pos - d.source_pos).normalized()
			d.stagger = 0.4
			en.take_damage(d)
			if is_inside_tree():
				GuardShot.fire(self, d.source_pos, d.hit_pos)
			if Audio != null:
				Audio.play_3d(&"sfx/gun_revolver_shot", d.source_pos, {"volume_db": 0.0, "max_distance": 300.0, "occlusion": false})


## Metres outside a safe zone where a drifting Hollowed is turned along the wire.
const AVOID_MARGIN: float = 14.0
## A guard's gun on a tower deck (waystation_tower: the deck at 4.5 m, a man's shoulder above it).
const TOWER_GUN_Y: float = 5.9


## The gun nearest a target: a guard tower of the post, else a point over its centre.
func _gun_for(e: Dictionary, target: Vector3) -> Vector3:
	var best := (e["pos"] as Vector3) + Vector3.UP * 7.0
	var best_d: float = INF
	for t: Vector3 in towers_of(e):
		var d: float = t.distance_to(target)
		if d < best_d:
			best = t
			best_d = d
	return best


## World positions of a post's guard guns (one per waystation_tower in its dressing).
static func towers_of(e: Dictionary) -> Array[Vector3]:
	var out: Array[Vector3] = []
	var td: TraderDef = e["def"]
	var basis := Basis(Vector3.UP, deg_to_rad(float(e.get("yaw", 0.0))))
	for v: Variant in td.props:
		var pd: Dictionary = v
		if str(pd.get("prop", "")) != "waystation_tower":
			continue
		var off: Array = pd.get("offset", [0, 0])
		out.append((e["pos"] as Vector3) + basis * Vector3(float(off[0]), 0.0, float(off[1])) + Vector3.UP * TOWER_GUN_Y)
	return out


## A Hollowed drifting toward the zone (not hunting the player inside it): its goal moves to the
## zone's edge, round the side it is on.
static func _steer_off(en: Enemy, centre: Vector3, radius: float) -> void:
	if en.state not in [Enemy.State.IDLE, Enemy.State.WANDER, Enemy.State.INVESTIGATE] or en.horde:
		return
	var t: Vector3 = en.target_pos
	var to_t := Vector2(t.x - centre.x, t.z - centre.z)
	if to_t.length() > radius:
		return
	var out := Vector2(en.global_position.x - centre.x, en.global_position.z - centre.z)
	out = out.normalized() if out.length() > 0.1 else Vector2.RIGHT
	var edge: Vector2 = Vector2(centre.x, centre.z) + out * (radius + AVOID_MARGIN * 0.5)
	en.target_pos = Vector3(edge.x, en.global_position.y, edge.y)
	en.home = en.target_pos


## A guard's shot made visible: a muzzle flash on the tower and a tracer to the target, gone in a
## tenth of a second.
class GuardShot:
	extends Node3D
	var _t: float = 0.0
	var _light: OmniLight3D
	var _line: MeshInstance3D

	static func fire(parent: Node, from: Vector3, to: Vector3) -> void:
		var s := GuardShot.new()
		parent.add_child(s)
		s.global_position = from
		s._build(to - from)

	func _build(rel: Vector3) -> void:
		_light = OmniLight3D.new()
		_light.light_color = Color(1.0, 0.78, 0.4)
		_light.omni_range = 6.0
		_light.light_energy = 3.0
		add_child(_light)
		var im := ImmediateMesh.new()
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(1.0, 0.85, 0.5, 0.8)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		im.surface_begin(Mesh.PRIMITIVE_LINES, mat)
		# The tracer: the last two thirds of the flight, so it reads as a streak, not a beam.
		im.surface_add_vertex(rel * 0.35)
		im.surface_add_vertex(rel)
		im.surface_end()
		_line = MeshInstance3D.new()
		_line.mesh = im
		_line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(_line)

	func _process(delta: float) -> void:
		_t += delta
		_light.light_energy = maxf(0.0, 3.0 * (1.0 - _t / 0.08))
		if _t > 0.12:
			queue_free()


# --- Tether ---------------------------------------------------------------------------------------

## Map markers: every post, and the local player's contract targets.
## [{pos: Vector3, kind: "trader" | "contract", ready: bool, label}]
func markers() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for pid: Variant in posts.keys():
		out.append({"pos": posts[pid]["pos"], "kind": "trader", "ready": false, "label": (posts[pid]["def"] as TraderDef).display_name})
	var p: PlayerState = Game.session.local_player() if Game.session != null else null
	if p != null:
		for c: Variant in p.contracts.active:
			var cd: Dictionary = c
			out.append({"pos": _vec(cd.get("spot", cd["pos"])), "kind": "contract",
				"ready": str(cd["state"]) == ContractLog.READY, "label": str(cd.get("name", ""))})
	return out


## Tether lines for the local player's contracts.
func lines() -> PackedStringArray:
	var out: PackedStringArray = []
	var p: PlayerState = Game.session.local_player() if Game.session != null else null
	if p == null:
		return out
	for c: Variant in p.contracts.active:
		var cd: Dictionary = c
		var qd: QuestDef = Content.get_def(&"quest", StringName(str(cd["def"]))) as QuestDef
		var due: int = due_day(cd)
		var state: String = "report in" if str(cd["state"]) == ContractLog.READY else (
			"holding %d%%" % int(run_progress(str(cd["id"])) * 100.0) if _runs.has(str(cd["id"])) else (
				"open, due by dawn of day %d" % due if due > 0 else "open"))
		out.append("%s — %s (%s)" % [qd.display_name if qd != null else str(cd["def"]), str(cd.get("name", "")), state])
	return out


# --- UI -------------------------------------------------------------------------------------------

## Opens the trade screen at a post (tab "shop" at the counter, "board" at the board).
func open_screen(post_id: String, tab: String) -> void:
	if world == null or world.get(&"ui") == null:
		return
	if screen == null or not is_instance_valid(screen):
		screen = TraderScreen.new()
		screen.name = "TraderScreen"
		screen.manager = self
		(world.get(&"ui") as Node).add_child(screen)
	(screen as TraderScreen).open(post_id, tab)


# --- Helpers --------------------------------------------------------------------------------------

func _player(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null


func _player_pos(p: PlayerState) -> Vector3:
	if world != null and p.id == Game.session.local_player_id and world.get(&"player") != null:
		return (world.get(&"player") as Node3D).global_position
	return p.position


func _drop(p: PlayerState, item: StringName, n: int) -> void:
	if world != null:
		ItemDrop.spawn(world, ItemStack.make(item, n), _player_pos(p) + Vector3.UP)


static func _vec(a: Variant) -> Vector3:
	var arr: Array = a
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))


static func _fail(why: String) -> Dictionary:
	return {"ok": false, "error": why}
