extends SceneTree
## The probe lab (`make probe-lab`): how this Godot handles UPDATE_ONCE interior reflection probes
## that are switched off and on, which decides how PoiManager's probe budget parks far ones
## (game/src/poi/interior_probe_budget.gd, TD-044). 70 closed rooms, each lit only by an emissive
## panel and holding a mirror sphere, are visited one at a time; only the current room's probe is
## on. Modes:
## * `hide`: the others are `visible = false`. Godot 4.7.2 keeps a hidden probe's atlas slot, so
##   past 64 rooms it logs "reflection probe atlas index invalid" and crashes (signal 4).
## * `detach`: the others are taken out of the tree. All 70 rooms light (what the budget does).
## * `base`: the others' RenderingServer base is detached. The slot is freed, but a probe put back
##   this way never renders again: every room is dark (each probe starts switched off).
## Prints `LAB2 <mode> done: ... dark rooms [...]` (a dark room's mirror shows no probe). Re-run it
## after any Godot upgrade before changing the budget.

const N: int = 70
const FRAMES: int = 14
var mode: String = "hide"
var frame: int = 0
var probes: Array[ReflectionProbe] = []
var parent: Node3D
var cam: Camera3D
var lumas: Array = []

func _initialize() -> void:
	for a: String in OS.get_cmdline_user_args():
		mode = a
	parent = Node3D.new()
	root.add_child(parent)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0, 0, 0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_DISABLED
	env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	var we := WorldEnvironment.new()
	we.environment = env
	parent.add_child(we)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.5, 0.5, 0.5)
	var emat := StandardMaterial3D.new()
	emat.albedo_color = Color(0, 0, 0)
	emat.emission_enabled = true
	emat.emission = Color(1.0, 0.6, 0.2)
	emat.emission_energy_multiplier = 4.0
	var mm := StandardMaterial3D.new()
	mm.metallic = 1.0
	mm.roughness = 0.05
	for k: int in N:
		var o := Vector3(k * 20.0, 0, 0)
		for f: Array in [[Vector3(0, -0.05, 0), Vector3(6, 0.1, 6)], [Vector3(0, 3.05, 0), Vector3(6, 0.1, 6)], [Vector3(-3.05, 1.5, 0), Vector3(0.1, 3, 6)],
				[Vector3(3.05, 1.5, 0), Vector3(0.1, 3, 6)], [Vector3(0, 1.5, -3.05), Vector3(6, 3, 0.1)], [Vector3(0, 1.5, 3.05), Vector3(6, 3, 0.1)]]:
			var mi := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = f[1]
			mi.mesh = bm
			mi.material_override = mat
			mi.position = o + f[0]
			parent.add_child(mi)
		var em := MeshInstance3D.new()
		var pm := BoxMesh.new()
		pm.size = Vector3(2.0, 1.0, 0.05)
		em.mesh = pm
		em.material_override = emat
		em.position = o + Vector3(0, 1.5, 2.9)
		parent.add_child(em)
		var sphere := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.6
		sm.height = 1.2
		sphere.mesh = sm
		sphere.material_override = mm
		sphere.position = o + Vector3(0, 1.5, -0.5)
		parent.add_child(sphere)
		var p := ReflectionProbe.new()
		p.size = Vector3(6, 3, 6)
		p.position = o + Vector3(0, 1.5, 0)
		p.interior = true
		p.update_mode = ReflectionProbe.UPDATE_ONCE
		parent.add_child(p)
		probes.append(p)
		_off(p)
	cam = Camera3D.new()
	parent.add_child(cam)
	cam.current = true

func _off(p: ReflectionProbe) -> void:
	if mode == "hide":
		p.visible = false
	elif mode == "base":
		RenderingServer.instance_set_base(p.get_instance(), RID())
	elif p.is_inside_tree():
		parent.remove_child(p)

func _on(p: ReflectionProbe) -> void:
	if mode == "hide":
		p.visible = true
	elif mode == "base":
		RenderingServer.instance_set_base(p.get_instance(), p.get_base())
	elif not p.is_inside_tree():
		parent.add_child(p)

func _process(_delta: float) -> bool:
	var room: int = frame / FRAMES
	var step: int = frame % FRAMES
	if room >= N:
		var bad: PackedStringArray = []
		for k: int in N:
			if float(lumas[k]) < 0.2:
				bad.append(str(k))
		print("LAB2 %s done: %d rooms, dark rooms %s; lumas 60..69 %s" % [mode, N, bad, lumas.slice(60, 70)])
		for p: ReflectionProbe in probes:
			if not p.is_inside_tree():
				p.free()
		quit(0)
		return false
	if step == 0:
		if room > 0:
			_off(probes[room - 1])
		_on(probes[room])
		cam.position = Vector3(room * 20.0, 1.5, 2.0)
		cam.look_at(Vector3(room * 20.0, 1.5, -0.5))
	if step == FRAMES - 1:
		var img: Image = root.get_texture().get_image()
		var lum: float = 0.0
		for dy: int in range(-6, 7, 3):
			for dx: int in range(-6, 7, 3):
				lum += img.get_pixel(img.get_width() / 2 + dx, img.get_height() / 2 + dy).get_luminance()
		lumas.append(snappedf(lum / 25.0, 0.01))
	frame += 1
	return false
