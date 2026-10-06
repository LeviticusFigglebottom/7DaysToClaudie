extends Node
## The work of poi_phase_bench.gd: builds buildings step by step as PoiManager._finish_poi does
## (the route check already run, as on its worker) and prints the longest step of each phase.

const Generator := preload("res://src/poi/building_generator.gd")
const Dressing := preload("res://src/poi/poi_dressing.gd")

## The heavy authored buildings of TD-107 plus the pools: data/config/world_gen.json's wilderness
## pool and the town set pieces (DESIGN §11).
const DEFAULT_IDS: Array[String] = ["tamsin_campground", "larch_hollow_sawmill", "merrow_house",
	"cordon_gas_garage", "ashen_watch_camp", "okafor_farmhouse",
	"cedar_ridge_lookout", "trappers_cabin", "tamsin_logging_camp", "larch_pond_boathouse",
	"timberline_motel", "mile9_diner", "camp_tamarack", "elk_ridge_lodge", "cordon_quarantine_camp",
	"haldane_place", "corvane_field_lab",
	"suds_spin_laundromat", "hollowmere_grocery", "bracken_lumber_feed", "pell_county_library", "khlw_valley_radio"]


func _ready() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var repeat: int = maxi(1, int(_arg(a, "--repeat", "3")))
	var slice: float = float(_arg(a, "--slice", "0"))
	var gen: int = int(_arg(a, "--generated", "2"))
	var ids: Array[String] = []
	var skip: bool = false
	for s: String in a:
		if skip:
			skip = false
		elif s.begins_with("--"):
			skip = true
		else:
			ids.append(s)
	if ids.is_empty():
		ids = DEFAULT_IDS.duplicate()
	var defs: Array[PoiDef] = []
	for id: String in ids:
		var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
		if pd == null:
			print("[bench] no poi %s" % id)
			continue
		defs.append(pd)
	var n: int = 0
	for t: Variant in Content.all(&"building_template"):
		if n >= gen:
			break
		var g: PoiDef = Generator.generate(t, 4242 + n)
		if g != null:
			defs.append(g)
			n += 1
	print("[bench] slice %.1f ms, fastest of %d builds" % [slice, repeat])
	var worst_all: float = 0.0
	for raw: PoiDef in defs:
		# Dressed per run, as the game builds it (run decals, per-run scatter).
		var ds: int = Dressing.dressing_seed(7, StringName("bench/%s" % raw.id), Dressing.MODE_PER_RUN)
		var pd: PoiDef = Dressing.resolve(raw, Dressing.roll(raw, ds), {"mode": Dressing.MODE_PER_RUN, "seed": ds})
		var best: Dictionary = {}
		var best_max: float = INF
		var steps: int = 0
		for r: int in repeat:
			var layout := PoiLayout.compile(pd)
			var v := PoiValidator.new()
			v.layout = layout
			v._run()
			PoiBuilder.prepare_check(v)
			var b: PoiBuilder = PoiBuilder.start(layout, StringName("bench/%s" % pd.id), v)
			var per: Dictionary = {}
			var mx: float = 0.0
			steps = 0
			while true:
				var phase: String = b.next_phase()
				var t0: int = Time.get_ticks_usec()
				var done: bool = b.step(slice)
				var ms: float = float(Time.get_ticks_usec() - t0) / 1000.0
				steps += 1
				per[phase] = maxf(float(per.get(phase, 0.0)), ms)
				mx = maxf(mx, ms)
				if done:
					break
			b.root.free()
			best_max = minf(best_max, mx)
			for k: String in per:
				best[k] = minf(float(best.get(k, INF)), float(per[k]))
		var parts: PackedStringArray = []
		for k: String in best:
			if float(best[k]) >= 1.0:
				parts.append("%s %.1f" % [k, float(best[k])])
		worst_all = maxf(worst_all, best_max)
		print("[bench] %-24s max %5.1f ms  steps %3d | %s" % [pd.id, best_max, steps, ", ".join(parts)])
	print("[bench] worst step %.1f ms" % worst_all)
	get_tree().quit(0)


func _arg(a: PackedStringArray, key: String, def: String) -> String:
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else def
