// Lakes and rivers. The surface is drawn as light it sends to the eye rather than lit as a
// material:
// * Body: the refracted scene behind it (screen texture), absorbed toward the water colour with
//   depth.
// * Reflection: the sky gradient (EnvironmentController publishes it as hm_sky_*). Low reflected
//   rays meet the dark tree line on the banks instead of bright sky: a band of conifer spires of
//   random heights around the horizon, which the ripples then break up. WaterSystem measures how
//   high the forest stands toward +X, +Z, -X and -Z from each vertex (COLOR.rgba, elevation sines),
//   so a lake in the woods shows a tall band and a river through a meadow mostly sky.
// The two are blended by Fresnel and emitted; albedo is black and ambient light is off, so the
// engine adds only the sun's glint. Without screen-space reflections the engine would mirror only
// bright sky at grazing angles, and the river read as pale sand.
// Also: two scrolling normal maps (rivers flow along UV.y), shoreline foam, rain ripples via
// hm_wetness. Rivers set flow_speed > 0.
shader_type spatial;
render_mode blend_mix, depth_draw_always, cull_back, diffuse_burley, specular_schlick_ggx, ambient_light_disabled;

uniform sampler2D normal_a : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_b : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D foam_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;
uniform vec4 shallow_color : source_color = vec4(0.15, 0.19, 0.13, 1.0);
uniform vec4 deep_color : source_color = vec4(0.025, 0.048, 0.045, 1.0);
uniform float absorption = 0.55;
uniform float flow_speed = 0.0;
uniform float normal_scale = 0.06;
uniform float normal_strength = 0.6;
uniform float refraction = 0.025;
uniform float foam_width = 0.6;
// How dark the reflected tree line is (share of trees over sky), and spires per full turn of the
// horizon.
uniform float treeline = 0.9;
uniform float spires = 110.0;

global uniform vec4 hm_wind;
global uniform float hm_wetness;
global uniform vec4 hm_sky_zenith;
global uniform vec4 hm_sky_horizon;

varying vec3 v_world;
varying vec4 v_tree;

float hash1(float n) {
	return fract(sin(n * 127.1) * 43758.5453);
}

// One row of fir crowns, `n` per full turn: each a pointed crown of its own height and width at a
// random spot in its cell.
float spire_row(float az, float n, float salt) {
	float x = az / 6.2831853 * n + salt;
	float cell = mod(floor(x), n);      // periodic, so the row closes seamlessly behind you
	float f = fract(x);
	float h = 0.45 + 0.55 * hash1(cell + salt * 17.0);
	float w = 0.5 + 0.45 * hash1(cell * 1.7 + 3.1 + salt);
	float c = 0.5 + (hash1(cell * 2.3 + 1.3 + salt) - 0.5) * (1.0 - w);
	return h * pow(max(1.0 - abs(f - c) / (w * 0.5), 0.0), 0.7);
}

// Tree-top elevation along the horizon at azimuth `az` (radians) for a tree line `height` high: a
// ragged ridge of firs in two overlapping rows over a slower swell of the bank.
float tree_tops(float az, float height) {
	float crown = max(spire_row(az, spires, 0.0), 0.9 * spire_row(az, round(spires * 0.43), 0.37));
	float swell = 0.75 + 0.25 * sin(az * 3.0 + 1.3) * sin(az * 7.0 + 0.4);
	return height * swell * mix(0.5, 1.0, crown);
}

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_tree = COLOR;
}

void fragment() {
	vec2 wuv = v_world.xz * normal_scale;
	vec2 drift = hm_wind.xy * TIME * (0.004 + 0.01 * hm_wind.z);
	vec2 flow = vec2(0.0, -TIME * flow_speed);
	vec2 uv1 = (flow_speed > 0.0 ? UV * 1.5 + flow : wuv + drift);
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
	// Daylight level from the sky, so the water colour itself darkens at dusk and night.
	vec3 sky_h = hm_sky_horizon.rgb;
	vec3 sky_z = hm_sky_zenith.rgb;
	float day = clamp(dot(sky_h, vec3(0.3, 0.55, 0.15)) * 2.2, 0.02, 1.2);
	float t = 1.0 - exp(-thickness * absorption);
	vec3 water_col = mix(shallow_color.rgb, deep_color.rgb, clamp(thickness / 6.0, 0.0, 1.0)) * day;
	vec3 body = mix(behind * vec3(0.82, 0.92, 0.9), water_col, t);
	// Reflection of the sky gradient, with the far bank's trees filling the low angles.
	vec3 nw = normalize(vec3(nrm.x * normal_strength * 0.6, 1.0, nrm.y * normal_strength * 0.6));
	vec3 view = normalize(CAMERA_POSITION_WORLD - v_world);
	vec3 r = reflect(-view, nw);
	float e = clamp(r.y, 0.0, 1.0);
	vec3 sky = mix(sky_h, sky_z, smoothstep(0.0, 0.6, e));
	vec3 trees = sky_h * vec3(0.06, 0.09, 0.06);
	// The tree line in the reflected ray's heading: +X, +Z, -X, -Z weights.
	vec4 hw = max(vec4(r.x, r.z, -r.x, -r.z), vec4(0.0));
	float band = dot(hw, v_tree) / max(dot(hw, vec4(1.0)), 1e-4);
	float top = tree_tops(atan(r.z, r.x), band);
	vec3 refl = mix(sky, trees, (1.0 - smoothstep(top - 0.015, top + 0.015, e)) * treeline);
	float fres = 0.02 + 0.98 * pow(1.0 - clamp(dot(nw, view), 0.0, 1.0), 5.0);
	vec3 col = mix(body, refl, fres);
	float foam = (1.0 - smoothstep(0.0, foam_width, thickness)) * texture(foam_tex, wuv * 3.0 + drift).r;
	col = mix(col, sky_h * 0.85, foam * 0.6);
	ALBEDO = vec3(foam * 0.5);
	EMISSION = col;
	ROUGHNESS = mix(0.04, 0.12, hm_wetness);
	METALLIC = 0.0;
	SPECULAR = 0.5;
	NORMAL_MAP = nrm * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = normal_strength;
}
