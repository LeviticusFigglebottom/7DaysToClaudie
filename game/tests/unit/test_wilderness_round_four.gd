extends GutTest
## Forest set pieces, round 4 (ADR-0053): seven dungeons random worlds place in the woods from the
## wilderness pool. Each building's own test (test_w4_<short>.gd) proves it validates clean, is a full
## dungeon and keeps its route clear for the player's capsule; this one checks how they join the
## world: one `late` pool entry each on a forest site, placed from their own streams after the
## farmsteads (generator v9), in regions as dangerous as their entries ask, and in most worlds.

const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")
const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")

const ROUND_FOUR: Dictionary = {
	"w4_hillside_bunker": 3,
	"w4_cordon_plane_wreck": 3,
	"w4_backcountry_ranger_station": 2,
	"w4_trestle_tunnel": 2,
	"w4_logging_truck_depot": 2,
	"w4_ridge_relay_hut": 1,
	"w4_overgrown_chapel": 2,
}


func _pool() -> Array:
	var cfg: Dictionary = Content.config(&"world_gen")
	return ((cfg.get("tuning", {}) as Dictionary).get("wilderness", {}) as Dictionary).get("pool", [])


func _entry(id: String) -> Dictionary:
	for e: Variant in _pool():
		if str((e as Dictionary).get("poi", "")) == id:
			return e
	return {}


func test_each_has_one_late_forest_entry() -> void:
	for id: String in ROUND_FOUR:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		assert_not_null(pd, "%s is content" % id)
		if pd == null:
			continue
		assert_eq(pd.tier, int(ROUND_FOUR[id]), "%s tier" % id)
		assert_true(pd.zoning.has("wilderness"), "%s is zoned wilderness" % id)
		var n: int = _pool().filter(func(e: Dictionary) -> bool: return str(e.get("poi", "")) == id).size()
		assert_eq(n, 1, "%s has one wilderness pool entry" % id)
		var pe: Dictionary = _entry(id)
		assert_eq(str(pe.get("site", "")), "forest", "%s stands in the woods" % id)
		assert_true(bool(pe.get("late", false)), "%s is placed late, from its own stream" % id)
		assert_gt(float(pe.get("per_region", 0.0)), 0.0, "%s is drawn" % id)


func test_generator_version_counts_them() -> void:
	assert_gte(Generator.VERSION, 9, "worlds cached before the forest set pieces regenerate")


func test_worlds_place_them_where_their_entries_allow() -> void:
	var seen: Dictionary = {}
	for seed: int in [1, 2, 3]:
		var g: RefCounted = Generator.generate(GenSettings.resolve(&"standard", {"size": 8}, seed))
		var regions: Dictionary = g.get(&"regions")
		for p: Variant in g.get(&"places") as Array:
			var pl: Dictionary = p
			var id: String = str(pl.get("def", ""))
			if not ROUND_FOUR.has(id):
				continue
			seen[id] = int(seen.get(id, 0)) + 1
			var want: int = int(_entry(id).get("min_danger", 1))
			assert_gte(int(regions[pl["cell"]]["danger"]), want, "seed %d: %s in a danger-%d+ region" % [seed, id, want])
	gut.p("forest set pieces placed in three 8 x 8 worlds: %s" % [seen])
	assert_gte(seen.size(), 5, "most of the seven turn up in three worlds: %s" % [seen])
