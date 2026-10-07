// Foliage cards / fronds / grass: alpha-cut, double-sided, translucent, wind + seasons.
// Vertex colour: R = AO, A = wind weight. hm_season = (spring, summer, autumn, winter) weights.
// Inside the Bloom (the field at the plant's foot, ADR-0025) plants wilt: they desaturate toward the
// material's wilt tint (ferns brown, grass greys), lose their translucency, thin out and droop, and
// fronds curl in toward the crown. Materials opt in with bloom_wilt > 0.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/wind.gdshaderinc"
#include "res://assets/shaders/bloom.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic;
uniform float alpha_scissor : hint_range(0.0, 1.0) = 0.42;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 spring_tint : source_color = vec4(1.05, 1.08, 0.95, 1.0);
uniform vec4 summer_tint : source_color = vec4(1.0);
uniform vec4 autumn_tint : source_color = vec4(1.0);
uniform vec4 winter_tint : source_color = vec4(0.85, 0.85, 0.82, 1.0);
// Deciduous species drop leaves in winter (alpha threshold rises with the winter weight).
uniform float winter_leaf_loss : hint_range(0.0, 1.0) = 0.0;
uniform float translucency : hint_range(0.0, 2.0) = 0.6;
uniform float sway_height = 18.0;
uniform float stiffness = 1.0;
uniform float flutter_strength = 1.0;
uniform float ao_strength : hint_range(0.0, 1.0) = 0.85;
uniform float normal_strength = 1.0;
uniform float roughness = 0.75;
// Alpha-tested needles and leaves thin out with distance because mipmaps average their alpha
// towards the background; scaling alpha up by the mip level keeps crowns and ferns dense (after
// Ben Golus, "Anti-aliased Alpha Test").
uniform float mip_alpha_scale = 0.25;
// Wire mesh (chain-link, chicken wire: TD-237) wants the opposite: a thin wire's mip alpha is its
// true coverage (~0.2), and scaling it up filled the diamonds, so a fence read as a solid panel at
// distance. With coverage_dither = 1 (and mip_alpha_scale = 0) the alpha test fades from the fixed
// scissor near to a screen-space ordered dither once the texture minifies, so a far fence keeps
// the coverage of its mips: a fine see-through screen, not a wall.
uniform float coverage_dither : hint_range(0.0, 1.0) = 0.0;
const float BAYER4[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
// The Bloom: how far this plant wilts at full strength (0 = never), the colour it dies back to
// (multiplied into its desaturated self), how far its tips droop and curl in (fraction of their
// height), and how much it thins (alpha threshold).
uniform float bloom_wilt : hint_range(0.0, 1.0) = 0.0;
uniform vec4 bloom_wilt_tint : source_color = vec4(0.6, 0.46, 0.31, 1.0);
uniform float bloom_droop : hint_range(0.0, 1.0) = 0.0;
uniform float bloom_thin : hint_range(0.0, 0.5) = 0.0;

global uniform vec4 hm_season;
#include "res://assets/shaders/weather.gdshaderinc"
global uniform float hm_snow;

varying vec3 v_world_normal;
varying float v_wilt;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	// Ground cover (VegetationManager's ground layer) carries its fade distance as a negative
	// INSTANCE_CUSTOM.a and shrinks away plant by plant over the last fifth of it, so nothing pops
	// out in whole blocks. Other MultiMeshes leave .a >= 0.
	if (INSTANCE_CUSTOM.a < 0.0) {
		VERTEX *= 1.0 - smoothstep(-INSTANCE_CUSTOM.a * 0.8, -INSTANCE_CUSTOM.a, distance(origin, CAMERA_POSITION_WORLD));
	}
	v_wilt = 0.0;
	if (bloom_wilt > 0.0) {
		v_wilt = smoothstep(0.08, 0.6, hm_bloom_at(origin.xz)) * bloom_wilt;
		// Tips (high wind weight) droop toward the ground and curl in toward the crown; the base
		// stays where it grows.
		float c = v_wilt * bloom_droop * COLOR.a * COLOR.a;
		VERTEX.y -= max(VERTEX.y, 0.0) * c * 0.75;
		VERTEX.xz *= 1.0 - c * 0.35;
	}
	vec3 wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.xz += hm_plant_sway(VERTEX, origin, sway_height, stiffness, TIME);
	// Wilted plants hang limp: less flutter.
	VERTEX += hm_flutter(wpos, NORMAL, COLOR.a * flutter_strength * (1.0 - 0.6 * v_wilt), TIME);
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec4 season = hm_season.x * spring_tint + hm_season.y * summer_tint + hm_season.z * autumn_tint + hm_season.w * winter_tint;
	float wsum = max(0.001, hm_season.x + hm_season.y + hm_season.z + hm_season.w);
	vec3 col = a.rgb * tint.rgb * (season.rgb / wsum);
	float threshold = mix(alpha_scissor, 1.01, hm_season.w / wsum * winter_leaf_loss);
	float trans = translucency;
	if (v_wilt > 0.001) {
		// Dying back: the green drains out (luminance kept) into the wilt tint, unevenly from frond
		// to frond (the generators' per-card variation, COLOR.b), and the tissue stops letting light
		// through.
		float lum = dot(col, vec3(0.299, 0.587, 0.114));
		float w = clamp(v_wilt * (0.7 + 0.6 * COLOR.b), 0.0, 1.0);
		// The tint is the dead colour of a mid-toned leaf; the texture's light and shade stay.
		col = mix(col, bloom_wilt_tint.rgb * (0.35 + 2.6 * lum), w);
		trans *= 1.0 - 0.7 * w;
		threshold = min(threshold + bloom_thin * w, 0.98);
	}
	vec3 orm = texture(orm_tex, UV).rgb;
	// Snow rides the upper faces of fronds and needles, in clumps (ADR-0033); wet leaves darken a
	// little under their film of water.
	float snow = hm_snow * smoothstep(0.25, 0.75, v_world_normal.y);
	if (snow > 0.001) {
		snow = smoothstep(0.0, 0.3, snow * 1.2 - (wx_noise(UV * 7.0 + COLOR.b * 11.0) - 0.5) * 0.5 * (1.0 - hm_snow));
	}
	col = mix(col, vec3(0.88, 0.9, 0.93), snow);
	col *= mix(1.0, 0.82, hm_wetness * (1.0 - snow));
	trans *= 1.0 - 0.6 * snow;
	ALBEDO = col * mix(1.0, COLOR.r, ao_strength);
	vec2 texel = UV * vec2(textureSize(albedo_tex, 0));
	vec2 ddx = dFdx(texel);
	vec2 ddy = dFdy(texel);
	float mip = max(0.0, 0.5 * log2(max(dot(ddx, ddx), dot(ddy, ddy))));
	ALPHA = min(1.0, a.a * (1.0 + mip * mip_alpha_scale));
	if (coverage_dither > 0.0) {
		ivec2 px = ivec2(FRAGCOORD.xy) % 4;
		float dither = (BAYER4[px.y * 4 + px.x] + 0.5) / 16.0;
		threshold = mix(threshold, dither, coverage_dither * smoothstep(0.75, 2.25, mip));
	}
	ALPHA_SCISSOR_THRESHOLD = threshold;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	ROUGHNESS = mix(roughness * orm.g, 0.2, hm_wetness * 0.7);
	AO = orm.r;
	BACKLIGHT = col * trans;
}
