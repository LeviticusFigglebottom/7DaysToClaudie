// Far terrain tiles (whole map, coarse): vertex colour = baked dominant ground colour; slope rock
// tint and snow/wetness; discards inside the near-terrain square.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 discard_rect = vec4(1.0, 1.0, -1.0, -1.0);
uniform vec4 rock_color : source_color = vec4(0.42, 0.41, 0.39, 1.0);
uniform sampler2D macro_variation : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float macro_scale = 0.0035;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	if (discard_rect.z > discard_rect.x && v_world_pos.x > discard_rect.x && v_world_pos.x < discard_rect.z
			&& v_world_pos.z > discard_rect.y && v_world_pos.z < discard_rect.w) {
		discard;
	}
	vec3 gn = normalize(v_world_normal);
	vec3 alb = COLOR.rgb;
	alb = mix(alb, rock_color.rgb, smoothstep(0.78, 0.6, gn.y));
	float mv = texture(macro_variation, v_world_pos.xz * macro_scale).r;
	alb *= 0.8 + mv * 0.4;
	float snow = max(hm_snow, smoothstep(900.0, 1250.0, v_world_pos.y)) * smoothstep(0.55, 0.85, gn.y);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	alb *= mix(1.0, 0.65, hm_wetness * 0.8);
	ALBEDO = alb;
	ROUGHNESS = mix(0.95, 0.4, hm_wetness);
	NORMAL = normalize((VIEW_MATRIX * vec4(gn, 0.0)).xyz);
}
