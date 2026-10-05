class_name Polyline2
extends RefCounted
## 2D polyline on the world XZ plane with arc-length parameterization and per-vertex values
## (e.g. river width/level) interpolated along it. Used by rivers, roads, paths and cliffs.

var points: PackedVector2Array = []
## Cumulative arc length at each point.
var lengths: PackedFloat32Array = []
var total_length: float = 0.0
var bounds := Rect2()


## Builds a polyline from [[x, z], ...]. With max_piece > 0 the control points are interpolated
## by a centripetal-ish Catmull-Rom spline into pieces of at most max_piece metres, so rivers and
## roads curve naturally and distance fields have no creases at sharp vertices.
static func from_array(arr: Array, max_piece: float = 10.0) -> Polyline2:
	var ctrl := PackedVector2Array()
	for p: Variant in arr:
		ctrl.append(Vector2(float(p[0]), float(p[1])))
	var pl := Polyline2.new()
	if max_piece <= 0.0 or ctrl.size() < 3:
		pl.points = ctrl
	else:
		pl.points = _catmull_rom(ctrl, max_piece)
	pl._rebuild()
	return pl


static func _catmull_rom(c: PackedVector2Array, max_piece: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var count: int = c.size()
	for i: int in count - 1:
		var p0: Vector2 = c[maxi(i - 1, 0)]
		var p1: Vector2 = c[i]
		var p2: Vector2 = c[i + 1]
		var p3: Vector2 = c[mini(i + 2, count - 1)]
		var steps: int = maxi(1, int(ceil(p1.distance_to(p2) / max_piece)))
		for k: int in steps:
			var t: float = float(k) / steps
			var t2: float = t * t
			var t3: float = t2 * t
			out.append(0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3))
	out.append(c[count - 1])
	return out


func _rebuild() -> void:
	lengths.resize(points.size())
	total_length = 0.0
	if points.is_empty():
		return
	lengths[0] = 0.0
	bounds = Rect2(points[0], Vector2.ZERO)
	for i: int in range(1, points.size()):
		total_length += points[i].distance_to(points[i - 1])
		lengths[i] = total_length
		bounds = bounds.expand(points[i])


## Point at arc length s (clamped).
func point_at(s: float) -> Vector2:
	if points.size() < 2:
		return points[0] if points.size() == 1 else Vector2.ZERO
	s = clampf(s, 0.0, total_length)
	var i: int = _segment_for(s)
	var seg_len: float = lengths[i + 1] - lengths[i]
	var t: float = 0.0 if seg_len <= 0.0 else (s - lengths[i]) / seg_len
	return points[i].lerp(points[i + 1], t)


## Unit tangent at arc length s.
func tangent_at(s: float) -> Vector2:
	if points.size() < 2:
		return Vector2.RIGHT
	var i: int = _segment_for(clampf(s, 0.0, total_length))
	return (points[i + 1] - points[i]).normalized()


func _segment_for(s: float) -> int:
	var lo: int = 0
	var hi: int = points.size() - 2
	while lo < hi:
		var mid: int = (lo + hi + 1) >> 1
		if lengths[mid] <= s:
			lo = mid
		else:
			hi = mid - 1
	return lo


## Closest point query. Returns Vector3(distance, arc_length_at_closest, signed_side) where the
## sign is +1 if p is to the left of the travel direction (when viewed with +Z down), -1 right.
func closest(p: Vector2) -> Vector3:
	var best_d2: float = INF
	var best_s: float = 0.0
	var best_side: float = 1.0
	for i: int in points.size() - 1:
		var a: Vector2 = points[i]
		var b: Vector2 = points[i + 1]
		var ab: Vector2 = b - a
		var l2: float = ab.length_squared()
		var t: float = 0.0 if l2 <= 0.0 else clampf((p - a).dot(ab) / l2, 0.0, 1.0)
		var q: Vector2 = a + ab * t
		var d2: float = p.distance_squared_to(q)
		if d2 < best_d2:
			best_d2 = d2
			best_s = lengths[i] + sqrt(l2) * t
			best_side = 1.0 if ab.cross(p - a) >= 0.0 else -1.0
	return Vector3(sqrt(best_d2), best_s, best_side)


## A value along the arc: a single number, a [start, end] pair interpolated linearly, or (ADR-0031,
## a generated river's level and width) three or more values spaced evenly along the arc and
## interpolated piecewise linearly between them.
func value_at(values: Variant, s: float) -> float:
	if values is float or values is int:
		return float(values)
	var arr: Array = values
	if arr.size() == 1:
		return float(arr[0])
	var t: float = 0.0 if total_length <= 0.0 else clampf(s / total_length, 0.0, 1.0)
	if arr.size() == 2:
		return lerpf(float(arr[0]), float(arr[1]), t)
	var f: float = t * (arr.size() - 1)
	var i: int = mini(int(f), arr.size() - 2)
	return lerpf(float(arr[i]), float(arr[i + 1]), f - i)
