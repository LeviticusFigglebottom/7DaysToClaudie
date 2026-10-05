class_name TetherRaise
extends RefCounted
## Raising the left wrist to read the tether (ADR-0029): lowered -> raising -> raised -> lowering,
## timed by data/config/viewmodel.json `tether`. While the wrist is up you can't swing; a swing
## (or anything that needs the hands) lowers it first. No nodes: tests step it directly.

enum State { LOWERED, RAISING, RAISED, LOWERING }

var state: State = State.LOWERED
## 0 lowered .. 1 raised.
var t: float = 0.0
var raise_time: float = 0.35
var lower_time: float = 0.25


func setup(cfg: Dictionary) -> void:
	var tc: Dictionary = cfg.get("tether", {})
	raise_time = maxf(0.01, float(tc.get("raise_time", raise_time)))
	lower_time = maxf(0.01, float(tc.get("lower_time", lower_time)))


## Asks for the wrist up or down; returns true if that changed anything.
func set_raised(up: bool) -> bool:
	if up and state in [State.RAISING, State.RAISED]:
		return false
	if not up and state in [State.LOWERING, State.LOWERED]:
		return false
	state = State.RAISING if up else State.LOWERING
	return true


func toggle() -> bool:
	return set_raised(not wants_up())


func wants_up() -> bool:
	return state == State.RAISING or state == State.RAISED


## Fully up: the screen is steady and readable.
func is_reading() -> bool:
	return state == State.RAISED


## Anything but fully lowered keeps the hands busy.
func blocks_attack() -> bool:
	return state != State.LOWERED


func update(dt: float) -> void:
	match state:
		State.RAISING:
			t = minf(1.0, t + dt / raise_time)
			if t >= 1.0:
				state = State.RAISED
		State.LOWERING:
			t = maxf(0.0, t - dt / lower_time)
			if t <= 0.0:
				state = State.LOWERED


## Eased progress, for blends (smoothstep).
func progress() -> float:
	return t * t * (3.0 - 2.0 * t)
