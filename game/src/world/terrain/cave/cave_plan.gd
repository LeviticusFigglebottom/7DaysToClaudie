class_name CavePlan
extends RefCounted
## One cave's shape (ADR-0056, docs/CAVES_PLAN.md): pure, deterministic and thread-safe.
##
## Built once from a spec, a seed and the *pristine* heights (never dug ones), then only read, so
## any number of worker threads may carve from it at once. The air is a union of primitives, each
## cut by a floor half-space so floors are flat and walkable:
##   * capsules along a Catmull-Rom spine that starts `outside` metres down the slope from the
##     mouth (so the tube breaks through the surface by itself), pitched into the hill with a
##     seeded yaw/pitch wander, their distance warped by a precomputed seeded 3D lattice;
##   * an optional end chamber and side pocket (ellipsoids).
## Density convention is VolumeTerrain's: positive = rock. `sdf` > 0 in rock, < 0 in cave air, and
## the terrain is `min(h - y, sdf(p))` clamped to ±CLAMP, so carving is a min() and the order caves
## are registered in does not matter.

const GEN_VERSION: int = 1
## VolumeTerrain.CLAMP: densities are clamped to ±2, so a cave further than 2 m changes nothing.
const CLAMP: float = 2.0
## VolumeTerrain.SIZE: the 16 m chunk / column size `columns()` reports in.
const CHUNK: float = 16.0
## Bound on |grad| of a primitive's unwarped distance (radius and floor vary along a capsule;
## ellipsoids keep their axis ratio under 1.5). Used for the sub-block skip/fill tests.
const LIP: float = 1.5
## carve_block works in sub-blocks of SUB³ samples: wholly-rock ones are skipped, wholly-air ones
## filled, and only the shell is sampled with the few primitives near it.
const SUB: int = 5
const WARP_N: int = 16
const WARP_MASK: int = 15

## Defaults mirror data/config/caves.json, so the planner works without config (tests, tools).
const DEFAULTS: Dictionary = {
	"min_cover": 2.0, "min_clear": 2.2, "min_mouth_r": 1.4, "min_slope_deg": 18.0, "search": 12.0,
	"region_margin": 32.0, "outside": 1.5, "step": 1.0, "pitch_deg": [-12.0, -4.0], "pitch_limit_deg": -20.0,
	"yaw_wander_deg": 22.0, "pitch_wander_deg": 3.0, "apron": 3.0, "daylight_falloff": 6.0,
	"warp": {"cell": 2.0, "amp": 0.45},
	"styles": {
		"shelter": {"length": [6.0, 10.0], "radius": [2.5, 3.5], "taper": 0.95, "points": [3, 4], "floor_drop": 0.25,
			"portal": 0.9, "min_slope_deg": 30.0, "chamber": [], "pocket_chance": 0.0},
		"grotto": {"length": [12.0, 30.0], "radius": [1.9, 2.6], "taper": 1.0, "points": [4, 6], "floor_drop": 0.5,
			"portal": 0.35, "portal_min": 10.0, "chamber": [5.0, 9.0], "chamber_height": [3.2, 4.5], "pocket_chance": 0.5, "pocket_radius": [1.6, 2.2]},
	},
}

var id: StringName
var region_id: String = ""
var style: StringName = &""
var seed: int = 0
var ok: bool = false
var reason: String = ""
## Origin on the opening's floor, -Z into the hill.
var mouth := Transform3D()
## Centre line sampled every ~`step` m, from `outside` m down the slope to the tunnel's end.
var spine := PackedVector3Array()
var radii := PackedFloat32Array()
var floor_y := PackedFloat32Array()
## Bounds of the cave air (what the cave can open).
var aabb := AABB()

# --- Shape (read-only after build) ---
var _heading: float = 0.0
var _length: float = 0.0
var _pitch: float = 0.0
var _arc := PackedFloat32Array()
var _mouth_i: int = 0
var _mouth_arc: float = 0.0
var _cover_fail_arc: float = 0.0
var _cover_fail_kind: StringName = &""
var _portal: float = 0.0
var _amp: float = 0.0
var _inv_cell: float = 0.5
var _warp := PackedFloat32Array()
# Capsules: start, end - start, 1 / |end - start|², start radius, radius change, start floor,
# floor change, warp amplitude, and bounds grown by CLAMP.
var _ca := PackedVector3Array()
var _cba := PackedVector3Array()
var _cinv := PackedFloat32Array()
var _cr0 := PackedFloat32Array()
var _cdr := PackedFloat32Array()
var _cf0 := PackedFloat32Array()
var _cdf := PackedFloat32Array()
var _cw := PackedFloat32Array()
var _cbox: Array[AABB] = []
# Ellipsoids (chamber, pocket): centre, radii, yaw cos/sin, floor, warp amplitude, grown bounds.
var _ec := PackedVector3Array()
var _er := PackedVector3Array()
var _ecos := PackedFloat32Array()
var _esin := PackedFloat32Array()
var _ef := PackedFloat32Array()
var _ew := PackedFloat32Array()
var _ekind: Array[StringName] = []
var _ebox: Array[AABB] = []
var _carve_aabb := AABB()
var _apron_a := Vector2.ZERO
var _apron_b := Vector2.ZERO
var _apron_r: float = 0.0
var _anchors: Array[Dictionary] = []
var _probes: Array = []


# --- Building -------------------------------------------------------------------------------

## Plans a cave. spec: {id, style, mouth: [x, z], heading: "uphill" | yaw degrees, search?,
## length?: [a, b] | m, region_id?, region_rect?: Rect2 | [x, z, w, d]}. The mouth settles on a
## slope (CaveSites.settle_mouth) within `search` m. heading yaw follows Basis(Vector3.UP, yaw):
## into the hill is (-sin yaw, 0, -cos yaw). Always returns a plan; check `ok` / `reason`.
static func build(spec: Dictionary, p_seed: int, height_fn: Callable, cfg: Dictionary) -> CavePlan:
	var plan := CavePlan.new()
	plan.id = StringName(str(spec.get("id", "cave")))
	plan.region_id = str(spec.get("region_id", ""))
	plan.style = StringName(str(spec.get("style", "grotto")))
	plan.seed = p_seed
	plan._build(spec, height_fn, cfg)
	return plan


static func _cfg(cfg: Dictionary, key: String) -> Variant:
	return cfg.get(key, DEFAULTS.get(key))


static func _range(v: Variant, rng: RandomNumberGenerator) -> float:
	if v is Array and (v as Array).size() >= 2:
		return rng.randf_range(float(v[0]), float(v[1]))
	if v is float or v is int:
		return float(v)
	return rng.randf()


func _fail(why: String) -> void:
	ok = false
	reason = why


func _build(spec: Dictionary, height_fn: Callable, cfg: Dictionary) -> void:
	var styles: Dictionary = _cfg(cfg, "styles")
	if not styles.has(String(style)) or String(style).begins_with("_"):
		_fail("unknown style '%s'" % style)
		return
	var st: Dictionary = styles[String(style)]
	var m: Variant = spec.get("mouth")
	if not (m is Array and (m as Array).size() >= 2):
		_fail("no mouth [x, z]")
		return
	var hint: float = NAN
	var hv: Variant = spec.get("heading", "uphill")
	if hv is float or hv is int:
		hint = deg_to_rad(float(hv))
	# A style may ask for a steeper face (a shelter is a short overhang: only a steep slope covers it).
	var min_slope: float = maxf(float(_cfg(cfg, "min_slope_deg")), float(st.get("min_slope_deg", 0.0)))
	var settled: Dictionary = CaveSites.settle_mouth(height_fn, Vector2(float(m[0]), float(m[1])),
		hint, float(spec.get("search", _cfg(cfg, "search"))), {"min_slope_deg": min_slope})
	if settled.is_empty():
		_fail("no slope >= %.0f deg within %.0f m of the mouth" % [min_slope, float(spec.get("search", _cfg(cfg, "search")))])
		return
	_heading = deg_to_rad(float(settled["heading_deg"]))
	var mpos: Vector3 = settled["pos"]

	# Every random number is drawn here, in a fixed order, so a retry (deeper pitch, shorter
	# tunnel) reshapes the same cave instead of rolling a new one.
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var lv: Variant = spec.get("length", st.get("length", [8.0, 12.0]))
	_length = _range(lv, rng)
	var r0: float = _range(st.get("radius", [2.0, 2.5]), rng)
	var pts_r: Array = st.get("points", [4, 5])
	var npts: int = clampi(rng.randi_range(int(pts_r[0]), int(pts_r[1])), 2, 8)
	_pitch = deg_to_rad(_range(_cfg(cfg, "pitch_deg"), rng))
	var yaw_w: float = deg_to_rad(float(_cfg(cfg, "yaw_wander_deg")))
	var pitch_w: float = deg_to_rad(float(_cfg(cfg, "pitch_wander_deg")))
	var yaw_off := PackedFloat32Array()
	var pitch_off := PackedFloat32Array()
	var r_jit := PackedFloat32Array()
	for i: int in 8:
		yaw_off.append(rng.randf_range(-yaw_w, yaw_w))
		pitch_off.append(rng.randf_range(-pitch_w, pitch_w))
		r_jit.append(rng.randf_range(0.92, 1.08))
	var cham: Array = st.get("chamber", [])
	var has_chamber: bool = cham.size() >= 2
	var cham_d: float = _range(cham, rng) if has_chamber else 0.0
	var cham_stretch: float = rng.randf_range(0.85, 1.15)
	var cham_h: float = _range(st.get("chamber_height", [3.2, 4.5]), rng)
	var has_pocket: bool = rng.randf() < float(st.get("pocket_chance", 0.0))
	var pocket_side: float = -1.0 if rng.randf() < 0.5 else 1.0
	var pocket_at: float = rng.randf_range(0.45, 0.7)
	var pocket_r: float = _range(st.get("pocket_radius", [1.6, 2.2]), rng)
	var wcfg: Dictionary = _cfg(cfg, "warp")
	_amp = float(wcfg.get("amp", 0.45))
	_inv_cell = 1.0 / maxf(0.25, float(wcfg.get("cell", 2.0)))
	_warp.resize(WARP_N * WARP_N * WARP_N)
	for i: int in _warp.size():
		_warp[i] = rng.randf_range(-1.0, 1.0)

	var drop: float = float(st.get("floor_drop", 0.5))
	var taper: float = float(st.get("taper", 1.0))
	var outside: float = float(_cfg(cfg, "outside"))
	var step: float = maxf(0.25, float(_cfg(cfg, "step")))
	var min_cover: float = float(_cfg(cfg, "min_cover"))
	# The portal (metres past the mouth) is where the hood over a slope is still thinner than
	# min_cover: on an 18° face a 3 m tall tunnel needs ~10 m to get 2 m of ground over it. It is
	# fixed from the first length, so shortening never shrinks it.
	var portal: float = maxf(float(st.get("portal", 0.4)) * _length, float(st.get("portal_min", 0.0)))
	var pitch_limit: float = deg_to_rad(float(_cfg(cfg, "pitch_limit_deg")))
	var min_len: float = maxf(_length * 0.5, minf(_length, portal + 2.0))
	_portal = portal
	var cover_note: String = ""
	for attempt: int in 24:
		_shape(mpos, outside, npts, yaw_off, pitch_off, r_jit, r0, taper, drop, step, yaw_w)
		_clear_prims()
		_add_capsules()
		if has_chamber:
			_add_chamber(cham_d, cham_stretch, cham_h)
		if has_pocket:
			_add_pocket(pocket_side, pocket_at, pocket_r)
		_cover_fail_kind = &""
		cover_note = _cover_problem(height_fn, min_cover, portal)
		if cover_note == "":
			break
		if _cover_fail_kind == &"pocket":
			# The pocket is optional: a hill too thin for it just loses it.
			has_pocket = false
			continue
		# Deepen the pitch first, then shorten the tunnel (which only helps when the far end is
		# what breaks out of the hill).
		if _pitch > pitch_limit + 0.001:
			_pitch = maxf(pitch_limit, _pitch - deg_to_rad(2.0))
		elif _cover_fail_arc > portal + 0.5 * (_length - portal) and _length * 0.85 >= min_len:
			_length *= 0.85
		else:
			break
	_finish_bounds(float(_cfg(cfg, "apron")))
	if cover_note != "":
		_fail(cover_note)
		return
	var clear_note: String = _clearance_problem(float(_cfg(cfg, "min_clear")))
	if clear_note != "":
		_fail(clear_note)
		return
	var mouth_note: String = _mouth_problem(float(_cfg(cfg, "min_mouth_r")))
	if mouth_note != "":
		_fail(mouth_note)
		return
	var rr: Variant = spec.get("region_rect")
	if rr is Array and (rr as Array).size() >= 4:
		rr = Rect2(float(rr[0]), float(rr[1]), float(rr[2]), float(rr[3]))
	if rr is Rect2:
		var inner: Rect2 = (rr as Rect2).grow(-float(_cfg(cfg, "region_margin")))
		if not inner.encloses(footprint()):
			_fail("closer than %.0f m to the region border" % float(_cfg(cfg, "region_margin")))
			return
	ok = true
	reason = ""
	_make_anchors()
	_make_probes(height_fn, float(_cfg(cfg, "daylight_falloff")))


## Lays the spine: control points from `outside` m down the slope, pitched into the hill with a
## cumulative yaw wander, through a Catmull-Rom spline sampled every `step` m.
func _shape(mpos: Vector3, outside: float, npts: int, yaw_off: PackedFloat32Array, pitch_off: PackedFloat32Array,
		r_jit: PackedFloat32Array, r0: float, taper: float, drop: float, step: float, yaw_w: float) -> void:
	var dir0 := Vector3(-sin(_heading), 0.0, -cos(_heading))
	var ctrl := PackedVector3Array()
	var cr := PackedFloat32Array()
	ctrl.append(mpos - dir0 * outside + Vector3.UP * (r0 * drop))
	cr.append(r0 * r_jit[0])
	var seg: float = (_length + outside) / float(npts - 1)
	var yaw: float = _heading
	for i: int in range(1, npts):
		# The first leg stays nearly straight and shallow so the opening is clean.
		var first: bool = i == 1
		yaw = clampf(yaw + yaw_off[i] * (0.3 if first else 1.0), _heading - yaw_w * 1.5, _heading + yaw_w * 1.5)
		var pitch: float = _pitch * (0.5 if first else 1.0) + pitch_off[i] * (0.0 if first else 1.0)
		var d := Vector3(-sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
		ctrl.append(ctrl[i - 1] + d * seg)
		cr.append(r0 * lerpf(1.0, taper, float(i) / float(npts - 1)) * r_jit[i])
	spine = PackedVector3Array()
	radii = PackedFloat32Array()
	floor_y = PackedFloat32Array()
	_arc = PackedFloat32Array()
	var m: int = ctrl.size()
	for i: int in m - 1:
		var p0: Vector3 = ctrl[i - 1] if i > 0 else ctrl[0] * 2.0 - ctrl[1]
		var p1: Vector3 = ctrl[i]
		var p2: Vector3 = ctrl[i + 1]
		var p3: Vector3 = ctrl[i + 2] if i + 2 < m else ctrl[m - 1] * 2.0 - ctrl[m - 2]
		var sub: int = maxi(1, int(ceil(p1.distance_to(p2) / step)))
		for s: int in sub:
			var t: float = float(s) / float(sub)
			_push_spine(_catmull(p0, p1, p2, p3, t), lerpf(cr[i], cr[i + 1], t), drop)
	_push_spine(ctrl[m - 1], cr[m - 1], drop)
	# The mouth is where the spine passes the settled point (horizontally).
	_mouth_i = 0
	for i: int in spine.size():
		if (spine[i] - spine[0]).dot(dir0) >= outside:
			_mouth_i = i
			break
	_mouth_arc = _arc[_mouth_i]
	mouth = Transform3D(Basis(Vector3.UP, _heading), Vector3(mpos.x, floor_y[_mouth_i], mpos.z))


func _push_spine(p: Vector3, r: float, drop: float) -> void:
	_arc.append(0.0 if spine.is_empty() else _arc[_arc.size() - 1] + p.distance_to(spine[spine.size() - 1]))
	spine.append(p)
	radii.append(r)
	floor_y.append(p.y - r * drop)


static func _catmull(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, t: float) -> Vector3:
	var t2: float = t * t
	return 0.5 * (p1 * 2.0 + (p2 - p0) * t + (p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3) * t2 + (p1 * 3.0 - p0 - p2 * 3.0 + p3) * t2 * t)


func _clear_prims() -> void:
	_ca = PackedVector3Array()
	_cba = PackedVector3Array()
	_cinv = PackedFloat32Array()
	_cr0 = PackedFloat32Array()
	_cdr = PackedFloat32Array()
	_cf0 = PackedFloat32Array()
	_cdf = PackedFloat32Array()
	_cw = PackedFloat32Array()
	_cbox = []
	_ec = PackedVector3Array()
	_er = PackedVector3Array()
	_ecos = PackedFloat32Array()
	_esin = PackedFloat32Array()
	_ef = PackedFloat32Array()
	_ew = PackedFloat32Array()
	_ekind = []
	_ebox = []


## One capsule per ~2 spine samples: the spline's curvature is gentle, so 2 m pieces follow it and
## halve the carving work against 1 m ones.
func _add_capsules() -> void:
	var last: int = spine.size() - 1
	var i: int = 0
	while i < last:
		var j: int = mini(i + 2, last)
		var a: Vector3 = spine[i]
		var ba: Vector3 = spine[j] - a
		_ca.append(a)
		_cba.append(ba)
		_cinv.append(1.0 / maxf(ba.length_squared(), 1e-6))
		_cr0.append(radii[i])
		_cdr.append(radii[j] - radii[i])
		_cf0.append(floor_y[i])
		_cdf.append(floor_y[j] - floor_y[i])
		# No warp at the opening (a clean, wide-enough mouth), full warp 3 m in.
		var w: float = _amp * smoothstep(0.0, 3.0, _arc[i] - _mouth_arc)
		_cw.append(w)
		var r: float = maxf(radii[i], radii[j]) + w
		var box := AABB(a, Vector3.ZERO).expand(spine[j]).grow(r)
		var fl: float = minf(floor_y[i], floor_y[j])
		box = AABB(Vector3(box.position.x, fl, box.position.z), Vector3(box.size.x, box.end.y - fl, box.size.z))
		_cbox.append(box)
		i = j


func _end_yaw() -> float:
	var n: int = spine.size()
	var d: Vector3 = spine[n - 1] - spine[maxi(0, n - 3)]
	return atan2(-d.x, -d.z) if Vector2(d.x, d.z).length() > 0.01 else _heading


func _add_ellipsoid(c: Vector3, r: Vector3, yaw: float, fl: float, kind: StringName) -> void:
	_ec.append(c)
	_er.append(r)
	_ecos.append(cos(yaw))
	_esin.append(sin(yaw))
	_ef.append(fl)
	_ew.append(_amp)
	_ekind.append(kind)
	var hr: float = maxf(r.x, r.z) + _amp + 0.5
	_ebox.append(AABB(Vector3(c.x - hr, fl, c.z - hr), Vector3(hr * 2.0, c.y + r.y + _amp + 0.5 - fl, hr * 2.0)))


func _add_chamber(diameter: float, stretch: float, height: float) -> void:
	var n: int = spine.size()
	var e: Vector3 = spine[n - 1]
	var yaw: float = _end_yaw()
	var rx: float = diameter * 0.5
	var rz: float = rx * stretch
	# Centre 0.4 ry over the floor, so the floor cut is 1.83 rx wide and the dome `height` tall.
	var ry: float = height / 1.4
	var fl: float = floor_y[n - 1]
	var fwd := Vector3(-sin(yaw), 0.0, -cos(yaw))
	_add_ellipsoid(Vector3(e.x, fl + ry * 0.4, e.z) + fwd * (rz * 0.7), Vector3(rx, ry, rz), yaw, fl, &"chamber")


func _add_pocket(side: float, at: float, r: float) -> void:
	# Past the portal, where the hood is thick enough to hold it.
	var first: int = _mouth_i
	while first < spine.size() - 1 and _arc[first] < _mouth_arc + _portal:
		first += 1
	var i: int = clampi(int(lerpf(float(first), float(spine.size() - 1), at)), 0, spine.size() - 1)
	var a: Vector3 = spine[maxi(0, i - 1)]
	var b: Vector3 = spine[mini(spine.size() - 1, i + 1)]
	var yaw: float = atan2(-(b - a).x, -(b - a).z)
	var lat := Vector3(cos(yaw), 0.0, -sin(yaw)) * side
	var c: Vector3 = Vector3(spine[i].x, floor_y[i] + r * 0.6, spine[i].z) + lat * (radii[i] + r * 0.5)
	_add_ellipsoid(c, Vector3(r * 1.2, r, r), yaw, floor_y[i], &"pocket")


func _finish_bounds(apron: float) -> void:
	var box := AABB()
	var first: bool = true
	for b: AABB in _cbox + _ebox:
		box = b if first else box.merge(b)
		first = false
	aabb = box
	_carve_aabb = aabb.grow(CLAMP)
	var dir := Vector2(-sin(_heading), -cos(_heading))
	var m := Vector2(mouth.origin.x, mouth.origin.z)
	_apron_a = Vector2(spine[0].x, spine[0].z) - dir * apron
	_apron_b = m + dir * 1.5
	_apron_r = radii[_mouth_i] + 0.5


# --- Plan-time checks -----------------------------------------------------------------------

## "" when the ground covers the cave by min_cover everywhere past the portal (`portal` m beyond
## the mouth, where the hood is still thin) and over the back wall, chamber and pocket; else why
## not, with the failing distance past the mouth in _cover_fail_arc (INF over an ellipsoid).
func _cover_problem(height_fn: Callable, min_cover: float, portal: float) -> String:
	var from_arc: float = _mouth_arc + portal
	var last: int = spine.size() - 1
	for i: int in spine.size():
		if _arc[i] < from_arc and i != last:
			continue
		var p: Vector3 = spine[i]
		var r: float = radii[i]
		var a: Vector3 = spine[maxi(0, i - 1)]
		var b: Vector3 = spine[mini(spine.size() - 1, i + 1)]
		var yaw: float = atan2(-(b - a).x, -(b - a).z)
		var lat := Vector3(cos(yaw), 0.0, -sin(yaw))
		for k: float in [0.0, -0.7, 0.7]:
			var q: Vector3 = p + lat * (r * k)
			var top: float = p.y + r * sqrt(1.0 - k * k) + _amp
			var cover: float = float(height_fn.call(q.x, q.z)) - top
			if cover < min_cover:
				_cover_fail_arc = _arc[i] - _mouth_arc
				return "cover %.1f m < %.1f m at %.0f m in" % [cover, min_cover, _arc[i] - _mouth_arc]
	for e: int in _ec.size():
		var c: Vector3 = _ec[e]
		var r3: Vector3 = _er[e]
		for o: Vector2 in [Vector2.ZERO, Vector2(0.7, 0.0), Vector2(-0.7, 0.0), Vector2(0.0, 0.7), Vector2(0.0, -0.7)]:
			var lx: float = o.x * r3.x
			var lz: float = o.y * r3.z
			var wx: float = c.x + lx * _ecos[e] + lz * _esin[e]
			var wz: float = c.z - lx * _esin[e] + lz * _ecos[e]
			var top2: float = c.y + r3.y * sqrt(maxf(0.0, 1.0 - o.length_squared())) + _amp
			var cover2: float = float(height_fn.call(wx, wz)) - top2
			if cover2 < min_cover:
				_cover_fail_arc = INF
				_cover_fail_kind = _ekind[e]
				return "cover %.1f m < %.1f m over the %s" % [cover2, min_cover, _ekind[e]]
	return ""


## "" when every spine sample past the mouth has min_clear of air over its floor.
func _clearance_problem(min_clear: float) -> String:
	for i: int in range(_mouth_i, spine.size()):
		var f := Vector3(spine[i].x, floor_y[i] + 0.05, spine[i].z)
		var h: float = 0.0
		while h < min_clear and sdf(f + Vector3(0.0, h, 0.0)) < 0.0:
			h += 0.1
		if h < min_clear:
			return "clearance %.1f m < %.1f m at %.0f m in" % [h, min_clear, _arc[i] - _mouth_arc]
	return ""


## "" when the opening holds a min_mouth_r half-disc of air over its floor.
func _mouth_problem(r: float) -> String:
	var o: Vector3 = mouth.origin + mouth.basis * Vector3(0.0, 0.0, -0.5)
	var lat: Vector3 = mouth.basis.x
	for q: Vector2 in [Vector2(0.0, 0.3), Vector2(0.0, r), Vector2(r * 0.7, r * 0.7), Vector2(-r * 0.7, r * 0.7), Vector2(r * 0.9, 0.3), Vector2(-r * 0.9, 0.3)]:
		if sdf(o + lat * q.x + Vector3.UP * q.y) >= 0.0:
			return "mouth narrower than %.1f m" % r
	return ""


# --- Distance -------------------------------------------------------------------------------

## The warp lattice at p, trilinear, in [-1, 1].
func _warp_at(p: Vector3) -> float:
	var gx: float = p.x * _inv_cell
	var gy: float = p.y * _inv_cell
	var gz: float = p.z * _inv_cell
	var fx0: float = floorf(gx)
	var fy0: float = floorf(gy)
	var fz0: float = floorf(gz)
	var fx: float = gx - fx0
	var fy: float = gy - fy0
	var fz: float = gz - fz0
	var x0: int = int(fx0) & WARP_MASK
	var y0: int = int(fy0) & WARP_MASK
	var z0: int = int(fz0) & WARP_MASK
	var x1: int = (x0 + 1) & WARP_MASK
	var y1: int = (y0 + 1) & WARP_MASK
	var z1: int = (z0 + 1) & WARP_MASK
	var r00: int = (z0 * WARP_N + y0) * WARP_N
	var r01: int = (z0 * WARP_N + y1) * WARP_N
	var r10: int = (z1 * WARP_N + y0) * WARP_N
	var r11: int = (z1 * WARP_N + y1) * WARP_N
	var a: float = lerpf(_warp[r00 + x0], _warp[r00 + x1], fx)
	var b: float = lerpf(_warp[r01 + x0], _warp[r01 + x1], fx)
	var c: float = lerpf(_warp[r10 + x0], _warp[r10 + x1], fx)
	var d: float = lerpf(_warp[r11 + x0], _warp[r11 + x1], fx)
	return lerpf(lerpf(a, b, fy), lerpf(c, d, fy), fz)


## Capsule i's unwarped distance at p, cut by its floor.
func _cap_raw(i: int, p: Vector3) -> float:
	var pa: Vector3 = p - _ca[i]
	var ba: Vector3 = _cba[i]
	var t: float = clampf(pa.dot(ba) * _cinv[i], 0.0, 1.0)
	return maxf((pa - ba * t).length() - (_cr0[i] + _cdr[i] * t), _cf0[i] + _cdf[i] * t - p.y)


## Ellipsoid e's unwarped (bound) distance at p, cut by its floor.
func _ell_raw(e: int, p: Vector3) -> float:
	var q: Vector3 = p - _ec[e]
	var r: Vector3 = _er[e]
	var lx: float = (q.x * _ecos[e] - q.z * _esin[e]) / r.x
	var ly: float = q.y / r.y
	var lz: float = (q.x * _esin[e] + q.z * _ecos[e]) / r.z
	var k0: float = sqrt(lx * lx + ly * ly + lz * lz)
	var k1: float = sqrt(lx * lx / (r.x * r.x) + ly * ly / (r.y * r.y) + lz * lz / (r.z * r.z))
	var d: float = k0 * (k0 - 1.0) / k1 if k1 > 1e-6 else -minf(r.x, minf(r.y, r.z))
	return maxf(d, _ef[e] - p.y)


## Signed distance to the cave air: > 0 in rock, < 0 in the cave. Beyond CLAMP of the air's
## bounds it is a lower bound (CLAMP + the distance to them), which clamps the same.
func sdf(p: Vector3) -> float:
	if not ok and _ca.is_empty():
		return INF
	if not _carve_aabb.has_point(p):
		return CLAMP + _box_distance(aabb, p)
	var w: float = _warp_at(p)
	var best: float = INF
	for i: int in _ca.size():
		if not _cbox[i].grow(CLAMP).has_point(p):
			continue
		var pa: Vector3 = p - _ca[i]
		var ba: Vector3 = _cba[i]
		var t: float = clampf(pa.dot(ba) * _cinv[i], 0.0, 1.0)
		var d: float = maxf((pa - ba * t).length() - (_cr0[i] + _cdr[i] * t) + _cw[i] * w, _cf0[i] + _cdf[i] * t - p.y)
		best = minf(best, d)
	for e: int in _ec.size():
		if not _ebox[e].grow(CLAMP).has_point(p):
			continue
		var q: Vector3 = p - _ec[e]
		var r: Vector3 = _er[e]
		var lx: float = (q.x * _ecos[e] - q.z * _esin[e]) / r.x
		var ly: float = q.y / r.y
		var lz: float = (q.x * _esin[e] + q.z * _ecos[e]) / r.z
		var k0: float = sqrt(lx * lx + ly * ly + lz * lz)
		var k1: float = sqrt(lx * lx / (r.x * r.x) + ly * ly / (r.y * r.y) + lz * lz / (r.z * r.z))
		var d2: float = k0 * (k0 - 1.0) / k1 if k1 > 1e-6 else -minf(r.x, minf(r.y, r.z))
		best = minf(best, maxf(d2 + _ew[e] * w, _ef[e] - p.y))
	if best == INF:
		return CLAMP + _box_distance(aabb, p)
	return best


static func _box_distance(b: AABB, p: Vector3) -> float:
	var q: Vector3 = (p - b.get_center()).abs() - b.size * 0.5
	return Vector3(maxf(q.x, 0.0), maxf(q.y, 0.0), maxf(q.z, 0.0)).length()


## min()s the cave into a padded block laid out like VolumeTerrain's chunks: `n` is the chunk's
## voxel count (VolumeTerrain.N), the block holds (n + 3)³ samples, sample (i, j, k) sits at
## origin + (Vector3(i, j, k) - Vector3.ONE) * voxel at index (k * s + j) * s + i, s = n + 3.
## Each sample becomes min(density, clamp(sdf, ±CLAMP)). Returns false when nothing changed.
## Pure: safe on worker threads, any number at once.
func carve_block(origin: Vector3, n: int, voxel: float, density: PackedFloat32Array) -> bool:
	if not ok:
		return false
	var s: int = n + 3
	if density.size() < s * s * s:
		return false
	var lo: Vector3 = origin - Vector3.ONE * voxel
	var span: float = float(s - 1) * voxel
	var block := AABB(lo, Vector3(span, span, span))
	if not block.intersects(_carve_aabb):
		return false
	# Primitives that can reach this block at all.
	var caps := PackedInt32Array()
	var ells := PackedInt32Array()
	for i: int in _ca.size():
		if _cbox[i].grow(CLAMP).intersects(block):
			caps.append(i)
	for e: int in _ec.size():
		if _ebox[e].grow(CLAMP).intersects(block):
			ells.append(e)
	if caps.is_empty() and ells.is_empty():
		return false
	var changed: bool = false
	var kc := PackedInt32Array()
	var ke := PackedInt32Array()
	var lbc := PackedFloat32Array()
	var lbe := PackedFloat32Array()
	for sk: int in range(0, s, SUB):
		var ek: int = mini(sk + SUB, s)
		for sj: int in range(0, s, SUB):
			var ej: int = mini(sj + SUB, s)
			for si: int in range(0, s, SUB):
				var ei: int = mini(si + SUB, s)
				var centre: Vector3 = lo + Vector3(float(si + ei - 1), float(sj + ej - 1), float(sk + ek - 1)) * (voxel * 0.5)
				var hd: float = Vector3(float(ei - si - 1), float(ej - sj - 1), float(ek - sk - 1)).length() * voxel * 0.5 * LIP
				# Bounds of every primitive over the sub-block: skip it when none can come within
				# CLAMP, fill it when one is CLAMP-deep air all over, else keep only the primitives
				# that can still be the nearest.
				var min_lb: float = INF
				var min_ub: float = INF
				lbc.resize(caps.size())
				lbe.resize(ells.size())
				for ci: int in caps.size():
					var c: int = caps[ci]
					var d: float = _cap_raw(c, centre)
					var slack: float = hd + _cw[c]
					lbc[ci] = d - slack
					min_lb = minf(min_lb, d - slack)
					min_ub = minf(min_ub, d + slack)
				for ei2: int in ells.size():
					var e: int = ells[ei2]
					var d2: float = _ell_raw(e, centre)
					var slack2: float = hd + _ew[e]
					lbe[ei2] = d2 - slack2
					min_lb = minf(min_lb, d2 - slack2)
					min_ub = minf(min_ub, d2 + slack2)
				if min_lb >= CLAMP:
					continue
				if min_ub <= -CLAMP:
					for k: int in range(sk, ek):
						for j: int in range(sj, ej):
							var row: int = (k * s + j) * s
							for i: int in range(si, ei):
								if density[row + i] > -CLAMP:
									density[row + i] = -CLAMP
									changed = true
					continue
				var cut: float = minf(CLAMP, min_ub)
				kc.clear()
				ke.clear()
				for ci: int in caps.size():
					if lbc[ci] < cut:
						kc.append(caps[ci])
				for ei2: int in ells.size():
					if lbe[ei2] < cut:
						ke.append(ells[ei2])
				if _carve_sub(lo, voxel, s, si, ei, sj, ej, sk, ek, kc, ke, density):
					changed = true
	return changed


## The per-sample shell of carve_block: the same arithmetic as sdf(), over the kept primitives.
func _carve_sub(lo: Vector3, voxel: float, s: int, si: int, ei: int, sj: int, ej: int, sk: int, ek: int,
		kc: PackedInt32Array, ke: PackedInt32Array, density: PackedFloat32Array) -> bool:
	var changed: bool = false
	var nc: int = kc.size()
	var ne: int = ke.size()
	for k: int in range(sk, ek):
		for j: int in range(sj, ej):
			var row: int = (k * s + j) * s
			for i: int in range(si, ei):
				var p: Vector3 = lo + Vector3(float(i), float(j), float(k)) * voxel
				var w: float = _warp_at(p)
				var best: float = CLAMP
				for ci: int in nc:
					var c: int = kc[ci]
					var pa: Vector3 = p - _ca[c]
					var ba: Vector3 = _cba[c]
					var t: float = clampf(pa.dot(ba) * _cinv[c], 0.0, 1.0)
					var d: float = maxf((pa - ba * t).length() - (_cr0[c] + _cdr[c] * t) + _cw[c] * w, _cf0[c] + _cdf[c] * t - p.y)
					if d < best:
						best = d
				for ei2: int in ne:
					var e: int = ke[ei2]
					var q: Vector3 = p - _ec[e]
					var r: Vector3 = _er[e]
					var lx: float = (q.x * _ecos[e] - q.z * _esin[e]) / r.x
					var ly: float = q.y / r.y
					var lz: float = (q.x * _esin[e] + q.z * _ecos[e]) / r.z
					var k0: float = sqrt(lx * lx + ly * ly + lz * lz)
					var k1: float = sqrt(lx * lx / (r.x * r.x) + ly * ly / (r.y * r.y) + lz * lz / (r.z * r.z))
					var d2: float = k0 * (k0 - 1.0) / k1 if k1 > 1e-6 else -minf(r.x, minf(r.y, r.z))
					d2 = maxf(d2 + _ew[e] * w, _ef[e] - p.y)
					if d2 < best:
						best = d2
				if best < -CLAMP:
					best = -CLAMP
				if best < density[row + i]:
					density[row + i] = best
					changed = true
	return changed


# --- Queries --------------------------------------------------------------------------------

## Vector2i(16 m column) -> Vector2i(cy0, cy1): the volume chunks whose padded samples the cave
## changes (its air bounds grown by CLAMP and one chunk padding).
func columns() -> Dictionary:
	var out: Dictionary = {}
	if not ok:
		return out
	var box: AABB = _carve_aabb.grow(1.0)
	var cy := Vector2i(int(floor(box.position.y / CHUNK)), int(floor(box.end.y / CHUNK)))
	for cz: int in range(int(floor(box.position.z / CHUNK)), int(floor(box.end.z / CHUNK)) + 1):
		for cx: int in range(int(floor(box.position.x / CHUNK)), int(floor(box.end.x / CHUNK)) + 1):
			out[Vector2i(cx, cz)] = cy
	return out


## In cave air (sd < -0.2) and at least 1 m under the ground.
func is_inside(p: Vector3, ground_y: float) -> bool:
	return ok and p.y <= ground_y - 1.0 and aabb.has_point(p) and sdf(p) < -0.2


## The cave floor under p, when p is under the cave's roof over a floor with air on it (or sunk
## up to 0.5 m into that floor); NAN otherwise (not over cave air, or up on the hill above it).
func floor_below(p: Vector3) -> float:
	if not ok or not _carve_aabb.has_point(p):
		return NAN
	var best: float = NAN
	for i: int in _ca.size():
		var box: AABB = _cbox[i]
		if p.x < box.position.x or p.x > box.end.x or p.z < box.position.z or p.z > box.end.z:
			continue
		var pa: Vector3 = p - _ca[i]
		var ba: Vector3 = _cba[i]
		var t: float = clampf(pa.dot(ba) * _cinv[i], 0.0, 1.0)
		var f: float = _cf0[i] + _cdf[i] * t
		var roof: float = _ca[i].y + ba.y * t + _cr0[i] + _cdr[i] * t + _cw[i]
		best = _floor_pick(p, f, roof, best)
	for e: int in _ec.size():
		var box2: AABB = _ebox[e]
		if p.x < box2.position.x or p.x > box2.end.x or p.z < box2.position.z or p.z > box2.end.z:
			continue
		best = _floor_pick(p, _ef[e], _ec[e].y + _er[e].y + _ew[e], best)
	return best


func _floor_pick(p: Vector3, f: float, roof: float, best: float) -> float:
	if f > p.y + 0.5 or p.y > roof or (not is_nan(best) and f <= best):
		return best
	return f if sdf(Vector3(p.x, f + 0.1, p.z)) < 0.0 else best


## The mouth apron (the opening and the slope below it), where vegetation must not grow.
func keep_out(x: float, z: float) -> bool:
	if not ok:
		return false
	var q := Vector2(x, z)
	var ab: Vector2 = _apron_b - _apron_a
	var t: float = clampf((q - _apron_a).dot(ab) / maxf(ab.length_squared(), 1e-6), 0.0, 1.0)
	return q.distance_to(_apron_a + ab * t) < _apron_r


## XZ rect covering the cave air and the mouth apron (grid indexing, region checks).
func footprint() -> Rect2:
	var r := Rect2(aabb.position.x, aabb.position.z, aabb.size.x, aabb.size.z)
	return r.expand(_apron_a).grow(_apron_r)


## {pos, normal, kind: &"mouth"|&"tunnel"|&"chamber"|&"pocket"}: floor points for props, spawns
## and set dressing. The mouth's normal points out of the hill; floor anchors' up.
func anchors() -> Array[Dictionary]:
	return _anchors.duplicate()


func _make_anchors() -> void:
	_anchors.clear()
	_anchors.append({"pos": mouth.origin, "normal": mouth.basis.z, "kind": &"mouth"})
	var next: float = _mouth_arc + 3.0
	for i: int in range(_mouth_i, spine.size()):
		if _arc[i] >= next:
			_anchors.append({"pos": Vector3(spine[i].x, floor_y[i], spine[i].z), "normal": Vector3.UP, "kind": &"tunnel"})
			next += 6.0
	for e: int in _ec.size():
		_anchors.append({"pos": Vector3(_ec[e].x, _ef[e], _ec[e].z), "normal": Vector3.UP, "kind": _ekind[e]})


## Up to 3 interior reflection-probe boxes: [[Transform3D, size: Vector3, daylight_ratio]].
## Each box's top stays >= 0.3 m under the ground at its corners; daylight falls with depth.
func probe_boxes() -> Array:
	return _probes.duplicate(true)


func _make_probes(height_fn: Callable, falloff: float) -> void:
	_probes.clear()
	var last: int = spine.size() - 1
	# Start where the roof is under ground: the opening itself is lit by the sky.
	var start: int = -1
	for i: int in range(_mouth_i, spine.size()):
		if float(height_fn.call(spine[i].x, spine[i].z)) - 0.3 >= floor_y[i] + 2.0:
			start = i
			break
	var ranges: Array[Vector2i] = []
	if start >= 0 and start < last:
		# The chamber takes a box of its own, so its tunnel gets at most two.
		var limit: int = 2 if _ekind.has(&"chamber") else 3
		var run: float = _arc[last] - _arc[start]
		var parts: int = clampi(int(run / 10.0), 1, limit)
		for p: int in parts:
			var a: int = start + (last - start) * p / parts
			var b: int = start + (last - start) * (p + 1) / parts
			if b > a:
				ranges.append(Vector2i(a, b))
	for rg: Vector2i in ranges:
		var a3: Vector3 = spine[rg.x]
		var b3: Vector3 = spine[rg.y]
		var yaw: float = atan2(-(b3 - a3).x, -(b3 - a3).z)
		var basis := Basis(Vector3.UP, yaw)
		var inv: Basis = basis.inverse()
		var lo := Vector3(INF, INF, INF)
		var hi := Vector3(-INF, -INF, -INF)
		for i: int in range(rg.x, rg.y + 1):
			var l: Vector3 = inv * spine[i]
			var r: float = radii[i]
			lo = lo.min(Vector3(l.x - r, floor_y[i], l.z - 0.5))
			hi = hi.max(Vector3(l.x + r, spine[i].y + r, l.z + 0.5))
		_push_probe(height_fn, basis, lo, hi, _arc[(rg.x + rg.y) / 2] - _mouth_arc, falloff)
	for e: int in _ec.size():
		if _ekind[e] != &"chamber":
			continue
		var basis2 := Basis(Vector3.UP, atan2(_esin[e], _ecos[e]))
		var l2: Vector3 = basis2.inverse() * _ec[e]
		var r3: Vector3 = _er[e]
		_push_probe(height_fn, basis2, Vector3(l2.x - r3.x, _ef[e], l2.z - r3.z), Vector3(l2.x + r3.x, _ec[e].y + r3.y, l2.z + r3.z),
			_arc[last] - _mouth_arc + r3.z, falloff)


## Adds a probe box spanning local [lo, hi] (y is world height) in `basis`, its top clamped under
## the ground at its corners and centre; dropped when that leaves under 1.5 m.
func _push_probe(height_fn: Callable, basis: Basis, lo: Vector3, hi: Vector3, depth: float, falloff: float) -> void:
	if _probes.size() >= 3:
		return
	var top: float = hi.y
	for c: Vector2 in [Vector2(lo.x, lo.z), Vector2(hi.x, lo.z), Vector2(lo.x, hi.z), Vector2(hi.x, hi.z), Vector2((lo.x + hi.x) * 0.5, (lo.z + hi.z) * 0.5)]:
		var w: Vector3 = basis * Vector3(c.x, 0.0, c.y)
		top = minf(top, float(height_fn.call(w.x, w.z)) - 0.3)
	var bottom: float = lo.y - 0.2
	if top - bottom < 1.5:
		return
	var centre_l := Vector3((lo.x + hi.x) * 0.5, 0.0, (lo.z + hi.z) * 0.5)
	var centre: Vector3 = basis * centre_l
	centre.y = (top + bottom) * 0.5
	var size := Vector3(hi.x - lo.x, top - bottom, hi.z - lo.z)
	var ratio: float = clampf(exp(-maxf(0.0, depth) / maxf(0.1, falloff)), 0.02, 1.0)
	_probes.append([Transform3D(basis, centre), size, ratio])


## Hash of everything that shapes the cave: equal digests mean identical carving.
func digest() -> String:
	var parts: PackedStringArray = [str(GEN_VERSION), str(id), str(style), str(seed), str(ok), reason]
	parts.append("%.3f|%.3f|%.3f|%.4f" % [mouth.origin.x, mouth.origin.y, mouth.origin.z, _heading])
	for i: int in spine.size():
		parts.append("%.3f,%.3f,%.3f,%.3f,%.3f" % [spine[i].x, spine[i].y, spine[i].z, radii[i], floor_y[i]])
	for e: int in _ec.size():
		parts.append("%s:%.3f,%.3f,%.3f/%.3f,%.3f,%.3f" % [_ekind[e], _ec[e].x, _ec[e].y, _ec[e].z, _er[e].x, _er[e].y, _er[e].z])
	var wsum: float = 0.0
	for i: int in _warp.size():
		wsum += _warp[i] * float(i % 97 + 1)
	parts.append("%.4f" % wsum)
	return "|".join(parts).sha256_text()
