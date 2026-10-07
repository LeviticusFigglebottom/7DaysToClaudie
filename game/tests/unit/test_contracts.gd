extends GutTest
## Waystation trading (ADR-0039), the deterministic half: the board deals the same offers for the
## same world, day and standing; each sends the player to a fitting building; the shop's stock
## follows the restock period; prices follow item value and standing; and the player's contract
## log survives a save.

const POST := Vector3(0, 0, 0)

var _td: TraderDef


func before_each() -> void:
	_td = Content.get_def(&"trader", &"waystation_9") as TraderDef


func _buildings() -> Array:
	var out: Array = []
	var defs: Array = [["water_works", 2], ["ridgeline_quarry_office", 2], ["vfw_post", 2], ["northfork_cannery", 3],
		["hollis_pawn_gun", 3], ["suds_spin_laundromat", 1], ["hollowmere_grocery", 2]]
	for i: int in 24:
		var d: Array = defs[i % defs.size()]
		var ang: float = float(i) * 0.7
		var r: float = 180.0 + float(i) * 55.0
		out.append({"id": "poi:%d" % i, "def": d[0], "name": "Building %d" % i, "tier": int(d[1]), "kind": "authored",
			"pos": Vector3(cos(ang) * r, 0.0, sin(ang) * r)})
	return out


func test_waystation_9_and_its_contracts_load() -> void:
	assert_not_null(_td)
	assert_gt(_td.stock.size(), 10, "a stocked shop")
	assert_eq(_td.rep_tiers.size(), 4)
	var kinds: Dictionary = {}
	for qd: QuestDef in Contracts.contract_defs(_td, 9):
		kinds[qd.quest_type] = true
	assert_eq(kinds.keys().size(), 3, "clear, fetch and defend contracts: %s" % [kinds.keys()])
	for e: String in Content.errors():
		assert_false(e.contains("traders/") or e.contains("quests/"), e)


func test_the_board_is_the_same_for_the_same_world_and_day() -> void:
	var b: Array = _buildings()
	var a1: Array[Dictionary] = Contracts.offers(_td, 3, 4471, b, POST, 0, {})
	var a2: Array[Dictionary] = Contracts.offers(_td, 3, 4471, b, POST, 0, {})
	assert_eq(a1.size(), _td.offers_per_day, "a full board")
	assert_eq(a1, a2, "deterministic")
	var shuffled: Array = b.duplicate()
	shuffled.reverse()
	assert_eq(Contracts.offers(_td, 3, 4471, shuffled, POST, 0, {}), a1, "not the order buildings were placed in")
	var other_days: int = 0
	for day: int in [4, 5, 6]:
		if Contracts.offers(_td, day, 4471, b, POST, 0, {}) != a1:
			other_days += 1
	assert_gt(other_days, 0, "a new board on other days")
	assert_ne(Contracts.offers(_td, 3, 9, b, POST, 0, {}), a1, "and in another world")


func test_offers_fit_their_bands_and_skip_visited_and_busy_buildings() -> void:
	var b: Array = _buildings()
	for day: int in range(1, 12):
		var offers: Array[Dictionary] = Contracts.offers(_td, day, 77, b, POST, 3, {"poi:0": {"visited": true}, "poi:1": {"cleared": true}},
			{"poi:2": true})
		var seen: Dictionary = {}
		for o: Dictionary in offers:
			var qd: QuestDef = Content.get_def(&"quest", StringName(str(o["def"]))) as QuestDef
			assert_true(qd.is_contract())
			assert_false(str(o["target"]) in ["poi:0", "poi:1", "poi:2"], "visited, cleared or busy: %s" % o["target"])
			assert_false(seen.has(o["target"]), "one offer per building")
			seen[o["target"]] = true
			var tb: Vector2i = qd.tier_band()
			assert_true(int(o["tier"]) >= tb.x and int(o["tier"]) <= tb.y, "%s tier %d in %s" % [qd.id, o["tier"], tb])
			var p: Array = o["pos"]
			var dist: float = Vector2(float(p[0]), float(p[2])).length()
			var db: Vector2 = qd.distance_band()
			assert_true(dist >= db.x and dist <= db.y, "%s at %.0f m in %s" % [qd.id, dist, db])


func test_standing_unlocks_harder_contracts() -> void:
	var low: Dictionary = {}
	var high: Dictionary = {}
	for qd: QuestDef in Contracts.contract_defs(_td, 0):
		low[qd.id] = true
	for qd2: QuestDef in Contracts.contract_defs(_td, 3):
		high[qd2.id] = true
	assert_gt(high.size(), low.size())
	assert_false(low.has(&"clear_t3"), "the hard clears wait for standing")
	assert_true(high.has(&"clear_t3"))


func test_stock_follows_the_restock_period() -> void:
	var s1: Dictionary = Contracts.roll_stock(_td, 0, 4471)
	assert_eq(Contracts.roll_stock(_td, 0, 4471), s1, "deterministic")
	assert_gt(s1.size(), 5)
	assert_eq(Contracts.period(_td, 1), Contracts.period(_td, _td.restock_days), "one period")
	assert_eq(Contracts.period(_td, _td.restock_days + 1), 1, "then the next")
	var changed: bool = false
	for p: int in range(1, 5):
		changed = changed or Contracts.roll_stock(_td, p, 4471) != s1
	assert_true(changed, "a restock changes the shelves")
	for item: Variant in s1.keys():
		assert_gt(int((s1[item] as Dictionary)["count"]), 0)


func test_relay_camps_roll_their_own_shelves() -> void:
	# TD-146: a def with stock_per_post rolls each post's shelves from its post id.
	var relay: TraderDef = Content.get_def(&"trader", &"program_relay") as TraderDef
	assert_true(relay.stock_per_post)
	assert_eq(TraderManager.stock_key(relay, "trader:program_relay:3"), "trader:program_relay:3")
	assert_eq(TraderManager.stock_key(_td, "trader:waystation_9"), "waystation_9", "one shop for a unique post")
	assert_eq(Contracts.roll_stock(relay, 0, 4471, "program_relay"), Contracts.roll_stock(relay, 0, 4471), "the def key is the old roll")
	var differs: bool = false
	for p: int in 4:
		differs = differs or Contracts.roll_stock(relay, p, 4471, "trader:program_relay:1") != Contracts.roll_stock(relay, p, 4471, "trader:program_relay:2")
	assert_true(differs, "two camps, two sets of shelves")


func test_contracts_expire_and_cost_standing_by_default() -> void:
	# TD-146: every board contract has a deadline and a price for failing or dropping it.
	for qd: QuestDef in Contracts.contract_defs(_td, 3):
		assert_true(qd.expires_days > 0, "%s expires" % qd.id)
		assert_gt(qd.fail_rep, 0)
		assert_gt(qd.abandon_rep, 0)
		assert_true(qd.abandon_rep <= qd.fail_rep, "%s: dropping a job costs less than failing it" % qd.id)
	var t5: QuestDef = Content.get_def(&"quest", &"fetch_t5") as QuestDef
	assert_eq(t5.expires_days, 7, "a week for the far lab")


func test_a_loot_room_prop_is_found_by_its_key() -> void:
	# TD-145: the container id's prop key places it in or out of the loot room.
	var l: PoiLayout = PoiLayout.compile(Content.get_def(&"poi", &"water_works") as PoiDef)
	var seen: Dictionary = {}
	for pr: Dictionary in l.props:
		seen[Contracts.prop_in_loot_room(l, str(pr["pkey"]))] = true
	assert_true(seen.has(1), "some prop stands in the loot room")
	assert_true(seen.has(0), "some does not")
	assert_eq(Contracts.prop_in_loot_room(l, "no_such_prop"), -1)
	assert_eq(Contracts.prop_in_loot_room(null, "0"), -1)


func test_prices_follow_value_and_standing() -> void:
	var pk: ItemDef = Content.item(&"first_aid_kit")
	assert_eq(_td.buy_price(pk, 0), ceili(pk.value * _td.buy_markup))
	assert_lt(_td.buy_price(pk, 3), _td.buy_price(pk, 0), "standing earns a discount")
	assert_eq(_td.sell_price(pk), floori(pk.value * _td.sell_ratio))
	assert_lt(_td.sell_price(pk), _td.buy_price(pk, 3), "no buying low and selling high at one counter")
	assert_eq(_td.sell_price(Content.item(&"scrip")), 0, "scrip isn't bought with scrip")
	assert_eq(_td.sell_price(Content.item(&"program_cache")), 0, "nor the Program's own caches")
	assert_eq(_td.rep_tier(0), 0)
	assert_eq(_td.rep_tier(60), 1)
	assert_eq(_td.rep_tier(10000), 3)


func test_briefing_names_the_building_and_distance() -> void:
	var qd: QuestDef = Content.get_def(&"quest", &"clear_t1") as QuestDef
	var text: String = Contracts.briefing(qd, {"name": "the Water Works", "pos": [0.0, 0.0, 1240.0]}, POST)
	assert_true(text.contains("the Water Works"), text)
	assert_true(text.contains("1.2 km"), text)


func test_contract_log_round_trips() -> void:
	var log := ContractLog.new()
	log.add_rep(&"waystation_9", 75)
	log.active.append({"id": "k:1", "def": "defend_t1", "giver": "waystation_9", "state": ContractLog.ACTIVE, "running": true})
	log.mark_taken("o:3:1", 3)
	log.done["clear_t1"] = 2
	var again := ContractLog.new()
	again.from_dict(JSON.parse_string(JSON.stringify(log.to_dict())))
	assert_eq(again.reputation(&"waystation_9"), 75)
	assert_true(again.has_taken("o:3:1", 3))
	assert_false(again.has_taken("o:3:1", 4), "offers repeat on other days")
	assert_eq(again.total_done(), 2)
	assert_false((again.active[0] as Dictionary).has("running"), "a defence starts over after a load")


func test_old_saves_load_with_no_trading() -> void:
	# Trading adds keys only, with no save bump (v7 is session 3's world bundle). A save without
	# them loads empty: unknown to the Program, nothing on the books, the shelves rolled fresh.
	var ws := WorldState.new()
	ws.from_dict({"structures": {}})
	assert_eq(ws.traders, {})
	var p := PlayerState.new()
	p.from_dict({"id": "p:1"})
	assert_eq(p.contracts.active.size(), 0)
	assert_eq(p.contracts.reputation(&"waystation_9"), 0)


func test_a_tier_five_site_has_a_contract() -> void:
	# TD-179: some contract the board deals targets tier 5, so the field lab is on it.
	var found: bool = false
	for qd: QuestDef in Contracts.contract_defs(_td, 3):
		if qd.tier_band().y >= 5:
			found = true
			assert_false(qd.place, "%s: the site's payoff is already there" % qd.id)
			assert_true(qd.once)
			assert_gt(int(qd.rewards.get("scrip", 0)), _td.sell_price(Content.item(StringName(qd.item))), "pays over the sale price")
	assert_true(found)


func test_a_fetch_cache_lands_on_free_floor_in_the_loot_room() -> void:
	# TD-144: never on a shelf or between props: a loot-room cell nothing stands in.
	var checked: int = 0
	for def_id: StringName in [&"water_works", &"hollis_pawn_gun", &"northfork_cannery", &"vfw_post"]:
		var pd: PoiDef = Content.get_def(&"poi", def_id) as PoiDef
		if pd == null:
			continue
		var l: PoiLayout = PoiLayout.compile(pd)
		var lr_level: int = int(l.loot_room.get("level", 0))
		var taken: Dictionary = Contracts.taken_cells(l, lr_level)
		for k: int in 6:
			var spot: Dictionary = Contracts.cache_spot(l, "test:%d" % k)
			assert_false(spot.is_empty(), String(def_id))
			assert_eq(spot, Contracts.cache_spot(l, "test:%d" % k), "deterministic")
			var pos: Vector3 = spot["pos"]
			var cell := Vector2i(int(floor(pos.x - l.origin.x)), int(floor(pos.z - l.origin.y)))
			assert_eq(l.room_at(lr_level, cell), str(l.loot_room.get("room", "")), "%s: in the loot room" % def_id)
			assert_false(taken.has(cell), "%s: %s is free floor" % [def_id, cell])
		checked += 1
	assert_gt(checked, 2)


func test_an_authored_cache_spot_wins() -> void:
	var l: PoiLayout = PoiLayout.compile(Content.get_def(&"poi", &"water_works") as PoiDef)
	var lr: Dictionary = l.loot_room.duplicate()
	var cell: Vector2i = Vector2i.ZERO
	for c: Vector2i in l.room_cells(int(lr.get("level", 0))):
		if l.room_at(int(lr.get("level", 0)), c) == str(lr.get("room", "")):
			cell = c
	lr["cache"] = [cell.x + 0.5, cell.y + 0.5]
	l.loot_room = lr
	var spot: Dictionary = Contracts.cache_spot(l, "any")
	assert_true(bool(spot["authored"]))
	assert_almost_eq((spot["pos"] as Vector3).x, l.origin.x + cell.x + 0.5, 0.001)
