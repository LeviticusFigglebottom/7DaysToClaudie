// Hollowmere characters (ADR-0028): what skin.gdshader and cloth.gdshader share.
//
// Vertex data baked by the character generator (tools/assetgen/blender/lib/char_attrs.py):
//   UV       material UV, metres (x uv_scale)
//   UV2      rest-pose position x, y (object space, metres)
//   CUSTOM0  rest-pose z, gate, wet (0..1), bruise (0..1)
//   CUSTOM1  trim (signed distance, m), seam (signed distance, m), paint (signed distance, m),
//            edge (distance to the nearest garment edge, m: + hemmed, - torn)
//   COLOR    R baked AO, G dirt / blood, B where the Bloom has spread
// Patterns read the rest pose, so veins, mottling, seams and paint stay put on the skin and the
// cloth as the limbs move (std_surface patterns from the skinned position and they slid: TD-027).
// A mesh without these attributes reads zeros: no marks, nothing gated.
//
// Instance uniforms keep std_surface's slots (instance_wear 0, instance_variation 1, bloom_glow 2,
// weather_exposure 3): every material on one mesh instance must agree on each name's index, and a
// body mixes skin, cloth and std_surface (hair, teeth, boots). hollow_burst takes slot 8, clear of
// std_surface's.

instance uniform float instance_wear : instance_index(0) = -1.0;
instance uniform float instance_variation : instance_index(1) = 0.5;
// How far the Bloom has taken this body (InfectedTiers glow: normal 0, Seeded 0.35, Bloomed 1).
instance uniform float bloom_glow : instance_index(2) = 0.0;
instance uniform float weather_exposure : instance_index(3) = 1.0;
// 1 once the Blister's pustules have burst (EnemyVisual.burst()).
instance uniform float hollow_burst : instance_index(8) = 0.0;

global uniform float hm_wetness;
global uniform float hm_snow;
// The Hum's glow (0..1): the Bloom brightens on Hum nights.
global uniform float hm_bloom;

varying vec3 v_rest;
// (rest z, gate, wet, bruise)
varying vec4 v_attr0;
// (trim, seam, paint, edge)
varying vec4 v_attr1;
varying vec3 v_world_normal;

// Gate codes (CUSTOM0.y): 0 always; 1 from the Seeded tier up; 2 Bloomed only; 4 an intact
// pustule (gone once burst); 5 a burst crater (there only once burst). The instance uniforms come
// in as arguments: the stage functions read them, helpers only get values.
float hm_tier_stage(float glow) {
	return glow > 0.6 ? 2.0 : (glow > 0.2 ? 1.0 : 0.0);
}

bool hm_gated_out(float gate, float glow, float burst) {
	if (gate < 0.5) {
		return false;
	}
	if (gate < 2.5) {
		return gate > hm_tier_stage(glow) + 0.5;
	}
	if (gate < 4.5) {
		return burst > 0.5;
	}
	return burst < 0.5;
}

// vertex() of each character shader starts with (Godot only lets the stage functions write
// varyings):
//   v_rest = vec3(UV2, CUSTOM0.x); v_attr0 = CUSTOM0; v_attr1 = CUSTOM1;
//   if (hm_gated_out(CUSTOM0.y, bloom_glow, hollow_burst)) { VERTEX = vec3(0.0); }
//   v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
// Gated-out geometry collapses to a point (no triangles drawn, no shadow cast): the tier's growths
// and both states of the pustules are in every body, shown per instance.

// --- noise (sin-free hashes: rest coordinates are small, but the same code serves gibs) ----------

float hm_char_hash(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

vec3 hm_char_hash3(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.xxy + p.yxx) * p.zyx);
}

float hm_char_noise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(hm_char_hash(i), hm_char_hash(i + vec3(1.0, 0.0, 0.0)), f.x);
	float b = mix(hm_char_hash(i + vec3(0.0, 1.0, 0.0)), hm_char_hash(i + vec3(1.0, 1.0, 0.0)), f.x);
	float c = mix(hm_char_hash(i + vec3(0.0, 0.0, 1.0)), hm_char_hash(i + vec3(1.0, 0.0, 1.0)), f.x);
	float d = mix(hm_char_hash(i + vec3(0.0, 1.0, 1.0)), hm_char_hash(i + vec3(1.0, 1.0, 1.0)), f.x);
	return mix(mix(a, b, f.y), mix(c, d, f.y), f.z);
}

// Meandering lines: distance-like value, ~0 on the 0.5 level set of a small fbm (veins and rivers
// look like level sets: long, branching-looking, never closed into cells).
float hm_level_lines(vec3 p) {
	float n = hm_char_noise(p) * 0.58 + hm_char_noise(p * 2.13 + 3.7) * 0.29 + hm_char_noise(p * 4.37 + 1.1) * 0.13;
	return abs(n - 0.5);
}

// The Bloom's filaments under the skin: warped level-set lines (veins a few centimetres apart)
// with finer threads where it is thick. `scale` per metre of rest space, `fine` 0..1 adds the
// threads. Anti-aliased: far away the lines fade to a faint average instead of shimmering.
float hm_bloom_net(vec3 rest, float scale, float fine) {
	vec3 w = rest * scale;
	vec3 warp = vec3(hm_char_noise(w * 0.37), hm_char_noise(w * 0.37 + 17.1), hm_char_noise(w * 0.37 + 41.3));
	w += (warp - 0.5) * 2.2;
	float l1 = hm_level_lines(w);
	float a1 = fwidth(l1);
	float v = 1.0 - smoothstep(0.010, 0.022 + a1 * 1.2, l1);
	v = mix(v, 0.12, smoothstep(0.03, 0.08, a1));
	if (fine > 0.01) {
		float l2 = hm_level_lines(w * 2.7 + 5.3);
		float a2 = fwidth(l2);
		float v2 = (1.0 - smoothstep(0.007, 0.016 + a2 * 1.2, l2)) * fine;
		v2 = mix(v2, 0.06 * fine, smoothstep(0.03, 0.08, a2));
		v = max(v, v2 * 0.65);
	}
	return v;
}

// Crisp mask from a signed distance (negative inside), anti-aliased over a pixel.
float hm_sd_mask(float sd, float soft) {
	float aa = fwidth(sd) * 0.75 + soft;
	return 1.0 - smoothstep(-aa, aa, sd);
}

// Rain darkens and glosses what faces the sky most; snow settles on shoulders and crowns.
// `exposure` is the instance's weather_exposure (0 indoors).
void hm_char_weather(inout vec3 alb, inout float rough, float porous, vec3 world_normal, float exposure) {
	float up = clamp(world_normal.y, 0.0, 1.0);
	float wet = hm_wetness * exposure * mix(0.55, 1.0, up);
	alb *= mix(1.0, mix(0.82, 0.58, porous), wet);
	rough = mix(rough, mix(0.18, 0.45, porous), wet * 0.85);
	float snow = hm_snow * exposure * smoothstep(0.6, 0.9, up);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	rough = mix(rough, 0.7, snow);
}
