// Lakes and rivers: depth-based absorption, refraction of the screen, two scrolling normal maps
// (rivers flow along UV.y), shoreline foam, rain ripples via hm_wetness, Fresnel sky reflection
// from the environment. Rivers set flow_speed > 0.
shader_type spatial;
render_mode blend_mix, depth_draw_always, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D normal_a : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_b : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D foam_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;
uniform vec4 shallow_color : source_color = vec4(0.16, 0.22, 0.18, 1.0);
uniform vec4 deep_color : source_color = vec4(0.03, 0.06, 0.07, 1.0);
uniform float absorption = 0.55;
uniform float flow_speed = 0.0;
uniform float normal_scale = 0.06;
uniform float normal_strength = 0.6;
uniform float refraction = 0.025;
uniform float foam_width = 0.6;

global uniform vec4 hm_wind;
global uniform float hm_wetness;

varying vec3 v_world;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 wuv = v_world.xz * normal_scale;
	vec2 drift = hm_wind.xy * TIME * (0.004 + 0.01 * hm_wind.z);
	vec2 flow = vec2(0.0, -TIME * flow_speed) ;
	vec2 uv1 = (flow_speed > 0.0 ? UV * vec2(1.0, 1.0) * 1.5 + flow : wuv + drift);
	vec2 uv2 = (flow_speed > 0.0 ? UV * 3.1 + flow * 1.7 + vec2(0.37, 0.11) : wuv * 2.3 - drift * 1.4 + vec2(0.31, 0.73));
	vec3 n1 = texture(normal_a, uv1).rgb;
	vec3 n2 = texture(normal_b, uv2).rgb;
	vec3 nrm = normalize(mix(n1, n2, 0.5) * 2.0 - 1.0);
	// Rain ripples: extra high-frequency normal noise.
	if (hm_wetness > 0.05) {
		vec3 n3 = texture(normal_b, wuv * 9.0 + vec2(TIME * 0.05, -TIME * 0.07)).rgb * 2.0 - 1.0;
		nrm = normalize(nrm + n3 * hm_wetness * 0.6);
	}
	// Water depth from the depth buffer.
	float depth = textureLod(depth_tex, SCREEN_UV, 0.0).r;
	vec4 upos = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	float scene_z = -upos.z / upos.w;
	float surf_z = -VERTEX.z;
	float thickness = max(scene_z - surf_z, 0.0);
	vec2 ruv = SCREEN_UV + nrm.xy * refraction * clamp(thickness, 0.0, 1.0);
	vec3 behind = textureLod(screen_tex, ruv, 0.0).rgb;
	float t = 1.0 - exp(-thickness * absorption);
	vec3 water_col = mix(shallow_color.rgb, deep_color.rgb, clamp(thickness / 6.0, 0.0, 1.0));
	vec3 col = mix(behind * vec3(0.85, 0.92, 0.9), water_col, t);
	float foam = (1.0 - smoothstep(0.0, foam_width, thickness)) * texture(foam_tex, wuv * 3.0 + drift).r;
	col = mix(col, vec3(0.8, 0.82, 0.8), foam * 0.6);
	ALBEDO = col;
	ROUGHNESS = mix(0.03, 0.12, hm_wetness);
	METALLIC = 0.0;
	SPECULAR = 0.6;
	NORMAL_MAP = nrm * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = normal_strength;
	EMISSION = vec3(0.0);
}
