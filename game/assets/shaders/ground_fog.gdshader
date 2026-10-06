// Ground fog round the camera (EnvironmentController, ADR-0033): a FogVolume whose density fills in
// below the local fog level, so mist pools in hollows and over water at dawn and dusk rather than
// hanging at one height everywhere. The level is the low ground at about 25 m scale (the weather
// map's smoothed ground, read at a coarse mip) plus depth_m, raised over water to the surface plus
// water_depth_m; off the map, a single level from the environment. Slow 3-D noise drifting with the
// wind tears it into banks and wisps, thinning toward the top.
shader_type fog;

uniform float density = 0.03;
uniform vec3 albedo = vec3(0.9, 0.92, 0.95);
uniform float depth_m = 6.0;
uniform float water_depth_m = 4.0;
uniform float noise_scale = 0.05;
uniform float fallback_level = 0.0;
uniform vec2 drift = vec2(0.0);

global uniform sampler2D hm_weather_map : filter_linear_mipmap, repeat_disable;
global uniform vec4 hm_weather_rect;

float fog_hash(vec3 p) {
	vec3 p3 = fract(p * 0.1031);
	p3 += dot(p3, p3.zyx + 31.32);
	return fract((p3.x + p3.y) * p3.z);
}

float fog_noise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(fog_hash(i), fog_hash(i + vec3(1.0, 0.0, 0.0)), f.x);
	float b = mix(fog_hash(i + vec3(0.0, 1.0, 0.0)), fog_hash(i + vec3(1.0, 1.0, 0.0)), f.x);
	float c = mix(fog_hash(i + vec3(0.0, 0.0, 1.0)), fog_hash(i + vec3(1.0, 0.0, 1.0)), f.x);
	float d = mix(fog_hash(i + vec3(0.0, 1.0, 1.0)), fog_hash(i + vec3(1.0, 1.0, 1.0)), f.x);
	return mix(mix(a, b, f.y), mix(c, d, f.y), f.z);
}

void fog() {
	vec3 p = WORLD_POSITION;
	float level = fallback_level;
	if (hm_weather_rect.z > 0.0) {
		vec2 uv = (p.xz - hm_weather_rect.xy) * hm_weather_rect.z;
		if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0) {
			float low = textureLod(hm_weather_map, uv, 4.0).b + hm_weather_rect.w + depth_m;
			float wat = textureLod(hm_weather_map, uv, 0.0).a;
			if (wat > -100.0) {
				low = max(low, wat + hm_weather_rect.w + water_depth_m);
			}
			float edge = smoothstep(0.0, 0.12, min(min(uv.x, uv.y), min(1.0 - uv.x, 1.0 - uv.y)));
			level = mix(fallback_level, low, edge);
		}
	}
	float below = level - p.y;
	float d = smoothstep(-1.5, 4.0, below);
	vec3 q = p * noise_scale + vec3(drift.x, 0.0, drift.y) * TIME * noise_scale;
	float n = fog_noise(q) * 0.65 + fog_noise(q * 2.7 + vec3(3.1, 1.7, 5.3)) * 0.35;
	// Denser down in the bank, torn at its top.
	float wisp = smoothstep(0.3, 0.7, n + 0.3 * smoothstep(0.0, 8.0, below));
	DENSITY = density * d * wisp;
	ALBEDO = albedo;
}
