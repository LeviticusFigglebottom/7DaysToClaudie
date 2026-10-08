// Near terrain: 8-layer splat (per-region palette into the global terrain texture arrays),
// height-based blending (layer height in albedo alpha), slope-driven triplanar rock, snow and
// wetness. Normals are blended in world space (whiteout), so the mesh needs no tangents.
// Layer order / tile sizes: game/data/materials/terrain_layers.json (TerrainTextures).
// Weather (ADR-0033, weather.gdshaderinc): rain soaks each layer by its porosity (litter and dirt
// darken most, asphalt least) and, once the ground is soaked, water stands in its hollows (the
// weather map's ground below its smoothed ground) and the layers' own dips, first on the layers that
// hold it (asphalt, mud), as dark mirrors that ring with the rain. Snow fills the dips first and
// covers the tops last. Nothing of it under a roof.
// Where the Bloom field holds the ground (ADR-0025) a white-grey mycelial web binds the litter: a
// generated thread mask revealed by coverage priority (cords first, then fans, then the cottony
// mat in the litter's hollows), over litter bleached by the rot; past a pixel or two the share of
// threads in the footprint instead (a pale veil, fading with distance); at night they glow faintly.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/bloom.gdshaderinc"
#include "res://assets/shaders/weather.gdshaderinc"

uniform sampler2DArray layer_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray layer_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float layer_tile[16];
uniform int rock_layer = 6;
uniform int snow_layer = 8;
uniform float rock_start = 0.80;
uniform float rock_end = 0.62;
uniform float normal_strength = 1.0;
// Far-field tiles discard inside the near square (x0, z0, x1, z1); disabled when x1 < x0.
uniform vec4 discard_rect = vec4(1.0, 1.0, -1.0, -1.0);

#include "res://assets/shaders/terrain_splat.gdshaderinc"

// The Bloom's web (BloomWorld.apply_web; textures/gen/bloom.py). Mask: R coverage priority
// (rank-equalised: a threshold t shows 1 - t of the ground at full growth), G age (fresh white ..
// old cream), B cottony mat, A thread body (opacity and glow).
uniform sampler2D bloom_web_mask : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bloom_web_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// The thread masks at a third, two thirds and all of full growth (RGB), binary: mipmapped, the share
// of threads in a footprint.
uniform sampler2D bloom_web_cov : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float bloom_web_tile = 1.6;
// Share of the tile the mask's threads cover (printed by the generator: keep in step). At full
// strength they all show; the cottony mat (B) fills in further.
uniform float bloom_web_cover = 0.33;
// Cream, not snow-white: a third of the ground in near-white threads brightened the dark litter
// 2-2.3x and, under the cold sky light, the colonised floor read as old snow.
uniform vec4 bloom_web_fresh : source_color = vec4(0.74, 0.72, 0.64, 1.0);
uniform vec4 bloom_web_aged : source_color = vec4(0.55, 0.5, 0.4, 1.0);
uniform float bloom_glow_energy = 0.035;

global uniform float hm_snow;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	if (discard_rect.z > discard_rect.x && v_world_pos.x > discard_rect.x && v_world_pos.x < discard_rect.z
			&& v_world_pos.z > discard_rect.y && v_world_pos.z < discard_rect.w) {
		discard;
	}
	vec3 gn = normalize(v_world_normal);
	// The region's splat through its palette, height-blended, with macro variation
	// (terrain_splat.gdshaderinc, shared with the volume terrain).
	vec3 alb;
	vec3 nrm;
	vec3 orm;
	float hgt;
	float pud_aff;
	float poro;
	terrain_splat(v_world_pos, gn, alb, nrm, orm, hgt, pud_aff, poro);

	// The Bloom: rot bleaches the litter, then the web binds it. Derivatives are taken here, outside
	// the (non-uniform) branch, where they are defined; the branch samples with textureGrad.
	float bloom_glow_m = 0.0;
	float field = hm_bloom_at(v_world_pos.xz);
	vec2 wuv = v_world_pos.xz / bloom_web_tile;
	vec2 wdx = dFdx(wuv);
	vec2 wdy = dFdy(wuv);
	if (field > 0.004) {
		float bf = hm_bloom_ragged(v_world_pos.xz, field);
		vec4 wm = textureGrad(bloom_web_mask, wuv, wdx, wdy);
		vec3 wcv = textureGrad(bloom_web_cov, wuv, wdx, wdy).rgb;
		// Coverage: a priority threshold near the camera (threads extend as the field rises); once a
		// texel is below a pixel, the share of threads in the footprint at this growth, from the
		// mipmapped binary masks (thresholding mipmapped priorities turns the web into blotches).
		vec2 wsize = vec2(textureSize(bloom_web_mask, 0));
		float lod = 0.5 * log2(max(max(dot(wdx * wsize, wdx * wsize), dot(wdy * wsize, wdy * wsize)), 1e-6));
		float mid_w = smoothstep(0.3, 1.3, lod);
		float t = 1.0 - bf * bloom_web_cover;
		float aa = 0.012 + 0.03 * max(lod, 0.0);
		float near_web = smoothstep(t - aa, t + aa, wm.r);
		float g = clamp(bf, 0.0, 1.0) * 3.0;
		float share = mix(mix(wcv.r * clamp(g, 0.0, 1.0), wcv.g, clamp(g - 1.0, 0.0, 1.0)), wcv.b, clamp(g - 2.0, 0.0, 1.0));
		float threads = mix(near_web, share, mid_w);
		// The threads are hair-thin: with distance they sink into the litter, a faint pale veil (the
		// floor 1.2-1.7x as bright as clean litter, not a sheet).
		float far_w = smoothstep(1.5, 4.5, lod);
		threads *= mix(1.0, 0.25, far_w);
		// The cottony mat, in the litter's hollows and only where the Bloom is strongest.
		float cotton = smoothstep(0.62, 1.0, bf) * wm.b * smoothstep(0.4, 0.8, 1.0 - hgt) * 0.55;
		// Rot drains some colour from what the web holds (no lighter, and only a quarter of the way to
		// grey: greyed litter turns the blue of snow in shade).
		float decay = smoothstep(0.06, 0.65, bf);
		float lum = dot(alb, vec3(0.299, 0.587, 0.114));
		alb = mix(alb, vec3(lum) * vec3(1.04, 1.0, 0.94), decay * 0.25);
		vec3 wc = mix(bloom_web_fresh.rgb, bloom_web_aged.rgb, wm.g);
		// Past a pixel per thread the web is a share of the footprint: kept thin, or a sunlit floor
		// turns into a cream sheet that reads as snow (TD-062).
		float body = mix(mix(0.5, 0.95, wm.a), 0.4, mid_w);
		float web = clamp(max(threads * body, cotton), 0.0, 1.0);
		alb = mix(alb, mix(wc, bloom_web_aged.rgb * 0.85, smoothstep(-0.05, 0.05, cotton - threads)), web);
		vec3 wn = whiteout_top(textureGrad(bloom_web_normal, wuv, wdx, wdy).rgb * 2.0 - 1.0, gn);
		nrm = normalize(mix(nrm, wn, threads * (1.0 - far_w) * 0.85));
		// Hyphae are matte; a glossier web caught the sky at grazing angles like frost.
		orm.g = mix(orm.g, 0.82, web);
		orm.r = mix(orm.r, 1.0, web * 0.25);
		bloom_glow_m = threads * body + cotton * 0.4;
	}

	// Slope rock (triplanar on X/Z projections + top).
	float rock_w = smoothstep(rock_start, rock_end, gn.y);
	if (rock_w > 0.001) {
		float t = max(layer_tile[rock_layer], 0.1);
		vec3 bw = pow(abs(gn), vec3(4.0));
		bw /= (bw.x + bw.y + bw.z);
		vec3 ax = texture(layer_albedo, vec3(vec2(v_world_pos.z, -v_world_pos.y) / t, float(rock_layer))).rgb;
		vec3 az = texture(layer_albedo, vec3(vec2(v_world_pos.x, -v_world_pos.y) / t, float(rock_layer))).rgb;
		vec3 ay = texture(layer_albedo, vec3(v_world_pos.xz / t, float(rock_layer))).rgb;
		vec3 ra = ax * bw.x + ay * bw.y + az * bw.z;
		vec3 nx = texture(layer_normal, vec3(vec2(v_world_pos.z, -v_world_pos.y) / t, float(rock_layer))).rgb * 2.0 - 1.0;
		vec3 nz = texture(layer_normal, vec3(vec2(v_world_pos.x, -v_world_pos.y) / t, float(rock_layer))).rgb * 2.0 - 1.0;
		vec3 wnx = normalize(vec3(abs(nx.z) * gn.x, nx.y + gn.y, nx.x * sign(gn.x) + gn.z));
		vec3 wnz = normalize(vec3(nz.x * sign(gn.z) + gn.x, nz.y + gn.y, abs(nz.z) * gn.z));
		vec3 wny = whiteout_top(texture(layer_normal, vec3(v_world_pos.xz / t, float(rock_layer))).rgb * 2.0 - 1.0, gn);
		vec3 rn = normalize(wnx * bw.x + wny * bw.y + wnz * bw.z);
		vec3 ro = texture(layer_orm, vec3(v_world_pos.xz / t, float(rock_layer))).rgb;
		alb = mix(alb, ra, rock_w);
		nrm = normalize(mix(nrm, rn, rock_w));
		orm = mix(orm, ro, rock_w);
	}

	// Snow settles on gentle slopes under the open sky: thin cover fills the dips of the ground's
	// relief first and lets the tops show through, broken by drifts; deep cover hides it all and
	// smooths the relief away.
	float expo = wx_exposed(v_world_pos, gn.y);
	float cover = hm_snow * smoothstep(0.62, 0.9, gn.y) * expo;
	float snow = 0.0;
	if (cover > 0.001) {
		float drift = wx_noise(v_world_pos.xz * 0.45) * 0.6 + wx_noise(v_world_pos.xz * 2.3 + 7.1) * 0.4;
		snow = smoothstep(0.0, 0.16, cover * 1.3 - (hgt - 0.45) * 0.45 * (1.0 - cover) - (drift - 0.5) * 0.4 * (1.0 - cover));
		vec2 suv2 = v_world_pos.xz / max(layer_tile[snow_layer], 0.1);
		alb = mix(alb, texture(layer_albedo, vec3(suv2, float(snow_layer))).rgb, snow);
		orm = mix(orm, texture(layer_orm, vec3(suv2, float(snow_layer))).rgb, snow);
		vec3 sn = whiteout_top(texture(layer_normal, vec3(suv2, float(snow_layer))).rgb * 2.0 - 1.0, gn);
		nrm = normalize(mix(nrm, sn, snow * 0.85));
		// Wind-packed drifts and scoured hollows: broad soft swells of brightness, so a covered field
		// reads as snow lying on ground rather than a white sheet.
		alb *= mix(1.0, 0.9 + 0.14 * drift, snow);
	}
	// Rain soaks each layer by its porosity (cliff rock as stone), drier on steep ground that sheds it.
	float flat_w = smoothstep(0.5, 0.95, gn.y);
	float porous = mix(poro, 0.5, rock_w);
	float wet = hm_wetness * mix(0.6, 1.0, flat_w) * expo * (1.0 - snow);
	alb = wx_wet_albedo(alb, wet, porous);
	orm.g = wx_wet_roughness(orm.g, wet, porous);
	// Standing water: a fill rank per point (deep in a hollow of the ground, low in the layer's own
	// relief, broken into separate pools by noise) against the water level on this layer.
	float level = hm_rain.y * expo * (1.0 - snow) * flat_w * mix(pud_aff, 0.3, rock_w);
	if (level > 0.005) {
		float hollow = wx_hollow(v_world_pos.xz);
		float pn = wx_noise(v_world_pos.xz * 0.37) * 0.65 + wx_noise(v_world_pos.xz * 1.7 + 4.1) * 0.35;
		float rank = clamp(0.6 * clamp(hollow / 0.14, 0.0, 1.0) + 0.45 * (1.0 - hgt) + 0.35 * (pn - 0.5) + 0.02, 0.0, 1.0);
		// Full standing water on asphalt pools about half of a flat road; lighter levels and
		// thirstier layers keep it to the hollows and the deepest dips. A flat road's ranks bunch
		// round 0.25, so the threshold falls fast at first (the hollows fill) and slowly at the end:
		// falling linearly, a road soaked for an hour (0.8) showed no pools at all.
		float t = 1.0 - 0.75 * sqrt(level);
		float puddle = smoothstep(t - 0.025, t + 0.025, rank);
		// The damp margin round a pool is darker still.
		float rim = smoothstep(t - 0.12, t, rank) * (1.0 - puddle);
		alb *= 1.0 - 0.18 * rim;
		orm.g = mix(orm.g, min(orm.g, 0.2), rim);
		if (puddle > 0.001) {
			// Water over the ground: what lies under it reads darker and browner, its top is a flat
			// mirror (the sky and every light in it) that rings where the rain lands.
			vec2 rip = wx_ripples(v_world_pos.xz, TIME, hm_rain.x);
			vec3 wn = normalize(vec3(-rip.x * 0.4, 1.0, -rip.y * 0.4));
			alb = mix(alb, alb * vec3(0.42, 0.4, 0.37), puddle);
			orm.g = mix(orm.g, 0.015, puddle);
			orm.r = mix(orm.r, 1.0, puddle);
			nrm = normalize(mix(nrm, wn, puddle));
		}
	}

	if (bloom_glow_m > 0.0) {
		// Nothing glows on cliff faces or under snow.
		EMISSION = hm_bloom_glow(bloom_glow_m * (1.0 - rock_w) * (1.0 - snow), v_world_pos.xz, TIME) * bloom_glow_energy;
	}
	ALBEDO = alb;
	// Standing water is a near mirror: the floor only stops a zero-roughness speckle.
	ROUGHNESS = clamp(orm.g, 0.012, 1.0);
	METALLIC = 0.0;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.2;
	NORMAL = normalize((VIEW_MATRIX * vec4(mix(gn, nrm, normal_strength), 0.0)).xyz);
}
