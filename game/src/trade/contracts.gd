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
## the player's active contracts; `done` the player's turned-in contracts by def id (a `once`
## contract done is never dealt again).
static func offers(trader: TraderDef, day: int, world_seed: int, buildings: Array, post_pos: Vector3,
		rep_tier: int, poi_states: Dictionary, busy: Dictionary = {}, done: Dictionary = {}) -> Array[Dictionary]:
	var defs: Array[QuestDef] = []
	for qd: QuestDef in contract_defs(trader, rep_tier):
		if not (qd.once and int(done.get(String(qd.id), 0)) > 0):
			defs.append(qd)
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
## not yet visited or cleared (unless its target isn't `fresh`), not `used`, and (for clear and
## fetch) holding sleepers. Among those the one the
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
		if qd.fresh_only() and (bool(st.get("visited", false)) or bool(st.get("cleared", false))):
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


## Whether the container prop `pkey` of a layout stands in its loot room (TD-145): 1 yes, 0 no,
## -1 when the layout has no such prop. The same test PoiBuilder uses for a loot-room container's
## bonus roll, so it counts the container wherever the player searched it from.
static func prop_in_loot_room(l: PoiLayout, pkey: String) -> int:
	if l == null or l.loot_room.is_empty():
		return -1 if l == null else 0
	for p: Dictionary in l.props:
		if str(p.get("pkey", "")) != pkey:
			continue
		var level: int = int(p.get("level", 0))
		return 1 if level == int(l.loot_room.get("level", 0)) and p.has("cell") \
			and l.room_at(level, p["cell"]) == str(l.loot_room.get("room", "")) else 0
	return -1


## The restock period a day falls in (stock re-rolls when it changes).
static func period(trader: TraderDef, day: int) -> int:
	return maxi(0, day - 1) / trader.restock_days


## The shop's stock for a period: {item id: {count, rep_tier}}. Every tier is rolled; the counter
## shows a player only the tiers their reputation has reached. `key` is the stock's key in
## WorldState.traders: a post id for a def with `stock_per_post` (each camp rolls its own shelves,
## TD-146); the def id (or "") otherwise.
static func roll_stock(trader: TraderDef, p: int, world_seed: int, key: String = "") -> Dictionary:
	var out: Dictionary = {}
	var k: String = String(trader.id) if key == "" or key == String(trader.id) else key
	for i: int in trader.stock.size():
		var e: Dictionary = trader.stock[i]
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("stock:%d:%s:%d:%d" % [world_seed, k, p, i])
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


## Where a fetch contract's cache is set down in a building (TD-144), in the layout's local frame:
## {level, pos: Vector3 (on the floor), authored: bool}, or {} when the building has no floor to
## put it on. An authored spot wins: `loot_room.cache: [x, z]` (footprint metres, on the loot
## room's level). Otherwise a free floor cell of the loot room (any room when it has none) that the
## seed key picks: one no prop stands on (by its def's size and turn), and no stair, ladder, hole,
## trap, sleeper or pickup takes, so the cache never lands on a shelf or between two of them.
static func cache_spot(l: PoiLayout, key: String) -> Dictionary:
	var level: int = int(l.loot_room.get("level", 0)) if not l.loot_room.is_empty() else 0
	var authored: Array = l.loot_room.get("cache", [])
	if authored.size() == 2:
		return {"level": level, "pos": l.local_pos(level, Vector2(float(authored[0]), float(authored[1]))), "authored": true}
	var room: String = str(l.loot_room.get("room", ""))
	var taken: Dictionary = taken_cells(l, level)
	var free: Array[Vector2i] = []
	var any: Array[Vector2i] = []
	for cell: Vector2i in l.room_cells(level):
		if room != "" and l.room_at(level, cell) != room:
			continue
		any.append(cell)
		if not taken.has(cell):
			free.append(cell)
	var pool: Array[Vector2i] = free if not free.is_empty() else any
	if pool.is_empty():
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("cache:%s" % key)
	return {"level": level, "pos": l.cell_center(level, pool[rng.randi() % pool.size()]), "authored": false}


## Cells of a level something already stands in: props (their def's footprint, turned), stairs,
## ladders, holes, traps, sleepers and pickups. Wall-mounted props and props without collision
## leave the floor free.
static func taken_cells(l: PoiLayout, level: int) -> Dictionary:
	var out: Dictionary = {}
	for p: Dictionary in l.props:
		if int(p.get("level", 0)) != level:
			continue
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd != null and (pd.wall_mounted or pd.collision == "none"):
			continue
		var size: Vector3 = pd.size if pd != null else Vector3.ONE
		var pos: Vector2 = p["pos"]
		var a: float = deg_to_rad(float(p.get("rot", 0.0)))
		# The turned footprint's extent (half width along x and z), less a margin so a prop
		# flush to a cell edge doesn't claim its neighbour.
		var hx: float = absf(cos(a)) * size.x * 0.5 + absf(sin(a)) * size.z * 0.5 - 0.05
		var hz: float = absf(sin(a)) * size.x * 0.5 + absf(cos(a)) * size.z * 0.5 - 0.05
		for z: int in range(int(floor(pos.y - hz)), int(floor(pos.y + hz)) + 1):
			for x: int in range(int(floor(pos.x - hx)), int(floor(pos.x + hx)) + 1):
				out[Vector2i(x, z)] = true
	for s: Dictionary in l.stairs:
		if int(s["level"]) == level or int(s["level"]) + 1 == level:
			for c: Vector2i in s["cells"]:
				out[c] = true
	for ld: Dictionary in l.ladders:
		if int(ld["level"]) == level or int(ld["level"]) + 1 == level:
			out[ld["cell"]] = true
	for t: Dictionary in l.traps:
		if int(t.get("level", 0)) == level:
			for c2: Vector2i in t.get("cells", [t["cell"]]):
				out[c2] = true
	for list: Array in [l.sleepers, l.pickups, l.holes]:
		for d: Variant in list:
			var dd: Dictionary = d
			if int(dd.get("level", 0)) == level and dd.has("cell"):
				out[dd["cell"]] = true
	return out
