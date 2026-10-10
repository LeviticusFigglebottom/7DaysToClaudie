extends GutTest
## A speaker's jaw (TD-309): the loudness envelope of a voice line opens the jaw on its syllables
## and shuts it in the pauses; on Ezra's skeleton it opens downward.


func _wav(parts: Array) -> AudioStreamWAV:
	# parts: [[seconds, amplitude], ...] of a 200 Hz tone at 22050 Hz, 16-bit mono.
	var sr: int = 22050
	var data := PackedByteArray()
	for p: Array in parts:
		var n: int = int(float(p[0]) * sr)
		var start: int = data.size()
		data.resize(start + n * 2)
		for i: int in n:
			data.encode_s16(start + i * 2, int(float(p[1]) * 32000.0 * sin(TAU * 200.0 * float(i) / float(sr))))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = sr
	w.data = data
	return w


func test_the_envelope_follows_the_syllables() -> void:
	var env: PackedFloat32Array = JawFlap.envelope(_wav([[0.3, 0.0], [0.3, 0.9], [0.3, 0.0], [0.3, 0.45]]))
	assert_almost_eq(float(env.size()), 1.2 * JawFlap.RATE, 2.0, "30 frames a second")
	assert_eq(JawFlap.at(env, 0.1), 0.0, "shut before he speaks")
	assert_gt(JawFlap.at(env, 0.45), 0.9, "wide on the loud syllable")
	assert_eq(JawFlap.at(env, 0.75), 0.0, "shut in the pause")
	var soft: float = JawFlap.at(env, 1.05)
	assert_between(soft, 0.3, 0.6, "half open on the quiet one")
	assert_eq(JawFlap.at(env, 5.0), 0.0, "shut past the end")
	assert_eq(JawFlap.envelope(AudioStreamGenerator.new()).size(), 0, "a stream it can't read keeps the jaw still")


func test_ezra_opens_his_jaw_downward() -> void:
	var path: String = "res://assets/generated/models/characters/ezra_vane.glb"
	if not ResourceLoader.exists(path):
		pass_test("ezra not generated: nothing to pose")
		return
	var root: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	add_child_autofree(root)
	var sk: Skeleton3D = root.find_child("Skeleton3D", true, false) as Skeleton3D
	var jaw: int = sk.find_bone("jaw")
	assert_gt(jaw, -1, "his skeleton has a jaw")
	var flap := JawFlap.new()
	sk.add_child(flap)
	# A modifier's pose holds only until the skin is drawn (then the skeleton restores its own): read
	# it the moment the modification is done.
	var seen: Array[Vector3] = [Vector3.ZERO]
	var read := func() -> void: seen[0] = sk.get_bone_global_pose(jaw).basis.y
	flap.modification_processed.connect(read)
	var shut: Vector3 = sk.get_bone_global_pose(jaw).basis.y
	flap.open = 1.0
	# In game the animation poses the skeleton every frame; a bare model needs a nudge to run its
	# modifiers.
	sk.set_bone_pose_rotation(jaw, sk.get_bone_pose_rotation(jaw))
	await get_tree().process_frame
	await get_tree().process_frame
	var opened: Vector3 = seen[0]
	assert_gt(rad_to_deg(shut.angle_to(opened)), JawFlap.MAX_DEG * 0.8, "turns by its full angle")
	assert_lt(opened.y, shut.y, "the chin drops (the jaw opens down, not up)")
