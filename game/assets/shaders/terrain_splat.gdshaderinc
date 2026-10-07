// The heightmap's ground colour, shared by terrain.gdshader and volume_terrain.gdshader (ADR-0056,
// CAVES_PLAN WS-D): a region's 8-layer splat through its palette into the global terrain layer
// arrays, height-blended (layer height in albedo alpha), with macro variation against tiling. The
// volume shader mixes it in where a converted column's mesh is the old ground surface, so a column
// that turns into volume (a dig, a cave) keeps the heightmap's look at the surface.
//
// The including shader declares the layer arrays first: layer_albedo, layer_normal, layer_orm
// (sampler2DArray) and layer_tile[16]. Region uniforms are set from TerrainManager's region
// material (_make_region_material; volume_material_for copies them).

uniform sampler2D splat0 : filter_linear, repeat_disable;
uniform sampler2D splat1 : filter_linear, repeat_disable;
uniform sampler2D macro_variation : hint_default_white, filter_linear_mipmap, repeat_enable;
// x0, z0, size, samples-1 (region rect and splat resolution)
uniform vec4 region_rect = vec4(0.0, 0.0, 1024.0, 1024.0);
uniform ivec4 palette0 = ivec4(0, 1, 2, 3);
uniform ivec4 palette1 = ivec4(4, 5, 9, 7);
uniform float height_blend_depth = 0.12;
uniform float macro_scale = 0.0035;
uniform float macro_strength = 0.35;

// Per layer slice (column = slice / 4): how readily water stands on it, how much darker it soaks.
global uniform mat4 hm_terrain_puddle;
global uniform mat4 hm_terrain_porosity;

vec3 whiteout_top(vec3 tn, vec3 gn) {
	// Tangent-space normal on the XZ plane (u = +X, v = +Z; OpenGL green up = -v).
	return normalize(vec3(tn.x + gn.x, abs(tn.z) * gn.y, -tn.y + gn.z));
}

// The splat's blend at world point `wp` with geometric normal `gn`: albedo (macro variation
// applied), world normal, ORM, layer height, puddle affinity and porosity.
void terrain_splat(vec3 wp, vec3 gn, out vec3 alb, out vec3 nrm, out vec3 orm, out float hgt, out float pud_aff, out float poro) {
	vec2 rel = (wp.xz - region_rect.xy) / region_rect.z;
	vec2 suv = (rel * region_rect.w + 0.5) / (region_rect.w + 1.0);
	vec4 w0 = texture(splat0, suv);
	vec4 w1 = texture(splat1, suv);
	float wts[8] = float[8](w0.r, w0.g, w0.b, w0.a, w1.r, w1.g, w1.b, w1.a);
	int ids[8] = int[8](palette0.x, palette0.y, palette0.z, palette0.w, palette1.x, palette1.y, palette1.z, palette1.w);

	// Height-blend: find max(height + weight) over active layers.
	float hb[8];
	vec4 albs[8];
	float best = -1.0;
	for (int i = 0; i < 8; i++) {
		hb[i] = -1.0;
		if (wts[i] > 0.003) {
			int L = ids[i];
			vec2 uv = wp.xz / max(layer_tile[L], 0.1);
			albs[i] = texture(layer_albedo, vec3(uv, float(L)));
			hb[i] = albs[i].a * 0.5 + wts[i];
			best = max(best, hb[i]);
		}
	}
	alb = vec3(0.0);
	nrm = vec3(0.0);
	orm = vec3(0.0);
	hgt = 0.0;
	float bsum = 0.0;
	pud_aff = 0.0;
	poro = 0.0;
	float cutoff = best - height_blend_depth;
	for (int i = 0; i < 8; i++) {
		if (hb[i] > cutoff) {
			float b = hb[i] - cutoff;
			int L = ids[i];
			vec2 uv = wp.xz / max(layer_tile[L], 0.1);
			alb += albs[i].rgb * b;
			hgt += albs[i].a * b;
			nrm += whiteout_top(texture(layer_normal, vec3(uv, float(L))).rgb * 2.0 - 1.0, gn) * b;
			orm += texture(layer_orm, vec3(uv, float(L))).rgb * b;
			pud_aff += hm_terrain_puddle[L / 4][L % 4] * b;
			poro += hm_terrain_porosity[L / 4][L % 4] * b;
			bsum += b;
		}
	}
	alb /= max(bsum, 1e-4);
	nrm = normalize(nrm);
	orm /= max(bsum, 1e-4);
	hgt /= max(bsum, 1e-4);
	pud_aff /= max(bsum, 1e-4);
	poro /= max(bsum, 1e-4);

	// Macro variation breaks up tiling at distance.
	float mv = texture(macro_variation, wp.xz * macro_scale).r;
	alb *= mix(1.0, 0.75 + mv * 0.5, macro_strength);
}
