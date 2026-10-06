extends GutTest
## The third block in random towns: Pell's Crossing's school, fire station and Savings & Loan are
## authored picks on Larch Street and also pool buildings (DESIGN §11, LotPicker, ADR-0030). Each is
## zoned, tiered and sized for the random generator's lots, a fitting lot picks it for some world
## seed, residential lots never do, and nothing a player reads in them names Pell's Crossing.

const Lots := preload("res://src/poi/lot_picker.gd")

## id -> the lot it fits: [zoning, tier, lot width, lot depth] (data/config/world_gen.json
## tuning.towns.lot: commercial 28 x 32 on the main street, civic 32 x 32).
const THIRD_BLOCK: Dictionary = {
	"pell_crossing_school": ["civic", 3, 32, 32],
	"pell_fire_station": ["civic", 2, 32, 32],
	"pell_savings_loan": ["commercial", 3, 28, 32],
}


func _fw(lots: Array) -> FrameworkDef:
	var fw := FrameworkDef.new()
	assert_eq(fw.parse({"id": "third_block_fw", "size": [400, 400], "tier_range": [1, 3], "lots": lots}, &"framework", "test"), PackedStringArray())
	return fw


func test_zoned_tiered_and_sized_for_town_lots() -> void:
	for id: String in THIRD_BLOCK:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		assert_not_null(pd)
		if pd == null:
			continue
		var want: Array = THIRD_BLOCK[id]
		assert_true(pd.zoning.has(str(want[0])), "%s is zoned %s" % [id, want[0]])
		assert_eq(pd.tier, int(want[1]))
		assert_true(pd.footprint.x <= int(want[2]) and pd.footprint.y <= int(want[3]),
			"%s footprint %s fits a %dx%d %s lot" % [id, pd.footprint, want[2], want[3], want[0]])
		assert_false(pd.zoning.has("residential"), "%s stays off residential streets" % id)


func test_a_fitting_lot_picks_each() -> void:
	for id: String in THIRD_BLOCK:
		var want: Array = THIRD_BLOCK[id]
		var t: int = int(want[1])
		var fw: FrameworkDef = _fw([{"id": "lot", "rect": [10, 10, int(want[2]), int(want[3])], "zoning": [want[0]], "facing": "S",
			"tier": [t, t], "pool": "authored"}])
		var picked: int = -1
		for ws: int in range(1, 513):
			if String(Lots.resolve(fw, "town", ws)[0].get("def_id", "")) == id:
				picked = ws
				break
		assert_gt(picked, 0, "a %s tier-%d lot picks %s for some world seed" % [want[0], t, id])
		for ws2: int in range(1, 33):
			for r: Dictionary in Lots.resolve(_fw([{"id": "home", "rect": [0, 0, 40, 40], "zoning": ["residential"], "facing": "S",
					"tier": [t, t]}]), "town", ws2):
				assert_ne(String(r.get("def_id", "")), id, "a residential lot never draws %s" % id)


func test_nothing_a_player_reads_names_the_town() -> void:
	for id: String in THIRD_BLOCK:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		assert_false(pd.display_name.contains("Pell"), "%s: its name" % id)
		assert_false(pd.story.contains("Pell's Crossing"), "%s: its story" % id)
	for nd: ContentDef in Content.all(&"note"):
		if String(nd.id).begins_with("town2_"):
			var body: String = str(nd.get(&"body"))
			assert_false(body.contains("Pell") or body.contains("Merrow") or body.contains("Larch") or body.contains("Okafor"),
				"note %s names a Pell's Crossing place" % nd.id)
