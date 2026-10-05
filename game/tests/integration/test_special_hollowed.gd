extends GutTest
## Special Hollowed abilities against real nodes: Husk armour (headshots only), the Rammer's wall
## charge, and a Blister glob arcing onto its target and leaving a spore puddle.


class Wall:
	extends StaticBody3D
	var taken: float = 0.0

	func take_damage(info: DamageInfo) -> void:
		taken += info.amount


func _floor() -> void:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(60, 1, 60)
	cs.shape = shape
	b.add_child(cs)
	add_child_autofree(b)
	b.global_position = Vector3(0, -0.5, 0)


func _enemy(id: StringName) -> Enemy:
	var e := Enemy.new()
	e.setup(StringName("test:%s" % id), Content.enemy(id), null, {"tier": "normal"})
	add_child_autofree(e)
	return e


func _bone_pos(e: Enemy, bone: String) -> Vector3:
	var sk: Skeleton3D = e.visual.skeleton
	if sk == null:
		return e.global_position + Vector3.UP * (1.65 if bone == "head" else 1.2)
	return sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bone)).origin


func _hit(e: Enemy, at: Vector3, amount: float) -> float:
	var before: float = e.health
	var info := DamageInfo.make(amount, &"slash", &"melee", &"")
	info.hit_pos = at
	info.direction = Vector3.FORWARD
	e.take_damage(info)
	return before - e.health


func test_husk_armour_blunts_body_hits_but_not_headshots() -> void:
	_floor()
	var e: Enemy = _enemy(&"husk")
	await get_tree().physics_frame
	var body: float = _hit(e, _bone_pos(e, "chest"), 50.0)
	var head: float = _hit(e, _bone_pos(e, "head"), 50.0)
	assert_almost_eq(body, 50.0 * (1.0 - 0.65), 1.0, "plates take most of a body blow")
	assert_gt(head, 100.0, "the head is soft (x2.2, no armour)")


func test_rammer_charge_hits_walls_with_everything() -> void:
	_floor()
	var e: Enemy = _enemy(&"rammer")
	var wall := Wall.new()
	add_child_autofree(wall)
	await get_tree().physics_frame
	e._charge_dir = Vector3.FORWARD
	e._charge_impact_structure(wall)
	var ch: Dictionary = Content.enemy(&"rammer").beh("charge", {})
	assert_almost_eq(wall.taken, float(ch["structure_damage"]) * e.structure_mult, 0.01)
	assert_eq(e.state, Enemy.State.STAGGER, "the Rammer reels after hitting a wall")


func test_blister_glob_lands_on_target_and_leaves_a_puddle() -> void:
	_floor()
	await get_tree().physics_frame
	var holder := Node3D.new()
	add_child_autofree(holder)
	var target := Vector3(8, 0, 0)
	Spores.spit(holder, Vector3(0, 1.5, 0), target, Content.enemy(&"blister").beh("spit", {}), &"test")
	var puddle: Node3D = null
	for i: int in 180:
		await get_tree().physics_frame
		for c: Node in holder.get_children():
			if c is Spores.Puddle:
				puddle = c
		if puddle != null:
			break
	assert_not_null(puddle, "the glob splashed")
	if puddle != null:
		assert_lt(Vector2(puddle.global_position.x - target.x, puddle.global_position.z - target.z).length(), 1.5)


func test_hit_zones_follow_bone_segments() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	await get_tree().physics_frame
	if e.visual.skeleton == null:
		pending("character models not built")
		return
	assert_eq(e.visual.limb_at(_bone_pos(e, "neck"), e), "torso", "a hit at the collar is not a headshot")
	assert_eq(e.visual.limb_at(_bone_pos(e, "head") + Vector3.UP * 0.1, e), "head")
	var mid_thigh: Vector3 = _bone_pos(e, "thigh.L").lerp(_bone_pos(e, "shin.L"), 0.5)
	assert_eq(e.visual.limb_at(mid_thigh, e), "leg_l", "mid-thigh is the leg, not the hips")


func test_capsule_fits_the_body_and_crawlers_lie_down() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	var c: Enemy = _enemy(&"dragger")
	await get_tree().physics_frame
	var cap: CapsuleShape3D = e._shape.shape
	assert_gt(cap.height, 1.6)
	assert_almost_eq(e._shape.rotation.x, 0.0, 0.001, "walkers stand upright")
	assert_almost_eq(c._shape.rotation.x, PI * 0.5, 0.001, "crawlers' capsules lie along the body")
	assert_lt(c._shape.position.y, 0.5)
