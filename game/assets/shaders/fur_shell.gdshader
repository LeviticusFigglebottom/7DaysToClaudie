shader_type spatial;
// Fur shells for the wildlife coats (TD-067): extra passes of a fur material (its next_pass chain,
// written by tools/assetgen/textures/materials.py from a material's "shells" block) that draw the
// mesh again pushed out along its normals, each a slice higher up the hair, keeping only the
// texels a strand passes through. Stacked, they give the coat depth and a soft, broken silhouette
// over the smooth skin the base fur.gdshader pass draws.
//
// Strands come from a hashed grid in the coat's UV space (UVs run with the lie of the hair, so the
// cells are stretched along it): each strand thins toward its tip, leans with the lie of the hair
// and droops a little under gravity. The coat colour matches fur.gdshader (vertex colour G = the
// pale coat, B = the dark coat, R = AO) and darkens toward the roots. No shells on the wet nose
// (B near 1) or where a coat is soaked (hm_wetness lays the hair flat). Shells stop at
// `fade_end` (fragments thinned out from fade_end * 0.6), so far deer cost their vertices only.

render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 base_color : source_color = vec4(0.45, 0.34, 0.24, 1.0);
uniform vec4 pale_color : source_color = vec4(0.85, 0.82, 0.76, 1.0);
uniform vec4 dark_color : source_color = vec4(0.16, 0.13, 0.11, 1.0);
uniform float uv_scale = 8.0;
uniform float grain : hint_range(0.0, 1.0) = 0.6;
uniform float roughness = 0.82;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 1.0;
uniform float sheen : hint_range(0.0, 1.0) = 0.35;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.6;
uniform float backlight_amount : hint_range(0.0, 1.0) = 0.15;
uniform vec4 backlight_color : source_color = vec4(0.7, 0.32, 0.2, 1.0);
// This shell's height as a fraction of the hair (0 < shell_k <= 1) and the hair's length (m).
uniform float shell_k = 0.5;
uniform float shell_length = 0.01;
// Strand cells per strand-texture tile across (u) and along (v) the hair's lie.
uniform vec2 strand_cells = vec2(48.0, 16.0);
// How much of a cell a strand fills at its root (radius, fraction of the cell).
uniform float strand_width : hint_range(0.05, 0.5) = 0.38;
uniform float fade_end = 14.0;
// Same slot as fur.gdshader's (the shells follow the animal's coat variation).
instance uniform float instance_variation : instance_index(1) = 0.5;
global uniform float hm_wetness;

varying float v_dist;
varying float v_len;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void vertex() {
	float wet = clamp(hm_wetness, 0.0, 1.0);
	// No hair on the wet nose; soaked hair lies flat.
	float len = shell_length * shell_k * (1.0 - smoothstep(0.88, 0.97, COLOR.b)) * (1.0 - 0.7 * wet);
	v_len = len;
	VERTEX += NORMAL * len;
	// Gravity: the tips droop (model space: +Y up).
	VERTEX.y -= len * 0.35 * shell_k;
	v_dist = length((MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz);
}

void fragment() {
	if (v_len < 0.0005 || v_dist > fade_end) {
		discard;
	}
	vec2 suv = UV * uv_scale * strand_cells;
	// Strands lean along the lie of the hair (v): shift the cell sample with height.
	suv.y -= shell_k * 0.6;
	vec2 cell = floor(suv);
	vec2 f = fract(suv) - 0.5;
	float h = hash12(cell);
	f += (vec2(hash12(cell + 17.0), hash12(cell + 41.0)) - 0.5) * 0.3;
	// Each strand has its own length: short ones end in the lower shells.
	float strand_len = 0.45 + 0.55 * h;
	float r = strand_width * (1.0 - shell_k / strand_len);
	// Cells are stretched along the hair: weigh the across-hair distance up.
	float d = length(f * vec2(1.0, 0.45));
	// Far away the shells thin out (dithered by the strand hash) before they stop.
	float keep = 1.0 - smoothstep(fade_end * 0.6, fade_end, v_dist);
	if (shell_k > strand_len || d > r || hash12(cell + 7.0) > keep) {
		discard;
	}
	vec3 tex = texture(albedo_tex, UV * uv_scale).rgb;
	vec3 coat = mix(base_color.rgb, pale_color.rgb, COLOR.g);
	coat = mix(coat, dark_color.rgb, COLOR.b);
	coat *= 0.92 + 0.16 * instance_variation;
	vec3 alb = coat * mix(vec3(1.0), tex * 2.0, grain);
	// Roots sit in the coat's shade; tips catch the light (and bleach a little).
	alb *= mix(0.72, 1.12, shell_k) * (0.9 + 0.2 * h);
	alb *= 1.0 - 0.3 * clamp(hm_wetness, 0.0, 1.0);
	ALBEDO = alb;
	AO = mix(1.0, COLOR.r, vertex_ao_strength) * mix(0.6, 1.0, shell_k);
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = roughness;
	SPECULAR = 0.3;
	RIM = sheen * shell_k;
	RIM_TINT = sheen_tint;
	BACKLIGHT = backlight_color.rgb * backlight_amount * (0.5 + shell_k);
}
