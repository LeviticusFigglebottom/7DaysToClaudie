// Far-tree impostor: a quad per MultiMesh instance that turns about the vertical axis to face the
// camera and shows the atlas frame baked nearest the current view direction (two frames blended).
// Instances inside `discard_rect` (the near-chunk square, which renders real meshes) collapse.
// Atlas layout and frame convention: see src/world/vegetation/impostor_library.gd.
shader_type spatial;
render_mode skip_vertex_transform, cull_disabled, depth_draw_opaque;

uniform sampler2D atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D normal_atlas : hint_normal, filter_linear_mipmap, repeat_disable;
uniform bool has_normals = false;
uniform int frames = 8;
// World-space XZ rectangle (x0, z0, x1, z1) whose instances are hidden.
uniform vec4 discard_rect = vec4(0.0);
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.42;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.92;
// The atlas is baked in summer colours; these are the species' foliage tints (foliage.gdshader),
// so the far canopy follows the season by the ratio season / summer.
uniform vec4 spring_tint : source_color = vec4(1.0);
uniform vec4 summer_tint : source_color = vec4(1.0);
uniform vec4 autumn_tint : source_color = vec4(1.0);
uniform vec4 winter_tint : source_color = vec4(1.0);

global uniform vec4 hm_season;
global uniform float hm_snow;

varying flat float v_frame0;
varying flat float v_blend;
varying vec3 v_right;
varying vec3 v_up;
varying vec3 v_fwd;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	bool hidden = origin.x > discard_rect.x && origin.x < discard_rect.z
		&& origin.z > discard_rect.y && origin.z < discard_rect.w;
	vec3 cam = INV_VIEW_MATRIX[3].xyz;
	vec3 to_cam = cam - origin;
	to_cam.y = 0.0;
	to_cam = length(to_cam) > 0.001 ? normalize(to_cam) : vec3(0.0, 0.0, 1.0);
	vec3 up = vec3(0.0, 1.0, 0.0);
	vec3 right = normalize(cross(up, to_cam));
	float sx = length(MODEL_MATRIX[0].xyz);
	float sy = length(MODEL_MATRIX[1].xyz);
	vec3 world = origin + right * VERTEX.x * sx + up * VERTEX.y * sy;
	// Local view azimuth relative to the instance's yaw picks the frame.
	vec3 ax = MODEL_MATRIX[0].xyz / max(sx, 0.0001);
	vec3 az = MODEL_MATRIX[2].xyz / max(length(MODEL_MATRIX[2].xyz), 0.0001);
	float a = atan(dot(to_cam, ax), dot(to_cam, az));
	float f = a / (6.2831853 / float(frames));
	f = mod(f + float(frames), float(frames));
	v_frame0 = floor(f);
	v_blend = fract(f);
	v_right = (VIEW_MATRIX * vec4(right, 0.0)).xyz;
	v_up = (VIEW_MATRIX * vec4(up, 0.0)).xyz;
	v_fwd = (VIEW_MATRIX * vec4(to_cam, 0.0)).xyz;
	VERTEX = (VIEW_MATRIX * vec4(world, 1.0)).xyz;
	NORMAL = v_fwd;
	if (hidden) {
		// Behind the camera: the whole quad is clipped.
		VERTEX = vec3(0.0, 0.0, 10.0);
	}
}

vec4 frame_sample(sampler2D tex, float frame, vec2 uv) {
	float fr = mod(frame, float(frames));
	return texture(tex, vec2((fr + uv.x) / float(frames), uv.y));
}

void fragment() {
	vec2 uv = vec2(clamp(UV.x, 0.002, 0.998), UV.y);
	vec4 c0 = frame_sample(atlas, v_frame0, uv);
	vec4 c1 = frame_sample(atlas, v_frame0 + 1.0, uv);
	vec4 c = mix(c0, c1, v_blend);
	vec3 n_frame;
	if (has_normals) {
		vec3 n0 = frame_sample(normal_atlas, v_frame0, uv).xyz;
		vec3 n1 = frame_sample(normal_atlas, v_frame0 + 1.0, uv).xyz;
		n_frame = normalize(mix(n0, n1, v_blend) * 2.0 - 1.0);
	} else {
		// Fake a rounded crown: lean normals outward across the quad and slightly upward.
		float sx = (uv.x - 0.5) * 2.0;
		n_frame = normalize(vec3(sx * 0.8, 0.35, sqrt(max(0.0, 1.0 - sx * sx * 0.64))));
	}
	NORMAL = normalize(n_frame.x * v_right + n_frame.y * v_up + n_frame.z * v_fwd);
	vec3 albedo = c.rgb;
	vec4 season = hm_season.x * spring_tint + hm_season.y * summer_tint + hm_season.z * autumn_tint + hm_season.w * winter_tint;
	float wsum = max(0.001, hm_season.x + hm_season.y + hm_season.z + hm_season.w);
	albedo *= clamp(season.rgb / wsum / max(summer_tint.rgb, vec3(0.05)), vec3(0.0), vec3(2.5));
	// Snow on upward-facing parts of the canopy.
	float snow = clamp(hm_snow * (n_frame.y * 1.6 + 0.2), 0.0, 1.0);
	albedo = mix(albedo, vec3(0.86, 0.88, 0.9), snow * 0.8);
	ALBEDO = albedo;
	ROUGHNESS = roughness_value;
	SPECULAR = 0.2;
	BACKLIGHT = albedo * 0.35;
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
}
