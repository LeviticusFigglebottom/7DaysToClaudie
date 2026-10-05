// Foliage cards / fronds / grass: alpha-cut, double-sided, translucent, wind + seasons.
// Vertex colour: R = AO, A = wind weight. hm_season = (spring, summer, autumn, winter) weights.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/wind.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic;
uniform float alpha_scissor : hint_range(0.0, 1.0) = 0.42;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 spring_tint : source_color = vec4(1.05, 1.08, 0.95, 1.0);
uniform vec4 summer_tint : source_color = vec4(1.0);
uniform vec4 autumn_tint : source_color = vec4(1.0);
uniform vec4 winter_tint : source_color = vec4(0.85, 0.85, 0.82, 1.0);
// Deciduous species drop leaves in winter (alpha threshold rises with the winter weight).
uniform float winter_leaf_loss : hint_range(0.0, 1.0) = 0.0;
uniform float translucency : hint_range(0.0, 2.0) = 0.6;
uniform float sway_height = 18.0;
uniform float stiffness = 1.0;
uniform float flutter_strength = 1.0;
uniform float ao_strength : hint_range(0.0, 1.0) = 0.85;
uniform float normal_strength = 1.0;
uniform float roughness = 0.75;

global uniform vec4 hm_season;
global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_normal;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	// Ground cover (VegetationManager's ground layer) carries its fade distance as a negative
	// INSTANCE_CUSTOM.a and shrinks away plant by plant over the last fifth of it, so nothing pops
	// out in whole blocks. Other MultiMeshes leave .a >= 0.
	if (INSTANCE_CUSTOM.a < 0.0) {
		VERTEX *= 1.0 - smoothstep(-INSTANCE_CUSTOM.a * 0.8, -INSTANCE_CUSTOM.a, distance(origin, CAMERA_POSITION_WORLD));
	}
	vec3 wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.xz += hm_plant_sway(VERTEX, origin, sway_height, stiffness, TIME);
	VERTEX += hm_flutter(wpos, NORMAL, COLOR.a * flutter_strength, TIME);
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec4 season = hm_season.x * spring_tint + hm_season.y * summer_tint + hm_season.z * autumn_tint + hm_season.w * winter_tint;
	float wsum = max(0.001, hm_season.x + hm_season.y + hm_season.z + hm_season.w);
	vec3 col = a.rgb * tint.rgb * (season.rgb / wsum);
	float threshold = mix(alpha_scissor, 1.01, hm_season.w / wsum * winter_leaf_loss);
	vec3 orm = texture(orm_tex, UV).rgb;
	float snow = hm_snow * smoothstep(0.3, 0.8, v_world_normal.y);
	col = mix(col, vec3(0.85, 0.87, 0.9), snow);
	ALBEDO = col * mix(1.0, COLOR.r, ao_strength);
	ALPHA = a.a;
	ALPHA_SCISSOR_THRESHOLD = threshold;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	ROUGHNESS = mix(roughness * orm.g, 0.2, hm_wetness * 0.7);
	AO = orm.r;
	BACKLIGHT = col * translucency;
}
