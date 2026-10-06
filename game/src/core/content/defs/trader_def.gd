class_name TraderDef
extends ContentDef
## A Remand Program trader post (ADR-0039): where it stands (a region `spawn` feature named
## `trader:<id>`), how it is dressed, the safe zone around it, its shop (stock, restocks, prices)
## and its contracts board (contract defs whose `giver` is this trader). Reputation is per player
## and per trader; its tiers unlock stock and harder contracts.

## Region spawn feature that places the post (default "trader:<id>").
var spawn: String = ""
## Metres around the post where no Hollowed spawn and the guards shoot any that walk in.
var safe_radius: float = 40.0
## Guard fire per second against a Hollowed inside the safe zone.
var guard_dps: float = 60.0
## The quartermaster: {model, offset: [x, y, z] from the post origin, yaw}.
var quartermaster: Dictionary = {}
## Set dressing: [{prop, offset: [x, z], rot, y?, variant?}], post-local (+Z faces the road).
var props: Array = []
## The trade counter and the contracts board: {prop, offset: [x, z], rot}; both interactable.
var counter: Dictionary = {}
var board: Dictionary = {}
## Days between restocks (stock re-rolls at dawn on those days).
var restock_days: int = 3
## Buy price = ceil(value * buy_markup * (1 - rep_discount * rep tier)).
var buy_markup: float = 2.0
var rep_discount: float = 0.05
## Sell price = floor(value * sell_ratio) (at least 1 for anything worth something).
var sell_ratio: float = 0.4
## Item categories the post never buys.
var no_buy: PackedStringArray = ["key", "quest", "note"]
## [{name, at}] in rising order: reputation needed for each tier (the first is 0).
var rep_tiers: Array = []
## [{item, count: [lo, hi], rep_tier, chance}]
var stock: Array = []
## Whose contracts its board posts (contract defs by `giver`; default: its own).
var contracts_from: PackedStringArray = []
var offers_per_day: int = 4
var max_active: int = 3


func _fields() -> PackedStringArray:
	return ["spawn", "safe_radius", "guard_dps", "quartermaster", "props", "counter", "board", "restock_days",
		"buy_markup", "rep_discount", "sell_ratio", "no_buy", "rep_tiers", "stock", "contracts_from", "offers_per_day", "max_active"]


func _parse(r: DefReader) -> void:
	spawn = r.str_field("spawn", "trader:%s" % id)
	safe_radius = r.num("safe_radius", 40.0)
	guard_dps = r.num("guard_dps", 60.0)
	quartermaster = r.dict("quartermaster")
	props = r.arr("props")
	counter = r.dict("counter")
	board = r.dict("board")
	restock_days = maxi(1, r.integer("restock_days", 3))
	buy_markup = r.num("buy_markup", 2.0)
	rep_discount = r.num("rep_discount", 0.05)
	sell_ratio = r.num("sell_ratio", 0.4)
	if r.has("no_buy"):
		no_buy = r.strings("no_buy")
	rep_tiers = r.arr("rep_tiers")
	if rep_tiers.is_empty():
		rep_tiers = [{"name": "Known", "at": 0}]
	stock = r.arr("stock")
	contracts_from = r.strings("contracts_from") if r.has("contracts_from") else PackedStringArray([String(id)])
	offers_per_day = maxi(1, r.integer("offers_per_day", 4))
	max_active = maxi(1, r.integer("max_active", 3))


func _validate(db: Node, out: PackedStringArray) -> void:
	for e: Variant in stock:
		var item := StringName(str((e as Dictionary).get("item", "")))
		if not db.has_def(&"item", item):
			out.append("%s: stock item '%s' unknown" % [ctx(), item])
		elif (db.get_def(&"item", item) as ItemDef).value <= 0:
			out.append("%s: stock item '%s' has no value to price it by" % [ctx(), item])
	var seen: Dictionary = {}
	for p: Variant in props + [counter, board]:
		var pid := StringName(str((p as Dictionary).get("prop", "")))
		if pid != &"" and not seen.has(pid) and not db.has_def(&"prop", pid):
			out.append("%s: prop '%s' unknown" % [ctx(), pid])
		seen[pid] = true
	for g: String in contracts_from:
		if not db.has_def(&"trader", StringName(g)):
			out.append("%s: contracts_from '%s' is not a trader" % [ctx(), g])
	var last: int = -1
	for t: Variant in rep_tiers:
		var at: int = int((t as Dictionary).get("at", 0))
		if at <= last:
			out.append("%s: rep_tiers must rise" % ctx())
		last = at


## The reputation tier (index into rep_tiers) a reputation score reaches.
func rep_tier(rep: int) -> int:
	var t: int = 0
	for i: int in rep_tiers.size():
		if rep >= int((rep_tiers[i] as Dictionary).get("at", 0)):
			t = i
	return t


func rep_tier_name(tier: int) -> String:
	return str((rep_tiers[clampi(tier, 0, rep_tiers.size() - 1)] as Dictionary).get("name", ""))


## What the post asks for one `item` at a reputation tier.
func buy_price(item: ItemDef, tier: int) -> int:
	return maxi(1, ceili(float(item.value) * buy_markup * maxf(0.5, 1.0 - rep_discount * float(tier))))


## What the post pays for one `item`, or 0 when it won't take it.
func sell_price(item: ItemDef) -> int:
	if item.value <= 0 or no_buy.has(item.category) or item.id == &"scrip":
		return 0
	return maxi(1, floori(float(item.value) * sell_ratio))
