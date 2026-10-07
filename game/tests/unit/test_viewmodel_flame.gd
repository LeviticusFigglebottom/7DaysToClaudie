extends GutTest
## Held flames (ViewModel.attach_flame, player report 3): every lit item with a flame socket burns
## in the socket's own space (no world-space trail when the view turns), at its own size (a
## lighter's 2-3 cm teardrop, a torch's hand-span licks), inside a culling box that holds it, with
## the viewmodel's field-of-view materials, and stands up in the world whichever way the hand is
## turned.


func _particles(root: Node) -> Array[GPUParticles3D]:
	var out: Array[GPUParticles3D] = []
	for n: Node in root.find_children("*", "GPUParticles3D", true, false):
		out.append(n as GPUParticles3D)
	return out


## A held item stand-in: the model's root, turned and scaled as a hold would, with the socket deep
## inside.
func _held() -> Node3D:
	var held := Node3D.new()
	held.rotation_degrees = Vector3(-90.0, 30.0, 0.0)
	held.scale = Vector3.ONE * 1.1
	var body := Node3D.new()
	body.name = "Body"
	held.add_child(body)
	var sock := Node3D.new()
	sock.name = "socket_flame"
	sock.position = Vector3(0.0, -0.04, 0.0)
	body.add_child(sock)
	return held


func test_flames_burn_in_the_sockets_space() -> void:
	for id: StringName in [&"lighter", &"torch", &"candle"]:
		var held: Node3D = _held()
		add_child_autofree(held)
		var f: Node3D = ViewModel.attach_flame(held, id)
		assert_not_null(f, "%s: a flame on the socket" % id)
		assert_eq(f.get_parent().name, &"socket_flame", "%s: parented to the held item's socket" % id)
		var ps: Array[GPUParticles3D] = _particles(f)
		assert_gt(ps.size(), 0, "%s: has particles" % id)
		for p: GPUParticles3D in ps:
			assert_true(p.local_coords, "%s/%s: local space, so it can't trail behind a turn" % [id, p.name])
			assert_gt(p.fixed_fps, 0, "%s/%s: fixed steps, so a long frame doesn't put it out" % [id, p.name])
			assert_eq(p.layers, FpMaterials.LAYER, "%s/%s: on the viewmodel layer" % [id, p.name])
			var mat: BaseMaterial3D = (p.draw_pass_1 as PrimitiveMesh).material as BaseMaterial3D
			assert_true(mat.use_fov_override and mat.use_z_clip_scale, "%s/%s: drawn with the viewmodel's FOV" % [id, p.name])
	var bare := Node3D.new()
	add_child_autofree(bare)
	assert_null(ViewModel.attach_flame(bare, &"lighter"), "no socket, no flame")


func test_flames_are_sized_per_item() -> void:
	var lighter: Dictionary = ViewModel.flame_spec(&"lighter")
	var lh: float = ViewModel.flame_height(lighter)
	assert_between(lh - float(lighter["rise"]) + float((lighter["size"] as Array)[1]) * 0.5, 0.018, 0.035,
		"a lighter's flame is 2-3 cm tall")
	assert_lt(float((lighter["size"] as Array)[0]), 0.02, "and narrow")
	var torch: Dictionary = ViewModel.flame_spec(&"torch")
	var th: float = ViewModel.flame_height(torch)
	assert_between(th, 0.12, 0.4, "a torch's flame reaches a hand-span or two")
	assert_gt(th, lh * 4.0, "the torch burns far bigger than the lighter")
	assert_eq(ViewModel.flame_spec(&"candle"), lighter, "an unknown flame burns small")
	for id: StringName in [&"lighter", &"torch"]:
		var spec: Dictionary = ViewModel.flame_spec(id)
		var f: Node3D = ViewModel.build_flame(id)
		var fire: GPUParticles3D = f.get_node("Fire")
		var box: AABB = fire.visibility_aabb
		assert_true(box.has_point(Vector3(0, ViewModel.flame_height(spec) - 0.001, 0)), "%s: the box holds the tip" % id)
		assert_true(box.has_point(Vector3(0, float(spec["rise"]), 0)), "%s: and the base" % id)
		assert_lt(box.size.length(), 1.2 if id == &"torch" else 0.15, "%s: a box the flame's size" % id)
		assert_almost_eq((fire.draw_pass_1 as QuadMesh).size.y, float((spec["size"] as Array)[1]), 1e-6)
		assert_eq(f.find_child("Embers", true, false) != null, id == &"torch", "%s: embers only off the torch" % id)
		f.free()


func test_flame_stands_up_and_leans_against_a_turn() -> void:
	var cam := Basis.from_euler(Vector3(deg_to_rad(-35.0), deg_to_rad(70.0), 0.0))
	var b: Basis = ViewModel.flame_basis(cam, Vector3.ZERO)
	assert_almost_eq(b.y.dot(Vector3.UP), 1.0, 1e-5, "upright in the world however the view is pitched")
	assert_almost_eq(b.determinant(), 1.0, 1e-4, "a rotation, no scale")
	var lean: Basis = ViewModel.flame_basis(Basis(), Vector3(0.2, 0.0, 0.0))
	assert_gt(lean.y.x, 0.1, "leans to the side it is pushed")
	var down: Basis = ViewModel.flame_basis(Basis.from_euler(Vector3(deg_to_rad(-90.0), 0.0, 0.0)), Vector3.ZERO)
	assert_almost_eq(down.determinant(), 1.0, 1e-4, "looking straight down still gives a rotation")


func test_teardrop_is_blue_below_and_yellow_above() -> void:
	var img: Image = ViewModel.teardrop_texture().get_image()
	var base: Color = img.get_pixel(img.get_width() / 2 - 6, int(img.get_height() * 0.88))
	var body: Color = img.get_pixel(img.get_width() / 2, int(img.get_height() * 0.55))
	assert_gt(base.b, base.r, "a blue root")
	assert_gt(body.r, body.b, "a yellow body")
	assert_eq(img.get_pixel(0, 2).a, 0.0, "clear around the point")


## Every lit held item with a flame socket in its generated viewmodel has a flame that fits it.
func test_every_flame_item_is_handled() -> void:
	var checked: int = 0
	for def: ItemDef in Content.all(&"item"):
		var id: StringName = def.id
		if str(def.equip.get("kind", "")) != "light" or (def.equip.get("light", {}) as Dictionary).has("spot_angle"):
			continue
		var path: String = ViewModel.VM_PATH % str(def.equip.get("viewmodel", ""))
		if not ResourceLoader.exists(path):
			continue
		var n: Node3D = (load(path) as PackedScene).instantiate() as Node3D
		var sock: Node3D = n.find_child("socket_flame", true, false) as Node3D
		assert_not_null(sock, "%s: a held flame needs a socket_flame" % id)
		if sock != null:
			assert_true(ViewModel.FLAMES.has(String(id)), "%s: has its own flame size" % id)
			checked += 1
		n.free()
	if checked == 0:
		pass_test("no generated viewmodels to check")
