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
instance uniform float instance_variation = 0.5;

global uniform float hm_wetness;
global uniform float hm_snow;

varying vec3 v_world_normal;
varying vec3 v_world_pos;

void vertex() {
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
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
	float wet = hm_wetness * mix(0.45, 1.0, up);
	alb *= mix(1.0, 0.6, wet);
	rough = mix(rough, 0.1, wet * 0.85);
	float snow = hm_snow * smoothstep(0.55, 0.85, up);
	alb = mix(alb, vec3(0.86, 0.88, 0.92), snow);
	rough = mix(rough, 0.7, snow);

	ALBEDO = clamp(alb, vec3(0.0), vec3(1.0));
	ROUGHNESS = rough;
	METALLIC = metal;
	AO = ao * vao;
	AO_LIGHT_AFFECT = 0.25;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
}
