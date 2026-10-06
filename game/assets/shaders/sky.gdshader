// Hollowmere sky: time-of-day gradient, sun disc + forward scattering, the moon, stars, a scrolling
// cloud layer (coverage driven by weather) and a faint Bloom aurora on Hum nights.
// Clouds shade themselves cheaply: the density a step toward the sun says whether a point faces
// the sun or sits behind the cloud's mass, and thick cores darken, so they read as volumes rather
// than cut-outs. A thin, streaky cirrus veil sits above them on fair days.
// The sun and the moon come in as uniforms from EnvironmentController (not LIGHT0/LIGHT1: a hidden
// sun drops out of the light list at night and the moon would take its slot).
// The moon (ADR-0023) is a sphere lit by the sun: its phase comes from moon_sun_dir, the sunlight
// direction at the moon, shaded with the Lommel-Seeliger law (a full moon is flat, not limb-dark).
// The night side keeps a faint earthshine, strongest at new moon when the Earth is "full" from the
// moon. Moonlight brightens the night sky, silvers the clouds and drowns the fainter stars.
// Lightning (ADR-0033) lights the cloud deck from within, most of all over the strike, and a strike
// near enough draws its bolt: a jagged channel from the cloud base down to the horizon on its
// bearing, wandering a few hundred metres, with a glow round it.
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
uniform vec3 sun_dir = vec3(0.0, 0.7, 0.7);
uniform vec3 sun_color = vec3(1.0, 0.95, 0.88);
uniform float sun_energy = 1.0;
uniform sampler2D cloud_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D star_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D moon_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform float cloud_cover : hint_range(0.0, 1.0) = 0.35;
uniform float cloud_darkness : hint_range(0.0, 1.0) = 0.0;
uniform vec2 cloud_wind = vec2(0.004, 0.0015);
uniform float cloud_scale = 0.35;
uniform float aurora = 0.0;
// Moon: direction to it, the sunlight direction at it, its angular radius (radians), the lit
// fraction, the disc's radiance, earthshine on its night side, its aureole and how much moonlight
// is in the sky (0 new moon or set .. 1 high full moon).
uniform vec3 moon_dir = vec3(0.0, 0.5, 0.86);
uniform vec3 moon_sun_dir = vec3(0.0, 1.0, 0.0);
uniform float moon_radius = 0.028;
uniform float moon_illum : hint_range(0.0, 1.0) = 1.0;
uniform float moon_disc_energy = 2.2;
uniform vec3 moon_color = vec3(0.73, 0.78, 0.9);
uniform float earthshine = 0.05;
uniform float moon_glow = 0.0;
uniform float moon_sky = 0.0;
uniform float star_visibility = 1.0;
// The star sphere turns about the celestial pole once a sidereal day (EnvironmentController).
uniform mat3 star_rotation = mat3(1.0);
// Lightning: the flash on the clouds, toward the strike's cloud base; the bolt's brightness, shape
// seed and distance (m).
uniform float lightning = 0.0;
uniform vec3 lightning_dir = vec3(0.0, 1.0, 0.0);
uniform float bolt = 0.0;
uniform float bolt_seed = 0.0;
uniform float bolt_distance = 3000.0;

float bolt_hash(float n) {
	return fract(sin(n * 12.9898 + bolt_seed * 78.233) * 43758.5453);
}

float bolt_noise(float x) {
	float i = floor(x);
	float f = fract(x);
	return mix(bolt_hash(i), bolt_hash(i + 1.0), f * f * (3.0 - 2.0 * f));
}

// Sideways wander of the channel (radians of azimuth) at height t (0 ground .. 1 cloud base).
float bolt_path(float t) {
	float w = (bolt_noise(t * 5.0) - 0.5) + (bolt_noise(t * 13.0 + 3.1) - 0.5) * 0.5 + (bolt_noise(t * 37.0 + 7.7) - 0.5) * 0.22
		+ (bolt_noise(t * 97.0 + 1.3) - 0.5) * 0.08;
	return w * 380.0 / max(bolt_distance, 100.0);
}

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

void sky() {
	vec3 dir = EYEDIR;
	float up = dir.y;
	// Base gradient.
	float h = clamp(up, 0.0, 1.0);
	vec3 col = mix(horizon_color.rgb, zenith_color.rgb, pow(h, 0.55));
	// Sunset band toward the sun.
	float sun_dot = dot(dir, sun_dir);
	float band = exp(-abs(up) * 6.0) * (0.45 + 0.55 * max(sun_dot, 0.0));
	col = mix(col, sunset_color.rgb, band * sunset_amount);
	// Below horizon: dark ground haze.
	col = mix(col, ground_color.rgb, smoothstep(0.0, -0.12, up));

	// Where the moon's disc covers the sky (stars behind it are hidden, its dark limb included).
	float md = dot(dir, moon_dir);
	float mcos = cos(moon_radius);
	float msin = sin(moon_radius);
	float moon_cover = 0.0;
	vec3 moon_rgb = vec3(0.0);
	if (md > mcos - 0.002 && moon_dir.y > -moon_radius) {
		vec3 t = normalize(cross(moon_dir, vec3(0.0, 1.0, 0.0)));
		vec3 b = cross(t, moon_dir);
		vec2 q = vec2(dot(dir, t), dot(dir, b)) / msin;
		float rr = dot(q, q);
		// The texture's disc fills 94% of its width (sky.py moon_disc); image rows run downward.
		vec4 m = texture(moon_tex, vec2(q.x, -q.y) * 0.47 + 0.5);
		float edge = fwidth(rr) + 0.004;
		moon_cover = (1.0 - smoothstep(1.0 - edge, 1.0 + edge, rr)) * smoothstep(-0.004, 0.004, up);
		float mu = sqrt(max(1.0 - rr, 0.0));
		vec3 n = q.x * t + q.y * b - mu * moon_dir;
		float mu0 = dot(n, moon_sun_dir);
		// Lommel-Seeliger (x2 so a full moon's centre is 1), with a narrow soft terminator.
		float lit = 2.0 * max(mu0, 0.0) / (max(mu0, 0.0) + mu + 1e-4) * smoothstep(-0.04, 0.05, mu0);
		vec3 albedo = m.rgb;
		vec3 earth = vec3(0.55, 0.68, 1.0) * earthshine * (1.0 - moon_illum) * (1.0 - smoothstep(-0.05, 0.1, mu0));
		moon_rgb = albedo * (moon_color * lit * moon_disc_energy + earth);
	}

	// Clouds (planar projection on a dome).
	float cloud_alpha = 0.0;
	if (up > 0.0) {
		vec2 drift = TIME * cloud_wind;
		vec2 uv = dir.xz / (up + 0.18) * cloud_scale + drift;
		float density = cloud_density(uv, drift);
		float threshold = mix(0.78, 0.18, cloud_cover);
		cloud_alpha = smoothstep(threshold, threshold + 0.22, density) * smoothstep(0.0, 0.12, up);
		vec3 lit = mix(vec3(1.0), sun_color * 0.9 + 0.1, 0.5) * mix(1.0, 0.45, cloud_darkness);
		// More cloud toward the sun: this point is on the far, shaded side of the mass.
		vec2 sun_step = normalize(sun_dir.xz + vec2(1e-4)) * 0.05;
		float mass = cloud_mass(uv);
		float toward = cloud_mass(uv + sun_step);
		float core = smoothstep(threshold + 0.1, threshold + 0.45, mass);
		float shade = clamp((toward - mass) * 7.0 + 0.2 + core * 0.5, 0.0, 1.0);
		vec3 shadow_col = mix(horizon_color.rgb, zenith_color.rgb, 0.35) * mix(0.8, 0.45, cloud_darkness);
		// A full deck is lit from above as one sheet: shading flattens as cover closes.
		vec3 cloud_col = mix(lit, shadow_col, shade * mix(0.85, 0.4, smoothstep(0.6, 1.0, cloud_cover)));
		cloud_col += sun_color * pow(max(sun_dot, 0.0), 12.0) * (1.0 - core) * 0.9;
		cloud_col = mix(cloud_col, sunset_color.rgb * 0.9, sunset_amount * 0.55);
		// At night clouds go dark, unless the moon lights them: grey-blue bodies, a silver edge
		// where they thin out in front of it.
		float moon_lit = moon_sky * (0.32 + 0.5 * pow(max(md, 0.0), 6.0));
		cloud_col *= mix(1.0, 0.05 + moon_lit, night_amount);
		cloud_col += moon_color * pow(max(md, 0.0), 40.0) * (1.0 - core) * moon_sky * 0.9 * night_amount;
		// Cirrus: thin streaks high above, faster and only on fair days.
		vec2 cuv = dir.xz / (up + 0.06) * cloud_scale * 0.45 + drift * 2.2;
		float streak = texture(cloud_tex, vec2(cuv.x * 0.35, cuv.y * 1.4) + vec2(0.13, 0.57)).g;
		float cirrus = smoothstep(0.55, 0.9, streak) * (1.0 - cloud_cover) * 0.45 * smoothstep(0.02, 0.3, up);
		col = mix(col, mix(lit, horizon_color.rgb, 0.3) * mix(1.0, 0.05 + moon_sky * 0.35, night_amount), cirrus);
		// Lightning lights the deck from inside: thick cores glow, the strike's quarter most.
		if (lightning > 0.001) {
			float toward = pow(max(dot(dir, lightning_dir), 0.0), 3.0);
			cloud_col += vec3(0.7, 0.76, 1.0) * lightning * (0.12 + 0.88 * toward) * (0.35 + 0.65 * core);
			col += vec3(0.5, 0.55, 0.75) * lightning * 0.08 * (0.3 + toward);
		}
		col = mix(col, cloud_col, cloud_alpha);
	}
	// The bolt, from the cloud base over the strike down to the horizon.
	if (bolt > 0.001) {
		float baz = atan(lightning_dir.z, lightning_dir.x);
		float top = asin(clamp(lightning_dir.y, -1.0, 1.0));
		float el = asin(clamp(up, -1.0, 1.0));
		if (el > -0.005 && el < top) {
			float t = el / max(top, 1e-3);
			float daz = mod(atan(dir.z, dir.x) - baz + 3.14159265, 6.2831853) - 3.14159265;
			float dx = (daz - bolt_path(t)) * cos(el);
			// A core a pixel or two wide and a glow round it; a fork leaves it halfway down.
			float w = 0.0012 + 0.0006 * (1.0 - t);
			float core = exp(-dx * dx / (w * w));
			float glow = exp(-abs(dx) / (w * 14.0)) * 0.35;
			float fork = 0.0;
			if (t > 0.25 && t < 0.62) {
				float fx = (daz - bolt_path(0.62) - (0.62 - t) * 0.5 * (bolt_hash(5.0) - 0.3) * 600.0 / max(bolt_distance, 100.0) - (bolt_noise(t * 41.0 + 9.0) - 0.5) * 0.06 * 380.0 / max(bolt_distance, 100.0)) * cos(el);
				fork = exp(-fx * fx / (w * w * 0.4)) * smoothstep(0.25, 0.45, t) * 0.6;
			}
			col += vec3(0.85, 0.9, 1.0) * (core * 9.0 + glow + fork * 5.0) * bolt * smoothstep(-0.005, 0.01, up);
		}
	}

	// Stars + aurora at night. Moonlight scatters in the air and drowns the faint stars, most of all
	// around the moon.
	if (night_amount > 0.01 && up > 0.0) {
		vec3 sdir = star_rotation * dir;
		// The star map is a 2:1 equirect with its stars pre-stretched in longitude (sky.py), so it
		// wraps once: tiling it twice squeezed every star into a dash along its meridian.
		vec2 suv = vec2(atan(sdir.x, sdir.z) / 6.2831853 + 0.5, acos(clamp(sdir.y, -1.0, 1.0)) / 3.1415926);
		vec3 stars = texture(star_tex, suv).rgb;
		float glare = moon_sky * smoothstep(0.86, 0.995, md);
		float vis = star_visibility * (1.0 - glare) * (1.0 - moon_cover);
		col += stars * night_amount * vis * (1.0 - cloud_alpha) * smoothstep(0.0, 0.25, up) * 1.4;
		if (aurora > 0.0) {
			float wave = sin(dir.x * 6.0 + TIME * 0.11) * 0.5 + 0.5;
			float curtain = smoothstep(0.08, 0.3, up) * smoothstep(0.75, 0.35, up) * wave;
			col += vec3(0.55, 0.85, 0.7) * curtain * aurora * 0.25 * (1.0 - cloud_alpha);
		}
	}

	// Sun disc and glow.
	float day_vis = 1.0 - night_amount;
	if (day_vis > 0.0) {
		float disc = smoothstep(sun_size, sun_size + 0.0003, sun_dot) * smoothstep(-0.01, 0.004, up);
		col += sun_color * sun_energy * disc * 12.0 * (1.0 - cloud_alpha * 0.9) * day_vis;
		col += sun_color * pow(max(sun_dot, 0.0), 220.0) * sun_glow * 4.0 * day_vis;
		col += sun_color * pow(max(sun_dot, 0.0), 8.0) * sun_glow * 0.25 * day_vis;
	}

	// The moon: an aureole in the haze (wider and stronger through thin cloud), then the disc over
	// the sky behind it. By day the disc is faint against the blue, as it should be.
	if (moon_glow > 0.0 && moon_dir.y > -0.1) {
		float g = pow(max(md, 0.0), 1800.0) * 0.6 + pow(max(md, 0.0), 90.0) * 0.08 + pow(max(md, 0.0), 12.0) * 0.012;
		col += moon_color * g * moon_glow * (1.0 + cloud_alpha * 2.0) * smoothstep(-0.05, 0.05, up);
	}
	if (moon_cover > 0.0) {
		float through = 1.0 - cloud_alpha * 0.92;
		col = mix(col, col * (1.0 - night_amount * 0.9) + moon_rgb * through, moon_cover);
	}
	COLOR = col * sky_energy;
}
