// Transparent glass and clear plastic: window panes, bottles, lenses (docs/ASSET_PIPELINE.md).
// Same texture slots and common parameters as std_surface, so a material spec only switches
// `shader`. Opacity comes from the albedo alpha when `use_texture_alpha` (the kit's glass texture
// stores 0.2 clean .. 0.9 grime there); otherwise from `opacity`, raised where the albedo is dark
// (dirt) by `grime_amount`. Fresnel makes grazing views more reflective and opaque, which is what
// sells glass under a single sun light.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float uv_scale = 1.0;
uniform bool use_texture_alpha = false;
uniform float opacity : hint_range(0.0, 1.0) = 0.25;
uniform float grime_amount : hint_range(0.0, 1.0) = 0.0;
uniform vec4 grime_color : source_color = vec4(0.16, 0.14, 0.11, 1.0);
uniform float normal_strength : hint_range(0.0, 3.0) = 0.4;
uniform float roughness_mult = 1.0;
uniform float roughness_add = 0.0;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 0.0;
// Lenses in front of a lit bulb (tail lights, lanterns) can glow faintly.
uniform vec4 emission_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy = 0.0;

void fragment() {
	vec2 uv = UV * uv_scale;
	vec4 tex = texture(albedo_tex, uv);
	vec3 orm = texture(orm_tex, uv).rgb;
	vec3 alb;
	float a;
	if (use_texture_alpha) {
		alb = tex.rgb * tint.rgb;
		a = tex.a;
	} else {
		float dirt = clamp((1.0 - dot(tex.rgb, vec3(0.333))) * grime_amount * 2.0, 0.0, 1.0);
		alb = mix(tint.rgb, grime_color.rgb, dirt);
		a = mix(opacity, 0.9, dirt);
	}
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 5.0);
	ALBEDO = alb * mix(1.0, COLOR.r, vertex_ao_strength);
	ALPHA = clamp(a + fres * (1.0 - a) * 0.6, 0.0, 1.0);
	ROUGHNESS = clamp(orm.g * roughness_mult + roughness_add, 0.02, 1.0);
	METALLIC = 0.0;
	SPECULAR = 0.65;
	NORMAL_MAP = texture(normal_tex, uv).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	EMISSION = emission_color.rgb * emission_energy;
}
