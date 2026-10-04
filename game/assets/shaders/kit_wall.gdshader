// POI kit walls and floors (docs/POI_KIT.md). One shader for every wall/floor piece of every
// building: each MultiMesh instance carries its finishes in INSTANCE_CUSTOM
//   r = finish slice for side A (UV2.x == 0: wall face toward +Z / floor top)
//   g = finish slice for side B (UV2.x == 1: wall face toward -Z / floor underside = ceiling)
//   b = decay 0..1 (stains, mould, grime overlay), a = per-instance random seed 0..1
// Finishes are projected in world space (metre scale) so pieces tile seamlessly. Edges/reveals
// (UV2.x == 0.5) take side A's finish slightly darkened.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;

uniform sampler2DArray finish_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray finish_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray finish_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Ceiling finishes come from the wall array when this is a floor material.
uniform sampler2DArray side_b_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool side_b_from_other_array = false;
uniform bool has_finishes = false;
uniform sampler2D decay_albedo : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D decay_orm : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform bool has_decay = false;
uniform float texture_scale = 1.0;
uniform bool is_floor = false;
// Fallback palette (when finish arrays are not generated yet): index -> colour.
const vec3 PALETTE[16] = vec3[](
	vec3(0.78, 0.76, 0.71), vec3(0.62, 0.66, 0.58), vec3(0.55, 0.6, 0.66), vec3(0.7, 0.62, 0.5),
	vec3(0.52, 0.36, 0.3), vec3(0.45, 0.5, 0.42), vec3(0.8, 0.78, 0.68), vec3(0.4, 0.38, 0.36),
	vec3(0.48, 0.34, 0.22), vec3(0.36, 0.26, 0.18), vec3(0.6, 0.6, 0.58), vec3(0.3, 0.3, 0.3),
	vec3(0.66, 0.54, 0.4), vec3(0.42, 0.44, 0.47), vec3(0.72, 0.7, 0.62), vec3(0.5, 0.45, 0.4));

global uniform float hm_wetness;

varying vec3 v_world;
varying vec3 v_wn;
varying flat vec4 v_custom;
varying float v_side;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_custom = INSTANCE_CUSTOM;
	v_side = UV2.x;
}

vec2 proj_uv() {
	vec3 n = abs(v_wn);
	vec2 uv;
	if (n.y > 0.7) {
		uv = v_world.xz;
	} else if (n.x > n.z) {
		uv = vec2(v_world.z, -v_world.y);
	} else {
		uv = vec2(v_world.x, -v_world.y);
	}
	return uv * texture_scale;
}

void fragment() {
	bool side_b = v_side > 0.75;
	bool edge = v_side > 0.25 && v_side < 0.75;
	float slice = side_b ? v_custom.g : v_custom.r;
	vec2 uv = proj_uv();
	vec3 albedo;
	vec3 orm = vec3(1.0, 0.85, 0.0);
	vec3 nmap = vec3(0.5, 0.5, 1.0);
	if (has_finishes) {
		if (side_b && side_b_from_other_array) {
			albedo = texture(side_b_albedo, vec3(uv, slice)).rgb;
		} else {
			albedo = texture(finish_albedo, vec3(uv, slice)).rgb;
			orm = texture(finish_orm, vec3(uv, slice)).rgb;
			nmap = texture(finish_normal, vec3(uv, slice)).rgb;
		}
	} else {
		albedo = PALETTE[int(clamp(round(slice), 0.0, 15.0))];
	}
	if (edge) {
		albedo *= 0.82;
	}
	// Vertex colour: R = AO, G = wear (exposed lath / chipped paint), B = variation.
	albedo *= mix(0.55, 1.0, COLOR.r);
	albedo = mix(albedo, albedo * vec3(0.78, 0.72, 0.64), COLOR.g * 0.8);
	float decay = v_custom.b;
	if (has_decay && decay > 0.01) {
		vec4 d = texture(decay_albedo, uv * 0.37 + v_custom.a * 7.0);
		float lowness = 1.0 - clamp((fract(v_world.y / 3.0) * 3.0) / 2.8, 0.0, 1.0);
		float m = clamp(d.a * decay * (0.6 + 0.6 * lowness), 0.0, 1.0);
		albedo = mix(albedo, d.rgb, m);
		orm.g = mix(orm.g, texture(decay_orm, uv * 0.37).g, m);
	} else {
		albedo *= 1.0 - decay * 0.25;
	}
	ALBEDO = albedo;
	AO = orm.r * COLOR.r;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = clamp(orm.g - hm_wetness * 0.2 * float(is_floor), 0.05, 1.0);
	METALLIC = orm.b;
	NORMAL_MAP = nmap;
	NORMAL_MAP_DEPTH = 0.8;
}
