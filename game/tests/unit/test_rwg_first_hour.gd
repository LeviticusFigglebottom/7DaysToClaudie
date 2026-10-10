extends GutTest
## A random world's first hour (owner report 5, the companion's camp TD-308): every preset and the
## 8-world road set give a player who lands at the drop site towns that exist and are named on the
## map, water within a short walk for the boil-water step, Ezra's camp for the tutorial's distress
## call, and a first town and a first place within a day's walk.

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Generator := preload("res://src/worldgen/rwg/rwg_generator.gd")

## Metres from the drop site: the nearest river or lake (coarse 32 m water distance), the nearest
## town's edge, the camp, any other place.
const WATER_MAX: float = 500.0
const TOWN_MAX: float = 1200.0
const PLACE_MAX: float = 900.0

## [preset, seed, overrides]: each preset at a seed of the 8-world set, the set itself (standard and
## settled, seeds 3, 7, 11, 21), and the two readings of the report (the most towns a 4 km map
## takes; a 10 km map at the default density).
const WORLDS: Array = [
	["standard", 3, {}], ["standard", 7, {}], ["standard", 11, {}], ["standard", 21, {}],
	["settled", 3, {}], ["settled", 7, {}], ["settled", 11, {}], ["settled", 21, {}],
	["small_valley", 7, {}], ["highlands", 7, {}], ["lakeland", 7, {}], ["wild", 7, {}],
	["standard", 7, {"size": 5}], ["standard", 7, {"town_density": 6.0}],
]


func _check(preset: String, seed: int, over: Dictionary) -> PackedStringArray:
	var bad: PackedStringArray = []
	var tag: String = "%s %d %s" % [preset, seed, over]
	var settings: RefCounted = GenSettings.resolve(StringName(preset), over, seed)
	var g: RefCounted = Generator.generate(settings)
	var vals: Dictionary = settings.get(&"values")
	var dp: Vector2 = (g.get(&"drop") as Dictionary).get("pos", Vector2.INF)
	if dp == Vector2.INF:
		return PackedStringArray(["%s: no drop site" % tag])
	var towns: Array = g.get(&"towns")
	var want: int = 1 if float(vals.get("town_density", 2.0)) > 0.0 else 0
	if towns.size() < want:
		bad.append("%s: %d towns" % [tag, towns.size()])
	for t: Dictionary in towns:
		if str(t.get("name", "")) == "":
			bad.append("%s: a town with no name for the map" % tag)
	var td: float = g.call(&"_town_distance", dp)
	if want > 0 and td > TOWN_MAX:
		bad.append("%s: nearest town %d m from the drop" % [tag, int(td)])
	var wd: float = g.call(&"water_at", dp)
	if wd > WATER_MAX:
		bad.append("%s: water %d m from the drop" % [tag, int(wd)])
	var camp: bool = false
	var near_place: float = INF
	for p: Dictionary in g.get(&"places"):
		var c: Vector2 = p["center"]
		if str(p["site"]) == "companion":
			camp = true
		elif str(p["site"]) != "crash":
			near_place = minf(near_place, c.distance_to(dp))
	if not camp:
		bad.append("%s: no camp for Ezra" % tag)
	if near_place > PLACE_MAX:
		bad.append("%s: nearest place %d m from the drop" % [tag, int(near_place)])
	gut.p("[first hour] %s: %d towns, town %d m, water %d m, place %d m" % [tag, towns.size(), int(td), int(wd), int(near_place)])
	return bad


func test_every_preset_gives_a_first_hour() -> void:
	var bad: PackedStringArray = []
	for w: Array in WORLDS:
		bad.append_array(_check(str(w[0]), int(w[1]), w[2]))
	assert_eq(bad, PackedStringArray(), "every world has its towns, water, camp and a place near the drop")
