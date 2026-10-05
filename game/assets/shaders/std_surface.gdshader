// Hollowmere master surface shader (props, rocks, buildings, structures).
// Tiling PBR set (albedo / normal / ORM) + layers driven by vertex colour channels from the
// asset pipeline: R = baked AO, G = wear/edge mask, B = moss/variation mask (see ASSET_PIPELINE.md).
// Global uniforms hm_* are driven by the weather system (wetness, snow).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float uv_scale = 1.0;
uniform float normal_strength : hint_range(0.0, 3.0) = 1.0;
uniform float roughness_mult = 1.0;
uniform float roughness_add = 0.0;
uniform float metallic_mult = 1.0;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 1.0;

// Wear layer (revealed on worn edges; e.g. bare wood under paint, rust under paint).
uniform sampler2D wear_albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float wear_amount : hint_range(0.0, 1.0) = 0.0;
uniform float wear_uv_scale = 1.0;
instance uniform float instance_wear = -1.0;

// Moss / lichen on up-facing surfaces (mask: vertex B * up-facing).
uniform sampler2D moss_albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float moss_amount : hint_range(0.0, 1.0) = 0.0;
uniform float moss_uv_scale = 1.0;

// Grime collects in occluded areas and near the ground.
uniform vec4 grime_color : source_color = vec4(0.16, 0.14, 0.11, 1.0);
uniform float grime_amount : hint_range(0.0, 1.0) = 0.0;
uniform float grime_height = 0.6;

uniform float variation_strength = 0.08;

// Self-lit surfaces (device screens, indicator LEDs): emission = colour x energy x albedo.
uniform vec4 emission_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy = 0.0;
instance uniform float instance_variation = 0.5;
// Infected tiers (Seeded/Bloomed Hollowed, InfectedTiers): pale Bloom filaments glowing under the
// skin, patterned in object space. The instance sets how far the Bloom has gone (bloom_glow); the
// material says where it can show (bloom_skin: Hollowed skin 1, fungal growths 0.8, cloth 0).
instance uniform float bloom_glow = 0.0;
uniform float bloom_skin : hint_range(0.0, 1.0) = 0.0;

global uniform float hm_wetness;
global uniform float hm_snow;
// 0 for things under a roof (POI furniture batched as indoor): no rain gloss or snow on them.
instance uniform float weather_exposure = 1.0;

varying vec3 v_world_normal;
varying vec3 v_world_pos;
varying vec3 v_obj_pos;

void vertex() {
	// Ground cover (moss, litter) shrinks away by distance; see foliage.gdshader.
	if (INSTANCE_CUSTOM.a < 0.0) {
		VERTEX *= 1.0 - smoothstep(-INSTANCE_CUSTOM.a * 0.8, -INSTANCE_CUSTOM.a, distance(MODEL_MATRIX[3].xyz, CAMERA_POSITION_WORLD));
	}
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_obj_pos = VERTEX;
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 alb = texture(albedo_tex, uv).rgb * tint.rgb;
	vec3 nrm = texture(normal_tex, uv).rgb;
	vec3 orm = texture(orm_tex, uv).rgb;
	float rough = clamp(orm.g * roughness_mult + roughness_add, 0.02, 1.0);
	float metal = orm.b * metallic_mult;
	float ao = orm.r;

	// Wear: crisp chipping where the edge mask beats a noise threshold taken from the wear texture.
	float wear_level = instance_wear >= 0.0 ? instance_wear : wear_amount;
	if (wear_level > 0.001) {
		vec2 wuv = UV * wear_uv_scale;
		vec3 wa = texture(wear_albedo_tex, wuv).rgb;
		float threshold = 1.0 - wear_level * (0.6 + COLOR.g * 0.9);
		float wm = smoothstep(threshold - 0.08, threshold + 0.08, COLOR.g * 0.7 + dot(wa, vec3(0.333)) * 0.5);
		alb = mix(alb, wa, wm);
		nrm = mix(nrm, texture(wear_normal_tex, wuv).rgb, wm);
		vec3 wo = texture(wear_orm_tex, wuv).rgb;
		rough = mix(rough, wo.g, wm);
		metal = mix(metal, wo.b, wm);
	}

	// Moss.
	float up = clamp(v_world_normal.y, 0.0, 1.0);
	if (moss_amount > 0.001) {
		vec2 muv = UV * moss_uv_scale;
		vec3 ma = texture(moss_albedo_tex, muv).rgb;
		float m = moss_amount * COLOR.b * smoothstep(0.25, 0.75, up) + (ma.g - 0.25) * 0.6 * moss_amount;
		m = smoothstep(0.35, 0.65, m);
		alb = mix(alb, ma, m);
		nrm = mix(nrm, texture(moss_normal_tex, muv).rgb, m);
		rough = mix(rough, texture(moss_orm_tex, muv).g, m);
		metal *= 1.0 - m;
	}

	// Grime.
	float vao = mix(1.0, COLOR.r, vertex_ao_strength);
	if (grime_amount > 0.001) {
		float g = grime_amount * clamp((1.0 - vao) * 1.5 + (1.0 - smoothstep(0.0, grime_height, v_world_pos.y - floor(v_world_pos.y / 100.0) * 100.0)) * 0.0, 0.0, 1.0);
		alb = mix(alb, grime_color.rgb, g);
		rough = mix(rough, 0.95, g);
	}

	alb *= 1.0 + (instance_variation - 0.5) * variation_strength * 2.0;

	// Weather: rain darkens and glosses surfaces facing the sky; snow settles on top.
	float wet = hm_wetness * weather_exposure * mix(0.45, 1.0, up);
	alb *= mix(1.0, 0.6, wet);
	rough = mix(rough, 0.1, wet * 0.85);
	float snow = hm_snow * weather_exposure * smoothstep(0.55, 0.85, up);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	rough = mix(rough, 0.7, snow);

	ALBEDO = clamp(alb, vec3(0.0), vec3(1.0));
	if (emission_energy > 0.0) {
		EMISSION = emission_color.rgb * emission_energy * clamp(alb, vec3(0.0), vec3(1.0));
	}
	float bg = bloom_glow * bloom_skin;
	if (bg > 0.001) {
		// Three warped sine sheets; a filament runs wherever one of them crosses zero (thin lines,
		// ~7 cm apart, 1-2 cm wide), anti-aliased so they don't shimmer at a distance.
		vec3 q = v_obj_pos * 16.0;
		float s1 = abs(sin(q.x + 1.7 * sin(q.y * 0.9 + q.z * 0.4)));
		float s2 = abs(sin(q.y * 0.8 + 1.9 * sin(q.z * 1.1 + q.x * 0.5)));
		float s3 = abs(sin(q.z + 1.6 * sin(q.x * 0.7 + q.y * 0.6)));
		float l = min(s1, min(s2, s3));
		float w = 0.03 + 0.06 * bg;
		float vein = 1.0 - smoothstep(w, w + fwidth(l) + 0.02, l);
		// Filaments gather in patches instead of netting the whole body evenly.
		vec3 c = v_obj_pos * 3.1;
		float patches = smoothstep(-0.3, 0.7, sin(c.x + 1.3 * sin(c.y)) * sin(c.y * 1.2 + 0.7) + 0.5 * sin(c.z * 1.4 + 2.0 * sin(c.x)));
		vein *= mix(0.2, 1.0, patches);
		ALBEDO = mix(ALBEDO, ALBEDO * vec3(0.9, 0.96, 0.88), bg * 0.4);
		ALBEDO = mix(ALBEDO, mix(ALBEDO, vec3(0.62, 0.76, 0.5), 0.4), vein * min(1.0, bg * 1.3));
		EMISSION += vec3(0.42, 0.75, 0.38) * vein * bg * 0.5;
	}
	ROUGHNESS = rough;
	METALLIC = metal;
	AO = ao * vao;
	AO_LIGHT_AFFECT = 0.25;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
}
