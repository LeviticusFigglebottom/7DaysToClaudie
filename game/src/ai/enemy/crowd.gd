class_name Crowd
extends RefCounted
## Separation steering for bodies on foot (TD-011): Hollowed bumping shoulder to shoulder jammed in
## doorways and stacked into one column on the player's heels, because each steers alone along its
## own nav path and only the physics capsules kept them apart. Each moving body is entered in a
## shared 2 m grid as it moves and reads its neighbours from the grid the previous physics frame
## built (double buffered: everyone sees everyone, one frame late, at the cost of a dictionary
## insert and a 3x3 cell scan), then leans its wanted velocity away from the ones closer than their
## radii plus PERSONAL m. The push is sideways-weighted (it slides past rather than braking) and
## never makes a body faster than it wanted to go.

const CELL: float = 2.0
## Room kept beyond the two capsules' radii (m).
const PERSONAL: float = 0.35
## How hard a full overlap pushes, as a share of the body's own speed.
const STRENGTH: float = 0.8
## A body rescans its neighbours every EVERY physics ticks (staggered by id; perf_capture --hum-full:
## scanning every tick cost ~9% of the bodies' step at 64 alive).
const EVERY: int = 3
## Only bodies this near the player (m) take part: a jam out of sight costs nothing to leave.
const RANGE: float = 30.0

## Off: bodies steer alone (perf_capture --no-crowd measures the difference).
static var enabled: bool = true
static var _cur: Dictionary = {}
static var _prev: Dictionary = {}
static var _frame: int = -1


static func _cell(p: Vector3) -> Vector2i:
	return Vector2i(floori(p.x / CELL), floori(p.z / CELL))


## Enters `who` (an id, so the body can skip itself) at `p` with `radius` for this frame.
static func enter(who: int, p: Vector3, radius: float) -> void:
	var f: int = Engine.get_physics_frames()
	if f != _frame:
		_prev = _cur
		_cur = {}
		_frame = f
	var c: Vector2i = _cell(p)
	var bucket: Array = _cur.get(c, [])
	bucket.append([who, p, radius])
	_cur[c] = bucket


## The neighbours entered last frame within reach of `p`: [[id, position, radius], ...].
static func near(p: Vector3) -> Array:
	var out: Array = []
	var c: Vector2i = _cell(p)
	for dx: int in range(-1, 2):
		for dz: int in range(-1, 2):
			var b: Variant = _prev.get(c + Vector2i(dx, dz))
			if b != null:
				out.append_array(b as Array)
	return out


## `want` (a flat velocity) leaned away from the neighbours: pure, for tests.
static func steer(want: Vector3, p: Vector3, radius: float, who: int, neighbours: Array) -> Vector3:
	return apply(want, push(p, radius, who, neighbours))


## The summed push away from the neighbours closer than reach (0 when clear). Bodies compute it
## every few ticks (EVERY) and lean on the same push in between: the scan is most of the cost.
static func push(p: Vector3, radius: float, who: int, neighbours: Array) -> Vector3:
	var out := Vector3.ZERO
	for n: Array in neighbours:
		if int(n[0]) == who:
			continue
		var d: Vector3 = p - (n[1] as Vector3)
		d.y = 0.0
		var reach: float = radius + float(n[2]) + PERSONAL
		var l: float = d.length()
		if l >= reach:
			continue
		# Two bodies on the same spot: split them by id so they don't stay stacked.
		var away: Vector3 = d / l if l > 0.001 else Vector3(1.0 if who % 2 == 0 else -1.0, 0.0, 0.0)
		out += away * (1.0 - l / reach)
	return out


## `want` leaned by `p` (from push): mostly sideways, never faster than it wanted.
static func apply(want: Vector3, p: Vector3) -> Vector3:
	var speed: float = Vector2(want.x, want.z).length()
	if speed < 0.05 or p == Vector3.ZERO:
		return want
	var fwd: Vector3 = Vector3(want.x, 0.0, want.z) / speed
	# The part of the push straight back against the way it wants to go is halved, so a crowd
	# files past each other instead of stopping dead.
	var back: float = minf(0.0, p.dot(fwd))
	p -= fwd * back * 0.5
	var out: Vector3 = Vector3(want.x, 0.0, want.z) + p * speed * STRENGTH
	var l2: float = out.length()
	if l2 > speed:
		out *= speed / l2
	return Vector3(out.x, want.y, out.z)


## Clears the grids (tests, a world unload).
static func reset() -> void:
	_cur = {}
	_prev = {}
	_frame = -1
