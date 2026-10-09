extends GutTest
## Waystation trading (ADR-0039) through its commands: buying and selling round-trip scrip and
## stock; a contract taken from the board, then each kind finished in the world (a building
## cleared and its stores searched, a cache carried out, a cache held to the end) and turned in for
## scrip, XP and standing; the post's safe zone vetoes spawns and its guards shoot Hollowed inside.

class FakeWorld:
	extends Node3D
	var ai: Node = null
	var pois: Node = null
	var terrain: Node = null
	var player: Node3D = null
	var ui: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


class FakeAI:
	extends Node
	var list: Array[Enemy] = []

	func enemies_in_radius(pos: Vector3, r: float) -> Array[Enemy]:
		var out: Array[Enemy] = []
		for e: Enemy in list:
			if is_instance_valid(e) and e.global_position.distance_to(pos) <= r:
				out.append(e)
		return out


var _prev: GameSession
var _tm: TraderManager
var _p: PlayerState
var _td: TraderDef
var _world: FakeWorld
const POST := Vector3(100, 0, 100)


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "slice"})
	_p = Game.session.local_player()
	_p.position = POST + Vector3(0, 0, 6)
	_td = Content.get_def(&"trader", &"waystation_9") as TraderDef
	_world = FakeWorld.new()
	add_child_autofree(_world)
	_tm = TraderManager.new()
	_world.add_child(_tm)
	_tm.setup_world(_world)
	_tm.add_post("trader:waystation_9", _td, POST, -90.0, false)
	_tm.buildings_source = func() -> Array:
		return [{"id": "poi:ww", "def": "water_works", "name": "the Water Works", "tier": 2, "kind": "authored", "pos": POST + Vector3(400, 0, 0)},
			{"id": "poi:vfw", "def": "vfw_post", "name": "the Veterans' Post", "tier": 2, "kind": "authored", "pos": POST + Vector3(0, 0, 500)},
			{"id": "poi:laund", "def": "suds_spin_laundromat", "name": "the laundromat", "tier": 1, "kind": "authored", "pos": POST + Vector3(-300, 0, 0)},
			{"id": "poi:gro", "def": "hollowmere_grocery", "name": "the grocery", "tier": 2, "kind": "authored", "pos": POST + Vector3(0, 0, -350)},
			{"id": "poi:quarry", "def": "ridgeline_quarry_office", "name": "the quarry", "tier": 2, "kind": "authored", "pos": POST + Vector3(250, 0, 250)}]


func after_each() -> void:
	Game.session = _prev


func _args(extra: Dictionary = {}) -> Dictionary:
	var a: Dictionary = {"player": String(_p.id), "trader": "waystation_9"}
	a.merge(extra, true)
	return a


func test_buying_and_selling_round_trip_scrip_and_stock() -> void:
	var stock: Dictionary = _tm.stock_of(&"waystation_9")
	assert_true(stock.has("water_bottle_clean") or stock.has("canned_beans"), "the basics are on the shelves")
	var item: String = "water_bottle_clean" if stock.has("water_bottle_clean") else "canned_beans"
	var before: int = int((stock[item] as Dictionary)["count"])
	var price: int = _td.buy_price(Content.item(StringName(item)), 0)
	assert_false(bool(Game.execute(&"trade.buy", _args({"item": item}))["ok"]), "no scrip, no sale")
	_p.inventory.add_item(&"scrip", 100)
	var r: Dictionary = Game.execute(&"trade.buy", _args({"item": item}))
	assert_true(bool(r["ok"]), str(r))
	assert_eq(_p.inventory.count_of(&"scrip"), 100 - price)
	assert_eq(_p.inventory.count_of(StringName(item)), 1)
	assert_eq(int((_tm.stock_of(&"waystation_9")[item] as Dictionary)["count"]), before - 1, "off the shelf")
	var sr: Dictionary = Game.execute(&"trade.sell", _args({"item": item}))
	assert_true(bool(sr["ok"]), str(sr))
	assert_eq(_p.inventory.count_of(&"scrip"), 100 - price + _td.sell_price(Content.item(StringName(item))))
	assert_eq(int((_tm.stock_of(&"waystation_9")[item] as Dictionary)["count"]), before, "back on the shelf")
	assert_lt(_p.inventory.count_of(&"scrip"), 100, "the counter keeps its margin")
	# Trusted-only stock stays behind the counter.
	var locked: String = ""
	for k: Variant in _tm.stock_of(&"waystation_9").keys():
		if int((_tm.stock_of(&"waystation_9")[k] as Dictionary)["rep_tier"]) > 0:
			locked = str(k)
	if locked != "":
		_p.inventory.add_item(&"scrip", 900)
		assert_false(bool(Game.execute(&"trade.buy", _args({"item": locked}))["ok"]), "%s needs standing" % locked)
	_p.position = POST + Vector3(300, 0, 0)
	assert_false(bool(Game.execute(&"trade.buy", _args({"item": item}))["ok"]), "only at the post")


func _take(kind: String) -> Dictionary:
	_p.contracts.add_rep(&"waystation_9", 500)
	for day: int in range(1, 40):
		Game.session.clock.total_minutes = float(day - 1) * 1440.0 + 540.0
		for o: Dictionary in _tm.board_offers(_p, _td):
			var qd: QuestDef = Content.get_def(&"quest", StringName(str(o["def"]))) as QuestDef
			if qd.quest_type == kind:
				var r: Dictionary = Game.execute(&"contract.accept", _args({"offer": str(o["id"])}))
				assert_true(bool(r["ok"]), str(r))
				return _p.contracts.get_contract(str(r["contract"]))
	return {}


func _turn_in(c: Dictionary) -> Dictionary:
	var scrip: int = _p.inventory.count_of(&"scrip")
	var rep: int = _p.contracts.reputation(&"waystation_9")
	var xp: int = _p.progression.xp
	var r: Dictionary = Game.execute(&"contract.turn_in", _args({"contract": str(c["id"])}))
	assert_true(bool(r["ok"]), str(r))
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	assert_eq(_p.inventory.count_of(&"scrip"), scrip + int(qd.rewards.get("scrip", 0)), "paid in scrip")
	assert_eq(_p.contracts.reputation(&"waystation_9"), rep + int(qd.rewards.get("reputation", 0)), "standing")
	assert_true(_p.progression.xp > xp or _p.progression.level > 1, "and XP")
	assert_true(_p.contracts.get_contract(str(c["id"])).is_empty(), "off the books")
	return r


func test_a_clear_contract_completes_when_the_building_is_cleared() -> void:
	var c: Dictionary = _take("clear")
	assert_false(c.is_empty(), "the board offered a clear")
	assert_false(bool(Game.execute(&"contract.turn_in", _args({"contract": str(c["id"])}))["ok"]), "not done yet")
	Game.session.world.poi_state(StringName(str(c["target"])))["cleared"] = true
	# Its loot room searched (the event a container in it raises while the player stands in it).
	c["looted"] = true
	Events.poi_cleared.emit(StringName(str(c["target"])))
	assert_eq(str(c["state"]), ContractLog.READY)
	_turn_in(c)
	assert_eq(int(_p.contracts.done.get(str(c["def"]), 0)), 1)


func test_a_clear_waits_for_the_loot_room() -> void:
	var c: Dictionary = _take("clear")
	Game.session.world.poi_state(StringName(str(c["target"])))["cleared"] = true
	Events.poi_cleared.emit(StringName(str(c["target"])))
	assert_eq(str(c["state"]), ContractLog.ACTIVE, "every sleeper down, the stores not searched yet")


func test_a_fetch_contract_completes_when_the_cache_is_carried_out() -> void:
	var c: Dictionary = _take("fetch")
	assert_false(c.is_empty(), "the board offered a fetch")
	# The cache is set down once the building stands (PoiInstance); here it is where the player is.
	c["placed"] = true
	c["cache_at"] = [_p.position.x, _p.position.y, _p.position.z]
	_p.inventory.add_item(&"program_cache", 1)
	Events.item_picked_up.emit(_p.id, &"program_cache", 1)
	assert_eq(str(c["state"]), ContractLog.READY)
	_turn_in(c)
	assert_eq(_p.inventory.count_of(&"program_cache"), 0, "the cache handed over")


func test_a_defend_contract_completes_when_the_cache_is_held() -> void:
	var c: Dictionary = _take("defend")
	assert_false(c.is_empty(), "the board offered a defence")
	assert_true(c.has("spot"))
	var spot := Vector3(float(c["spot"][0]), float(c["spot"][1]), float(c["spot"][2]))
	assert_false(bool(Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})["ok"]), "at the cache only")
	_p.position = spot
	assert_true(bool(Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})["ok"]))
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	var t: float = 0.0
	while t < qd.duration + 1.0:
		_tm._follow_defence(_p, c, 1.0)
		t += 1.0
	assert_eq(str(c["state"]), ContractLog.READY)
	_p.position = POST + Vector3(0, 0, 6)
	_turn_in(c)


func test_walking_off_a_defence_drops_it() -> void:
	var c: Dictionary = _take("defend")
	_p.position = Vector3(float(c["spot"][0]), 0.0, float(c["spot"][2]))
	Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})
	_p.position += Vector3(80, 0, 0)
	for i: int in 12:
		_tm._follow_defence(_p, c, 1.0)
	assert_false(_tm.is_running(str(c["id"])), "the uplink dropped")
	assert_eq(str(c["state"]), ContractLog.ACTIVE, "start it again")


func test_the_board_caps_contracts_and_saves_them() -> void:
	_p.contracts.add_rep(&"waystation_9", 500)
	var taken: int = 0
	for o: Dictionary in _tm.board_offers(_p, _td):
		if bool(Game.execute(&"contract.accept", _args({"offer": str(o["id"])}))["ok"]):
			taken += 1
	assert_eq(taken, mini(_td.max_active, _td.offers_per_day))
	assert_eq(_p.contracts.count_for(&"waystation_9"), taken)
	var again := PlayerState.new()
	again.from_dict(JSON.parse_string(JSON.stringify(_p.to_dict())))
	assert_eq(again.contracts.count_for(&"waystation_9"), taken, "contracts survive a save")
	assert_eq(again.contracts.reputation(&"waystation_9"), 500)


func test_the_safe_zone_keeps_hollowed_out() -> void:
	assert_true(_tm.is_safe(POST + Vector3(10, 0, 10)))
	assert_false(_tm.is_safe(POST + Vector3(_td.safe_radius + 5.0, 0, 0)))
	var ai := FakeAI.new()
	add_child_autofree(ai)
	_world.ai = ai
	var e := Enemy.new()
	e.setup(&"test:guard", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = POST + Vector3(5, 0, 0)
	ai.list.append(e)
	var hp: float = e.health
	_tm._guards(1.0)
	assert_lt(e.health, hp, "the guards fire on a Hollowed inside the wire")
	for i: int in 20:
		_tm._guards(1.0)
	assert_true(e.health <= 0.0 or e.state == Enemy.State.DEAD, "and put it down")


## TD-179: the field lab's Bloom core. The board deals it only to a Trusted player, sends them to
## the tier-5 site even after they have been inside, is done while they carry a core, and is never
## dealt again once turned in.
func test_the_field_lab_contract_brings_in_a_bloom_core() -> void:
	var lab: Dictionary = {"id": "poi:lab", "def": "corvane_field_lab", "name": "the Corvane Field Lab", "tier": 5,
		"kind": "generated", "pos": POST + Vector3(2400, 0, -1800)}
	_tm.buildings_source = func() -> Array:
		return [lab]
	Game.session.world.poi_state(&"poi:lab")["visited"] = true
	var lab_offer := func() -> Dictionary:
		for day: int in range(1, 30):
			Game.session.clock.total_minutes = float(day - 1) * 1440.0 + 540.0
			for o: Dictionary in _tm.board_offers(_p, _td):
				if str(o["def"]) == "fetch_t5":
					return o
		return {}
	_p.contracts.add_rep(&"waystation_9", 100)
	assert_true((lab_offer.call() as Dictionary).is_empty(), "Known isn't trusted with it")
	_p.contracts.add_rep(&"waystation_9", 150)
	var o: Dictionary = lab_offer.call()
	assert_false(o.is_empty(), "a Trusted player is sent to the lab, visited or not")
	assert_eq(str(o["target"]), "poi:lab")
	var r: Dictionary = Game.execute(&"contract.accept", _args({"offer": str(o["id"])}))
	assert_true(bool(r["ok"]), str(r))
	var c: Dictionary = _p.contracts.get_contract(str(r["contract"]))
	_tm._follow(_p, c, 1.0)
	assert_eq(str(c["state"]), ContractLog.ACTIVE)
	assert_false(c.has("placed"), "the vault already holds one: nothing is set down")
	_p.inventory.add_item(&"bloom_core_canister", 1)
	_tm._follow(_p, c, 1.0)
	assert_eq(str(c["state"]), ContractLog.READY, "carrying a core")
	_p.inventory.remove(&"bloom_core_canister", 1)
	_tm._follow(_p, c, 1.0)
	assert_eq(str(c["state"]), ContractLog.ACTIVE, "sold or dropped it: open again")
	_p.inventory.add_item(&"bloom_core_canister", 1)
	_tm._follow(_p, c, 1.0)
	_turn_in(c)
	assert_eq(_p.inventory.count_of(&"bloom_core_canister"), 0, "the core handed over")
	assert_eq(_p.inventory.count_of(&"lab_antifungal_ampoule"), 2)
	assert_true((lab_offer.call() as Dictionary).is_empty(), "a one-off job")


func test_a_defence_never_runs_into_the_hum() -> void:
	# TD-142: no uplink while the Hum is out or when it would come before the hold is done.
	var c: Dictionary = _take("defend")
	var clock: WorldClock = Game.session.clock
	var hd: int = clock.next_horde_day(clock.day())
	clock.set_time(hd, clock.horde_start_hour - 0.2)
	_p.position = Vector3(float(c["spot"][0]), float(c["spot"][1]), float(c["spot"][2]))
	var r: Dictionary = Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})
	assert_false(bool(r["ok"]), "the Hum is minutes off")
	clock.set_time(hd, clock.horde_start_hour + 1.0)
	assert_false(bool(Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})["ok"]), "the Hum is out")
	clock.set_time(hd + 1, 12.0)
	assert_true(bool(Game.execute(&"contract.start_defend", {"player": String(_p.id), "contract": c["id"]})["ok"]), "the next noon is fine")


func test_waves_grow_with_the_gamestage() -> void:
	var qd: QuestDef = Content.get_def(&"quest", &"defend_t1") as QuestDef
	var lo: int = 0
	var hi: int = 0
	for i: int in 20:
		var r1 := RandomNumberGenerator.new()
		r1.seed = i
		lo += TraderManager.wave_count(qd, 0, r1)
		var r2 := RandomNumberGenerator.new()
		r2.seed = i
		hi += TraderManager.wave_count(qd, 60, r2)
	assert_gt(hi, lo)


func test_the_guards_fire_from_their_towers_and_turn_drifters_aside() -> void:
	# TD-143: shots come from the towers, and a Hollowed wandering toward the wire is turned along it.
	var e: Dictionary = _tm.posts["trader:waystation_9"]
	var towers: Array[Vector3] = TraderManager.towers_of(e)
	assert_eq(towers.size(), 2, "Waystation 9's two towers")
	for t: Vector3 in towers:
		assert_gt(t.y, POST.y + 5.0, "on the deck")
		assert_lt(Vector2(t.x - POST.x, t.z - POST.z).length(), _td.safe_radius)
	var gun: Vector3 = _tm._gun_for(e, towers[0] + Vector3(1, -5, 1))
	assert_eq(gun, towers[0], "the nearest tower fires")
	var ai := AIDirector.new()
	add_child_autofree(ai)
	var en: Enemy = ai.spawn(&"hollow", POST + Vector3(_td.safe_radius + 6.0, 0, 0), {"tier": "normal", "authored": true})
	await get_tree().physics_frame
	en.target_pos = POST
	en._set_state(Enemy.State.INVESTIGATE)
	TraderManager._steer_off(en, POST, _td.safe_radius)
	assert_gt(Vector2(en.target_pos.x - POST.x, en.target_pos.z - POST.z).length(), _td.safe_radius, "its goal is outside the wire")


class FakePois:
	extends Node
	var instances: Dictionary = {}


## TD-145: a container standing in the target's loot room counts it searched wherever the player
## reached it from (here the player is back at the post); one outside the loot room does not.
func test_a_loot_room_container_counts_without_standing_in_the_room() -> void:
	var c: Dictionary = _take("clear")
	assert_false(c.is_empty(), "the board offered a clear")
	var target := StringName(str(c["target"]))
	var l: PoiLayout = PoiLayout.compile(Content.get_def(&"poi", _tm._target_def(c)) as PoiDef)
	assert_false(l.loot_room.is_empty(), "%s has a loot room" % l.def.id)
	var inside: String = ""
	var outside: String = ""
	for pr: Dictionary in l.props:
		var at: int = Contracts.prop_in_loot_room(l, str(pr["pkey"]))
		if at == 1 and inside == "":
			inside = str(pr["pkey"])
		elif at == 0 and outside == "":
			outside = str(pr["pkey"])
	assert_ne(inside, "", "a prop in the loot room")
	var inst := PoiInstance.new()
	autofree(inst)
	inst.layout = l
	inst.instance_id = target
	var pois := FakePois.new()
	add_child_autofree(pois)
	pois.instances[target] = inst
	_world.pois = pois
	_p.position = POST + Vector3(0, 0, 6)
	Game.session.world.poi_state(target)["cleared"] = true
	if outside != "":
		Events.container_looted.emit(_p.id, StringName("c:%s:%s" % [target, outside]), 2)
		assert_false(bool(c.get("looted", false)), "a container outside the loot room")
	Events.container_looted.emit(_p.id, StringName("c:%s:%s" % [target, inside]), 2)
	assert_true(bool(c.get("looted", false)), "the loot room's container, searched from anywhere")
	assert_eq(str(c["state"]), ContractLog.READY)


## TD-146: an open contract fails at the dawn of its due day, costs standing and frees its target;
## one done and waiting to be reported does not.
func test_an_open_contract_expires_at_dawn_and_costs_standing() -> void:
	# The run's first lapse is spared (test below): this one tests a later lapse.
	_p.contracts.lapsed = 1
	var c: Dictionary = _take("clear")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	assert_gt(qd.expires_days, 0)
	var due: int = int(c["day"]) + qd.expires_days
	assert_eq(TraderManager.due_day(c), due)
	var rep: int = _p.contracts.reputation(&"waystation_9")
	var clock: WorldClock = Game.session.clock
	clock.set_time(due, clock.sunrise_hour - 0.5)
	_tm.expire_contracts(_p)
	assert_false(_p.contracts.get_contract(str(c["id"])).is_empty(), "still before dawn")
	clock.set_time(due, clock.sunrise_hour + 0.1)
	_tm.expire_contracts(_p)
	assert_true(_p.contracts.get_contract(str(c["id"])).is_empty(), "failed at dawn")
	assert_eq(_p.contracts.reputation(&"waystation_9"), rep - qd.fail_rep, "the Program noticed")
	assert_false(_p.contracts.busy_targets().has(str(c["target"])), "the building is free again")
	# A contract done before its dawn waits to be reported.
	var c2: Dictionary = _take("fetch")
	c2["state"] = ContractLog.READY
	clock.set_time(TraderManager.due_day(c2) + 2, 12.0)
	_tm.expire_contracts(_p)
	assert_false(_p.contracts.get_contract(str(c2["id"])).is_empty(), "done, only not reported")
	# A contract saved before expiry existed has no `due`: it takes it from its def.
	c2.erase("due")
	assert_eq(TraderManager.due_day(c2), int(c2["day"]) + (Content.get_def(&"quest", StringName(str(c2["def"]))) as QuestDef).expires_days)


## First-week audit W12: the first contract a run lets lapse costs no standing (data:
## config/contracts.json spared_lapses), and says so; the next one costs as usual.
func test_a_runs_first_lapsed_contract_is_spared() -> void:
	assert_eq(int(Content.config(&"contracts").get("spared_lapses", 0)), 1)
	var lines: Array[String] = []
	var on_msg := func(text: String, _kind: StringName) -> void: lines.append(text)
	Events.player_status_message.connect(on_msg)
	var clock: WorldClock = Game.session.clock
	var c: Dictionary = _take("clear")
	var rep: int = _p.contracts.reputation(&"waystation_9")
	clock.set_time(TraderManager.due_day(c) + 1, 12.0)
	_tm.expire_contracts(_p)
	assert_true(_p.contracts.get_contract(str(c["id"])).is_empty(), "it still lapses")
	assert_eq(_p.contracts.reputation(&"waystation_9"), rep, "no standing lost the first time")
	assert_eq(_p.contracts.lapsed, 1)
	assert_true(lines.size() > 0 and lines.back().contains("lets it go this once"), str(lines))
	assert_eq(ContractLog.new().lapsed, 0)
	var saved := ContractLog.new()
	saved.from_dict(_p.contracts.to_dict())
	assert_eq(saved.lapsed, 1, "the spared lapse is remembered across a save")
	var c2: Dictionary = _take("clear")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c2["def"]))) as QuestDef
	rep = _p.contracts.reputation(&"waystation_9")
	clock.set_time(TraderManager.due_day(c2) + 1, 12.0)
	_tm.expire_contracts(_p)
	assert_eq(_p.contracts.reputation(&"waystation_9"), rep - qd.fail_rep, "the second lapse costs")
	assert_true(lines.back().contains("-%d standing" % qd.fail_rep), lines.back())
	Events.player_status_message.disconnect(on_msg)


func test_abandoning_a_contract_costs_standing() -> void:
	var c: Dictionary = _take("clear")
	var qd: QuestDef = Content.get_def(&"quest", StringName(str(c["def"]))) as QuestDef
	var rep: int = _p.contracts.reputation(&"waystation_9")
	var r: Dictionary = Game.execute(&"contract.abandon", _args({"contract": str(c["id"])}))
	assert_true(bool(r["ok"]), str(r))
	assert_gt(qd.abandon_rep, 0)
	assert_eq(_p.contracts.reputation(&"waystation_9"), rep - qd.abandon_rep)
	assert_true(_p.contracts.get_contract(str(c["id"])).is_empty())


## TD-146: each relay camp keeps its own shelves (keyed by its post id); Waystation 9 keeps one.
func test_two_relay_posts_keep_separate_stock() -> void:
	var relay: TraderDef = Content.get_def(&"trader", &"program_relay") as TraderDef
	assert_true(relay.stock_per_post)
	assert_false(_td.stock_per_post)
	var a := POST + Vector3(2000, 0, 0)
	var b := POST + Vector3(-2000, 0, 0)
	_tm.add_post("trader:program_relay:1", relay, a, 0.0, false)
	_tm.add_post("trader:program_relay:2", relay, b, 0.0, false)
	var item: String = "water_bottle_clean"
	assert_true(_tm.stock_of(&"program_relay", "trader:program_relay:1").has(item))
	var before_b: int = int((_tm.stock_of(&"program_relay", "trader:program_relay:2")[item] as Dictionary)["count"])
	var before_a: int = int((_tm.stock_of(&"program_relay", "trader:program_relay:1")[item] as Dictionary)["count"])
	_p.position = a + Vector3(0, 0, 6)
	_p.inventory.add_item(&"scrip", 200)
	var r: Dictionary = Game.execute(&"trade.buy", {"player": String(_p.id), "trader": "program_relay", "item": item})
	assert_true(bool(r["ok"]), str(r))
	assert_eq(int((_tm.stock_of(&"program_relay", "trader:program_relay:1")[item] as Dictionary)["count"]), before_a - 1, "off camp 1's shelf")
	assert_eq(int((_tm.stock_of(&"program_relay", "trader:program_relay:2")[item] as Dictionary)["count"]), before_b, "camp 2 untouched")
	var keys: Dictionary = Game.session.world.traders
	assert_true(keys.has("trader:program_relay:1") and keys.has("trader:program_relay:2"))
	assert_false(keys.has("program_relay"), "no def-keyed relay stock")
	_tm.stock_of(&"waystation_9", "trader:waystation_9")
	assert_true(keys.has("waystation_9"), "Waystation 9 keeps its def-keyed stock")


## A save from before per-post stock keyed the relay camps' shelves by the def id: each post
## starts from that entry.
func test_an_old_def_keyed_relay_stock_still_loads() -> void:
	var relay: TraderDef = Content.get_def(&"trader", &"program_relay") as TraderDef
	_tm.add_post("trader:program_relay:1", relay, POST + Vector3(2000, 0, 0), 0.0, false)
	var p: int = Contracts.period(relay, Game.session.clock.day())
	var ws := WorldState.new()
	ws.from_dict(JSON.parse_string(JSON.stringify({"traders": {"program_relay": {"period": p,
		"stock": {"canned_beans": {"count": 42, "rep_tier": 0}}}}})))
	Game.session.world.traders = ws.traders
	var st: Dictionary = _tm.stock_of(&"program_relay", "trader:program_relay:1")
	assert_eq(int((st.get("canned_beans", {"count": 0}) as Dictionary)["count"]), 42, "the old shelves carried over")
	assert_true(Game.session.world.traders.has("trader:program_relay:1"))
