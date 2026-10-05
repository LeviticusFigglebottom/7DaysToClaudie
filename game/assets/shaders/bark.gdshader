// Tree trunks/branches: tiling bark + vertex AO + moss mask (B), sways with the same wind as
// the foliage of the same plant. Stumps and logs use std_surface (they do not sway).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/wind.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Moss fronds have their own relief: under a moss patch the bark furrows give way to it.
uniform sampler2D moss_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec2 uv_scale = vec2(1.0, 1.0);
uniform float normal_strength = 1.2;
uniform float moss_amount : hint_range(0.0, 1.0) = 0.0;
uniform float sway_height = 18.0;
uniform float stiffness = 1.0;
uniform float ao_strength : hint_range(0.0, 1.0) = 1.0;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_normal;

void vertex() {
	VERTEX.xz += hm_plant_sway(VERTEX, MODEL_MATRIX[3].xyz, sway_height, stiffness, TIME);
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 alb = texture(albedo_tex, uv).rgb * tint.rgb;
	vec3 orm = texture(orm_tex, uv).rgb;
	float rough = orm.g;
	vec3 nrm = texture(normal_tex, uv).rgb;
	if (moss_amount > 0.001) {
		vec3 ma = texture(moss_albedo_tex, uv * 0.7).rgb;
		// Moss grows on the shaded/wet side and low on the trunk (COLOR.b from the generator).
		float m = smoothstep(0.35, 0.7, COLOR.b * moss_amount + (ma.g - 0.3) * 0.5);
		alb = mix(alb, ma, m);
		rough = mix(rough, 0.95, m);
		nrm = mix(nrm, texture(moss_normal_tex, uv * 0.7).rgb, m);
	}
	float wet = hm_wetness * 0.8;
	alb *= mix(1.0, 0.55, wet);
	rough = mix(rough, 0.15, wet);
	float snow = hm_snow * smoothstep(0.5, 0.85, v_world_normal.y);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	ALBEDO = alb * mix(1.0, COLOR.r, ao_strength);
	ROUGHNESS = rough;
	AO = orm.r;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
}
