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
