// Shared wind deformation for vegetation (trunks and foliage must use the same function so the
// crown and trunk move together). Inputs: hm_wind = (dir.x, dir.z, strength 0..1, gustiness 0..1).
global uniform vec4 hm_wind;

// Whole-plant sway: bends proportional to (height / sway_height)^2. Returns XZ offset.
vec2 hm_plant_sway(vec3 vertex, vec3 instance_origin, float sway_height, float stiffness, float t) {
	vec2 dir = normalize(hm_wind.xy + vec2(0.0001, 0.0));
	float phase = dot(instance_origin, vec3(0.071, 0.0, 0.113));
	float strength = hm_wind.z;
	float gust = 0.6 + 0.4 * sin(t * 0.21 + phase * 0.5) * hm_wind.w;
	float s = (sin(t * 0.63 + phase) * 0.65 + sin(t * 1.37 + phase * 1.9) * 0.35) * strength * gust;
	float h = max(vertex.y, 0.0) / max(sway_height, 0.01);
	return dir * (s + strength * 0.35) * h * h * (0.45 / max(stiffness, 0.05));
}

// Leaf/branch flutter along the normal, weighted by vertex alpha (0 = rigid, 1 = free).
vec3 hm_flutter(vec3 world_pos, vec3 normal, float weight, float t) {
	float f = sin(t * 7.3 + dot(world_pos, vec3(1.7, 2.3, 1.1))) * 0.6 + sin(t * 11.1 + dot(world_pos, vec3(2.9, 0.7, 3.3))) * 0.4;
	return normal * f * 0.035 * weight * (0.3 + hm_wind.z);
}
