// The Bloom on the land (ADR-0025): the world-space infestation field and its night glow, shared by
// the terrain, bark, foliage and fungus shaders.
//   hm_bloom_map    R8 field over the built regions, 0 clean .. 1 fully colonised (BloomField)
//   hm_bloom_rect   (x0, z0, 1/width, 1/depth) in metres; 1/width is 0 while there is no field
//   hm_bloom_night  0 by day .. 1 in full dark (BloomWorld, from the sun's elevation)
//   hm_bloom        the Hum's glow 0..1 (EnvironmentController): the threads brighten on Hum nights
global uniform sampler2D hm_bloom_map : filter_linear, repeat_disable;
global uniform vec4 hm_bloom_rect;
global uniform float hm_bloom_night;
global uniform float hm_bloom;

// Cold and pale, green-cyan: the family of the Hum's aurora and the Hollowed's veins, but colder.
const vec3 HM_BLOOM_GLOW = vec3(0.42, 0.86, 0.80);

// Hashes without sin(): world coordinates run to thousands of metres, where sin-based hashes band.
float hm_bloom_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float hm_bloom_hash3(vec3 p) {
	vec3 p3 = fract(p * 0.1031);
	p3 += dot(p3, p3.zyx + 31.32);
	return fract((p3.x + p3.y) * p3.z);
}

float hm_bloom_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hm_bloom_hash(i);
	float b = hm_bloom_hash(i + vec2(1.0, 0.0));
	float c = hm_bloom_hash(i + vec2(0.0, 1.0));
	float d = hm_bloom_hash(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float hm_bloom_noise3(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(hm_bloom_hash3(i), hm_bloom_hash3(i + vec3(1.0, 0.0, 0.0)), f.x);
	float b = mix(hm_bloom_hash3(i + vec3(0.0, 1.0, 0.0)), hm_bloom_hash3(i + vec3(1.0, 1.0, 0.0)), f.x);
	float c = mix(hm_bloom_hash3(i + vec3(0.0, 0.0, 1.0)), hm_bloom_hash3(i + vec3(1.0, 0.0, 1.0)), f.x);
	float d = mix(hm_bloom_hash3(i + vec3(0.0, 1.0, 1.0)), hm_bloom_hash3(i + vec3(1.0, 1.0, 1.0)), f.x);
	return mix(mix(a, b, f.y), mix(c, d, f.y), f.z);
}

// Field strength at a world XZ position (bilinear, as BloomField.at() reads it); 0 off the map.
float hm_bloom_at(vec2 xz) {
	if (hm_bloom_rect.z <= 0.0) {
		return 0.0;
	}
	vec2 uv = (xz - hm_bloom_rect.xy) * hm_bloom_rect.zw;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return 0.0;
	}
	return textureLod(hm_bloom_map, uv, 0.0).r;
}

// The field with metre-scale raggedness where it is neither clean nor solid: the map's 2 m texels
// would otherwise draw smooth, blurry edges.
float hm_bloom_ragged(vec2 xz, float field) {
	float n = hm_bloom_noise(xz * 0.45) * 0.65 + hm_bloom_noise(xz * 1.3 + 7.1) * 0.35;
	return clamp(field + (n - 0.5) * 1.8 * field * (1.0 - field), 0.0, 1.0);
}

// A slow breath (about 10 s) out of phase across the land, so it rolls through the web instead of
// blinking in unison. It only ever dims to 70 %: the Bloom glows, it never flashes.
float hm_bloom_pulse(vec2 xz, float t) {
	float ph = hm_bloom_noise(xz * 0.045) * 12.566;
	return 0.85 + 0.15 * sin(t * 0.6 + ph);
}

// Night glow radiance of a thread mask (0..1). Zero by day; brighter while the Hum builds.
vec3 hm_bloom_glow(float threads, vec2 xz, float t) {
	float level = hm_bloom_night * (1.0 + 1.4 * hm_bloom);
	if (level <= 0.0 || threads <= 0.0) {
		return vec3(0.0);
	}
	return HM_BLOOM_GLOW * threads * level * hm_bloom_pulse(xz, t);
}
