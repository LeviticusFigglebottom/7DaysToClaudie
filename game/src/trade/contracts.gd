class_name Contracts
extends RefCounted
## The deterministic half of trading (ADR-0039): what a trader's board offers on a day, which
## building each offer sends the player to, and what the shop stocks in a restock period. All of
## it follows the world seed, the trader, the day (or period) and the slot, so two players of one
## world see the same board, and a reload changes nothing. TraderManager does the live half.

## def id -> sleepers in its compiled layout (a building with none can never be cleared).
static var _sleeper_counts: Dictionary = {}
## def id -> whether its layout has a loot room.
static var _loot_rooms: Dictionary = {}


## Board offers of `trader` on `day`: [{id, def, target, name, pos: [3], tier, day}]. `buildings`
## is PoiManager.all_buildings(); `poi_states` WorldState.pois (visited or cleared buildings are
## never offered); `rep_tier` caps the contracts dealt; `busy` holds building ids already taken by
## the player's active contracts.
static func offers(trader: TraderDef, day: int, world_seed: int, buildings: Array, post_pos: Vector3,
		rep_tier: int, poi_states: Dictionary, busy: Dictionary = {}) -> Array[Dictionary]:
	var defs: Array[QuestDef] = contract_defs(trader, rep_tier)
	var out: Array[Dictionary] = []
	if defs.is_empty():
		return out
	var used: Dictionary = busy.duplicate()
	for slot: int in trader.offers_per_day:
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("offer:%d:%s:%d:%d" % [world_seed, trader.id, day, slot])
		# A def with no building left to send the player to gives its slot to another.
		for attempt: int in 4:
			var qd: QuestDef = _weighted(defs, rng)
			var b: Dictionary = pick_target(qd, buildings, post_pos, poi_states, used,
				"%d:%s:%d:%d" % [world_seed, trader.id, day, slot])
			if b.is_empty():
				continue
			used[str(b["id"])] = true
			var p: Vector3 = b["pos"]
			out.append({"id": "o:%s:%d:%d" % [trader.id, day, slot], "def": String(qd.id), "target": str(b["id"]),
				"name": str(b.get("name", "")), "pos": [p.x, p.y, p.z], "tier": int(b.get("tier", 1)), "day": day})
			break
	return out


## The trader's contract templates a reputation tier unlocks, sorted by id.
static func contract_defs(trader: TraderDef, rep_tier: int) -> Array[QuestDef]:
	var out: Array[QuestDef] = []
	for d: ContentDef in Content.all(&"quest"):
		var qd: QuestDef = d as QuestDef
		if qd.is_contract() and trader.contracts_from.has(qd.giver) and qd.rep_tier <= rep_tier:
			out.append(qd)
	return out


static func _weighted(defs: Array[QuestDef], rng: RandomNumberGenerator) -> QuestDef:
	var total: float = 0.0
	for qd: QuestDef in defs:
		total += maxf(0.0, qd.weight)
	var r: float = rng.randf() * total
	for qd: QuestDef in defs:
		r -= maxf(0.0, qd.weight)
		if r <= 0.0:
			return qd
	return defs[defs.size() - 1]


## The building an offer of `qd` sends the player to: in its tier and distance bands, of its kind,
## not yet visited or cleared, not `used`, and (for clear) holding sleepers. Among those the one the
## seed key ranks first, so the pick does not depend on the order buildings were placed in.
static func pick_target(qd: QuestDef, buildings: Array, post_pos: Vector3, poi_states: Dictionary,
		used: Dictionary, key: String) -> Dictionary:
	var tb: Vector2i = qd.tier_band()
	var db: Vector2 = qd.distance_band()
	var kind: String = str(qd.target.get("kind", "any"))
	var best: Dictionary = {}
	var best_rank: int = 0
	for v: Variant in buildings:
		var b: Dictionary = v
		var bid: String = str(b.get("id", ""))
		var t: int = int(b.get("tier", 1))
		if used.has(bid) or t < tb.x or t > tb.y:
			continue
		if kind != "any" and str(b.get("kind", "")) != kind:
			continue
		var p: Vector3 = b.get("pos", Vector3.ZERO)
		var dist: float = Vector2(p.x - post_pos.x, p.z - post_pos.z).length()
		if dist < db.x or dist > db.y:
			continue
		var st: Dictionary = poi_states.get(bid, {})
		if bool(st.get("visited", false)) or bool(st.get("cleared", false)):
			continue
		if qd.quest_type != "defend" and sleepers_of(StringName(str(b.get("def", "")))) == 0:
			continue
		var rank: int = Ids.hash64("target:%s:%s:%s" % [key, qd.id, bid])
		if best.is_empty() or rank < best_rank:
			best = b
			best_rank = rank
	return best


static func sleepers_of(def_id: StringName) -> int:
	if not _sleeper_counts.has(def_id):
		var pd: PoiDef = Content.get_def(&"poi", def_id) as PoiDef
		var n: int = 0
		var lr: bool = false
		if pd != null:
			var l: PoiLayout = PoiLayout.compile(pd)
			n = l.sleepers.size()
			lr = not l.loot_room.is_empty()
		_sleeper_counts[def_id] = n
		_loot_rooms[def_id] = lr
	return int(_sleeper_counts[def_id])


## Whether clearing `def_id` also means searching its loot room.
static func has_loot_room(def_id: StringName) -> bool:
	sleepers_of(def_id)
	return bool(_loot_rooms.get(def_id, false))


## The restock period a day falls in (stock re-rolls when it changes).
static func period(trader: TraderDef, day: int) -> int:
	return maxi(0, day - 1) / trader.restock_days


## The shop's stock for a period: {item id: {count, rep_tier}}. Every tier is rolled; the counter
## shows a player only the tiers their reputation has reached.
static func roll_stock(trader: TraderDef, p: int, world_seed: int) -> Dictionary:
	var out: Dictionary = {}
	for i: int in trader.stock.size():
		var e: Dictionary = trader.stock[i]
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("stock:%d:%s:%d:%d" % [world_seed, trader.id, p, i])
		if rng.randf() > float(e.get("chance", 1.0)):
			continue
		var c: Array = e.get("count", [1, 1])
		var n: int = rng.randi_range(int(c[0]), int(c[c.size() - 1]))
		if n <= 0:
			continue
		var item: String = str(e["item"])
		var prev: Dictionary = out.get(item, {"count": 0, "rep_tier": int(e.get("rep_tier", 0))})
		out[item] = {"count": int(prev["count"]) + n, "rep_tier": mini(int(prev["rep_tier"]), int(e.get("rep_tier", 0)))}
	return out


## Fills `{building}` and `{distance}` in a contract's briefing.
static func briefing(qd: QuestDef, offer: Dictionary, post_pos: Vector3) -> String:
	var p: Array = offer.get("pos", [0, 0, 0])
	var d: float = Vector2(float(p[0]) - post_pos.x, float(p[2]) - post_pos.z).length()
	var text: String = qd.briefing if qd.briefing != "" else qd.description
	return text.replace("{building}", str(offer.get("name", "the building"))).replace("{distance}",
		"%.1f km" % (d / 1000.0) if d >= 1000.0 else "%d m" % int(round(d / 10.0) * 10.0))


## A point to hold for a defend contract: `dist` metres from a building, on a bearing the seed key
## picks, where `ok` (Callable(Vector3) -> bool) accepts it. Falls back to the building itself.
static func defend_spot(building_pos: Vector3, key: String, ok: Callable, dist: Vector2 = Vector2(16.0, 26.0)) -> Vector3:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("defend:%s" % key)
	for attempt: int in 24:
		var ang: float = rng.randf() * TAU
		var r: float = rng.randf_range(dist.x, dist.y)
		var p := Vector3(building_pos.x + cos(ang) * r, building_pos.y, building_pos.z + sin(ang) * r)
		if ok.call(p):
			return p
	return building_pos
