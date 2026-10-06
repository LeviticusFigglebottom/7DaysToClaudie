extends GutTest
## Wall props sit on their walls (TD-159): a wall-mounted prop placed `against` a wall hangs with its
## back on the wall's face (its origin is on the wall plane, docs/ASSET_PIPELINE.md), a floor prop
## stands 1 cm off it; PoiValidator reports any wall prop (authored or generated) more than
## WALL_GAP_MAX off its wall, sunk into it or with no wall behind it; and every generated prop
## model's back is where its PropDef says (PropDef.back_depth), so the placement math holds for
## the real meshes.


func _def(raw_layout: Dictionary) -> PoiDef:
	var raw: Dictionary = {"id": "t", "name": "T", "tier": 1, "footprint": [16, 16]}
	raw.merge(raw_layout, true)
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func _gaps(v: PoiValidator) -> PackedStringArray:
	var out: PackedStringArray = []
	for w: String in v.warnings:
		if w.contains(": wall gap: "):
			out.append(w)
	return out


func test_a_wall_mounted_prop_against_a_wall_hangs_on_its_face() -> void:
	# A 0.35 m deep wall cabinet on each wall of a 3x3 room. Round 1 stood it half its depth
	# (17.5 cm) out in the room.
	var layout := PoiLayout.compile(_def({
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"props": [
			{"id": "n", "prop": "kitchen_wall_cabinet", "at": [1, 0], "against": "N"},
			{"id": "e", "prop": "kitchen_wall_cabinet", "at": [2, 1], "against": "E"},
			{"id": "s", "prop": "kitchen_wall_cabinet", "at": [1, 2], "against": "S"},
			{"id": "w", "prop": "kitchen_wall_cabinet", "at": [0, 1], "against": "W"}]}))
	var pd: PropDef = Content.get_def(&"prop", &"kitchen_wall_cabinet") as PropDef
	assert_true(pd.wall_mounted)
	assert_eq(pd.back_depth(), 0.0, "a wall-mounted model's origin is on the wall plane")
	for p: Dictionary in layout.props:
		var plan: Vector3 = PoiLayout.prop_plan(p, pd)
		var toward: Vector2i = PoiLayout.DIRS[PoiLayout.SIDES[p["against"]]]
		var face: Vector2 = Vector2(p["cell"]) + Vector2(0.5, 0.5) + Vector2(toward) * (0.5 - PoiBuilder.WALL_T * 0.5)
		assert_almost_eq((Vector2(plan.x, plan.y) - face).dot(-Vector2(toward)), 0.01, 0.001,
			"%s: its back 1 cm off the wall's face" % p["id"])
	assert_eq(_gaps(PoiValidator.validate(layout.def)), PackedStringArray())


func test_a_prop_turned_against_its_wall_keeps_its_whole_footprint_off_it() -> void:
	# A steel shelf (0.95 m wide, 0.45 m deep) side on to the N wall, and one turned 25° off it as
	# the builder's wall scatter does: the nearest corner, not the back's middle, comes to the wall.
	var pd: PropDef = Content.get_def(&"prop", &"metal_shelf") as PropDef
	var face: float = PoiBuilder.WALL_T * 0.5
	var side_on: Vector3 = PoiLayout.prop_plan({"pos": Vector2(1.5, 0.5), "cell": Vector2i(1, 0), "against": "N", "rot": 90.0}, pd)
	assert_almost_eq(side_on.y, face + pd.size.x * 0.5 + 0.01, 0.001, "side on: half its width off the wall")
	var t: float = deg_to_rad(25.0)
	var turned: Vector3 = PoiLayout.prop_plan({"pos": Vector2(1.5, 0.5), "cell": Vector2i(1, 0), "against": "N", "rot": 25.0}, pd)
	assert_almost_eq(turned.y, face + pd.size.z * 0.5 * cos(t) + pd.size.x * 0.5 * sin(t) + 0.01, 0.001,
		"turned 25°: its back corner 1 cm off the wall")
	assert_almost_eq(turned.z, 25.0, 0.001, "and it keeps its turn")
	var v: PoiValidator = PoiValidator.validate(_def({
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"props": [{"id": "side_on", "prop": "metal_shelf", "at": [1, 0], "against": "N", "rot": 90}]}))
	assert_eq(_gaps(v), PackedStringArray(), "the validator measures it the same way")


func test_the_collision_box_covers_the_model_not_the_wall() -> void:
	var cab: PropDef = Content.get_def(&"prop", &"kitchen_wall_cabinet") as PropDef
	assert_almost_eq(cab.box_centre().z, cab.size.z * 0.5, 0.001, "wall-mounted: the box stands forward of the wall plane")
	var shelf: PropDef = Content.get_def(&"prop", &"metal_shelf") as PropDef
	assert_almost_eq(shelf.box_centre().z, 0.0, 0.001, "depth-centred: the box is centred on the origin")
	assert_almost_eq(shelf.back_depth(), shelf.size.z * 0.5, 0.001)


func test_the_validator_reports_a_prop_off_its_wall_in_it_or_on_nothing() -> void:
	# Hand-placed (pos) cabinets on the N wall (centre line z = 0, face at 0.08): 12 cm off it,
	# 8 cm into it, flush; and one in the middle of the room, nothing behind it.
	var v: PoiValidator = PoiValidator.validate(_def({
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}],
		"props": [
			{"id": "off", "prop": "kitchen_wall_cabinet", "pos": [0.5, 0.2], "rot": 0},
			{"id": "into", "prop": "kitchen_wall_cabinet", "pos": [1.5, 0.0], "rot": 0},
			{"id": "flush", "prop": "kitchen_wall_cabinet", "pos": [2.5, 0.09], "rot": 0},
			{"id": "air", "prop": "kitchen_wall_cabinet", "pos": [1.5, 1.5], "rot": 0}]}))
	var gaps: String = "\n".join(_gaps(v))
	assert_string_contains(gaps, "'off' (kitchen_wall_cabinet) at (0.5, 0.2) level 0 stands 0.12 m off its wall")
	assert_string_contains(gaps, "'into' (kitchen_wall_cabinet) at (1.5, 0.0) level 0 sinks 0.08 m into its wall")
	assert_string_contains(gaps, "'air' (kitchen_wall_cabinet) at (1.5, 1.5) level 0 has no wall")
	assert_false(gaps.contains("'flush'"), "1 cm off is on the wall")
	assert_eq(_gaps(v).size(), 3)


func test_every_authored_wall_prop_is_on_its_wall() -> void:
	var bad: PackedStringArray = []
	for d: PoiDef in Content.all(&"poi"):
		bad.append_array(_gaps(PoiValidator.validate(d)))
	assert_eq(bad, PackedStringArray(), "every authored POI's wall props sit on their walls")


func test_generated_buildings_on_framework_lots_keep_their_wall_props_on_walls() -> void:
	# Templates are checked over 50 seeds each by test_building_generator (it fails on any
	# warning); this adds the buildings framework lots generate.
	var bad: PackedStringArray = []
	for w: String in PoiValidator.validate_generated()["warnings"] as PackedStringArray:
		if w.contains("wall gap"):
			bad.append(w)
	assert_eq(bad, PackedStringArray())


## Props that go against walls: wall-mounted ones, those authored `against` a wall in any POI
## (every alternative dressing included) and the generator's wall furniture.
func _wall_props() -> Dictionary:
	var out: Dictionary = {}
	for pd: PropDef in Content.all(&"prop"):
		if pd.wall_mounted:
			out[pd.id] = true
	for d: PoiDef in Content.all(&"poi"):
		var lists: Array = [d.layout.get("props", [])]
		for g: Variant in d.layout.get("alternatives", []):
			for o: Variant in (g as Dictionary).get("options", []):
				lists.append((o as Dictionary).get("props", []))
		for list: Variant in lists:
			for p: Variant in list:
				if p is Dictionary and (p as Dictionary).has("against"):
					out[StringName(str(p["prop"]))] = true
	for room: String in BuildingGenerator.FURNITURE:
		for f: Array in BuildingGenerator.FURNITURE[room]:
			if str(f[1]) in ["wall", "high"]:
				out[StringName(str(f[0]))] = true
	return out


func test_every_wall_prop_model_has_its_back_where_its_def_says() -> void:
	# Measured on the clean variant's merged mesh: the depth behind the origin (prop-local −Z) is
	# what PoiLayout.prop_plan stands off the wall. Needs `make assets`; CI builds them.
	const TOL: float = 0.03
	var checked: int = 0
	var bad: PackedStringArray = []
	var wall: Dictionary = _wall_props()
	assert_gt(wall.size(), 100, "the wall props are found")
	for id: StringName in wall:
		var pd: PropDef = Content.get_def(&"prop", id) as PropDef
		if pd == null:
			continue
		var m: Mesh = ModelLibrary.generated_mesh(pd.model_for("clean"))
		if m == null:
			continue
		checked += 1
		var box: AABB = m.get_aabb()
		var back: float = -box.position.z
		if absf(back - pd.back_depth()) > TOL:
			bad.append("%s: model back %.3f m behind its origin (front %.3f), def says %.3f%s" % [pd.id, back,
				box.end.z, pd.back_depth(), " (wall_mounted)" if pd.wall_mounted else ""])
	if checked == 0:
		pending("no generated prop models (run make assets)")
		return
	assert_eq(bad, PackedStringArray(), "%d wall prop models measured" % checked)
