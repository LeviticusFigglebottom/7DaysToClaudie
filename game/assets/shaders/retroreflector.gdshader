// Retroreflective delineators (bridge guardrail posts, ADR-0023). A microprism sheet throws light
// back toward wherever it came from, so a reflector flares for whoever holds the torch and stays a
// dull plastic plate for everyone else: ordinary diffuse light plus a narrow lobe where the light
// arrives from close to the view direction. There is no deck lighting on the valley's bridges
// (no power), so at night these are what trace the edge of the deck in your light.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 tint : source_color = vec4(1.0, 0.68, 0.12, 1.0);
// Strength of the returned light and the lobe's width (cosine of its half-angle).
uniform float retro = 9.0;
uniform float retro_cos = 0.992;
uniform float roughness : hint_range(0.0, 1.0) = 0.45;
global uniform float hm_wetness;

void fragment() {
	// Grime and road film dull the sheet; rain beads on it and scatters the return a little.
	ALBEDO = tint.rgb * 0.5;
	ROUGHNESS = mix(roughness, 0.15, hm_wetness);
	METALLIC = 0.0;
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	DIFFUSE_LIGHT += ndl * ATTENUATION * LIGHT_COLOR / PI;
	float back = smoothstep(retro_cos, 1.0, dot(LIGHT, VIEW));
	SPECULAR_LIGHT += back * sqrt(ndl) * ATTENUATION * LIGHT_COLOR * tint.rgb * retro * (1.0 - 0.3 * hm_wetness);
}
