class_name ViewModelClimb
extends RefCounted
## First-person climbing arms (ADR-0057): while the player climbs a ladder or a rope
## (PoiPieces.Ladder, ADR-0051) the item in hand is stowed, the hands come up and close on the
## rails (`fp_<hold>_grab`), go hand over hand as the player climbs, and open and drop away when
## they let go (`fp_<hold>_release`) before the item comes back. The cycle (`fp_<hold>_cycle`) is
## never played: it is seeked to the phase the metres climbed give (viewmodel.json
## `climb.cycle_m`), so a gripping hand rides down the view exactly as fast as the rails do,
## runs backwards climbing down and holds still when the player does. The arms are kept level and
## square to the ladder rather than to the view, so looking around doesn't take the hands off it.
##
## Movement is Player's (it owns the ladder): this only polls its getters each frame, duck-typed
## (is_climbing, climbing_ladder, climb_speed), and is inert on a player without them. Node-free
## and Input-free, so tests drive it with a fake player.

enum State { OFF, GRAB, CLIMB, RELEASE }

const LADDER: StringName = &"climb"
const ROPE: StringName = &"climb_rope"

var state: State = State.OFF
## 0..1 through the hand-over-hand cycle.
var phase: float = 0.0
## The hold climbing now (or last): LADDER or ROPE.
var hold: StringName = LADDER
## Seconds into the grab-on or let-go.
var t: float = 0.0
## The player (or a stand-in) polled each frame; ViewModel sets it to its own player.
var source: Object = null
## The ladder's horizontal direction toward the climber, kept for the let-go (Vector3.ZERO = none).
var face := Vector3.ZERO
## How far the arms are anchored to the ladder (0 = they follow the view), eased in and out.
var anchor: float = 0.0

var cycle_m: Dictionary = {LADDER: 0.58, ROPE: 0.48}
var grab_time: float = 0.3
var release_time: float = 0.35
var anchor_max: float = 1.0


func setup(cfg: Dictionary) -> void:
	var c: Dictionary = cfg.get("climb", {})
	var cm: Dictionary = c.get("cycle_m", {})
	for k: Variant in cm:
		cycle_m[StringName(str(k))] = maxf(0.05, float(cm[k]))
	grab_time = maxf(0.05, float(c.get("grab_time", grab_time)))
	release_time = maxf(0.05, float(c.get("release_time", release_time)))
	anchor_max = clampf(float(c.get("anchor", anchor_max)), 0.0, 1.0)


# --- The player's climbing, duck-typed -------------------------------------------------------

static func is_climbing(p: Object) -> bool:
	return p != null and is_instance_valid(p) and p.has_method(&"is_climbing") and bool(p.call(&"is_climbing"))


static func ladder_of(p: Object) -> Node3D:
	if p == null or not is_instance_valid(p) or not p.has_method(&"climbing_ladder"):
		return null
	return p.call(&"climbing_ladder") as Node3D


static func speed_of(p: Object) -> float:
	if p == null or not is_instance_valid(p) or not p.has_method(&"climb_speed"):
		return 0.0
	return float(p.call(&"climb_speed"))


## The hold for a ladder: a rope (meta `climb_style` "rope", ClimbMount) or rails.
static func hold_for(ladder: Node) -> StringName:
	if ladder != null and ladder.has_meta(&"climb_style") and str(ladder.get_meta(&"climb_style")) == "rope":
		return ROPE
	return LADDER


## The horizontal direction from a ladder's rails toward its climber: its face() when it has one.
static func face_of(ladder: Node3D) -> Vector3:
	if ladder == null:
		return Vector3.ZERO
	var f: Vector3 = ladder.call(&"face") if ladder.has_method(&"face") else ladder.global_basis.z
	f.y = 0.0
	return f.normalized() if f.length() > 0.01 else Vector3.BACK


# --- Per frame -----------------------------------------------------------------------------------

## Advances by one frame of `delta` seconds. Returns true when the state changed (ViewModel then
## plays the grab-on or the let-go, or brings the item back).
func update(delta: float) -> bool:
	var on: bool = is_climbing(source)
	var before: State = state
	match state:
		State.OFF:
			if on:
				_begin()
		State.GRAB:
			t += delta
			if not on:
				_end()
			elif t >= grab_time:
				state = State.CLIMB
		State.CLIMB:
			if not on:
				_end()
			else:
				var m: float = float(cycle_m.get(hold, 0.58))
				phase = fposmod(phase + speed_of(source) * delta / m, 1.0)
		State.RELEASE:
			t += delta
			if on:
				_begin()
			elif t >= release_time:
				state = State.OFF
				face = Vector3.ZERO
	if on:
		var lad: Node3D = ladder_of(source)
		if lad != null:
			face = face_of(lad)
	var want: float = anchor_max if state == State.GRAB or state == State.CLIMB else 0.0
	anchor = move_toward(anchor, want, delta / maxf(0.05, grab_time if want > anchor else release_time))
	return state != before


func _begin() -> void:
	state = State.GRAB
	t = 0.0
	phase = 0.0
	hold = hold_for(ladder_of(source))


func _end() -> void:
	state = State.RELEASE
	t = 0.0


## The item in hand is put away from the grab-on until the let-go is over.
func stows_item() -> bool:
	return state != State.OFF


## Climbing or letting go: the arms are this module's, not the hold's.
func busy() -> bool:
	return state != State.OFF


func cycle_action() -> StringName:
	return StringName("fp_%s_cycle" % hold)


func grab_action() -> StringName:
	return StringName("fp_%s_grab" % hold)


func release_action() -> StringName:
	return StringName("fp_%s_release" % hold)


## Seconds into the cycle action of `length` seconds for the current phase.
func cycle_time(length: float) -> float:
	return phase * length


## The arms' turn under the camera that keeps them level and facing the ladder (`face` points from
## the rails to the climber), blended by `anchor`: identity off a ladder or looking straight at it.
func rig_basis(cam_basis: Basis) -> Basis:
	if anchor <= 0.0 or face == Vector3.ZERO:
		return Basis()
	var fwd: Vector3 = -face
	var level := Basis(fwd.cross(Vector3.UP).normalized(), Vector3.UP, -fwd)
	var q := Quaternion(cam_basis.orthonormalized().inverse() * level)
	return Basis(Quaternion.IDENTITY.slerp(q, anchor))
