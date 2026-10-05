extends GutTest
## Idle and shamble variants (ADR-0028): each Hollowed settles on one idle (sway, head loll or
## twitching) and a share of them limp hard, deterministically per Hollowed, so a crowd does not
## move in step; bodies without the variant actions keep the base ones.


func _visual(entity: String, actions: Array[StringName]) -> EnemyVisual:
	var e := Enemy.new()
	e.entity_id = StringName(entity)
	var v := EnemyVisual.new()
	e.add_child(v)
	v.model_id = "characters/hollow_a"
	var ap := AnimationPlayer.new()
	var lib := AnimationLibrary.new()
	for a: StringName in actions:
		lib.add_animation(a, Animation.new())
	ap.add_animation_library(&"", lib)
	v.add_child(ap)
	v.anim = ap
	v._pick_variants()
	return v


func _free(v: EnemyVisual) -> void:
	v.get_parent().free()


func test_variants_are_deterministic_per_hollowed() -> void:
	var all: Array[StringName] = [&"idle", &"idle_b", &"idle_c", &"walk", &"walk_b", &"walk_limp"]
	var a := _visual("sl:tamsin_clinic:waiting_1", all)
	var b := _visual("sl:tamsin_clinic:waiting_1", all)
	assert_eq(a._variants, b._variants, "the same Hollowed moves the same way on every visit")
	_free(a)
	_free(b)


func test_a_crowd_mixes_its_idles_and_limps() -> void:
	var all: Array[StringName] = [&"idle", &"idle_b", &"idle_c", &"walk", &"walk_b", &"walk_limp"]
	var idles: Dictionary = {}
	var limps: int = 0
	var n: int = 300
	for i: int in n:
		var v := _visual("e:%d" % i, all)
		idles[v._variants[&"idle"]] = int(idles.get(v._variants[&"idle"], 0)) + 1
		if v._variants.get(&"walk_b", &"") == &"walk_limp":
			limps += 1
		_free(v)
	assert_eq(idles.size(), 3, "all three idles in a crowd: %s" % [idles])
	for k: StringName in idles:
		assert_gt(int(idles[k]), n / 6, "%s is common enough" % k)
	assert_almost_eq(float(limps), n / 3.0, n * 0.1, "about a third limp hard")


func test_bodies_without_variants_keep_the_base_actions() -> void:
	var base: Array[StringName] = [&"idle", &"walk", &"walk_b"]
	var v := _visual("e:1", base)
	assert_eq(v._variants[&"idle"], &"idle")
	assert_false(v._variants.has(&"walk_b"), "no limp action, no swap")
	_free(v)
