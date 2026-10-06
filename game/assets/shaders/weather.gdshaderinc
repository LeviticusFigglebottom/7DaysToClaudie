// Weather on surfaces (ADR-0033), shared by the terrain, water, std_surface, kit_wall, bark and
// foliage shaders. Globals (EnvironmentController, WeatherFx):
//   hm_wetness       how soaked surfaces are, 0 dry .. 1 soaked (rises in rain, dries slowly)
//   hm_rain          x rainfall now 0..1, y standing water (puddles) 0..1, z lightning flash, w snowfall
//   hm_weather_map   round the camera (WeatherMaps): R where rain lands, G ground, B ground smoothed
//                    over ~9 m, A water surface (-1000 none); heights relative to hm_weather_rect.w
//   hm_weather_rect  (x0, z0, 1 / size, base height); z = 0 while there is no map
// Wet surfaces follow the porosity model (after Lagarde, "Water drop 2b - Dynamic rain and its
// effects"): a porous surface first drinks the water and darkens (light is trapped in the wet pores)
// with little change in gloss; only once it is soaked does a film of water sit on it, which is
// glossy. A sealed surface (glazed tile, varnish, metal paint) barely darkens and glosses at once.
global uniform float hm_wetness;
global uniform vec4 hm_rain;
global uniform sampler2D hm_weather_map : filter_linear_mipmap, repeat_disable;
global uniform vec4 hm_weather_rect;

// Hashes without sin(): world coordinates run to thousands of metres, where sin-based hashes band.
float wx_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 wx_hash2(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float wx_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(wx_hash(i), wx_hash(i + vec2(1.0, 0.0)), f.x), mix(wx_hash(i + vec2(0.0, 1.0)), wx_hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

// The water film: 0 dry .. 1 a continuous film. Porous surfaces only grow one once soaked.
float wx_film(float wet, float porosity) {
	return wet * mix(1.0, smoothstep(0.45, 1.0, wet), porosity);
}

// Soaked albedo: darker (most for porous surfaces) and a touch more saturated (the film).
vec3 wx_wet_albedo(vec3 alb, float wet, float porosity) {
	vec3 d = alb * mix(1.0, mix(0.82, 0.38, porosity), wet);
	float l = dot(d, vec3(0.299, 0.587, 0.114));
	return max(mix(vec3(l), d, 1.0 + 0.2 * wet), vec3(0.0));
}

// Soaked roughness: the film is glossy where it covers.
float wx_wet_roughness(float rough, float wet, float porosity) {
	return mix(rough, min(rough, 0.12), wx_film(wet, porosity) * 0.92);
}

// Ripples from raindrops on standing water: rings spreading from random points, each cell struck
// about once a second (fewer in light rain). Returns the surface slope (d/dx, d/dz) to tilt a
// normal with. Two layers at different scales and phases; a ring fits inside its cell, so one
// hash per cell and layer is enough.
vec2 wx_ripple_layer(vec2 p, float t, float rate, float salt) {
	vec2 cell = floor(p);
	vec2 f = fract(p);
	float off = wx_hash(cell + salt);
	float cyc = t * 0.9 + off * 7.0;
	float phase = fract(cyc);
	// Is this cell struck on this cycle?
	float on = step(wx_hash(cell * 1.37 + floor(cyc) * 0.71 + salt * 3.1), rate);
	vec2 c = 0.3 + 0.4 * wx_hash2(cell + floor(cyc) * 1.93 + salt);
	vec2 d = f - c;
	float r = length(d);
	float radius = phase * 0.3;
	float x = (r - radius) * 38.0;
	// A ring with a crest and a trough, fading as it spreads.
	float slope = -sin(clamp(x, -3.14159, 3.14159)) * step(abs(x), 3.14159);
	float fade = (1.0 - phase) * (1.0 - phase) * on;
	return d / max(r, 1e-4) * slope * fade;
}

vec2 wx_ripples(vec2 xz, float t, float rain) {
	if (rain < 0.02) {
		return vec2(0.0);
	}
	float rate = clamp(rain * 1.3, 0.0, 1.0);
	return (wx_ripple_layer(xz * 2.9, t, rate, 0.0) + wx_ripple_layer(xz * 4.3 + 7.7, t * 1.13, rate, 5.3) * 0.7) * min(rain * 2.0, 1.0);
}

// The weather map texel under a world point (heights back to world metres), and whether there is
// one. Off the map: valid = 0.
vec4 wx_map(vec2 xz, out float valid) {
	valid = 0.0;
	if (hm_weather_rect.z <= 0.0) {
		return vec4(0.0);
	}
	vec2 uv = (xz - hm_weather_rect.xy) * hm_weather_rect.z;
	if (uv.x <= 0.0 || uv.y <= 0.0 || uv.x >= 1.0 || uv.y >= 1.0) {
		return vec4(0.0);
	}
	// Fade out over the map's last tenth so nothing ends on a line.
	valid = smoothstep(0.0, 0.08, min(min(uv.x, uv.y), min(1.0 - uv.x, 1.0 - uv.y)));
	return textureLod(hm_weather_map, uv, 0.0) + vec4(hm_weather_rect.w);
}

// How far below the smoothed ground a point lies (metres, >= 0): where standing water collects.
float wx_hollow(vec2 xz) {
	float valid;
	vec4 m = wx_map(xz, valid);
	return max(m.b - m.g, 0.0) * valid;
}

// Rain reaches this point (it stands under open sky, not under a roof). `up` is the surface's
// world normal y: a sloping roof rises and falls across a map cell, so the steeper it is the more
// it may lie below the cell's own height and still be the surface the rain lands on. Off the map: 1.
float wx_exposed(vec3 p, float up) {
	float valid;
	vec4 m = wx_map(p.xz, valid);
	return mix(1.0, smoothstep(-0.1, 0.1, p.y + 0.35 + 1.5 * (1.0 - clamp(up, 0.0, 1.0)) - m.r), valid);
}
