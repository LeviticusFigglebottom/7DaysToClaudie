class_name FxLibrary
extends RefCounted
## One-shot particle bursts for impacts (chips, dust, sparks, blood, leaves). Each kind is data
## below; meshes/materials are built once and shared. Uses the generated FX atlases/flipbooks
## (assets/generated/textures/fx_*.png) when present, plain shaded shapes otherwise.

## texture: generated FX atlas (textures/<name>.png); frames: [h, v] atlas cells; anim: play the
## cells over the particle's life (flipbooks) instead of picking one at random.
const KINDS: Dictionary = {
	"wood": {"amount": 14, "life": 0.9, "speed": [2.0, 4.5], "spread": 55.0, "gravity": 9.8, "size": [0.04, 0.08], "color": Color(0.9, 0.8, 0.65), "shape": "billboard", "texture": "fx_wood_chips", "frames": [4, 4]},
	"bark": {"amount": 8, "life": 1.2, "speed": [1.0, 2.5], "spread": 70.0, "gravity": 6.0, "size": [0.04, 0.08], "color": Color(0.45, 0.36, 0.28), "shape": "billboard", "texture": "fx_wood_chips", "frames": [4, 4]},
	"leaves": {"amount": 18, "life": 3.0, "speed": [0.3, 1.2], "spread": 180.0, "gravity": 0.8, "size": [0.05, 0.09], "color": Color(0.2, 0.3, 0.1), "shape": "quad"},
	"dust": {"amount": 10, "life": 1.8, "speed": [0.4, 1.4], "spread": 180.0, "gravity": -0.2, "size": [0.5, 1.1], "color": Color(0.62, 0.58, 0.52, 0.45), "shape": "billboard", "texture": "fx_smoke_flipbook", "frames": [8, 8], "anim": true},
	"dirt": {"amount": 16, "life": 0.9, "speed": [1.5, 3.5], "spread": 50.0, "gravity": 9.8, "size": [0.05, 0.1], "color": Color(1, 1, 1), "shape": "billboard", "texture": "fx_dirt_chunks", "frames": [4, 4]},
	"stone": {"amount": 10, "life": 0.8, "speed": [2.5, 5.0], "spread": 45.0, "gravity": 9.8, "size": [0.03, 0.06], "color": Color(0.7, 0.7, 0.68), "shape": "billboard", "texture": "fx_dirt_chunks", "frames": [4, 4]},
	"sparks": {"amount": 12, "life": 0.35, "speed": [3.0, 7.0], "spread": 40.0, "gravity": 4.0, "size": [0.02, 0.04], "color": Color(1.0, 0.7, 0.3), "shape": "billboard", "texture": "fx_spark", "emissive": 6.0},
	"blood": {"amount": 14, "life": 0.8, "speed": [1.5, 4.0], "spread": 35.0, "gravity": 9.8, "size": [0.06, 0.14], "color": Color(1, 1, 1), "shape": "billboard", "texture": "fx_blood_spray", "frames": [4, 4]},
	"gore": {"amount": 8, "life": 1.4, "speed": [2.0, 4.5], "spread": 50.0, "gravity": 9.8, "size": [0.04, 0.09], "color": Color(0.3, 0.06, 0.05), "shape": "box"},
	"water": {"amount": 16, "life": 0.7, "speed": [1.5, 3.5], "spread": 30.0, "gravity": 9.8, "size": [0.15, 0.3], "color": Color(0.85, 0.9, 0.95, 0.7), "shape": "billboard", "texture": "fx_splash", "frames": [4, 4]},
	"splinters": {"amount": 22, "life": 1.1, "speed": [2.5, 6.0], "spread": 70.0, "gravity": 9.8, "size": [0.05, 0.14], "color": Color(0.95, 0.85, 0.7), "shape": "billboard", "texture": "fx_wood_chips", "frames": [4, 4]},
}

static var _draw: Dictionary = {}


## Wood chips flying off a chop or hit, plus a little bark.
static func spawn_chips(parent: Node, pos: Vector3, normal: Vector3) -> void:
	burst(parent, "wood", pos, normal)
	burst(parent, "bark", pos, normal)


static func burst(parent: Node, kind: String, pos: Vector3, dir: Vector3 = Vector3.UP, scale: float = 1.0) -> GPUParticles3D:
	if parent == null or not parent.is_inside_tree() or not KINDS.has(kind):
		return null
	if DisplayServer.get_name() == "headless":
		return null
	var k: Dictionary = KINDS[kind]
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 0.92
	p.amount = maxi(1, int(float(k["amount"]) * clampf(scale, 0.3, 3.0)))
	p.lifetime = float(k["life"])
	p.local_coords = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.process_material = _process_material(kind, k, dir, scale)
	p.draw_pass_1 = _mesh(kind, k)
	p.visibility_aabb = AABB(Vector3(-4, -4, -4), Vector3(8, 8, 8))
	parent.add_child(p)
	p.global_position = pos
	p.emitting = true
	parent.get_tree().create_timer(p.lifetime + 0.6).timeout.connect(p.queue_free)
	return p


static func _process_material(_kind: String, k: Dictionary, dir: Vector3, scale: float) -> ParticleProcessMaterial:
	var m := ParticleProcessMaterial.new()
	var d: Vector3 = dir.normalized() if dir.length() > 0.01 else Vector3.UP
	m.direction = d
	m.spread = float(k["spread"])
	var sp: Array = k["speed"]
	m.initial_velocity_min = float(sp[0]) * sqrt(scale)
	m.initial_velocity_max = float(sp[1]) * sqrt(scale)
	m.gravity = Vector3(0, -float(k["gravity"]), 0)
	var sz: Array = k["size"]
	m.scale_min = float(sz[0]) / 0.05
	m.scale_max = float(sz[1]) / 0.05
	m.angular_velocity_min = -360.0
	m.angular_velocity_max = 360.0
	m.angle_min = 0.0
	m.angle_max = 360.0
	m.damping_min = 0.5
	m.damping_max = 2.0
	if k.has("frames"):
		if bool(k.get("anim", false)):
			m.anim_speed_min = 1.0
			m.anim_speed_max = 1.0
		else:
			m.anim_offset_min = 0.0
			m.anim_offset_max = 1.0
	m.collision_mode = ParticleProcessMaterial.COLLISION_RIGID
	m.collision_friction = 0.8
	m.collision_bounce = 0.15
	var fade := Gradient.new()
	fade.set_color(0, Color(1, 1, 1, 1))
	fade.set_color(1, Color(1, 1, 1, 0))
	fade.add_point(0.7, Color(1, 1, 1, 1))
	var gt := GradientTexture1D.new()
	gt.gradient = fade
	m.color_ramp = gt
	return m


static func _mesh(kind: String, k: Dictionary) -> Mesh:
	if _draw.has(kind):
		return _draw[kind]
	var mat := StandardMaterial3D.new()
	mat.albedo_color = k["color"]
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.85
	var tex_path: String = "res://assets/generated/textures/%s.png" % str(k.get("texture", ""))
	var textured: bool = k.has("texture") and ResourceLoader.exists(tex_path)
	if textured:
		mat.albedo_texture = load(tex_path)
		if k.has("frames"):
			var fr: Array = k["frames"]
			mat.particles_anim_h_frames = int(fr[0])
			mat.particles_anim_v_frames = int(fr[1])
			mat.particles_anim_loop = false
	var shape: String = str(k["shape"])
	if (k["color"] as Color).a < 1.0 or shape != "box":
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if not textured or kind in ["dust", "water"] else BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	if k.has("emissive"):
		mat.emission_enabled = true
		mat.emission = k["color"]
		mat.emission_energy_multiplier = float(k["emissive"])
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var mesh: PrimitiveMesh
	match shape:
		"box":
			var b := BoxMesh.new()
			b.size = Vector3(0.05, 0.03, 0.05)
			mesh = b
		"quad":
			var q := QuadMesh.new()
			q.size = Vector2(0.05, 0.05)
			mat.cull_mode = BaseMaterial3D.CULL_DISABLED
			mesh = q
		_:
			var q2 := QuadMesh.new()
			q2.size = Vector2(0.05, 0.05)
			mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
			mat.billboard_keep_scale = true
			mesh = q2
	mesh.material = mat
	_draw[kind] = mesh
	return mesh
