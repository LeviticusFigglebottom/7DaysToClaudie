class_name EnemyVisual
extends Node3D
## Presentation of a Hollowed body: the generated skinned model (docs/CHARACTERS.md), its
## animations with cross-fades, segment hiding + stump caps for dismemberment, and gib spawning.
## Falls back to a procedural stand-in body (no skeleton) if the model is not generated yet.

const SEGMENTS: Dictionary = {
	"head": ["body_head"],
	"arm_l": ["body_upper_arm.L", "body_forearm.L"],
	"arm_r": ["body_upper_arm.R", "body_forearm.R"],
	"leg_l": ["body_thigh.L", "body_shin.L"],
	"leg_r": ["body_thigh.R", "body_shin.R"],
}
const STUMPS: Dictionary = {
	"head": "stump_neck", "arm_l": "stump_shoulder.L", "arm_r": "stump_shoulder.R",
	"leg_l": "stump_hip.L", "leg_r": "stump_hip.R",
}
const GIBS: Dictionary = {"head": "gib_head", "arm_l": "gib_arm_upper", "arm_r": "gib_arm_upper", "leg_l": "gib_leg_upper", "leg_r": "gib_leg_upper"}
## Limb -> bone used to locate hits.
const LIMB_BONES: Dictionary = {
	"head": ["head", "neck"], "torso": ["chest", "spine", "hips"],
	"arm_l": ["upper_arm.L", "forearm.L", "hand.L"], "arm_r": ["upper_arm.R", "forearm.R", "hand.R"],
	"leg_l": ["thigh.L", "shin.L", "foot.L"], "leg_r": ["thigh.R", "shin.R", "foot.R"],
}

var model_id: String = ""
var anim: AnimationPlayer = null
var skeleton: Skeleton3D = null
var current_anim: StringName = &""
var _root: Node3D = null
var _placeholder: bool = false
var _segments: Dictionary = {}
var _stumps: Dictionary = {}
var _bob_t: float = 0.0
const SENSE_SHADER: String = "res://assets/shaders/sleeper_sense.gdshader"
static var _sense_material: ShaderMaterial = null


## Godot replaces "." in node names on import ("body_upper_arm.L" -> "body_upper_arm_L"); map
## the side suffix back so lookups can use the Blender names from docs/CHARACTERS.md.
static func canonical_name(nm: String) -> String:
	if nm.length() > 2 and (nm.ends_with("_L") or nm.ends_with("_R")):
		return nm.substr(0, nm.length() - 2) + "." + nm.right(1)
	return nm


## Infected-tier glow (std_surface `bloom_glow` instance uniform) on every part of the body.
func set_bloom(glow: float) -> void:
	if _placeholder or _root == null:
		return
	for g: Node in _root.find_children("*", "GeometryInstance3D", true, false):
		(g as GeometryInstance3D).set_instance_shader_parameter(&"bloom_glow", glow)


## Sleeper Sense outline (a shared see-through rim overlay) on or off.
func set_sensed(on: bool) -> void:
	if _root == null:
		return
	if on and _sense_material == null and ResourceLoader.exists(SENSE_SHADER):
		_sense_material = ShaderMaterial.new()
		_sense_material.shader = load(SENSE_SHADER)
	for g: Node in _root.find_children("*", "GeometryInstance3D", true, false):
		(g as GeometryInstance3D).material_overlay = _sense_material if on else null
	if _root is GeometryInstance3D:
		(_root as GeometryInstance3D).material_overlay = _sense_material if on else null


static func model_path(id: String) -> String:
	return "res://assets/generated/models/%s.glb" % id


## height_scale is uniform; body_scale widens/deepens a frame (Rammer bulk) on top of it.
func build(p_model_id: String, height_scale: float, body_scale := Vector3.ONE) -> void:
	model_id = p_model_id
	scale = body_scale * height_scale
	var path: String = model_path(model_id)
	if ResourceLoader.exists(path):
		_root = (load(path) as PackedScene).instantiate() as Node3D
		add_child(_root)
		anim = _root.find_child("AnimationPlayer", true, false) as AnimationPlayer
		skeleton = _root.find_child("Skeleton3D", true, false) as Skeleton3D
		for n: Node in _root.find_children("*", "MeshInstance3D", true, false):
			var nm: String = canonical_name(String(n.name))
			_segments[nm] = n
			if nm.begins_with("stump_"):
				(n as MeshInstance3D).visible = false
				_stumps[nm] = n
		if anim != null:
			for a: StringName in anim.get_animation_list():
				var res: Animation = anim.get_animation(a)
				if String(a).begins_with("idle") or a in [&"walk", &"walk_b", &"run", &"crawl", &"attack_structure", &"eat"]:
					res.loop_mode = Animation.LOOP_LINEAR
	else:
		_placeholder = true
		_root = _make_placeholder()
		add_child(_root)


func _make_placeholder() -> Node3D:
	var root := Node3D.new()
	var skin := StandardMaterial3D.new()
	skin.albedo_color = Color(0.55, 0.56, 0.52)
	var cloth := StandardMaterial3D.new()
	cloth.albedo_color = Color(0.22, 0.24, 0.28)
	var parts: Array = [
		["body_torso", CapsuleMesh.new(), Vector3(0, 1.15, 0), cloth, Vector2(0.2, 0.65)],
		["body_head", SphereMesh.new(), Vector3(0, 1.63, 0.02), skin, Vector2(0.12, 0.26)],
		["body_upper_arm.L", CapsuleMesh.new(), Vector3(-0.27, 1.12, 0.05), skin, Vector2(0.06, 0.62)],
		["body_upper_arm.R", CapsuleMesh.new(), Vector3(0.27, 1.12, 0.05), skin, Vector2(0.06, 0.62)],
		["body_thigh.L", CapsuleMesh.new(), Vector3(-0.1, 0.45, 0), cloth, Vector2(0.08, 0.9)],
		["body_thigh.R", CapsuleMesh.new(), Vector3(0.1, 0.45, 0), cloth, Vector2(0.08, 0.9)],
	]
	for p: Array in parts:
		var mi := MeshInstance3D.new()
		mi.name = p[0]
		var m: PrimitiveMesh = p[1]
		var dims: Vector2 = p[4]
		if m is CapsuleMesh:
			(m as CapsuleMesh).radius = dims.x
			(m as CapsuleMesh).height = dims.y
		elif m is SphereMesh:
			(m as SphereMesh).radius = dims.x
			(m as SphereMesh).height = dims.y
		m.material = p[3]
		mi.mesh = m
		mi.position = p[2]
		root.add_child(mi)
		_segments[String(p[0])] = mi
	return root


func has_anim(n: StringName) -> bool:
	return anim != null and anim.has_animation(n)


## Plays (cross-fading) an animation; `speed` scales playback. Falls back through `alts`.
func play(n: StringName, speed: float = 1.0, blend: float = 0.25, alts: Array[StringName] = []) -> void:
	if anim == null:
		current_anim = n
		return
	var name_to_play: StringName = n
	if not anim.has_animation(name_to_play):
		name_to_play = &""
		for a: StringName in alts:
			if anim.has_animation(a):
				name_to_play = a
				break
		if name_to_play == &"":
			return
	if current_anim == name_to_play and anim.is_playing():
		anim.speed_scale = speed
		return
	current_anim = name_to_play
	anim.play(name_to_play, blend, 1.0)
	anim.speed_scale = speed


func play_once(n: StringName, speed: float = 1.0, alts: Array[StringName] = []) -> float:
	if anim == null:
		current_anim = n
		return 0.6
	var name_to_play: StringName = n if anim.has_animation(n) else &""
	if name_to_play == &"":
		for a: StringName in alts:
			if anim.has_animation(a):
				name_to_play = a
				break
	if name_to_play == &"":
		return 0.6
	current_anim = name_to_play
	anim.play(name_to_play, 0.12, 1.0)
	anim.speed_scale = speed
	return anim.get_animation(name_to_play).length / maxf(speed, 0.05)


## Placeholder bodies get a little procedural life (sway / lean while moving).
func animate_placeholder(delta: float, speed: float, lying: bool) -> void:
	if not _placeholder:
		return
	_bob_t += delta * (2.0 + speed * 2.5)
	if lying:
		_root.rotation = Vector3(-PI * 0.5, 0, 0)
		_root.position = Vector3(0, 0.2, 0.9)
		return
	_root.rotation = Vector3(-0.12 - speed * 0.04, 0, sin(_bob_t) * 0.06)
	_root.position = Vector3(0, absf(sin(_bob_t)) * 0.03, 0)


## Which limb a world-space hit point belongs to.
func limb_at(world_pos: Vector3, owner_body: Node3D) -> String:
	if skeleton != null:
		var best: String = "torso"
		var best_d: float = INF
		for limb: String in LIMB_BONES:
			for bone_name: String in LIMB_BONES[limb]:
				var bi: int = skeleton.find_bone(bone_name)
				if bi < 0:
					continue
				var bp: Vector3 = skeleton.global_transform * skeleton.get_bone_global_pose(bi).origin
				var d: float = bp.distance_to(world_pos)
				if d < best_d:
					best_d = d
					best = limb
		return best
	var local: Vector3 = owner_body.global_transform.affine_inverse() * world_pos
	var h: float = local.y / maxf(scale.y, 0.5)
	if h > 1.48:
		return "head"
	if h < 0.85:
		return "leg_l" if local.x < 0.0 else "leg_r"
	if absf(local.x) > 0.2:
		return "arm_l" if local.x < 0.0 else "arm_r"
	return "torso"


## Hides a limb's segments, shows its stump and throws a gib. Returns the gib node (or null).
func sever(limb: String, impulse: Vector3) -> Node3D:
	var world_pos: Vector3 = global_position + Vector3.UP * 1.2
	for seg: String in SEGMENTS.get(limb, []):
		var mi: MeshInstance3D = _segments.get(seg)
		if mi != null:
			world_pos = mi.global_transform * mi.get_aabb().get_center()
			mi.visible = false
	var stump: MeshInstance3D = _stumps.get(STUMPS.get(limb, ""))
	if stump != null:
		stump.visible = true
	return _spawn_gib(limb, world_pos, impulse)


func _spawn_gib(limb: String, pos: Vector3, impulse: Vector3) -> Node3D:
	var parent: Node = get_tree().current_scene if is_inside_tree() else null
	if parent == null:
		return null
	var mesh: Mesh = null
	var gib_path: String = model_path("characters/gibs")
	if ResourceLoader.exists(gib_path):
		var gibs: Node = (load(gib_path) as PackedScene).instantiate()
		var src: MeshInstance3D = gibs.find_child(String(GIBS.get(limb, "gib_chunk_a")), true, false) as MeshInstance3D
		if src != null:
			mesh = src.mesh
		gibs.free()
	if mesh == null:
		var c := CapsuleMesh.new()
		c.radius = 0.07 if limb != "head" else 0.11
		c.height = 0.4 if limb != "head" else 0.24
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.45, 0.3, 0.28)
		c.material = m
		mesh = c
	return StructureDebris.spawn(parent, mesh, Transform3D(Basis(), pos), Vector3(0.12, 0.3, 0.12), impulse)
