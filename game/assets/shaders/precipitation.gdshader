// Rain, snow and eave drips round the camera (WeatherFx, ADR-0033). Particles spawn in a column box
// round the emitter (it follows the camera; the particles live in world space), fall with the wind,
// and stop where the weather map says rain lands (hm_weather_map R: roofs, ground, the water
// surface), so nothing falls indoors or under a roof. A drop that lands becomes a splash where it
// landed (CUSTOM.x = 1, CUSTOM.y its age) until splash_s, then waits for its next cycle; a flake just
// settles. Drips start on an eave point (eave_tex, two texels each: position and drop height, then
// the edge's direction), fall from rest under gravity and splash on the ground below.
// The particle's Y axis carries the direction it moves in, for the streaks (precipitation_draw).
// CUSTOM: x 0 falling / 1 landed, y age in the air or since landing (s; a drip's wait on the eave
// counts up from below 0), z where a drip lands, w random 0..1.
shader_type particles;
render_mode disable_velocity, disable_force;

// 0 rain, 1 snow, 2 eave drips.
uniform int mode = 0;
// Half-width, metres above and below the emitter.
uniform vec3 box = vec3(16.0, 12.0, 4.0);
uniform float fall_speed = 8.0;
// Drift with the wind and its gusts, metres per second (x, z).
uniform vec2 wind = vec2(0.0);
uniform float splash_s = 0.24;
uniform sampler2D eave_tex : filter_nearest, repeat_disable;
uniform int eave_count = 0;
// The weather map's cell: drips start anywhere along their eave cell's edge.
uniform float eave_cell = 1.5;

global uniform sampler2D hm_weather_map : filter_linear_mipmap, repeat_disable;
global uniform vec4 hm_weather_rect;

uint wx_hash_u(uint x) {
	x = ((x >> uint(16)) ^ x) * uint(73244475);
	x = ((x >> uint(16)) ^ x) * uint(73244475);
	x = (x >> uint(16)) ^ x;
	return x;
}

float wx_rand(inout uint seed) {
	seed = wx_hash_u(seed + uint(0x9E3779B9));
	return float(seed & uint(0xFFFFFF)) / 16777216.0;
}

// Where rain lands under (x, z): the weather map's R, texel-exact so a roof edge stays sharp; the
// bottom of the box off the map.
float landing(vec2 xz, float floor_y) {
	if (hm_weather_rect.z <= 0.0) {
		return floor_y;
	}
	vec2 uv = (xz - hm_weather_rect.xy) * hm_weather_rect.z;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x >= 1.0 || uv.y >= 1.0) {
		return floor_y;
	}
	ivec2 sz = textureSize(hm_weather_map, 0);
	ivec2 t = clamp(ivec2(uv * vec2(sz)), ivec2(0), sz - 1);
	return texelFetch(hm_weather_map, t, 0).r + hm_weather_rect.w;
}

void start() {
	uint seed = wx_hash_u(NUMBER * uint(747796405) + RANDOM_SEED + uint(1));
	float r1 = wx_rand(seed);
	float r2 = wx_rand(seed);
	float r3 = wx_rand(seed);
	float r4 = wx_rand(seed);
	vec3 origin = EMISSION_TRANSFORM[3].xyz;
	vec3 p = origin;
	CUSTOM = vec4(0.0, 0.0, -1e6, r4);
	VELOCITY = vec3(0.0);
	if (mode == 2) {
		if (eave_count <= 0) {
			ACTIVE = false;
		} else {
			int i = min(int(r1 * float(eave_count)), eave_count - 1);
			vec4 a = texelFetch(eave_tex, ivec2(i * 2, 0), 0);
			vec4 e = texelFetch(eave_tex, ivec2(i * 2 + 1, 0), 0);
			p = a.xyz + e.xyz * (r2 - 0.5) * eave_cell;
			CUSTOM.z = a.y - a.w;
			// Drips let go at their own pace: hold on the eave a moment before falling.
			CUSTOM.y = -r3 * 0.8;
		}
	} else {
		// Anywhere in the column (the wind carries them across it; process() wraps them round).
		p = origin + vec3((r1 * 2.0 - 1.0) * box.x, mix(-box.z, box.y, r2), (r3 * 2.0 - 1.0) * box.x);
	}
	TRANSFORM = mat4(1.0);
	TRANSFORM[3].xyz = p;
}

void process() {
	if (CUSTOM.x < 0.5) {
		vec3 p = TRANSFORM[3].xyz;
		vec3 v;
		if (mode == 1) {
			// Flakes tumble down on the wind, each with a slow swirl of its own.
			float ph = CUSTOM.w * 6.2831853;
			vec2 swirl = vec2(sin(TIME * (0.7 + CUSTOM.w) + ph), cos(TIME * (0.55 + 0.7 * CUSTOM.w) + ph * 1.3)) * 0.4;
			v = vec3(wind.x + swirl.x, -fall_speed * (0.7 + 0.6 * CUSTOM.w), wind.y + swirl.y);
		} else if (mode == 2) {
			if (CUSTOM.y < 0.0) {
				// Still swelling on the eave.
				CUSTOM.y += DELTA;
				v = vec3(0.0);
			} else {
				v = VELOCITY + vec3(wind.x * DELTA, -9.8 * DELTA, wind.y * DELTA);
			}
		} else {
			v = vec3(wind.x, -fall_speed * (0.85 + 0.3 * CUSTOM.w), wind.y);
		}
		if (mode != 2) {
			// Age in the air: the draw fades a drop or flake in after its birth and out before its
			// cycle ends.
			CUSTOM.y += DELTA;
		}
		VELOCITY = v;
		p += v * DELTA;
		if (mode != 2) {
			// The column moves with the camera and the wind blows across it: whatever leaves one
			// side comes back in on the other, so it stays evenly filled.
			vec2 rel = p.xz - EMISSION_TRANSFORM[3].xz;
			p.xz -= 2.0 * box.x * floor((rel + box.x) / (2.0 * box.x));
		}
		float land = mode == 2 ? CUSTOM.z : landing(p.xz, EMISSION_TRANSFORM[3].y - box.z);
		if (p.y <= land) {
			p.y = land + 0.01;
			CUSTOM.x = 1.0;
			CUSTOM.y = 0.0;
			VELOCITY = vec3(0.0);
			v = vec3(0.0, 1.0, 0.0);
		}
		TRANSFORM[0] = vec4(1.0, 0.0, 0.0, 0.0);
		TRANSFORM[1] = vec4(normalize(v + vec3(0.0, -1e-4, 0.0)), 0.0);
		TRANSFORM[2] = vec4(0.0, 0.0, 1.0, 0.0);
		TRANSFORM[3].xyz = p;
	} else {
		CUSTOM.y += DELTA;
		if (CUSTOM.y > (mode == 1 ? 0.6 : splash_s)) {
			ACTIVE = false;
		}
	}
}
