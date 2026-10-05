// Near terrain: 8-layer splat (per-region palette into the global terrain texture arrays),
// height-based blending (layer height in albedo alpha), slope-driven triplanar rock, snow and
// wetness. Normals are blended in world space (whiteout), so the mesh needs no tangents.
// Layer order / tile sizes: game/data/materials/terrain_layers.json (TerrainTextures).
// Where the Bloom field holds the ground (ADR-0025) a white-grey mycelial web binds the litter: a
// generated thread mask revealed by coverage priority (cords first, then fans, then the cottony
// mat in the litter's hollows), over litter bleached by the rot; past a pixel or two the share of
// threads in the footprint instead (a pale veil, fading with distance); at night they glow faintly.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/bloom.gdshaderinc"

uniform sampler2DArray layer_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D splat0 : filter_linear, repeat_disable;
uniform sampler2D splat1 : filter_linear, repeat_disable;
uniform sampler2D macro_variation : hint_default_white, filter_linear_mipmap, repeat_enable;
// x0, z0, size, samples-1 (region rect and splat resolution)
uniform vec4 region_rect = vec4(0.0, 0.0, 1024.0, 1024.0);
uniform ivec4 palette0 = ivec4(0, 1, 2, 3);
uniform ivec4 palette1 = ivec4(4, 5, 9, 7);
uniform float layer_tile[16];
uniform int rock_layer = 6;
uniform int snow_layer = 8;
uniform float rock_start = 0.80;
uniform float rock_end = 0.62;
uniform float height_blend_depth = 0.12;
uniform float macro_scale = 0.0035;
uniform float macro_strength = 0.35;
uniform float normal_strength = 1.0;
// Far-field tiles discard inside the near square (x0, z0, x1, z1); disabled when x1 < x0.
uniform vec4 discard_rect = vec4(1.0, 1.0, -1.0, -1.0);

// The Bloom's web (BloomWorld.apply_web; textures/gen/bloom.py). Mask: R coverage priority
// (rank-equalised: a threshold t shows 1 - t of the ground at full growth), G age (fresh white ..
// old cream), B cottony mat, A thread body (opacity and glow).
uniform sampler2D bloom_web_mask : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bloom_web_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// The thread masks at a third, two thirds and all of full growth (RGB), binary: mipmapped, the share
// of threads in a footprint.
uniform sampler2D bloom_web_cov : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float bloom_web_tile = 1.6;
// Share of the tile the mask's threads cover (printed by the generator: keep in step). At full
// strength they all show; the cottony mat (B) fills in further.
uniform float bloom_web_cover = 0.33;
// Cream, not snow-white: a third of the ground in near-white threads brightened the dark litter
// 2-2.3x and, under the cold sky light, the colonised floor read as old snow.
uniform vec4 bloom_web_fresh : source_color = vec4(0.8, 0.78, 0.7, 1.0);
uniform vec4 bloom_web_aged : source_color = vec4(0.62, 0.57, 0.46, 1.0);
uniform float bloom_glow_energy = 0.035;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 whiteout_top(vec3 tn, vec3 gn) {
	// Tangent-space normal on the XZ plane (u = +X, v = +Z; OpenGL green up = -v).
	return normalize(vec3(tn.x + gn.x, abs(tn.z) * gn.y, -tn.y + gn.z));
}

void fragment() {
	if (discard_rect.z > discard_rect.x && v_world_pos.x > discard_rect.x && v_world_pos.x < discard_rect.z
			&& v_world_pos.z > discard_rect.y && v_world_pos.z < discard_rect.w) {
		discard;
	}
	vec3 gn = normalize(v_world_normal);
	vec2 rel = (v_world_pos.xz - region_rect.xy) / region_rect.z;
	vec2 suv = (rel * region_rect.w + 0.5) / (region_rect.w + 1.0);
	vec4 w0 = texture(splat0, suv);
	vec4 w1 = texture(splat1, suv);
	float wts[8] = float[8](w0.r, w0.g, w0.b, w0.a, w1.r, w1.g, w1.b, w1.a);
	int ids[8] = int[8](palette0.x, palette0.y, palette0.z, palette0.w, palette1.x, palette1.y, palette1.z, palette1.w);

	// Height-blend: find max(height + weight) over active layers.
	float hb[8];
	vec4 albs[8];
	float best = -1.0;
	for (int i = 0; i < 8; i++) {
		hb[i] = -1.0;
		if (wts[i] > 0.003) {
			int L = ids[i];
			vec2 uv = v_world_pos.xz / max(layer_tile[L], 0.1);
			albs[i] = texture(layer_albedo, vec3(uv, float(L)));
			hb[i] = albs[i].a * 0.5 + wts[i];
			best = max(best, hb[i]);
		}
	}
	vec3 alb = vec3(0.0);
	vec3 nrm = vec3(0.0);
	vec3 orm = vec3(0.0);
	float hgt = 0.0;
	float bsum = 0.0;
	float cutoff = best - height_blend_depth;
	for (int i = 0; i < 8; i++) {
		if (hb[i] > cutoff) {
			float b = hb[i] - cutoff;
			int L = ids[i];
			vec2 uv = v_world_pos.xz / max(layer_tile[L], 0.1);
			alb += albs[i].rgb * b;
			hgt += albs[i].a * b;
			nrm += whiteout_top(texture(layer_normal, vec3(uv, float(L))).rgb * 2.0 - 1.0, gn) * b;
			orm += texture(layer_orm, vec3(uv, float(L))).rgb * b;
			bsum += b;
		}
	}
	alb /= max(bsum, 1e-4);
	nrm = normalize(nrm);
	orm /= max(bsum, 1e-4);
	hgt /= max(bsum, 1e-4);

	// Macro variation breaks up tiling at distance.
	float mv = texture(macro_variation, v_world_pos.xz * macro_scale).r;
	alb *= mix(1.0, 0.75 + mv * 0.5, macro_strength);

	// The Bloom: rot bleaches the litter, then the web binds it. Derivatives are taken here, outside
	// the (non-uniform) branch, where they are defined; the branch samples with textureGrad.
	float bloom_glow_m = 0.0;
	float field = hm_bloom_at(v_world_pos.xz);
	vec2 wuv = v_world_pos.xz / bloom_web_tile;
	vec2 wdx = dFdx(wuv);
	vec2 wdy = dFdy(wuv);
	if (field > 0.004) {
		float bf = hm_bloom_ragged(v_world_pos.xz, field);
		vec4 wm = textureGrad(bloom_web_mask, wuv, wdx, wdy);
		vec3 wcv = textureGrad(bloom_web_cov, wuv, wdx, wdy).rgb;
		// Coverage: a priority threshold near the camera (threads extend as the field rises); once a
		// texel is below a pixel, the share of threads in the footprint at this growth, from the
		// mipmapped binary masks (thresholding mipmapped priorities turns the web into blotches).
		vec2 wsize = vec2(textureSize(bloom_web_mask, 0));
		float lod = 0.5 * log2(max(max(dot(wdx * wsize, wdx * wsize), dot(wdy * wsize, wdy * wsize)), 1e-6));
		float mid_w = smoothstep(0.3, 1.3, lod);
		float t = 1.0 - bf * bloom_web_cover;
		float aa = 0.012 + 0.03 * max(lod, 0.0);
		float near_web = smoothstep(t - aa, t + aa, wm.r);
		float g = clamp(bf, 0.0, 1.0) * 3.0;
		float share = mix(mix(wcv.r * clamp(g, 0.0, 1.0), wcv.g, clamp(g - 1.0, 0.0, 1.0)), wcv.b, clamp(g - 2.0, 0.0, 1.0));
		float threads = mix(near_web, share, mid_w);
		// The threads are hair-thin: with distance they sink into the litter, a faint pale veil (the
		// floor 1.2-1.7x as bright as clean litter, not a sheet).
		float far_w = smoothstep(1.5, 4.5, lod);
		threads *= mix(1.0, 0.3, far_w);
		// The cottony mat, in the litter's hollows and only where the Bloom is strongest.
		float cotton = smoothstep(0.62, 1.0, bf) * wm.b * smoothstep(0.4, 0.8, 1.0 - hgt) * 0.55;
		// Rot drains some colour from what the web holds (no lighter, and only a quarter of the way to
		// grey: greyed litter turns the blue of snow in shade).
		float decay = smoothstep(0.06, 0.65, bf);
		float lum = dot(alb, vec3(0.299, 0.587, 0.114));
		alb = mix(alb, vec3(lum) * vec3(1.04, 1.0, 0.94), decay * 0.25);
		vec3 wc = mix(bloom_web_fresh.rgb, bloom_web_aged.rgb, wm.g);
		float body = mix(mix(0.5, 0.95, wm.a), 0.55, mid_w);
		float web = clamp(max(threads * body, cotton), 0.0, 1.0);
		alb = mix(alb, mix(wc, bloom_web_aged.rgb * 0.85, smoothstep(-0.05, 0.05, cotton - threads)), web);
		vec3 wn = whiteout_top(textureGrad(bloom_web_normal, wuv, wdx, wdy).rgb * 2.0 - 1.0, gn);
		nrm = normalize(mix(nrm, wn, threads * (1.0 - far_w) * 0.85));
		orm.g = mix(orm.g, 0.58, web);
		orm.r = mix(orm.r, 1.0, web * 0.5);
		bloom_glow_m = threads * body + cotton * 0.4;
	}

	// Slope rock (triplanar on X/Z projections + top).
	float rock_w = smoothstep(rock_start, rock_end, gn.y);
	if (rock_w > 0.001) {
		float t = max(layer_tile[rock_layer], 0.1);
		vec3 bw = pow(abs(gn), vec3(4.0));
		bw /= (bw.x + bw.y + bw.z);
		vec3 ax = texture(layer_albedo, vec3(vec2(v_world_pos.z, -v_world_pos.y) / t, float(rock_layer))).rgb;
		vec3 az = texture(layer_albedo, vec3(vec2(v_world_pos.x, -v_world_pos.y) / t, float(rock_layer))).rgb;
		vec3 ay = texture(layer_albedo, vec3(v_world_pos.xz / t, float(rock_layer))).rgb;
		vec3 ra = ax * bw.x + ay * bw.y + az * bw.z;
		vec3 nx = texture(layer_normal, vec3(vec2(v_world_pos.z, -v_world_pos.y) / t, float(rock_layer))).rgb * 2.0 - 1.0;
		vec3 nz = texture(layer_normal, vec3(vec2(v_world_pos.x, -v_world_pos.y) / t, float(rock_layer))).rgb * 2.0 - 1.0;
		vec3 wnx = normalize(vec3(abs(nx.z) * gn.x, nx.y + gn.y, nx.x * sign(gn.x) + gn.z));
		vec3 wnz = normalize(vec3(nz.x * sign(gn.z) + gn.x, nz.y + gn.y, abs(nz.z) * gn.z));
		vec3 wny = whiteout_top(texture(layer_normal, vec3(v_world_pos.xz / t, float(rock_layer))).rgb * 2.0 - 1.0, gn);
		vec3 rn = normalize(wnx * bw.x + wny * bw.y + wnz * bw.z);
		vec3 ro = texture(layer_orm, vec3(v_world_pos.xz / t, float(rock_layer))).rgb;
		alb = mix(alb, ra, rock_w);
		nrm = normalize(mix(nrm, rn, rock_w));
		orm = mix(orm, ro, rock_w);
	}

	// Snow settles on gentle slopes; wetness darkens and glosses.
	float snow = hm_snow * smoothstep(0.65, 0.9, gn.y);
	if (snow > 0.001) {
		vec2 suv2 = v_world_pos.xz / max(layer_tile[snow_layer], 0.1);
		alb = mix(alb, texture(layer_albedo, vec3(suv2, float(snow_layer))).rgb, snow);
		orm = mix(orm, texture(layer_orm, vec3(suv2, float(snow_layer))).rgb, snow);
	}
	float wet = hm_wetness * smoothstep(0.5, 0.95, gn.y);
	alb *= mix(1.0, 0.62, wet);
	orm.g = mix(orm.g, 0.18, wet * 0.85);

	if (bloom_glow_m > 0.0) {
		// Nothing glows on cliff faces or under snow.
		EMISSION = hm_bloom_glow(bloom_glow_m * (1.0 - rock_w) * (1.0 - snow), v_world_pos.xz, TIME) * bloom_glow_energy;
	}
	ALBEDO = alb;
	ROUGHNESS = clamp(orm.g, 0.05, 1.0);
	METALLIC = 0.0;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.2;
	NORMAL = normalize((VIEW_MATRIX * vec4(mix(gn, nrm, normal_strength), 0.0)).xyz);
}
