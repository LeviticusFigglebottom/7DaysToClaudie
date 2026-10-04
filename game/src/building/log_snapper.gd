class_name LogSnapper
extends RefCounted
## Snap targets for 4 m logs (length along local +X, Ø 0.34 m), the freeform-building core.
## Pure functions (unit-tested): the preview asks for the candidate nearest the free aim point
## among the logs around it, preferring candidates whose axis matches the player's chosen
## orientation, so rotating the held log selects between "continue the wall" and "corner".
##
## Candidates around an existing horizontal log L:
##   course above / below (notched stacking, STACK apart), end to end (±LENGTH along X),
##   side by side (±DIAM along Z), perpendicular corner notches (±CORNER along X and Z, half a
##   course up or down), and perpendicular deck logs resting across the top.
## Around a vertical post: a crossbeam resting on its top in either horizontal direction.

const LENGTH: float = 4.0
const DIAM: float = 0.34
const RADIUS: float = 0.17
const STACK: float = 0.29
const CORNER: float = 1.83
## Adjacent walls interleave at corners: each wall's courses sit half a course above the other's.
const CORNER_RISE: float = STACK * 0.5
const SNAP_DIST: float = 0.8
const AXIS_MISMATCH_PENALTY: float = 0.55


static func is_vertical(b: Basis) -> bool:
	return absf(b.x.normalized().y) > 0.8


## Log end points (segment the collision capsule spans).
static func segment(t: Transform3D) -> PackedVector3Array:
	var ax: Vector3 = t.basis.x.normalized() * LENGTH * 0.5
	return PackedVector3Array([t.origin - ax, t.origin + ax])


static func candidates(t: Transform3D) -> Array[Transform3D]:
	var out: Array[Transform3D] = []
	var b: Basis = t.basis.orthonormalized()
	var x: Vector3 = b.x
	var z: Vector3 = b.z
	if is_vertical(b):
		var top: Vector3 = t.origin + (x if x.y > 0.0 else -x) * LENGTH * 0.5
		for yaw: float in [0.0, PI * 0.5]:
			var hb := Basis(Vector3.UP, yaw)
			out.append(Transform3D(hb, top + Vector3.UP * RADIUS))
			out.append(Transform3D(hb, top + Vector3.UP * RADIUS + hb.x * LENGTH * 0.5))
			out.append(Transform3D(hb, top + Vector3.UP * RADIUS - hb.x * LENGTH * 0.5))
		return out
	var flat_x := Vector3(x.x, 0.0, x.z).normalized() if Vector2(x.x, x.z).length() > 0.01 else Vector3.RIGHT
	var perp := Basis(Vector3.UP, PI * 0.5) * b
	out.append(Transform3D(b, t.origin + Vector3.UP * STACK))
	out.append(Transform3D(b, t.origin - Vector3.UP * STACK))
	out.append(Transform3D(b, t.origin + x * LENGTH))
	out.append(Transform3D(b, t.origin - x * LENGTH))
	out.append(Transform3D(b, t.origin + z * DIAM))
	out.append(Transform3D(b, t.origin - z * DIAM))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			for sy: float in [-1.0, 1.0]:
				out.append(Transform3D(perp, t.origin + flat_x * CORNER * sx + z * CORNER * sz + Vector3.UP * CORNER_RISE * sy))
	# Deck logs resting across this one, side by side, centred 1.6 m to either side (a sill pair
	# 3.2 m apart carries a 4 m deck).
	for i: int in 12:
		var k: float = -1.87 + DIAM * float(i)
		for side: float in [-1.0, 1.0]:
			out.append(Transform3D(perp, t.origin + flat_x * k + z * 1.6 * side + Vector3.UP * (DIAM - 0.01)))
	return out


## Best snap for a free placement among neighbouring logs. Returns {ok, xform, from} where
## `from` is the index of the neighbour that produced it.
static func best_snap(free: Transform3D, neighbours: Array[Transform3D]) -> Dictionary:
	var best_d: float = SNAP_DIST
	var best: Transform3D = free
	var from: int = -1
	var want_axis: Vector3 = free.basis.x.normalized()
	for i: int in neighbours.size():
		for c: Transform3D in candidates(neighbours[i]):
			var d: float = c.origin.distance_to(free.origin)
			if absf(c.basis.x.normalized().dot(want_axis)) < 0.8:
				d += AXIS_MISMATCH_PENALTY
			if d < best_d:
				best_d = d
				best = c
				from = i
	return {"ok": from >= 0, "xform": best, "from": from}


## Shortest distance between two logs' axes (contact when <= DIAM + tolerance).
static func axis_distance(a: Transform3D, b: Transform3D) -> float:
	var sa: PackedVector3Array = segment(a)
	var sb: PackedVector3Array = segment(b)
	var pts: PackedVector3Array = Geometry3D.get_closest_points_between_segments(sa[0], sa[1], sb[0], sb[1])
	return pts[0].distance_to(pts[1])


## How log `a` touches log `b`: &"on" (a rests on b), &"under" (b rests on a), &"side", or &"" (apart).
static func relation(a: Transform3D, b: Transform3D, tolerance: float = 0.08) -> StringName:
	var sa: PackedVector3Array = segment(a)
	var sb: PackedVector3Array = segment(b)
	var pts: PackedVector3Array = Geometry3D.get_closest_points_between_segments(sa[0], sa[1], sb[0], sb[1])
	var d: float = pts[0].distance_to(pts[1])
	if d > DIAM + tolerance:
		return &""
	var dy: float = pts[0].y - pts[1].y
	if dy > 0.12:
		return &"on"
	if dy < -0.12:
		return &"under"
	return &"side"


## True if two logs would interpenetrate (axes much closer than one diameter): placement blocker.
## Ends are trimmed so logs butted end to end or notched at corners do not count.
static func overlaps(a: Transform3D, b: Transform3D) -> bool:
	var sa: PackedVector3Array = _trimmed(a, 0.3)
	var sb: PackedVector3Array = _trimmed(b, 0.3)
	var pts: PackedVector3Array = Geometry3D.get_closest_points_between_segments(sa[0], sa[1], sb[0], sb[1])
	return pts[0].distance_to(pts[1]) < DIAM * 0.62


static func _trimmed(t: Transform3D, trim: float) -> PackedVector3Array:
	var ax: Vector3 = t.basis.x.normalized() * (LENGTH * 0.5 - trim)
	return PackedVector3Array([t.origin - ax, t.origin + ax])
