extends GutTest
## First person (ADR-0029): every item resolves to a hold class from data/config/viewmodel.json
## (explicitly or by kind, damage type and category), with the swing, use, guard and in-hand
## placement that go with it; the data hangs together; bad equip.hold / equip.swing fail
## validation; struck surfaces classify for their feedback; and the generated arms carry an action
## for every hold, attack and use the data names.

const ARMS: String = "res://assets/generated/models/characters/fp_arms.glb"


func _cls(id: StringName) -> StringName:
	return ViewModelHolds.hold_class(Content.item(id))


func test_hold_classes_by_item() -> void:
	var want: Dictionary = {
		&"stone_axe": &"one_hand", &"hatchet": &"one_hand", &"machete": &"one_hand", &"kitchen_knife": &"one_hand",
		&"claw_hammer": &"one_hand", &"crude_spear": &"spear", &"stone_club": &"club", &"steel_pipe": &"club",
		&"shovel": &"two_hand", &"torch": &"light_left", &"flashlight": &"flashlight", &"lighter": &"lighter",
		&"revolver": &"pistol", &"canned_beans": &"food", &"water_bottle_clean": &"bottle", &"cloth_bandage": &"held",
		&"stone": &"held", &"can_chime": &"held",
	}
	for id: StringName in want:
		assert_not_null(Content.item(id), "%s exists" % id)
		assert_eq(_cls(id), want[id], "%s is held as %s" % [id, want[id]])
	assert_eq(ViewModelHolds.hold_class(null), ViewModelHolds.EMPTY, "nothing in hand: bare fists")


func test_swings_and_uses_follow_the_class() -> void:
	var swings: Dictionary = {&"stone_axe": &"chop", &"hatchet": &"chop", &"machete": &"slash", &"kitchen_knife": &"slash",
		&"crude_spear": &"stab", &"stone_club": &"bash", &"steel_pipe": &"bash", &"shovel": &"dig", &"torch": &"torch", &"flashlight": &"jab"}
	for id: StringName in swings:
		assert_eq(ViewModelHolds.attack_style(Content.item(id), _cls(id)), swings[id], "%s swings %s" % [id, swings[id]])
	assert_eq(ViewModelHolds.attack_style(null, ViewModelHolds.EMPTY), &"punch", "bare hands punch")
	assert_eq(ViewModelHolds.use_action(Content.item(&"canned_beans"), &"food"), &"eat")
	assert_eq(ViewModelHolds.use_action(Content.item(&"water_bottle_clean"), &"bottle"), &"drink")
	assert_eq(ViewModelHolds.use_action(Content.item(&"cloth_bandage"), &"held"), &"apply", "bandages are wrapped on")
	for style: StringName in [&"chop", &"slash", &"bash", &"stab", &"dig", &"punch", &"torch", &"jab"]:
		var f: float = ViewModelHolds.impact_fraction(style)
		assert_between(f, 0.2, 0.7, "%s connects partway through its swing" % style)


func test_every_equippable_item_has_a_known_hold() -> void:
	var cfg: Dictionary = ViewModelHolds.config()
	var holds: Dictionary = cfg.get("holds", {})
	for d: ItemDef in Content.all(&"item"):
		if d.equip.is_empty() and not d.is_consumable():
			continue
		var cls: StringName = ViewModelHolds.hold_class(d)
		assert_true(holds.has(String(cls)), "%s -> hold %s exists" % [d.id, cls])
	assert_eq(ViewModelHolds.problems(), PackedStringArray(), "viewmodel.json hangs together")


func test_guards_and_placement() -> void:
	var club: float = ViewModelHolds.block_share(Content.item(&"stone_club"), &"club")
	var axe: float = ViewModelHolds.block_share(Content.item(&"stone_axe"), &"one_hand")
	assert_gt(club, axe, "a club blocks more than a hatchet-sized tool")
	assert_gt(axe, 0.0, "one-handed tools can guard")
	assert_eq(ViewModelHolds.block_share(Content.item(&"canned_beans"), &"food"), 0.0, "food has no guard")
	var tmp := ItemDef.new()
	tmp.equip = {"kind": "melee", "damage_type": "blunt", "block": 0.8}
	assert_almost_eq(ViewModelHolds.block_share(tmp, &"club"), 0.8, 1e-6, "equip.block overrides the hold's")
	# One-handed tools turn their edge towards the palm, so the axe head shows broadside.
	var xf: Transform3D = ViewModelHolds.item_transform(Content.item(&"stone_axe"), &"one_hand")
	assert_almost_eq((xf.basis * Vector3(0, 0, 1)).dot(Vector3(0, 0, -1)), 1.0, 1e-4, "edge (+Z) faces the palm (-Z)")
	assert_eq(ViewModelHolds.item_hand(&"light_left"), "L", "lights go in the left hand")
	# The flashlight lies along the fist with its lens out of the little-finger side (-Y).
	var fl: Transform3D = ViewModelHolds.item_transform(Content.item(&"flashlight"), &"flashlight")
	assert_almost_eq((fl.basis * Vector3(0, 0, 1)).dot(Vector3(0, -1, 0)), 1.0, 1e-4, "beam (+Z) out of the little-finger side")
	assert_eq(ViewModelHolds.item_hand(&"one_hand"), "R")


func test_bad_hold_data_fails_validation() -> void:
	var raw: Dictionary = {"id": "t_vm", "name": "T", "category": "tool",
		"equip": {"slot": "hand", "kind": "melee", "hold": "juggle", "swing": "pirouette"}}
	var d := ItemDef.new()
	assert_eq(d.parse(raw, &"item", "test"), PackedStringArray())
	var out: PackedStringArray = []
	d._validate(Content, out)
	var text: String = "\n".join(out)
	assert_string_contains(text, "equip.hold 'juggle'")
	assert_string_contains(text, "equip.swing 'pirouette'")
	var cfg: Dictionary = ViewModelHolds.config().duplicate(true)
	(cfg["holds"] as Dictionary)["one_hand"]["attack"] = "flail"
	assert_string_contains("\n".join(ViewModelHolds.problems(cfg)), "attack 'flail'")


func test_struck_surfaces_classify() -> void:
	var metal := StaticBody3D.new()
	metal.set_meta(&"surface", "metal")
	var wood := StaticBody3D.new()
	wood.set_meta(&"surface", "wood_floor")
	var ground := StaticBody3D.new()
	ground.set_meta(&"terrain", true)
	var tree := StaticBody3D.new()
	tree.add_to_group(&"tree_body")
	var loose_log := LogEntity.new()
	var plain := StaticBody3D.new()
	for n: Node in [metal, wood, ground, tree, loose_log, plain]:
		autofree(n)
	assert_eq(ViewModelHolds.surface_kind(metal, null), &"metal")
	assert_eq(ViewModelHolds.surface_kind(wood, null), &"wood")
	assert_eq(ViewModelHolds.surface_kind(ground, null), &"dirt")
	assert_eq(ViewModelHolds.surface_kind(tree, null), &"wood")
	assert_eq(ViewModelHolds.surface_kind(loose_log, null), &"bark", "a loose log sheds bark")
	assert_eq(ViewModelHolds.surface_kind(plain, null), &"solid")
	var surfaces: Dictionary = (ViewModelHolds.config().get("impact", {}) as Dictionary).get("surfaces", {})
	for s: String in ["wood", "bark", "flesh", "metal", "stone", "dirt", "solid"]:
		assert_true(surfaces.has(s), "impact feedback for %s" % s)
		assert_gt(float((surfaces[s] as Dictionary).get("hitstop", 0.0)), 0.0, "%s freezes the swing a beat" % s)


func test_arms_carry_every_action() -> void:
	if not ResourceLoader.exists(ARMS):
		pending("arms not built (make assets)")
		return
	var arms: Node = (load(ARMS) as PackedScene).instantiate()
	autofree(arms)
	var anim: AnimationPlayer = arms.find_child("AnimationPlayer", true, false) as AnimationPlayer
	assert_not_null(anim)
	if anim == null or not anim.has_animation(&"fp_one_hand"):
		pending("arms predate the hold classes (rebuild fp_arms)")
		return
	var cfg: Dictionary = ViewModelHolds.config()
	for cls: String in cfg.get("holds", {}):
		assert_true(anim.has_animation(ViewModelHolds.idle_action(StringName(cls))), "fp_%s" % cls)
		if (cfg["holds"][cls] as Dictionary).has("guard"):
			assert_true(anim.has_animation(ViewModelHolds.guard_action(StringName(cls))), "fp_%s_guard" % cls)
	for group: String in ["attacks", "uses"]:
		for name: String in cfg.get(group, {}):
			if not name.begins_with("_"):
				assert_true(anim.has_animation(StringName("fp_%s" % name)), "fp_%s" % name)
	assert_true(anim.has_animation(&"fp_one_hand_tether"), "reading the tether with a tool in hand")
	assert_not_null(ViewModel._find_socket(arms, "socket_hand.R"), "right hand socket")
	assert_not_null(ViewModel._find_socket(arms, "socket_hand.L"), "left hand socket")


## (swing, roll) in degrees of a hand bone's rotation off its rest relative to its forearm: the
## roll about the forearm's axis, the swing (the wrist's bend) what is left.
func _wrist(rest: Basis, pose: Quaternion) -> Vector2:
	var rel := Quaternion(rest.inverse() * Basis(pose))
	var axis: Vector3 = (rest.inverse() * Vector3.UP).normalized()
	var p: float = Vector3(rel.x, rel.y, rel.z).dot(axis)
	var twist := Quaternion(axis.x * p, axis.y * p, axis.z * p, rel.w)
	twist = twist.normalized() if twist.length() > 1e-6 else Quaternion.IDENTITY
	var swing: Quaternion = rel * twist.inverse()
	var roll: float = rad_to_deg(twist.get_angle())
	return Vector2(rad_to_deg(swing.get_angle()), roll if roll <= 180.0 else 360.0 - roll)


func test_baked_wrists_stay_in_a_wrists_range() -> void:
	# ADR-0045: the holds once bent the wrists ~90° at rest and up to 140° mid-swing. Every frame
	# of every baked action, each hand's bend off its forearm stays inside viewmodel.json's wrist
	# range (its widest axis, plus a little for the ellipse's rounding) and its roll inside the
	# forearm's.
	if not ResourceLoader.exists(ARMS):
		pending("arms not built (make assets)")
		return
	var arms: Node = (load(ARMS) as PackedScene).instantiate()
	autofree(arms)
	var anim: AnimationPlayer = arms.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var skel: Skeleton3D = arms.find_child("Skeleton3D", true, false) as Skeleton3D
	if anim == null or skel == null or skel.find_bone("middle_1.R") < 0:
		pending("arms predate ADR-0045's rig (rebuild fp_arms)")
		return
	var w: Dictionary = ViewModelHolds.config().get("wrist", {})
	var bend_max: float = maxf(float(w.get("flex", 65)), float(w.get("extend", 55))) + 3.0
	var roll_max: float = float(w.get("roll", 95)) + 3.0
	var bad: PackedStringArray = []
	var checked: int = 0
	for name: StringName in anim.get_animation_list():
		if not String(name).begins_with("fp_"):
			continue
		var a: Animation = anim.get_animation(name)
		for sd: String in ["R", "L"]:
			var bone: int = skel.find_bone("hand.%s" % sd)
			var tr: int = -1
			for t: int in a.get_track_count():
				if a.track_get_type(t) == Animation.TYPE_ROTATION_3D and String(a.track_get_path(t)).ends_with(":hand.%s" % sd):
					tr = t
			if tr < 0:
				continue
			var rest: Basis = skel.get_bone_rest(bone).basis
			var worst := Vector2.ZERO
			for k: int in 31:
				var v: Vector2 = _wrist(rest, a.rotation_track_interpolate(tr, a.length * k / 30.0))
				worst = worst.max(v)
			checked += 1
			if worst.x > bend_max or worst.y > roll_max:
				bad.append("%s %s: wrist bent %.0f°, rolled %.0f°" % [name, sd, worst.x, worst.y])
	assert_gt(checked, 60, "every action's hands measured")
	assert_eq(bad, PackedStringArray(), "bend <= %.0f°, roll <= %.0f°" % [bend_max, roll_max])
