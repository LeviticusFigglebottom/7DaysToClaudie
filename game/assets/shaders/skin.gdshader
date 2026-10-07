// Hollowmere character skin (ADR-0028): the Hollowed's dead skin, the player's arms, the eyes, the
// Bloom's fruiting caps and the Blister's pustules.
//  * Light under the skin (Godot's skin subsurface profile) and through thin parts (ears, fingers,
//    caps, pustules: transmittance and back light), only for the materials that use this shader.
//  * Dead skin: pallor and livid / sallow mottling patterned in rest space; bruised extremities and
//    settled blood (CUSTOM0.w); wet lips, mouth corners and eyelids (CUSTOM0.z); eyes wet all over.
//  * The Bloom: pale filaments under the skin around its sites (vertex B) and, as the infected tier
//    rises (bloom_glow), over the whole body, with a faint cold glow that the dark shows and the Hum
//    brightens. Growth materials (caps, mats) glow with the tier too.
//  * The Ashen's lichen-ash: ash dusted over everything, lichen paint inside painted shapes.
// Vertex data and instance uniforms: character.gdshaderinc.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx, sss_mode_skin;

#include "res://assets/shaders/character.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float uv_scale = 3.0;
uniform float normal_strength : hint_range(0.0, 3.0) = 1.0;
uniform float roughness_add = 0.0;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 1.0;
uniform float variation_strength = 0.06;

// Blood and grime soaked in where vertex G is high (std_surface's wear layer).
uniform sampler2D wear_albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wear_orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float wear_amount : hint_range(0.0, 1.0) = 0.0;
uniform float wear_uv_scale = 1.0;

// Light under and through the skin.
uniform float sss_strength : hint_range(0.0, 1.0) = 0.4;
uniform vec4 transmittance_color : source_color = vec4(0.62, 0.30, 0.22, 1.0);
uniform float transmittance_depth = 0.03;
uniform float transmittance_boost = 0.0;
// Thin translucent growths (caps, pustules): light from behind comes through, in this colour.
uniform float backlight : hint_range(0.0, 2.0) = 0.0;
uniform vec4 backlight_color : source_color = vec4(0.92, 0.88, 0.66, 1.0);

// Dead skin: pallor, and livid / sallow mottling a hand's width across (rest space).
uniform float pallor : hint_range(0.0, 1.0) = 0.0;
uniform vec4 pallor_color : source_color = vec4(0.66, 0.68, 0.64, 1.0);
uniform float mottle : hint_range(0.0, 1.0) = 0.0;
uniform float mottle_scale = 7.0;
uniform vec4 mottle_livid : source_color = vec4(0.46, 0.38, 0.47, 1.0);
uniform vec4 mottle_sallow : source_color = vec4(0.62, 0.56, 0.38, 1.0);
// Living skin flushed where blood runs close under it (knuckles, finger joints, fingertips): vertex
// B on a skin with no Bloom (the player's arms, bloom_skin 0). Off by default.
uniform float flush : hint_range(0.0, 1.0) = 0.0;
uniform vec4 flush_color : source_color = vec4(0.78, 0.40, 0.34, 1.0);
// Decay: broad patches (a forearm or a cheek across) gone dark, green-brown and slick, so a body
// reads as rotting rather than evenly pale from twenty metres (rest space: the patches ride the body).
uniform float rot : hint_range(0.0, 1.0) = 0.0;
uniform float rot_scale = 2.6;
uniform vec4 rot_color : source_color = vec4(0.36, 0.38, 0.24, 1.0);
// Bruised fingertips, toes, ears, knees and the blood settled in the lower legs (CUSTOM0.w).
uniform float bruise : hint_range(0.0, 1.0) = 0.0;
uniform vec4 bruise_color : source_color = vec4(0.27, 0.17, 0.26, 1.0);
// Wet lips, mouth corners, eyelids, wounds (CUSTOM0.z x wet_mask); eyes are wet all over (wet_base).
uniform float wet_base : hint_range(0.0, 1.0) = 0.0;
uniform float wet_mask : hint_range(0.0, 1.0) = 1.0;
uniform float wet_roughness = 0.14;
uniform float wet_clearcoat : hint_range(0.0, 1.0) = 0.0;
// The Ashen: lichen-ash dusted over everything, lichen paint inside the painted shapes.
uniform float ash : hint_range(0.0, 1.0) = 0.0;
uniform vec4 ash_color : source_color = vec4(0.70, 0.69, 0.66, 1.0);
uniform float paint : hint_range(0.0, 1.0) = 0.0;
uniform vec4 paint_color : source_color = vec4(0.30, 0.36, 0.27, 1.0);
// Living skin (the first-person arms; every one off by default, so other skins draw as before).
// Vertex A is the back of the hand and forearm (1) against the palm and inner forearm (0), and
// CUSTOM0.w how thin the flesh is (fingers 1): the arms have no bruising (bruise 0) to read it.
// Palms and inner forearms paler and less red.
uniform float palm_pale : hint_range(0.0, 1.0) = 0.0;
uniform vec4 palm_color : source_color = vec4(0.96, 0.84, 0.76, 1.0);
// Veins showing blue-grey through the back of the hand and wrist (not the fingers or the palm).
uniform float back_veins : hint_range(0.0, 1.0) = 0.0;
uniform float back_vein_scale = 30.0;
uniform vec4 back_vein_color : source_color = vec4(0.56, 0.62, 0.74, 1.0);
// Skin stretched over the knuckles and finger joints (vertex B on the back) is smoother: a sheen.
uniform float knuckle_sheen : hint_range(0.0, 1.0) = 0.0;
// Light through thin flesh (fingers, the web of the thumb) in transmittance_color, from behind
// and towards the eye (BACKLIGHT; drawn by light() in the viewmodel, by Godot's backlight
// elsewhere). Godot's own transmittance needs the screen-space subsurface pass the viewmodel can't
// use and a shadow the viewmodel doesn't cast.
uniform float translucency : hint_range(0.0, 2.0) = 0.0;
// How much the baked AO darkens direct light (the viewmodel casts no shadows on itself, so its
// fingers lean on their baked AO more), and the dielectric specular (0.5 = Godot's 4 %; skin ~2.8 %).
uniform float ao_light_affect : hint_range(0.0, 1.0) = 0.3;
uniform float skin_specular : hint_range(0.0, 1.0) = 0.5;
// Viewmodel lighting (light() below, compiled only into FpMaterials' copy, HM_VIEWMODEL). A
// held flame burns a hand's width from the fingers: past vm_light_knee (irradiance) a point
// light's falloff is compressed (an eye adapting to the flame) so the hand isn't one clipped orange.
uniform float vm_light_knee = 0.9;
uniform float vm_light_compress : hint_range(0.1, 1.0) = 0.55;
// Skin's wrapped diffuse: red light scatters furthest past the terminator.
uniform vec3 vm_wrap = vec3(0.20, 0.10, 0.07);
// A second, tighter specular lobe: the oily sheen over the knuckles and fingertips.
uniform float vm_sheen_lobe = 0.12;
// The Bloom under the skin: how much this material shows it (skin 1, cloth 0).
uniform float bloom_skin : hint_range(0.0, 1.0) = 0.0;
uniform float vein_scale = 11.0;
uniform vec4 vein_dark : source_color = vec4(0.42, 0.50, 0.44, 1.0);
uniform vec4 vein_pale : source_color = vec4(0.74, 0.84, 0.72, 1.0);
// Cold and pale, the family of the Hum's aurora (bloom.gdshaderinc HM_BLOOM_GLOW).
uniform vec4 glow_color : source_color = vec4(0.42, 0.86, 0.80, 1.0);
uniform float glow_energy = 0.15;
// Growths (caps, filament mats) glow on their own as the tier rises, brightest where pale.
uniform float growth_glow = 0.0;

void vertex() {
	v_rest = vec3(UV2, CUSTOM0.x);
	v_attr0 = CUSTOM0;
	v_attr1 = CUSTOM1;
	if (hm_gated_out(CUSTOM0.y, bloom_glow, hollow_burst)) {
		VERTEX = vec3(0.0);
	}
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 alb = texture(albedo_tex, uv).rgb * tint.rgb;
	vec3 nrm = texture(normal_tex, uv).rgb;
	vec3 orm = texture(orm_tex, uv).rgb;
	float rough = clamp(orm.g + roughness_add, 0.02, 1.0);
	vec3 rest = v_rest;
	alb *= 1.0 + (instance_variation - 0.5) * variation_strength * 2.0;
	float luma = dot(alb, vec3(0.3, 0.59, 0.11));

	if (pallor > 0.0) {
		alb = mix(alb, luma * pallor_color.rgb * 1.5, pallor);
	}
	if (mottle > 0.0) {
		vec3 mp = rest * mottle_scale;
		float m = hm_char_noise(mp) * 0.6 + hm_char_noise(mp * 2.3 + 7.1) * 0.4;
		alb = mix(alb, alb * mottle_livid.rgb * 2.1, smoothstep(0.55, 0.78, m) * mottle * 0.55);
		alb = mix(alb, alb * mottle_sallow.rgb * 1.7, smoothstep(0.44, 0.22, m) * mottle * 0.45);
	}
	if (flush > 0.0) {
		alb = mix(alb, alb * flush_color.rgb * 1.6, clamp(COLOR.b, 0.0, 1.0) * flush);
	}
	float dorsal = clamp(COLOR.a, 0.0, 1.0);
	float thin = clamp(v_attr0.w, 0.0, 1.0);
	if (palm_pale > 0.0) {
		float pl = (1.0 - dorsal) * palm_pale;
		alb = mix(alb, mix(alb, vec3(dot(alb, vec3(0.3, 0.59, 0.11))), 0.3) * palm_color.rgb * 1.22, pl);
	}
	if (back_veins > 0.0) {
		float vm = dorsal * (1.0 - smoothstep(0.45, 0.8, thin)) * back_veins;
		if (vm > 0.01) {
			float net = hm_bloom_net(rest, back_vein_scale, 0.0);
			alb = mix(alb, alb * back_vein_color.rgb * 1.3, net * vm);
		}
	}
	if (knuckle_sheen > 0.0) {
		rough = mix(rough, rough * 0.55, clamp(COLOR.b, 0.0, 1.0) * dorsal * knuckle_sheen);
	}
	if (rot > 0.0) {
		float rn = hm_char_noise(rest * rot_scale + 11.3) * 0.6 + hm_char_noise(rest * rot_scale * 3.7 + 4.1) * 0.4;
		float rm = smoothstep(0.46, 0.70, rn) * rot;
		alb = mix(alb, alb * rot_color.rgb * 1.7, rm);
		rough = mix(rough, rough * 0.75, rm * 0.6);
	}
	float br = clamp(v_attr0.w, 0.0, 1.0) * bruise;
	if (br > 0.0) {
		// Bruising breaks up into blotches rather than a smooth gradient.
		float bn = hm_char_noise(rest * 38.0 + 2.7);
		br *= smoothstep(0.15, 0.55, br + (bn - 0.5) * 0.5);
		alb = mix(alb, alb * bruise_color.rgb * 2.6, br);
	}

	// Blood and grime.
	float wear_level = instance_wear >= 0.0 ? instance_wear : wear_amount;
	if (wear_level > 0.001) {
		vec2 wuv = UV * wear_uv_scale;
		vec3 wa = texture(wear_albedo_tex, wuv).rgb;
		float threshold = 1.0 - wear_level * (0.6 + COLOR.g * 0.9);
		float wm = smoothstep(threshold - 0.08, threshold + 0.08, COLOR.g * 0.7 + dot(wa, vec3(0.333)) * 0.5);
		alb = mix(alb, wa, wm);
		nrm = mix(nrm, texture(wear_normal_tex, wuv).rgb, wm);
		rough = mix(rough, texture(wear_orm_tex, wuv).g, wm);
	}

	// The Ashen's lichen-ash.
	if (ash > 0.0) {
		float dust = ash * smoothstep(0.25, 0.75, hm_char_noise(rest * 9.0) * 0.6 + hm_char_noise(rest * 31.0 + 3.0) * 0.4 + 0.15);
		alb = mix(alb, ash_color.rgb * (0.85 + 0.3 * hm_char_noise(rest * 60.0)), dust * 0.85);
		rough = mix(rough, 0.92, dust);
	}
	if (paint > 0.0) {
		float ragged = (hm_char_noise(rest * 70.0) - 0.5) * 0.006;
		float pm = hm_sd_mask(v_attr1.z + ragged, 0.0008) * paint;
		alb = mix(alb, paint_color.rgb * (0.8 + 0.35 * hm_char_noise(rest * 120.0)), pm);
		rough = mix(rough, 0.95, pm);
	}

	// The Bloom under the skin. Near its sites (vertex B) a dark net of veins on every Hollowed;
	// as the tier rises it pales into filaments that spread in patches over the body and glow.
	float bg = clamp(bloom_glow, 0.0, 1.0);
	float glow = 0.0;
	if (bloom_skin > 0.0) {
		float spread = COLOR.b * 1.25 + bg * 0.55;
		float patch = hm_char_noise(rest * 2.2 + 3.3) * 0.7 + hm_char_noise(rest * 6.1 + 1.7) * 0.3;
		float show = smoothstep(0.45, 0.8, spread + (patch - 0.5) * 0.9) * bloom_skin;
		if (show > 0.01) {
			float net = hm_bloom_net(rest, vein_scale, clamp(COLOR.b + bg * 0.5, 0.0, 1.0)) * show;
			alb = mix(alb, alb * vein_dark.rgb * 1.5, net * (1.0 - bg) * 0.75);
			alb = mix(alb, mix(alb, vein_pale.rgb, 0.45), net * bg);
			rough = mix(rough, rough * 0.85, net * bg);
			glow = net * bg;
		}
	}
	if (growth_glow > 0.0) {
		glow = max(glow, growth_glow * bg * smoothstep(0.35, 0.75, dot(alb, vec3(0.333))));
	}

	// Wet mouths and eyes.
	float wet = clamp(wet_base + v_attr0.z * wet_mask, 0.0, 1.0);
	alb *= mix(1.0, 0.86, wet * (1.0 - wet_base));
	rough = mix(rough, wet_roughness, wet);

	hm_char_weather(alb, rough, 0.2, v_world_normal, weather_exposure);

	float vao = mix(1.0, COLOR.r, vertex_ao_strength);
	ALBEDO = clamp(alb, vec3(0.0), vec3(1.0));
	ROUGHNESS = rough;
	METALLIC = 0.0;
	AO = orm.r * vao;
	AO_LIGHT_AFFECT = ao_light_affect;
	SPECULAR = skin_specular;
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = normal_strength;
	SSS_STRENGTH = sss_strength;
	SSS_TRANSMITTANCE_COLOR = transmittance_color;
	SSS_TRANSMITTANCE_DEPTH = transmittance_depth;
	SSS_TRANSMITTANCE_BOOST = transmittance_boost;
	if (backlight > 0.0) {
		BACKLIGHT = backlight_color.rgb * ALBEDO * backlight;
	}
	if (translucency > 0.0) {
		// Squared: the fingers glow, the hand and wrist hardly.
		BACKLIGHT = transmittance_color.rgb * thin * thin * translucency;
	}
	if (wet_clearcoat > 0.0) {
		CLEARCOAT = wet * wet_clearcoat;
		CLEARCOAT_ROUGHNESS = 0.04;
	}
	if (glow > 0.0) {
		// Faint: it reads in the dark and vanishes in daylight; the Hum brightens it.
		EMISSION = glow_color.rgb * glow * glow_energy * (1.0 + 1.4 * hm_bloom);
	}
}

#ifdef HM_VIEWMODEL
// The first-person arms only (FpMaterials defines HM_VIEWMODEL in its copy of this shader; the
// Hollowed and the Ashen keep Godot's own lighting). The viewmodel casts no shadow, not even on
// itself, and a held flame burns a few centimetres from the fingers: Godot's lighting turned the
// hand one flat, clipped orange under the lighter.
void light() {
	float att = ATTENUATION;
	if (!LIGHT_IS_DIRECTIONAL) {
		// Irradiance past the knee is compressed (keeps the falloff across the hand, loses the clip).
		// Measured on the strongest channel: a warm flame clips red first, and a skin clipped in red
		// alone is the flat orange.
		float e = att * max(LIGHT_COLOR.r, max(LIGHT_COLOR.g, LIGHT_COLOR.b)) / PI;
		if (e > vm_light_knee) {
			att *= vm_light_knee * pow(e / vm_light_knee, vm_light_compress) / e;
		}
	}
	vec3 radiance = LIGHT_COLOR * att / PI;
	float ndl = dot(NORMAL, LIGHT);
	// Wrapped per channel, energy-normalised: a warm terminator rather than a hard plastic one.
	vec3 wrap = clamp((vec3(ndl) + vm_wrap) / (1.0 + vm_wrap), vec3(0.0), vec3(1.0)) / (1.0 + vm_wrap * 0.5);
	DIFFUSE_LIGHT += radiance * wrap;
	// Through thin flesh: from behind, brightest looking towards the light (a finger in front of
	// the flame glows red at its edges).
	float behind = clamp(0.5 - 0.5 * ndl, 0.0, 1.0);
	float toward = pow(clamp(dot(VIEW, -LIGHT), 0.0, 1.0), 3.0);
	DIFFUSE_LIGHT += radiance * BACKLIGHT * behind * (0.15 * behind + 0.85 * toward);
	if (ndl > 0.0) {
		float nv = clamp(dot(NORMAL, VIEW), 0.001, 1.0);
		vec3 h = normalize(LIGHT + VIEW);
		float nh = clamp(dot(NORMAL, h), 0.0, 1.0);
		float f0 = 0.16 * skin_specular * skin_specular;
		float F = f0 + (1.0 - f0) * pow(1.0 - clamp(dot(h, VIEW), 0.0, 1.0), 5.0);
		float spec = 0.0;
		for (int i = 0; i < 2; i++) {
			float r = i == 0 ? ROUGHNESS : ROUGHNESS * 0.55;
			float a = max(r * r, 0.002);
			float a2 = a * a;
			float dn = nh * nh * (a2 - 1.0) + 1.0;
			float D = a2 / (PI * dn * dn);
			float V = 0.5 / mix(2.0 * ndl * nv, ndl + nv, a);
			spec += D * V * (i == 0 ? 1.0 : vm_sheen_lobe);
		}
		SPECULAR_LIGHT += LIGHT_COLOR * att * F * spec * ndl * SPECULAR_AMOUNT;
	}
}
#endif
