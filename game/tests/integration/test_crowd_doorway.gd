extends GutTest
## Crowd separation in a doorway (TD-011): six Hollowed pushed at a 1.4 m gap in a wall get through
## without jittering or circling at it. They are steered straight at the goal (no nav mesh: what is
## measured is the separation against physics), each physics tick driving Enemy._move.

const GOAL := Vector3(0, 0, -6)


func after_each() -> void:
	Crowd.enabled = true
	Crowd.reset()


func _box(at: Vector3, size: Vector3) -> void:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	add_child_autofree(b)
	b.global_position = at


## Runs the crowd for up to `seconds` (or until all are through); returns {through, jitter (mean
## turn of the heading, degrees a tick, while moving), seconds, all_through_s (-1: not all)}.
func _run(seconds: float) -> Dictionary:
	_box(Vector3(0, -0.5, 0), Vector3(40, 1, 40))
	# A wall along x at z = 0 with a 1.4 m doorway in the middle.
	_box(Vector3(-5.7, 1.2, 0), Vector3(10, 2.4, 0.3))
	_box(Vector3(5.7, 1.2, 0), Vector3(10, 2.4, 0.3))
	var bodies: Array[Enemy] = []
	for i: int in 6:
		var e := Enemy.new()
		e.setup(StringName("test:crowd%d" % i), Content.enemy(&"hollow"), null, {"tier": "normal"})
		add_child_autofree(e)
		e.set_physics_process(false)
		e.global_position = Vector3(-1.5 + float(i % 3) * 1.5, 0.05, 3.0 + float(i / 3) * 1.4)
		bodies.append(e)
	await get_tree().physics_frame
	var turn: float = 0.0
	var samples: int = 0
	var last: Dictionary = {}
	var t: float = 0.0
	var all_through: float = -1.0
	var dt: float = 1.0 / float(Engine.physics_ticks_per_second)
	while t < seconds:
		await get_tree().physics_frame
		t += dt
		var left: int = 0
		for e: Enemy in bodies:
			var to: Vector3 = GOAL - e.global_position
			to.y = 0.0
			if to.length() < 0.8:
				continue
			left += 1
			e._move(to.normalized() * 2.5, dt, 5.0)
			var v := Vector2(e.velocity.x, e.velocity.z)
			if v.length() > 0.3:
				var a: float = v.angle()
				if last.has(e):
					turn += absf(rad_to_deg(angle_difference(float(last[e]), a)))
					samples += 1
				last[e] = a
		if all_through < 0.0 and bodies.all(func(b: Enemy) -> bool: return b.global_position.z < -0.5):
			all_through = t
			break
		if left == 0:
			break
	var through: int = 0
	for e: Enemy in bodies:
		if e.global_position.z < -0.5:
			through += 1
	return {"through": through, "jitter": turn / maxf(1.0, float(samples)), "seconds": t, "all_through_s": all_through}


func test_six_get_through_a_doorway_without_jitter() -> void:
	var r: Dictionary = await _run(10.0)
	gut.p("crowd: %s" % r)
	assert_eq(int(r["through"]), 6, "all six through the doorway")
	assert_lt(float(r["jitter"]), 4.0, "headings turn smoothly (degrees a tick)")


## The same run with separation off, for comparison in the log (physics alone also gets them
## through, slower and with more shoving).
func test_baseline_without_separation_runs() -> void:
	Crowd.enabled = false
	var off: Dictionary = await _run(10.0)
	gut.p("no crowd: %s" % off)
	assert_gt(float(off["seconds"]), 0.0)
