// Hollowmere sky: time-of-day gradient, sun disc + forward scattering, moon disc, stars,
// a scrolling cloud layer (coverage driven by weather) and a faint Bloom aurora on Hum nights.
// Clouds shade themselves cheaply: the density a step toward the sun says whether a point faces
// the sun or sits behind the cloud's mass, and thick cores darken, so they read as volumes rather
// than cut-outs. A thin, streaky cirrus veil sits above them on fair days.
// LIGHT0 = sun, LIGHT1 = moon (DirectionalLight3D order in the scene).
shader_type sky;
render_mode use_half_res_pass;

uniform vec4 zenith_color : source_color = vec4(0.22, 0.36, 0.58, 1.0);
uniform vec4 horizon_color : source_color = vec4(0.62, 0.68, 0.74, 1.0);
uniform vec4 ground_color : source_color = vec4(0.16, 0.16, 0.15, 1.0);
uniform vec4 sunset_color : source_color = vec4(1.0, 0.48, 0.22, 1.0);
uniform float sunset_amount : hint_range(0.0, 1.0) = 0.0;
uniform float night_amount : hint_range(0.0, 1.0) = 0.0;
uniform float sky_energy = 1.0;
uniform float sun_size = 0.9994;
uniform float sun_glow = 0.35;
uniform sampler2D cloud_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D star_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D moon_tex : source_color, filter_linear, repeat_disable;
uniform float cloud_cover : hint_range(0.0, 1.0) = 0.35;
uniform float cloud_darkness : hint_range(0.0, 1.0) = 0.0;
uniform vec2 cloud_wind = vec2(0.004, 0.0015);
uniform float cloud_scale = 0.35;
uniform float moon_size = 0.9996;
uniform float aurora = 0.0;

float cloud_density(vec2 uv, vec2 drift) {
	vec4 n = texture(cloud_tex, uv);
	vec4 n2 = texture(cloud_tex, uv * 2.7 + vec2(0.37, 0.71) + drift * 1.6);
	return n.r * 0.6 + n.g * 0.25 + n2.b * 0.15;
}

// The cloud's large-scale mass (no fine detail), for shading: lighting follows the big shapes.
float cloud_mass(vec2 uv) {
	vec4 n = texture(cloud_tex, uv);
	return n.r * 0.75 + n.g * 0.25;
}

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void sky() {
	vec3 dir = EYEDIR;
	float up = dir.y;
	// Base gradient.
	float h = clamp(up, 0.0, 1.0);
	vec3 col = mix(horizon_color.rgb, zenith_color.rgb, pow(h, 0.55));
	// Sunset band toward the sun.
	float sun_dot = dot(dir, LIGHT0_DIRECTION);
	float band = exp(-abs(up) * 6.0) * (0.45 + 0.55 * max(sun_dot, 0.0));
	col = mix(col, sunset_color.rgb, band * sunset_amount);
	// Below horizon: dark ground haze.
	col = mix(col, ground_color.rgb, smoothstep(0.0, -0.12, up));

	// Clouds (planar projection on a dome).
	float cloud_alpha = 0.0;
	if (up > 0.0) {
		vec2 drift = TIME * cloud_wind;
		vec2 uv = dir.xz / (up + 0.18) * cloud_scale + drift;
		float density = cloud_density(uv, drift);
		float threshold = mix(0.78, 0.18, cloud_cover);
		cloud_alpha = smoothstep(threshold, threshold + 0.22, density) * smoothstep(0.0, 0.12, up);
		vec3 lit = mix(vec3(1.0), LIGHT0_COLOR * 0.9 + 0.1, 0.5) * mix(1.0, 0.45, cloud_darkness);
		// More cloud toward the sun: this point is on the far, shaded side of the mass.
		vec2 sun_step = normalize(LIGHT0_DIRECTION.xz + vec2(1e-4)) * 0.05;
		float mass = cloud_mass(uv);
		float toward = cloud_mass(uv + sun_step);
		float core = smoothstep(threshold + 0.1, threshold + 0.45, mass);
		float shade = clamp((toward - mass) * 7.0 + 0.2 + core * 0.5, 0.0, 1.0);
		vec3 shadow_col = mix(horizon_color.rgb, zenith_color.rgb, 0.35) * mix(0.8, 0.45, cloud_darkness);
		// A full deck is lit from above as one sheet: shading flattens as cover closes.
		vec3 cloud_col = mix(lit, shadow_col, shade * mix(0.85, 0.4, smoothstep(0.6, 1.0, cloud_cover)));
		cloud_col += LIGHT0_COLOR * pow(max(sun_dot, 0.0), 12.0) * (1.0 - core) * 0.9;
		cloud_col = mix(cloud_col, sunset_color.rgb * 0.9, sunset_amount * 0.55);
		cloud_col *= mix(1.0, 0.05, night_amount);
		// Cirrus: thin streaks high above, faster and only on fair days.
		vec2 cuv = dir.xz / (up + 0.06) * cloud_scale * 0.45 + drift * 2.2;
		float streak = texture(cloud_tex, vec2(cuv.x * 0.35, cuv.y * 1.4) + vec2(0.13, 0.57)).g;
		float cirrus = smoothstep(0.55, 0.9, streak) * (1.0 - cloud_cover) * 0.45 * smoothstep(0.02, 0.3, up);
		col = mix(col, mix(lit, horizon_color.rgb, 0.3) * mix(1.0, 0.05, night_amount), cirrus);
		col = mix(col, cloud_col, cloud_alpha);
	}

	// Stars + aurora at night.
	if (night_amount > 0.01 && up > 0.0) {
		vec2 suv = vec2(atan(dir.x, dir.z) / 6.2831853 + 0.5, acos(clamp(up, -1.0, 1.0)) / 3.1415926);
		vec3 stars = texture(star_tex, suv * vec2(2.0, 1.0)).rgb;
		col += stars * night_amount * (1.0 - cloud_alpha) * smoothstep(0.0, 0.25, up) * 1.4;
		if (aurora > 0.0) {
			float wave = sin(dir.x * 6.0 + TIME * 0.11) * 0.5 + 0.5;
			float curtain = smoothstep(0.08, 0.3, up) * smoothstep(0.75, 0.35, up) * wave;
			col += vec3(0.55, 0.85, 0.7) * curtain * aurora * 0.25 * (1.0 - cloud_alpha);
		}
	}

	// Sun disc and glow.
	if (LIGHT0_ENABLED) {
		float disc = smoothstep(sun_size, sun_size + 0.0003, sun_dot);
		col += LIGHT0_COLOR * LIGHT0_ENERGY * disc * 12.0 * (1.0 - cloud_alpha * 0.9) * (1.0 - night_amount);
		col += LIGHT0_COLOR * pow(max(sun_dot, 0.0), 220.0) * sun_glow * 4.0 * (1.0 - night_amount);
		col += LIGHT0_COLOR * pow(max(sun_dot, 0.0), 8.0) * sun_glow * 0.25 * (1.0 - night_amount);
	}
	// Moon disc.
	if (LIGHT1_ENABLED) {
		float md = dot(dir, LIGHT1_DIRECTION);
		if (md > moon_size) {
			vec3 t = normalize(cross(LIGHT1_DIRECTION, vec3(0.0, 1.0, 0.0)));
			vec3 b = cross(t, LIGHT1_DIRECTION);
			float r = sqrt(max(1.0 - moon_size * moon_size, 1e-6));
			vec2 muv = vec2(dot(dir, t), dot(dir, b)) / r * 0.5 + 0.5;
			vec4 m = texture(moon_tex, muv);
			col = mix(col, m.rgb * 1.6, m.a * (1.0 - cloud_alpha * 0.85));
		}
	}
	COLOR = col * sky_energy;
}
