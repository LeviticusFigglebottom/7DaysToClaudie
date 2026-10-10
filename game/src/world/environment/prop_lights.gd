class_name PropLights
extends RefCounted
## Burning light sources on props (ADR-0023). Power has been out in the valley since the Cordon
## went up, so what still burns is what somebody keeps fed: candles, kerosene and propane lanterns,
## wood stoves and burn barrels that the buildings' stories light (`"lit": true` on a POI prop).
## PropDef.light_for() decides whether a prop's condition variant can burn at all (a destroyed
## lantern stays dark, mains fixtures never light); this builds what a burning one shows:
##  * its light at the prop's offset, flickering if it is a flame;
##  * its own mesh instance with `light_lit` set, so its glow materials (std_surface
##    `light_source`: flames, embers, lamp globes, lenses) shine and its flames exist at all;
##  * for fires (`"fx": "fire"`), flames rising off the embers and a crackle.

## Instance uniform (std_surface, instance_index 4): 1 lights the instance's glow materials.
const LIT_PARAM := &"light_lit"


## Turns the glow materials of one drawn instance on or off.
static func set_lit(gi: GeometryInstance3D, on: bool) -> void:
	if RenderCaps.instance_uniforms():
		gi.set_instance_shader_parameter(LIT_PARAM, 1.0 if on else 0.0)


## A burning prop's mesh, drawn on its own (batched props share one instance-uniform value) so its
## flame or globe glows. `indoor` keeps rain and snow off it, as PoiBuilder's indoor batches do.
static func lit_mesh(model: String, xf: Transform3D, indoor: bool) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = "Lit_" + model.get_file()
	mi.mesh = ModelLibrary.mesh(model, "box")
	mi.transform = xf
	set_lit(mi, true)
	if indoor and RenderCaps.instance_uniforms():
		mi.set_instance_shader_parameter(&"weather_exposure", 0.0)
	return mi


## The light of a burning prop placed at `xf`: `l` is PropDef.light_for(condition).
static func light_node(l: Dictionary, xf: Transform3D) -> Node3D:
	var off: Array = l.get("offset", [0.0, 1.0, 0.0])
	var at: Vector3 = xf * Vector3(float(off[0]), float(off[1]), float(off[2]))
	var flicker: float = float(l.get("flicker", 0.0))
	var light: OmniLight3D = FlickerLight.new() if flicker > 0.0 else OmniLight3D.new()
	if light is FlickerLight:
		(light as FlickerLight).flicker = flicker
	light.name = "PropLight"
	light.light_color = Color.html(str(l.get("color", "#ffcf96")))
	light.light_energy = float(l.get("energy", 1.0))
	light.omni_range = float(l.get("range", 6.0))
	light.shadow_enabled = bool(l.get("shadow", false))
	if light.shadow_enabled:
		light.add_to_group(&"shadow_light_budget")
	light.position = at
	if str(l.get("fx", "")) == "fire":
		_add_fire(light, float(l.get("fx_size", 0.4)))
	return light


## Flames licking up off a fire's embers (just under the light) and its crackle.
static func _add_fire(light: OmniLight3D, size: float) -> void:
	var loop := AudioStreamPlayer3D.new()
	loop.name = "Crackle"
	loop.stream = Audio.stream(&"sfx/fire_loop_small")
	loop.bus = &"SFX"
	loop.unit_size = 3.0
	loop.max_distance = 26.0
	loop.volume_db = -8.0
	loop.autoplay = loop.stream != null
	light.add_child(loop)
	var flames: GPUParticles3D = flames(size)
	if flames != null:
		flames.position = Vector3(0.0, -0.2, 0.0)
		light.add_child(flames)


## A small flame column from the generated flipbook (none headless, where nothing draws).
static func flames(size: float) -> GPUParticles3D:
	if DisplayServer.get_name() == "headless":
		return null
	var p := GPUParticles3D.new()
	p.name = "Flames"
	p.amount = 18
	p.lifetime = 0.8
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.emission_sphere_radius = size * 0.45
	m.direction = Vector3.UP
	m.spread = 10.0
	m.initial_velocity_min = 0.35
	m.initial_velocity_max = 0.8
	m.gravity = Vector3(0.0, 0.5, 0.0)
	m.scale_min = 0.7
	m.scale_max = 1.2
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.82, 0.45, 1.0))
	g.set_color(1, Color(0.55, 0.12, 0.04, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	p.process_material = m
	var q := QuadMesh.new()
	q.size = Vector2(size * 0.7, size)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	var tex: String = "res://assets/generated/textures/fx_fire_flipbook.png"
	if ResourceLoader.exists(tex):
		mat.albedo_texture = load(tex)
		mat.particles_anim_h_frames = 8
		mat.particles_anim_v_frames = 8
		mat.particles_anim_loop = true
		m.anim_speed_min = 1.0
		m.anim_speed_max = 1.4
		m.anim_offset_max = 1.0
	q.material = mat
	p.draw_pass_1 = q
	return p
