// Tree trunks/branches: tiling bark + vertex AO + moss mask (B), sways with the same wind as
// the foliage of the same plant. Stumps and logs use std_surface (they do not sway).
// Near infested ground (the Bloom field at the tree's foot, ADR-0025) pale hyphal cords climb the
// trunk from the roots: a generated thread mask in the bark's UVs (cords run up the trunk), revealed
// by coverage priority as far as the field, the height on the trunk and world-space clumps allow,
// with a few bracket-like crusts low down. Where the mask's detail is below a pixel the share of
// threads in the footprint shows instead (mipmapped binary masks), fading to a faint pale cast on
// far LODs. At night the threads glow faintly.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/wind.gdshaderinc"
#include "res://assets/shaders/bloom.gdshaderinc"

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

// The Bloom (ADR-0025; textures/gen/bloom.py). Mask: R coverage priority (cords highest), G age,
// B crusts, A thread body.
uniform sampler2D bloom_mask_tex : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bloom_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// The thread masks at a third, two thirds and all of full growth (RGB) and with the felt sheath (A),
// binary: mipmapped, the share of each in a footprint.
uniform sampler2D bloom_cov_tex : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
// Thread-mask repeats per bark UV unit (one mask tile is ~1 m of bark; the bark tiles differ).
uniform vec2 bloom_uv_scale = vec2(1.0, 1.0);
// How readily this species is colonised (0 = never): larch most, then dead wood, fir, birch.
uniform float bloom_affinity : hint_range(0.0, 1.5) = 0.0;
// Metres the cords climb at full strength (the tallest tongues reach about 1.4 times this).
uniform float bloom_climb = 3.0;
// Share of the mask's tile its threads cover (printed by the generator: keep in step).
uniform float bloom_cover = 0.26;
uniform vec4 bloom_fresh : source_color = vec4(0.84, 0.84, 0.79, 1.0);
uniform vec4 bloom_aged : source_color = vec4(0.67, 0.63, 0.53, 1.0);
uniform vec4 bloom_crust : source_color = vec4(0.78, 0.73, 0.6, 1.0);
uniform float bloom_glow_energy = 0.045;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_normal;
varying vec3 v_wpos;
// Field at the tree's foot x affinity, and the height above it (m, before the sway).
varying float v_bloom;
varying float v_trunk_h;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	v_trunk_h = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y - origin.y;
	VERTEX.xz += hm_plant_sway(VERTEX, origin, sway_height, stiffness, TIME);
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_bloom = bloom_affinity > 0.0 ? hm_bloom_at(origin.xz) * bloom_affinity : 0.0;
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
	float glow_m = 0.0;
	// Derivatives outside the (non-uniform) branch, where they are defined.
	vec2 buv = UV * bloom_uv_scale;
	vec2 bdx = dFdx(buv);
	vec2 bdy = dFdy(buv);
	if (v_bloom > 0.01) {
		// Clumps in world space: the threads climb in tongues, higher on one side of a trunk than
		// the other and differently on every tree, and thin out between them.
		float clump = hm_bloom_noise3(v_wpos * vec3(1.6, 0.42, 1.6) + vec3(0.0, 3.1, 0.0)) * 0.7
			+ hm_bloom_noise3(v_wpos * vec3(4.1, 1.3, 4.1)) * 0.3;
		float reach = bloom_climb * v_bloom * (0.3 + 1.1 * clump);
		float dens = v_bloom * (1.0 - smoothstep(reach * 0.2, reach, v_trunk_h)) * mix(0.45, 1.15, clump);
		// The root flares and the first half metre are bound solid.
		dens = clamp(dens + v_bloom * (1.0 - smoothstep(0.1, 0.6, v_trunk_h)) * 0.35, 0.0, 1.0);
		vec4 bm = textureGrad(bloom_mask_tex, buv, bdx, bdy);
		vec4 bcv = textureGrad(bloom_cov_tex, buv, bdx, bdy);
		vec2 bsize = vec2(textureSize(bloom_mask_tex, 0));
		float lod = 0.5 * log2(max(max(dot(bdx * bsize, bdx * bsize), dot(bdy * bsize, bdy * bsize)), 1e-6));
		float mid_w = smoothstep(0.3, 1.3, lod);
		float far_w = smoothstep(2.0, 5.0, lod);
		float t = 1.0 - dens * bloom_cover;
		float aa = 0.012 + 0.03 * max(lod, 0.0);
		float near_t = smoothstep(t - aa, t + aa, bm.r);
		// Where the trunk is bound solid a felted sheath grows along the cords (the gap pixels
		// rank by their closeness to a thread).
		float sheath = smoothstep(0.7, 1.0, dens) * 0.7;
		near_t = max(near_t, smoothstep(1.0 - bloom_cover - 0.3, 1.0 - bloom_cover, bm.r) * sheath);
		// Below a pixel: the share of threads (and sheath) in the footprint at this growth.
		float g = clamp(dens, 0.0, 1.0) * 3.0;
		float share = mix(mix(bcv.r * clamp(g, 0.0, 1.0), bcv.g, clamp(g - 1.0, 0.0, 1.0)), bcv.b, clamp(g - 2.0, 0.0, 1.0));
		share = max(share, bcv.a * sheath);
		// Far away only a faint pale cast is left of them.
		float threads = mix(near_t, share, mid_w) * mix(1.0, 0.6, far_w);
		float body = mix(mix(0.6, 1.0, bm.a), 0.8, mid_w);
		vec3 tc = mix(bloom_fresh.rgb, bloom_aged.rgb, bm.g);
		alb = mix(alb, tc, threads * body);
		nrm = mix(nrm, textureGrad(bloom_normal_tex, buv, bdx, bdy).rgb, threads * (1.0 - far_w) * 0.9);
		rough = mix(rough, 0.52, threads);
		// Bracket-like crusts low on the most colonised trunks, gated in world space so the mask's
		// tile doesn't repeat them around every trunk.
		float gate = smoothstep(0.55, 0.72, hm_bloom_noise3(v_wpos * vec3(0.9, 0.7, 0.9) + vec3(13.0)));
		float crust = bm.b * gate * smoothstep(0.5, 0.85, dens) * (1.0 - smoothstep(0.6, 1.8, v_trunk_h)) * (1.0 - far_w);
		alb = mix(alb, bloom_crust.rgb * mix(0.8, 1.05, bm.g), crust);
		rough = mix(rough, 0.8, crust);
		glow_m = threads * body + crust * 0.3;
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
	if (glow_m > 0.0) {
		EMISSION = hm_bloom_glow(glow_m * (1.0 - snow), v_wpos.xz, TIME) * bloom_glow_energy * mix(1.0, COLOR.r, 0.5);
	}
}
