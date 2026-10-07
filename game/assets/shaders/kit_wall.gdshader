// POI kit walls and floors (docs/POI_KIT.md). One shader for every wall/floor piece of every
// building: each MultiMesh instance carries its finishes in INSTANCE_CUSTOM
//   r = finish slice for side A (UV2.x == 0: wall face toward +Z / floor top)
//   g = finish slice for side B (UV2.x == 1: wall face toward -Z / floor underside = ceiling)
//   b = the building's decay 0..1 (drives every wear layer below), a = per-instance random 0..1
//   plus a height code in its integer part (ADR-0021): per side (A + 16 x B), the storeys the piece
//   stands above its room's floor (0..3) + 4 x (the storeys that room is tall - 1), so a tall
//   room's stacked pieces share one baseboard, one band of floor grime and one ceiling
// Finishes are projected in world space (metre scale) so pieces tile seamlessly. Edges/reveals
// (UV2.x == 0.5) take side A's finish slightly darkened.
//
// Wear is composed here rather than baked into the finishes, so nothing repeats at their 1-2 m tile:
// the kit_decay masks hold uniform coverage priorities in world space (2.5 m tile, plus a coarser
// "zone" sample that makes some corners damp and others dry), and each layer reveals the area above
// a threshold set by decay and by the height in the room (local y: 0 at the floor, 2.8 under the
// ceiling). Water stains spread down from the ceiling with dark tide lines and drips, grime collects
// low, mould grows along floors and ceilings, paint and wallpaper peel to their substrate, ceiling
// plaster falls away from the lath, floors gather dust and scuffs. Interior walls get a baseboard.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;

uniform sampler2DArray finish_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray finish_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray finish_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Ceiling finishes come from the wall array when this is a floor material.
uniform sampler2DArray side_b_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
// The wall finishes' normal and ORM for a floor slab's underside (a ceiling), with side_b_albedo.
uniform sampler2DArray side_b_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray side_b_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool side_b_has_maps = false;
uniform bool side_b_from_other_array = false;
uniform bool has_finishes = false;
// Linear masks (tools/assetgen/textures/gen/kit.py): RGBA coverage priorities (grime, water stains +
// drips, mould, peel) and RGB detail (macro tone, substrate grain + cracks, scuff strokes).
uniform sampler2D decay_albedo : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform sampler2D decay_orm : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform bool has_decay = false;
uniform float texture_scale = 1.0;
uniform bool is_floor = false;
// Fallback palette (when finish arrays are not generated yet): index -> colour.
const vec3 PALETTE[18] = vec3[](
	vec3(0.78, 0.76, 0.71), vec3(0.62, 0.66, 0.58), vec3(0.55, 0.6, 0.66), vec3(0.7, 0.62, 0.5),
	vec3(0.52, 0.36, 0.3), vec3(0.45, 0.5, 0.42), vec3(0.8, 0.78, 0.68), vec3(0.4, 0.38, 0.36),
	vec3(0.48, 0.34, 0.22), vec3(0.36, 0.26, 0.18), vec3(0.6, 0.6, 0.58), vec3(0.3, 0.3, 0.3),
	vec3(0.66, 0.54, 0.4), vec3(0.42, 0.44, 0.47), vec3(0.72, 0.7, 0.62), vec3(0.5, 0.45, 0.4),
	vec3(0.24, 0.22, 0.2), vec3(0.62, 0.58, 0.5));

// Metres per tile of the decay masks (kit.py DECAY_TILE_M).
const float DECAY_TILE = 2.5;
const float BASEBOARD_H = 0.11;
// Wall finish slices (data/materials/kit_finishes.json): 0-1 plaster, 2-4 paint, 5-7 wallpaper,
// 8 wood panelling, 9-10 tile, 11-13 siding, 14 brick, 15 concrete block, 16-17 rock (drift,
// limestone: mine levels and caves, ADR-0044; they never peel and take no baseboard). Colours are linear.
// What peeling reveals: brown-coat plaster, white plaster under paint, backing paper and glue,
// tile backer, grey weathered wood under siding paint, bare block.
const vec3 WALL_SUBSTRATE[18] = vec3[](
	vec3(0.26, 0.2, 0.13), vec3(0.24, 0.2, 0.15),
	vec3(0.5, 0.46, 0.38), vec3(0.5, 0.46, 0.38), vec3(0.5, 0.46, 0.38),
	vec3(0.42, 0.35, 0.23), vec3(0.42, 0.35, 0.23), vec3(0.42, 0.35, 0.23),
	vec3(0.16, 0.1, 0.06), vec3(0.27, 0.25, 0.22), vec3(0.27, 0.25, 0.22),
	vec3(0.26, 0.24, 0.2), vec3(0.26, 0.24, 0.2), vec3(0.26, 0.24, 0.2),
	vec3(0.2, 0.1, 0.07), vec3(0.26, 0.25, 0.22),
	vec3(0.2, 0.19, 0.17), vec3(0.5, 0.47, 0.4));
// How readily each wall finish peels (0 = never).
const float WALL_PEEL[18] = float[](0.35, 0.3, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.15, 0.15, 0.9, 0.9, 0.9, 0.0, 0.3, 0.0, 0.0);
// Baseboard per wall finish (a = 0: none): painted trim on plaster and paint, stained wood under
// wallpaper and panelling, none on tile and exterior finishes.
const vec4 BASEBOARD[18] = vec4[](
	vec4(0.7, 0.66, 0.56, 1.0), vec4(0.62, 0.6, 0.54, 1.0),
	vec4(0.7, 0.66, 0.56, 1.0), vec4(0.7, 0.66, 0.56, 1.0), vec4(0.7, 0.66, 0.56, 1.0),
	vec4(0.11, 0.05, 0.022, 1.0), vec4(0.11, 0.05, 0.022, 1.0), vec4(0.11, 0.05, 0.022, 1.0),
	vec4(0.045, 0.022, 0.011, 1.0), vec4(0.0), vec4(0.0),
	vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0));
// Floor finish slices: 0-1 wood, 2-3 carpet, 4-5 linoleum, 6 tile, 7 concrete, 8-9 rock and cave
// mud (ADR-0044; nothing wears through). What wears through:
// bare grey wood under the varnish, jute backing, subfloor boards, mortar bed.
const vec3 FLOOR_SUBSTRATE[10] = vec3[](
	vec3(0.33, 0.25, 0.16), vec3(0.36, 0.27, 0.16), vec3(0.26, 0.2, 0.1), vec3(0.26, 0.2, 0.1),
	vec3(0.12, 0.08, 0.05), vec3(0.12, 0.08, 0.05), vec3(0.21, 0.19, 0.15), vec3(0.2, 0.19, 0.17),
	vec3(0.18, 0.16, 0.14), vec3(0.2, 0.15, 0.1));
const float FLOOR_PEEL[10] = float[](0.3, 0.35, 0.25, 0.4, 0.7, 0.8, 0.2, 0.0, 0.0, 0.0);

// Weather (ADR-0033): exterior faces take driven rain and darken by their porosity; floors open to
// the sky soak like the ground. hm_wetness comes with the include.
#include "res://assets/shaders/weather.gdshaderinc"
// 0 for pieces under a roof (PoiBuilder batches indoor floors separately): rain never reaches them.
// Same slot as std_surface's (furniture and fixtures share the indoor batches' instances).
instance uniform float weather_exposure : instance_index(3) = 1.0;

varying vec3 v_world;
varying vec3 v_wn;
varying flat vec4 v_custom;
varying float v_side;
varying float v_h;

void vertex() {
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_custom = INSTANCE_CUSTOM;
	v_side = UV2.x;
	// Kit pieces stand on their slab top (walls 0..2.8, slabs -0.2..0), so the local height is the
	// height in the room on every storey, wherever the building sits.
	v_h = VERTEX.y;
}

// World-space projection in metres: floors/ceilings on XZ, walls along their face with V down.
vec2 proj_metres() {
	vec3 n = abs(v_wn);
	if (n.y > 0.7) {
		return v_world.xz;
	} else if (n.x > n.z) {
		return vec2(v_world.z, -v_world.y);
	}
	return vec2(v_world.x, -v_world.y);
}

// 1 where a uniform priority lies above 1 - coverage, with a soft edge of `soft`.
float reveal(float priority, float coverage, float soft) {
	float t = 1.0 - coverage;
	return smoothstep(t, t + soft, priority);
}

void fragment() {
	bool side_b = v_side > 0.75;
	bool edge = v_side > 0.25 && v_side < 0.75;
	float slice = side_b ? v_custom.g : v_custom.r;
	vec2 m = proj_metres();
	vec2 uv = m * texture_scale;
	vec3 albedo;
	vec3 orm = vec3(1.0, 0.85, 0.0);
	vec3 nmap = vec3(0.5, 0.5, 1.0);
	if (has_finishes) {
		if (side_b && side_b_from_other_array) {
			// Wall finishes are authored at 1 m per tile; `uv` carries the floors' 2 m scale.
			albedo = texture(side_b_albedo, vec3(m, slice)).rgb;
			// Rock ceilings only (wall slices 16-17, not later ones such as log_chinked): other wall finishes' ORM and normal are authored for
			// walls, and on a ceiling they darkened wood and plaster (Haldane bunker render).
			if (side_b_has_maps && slice > 15.5 && slice < 17.5) {
				orm = texture(side_b_orm, vec3(m, slice)).rgb;
				nmap = texture(side_b_normal, vec3(m, slice)).rgb;
			}
		} else {
			albedo = texture(finish_albedo, vec3(uv, slice)).rgb;
			orm = texture(finish_orm, vec3(uv, slice)).rgb;
			nmap = texture(finish_normal, vec3(uv, slice)).rgb;
		}
	} else {
		albedo = PALETTE[int(clamp(round(slice), 0.0, 17.0))];
	}
	if (edge) {
		albedo *= 0.82;
	}
	// Vertex colour: R = AO, G = wear (exposed lath / chipped paint), B = variation.
	albedo *= mix(0.55, 1.0, COLOR.r);
	albedo = mix(albedo, albedo * vec3(0.78, 0.72, 0.64), COLOR.g * 0.8);
	float rough = orm.g;
	float ao = orm.r * COLOR.r;
	float decay = clamp(v_custom.b, 0.0, 1.0);

	bool ceiling = is_floor && side_b;
	bool floor_top = is_floor && !side_b;
	bool wall = !is_floor;
	int wi = int(clamp(round(slice), 0.0, 17.0));
	int fi = int(clamp(round(slice), 0.0, 9.0));
	bool exterior = wall && wi >= 11 && wi <= 15;
	if (has_decay) {
		// The two faces of a wall share a projection: offset side B so they don't mirror each other.
		vec2 dm = m / DECAY_TILE + (side_b ? vec2(0.37, 0.61) : vec2(0.0));
		vec4 mk = texture(decay_albedo, dm);
		// Room-scale zones (damp corner, dry wall): scale each layer's coverage 0.4..1.6, mean 1.
		vec4 zone = 0.4 + 1.2 * texture(decay_albedo, dm * 0.23 + vec2(0.13, 0.71));
		vec3 dt = texture(decay_orm, dm * 1.7).rgb;
		float macro = texture(decay_orm, dm * 0.19).r;
		// Height in the room and the room's height (tall rooms: ADR-0021 code in INSTANCE_CUSTOM.a).
		int hcode = int(floor(v_custom.a));
		int hside = side_b ? (hcode / 16) % 16 : hcode % 16;
		float hr = v_h + 3.0 * float(hside % 4);
		float room_h = 3.0 * float(hside / 4 + 1) - 0.2;
		float low = 1.0 - smoothstep(0.0, 0.9, hr);
		float high = smoothstep(room_h - 1.4, room_h, hr);
		float d2 = decay * decay;

		// Macro tone breaks the finish tiling; interiors yellow with age.
		albedo *= 0.9 + 0.2 * macro;
		bool rock = (floor_top && (fi == 8 || fi == 9)) || (!floor_top && (wi == 16 || wi == 17));
		if (!exterior && !rock) {
			albedo = mix(albedo, albedo * vec3(1.02, 0.95, 0.8), decay * 0.45 * smoothstep(0.3, 0.8, macro));
		}

		// Coverage of each layer for this surface.
		float peel_c;
		float stain_c;
		float mould_c;
		float grime_c;
		vec3 substrate;
		if (floor_top) {
			peel_c = d2 * 0.35 * FLOOR_PEEL[fi];
			stain_c = decay * 0.1;
			mould_c = (fi == 2 || fi == 3) ? d2 * 0.18 : d2 * 0.04;
			grime_c = decay * 0.45;
			substrate = FLOOR_SUBSTRATE[fi];
		} else if (ceiling) {
			peel_c = d2 * 0.3 * WALL_PEEL[wi];
			stain_c = decay * 0.22;
			mould_c = d2 * 0.05;
			grime_c = decay * 0.15;
			substrate = vec3(0.0);
		} else if (exterior) {
			peel_c = d2 * 0.22 * WALL_PEEL[wi];
			stain_c = decay * 0.12;
			mould_c = decay * (0.06 + 0.45 * low * low);
			grime_c = decay * (0.15 + 0.7 * low);
			substrate = WALL_SUBSTRATE[wi];
		} else {
			peel_c = d2 * 0.28 * WALL_PEEL[wi];
			// Leaks start under the ceiling; their drips carry the stain down the wall.
			stain_c = decay * (0.015 + 0.3 * high * high);
			mould_c = d2 * (0.03 + 0.25 * low * low + 0.15 * high * high) * ((wi == 9 || wi == 10) ? 1.8 : 1.0);
			grime_c = decay * (0.1 + 0.8 * low * low);
			substrate = WALL_SUBSTRATE[wi];
		}
		// Bare rock (wall and ceiling slices 16-17, floor 8-9: mine levels and caves, ADR-0044) has
		// no paint to stain: no leak blots or tide lines, which read as stained plaster on pale
		// limestone. Damp (mould) and dirt stay.
		if (rock) {
			peel_c = 0.0;
			stain_c = 0.0;
		}

		// Peeling: paint, paper, plaster or flooring gone in clusters, a shadow under the torn edge and
		// a lifted lip around it. A metre-scale clump mask gathers the coverage (x0.25..x1.75, mean
		// ~1) into damaged areas; spread evenly, the patches read as a speckle over every wall.
		float clump = texture(decay_orm, dm * 0.55 + vec2(0.31, 0.17)).r;
		float pc = peel_c * zone.a * (0.25 + 1.5 * smoothstep(0.3, 0.75, clump));
		if (pc > 0.0005) {
			float pp = mk.a;
			if (exterior && wi <= 13) {
				// Siding paint fails board by board: one priority per 10 cm board (kit.py _siding,
				// rows on world y), stretched along it, worst at the butt edge where water sits. So
				// the paint goes in strips that stop at the laps, not in blobs across them.
				float yb = -v_world.y / 0.1;
				float row = floor(yb);
				pp = texture(decay_albedo, vec2(dm.x * 0.35 + row * 0.173, row * 0.041) + vec2(0.29, 0.07)).a;
				pp += 0.06 * smoothstep(0.5, 1.0, fract(yb));
			} else if (exterior) {
				pp = texture(decay_albedo, vec2(dm.x * 0.35, dm.y * 1.6) + vec2(0.29, 0.07)).a;
			}
			float t = 1.0 - pc;
			float hole = smoothstep(t, t + 0.006, pp);
			float lip = hole * (1.0 - smoothstep(0.0, 0.025, pp - t));
			float rim = smoothstep(t - 0.025, t, pp) * (1.0 - hole);
			vec3 sub = substrate * (0.8 + 0.4 * dt.g);
			if (ceiling) {
				// Fallen ceiling plaster shows the wood lath and the dark gaps between the strips.
				float lath = smoothstep(0.25, 0.32, fract(m.x * 26.0)) * (1.0 - smoothstep(0.88, 0.95, fract(m.x * 26.0)));
				sub = mix(vec3(0.015, 0.012, 0.01), vec3(0.2, 0.14, 0.08) * (0.7 + 0.6 * dt.g), lath);
			}
			albedo = mix(albedo, sub, hole);
			albedo *= 1.0 - (exterior ? 0.15 : 0.35) * lip;
			albedo *= 1.0 + 0.15 * rim;
			rough = mix(rough, 0.95, hole);
			nmap = mix(nmap, vec3(0.5, 0.5, 1.0), hole * 0.8);
		}

		// Water stains: a tinted blot whose edge is a brown tide line, with fainter inner rings and
		// drips below (exterior walls: grey rain streaks). Part tint, part pigment, so dark paint takes
		// a brown cast instead of turning black.
		float sc = stain_c * zone.g;
		if (sc > 0.0005) {
			// Outside, rain draws the stains into long vertical streaks of dirt.
			float sp = exterior ? texture(decay_albedo, vec2(dm.x * 2.2, dm.y * 0.4) + vec2(0.51, 0.17)).g : mk.g;
			float d = sp - (1.0 - sc);
			float inside = smoothstep(0.0, 0.006, d);
			float tide = inside * (1.0 - smoothstep(0.004, 0.03, d));
			float rings = inside * pow(0.5 + 0.5 * cos(d * 6.2832 * 22.0), 8.0) * (1.0 - smoothstep(0.0, 0.25, d));
			vec3 tint = exterior ? vec3(0.8, 0.79, 0.76) : vec3(0.88, 0.76, 0.55);
			vec3 pigment = exterior ? vec3(0.05, 0.05, 0.045) : vec3(0.3, 0.22, 0.11);
			vec3 line = exterior ? vec3(0.06, 0.06, 0.055) : vec3(0.16, 0.1, 0.045);
			albedo = mix(albedo, mix(albedo * tint, pigment, exterior ? 0.3 : 0.22), inside * 0.8);
			albedo = mix(albedo, line, clamp(tide * 0.55 + rings * 0.2, 0.0, 1.0) * (exterior ? 0.3 : 1.0));
			ao *= 1.0 - 0.1 * tide;
		}

		// Mould colonies (green algae outside), densest at their cores.
		float mc = mould_c * zone.b;
		if (mc > 0.0005) {
			float t = 1.0 - mc;
			float mo = smoothstep(t, t + 0.05, mk.b);
			float core = smoothstep(t + 0.04, t + 0.12, mk.b);
			vec3 mcol = exterior ? vec3(0.05, 0.075, 0.03) : mix(vec3(0.03, 0.035, 0.02), vec3(0.012, 0.012, 0.008), core);
			albedo = mix(albedo, mcol * (0.7 + 0.6 * dt.g), mo * (exterior ? 0.65 : 0.85));
			rough = mix(rough, 0.97, mo);
		}

		// Baseboard: painted or stained trim with a rounded top that catches the light and a soft
		// shadow on the wall above it; kicked and scuffed.
		vec4 bb = BASEBOARD[wi];
		if (wall && !edge && bb.a > 0.5) {
			float aa = fwidth(hr) * 1.5;
			float board = 1.0 - smoothstep(BASEBOARD_H - aa, BASEBOARD_H + aa, hr);
			float bevel = smoothstep(BASEBOARD_H - 0.022, BASEBOARD_H - 0.006, hr) * board;
			float shade = (1.0 - smoothstep(BASEBOARD_H, BASEBOARD_H + 0.02, hr)) * (1.0 - board);
			vec3 bcol = bb.rgb * (0.92 + 0.16 * dt.g);
			bcol *= 1.0 - 0.35 * decay * dt.b;
			albedo = mix(albedo, bcol * (1.0 + 0.35 * bevel), board);
			albedo *= 1.0 - 0.35 * shade;
			rough = mix(rough, bb.r > 0.3 ? 0.42 : 0.55, board);
			nmap = mix(nmap, vec3(0.5, 0.5, 1.0), board);
			ao = mix(ao, 1.0, board);
		}

		// Grime: soft dirt, plus the gradients every abandoned room shows: kicked-up dirt along the
		// floor, soot and dust under the ceiling, a dark line where wall meets floor.
		float g = smoothstep(1.0 - grime_c * zone.r - 0.2, 1.0 - grime_c * zone.r + 0.15, mk.r) * step(0.0005, grime_c);
		albedo *= mix(vec3(1.0), exterior ? vec3(0.62, 0.6, 0.55) : vec3(0.6, 0.55, 0.47), g * 0.75);
		rough = mix(rough, min(1.0, rough + 0.1), g);
		if (wall && !exterior) {
			albedo *= 1.0 - decay * 0.3 * (1.0 - smoothstep(0.0, 0.3, hr));
			albedo *= 1.0 - (0.08 + 0.15 * decay) * smoothstep(room_h - 0.35, room_h, hr);
			ao *= 0.7 + 0.3 * smoothstep(0.0, 0.025, hr);
		}
		if (floor_top) {
			// Dust settles (lighter and flatter on dark floors), scuffed where people walked.
			albedo = mix(albedo, vec3(0.3, 0.28, 0.25), decay * 0.22 * (0.6 + 0.8 * mk.r));
			albedo *= 1.0 - 0.25 * decay * dt.b;
			rough = mix(rough, 0.9, decay * 0.5);
		}
	} else {
		albedo *= 1.0 - decay * 0.25;
	}
	float wet = 0.0;
	if (weather_exposure > 0.0 && hm_wetness > 0.0) {
		if (exterior) {
			wet = hm_wetness * (edge ? 0.6 : 0.85);
		} else if (floor_top) {
			wet = hm_wetness * wx_exposed(v_world, 1.0);
		}
		wet *= weather_exposure;
	}
	if (wet > 0.0) {
		float porosity = clamp((rough - 0.35) / 0.5, 0.0, 1.0) * (1.0 - orm.b);
		if (exterior && hm_rain.x > 0.02) {
			// Runs: while it rains, water sheets down an outside wall in thin rivulets that wander
			// and bead, wetter and glossier than the wall round them.
			float col = m.x * 7.0 + 0.35 * sin(m.y * 2.3 + floor(m.x * 7.0) * 1.7);
			float lane = floor(col);
			float on = step(0.55, wx_hash(vec2(lane, 3.7)));
			float line = 1.0 - smoothstep(0.0, 0.09, abs(fract(col) - 0.5));
			float bead = 0.6 + 0.4 * smoothstep(0.6, 1.0, fract(-m.y * 1.3 + TIME * (0.5 + wx_hash(vec2(lane, 9.1))) + wx_hash(vec2(lane, 1.3))));
			float run = line * on * bead * hm_rain.x;
			wet = min(1.0, wet + run);
			porosity *= 1.0 - run;
		}
		albedo = wx_wet_albedo(albedo, wet, porosity);
		rough = wx_wet_roughness(rough, wet, porosity);
	}
	ALBEDO = albedo;
	AO = ao;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = clamp(rough, 0.05, 1.0);
	METALLIC = orm.b;
	NORMAL_MAP = nmap;
	NORMAL_MAP_DEPTH = 0.8;
}
