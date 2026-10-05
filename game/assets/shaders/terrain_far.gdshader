// Far terrain tiles (whole map, coarse): vertex colour = baked dominant ground colour; slope rock
// tint and snow/wetness; discards inside the near-terrain square.
//
// Forest canopy from afar: in coarse regions (built ones draw real impostor trees) TerrainManager
// raises the far mesh by canopy_height x canopy cover, so forested hills keep their silhouette and
// the mesh normals see the forest edges. COLOR.a packs the cover (high 4 bits) and the deciduous
// share (low 4 bits). They are decoded per vertex, before interpolation would mix the bits.
// * Near the near square's edge, where the tile is cut away, the raise is taken back down. A raised
//   edge there would show sky underneath.
// * The canopy shades as crowns: dark gaps and lit tops from world-space noise, with matching
//   normal relief so a low sun picks the canopy out. The crown detail fades out where it would
//   alias.
// * Conifers stay dark green; deciduous crowns follow the season (bare in winter).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 discard_rect = vec4(1.0, 1.0, -1.0, -1.0);
uniform vec4 rock_color : source_color = vec4(0.42, 0.41, 0.39, 1.0);
uniform sampler2D macro_variation : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float macro_scale = 0.0035;
// Set by TerrainManager: the raise its far mesh already carries at full cover.
uniform float canopy_height = 17.0;
uniform float crown_size = 7.0;
uniform float canopy_edge_fade = 96.0;

// Crown colours (linear albedo, lit tops; gaps are a third of it).
const vec3 CONIFER = vec3(0.085, 0.12, 0.062);
// Deciduous by season: spring, summer, autumn, winter (bare twigs).
const vec3 LEAFY[4] = vec3[](vec3(0.11, 0.16, 0.05), vec3(0.075, 0.12, 0.045), vec3(0.26, 0.18, 0.05), vec3(0.11, 0.1, 0.085));

global uniform float hm_wetness;
global uniform float hm_snow;
global uniform vec4 hm_season;

varying vec3 v_world_pos;
varying vec3 v_world_normal;
varying float v_canopy;
varying float v_decid;

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	vec4 h = fract(sin(vec4(dot(i, vec2(127.1, 311.7)), dot(i + vec2(1.0, 0.0), vec2(127.1, 311.7)),
		dot(i + vec2(0.0, 1.0), vec2(127.1, 311.7)), dot(i + vec2(1.0, 1.0), vec2(127.1, 311.7)))) * 43758.5453);
	return mix(mix(h.x, h.y, f.x), mix(h.z, h.w, f.x), f.y);
}

float crowns(vec2 p) {
	return 0.65 * value_noise(p) + 0.35 * value_noise(p * 2.7 + vec2(3.1, 1.7));
}

void vertex() {
	float packed = round(COLOR.a * 255.0);
	float canopy = floor(packed / 16.0) / 15.0;
	v_decid = mod(packed, 16.0) / 15.0;
	float keep = 1.0;
	if (discard_rect.z > discard_rect.x) {
		vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
		vec2 out_d = max(max(discard_rect.xy - wp.xz, wp.xz - discard_rect.zw), vec2(0.0));
		keep = smoothstep(0.0, canopy_edge_fade, length(out_d));
	}
	VERTEX.y -= canopy * (1.0 - keep) * canopy_height;
	v_canopy = canopy * keep;
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
	float mv = texture(macro_variation, v_world_pos.xz * macro_scale).r;
	// Rock on steep ground, but not on the steep sides the canopy raise makes at forest edges.
	float under = smoothstep(0.0, 0.6, v_canopy);
	alb = mix(alb, rock_color.rgb, smoothstep(0.78, 0.6, gn.y) * (1.0 - under));
	if (v_canopy > 0.01) {
		vec2 p = v_world_pos.xz / crown_size;
		float detail = 1.0 - smoothstep(0.35, 1.2, length(fwidth(p)));
		float c = crowns(p);
		float e = 0.25;
		float cx = crowns(p + vec2(e, 0.0));
		float cz = crowns(p + vec2(0.0, e));
		float lit = mix(0.5, smoothstep(0.3, 0.75, c), detail);
		vec4 sw = hm_season / max(0.001, dot(hm_season, vec4(1.0)));
		vec3 leafy = LEAFY[0] * sw.x + LEAFY[1] * sw.y + LEAFY[2] * sw.z + LEAFY[3] * sw.w;
		vec3 top = mix(CONIFER, leafy, v_decid);
		vec3 canopy_col = mix(top * 0.33, top, lit) * (0.8 + 0.4 * mv);
		// Thin cover shows the ground between crowns.
		alb = mix(alb, canopy_col, under);
		gn = normalize(gn + vec3(-(cx - c) / e, 0.0, -(cz - c) / e) * 0.8 * detail * v_canopy);
	}
	alb *= 0.8 + mv * 0.4;
	float snow = max(hm_snow, smoothstep(900.0, 1250.0, v_world_pos.y)) * smoothstep(0.55, 0.85, gn.y);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	alb *= mix(1.0, 0.65, hm_wetness * 0.8);
	ALBEDO = alb;
	ROUGHNESS = mix(0.95, 0.4, hm_wetness);
	NORMAL = normalize((VIEW_MATRIX * vec4(gn, 0.0)).xyz);
}
