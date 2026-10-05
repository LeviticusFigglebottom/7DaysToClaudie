extends GutTest
## Prop lights (ADR-0023): lights are per condition variant (a destroyed lantern stays dark), mains
## fixtures never light in the powered-down valley, a lit prop glows on its own instance, and bad
## light data fails validation.


func _prop(id: StringName) -> PropDef:
	return Content.get_def(&"prop", id) as PropDef


func test_lights_are_per_variant() -> void:
	var lantern: PropDef = _prop(&"lantern_camping")
	assert_false(lantern.light_for("clean").is_empty(), "a clean lantern burns")
	assert_false(lantern.light_for("worn").is_empty(), "a cracked one still burns")
	assert_true(lantern.light_for("destroyed").is_empty(), "a smashed lantern stays dark")
	assert_lt(float(lantern.light_for("worn")["energy"]), float(lantern.light_for("clean")["energy"]), "the worn variant overrides energy")
	assert_false(lantern.light_for("clean").has("variants"), "overrides are resolved, not passed on")
	# A burnt-down candle's flame sits lower.
	var candles: PropDef = _prop(&"candle_cluster")
	assert_lt(float((candles.light_for("worn")["offset"] as Array)[1]), float((candles.light_for("clean")["offset"] as Array)[1]))
	# A condition the prop has no model for falls back the way model_for does, light included.
	assert_eq(candles.variant_for("destroyed"), "worn")
	assert_false(candles.light_for("destroyed").is_empty(), "the fallback model is the worn one, which can burn")


func test_power_is_out() -> void:
	for id: StringName in [&"street_lamp", &"ceiling_light", &"floor_lamp", &"desk_lamp", &"wall_sconce", &"road_canopy_light"]:
		var pd: PropDef = _prop(id)
		assert_eq(str(pd.light.get("power", "")), "mains", "%s runs on mains" % id)
		assert_true(pd.light_for("clean").is_empty(), "%s is dark: no grid in the valley" % id)
	for id: StringName in [&"candle_cluster", &"lantern_camping", &"oil_drum_fire", &"wild_oil_lantern", &"wild_wood_stove", &"civic_altar"]:
		assert_eq(str(_prop(id).light.get("power", "")), "flame", "%s burns fuel" % id)
	assert_eq(str(_prop(&"oil_drum_fire").light_for("worn").get("fx", "")), "fire", "a burn barrel has flames")


func test_light_data_is_validated() -> void:
	var raw: Dictionary = {"id": "t_lamp", "name": "T", "variants": {"clean": "props/x", "destroyed": "props/x_d"},
		"light": {"color": "#ffffff", "energy": 1.0, "range": 3.0, "offset": [0, 1, 0], "power": "solar", "glow": 2,
			"variants": {"worn": {"energy": 0.5}, "clean": {"hue": 1}}}}
	var pd := PropDef.new()
	assert_eq(pd.parse(raw, &"prop", "test"), PackedStringArray())
	var out: PackedStringArray = []
	pd._validate(Content, out)
	var text: String = "\n".join(out)
	assert_string_contains(text, "power 'solar'")
	assert_string_contains(text, "unknown light key 'glow'")
	assert_string_contains(text, "light variant 'worn' is not one of the prop's variants")
	assert_string_contains(text, "unknown light key 'hue' in variant 'clean'")
	for pd2: PropDef in Content.all(&"prop"):
		var o2: PackedStringArray = []
		pd2._validate_light(o2)
		assert_eq(o2, PackedStringArray(), "%s light data is valid" % pd2.id)


func _poi(props: Array) -> PoiDef:
	var raw: Dictionary = {"id": "t_lights", "name": "T", "tier": 1, "footprint": [8, 8],
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}}], "props": props}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func test_lit_props_burn_and_glow_on_their_own_instance() -> void:
	var d: PoiDef = _poi([
		{"id": "l1", "prop": "lantern_camping", "at": [0, 0], "variant": "clean", "lit": true},
		{"id": "l2", "prop": "lantern_camping", "at": [1, 0], "variant": "destroyed", "lit": true},
		{"id": "l3", "prop": "lantern_camping", "at": [2, 0], "variant": "clean"},
		{"id": "l4", "prop": "street_lamp", "at": [3, 1], "variant": "clean", "lit": true},
		{"id": "l5", "prop": "oil_drum_fire", "at": [0, 2], "variant": "worn", "lit": true},
	])
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(d), &"test/lights")
	add_child_autofree(inst)
	# (Sibling names may be made unique by the tree, so find them by type.)
	var lights: Array[Node] = inst.find_children("*", "OmniLight3D", true, false)
	assert_eq(lights.size(), 2, "the clean lantern and the barrel burn; the smashed lantern, the unlit one and the street lamp don't")
	var lit_meshes: int = 0
	for c: Node in inst.get_children():
		var v: Variant = (c as GeometryInstance3D).get_instance_shader_parameter(PropLights.LIT_PARAM) if c is MeshInstance3D else null
		if v != null and float(v) > 0.5:
			lit_meshes += 1
	assert_eq(lit_meshes, 2, "each burning prop is drawn on its own with its glow on")
	var barrel: OmniLight3D = null
	for l: Node in lights:
		if is_equal_approx((l as OmniLight3D).light_energy, float(_prop(&"oil_drum_fire").light_for("worn")["energy"])):
			barrel = l
	assert_not_null(barrel, "the barrel burns at its worn variant's energy")
	if barrel != null:
		assert_not_null(barrel.get_node_or_null(^"Crackle"), "a fire crackles")
