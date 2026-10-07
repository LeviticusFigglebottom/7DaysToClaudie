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
## The neck counts as torso: hits at the collar were landing as 2.2x headshots.
const LIMB_BONES: Dictionary = {
	"head": ["head"], "torso": ["chest", "spine", "hips", "neck"],
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
## The stand-in is a four-legged one (a hound's, ADR-0034).
var _quad: bool = false
## Idle and shamble variants this body plays (ADR-0028): action name -> the variant to play.
var _variants: Dictionary = {}
const SENSE_SHADER: String = "res://assets/shaders/sleeper_sense.gdshader"
static var _sense_material: ShaderMaterial = null
## Warmer, stronger rim for a POI guardian (ADR-0018): Sleeper Sense tells the loot room's
## keeper from the rest.
static var _sense_guardian_material: ShaderMaterial = null


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


## Sleeper Sense outline (a shared see-through rim overlay) on or off; `guardian` uses the warm
## guardian rim.
func set_sensed(on: bool, guardian: bool = false) -> void:
	if _root == null:
		return
	var mat: ShaderMaterial = null
	if on and ResourceLoader.exists(SENSE_SHADER):
		if guardian:
			if _sense_guardian_material == null:
				_sense_guardian_material = ShaderMaterial.new()
				_sense_guardian_material.shader = load(SENSE_SHADER)
				_sense_guardian_material.set_shader_parameter(&"tint", Color(1.0, 0.58, 0.28))
				_sense_guardian_material.set_shader_parameter(&"strength", 0.42)
			mat = _sense_guardian_material
		else:
			if _sense_material == null:
				_sense_material = ShaderMaterial.new()
				_sense_material.shader = load(SENSE_SHADER)
			mat = _sense_material
	for g: Node in _root.find_children("*", "GeometryInstance3D", true, false):
		(g as GeometryInstance3D).material_overlay = mat
	if _root is GeometryInstance3D:
		(_root as GeometryInstance3D).material_overlay = mat


static func model_path(id: String) -> String:
	return "res://assets/generated/models/%s.glb" % id


## Population looks (ADR-0028): the body a Hollowed wears comes from the population its sleeper
## post, its building or its region asks for (PopulationDef); `fallback`, the type's own pick,
## otherwise, and while that body's model is not generated yet.
static func population_body(enemy: Node, fallback: String) -> String:
	var e := enemy as Enemy
	if e == null or e.def == null:
		return fallback
	var pop: StringName = population_of(e)
	if pop == &"":
		return fallback
	var pd := Content.get_def(&"population", pop) as PopulationDef
	if pd == null:
		return fallback
	var body: String = pd.pick(e.def.id, String(e.entity_id))
	if body == "" or not ResourceLoader.exists(model_path(body)):
		return fallback
	return body


## The population a Hollowed belongs to: its sleeper entry's, else its building's, else its
## region's (region.json "population"); &"" for none.
static func population_of(e: Enemy) -> StringName:
	var w: Node = Game.world
	if w == null:
		return &""
	var pois: Node = w.get(&"pois")
	if e.poi_id != &"" and pois != null:
		var inst := (pois.get(&"instances") as Dictionary).get(e.poi_id) as PoiInstance
		if inst != null and inst.layout != null:
			for sl: Dictionary in inst.layout.sleepers:
				if str(sl.get("sid", "")) == String(e.sleeper_id) and sl.has("population"):
					return StringName(str(sl["population"]))
			if inst.layout.def.population != &"":
				return inst.layout.def.population
	var wd: WorldDef = w.get(&"world_def") as WorldDef
	if wd != null and e.is_inside_tree():
		var rid: String = wd.region_at(e.global_position.x, e.global_position.z)
		if rid != "":
			return StringName(str(wd.region_data(rid).get("population", "")))
	return &""


## The Blister's pustules burst (the skin shader swaps them for torn craters, ADR-0028).
func burst() -> void:
	if _placeholder or _root == null:
		return
	for g: Node in _root.find_children("*", "GeometryInstance3D", true, false):
		(g as GeometryInstance3D).set_instance_shader_parameter(&"hollow_burst", 1.0)


## height_scale is uniform; body_scale widens/deepens a frame on top of it (the Rammer's bulk is
## now built into its own mesh: ADR-0028).
func build(p_model_id: String, height_scale: float, body_scale := Vector3.ONE) -> void:
	model_id = population_body(get_parent(), p_model_id)
	scale = body_scale * height_scale
	var path: String = model_path(model_id)
	# A model regenerated but not imported yet has a sidecar and no scene: the stand-in body then,
	# rather than a Hollowed with no body at all.
	var ps: PackedScene = load(path) as PackedScene if ResourceLoader.exists(path) else null
	if ps != null:
		_root = ps.instantiate() as Node3D
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
				if String(a).begins_with("idle") or a in [&"walk", &"walk_b", &"walk_limp", &"run", &"crawl", &"attack_structure", &"eat", &"track"]:
					res.loop_mode = Animation.LOOP_LINEAR
			_pick_variants()
	else:
		_placeholder = true
		_root = _make_quad_placeholder() if model_id.begins_with("animals/") else _make_placeholder()
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


## A hound's stand-in until `make assets` (ADR-0034): a lean grey-brown body on four legs, its
## head held low and forward (+Z).
func _make_quad_placeholder() -> Node3D:
	_quad = true
	var root := Node3D.new()
	var coat := StandardMaterial3D.new()
	coat.albedo_color = Color(0.36, 0.33, 0.29)
	var growth := StandardMaterial3D.new()
	growth.albedo_color = Color(0.78, 0.74, 0.62)
	var parts: Array = [
		["body_torso", Vector3(0, 0.55, 0), Vector3(PI * 0.5, 0, 0), Vector2(0.15, 0.85), coat],
		["body_head", Vector3(0, 0.66, 0.5), Vector3(PI * 0.5, 0, 0), Vector2(0.09, 0.32), coat],
		["growth", Vector3(0, 0.7, -0.05), Vector3(PI * 0.5, 0, 0), Vector2(0.06, 0.4), growth],
		["leg_fl", Vector3(-0.09, 0.26, 0.26), Vector3.ZERO, Vector2(0.035, 0.52), coat],
		["leg_fr", Vector3(0.09, 0.26, 0.26), Vector3.ZERO, Vector2(0.035, 0.52), coat],
		["leg_hl", Vector3(-0.09, 0.26, -0.28), Vector3.ZERO, Vector2(0.04, 0.52), coat],
		["leg_hr", Vector3(0.09, 0.26, -0.28), Vector3.ZERO, Vector2(0.04, 0.52), coat],
	]
	for p: Array in parts:
		var mi := MeshInstance3D.new()
		mi.name = p[0]
		var c := CapsuleMesh.new()
		var dims: Vector2 = p[3]
		c.radius = dims.x
		c.height = dims.y
		c.material = p[4]
		mi.mesh = c
		mi.position = p[1]
		mi.rotation = p[2]
		root.add_child(mi)
		_segments[String(p[0])] = mi
	return root


## Each body settles on one idle (sway, head loll or twitching) and a third of them limp hard in
## place of dragging a foot, so a crowd does not move in step. Deterministic per Hollowed.
func _pick_variants() -> void:
	var key: String = "%s:%s" % [model_id, str(get_parent().get(&"entity_id")) if get_parent() != null else ""]
	# Through an RNG: the raw FNV hash's low bits barely change between ids like "e:1", "e:2"
	# (nearly every body took the same idle).
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("variants:" + key)
	var idles: Array[StringName] = [&"idle"]
	for v: StringName in [&"idle_b", &"idle_c"]:
		if anim.has_animation(v):
			idles.append(v)
	_variants[&"idle"] = idles[rng.randi() % idles.size()]
	if anim.has_animation(&"walk_limp") and rng.randf() < 1.0 / 3.0:
		_variants[&"walk_b"] = &"walk_limp"


func has_anim(n: StringName) -> bool:
	return anim != null and anim.has_animation(n)


## Plays (cross-fading) an animation; `speed` scales playback. Falls back through `alts`.
func play(n: StringName, speed: float = 1.0, blend: float = 0.25, alts: Array[StringName] = []) -> void:
	if anim == null:
		current_anim = n
		return
	var name_to_play: StringName = _variants.get(n, n)
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


## Seconds an animation lasts at speed 1 (`fallback` when the body lacks it).
func clip_length(n: StringName, fallback: float = 0.0) -> float:
	return anim.get_animation(n).length if has_anim(n) else fallback


## Cross-fade into a one-shot (s), by clip: a blow cuts in fast but not on the frame, heavier clips
## ease in, the get-up blends out of the lying pose; anything else ONCE_BLEND.
const ONCE_BLEND: float = 0.12
const BLEND_IN: Dictionary = {
	&"hit_front": 0.06, &"hit_back": 0.06, &"stagger": 0.08, &"knockdown": 0.08, &"stumble": 0.18,
	&"attack_a": 0.14, &"attack_b": 0.14, &"crawl_attack": 0.14, &"wake_lie": 0.2, &"scream": 0.2,
	&"death_front": 0.1, &"death_back": 0.1,
}


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
	if String(name_to_play).begins_with("death"):
		# whatever kills it bursts the pustules it carries (only the Blister has any)
		burst()
	current_anim = name_to_play
	anim.play(name_to_play, float(BLEND_IN.get(name_to_play, ONCE_BLEND)), 1.0)
	anim.speed_scale = speed
	return anim.get_animation(name_to_play).length / maxf(speed, 0.05)


## Holds the pose it is in (a sleeper killed where it sat or lay stays that way).
func freeze() -> void:
	if anim != null:
		anim.pause()


## Placeholder bodies get a little procedural life (sway / lean while moving).
func animate_placeholder(delta: float, speed: float, lying: bool) -> void:
	if not _placeholder:
		return
	_bob_t += delta * (2.0 + speed * 2.5)
	if _quad:
		# a lope: the body rocks nose to tail, lying on its side once down
		_root.rotation = Vector3(0, 0, PI * 0.5) if lying else Vector3(sin(_bob_t * 1.5) * 0.05 * minf(speed, 4.0), 0, 0)
		_root.position = Vector3(0, 0.0 if lying else absf(sin(_bob_t * 1.5)) * 0.03 * minf(speed, 4.0), 0)
		return
	if lying:
		_root.rotation = Vector3(-PI * 0.5, 0, 0)
		_root.position = Vector3(0, 0.2, 0.9)
		return
	_root.rotation = Vector3(-0.12 - speed * 0.04, 0, sin(_bob_t) * 0.06)
	_root.position = Vector3(0, absf(sin(_bob_t)) * 0.03, 0)


## Which limb a world-space hit point belongs to.
func limb_at(world_pos: Vector3, owner_body: Node3D) -> String:
	if skeleton != null:
		# Distance to each bone as a segment (joint to the next joint), not to its joint alone: a hit
		# mid-thigh is nearer the hip joint than the knee, and used to count as the torso.
		var best: String = "torso"
		var best_d: float = INF
		var sx: Transform3D = skeleton.global_transform
		for limb: String in LIMB_BONES:
			for bone_name: String in LIMB_BONES[limb]:
				var bi: int = skeleton.find_bone(bone_name)
				if bi < 0:
					continue
				var pose: Transform3D = skeleton.get_bone_global_pose(bi)
				var a: Vector3 = sx * pose.origin
				var kids: PackedInt32Array = skeleton.get_bone_children(bi)
				# A bone without children (head, hands, feet) reaches along its own axis.
				var b: Vector3 = sx * skeleton.get_bone_global_pose(kids[0]).origin if not kids.is_empty() \
					else sx * (pose.origin + pose.basis.y.normalized() * (0.22 if bone_name == "head" else 0.1))
				var d: float = world_pos.distance_to(Geometry3D.get_closest_point_to_segment(world_pos, a, b))
				if d < best_d:
					best_d = d
					best = limb
		return best
	var local: Vector3 = owner_body.global_transform.affine_inverse() * world_pos
	if _quad:
		return "head" if local.z > 0.38 * scale.z else "torso"
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
	var gib_scene: PackedScene = load(gib_path) as PackedScene if ResourceLoader.exists(gib_path) else null
	if gib_scene != null:
		var gibs: Node = gib_scene.instantiate()
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
