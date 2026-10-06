class_name CropDef
extends ContentDef
## A garden crop (ADR-0049): what you plant it from, how long it takes, what it gives, and how hard
## the weather is on it. Growth itself is Farming's business; state lives in WorldState.farms.

const SEASONS: PackedStringArray = ["spring", "summer", "autumn", "winter"]

## Items that plant it (seed packets, a seed potato, a potato itself). The first is the usual one.
var seeds: PackedStringArray = []
## {item_id: [min, max]} picked at harvest.
var produce: Dictionary = {}
## {item_id: [min, max]} seeds saved back from a harvest (so a garden can keep itself going).
var seed_return: Dictionary = {}
## Game days of good growth (watered, in season, warm enough) from planting to ripe.
var grow_days: float = 4.0
## Visual stages, the last one ripe (models "<model>_s1".."<model>_s<stages>").
var stages: int = 4
## Days a plant lasts in dry soil before it dies (it wilts on the way).
var wilt_days: float = 1.5
## Below this ambient temperature (°C) it does not grow at all.
var min_temp_c: float = 5.0
## Below this ambient temperature (°C) frost hurts it.
var frost_c: float = -1.0
## Per-season growth multipliers; seasons left out use data/config/farming.json "seasons".
var seasons: Dictionary = {}
## A perennial goes back to this stage (0-based) after a harvest instead of being used up; -1 =
## annual (the plot is empty again).
var regrow_stage: int = -1
## Model id prefix (assets/generated/models/<model>_s<n>.glb).
var model: String = ""
## Stand-in colours: foliage, and the produce shown when ripe.
var leaf_color: Color = Color(0.3, 0.5, 0.2)
var color: Color = Color(0.6, 0.4, 0.2)
## Height (m) of the ripe plant (the stand-in's scale).
var height: float = 0.5


func _fields() -> PackedStringArray:
	return ["seeds", "produce", "seed_return", "grow_days", "stages", "wilt_days", "min_temp_c", "frost_c", "seasons",
		"regrow_stage", "model", "leaf_color", "color", "height"]


func _parse(r: DefReader) -> void:
	seeds = r.strings("seeds")
	produce = r.dict("produce")
	seed_return = r.dict("seed_return")
	grow_days = maxf(0.1, r.num("grow_days", 4.0))
	stages = clampi(r.integer("stages", 4), 2, 8)
	wilt_days = maxf(0.1, r.num("wilt_days", 1.5))
	min_temp_c = r.num("min_temp_c", 5.0)
	frost_c = r.num("frost_c", -1.0)
	seasons = r.dict("seasons")
	regrow_stage = r.integer("regrow_stage", -1)
	model = r.str_field("model", "crops/%s" % id)
	leaf_color = Color.html(r.str_field("leaf_color", "#4d7f33"))
	color = Color.html(r.str_field("color", "#99663a"))
	height = maxf(0.05, r.num("height", 0.5))
	if seeds.is_empty():
		r.err("a crop needs at least one seed item")
	if produce.is_empty():
		r.err("a crop needs produce")
	if regrow_stage >= stages - 1:
		r.err("regrow_stage must be below the ripe stage (%d)" % (stages - 1))
	for k: Variant in seasons.keys():
		if not SEASONS.has(str(k)):
			r.err("seasons: unknown season '%s'" % k)


func _validate(db: Node, out: PackedStringArray) -> void:
	for s: String in seeds:
		if not db.has_def(&"item", StringName(s)):
			out.append("%s: seed item '%s' unknown" % [ctx(), s])
	for dict: Dictionary in [produce, seed_return]:
		for k: Variant in dict.keys():
			if not db.has_def(&"item", StringName(str(k))):
				out.append("%s: item '%s' unknown" % [ctx(), k])
			var r: Variant = dict[k]
			if not (r is Array and (r as Array).size() == 2):
				out.append("%s: '%s' needs [min, max]" % [ctx(), k])


## Model id of a stage (0-based).
func stage_model(stage: int) -> String:
	return "%s_s%d" % [model, clampi(stage, 0, stages - 1) + 1]
