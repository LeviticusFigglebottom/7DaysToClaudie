extends GutTest
## The Ashen highcamp (ADR-0048): a living tier-3 camp in the high timber. It validates clean, its route
## is a dungeon's (open gateway, chained hut, key, hide-hung breach, cache pit, bolted shortcut out), and it
## is *living*: its people come from the AshenDirector, so its only sleepers are the three taken the camp
## keeps chained in the binding hut, and its fires and pyre burn (lit and kept, lights_on 1). Its new props
## (props/ashen.json) resolve with the sizes and light the generator builds, and its notes tell the story
## without naming a town.

const ID := "ashen_highcamp"
const NEW_PROPS: Array[String] = ["ashen_war_drum", "ashen_spear_rack", "ashen_ash_pots", "ashen_drying_rack", "ashen_camp_fire"]
## Places a player could read a town's name in.
const TOWNS: Array[String] = ["Pell", "Merrow", "Larch", "Hollowmere", "Tamsin", "Bracken"]

var _v: PoiValidator


func _def() -> PoiDef:
	return Content.get_def(&"poi", StringName(ID)) as PoiDef


func _validated() -> PoiValidator:
	if _v == null:
		_v = PoiValidator.validate(_def())
	return _v


func test_tier_three_wilderness() -> void:
	var pd: PoiDef = _def()
	assert_not_null(pd, "the highcamp is content")
	if pd == null:
		return
	assert_eq(pd.tier, 3, "tier 3")
	assert_true(pd.zoning.has("wilderness"), "zoned wilderness")
	assert_false(pd.zoning.has("residential") or pd.zoning.has("commercial"), "stays out of town lots")
	assert_eq(pd.population, &"", "no POI-wide population: the camp's people are spawned awake by the AshenDirector")


func test_validates_clean() -> void:
	var v: PoiValidator = _validated()
	assert_eq(v.errors, PackedStringArray(), "validates")
	assert_eq(v.warnings, PackedStringArray(), "no warnings")


func test_route_is_walked_end_to_end() -> void:
	var v: PoiValidator = _validated()
	var l: PoiLayout = v.layout
	assert_gt(l.route.size(), 6, "a route of beats")
	assert_eq(v.paths.size(), l.route.size(), "every leg of the route was walked")
	assert_eq(str(l.loot_room.get("room", "")), "C", "the cache pit is the loot room")
	assert_eq(int(l.loot_room.get("level", 0)), -1, "under the longhouse")
	assert_true((v.stats.get("keys", []) as Array).has("out_ashen_cache_key"), "the route picks up the cache key")
	var cache_keyed: bool = false
	for p: Dictionary in l.props:
		if str(p.get("prop", "")) == "out_ashen_cache" and int(p.get("level", 0)) == -1:
			cache_keyed = str(p.get("key", "")) == "out_ashen_cache_key"
	assert_true(cache_keyed, "the cache in the pit is locked with the key the route finds")


func test_a_dungeon_shape() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var shortcut_ok: bool = false
	for sc: Variant in l.shortcuts:
		shortcut_ok = shortcut_ok or str(l.opening(str((sc as Dictionary).get("opening", ""))).get("state", "")) == "locked_inside"
	assert_true(shortcut_ok, "a bolted shortcut out")
	var locks: int = 0
	for op: Dictionary in l.openings:
		if str(op.get("lock", "")) != "":
			locks += 1
	assert_gt(locks, 1, "lock cues: the bolt and the chain")
	var chain: Dictionary = l.opening("binding_door")
	assert_eq(str(chain.get("lock", "")), "chain", "the binding hut is chained")
	var key_held: int = 0
	for pk: Dictionary in l.pickups:
		if str(pk.get("item", "")) == str(chain.get("key", "")):
			key_held += 1
	assert_eq(key_held, 1, "the chain's key lies in the camp once")
	assert_not_null(Content.get_def(&"item", StringName(str(chain.get("key", "")))), "the chain's key is an item")
	assert_gt(l.traps.size(), 1, "sets traps")
	var trap_trigger: bool = false
	for tg: Dictionary in l.triggers:
		trap_trigger = trap_trigger or (str(tg.get("on", "")) == "trap" and not bool(tg["implicit"]))
	assert_true(trap_trigger, "tier 3: a trap sets off an ambush")


func test_living_camp_keeps_only_the_taken() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_between(l.sleepers.size(), 1, 3, "only the taken sleep here (the living are the AshenDirector's)")
	for s: Dictionary in l.sleepers:
		assert_eq(str(s["group"]), "taken", "%s is one of the taken" % s["sid"])
		assert_eq(l.room_at(int(s["level"]), s["cell"]), "B", "%s is chained in the binding hut" % s["sid"])
		assert_eq(str(s.get("population", "")), "ashen", "%s wears Ashen dress" % s["sid"])
		assert_false(bool(s["guardian"]), "no guardian: the camp's people guard the cache")
	var wakes: Dictionary = {}
	for tg: Dictionary in l.triggers:
		if str(tg["group"]) == "taken":
			wakes[str(tg["on"])] = true
	assert_true(wakes.has("opening") and wakes.has("trap"), "the chain or the jaws set the taken loose")


func test_fires_burn() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	assert_eq(float(l.style.get("lights_on", 0.0)), 1.0, "every light burns: somebody feeds these fires")
	var fires: int = 0
	var pyre_lit: bool = false
	for p: Dictionary in l.props:
		if not bool(p.get("lit", false)):
			continue
		assert_true(bool(p.get("keep", false)), "%s is kept lit every run" % p.get("prop"))
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		var light: Dictionary = pd.light_for(str(p.get("variant", "clean"))) if pd != null else {}
		assert_false(light.is_empty(), "%s (%s) can burn" % [p.get("prop"), p.get("variant", "clean")])
		if str(light.get("fx", "")) == "fire":
			fires += 1
			pyre_lit = pyre_lit or str(p.get("prop", "")) == "out_pyre"
	assert_gt(fires, 4, "lit fires: the gateway, the yard, the lean-to, the longhouse hearth, the smoke hut")
	assert_true(pyre_lit, "the pyre burns")


func test_new_props_resolve_and_are_placed() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var placed: Dictionary = {}
	for p: Dictionary in l.props:
		placed[str(p.get("prop", ""))] = true
	for id: String in NEW_PROPS:
		var pd: PropDef = Content.get_def(&"prop", StringName(id)) as PropDef
		assert_not_null(pd, "%s is a prop" % id)
		if pd == null:
			continue
		assert_eq(pd.model_for("clean"), "props/%s" % id, "%s draws its generated model" % id)
		assert_eq(pd.model_for("worn"), "props/%s_worn" % id, "%s has a worn variant" % id)
		assert_true(pd.size.x > 0.3 and pd.size.y > 0.3 and pd.size.z > 0.3, "%s has a box to stand in before assets" % id)
		assert_true(placed.has(id), "the highcamp places %s" % id)
	var fire: PropDef = Content.get_def(&"prop", &"ashen_camp_fire") as PropDef
	assert_eq(str(fire.light_for("clean").get("fx", "")), "fire", "the camp fire has flames")
	assert_eq(str(fire.light_for("worn").get("power", "")), "flame", "burning low it still burns")
	var pyre: PropDef = Content.get_def(&"prop", &"out_pyre") as PropDef
	assert_false(pyre.light_for("clean").is_empty(), "a lit pyre burns")
	assert_true(pyre.light_for("worn").is_empty(), "a burnt-down pyre does not")


func test_notes_resolve_and_name_no_town() -> void:
	var l: PoiLayout = PoiLayout.compile(_def())
	var notes: int = 0
	for pk: Dictionary in l.pickups:
		assert_not_null(Content.get_def(&"item", StringName(str(pk.get("item", "")))), "pickup %s is an item" % pk.get("item"))
		if not bool(pk.get("is_note", false)):
			continue
		notes += 1
		var nid: String = str(pk["item"]).trim_prefix("note_")
		var nd: ContentDef = Content.get_def(&"note", StringName(nid))
		assert_not_null(nd, "note %s exists" % nid)
		if nd == null:
			continue
		var body: String = str(nd.get(&"body"))
		assert_gt(body.length(), 120, "note %s says something" % nid)
		for town: String in TOWNS:
			assert_false(body.contains(town), "note %s names no town (%s): the camp may sit anywhere" % [nid, town])
	assert_gt(notes, 1, "the story is told in notes")
	for e: String in Content.errors():
		assert_false(e.contains(ID) or e.contains("ashen_highcamp") or e.contains("ashen.json"), "content error: %s" % e)
