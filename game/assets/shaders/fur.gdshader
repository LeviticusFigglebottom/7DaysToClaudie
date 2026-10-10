shader_type spatial;
// Fur and feathers for the valley's wildlife (ADR-0027): deer, hare, songbirds, crows.
//
// The coat is painted by the generator in vertex colour (R = baked AO, G = the pale coat: belly,
// throat, rump patch, a bird's breast; B = the dark coat: nose, ear rims, tail top, a crow all
// over) and mixed between three tints per material; a neutral strand texture (UVs run with the
// lie of the hair: head to tail, down the legs, out along a wing) gives the hair its grain. Light
// catches the tips with a soft rim and the ears glow when backlit. Rain flattens and darkens the
// coat (global hm_wetness). The wet nose is the darkest point of the dark coat.
//
// Birds are MultiMesh instances that flap in the vertex stage: UV2.x is how far out along the
// wing a vertex lies (0 on the body, 1 at the tip), and each instance's INSTANCE_CUSTOM holds its
// flap phase (r, cycles), rate (g, Hz) and amplitude (b, 0 = gliding) — no skeleton per bird.

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 base_color : source_color = vec4(0.45, 0.34, 0.24, 1.0);
uniform vec4 pale_color : source_color = vec4(0.85, 0.82, 0.76, 1.0);
uniform vec4 dark_color : source_color = vec4(0.16, 0.13, 0.11, 1.0);
uniform float uv_scale = 8.0;
uniform float normal_strength : hint_range(0.0, 3.0) = 1.0;
uniform float grain : hint_range(0.0, 1.0) = 0.6;
uniform float roughness = 0.82;
uniform float vertex_ao_strength : hint_range(0.0, 1.0) = 1.0;
uniform float sheen : hint_range(0.0, 1.0) = 0.35;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.6;
uniform float backlight_amount : hint_range(0.0, 1.0) = 0.15;
uniform vec4 backlight_color : source_color = vec4(0.7, 0.32, 0.2, 1.0);
// Oil on a crow's feathers: a blue-violet sheen at grazing angles.
uniform vec4 iridescence : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float nose_roughness = 0.22;
uniform bool wing_flap = false;
// Shoulder line of the wings (object space, metres out from the midline) and the flap's reach.
uniform float shoulder_x = 0.02;
uniform float flap_degrees = 55.0;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
// Compatibility: a material uniform (GL caps the instance-uniform buffer at 4096 slots, which a
// streamed world overflows; TD-325). Per-instance values are ignored there.
uniform float instance_variation = 0.5;
#else
instance uniform float instance_variation : instance_index(1) = 0.5;
#endif
global uniform float hm_wetness;

varying float v_tip;

void vertex() {
	v_tip = 0.0;
	if (wing_flap) {
		float span = UV2.x;
		v_tip = span;
		float amp = INSTANCE_CUSTOM.b;
		if (span > 0.0 && amp > 0.0) {
			float ph = INSTANCE_CUSTOM.r * 6.2831853 + TIME * INSTANCE_CUSTOM.g * 6.2831853;
			// Downstroke faster than the upstroke; the outer wing lags and whips.
			float s = sin(ph) + 0.25 * sin(2.0 * ph);
			float a = radians(flap_degrees) * amp * (s * 0.8 + 0.2);
			float side = sign(VERTEX.x);
			float a_in = a;
			float a_out = a * (1.0 + 0.45 * span) + radians(12.0) * amp * cos(ph);
			float ang = mix(a_in, a_out, smoothstep(0.35, 1.0, span));
			vec2 pivot = vec2(side * shoulder_x, 0.0);
			vec2 p = VERTEX.xy - pivot;
			float c = cos(ang * side);
			float sn = sin(ang * side);
			VERTEX.xy = pivot + vec2(p.x * c - p.y * sn, p.x * sn + p.y * c);
			vec2 nn = NORMAL.xy;
			NORMAL.xy = vec2(nn.x * c - nn.y * sn, nn.x * sn + nn.y * c);
			// The wing sweeps forward on the downstroke.
			VERTEX.z += 0.25 * abs(p.x) * amp * cos(ph);
		}
	}
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 tex = texture(albedo_tex, uv).rgb;
	vec3 orm = texture(orm_tex, uv).rgb;
	float lum = dot(tex, vec3(0.333));
	vec3 coat = mix(base_color.rgb, pale_color.rgb, COLOR.g);
	coat = mix(coat, dark_color.rgb, COLOR.b);
	// a little coat-to-coat difference between animals
	coat *= 0.92 + 0.16 * instance_variation;
	// the strand texture is neutral grey around 0.5: it shades the coat, never recolours it
	vec3 alb = coat * mix(vec3(1.0), tex * 2.0, grain);
	float wet = clamp(hm_wetness, 0.0, 1.0);
	alb *= 1.0 - 0.3 * wet;
	float ao = mix(1.0, COLOR.r, vertex_ao_strength) * mix(1.0, orm.r, 0.6);
	float nose = smoothstep(0.93, 0.99, COLOR.b);
	float graze = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	alb += iridescence.rgb * pow(graze, 3.0) * 0.35;
	ALBEDO = alb;
	AO = ao;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = mix(mix(clamp(orm.g * roughness, 0.3, 1.0), 0.45, wet * 0.7), nose_roughness, nose);
	SPECULAR = mix(0.3, 0.55, nose);
	METALLIC = 0.0;
	NORMAL_MAP = texture(normal_tex, uv).rgb;
	NORMAL_MAP_DEPTH = normal_strength * (1.0 - 0.5 * wet);
	// soft rim on the hair tips, tinted by the coat; oil-slick sheen on dark feathers
	RIM = sheen * (1.0 - 0.6 * wet) * (0.6 + 0.4 * lum);
	RIM_TINT = sheen_tint;
	BACKLIGHT = backlight_color.rgb * backlight_amount;
}
