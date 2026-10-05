// The Bloom's fruiting bodies and rooting mounds (ADR-0025): pale, waxy, faintly translucent flesh.
// Double-sided (thin caps and gills; Godot flips the normal on back faces). Vertex colour from
// tools/assetgen/blender/generators/veg_fungus.py: R = baked AO, G = gills / underside, B = thinness
// (margins and gills let light through). At night the gills and the felt's threads glow faintly.
// Ground cover (VegetationManager) carries its fade distance as a negative INSTANCE_CUSTOM.a.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/bloom.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float uv_scale = 1.0;
uniform float normal_strength = 1.0;
uniform float ao_strength : hint_range(0.0, 1.0) = 0.9;
// Light through the thin parts (B), toward this colour.
uniform float translucency : hint_range(0.0, 2.0) = 0.8;
uniform vec4 translucent_tint : source_color = vec4(0.92, 0.95, 0.86, 1.0);
// Gills and undersides (G) are greyer and darker than the cap.
uniform vec4 gill_tint : source_color = vec4(0.78, 0.78, 0.74, 1.0);
// Night glow: the gills (G) of caps; for the felt, its brightest threads (albedo above `glow_from`).
uniform float glow_energy = 0.06;
uniform float glow_gills = 1.0;
uniform float glow_from : hint_range(0.0, 1.0) = 1.0;
uniform float glow_felt = 0.0;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	if (INSTANCE_CUSTOM.a < 0.0) {
		VERTEX *= 1.0 - smoothstep(-INSTANCE_CUSTOM.a * 0.8, -INSTANCE_CUSTOM.a, distance(origin, CAMERA_POSITION_WORLD));
	}
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec4 a = texture(albedo_tex, uv);
	vec3 orm = texture(orm_tex, uv).rgb;
	vec3 col = a.rgb * tint.rgb;
	col = mix(col, col * gill_tint.rgb, COLOR.g);
	float rough = orm.g;
	// Wet caps darken a little and turn slick.
	float wet = hm_wetness * (1.0 - COLOR.g * 0.6);
	col *= mix(1.0, 0.8, wet);
	rough = mix(rough, 0.12, wet * 0.8);
	float snow = hm_snow * smoothstep(0.55, 0.85, v_world_normal.y) * (1.0 - COLOR.g);
	col = mix(col, vec3(0.86, 0.88, 0.92), snow);
	ALBEDO = col * mix(1.0, COLOR.r, ao_strength);
	ROUGHNESS = rough;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.3;
	NORMAL_MAP = texture(normal_tex, uv).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	BACKLIGHT = col * translucent_tint.rgb * translucency * (0.25 + 0.75 * COLOR.b);
	float threads = COLOR.g * glow_gills + glow_felt * smoothstep(glow_from, min(1.0, glow_from + 0.15), dot(a.rgb, vec3(0.333)));
	if (threads > 0.0) {
		EMISSION = hm_bloom_glow(threads * (0.4 + 0.6 * COLOR.r) * (1.0 - snow), v_world_pos.xz, TIME) * glow_energy;
	}
}
