shader_type spatial;
// Sleeper Sense overlay (material_overlay on a dormant Hollowed's body parts): a faint additive
// rim drawn through walls, so the perk reads a room before the door opens.
render_mode unshaded, blend_add, depth_test_disabled, depth_draw_never, cull_back, fog_disabled;

uniform vec4 tint : source_color = vec4(0.55, 0.85, 0.72, 1.0);
uniform float strength = 0.3;

void fragment() {
	float rim = 1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0);
	ALBEDO = tint.rgb * (0.12 + pow(rim, 2.2)) * strength;
}
