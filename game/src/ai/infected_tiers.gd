class_name InfectedTiers
extends RefCounted
## Infected tiers (normal / Seeded / Bloomed): stat multipliers per tier and the gamestage
## brackets that decide how often each appears (data/config/infected_tiers.json, ADR-0014).


static func cfg() -> Dictionary:
	return Content.config(&"infected_tiers")


## Multipliers and extras for a tier id (falls back to normal).
static func tier(id: StringName) -> Dictionary:
	var tiers: Dictionary = cfg().get("tiers", {})
	return tiers.get(String(id), tiers.get("normal", {}))


## The weighted bracket for a gamestage: the last entry whose gs <= gamestage.
static func bracket(gamestage: int) -> Dictionary:
	var best: Dictionary = {"pick": {"normal": 1.0}}
	for b: Variant in cfg().get("by_gamestage", []):
		if int((b as Dictionary).get("gs", 0)) <= gamestage:
			best = b
	return best.get("pick", {"normal": 1.0})


## Rolls a tier for a spawn at this gamestage (always normal when the world setting is off).
static func pick(gamestage: int, rng: RandomNumberGenerator) -> StringName:
	if not GameRules.current().flag("infected_tiers"):
		return &"normal"
	var pick: Dictionary = bracket(gamestage)
	var total: float = 0.0
	for k: String in pick:
		total += float(pick[k])
	var r: float = rng.randf() * total
	for k: String in pick:
		r -= float(pick[k])
		if r <= 0.0:
			return StringName(k)
	return &"normal"
