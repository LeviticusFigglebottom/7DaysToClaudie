// Hollowmere character cloth (ADR-0028): every garment a Hollowed (or the player) wears.
//  * A fabric BRDF in light(): wrapped diffuse (light creeps round the folds), GGX specular and a
//    fibre sheen at grazing angles; the direct light only, Godot still adds sky and GI.
//  * Seams and stitching from the generator's seam field (CUSTOM1.y: signed distance to the seam
//    lines in metres), hem stitching a little in from hemmed edges, fraying and dirt along torn ones
//    (CUSTOM1.w). Distances interpolate linearly across a triangle, so the lines stay crisp on a
//    body whose triangles are centimetres across.
//  * Trim inside the trim field (CUSTOM1.x < 0): the Cordon's retroreflective tape flares back at
//    whoever holds the light, like the bridge delineators (retroreflector.gdshader).
//  * Blood and grime soaked in where vertex G is high; rain darkens and glosses it.
// Vertex data and instance uniforms: character.gdshaderinc.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;

#include "res://assets/shaders/character.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float uv_scale = 3.0;
uniform float normal_strength : hint_range(0.0, 3.0) = 1.0;
uniform float roughness_add = 0.0;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 1.0;
uniform float variation_strength = 0.08;

uniform sampler2D wear_albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float wear_amount : hint_range(0.0, 1.0) = 0.0;
uniform float wear_uv_scale = 1.0;
// Dirt where vertex A is high (bodies only: hm_char_dirt). 0 = none.
uniform float dirt_amount : hint_range(0.0, 2.0) = 0.0;
uniform vec4 dirt_color : source_color = vec4(0.22, 0.18, 0.13, 1.0);
// Grime gathers in the creases (low baked AO).
uniform vec4 grime_color : source_color = vec4(0.16, 0.14, 0.11, 1.0);
uniform float grime_amount : hint_range(0.0, 1.0) = 0.0;

// Fabric light.
uniform float wrap : hint_range(0.0, 1.0) = 0.35;
uniform float sheen : hint_range(0.0, 2.0) = 0.4;
uniform vec4 sheen_tint : source_color = vec4(1.0);
// Porous cloth soaks up rain (darker, less glossy than skin).
uniform float porous : hint_range(0.0, 1.0) = 0.8;

// Seams and stitching.
uniform float seam_width = 0.0035;
uniform float seam_shade : hint_range(0.0, 1.0) = 0.45;
uniform vec4 stitch_color : source_color = vec4(0.62, 0.58, 0.50, 1.0);
uniform float stitch_rows = 0.004;
uniform float stitch_amount : hint_range(0.0, 1.0) = 0.6;
uniform float hem_inset = 0.012;
// Torn edges: frayed, paler threads, dirt.
uniform vec4 fray_color : source_color = vec4(0.62, 0.58, 0.52, 1.0);
uniform float fray_width = 0.02;

// Trim (tape, stripes, patches) inside the trim field.
uniform float trim : hint_range(0.0, 1.0) = 0.0;
uniform vec4 trim_color : source_color = vec4(0.72, 0.73, 0.72, 1.0);
uniform float trim_roughness = 0.35;
// Retroreflective trim: strength of the light thrown back toward its source, and the lobe's width
// (cosine of its half-angle).
uniform float trim_retro = 0.0;
uniform float retro_cos = 0.985;

varying float v_retro;

void vertex() {
	v_rest = vec3(UV2, CUSTOM0.x);
	v_attr0 = CUSTOM0;
	v_attr1 = CUSTOM1;
	if (hm_gated_out(CUSTOM0.y, bloom_glow, hollow_burst)) {
		VERTEX = vec3(0.0);
	}
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 alb = texture(albedo_tex, uv).rgb * tint.rgb;
	vec3 nrm = texture(normal_tex, uv).rgb;
	vec3 orm = texture(orm_tex, uv).rgb;
	float rough = clamp(orm.g + roughness_add, 0.02, 1.0);
	vec3 rest = v_rest;
	alb *= 1.0 + (instance_variation - 0.5) * variation_strength * 2.0;
	float ao_shade = 1.0;
	v_retro = 0.0;

	// Trim.
	if (trim > 0.0) {
		float tm = hm_sd_mask(v_attr1.x, 0.0005) * trim;
		// Tape gets grubby and cracks: the grime texture shows through in flecks.
		float crack = smoothstep(0.62, 0.72, hm_char_noise(rest * 160.0));
		alb = mix(alb, trim_color.rgb * (0.88 + 0.16 * hm_char_noise(rest * 40.0)) * (1.0 - 0.5 * crack), tm);
		rough = mix(rough, trim_roughness, tm);
		v_retro = tm * trim_retro * (1.0 - crack);
	}

	// Seams: a shadowed groove where panels meet, with a row of stitches either side.
	float seam = v_attr1.y;
	float sw = fwidth(seam);
	if (abs(seam) < 0.03 && sw < 0.01) {
		float groove = 1.0 - smoothstep(seam_width * 0.5, seam_width * 0.5 + sw * 1.5, abs(seam));
		ao_shade *= 1.0 - groove * seam_shade;
		float row = 1.0 - smoothstep(0.0008, 0.0008 + sw * 1.2, abs(abs(seam) - stitch_rows));
		// Dashes: stitches about 3 mm long. The seam has no length coordinate, so two crossed
		// periodic sheets in rest space stand in for one; either breaks the row into dashes.
		float dash = step(0.45, fract(dot(rest, vec3(211.0, 173.0, 97.0)))) * step(0.4, fract(dot(rest, vec3(-89.0, 197.0, 151.0))));
		alb = mix(alb, stitch_color.rgb, row * dash * stitch_amount * (1.0 - smoothstep(0.0012, 0.004, sw)));
	}
	// Hems: a stitch row hem_inset in from a hemmed edge. Torn edges fray and gather dirt.
	float edge = v_attr1.w;
	if (edge > 0.0 && edge < hem_inset * 2.5) {
		float ew = fwidth(edge);
		float hrow = 1.0 - smoothstep(0.0008, 0.0008 + ew * 1.2, abs(edge - hem_inset));
		float dash = step(0.45, fract(dot(rest, vec3(211.0, 173.0, 97.0))));
		alb = mix(alb, stitch_color.rgb, hrow * dash * stitch_amount * (1.0 - smoothstep(0.0012, 0.004, ew)));
		ao_shade *= 1.0 - 0.25 * (1.0 - smoothstep(0.0, 0.004, edge));
	} else if (edge < 0.0) {
		float t = 1.0 - smoothstep(0.0, fray_width, -edge);
		float threads = hm_char_noise(rest * vec3(400.0, 90.0, 400.0)) * t;
		alb = mix(alb, fray_color.rgb * dot(alb, vec3(0.5)) * 2.2, smoothstep(0.35, 0.8, threads) * 0.6);
		alb = mix(alb, grime_color.rgb, t * 0.35);
	}

	// Dirt, then blood over it.
	hm_char_dirt(alb, rough, COLOR.a, COLOR.r, rest, dirt_amount, dirt_color.rgb);
	// Blood.
	float wear_level = instance_wear >= 0.0 ? instance_wear : wear_amount;
	if (wear_level > 0.001) {
		vec2 wuv = UV * wear_uv_scale;
		vec3 wa = texture(wear_albedo_tex, wuv).rgb;
		float threshold = 1.0 - wear_level * (0.6 + COLOR.g * 0.9);
		float wm = smoothstep(threshold - 0.08, threshold + 0.08, COLOR.g * 0.7 + dot(wa, vec3(0.333)) * 0.5);
		alb = mix(alb, wa, wm);
		nrm = mix(nrm, texture(wear_normal_tex, wuv).rgb, wm);
		rough = mix(rough, texture(wear_orm_tex, wuv).g, wm);
		v_retro *= 1.0 - wm;
	}
	float vao = mix(1.0, COLOR.r, vertex_ao_strength);
	if (grime_amount > 0.001) {
		float g = grime_amount * clamp((1.0 - vao) * 1.5, 0.0, 1.0);
		alb = mix(alb, grime_color.rgb, g);
		rough = mix(rough, 0.95, g);
	}

	hm_char_weather(alb, rough, porous, v_world_normal, weather_exposure);

	ALBEDO = clamp(alb, vec3(0.0), vec3(1.0));
	ROUGHNESS = rough;
	METALLIC = 0.0;
	AO = orm.r * vao * ao_shade;
	AO_LIGHT_AFFECT = 0.35;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float nl = clamp(ndl, 0.0, 1.0);
	// Wrapped, energy-normalised diffuse.
	float d = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0) / (1.0 + wrap);
	DIFFUSE_LIGHT += d * ATTENUATION * LIGHT_COLOR / PI;
	float nv = clamp(dot(NORMAL, VIEW), 0.001, 1.0);
	vec3 h = normalize(LIGHT + VIEW);
	float nh = clamp(dot(NORMAL, h), 0.0, 1.0);
	float a = max(ROUGHNESS * ROUGHNESS, 0.002);
	float a2 = a * a;
	float dn = nh * nh * (a2 - 1.0) + 1.0;
	float D = a2 / (PI * dn * dn);
	float k = (ROUGHNESS + 1.0) * (ROUGHNESS + 1.0) / 8.0;
	float G = (nl / (nl * (1.0 - k) + k)) * (nv / (nv * (1.0 - k) + k));
	float F = 0.04 + 0.96 * pow(1.0 - clamp(dot(h, VIEW), 0.0, 1.0), 5.0);
	float spec = D * G * F / max(4.0 * nl * nv, 0.001) * nl;
	SPECULAR_LIGHT += spec * ATTENUATION * LIGHT_COLOR * SPECULAR_AMOUNT;
	// Fibre sheen: a soft rim where the cloth turns away, tinted by the cloth.
	float rim = pow(1.0 - nv, 4.0) * smoothstep(-0.2, 0.4, ndl);
	SPECULAR_LIGHT += rim * sheen * sheen_tint.rgb * ALBEDO * ATTENUATION * LIGHT_COLOR / PI;
	if (v_retro > 0.0) {
		float back = smoothstep(retro_cos, 1.0, dot(LIGHT, VIEW));
		SPECULAR_LIGHT += back * sqrt(nl) * ATTENUATION * LIGHT_COLOR * v_retro * (1.0 - 0.3 * hm_wetness);
	}
}
