class_name LootRoller
extends RefCounted
## Rolls loot tables deterministically given an RNG. Loot scales with:
##  - container/POI tier (1..5): fewer empty containers, more rolls, better quality;
##  - gamestage (player progression/days survived): higher quality ceiling;
##  - entry tier gates (tier_min/tier_max) for rare items.
## Tuning lives in data/config/loot.json.

const MAX_DEPTH: int = 6


class Context:
	var tier: int = 1
	var gamestage: int = 1
	var biome: StringName = &""
	var rng: RandomNumberGenerator

	func _init(p_tier: int = 1, p_gamestage: int = 1, p_rng: RandomNumberGenerator = null) -> void:
		tier = clampi(p_tier, 1, 5)
		gamestage = maxi(1, p_gamestage)
		rng = p_rng if p_rng != null else RandomNumberGenerator.new()


static func roll(table_id: StringName, ctx: Context) -> Array[ItemStack]:
	var out: Array[ItemStack] = []
	_roll_into(table_id, ctx, out, 0, true)
	return _merge(out)


static func _roll_into(table_id: StringName, ctx: Context, out: Array[ItemStack], depth: int, top: bool) -> void:
	if depth > MAX_DEPTH:
		push_warning("LootRoller: max depth at %s" % table_id)
		return
	var t: LootTableDef = Content.loot_table(table_id)
	if t == null:
		push_warning("LootRoller: unknown table %s" % table_id)
		return
	var cfg: Dictionary = Content.config(&"loot")
	if top:
		var empty_reduction: float = float(cfg.get("empty_reduction_per_tier", 0.05)) * float(ctx.tier - 1)
		if ctx.rng.randf() < maxf(0.0, t.empty_chance - empty_reduction):
			return
	for g: Dictionary in t.guaranteed:
		var n: int = Weighted.randi_range_v(g["count"], ctx.rng)
		if n > 0:
			out.append(ItemStack.make(g["item"], n, _quality(g["item"], ctx, 0)))
	var rolls: int = Weighted.randi_range_v(t.rolls, ctx.rng)
	if top:
		rolls += int(floor(float(ctx.tier - 1) * float(cfg.get("extra_rolls_per_tier", 0.34))))
	var eligible: Array[Dictionary] = []
	var weights := PackedFloat32Array()
	for e: Dictionary in t.entries:
		if ctx.tier < int(e["tier_min"]) or ctx.tier > int(e["tier_max"]):
			continue
		eligible.append(e)
		weights.append(float(e["weight"]))
	if eligible.is_empty():
		return
	for i: int in rolls:
		var idx: int = Weighted.pick_index(weights, ctx.rng)
		if idx < 0:
			break
		var e: Dictionary = eligible[idx]
		if e["table"] != &"":
			_roll_into(e["table"], ctx, out, depth + 1, false)
		else:
			var n: int = Weighted.randi_range_v(e["count"], ctx.rng)
			if n > 0:
				out.append(ItemStack.make(e["item"], n, _quality(e["item"], ctx, int(e["quality_bias"]))))


## Quality 1..6 for quality items; 0 otherwise. Distribution centre rises with tier & gamestage.
static func _quality(item_id: StringName, ctx: Context, bias: int) -> int:
	var d: ItemDef = Content.item(item_id)
	if d == null or not d.has_quality:
		return 0
	var cfg: Dictionary = Content.config(&"loot")
	var centre: float = 1.0 + float(ctx.tier - 1) * float(cfg.get("quality_per_tier", 0.6)) \
		+ float(ctx.gamestage) * float(cfg.get("quality_per_gamestage", 0.02)) + float(bias)
	var spread: float = float(cfg.get("quality_spread", 0.9))
	var q: float = centre + ctx.rng.randfn(0.0, spread)
	var cap: int = clampi(2 + ctx.tier + int(ctx.gamestage / 20), 2, 6)
	return clampi(int(round(q)), 1, cap)


## Merges identical stackable results so containers do not show "nails x2, nails x3".
static func _merge(stacks: Array[ItemStack]) -> Array[ItemStack]:
	var out: Array[ItemStack] = []
	for s: ItemStack in stacks:
		var merged: bool = false
		for o: ItemStack in out:
			if o.can_merge(s) and o.count + s.count <= o.max_stack():
				o.count += s.count
				merged = true
				break
		if not merged:
			out.append(s)
	return out
