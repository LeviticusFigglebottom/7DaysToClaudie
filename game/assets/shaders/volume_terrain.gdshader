// SDF volume terrain (tunnels, pits, mined faces): world-space triplanar blend of the terrain
// layer arrays — dug earth on top faces, packed dirt on the walls, rock deeper down and on
// steep faces. Shares the layer arrays with the heightmap shader so the hand-off is seamless.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;

uniform sampler2DArray layer_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float layer_tile[16];
uniform int rock_layer = 6;
uniform int dirt_layer = 3;
uniform int top_layer = 0;
uniform float surface_y_fade = 1.5;
uniform bool has_layers = true;

varying vec3 v_world;
varying vec3 v_wn;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec4 tri(sampler2DArray tex, int layer, vec3 p, vec3 w, float tile) {
	vec4 x = texture(tex, vec3(p.zy / tile, float(layer)));
	vec4 y = texture(tex, vec3(p.xz / tile, float(layer)));
	vec4 z = texture(tex, vec3(p.xy / tile, float(layer)));
	return x * w.x + y * w.y + z * w.z;
}

void fragment() {
	vec3 w = pow(abs(v_wn), vec3(4.0));
	w /= (w.x + w.y + w.z);
	float up = clamp(v_wn.y, 0.0, 1.0);
	float steep = 1.0 - smoothstep(0.55, 0.85, up);
	int a = dirt_layer;
	int b = rock_layer;
	float rockiness = clamp(steep * 0.8 + 0.25, 0.0, 1.0);
	vec3 albedo;
	vec3 orm;
	if (has_layers) {
		float ta = layer_tile[a] > 0.0 ? layer_tile[a] : 2.5;
		float tb = layer_tile[b] > 0.0 ? layer_tile[b] : 4.0;
		vec3 ca = tri(layer_albedo, a, v_world, w, ta).rgb;
		vec3 cb = tri(layer_albedo, b, v_world, w, tb).rgb;
		albedo = mix(ca, cb, rockiness);
		vec3 oa = tri(layer_orm, a, v_world, w, ta).rgb;
		vec3 ob = tri(layer_orm, b, v_world, w, tb).rgb;
		orm = mix(oa, ob, rockiness);
	} else {
		albedo = mix(vec3(0.32, 0.24, 0.17), vec3(0.42, 0.41, 0.39), rockiness);
		orm = vec3(1.0, 0.9, 0.0);
	}
	// Freshly cut earth is darker and wetter.
	albedo *= 0.82;
	ALBEDO = albedo;
	AO = orm.r;
	ROUGHNESS = clamp(orm.g, 0.4, 1.0);
	METALLIC = 0.0;
}
