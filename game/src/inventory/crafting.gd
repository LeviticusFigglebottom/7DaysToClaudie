class_name Crafting
extends RefCounted
## Crafting rules (pure functions over Inventory + content). Used by the salvage-roll UI (hand
## recipes matched from items laid on the work slate) and by station menus.

## Result of a craft attempt.
class Result:
	var ok: bool = false
	var reason: String = ""
	var stack: ItemStack = null

	static func fail(why: String) -> Result:
		var r := Result.new()
		r.reason = why
		return r


## Finds the hand/station recipe whose ingredients exactly equal the items on the slate.
## slate: {item_id(StringName): count}. `knows` returns true for recipes the crafter knows.
static func match_recipe(slate: Dictionary, station: StringName, knows: Callable) -> RecipeDef:
	if slate.is_empty():
		return null
	for r: RecipeDef in Content.all(&"recipe"):
		if r.station != station:
			continue
		if r.ingredients.size() != slate.size():
			continue
		var same: bool = true
		for k: StringName in r.ingredients:
			if int(slate.get(k, 0)) != int(r.ingredients[k]):
				same = false
				break
		if same and knows.call(r):
			return r
	return null


## Recipes whose ingredient set is a superset of what's on the slate (for "almost there" hints).
static func partial_matches(slate: Dictionary, station: StringName, knows: Callable) -> Array[RecipeDef]:
	var out: Array[RecipeDef] = []
	for r: RecipeDef in Content.all(&"recipe"):
		if r.station != station or not knows.call(r):
			continue
		var ok: bool = true
		for k: Variant in slate.keys():
			if not r.ingredients.has(StringName(k)) or int(slate[k]) > int(r.ingredients[StringName(k)]):
				ok = false
				break
		if ok:
			out.append(r)
	return out


static func check(recipe: RecipeDef, inv: Inventory, station: StringName, times: int = 1) -> Result:
	if recipe == null:
		return Result.fail("no recipe")
	if recipe.station != station:
		return Result.fail("needs %s" % (recipe.station if recipe.station != &"" else "hands"))
	for k: StringName in recipe.ingredients:
		if inv.count_of(k) < int(recipe.ingredients[k]) * times:
			return Result.fail("missing %s" % k)
	for t: String in recipe.tools_required:
		if inv.find_tool(t) == null:
			var r: Result = Result.fail("needs a %s" % t)
			return r
	var r := Result.new()
	r.ok = true
	return r


## Consumes ingredients and adds the result. Atomic: if the result cannot fit, nothing changes.
static func craft(recipe: RecipeDef, inv: Inventory, station: StringName, quality: int = 0) -> Result:
	var chk: Result = check(recipe, inv, station)
	if not chk.ok:
		return chk
	var out: ItemStack = ItemStack.make(recipe.result, recipe.result_count, quality)
	# Ingredients free up bulk/slots, so test the fit against a simulated post-consumption state.
	var sim: Inventory = Inventory.from_dict(inv.to_dict())
	sim.remove_all(recipe.ingredients)
	if sim.capacity_for(out) < out.count:
		return Result.fail("no room for %s" % recipe.result)
	inv.remove_all(recipe.ingredients)
	var leftover: int = inv.add(out)
	assert(leftover == 0)
	var r := Result.new()
	r.ok = true
	r.stack = out
	return r


## Crafted quality from the crafter's relevant perk/skill level (0 for non-quality items).
static func quality_for(recipe: RecipeDef, craft_skill_level: int) -> int:
	var d: ItemDef = Content.item(recipe.result)
	if d == null or not d.has_quality:
		return 0
	return clampi(1 + craft_skill_level, 1, 6)
