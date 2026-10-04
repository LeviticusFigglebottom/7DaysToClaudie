// Blueprint ghost: pale, translucent, rim-lit outline of a structure still to be built.
// `fill` (0..1) shows delivered materials as a denser band rising from the base.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_never, blend_mix;

uniform vec4 tint : source_color = vec4(0.78, 0.86, 0.95, 0.32);
uniform float fill : hint_range(0.0, 1.0) = 0.0;
uniform float height = 2.0;
uniform float base_y = 0.0;

varying float v_local_y;

void vertex() {
	v_local_y = VERTEX.y;
}

void fragment() {
	float rim = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 2.2);
	float lines = smoothstep(0.92, 1.0, abs(sin((v_local_y - base_y) * 18.0 + TIME * 0.6)));
	float filled = step(v_local_y - base_y, fill * height);
	ALBEDO = tint.rgb * (0.7 + rim * 0.9) + vec3(lines * 0.08);
	ALPHA = clamp(tint.a * (0.45 + rim * 1.2) + lines * 0.05 + filled * 0.25, 0.0, 0.85);
}
