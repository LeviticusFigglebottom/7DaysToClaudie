class_name FpMaterials
extends RefCounted
## First-person materials (ADR-0029). The arms and the held item draw with their own field of view
## (data/config/viewmodel.json `fov`), so a wide world FOV setting or the sprint FOV kick doesn't
## stretch them, and with their depth squeezed towards the near plane (`z_clip_scale`), so a tool
## never sinks into a wall you stand against. This is Godot's own viewmodel technique
## (BaseMaterial3D use_fov_override / use_z_clip_scale): BaseMaterial3Ds get those flags, and
## ShaderMaterials (std_surface, std_glass...) get a copy of their shader with the same lines
## added at the end of vertex(). Converted shaders are cached, and each converted material is kept
## on its source (metadata), so swapping items doesn't recompile anything while a material made at
## runtime (a torch flame per lighting, the tether screen) is freed with its node instead of piling
## up in a static cache; set_fov() retunes every live one (reading the tether narrows it).

## Render layer 2 ("viewmodel" in project settings): other cameras can leave the arms out.
const LAYER: int = 1 << 1
const FP_UNIFORMS: String = "uniform float fp_fov = 58.0;\nuniform float fp_z_clip_scale = 0.04;\n"
const FP_VERTEX: String = """
	// First-person viewmodel (FpMaterials, ADR-0029): own field of view, depth squeezed forward.
	Z_CLIP_SCALE = fp_z_clip_scale;
	if (!IN_SHADOW_PASS) {
		float fp_flip_y = sign(PROJECTION_MATRIX[1][1]);
		float fp_aspect = PROJECTION_MATRIX[1][1] / PROJECTION_MATRIX[0][0];
		float fp_f = fp_flip_y / tan(fp_fov * PI / 360.0);
		PROJECTION_MATRIX[0][0] = fp_f / fp_aspect;
		PROJECTION_MATRIX[1][1] = fp_f;
	}
"""

static var fov: float = 58.0
static var z_clip: float = 0.04
## Metadata on a source material naming its first-person copy.
const META: StringName = &"fp_material"

## source Shader -> first-person Shader (or the source itself when it couldn't be converted)
static var _shaders: Dictionary = {}
## Every first-person material made, held weakly, for set_fov().
static var _live: Array[WeakRef] = []
## The converted shaders (a set): only their materials take the fp_* uniforms.
static var _converted: Dictionary = {}


static func configure(cfg: Dictionary) -> void:
	z_clip = float(cfg.get("z_clip_scale", z_clip))
	set_fov(float(cfg.get("fov", fov)))


## Converts every mesh under `root` (surface overrides, so shared meshes stay untouched), puts it
## on the viewmodel layer, keeps it out of shadows and stops it being culled at the screen edge
## (the viewmodel FOV can be wider than the camera's).
static func apply(root: Node) -> void:
	if root is GeometryInstance3D:
		var gi: GeometryInstance3D = root
		gi.layers = LAYER
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		gi.extra_cull_margin = 2.0
		if gi.material_override != null:
			gi.material_override = fp_material(gi.material_override)
		if root is MeshInstance3D:
			var mi: MeshInstance3D = root
			if mi.mesh != null:
				for i: int in mi.mesh.get_surface_count():
					var m: Material = mi.get_active_material(i)
					if m != null:
						mi.set_surface_override_material(i, fp_material(m))
		elif root is GPUParticles3D:
			var gp: GPUParticles3D = root
			for i: int in gp.draw_passes:
				var pm: Mesh = gp.get_draw_pass_mesh(i)
				if pm is PrimitiveMesh and (pm as PrimitiveMesh).material != null:
					(pm as PrimitiveMesh).material = fp_material((pm as PrimitiveMesh).material)
	for c: Node in root.get_children():
		apply(c)


static func fp_material(mat: Material) -> Material:
	if mat == null:
		return null
	if _is_fp(mat):
		return mat
	if mat.has_meta(META):
		return mat.get_meta(META) as Material
	var out: Material = mat
	if mat is BaseMaterial3D:
		var b: BaseMaterial3D = mat.duplicate()
		b.use_fov_override = true
		b.fov_override = fov
		b.use_z_clip_scale = true
		b.z_clip_scale = z_clip
		out = b
	elif mat is ShaderMaterial and (mat as ShaderMaterial).shader != null:
		var sm: ShaderMaterial = mat
		var sh: Shader = fp_shader(sm.shader)
		if sh != sm.shader:
			var n: ShaderMaterial = sm.duplicate()
			n.shader = sh
			n.set_shader_parameter(&"fp_fov", fov)
			n.set_shader_parameter(&"fp_z_clip_scale", z_clip)
			out = n
	if out != mat:
		mat.set_meta(META, out)
		if _live.size() > 256:
			_prune()
		_live.append(weakref(out))
	return out


## Already a first-person material (made by fp_material()).
static func _is_fp(mat: Material) -> bool:
	if mat is BaseMaterial3D:
		return (mat as BaseMaterial3D).use_z_clip_scale
	return mat is ShaderMaterial and _converted.has((mat as ShaderMaterial).shader)


## Drops the weak references whose materials are gone.
static func _prune() -> void:
	var alive: Array[WeakRef] = []
	for w: WeakRef in _live:
		if w.get_ref() != null:
			alive.append(w)
	_live = alive


## The shader with the first-person lines at the end of vertex() (one is added when it has none).
## Returns the source unchanged if it isn't a spatial shader or already does its own.
static func fp_shader(src: Shader) -> Shader:
	if _shaders.has(src):
		return _shaders[src]
	var code: String = inject(src.code)
	var out: Shader = src
	if code != "":
		out = Shader.new()
		out.code = code
		_converted[out] = true
	_shaders[src] = out
	return out


## Source code with the viewmodel projection added, or "" when it can't (not spatial, already has
## Z_CLIP_SCALE, or unbalanced braces).
static func inject(code: String) -> String:
	if not code.contains("shader_type spatial") or code.contains("Z_CLIP_SCALE"):
		return ""
	var at: int = code.find("void vertex()")
	if at < 0:
		var fn_at: int = _first_function(code)
		var decl: String = FP_UNIFORMS + "void vertex() {" + FP_VERTEX + "}\n\n"
		return code.insert(fn_at, decl) if fn_at >= 0 else code + "\n" + decl
	var open: int = code.find("{", at)
	if open < 0:
		return ""
	var depth: int = 0
	var close: int = -1
	for i: int in range(open, code.length()):
		var ch: String = code[i]
		if ch == "{":
			depth += 1
		elif ch == "}":
			depth -= 1
			if depth == 0:
				close = i
				break
	if close < 0:
		return ""
	return code.substr(0, at) + FP_UNIFORMS + code.substr(at, close - at) + FP_VERTEX + code.substr(close)


## Index of the first top-level function definition (where uniforms can still be declared).
static func _first_function(code: String) -> int:
	var re := RegEx.new()
	re.compile("\\n(void|float|vec[234]|mat[34]|int|bool)\\s+\\w+\\s*\\(")
	var m: RegExMatch = re.search(code)
	return m.get_start() + 1 if m != null else -1


## Retunes every first-person material to a new viewmodel field of view (degrees).
static func set_fov(deg: float) -> void:
	fov = deg
	_prune()
	for w: WeakRef in _live:
		var m: Material = w.get_ref() as Material
		if m is BaseMaterial3D:
			(m as BaseMaterial3D).fov_override = deg
			(m as BaseMaterial3D).z_clip_scale = z_clip
		elif m is ShaderMaterial and _converted.has((m as ShaderMaterial).shader):
			(m as ShaderMaterial).set_shader_parameter(&"fp_fov", deg)
			(m as ShaderMaterial).set_shader_parameter(&"fp_z_clip_scale", z_clip)
