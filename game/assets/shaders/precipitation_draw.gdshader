// How rain, snow and eave drips look (WeatherFx, ADR-0033; particles from precipitation.gdshader).
// One unit quad per particle, placed in world space here:
// * a falling drop is a streak along its motion (the particle's Y axis), turned to face the camera
//   and never thinner than about a pixel (a sub-pixel streak shimmers; a wider one is fainter by the
//   same factor, so far rain keeps its weight); its profile is drawn, not sampled;
// * a landed drop is a splash crown standing on the surface (the fx_splash flipbook);
// * a flake is a small soft disc facing the camera.
// Water is lit like anything else, so streaks catch lamps, torches and the lightning (from behind
// too: rain glows round a light), and mirror the sky's brightness by day.
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, skip_vertex_transform, diffuse_lambert_wrap, specular_schlick_ggx;

// 0 rain, 1 snow, 2 eave drips.
uniform int mode = 0;
uniform sampler2D splash_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform bool has_textures = false;
// Snowflakes up close (fx_snowflakes: 4x4 cells of crystal aggregates and graupel).
uniform sampler2D flake_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform bool has_flakes = false;
uniform float streak_length = 0.5;
uniform float streak_width = 0.0085;
uniform float splash_size = 0.15;
uniform float splash_s = 0.24;
uniform vec2 flake_size = vec2(0.014, 0.034);
uniform float opacity = 0.72;
// Fades out toward the column's edge (its half-width).
uniform float fade_far = 16.0;
// The particles' lifetime (s): a flake that never lands fades out before its cycle restarts it.
uniform float life = 10.0;

global uniform vec4 hm_sky_horizon;
global uniform vec4 hm_rain;

varying vec2 v_uv;
varying flat float v_kind;
varying flat float v_frame;
varying flat float v_variant;
varying float v_alpha;

void vertex() {
	vec3 c = MODEL_MATRIX[3].xyz;
	vec4 cu = INSTANCE_CUSTOM;
	vec3 to_cam = CAMERA_POSITION_WORLD - c;
	float dist = max(length(to_cam), 1e-3);
	to_cam /= dist;
	// The angle one pixel subtends.
	float px = 2.0 / (PROJECTION_MATRIX[1][1] * VIEWPORT_SIZE.y);
	vec3 world;
	v_uv = UV;
	v_variant = floor(cu.w * 3.999);
	v_frame = 0.0;
	v_alpha = smoothstep(0.35, 1.5, dist) * (1.0 - smoothstep(fade_far * 0.7, fade_far, dist));
	if (cu.x > 0.5 && mode != 1) {
		// A splash crown on the surface, facing the camera about the vertical. The flipbook's
		// surface line is 78% down its cell.
		vec3 side = normalize(cross(vec3(0.0, 1.0, 0.0), to_cam) + vec3(1e-4, 0.0, 0.0));
		float s = splash_size * (0.7 + 0.6 * cu.w) * (mode == 2 ? 1.5 : 1.0);
		s = max(s, dist * px * 6.0);
		world = c + side * VERTEX.x * s + vec3(0.0, 1.0, 0.0) * (VERTEX.y + 0.28) * s;
		v_kind = 1.0;
		v_frame = floor(clamp(cu.y / splash_s, 0.0, 0.999) * 16.0);
	} else if (mode == 1) {
		vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), to_cam) + vec3(1e-4, 0.0, 0.0));
		vec3 up = cross(to_cam, right);
		float s = mix(flake_size.x, flake_size.y, cu.w);
		float s_px = max(s, dist * px * 1.5);
		// Flakes tumble as they fall.
		float spin = TIME * (0.6 + 1.6 * fract(cu.w * 13.7)) + cu.w * 31.0;
		vec2 q = mat2(vec2(cos(spin), sin(spin)), vec2(-sin(spin), cos(spin))) * VERTEX.xy;
		world = c + (right * q.x + up * q.y) * s_px;
		v_variant = floor(fract(cu.w * 7.31) * 15.999);
		// How many pixels across the flake is (the fragment picks crystal or soft disc by it).
		v_frame = s_px / max(dist * px, 1e-6);
		v_alpha *= min(1.0, s * s / (s_px * s_px) * 1.6);
		// Settled flakes linger a moment, then go.
		v_alpha *= cu.x > 0.5 ? 1.0 - smoothstep(0.2, 0.6, cu.y) : smoothstep(0.0, 0.6, cu.y) * (1.0 - smoothstep(life - 0.8, life - 0.1, cu.y));
		v_kind = 2.0;
	} else {
		// An inactive particle comes with a zeroed transform: normalising its axis would make NaN
		// vertices, which a rasteriser may still turn into a stray NaN pixel (glow then blows each
		// one up into a white disc). Collapse it instead.
		float al = length(MODEL_MATRIX[1].xyz);
		vec3 axis = al > 1e-5 ? MODEL_MATRIX[1].xyz / al : vec3(0.0, 1.0, 0.0);
		vec3 side = cross(axis, to_cam);
		float sl = length(side);
		// Seen end-on a streak collapses: show the drop instead.
		side = sl > 1e-3 ? side / sl : normalize(cross(vec3(1.0, 0.0, 0.0), to_cam));
		float len = mode == 2 ? 0.07 + 0.1 * min(length(cu.y), 1.0) : streak_length * (0.75 + 0.5 * cu.w);
		float w = mode == 2 ? streak_width * 2.6 : streak_width;
		float w_px = max(w, dist * px * 1.1);
		world = c + axis * VERTEX.y * len + side * VERTEX.x * w_px;
		v_alpha *= w / w_px;
		if (mode == 0) {
			v_alpha *= smoothstep(0.0, 0.15, cu.y);
		}
		if (al <= 1e-5) {
			world = c;
			v_alpha = 0.0;
		}
		v_kind = 0.0;
	}
	VERTEX = (VIEW_MATRIX * vec4(world, 1.0)).xyz;
	NORMAL = normalize((VIEW_MATRIX * vec4(to_cam, 0.0)).xyz);
}

void fragment() {
	float a;
	if (v_kind < 0.5) {
		// The streak's profile is drawn here, not sampled: a streak a pixel or two wide would take
		// the generated streak cell's mip, in which the thin line has averaged away to nothing.
		// Clamped: an interpolated UV can land a hair outside 0..1 on a one-pixel streak's edge, and
		// pow() of a negative number is NaN.
		float x = clamp(1.0 - abs(v_uv.x * 2.0 - 1.0), 0.0, 1.0);
		float ends = smoothstep(0.0, 0.22, v_uv.y) * smoothstep(1.0, 0.7, v_uv.y);
		if (mode == 2) {
			// A drip: a round drop stretched by its fall.
			a = smoothstep(0.0, 0.6, x) * smoothstep(0.0, 0.35, v_uv.y) * smoothstep(1.0, 0.55, v_uv.y);
		} else {
			// Brighter where the drop catches the light, varying along its blur.
			a = pow(x, 1.4) * ends * (0.75 + 0.25 * sin(v_uv.y * 9.0 + v_variant * 1.7));
		}
	} else if (v_kind < 1.5) {
		if (has_textures) {
			vec2 cell = vec2(mod(v_frame, 4.0), floor(v_frame / 4.0));
			a = texture(splash_tex, (cell + v_uv) * 0.25).a;
		} else {
			vec2 q = v_uv * 2.0 - 1.0;
			a = smoothstep(1.0, 0.4, length(q * vec2(1.0, 2.5) + vec2(0.0, -1.0))) * 0.6;
		}
	} else {
		vec2 q = v_uv * 2.0 - 1.0;
		a = smoothstep(1.0, 0.25, length(q));
		if (has_flakes) {
			// A crystal's thin arms average away in the mips of a flake a few pixels across, which
			// left falling snow invisible: the atlas shows only up close, a soft disc further off.
			vec2 cell = vec2(mod(v_variant, 4.0), floor(v_variant / 4.0));
			float crystal = texture(flake_tex, (cell + v_uv) * 0.25).a * 1.3;
			a = mix(a, crystal, smoothstep(10.0, 22.0, v_frame));
		}
	}
	float alpha = a * v_alpha * (v_kind > 1.5 ? 0.95 : opacity);
	// Written so that a NaN is discarded too (every comparison with NaN is false).
	if (!(alpha >= 0.004)) {
		discard;
	}
	alpha = min(alpha, 1.0);
	vec3 water = vec3(0.5, 0.55, 0.6);
	ALBEDO = v_kind > 1.5 ? vec3(0.92, 0.94, 0.97) : water;
	ALPHA = alpha;
	ROUGHNESS = v_kind > 1.5 ? 0.85 : 0.15;
	// Water mirrors the sky around it (dark at night, when only lamps, torches and the lightning
	// light it), so by day a streak reads lighter than a wall or the road behind it and fades into
	// the sky itself; the flash shows in every drop.
	EMISSION = hm_sky_horizon.rgb * (v_kind > 1.5 ? 0.15 : 0.62) + vec3(0.75, 0.8, 1.0) * hm_rain.z * 0.6;
	BACKLIGHT = v_kind > 1.5 ? vec3(0.5) : vec3(0.85, 0.88, 0.92);
}
