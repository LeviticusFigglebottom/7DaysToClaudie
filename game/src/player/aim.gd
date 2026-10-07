class_name PlayerAim
extends Node
## Aiming a ranged weapon (ADR-0057). Holding Aim (right mouse) with a gun in hand raises it to the
## eye over the gun's aim time: the view narrows by its zoom factor (a scoped rifle far more than
## the revolver's iron sights), shots wander less (spread multiplier), the arms sway less, the
## player walks slower and turns slower in proportion to the zoom. A scoped gun, once fully up,
## puts the scope picture over the view (ScopeOverlay) and hides the arms. Reloading, building,
## reading the tether or sprinting lower it; changing what is in hand drops it at once.
##
## The numbers: data/config/viewmodel.json `aim` (defaults) overridden per item by equip.aim
## {zoom, spread, sway, move, time, scope}; where the gun sits when up is the hold's `aim` (the
## sight socket brought onto the line of sight, ViewModel). The state machine is update(), which
## the tests drive directly; _physics_process only gathers the input.

## Seconds of aim progress per second are 1 / time; progress is linear, amount() eases it.
var progress: float = 0.0
## Aim is held and allowed this frame.
var wanted: bool = false
var player: Player = null
var _item: StringName = &""
var _cfg: Dictionary = {}
var _overlay: ScopeOverlay = null


func _ready() -> void:
	player = get_parent() as Player


## The aim settings for an item: viewmodel.json `aim` overridden by its equip.aim. Empty for
## anything that is not a ranged weapon (it can't be aimed).
static func settings(def: ItemDef) -> Dictionary:
	if def == null or str(def.equip.get("kind", "")) != "ranged":
		return {}
	var out: Dictionary = (ViewModelHolds.config().get("aim", {}) as Dictionary).duplicate()
	out.erase("_doc")
	var own: Variant = def.equip.get("aim", {})
	if own is Dictionary:
		out.merge(own, true)
	return out


## The rig offset that brings a sight onto the line of sight: `sight` is the sight socket in the
## rig's space (its -Z down the barrel, +Y up), the aim point `up` metres above it, put `relief`
## metres in front of the eye on the view's axis (plus `move`), looking straight down it.
static func sight_offset(sight: Transform3D, up: float, relief: float, move: Vector3 = Vector3.ZERO) -> Transform3D:
	var b: Basis = sight.basis.orthonormalized()
	var at := Transform3D(b, sight.origin + b.y * up)
	var target := Transform3D(Basis(), Vector3(move.x, move.y, -relief + move.z))
	return target * at.affine_inverse()


static func can_aim(def: ItemDef) -> bool:
	return not settings(def).is_empty()


## Steps the aim: `want` is the button (and everything that allows it), `item` what is in hand.
func update(delta: float, want: bool, item: StringName) -> void:
	if item != _item:
		_item = item
		_cfg = settings(Content.item(item)) if item != &"" else {}
		progress = 0.0
	wanted = want and not _cfg.is_empty()
	var t: float = maxf(0.02, float(_cfg.get("time", 0.25)))
	progress = move_toward(progress, 1.0 if wanted else 0.0, delta / t)


## How far up the gun is, eased (0 at the hip, 1 on the sights).
func amount() -> float:
	return smoothstep(0.0, 1.0, progress)


func is_aiming() -> bool:
	return progress > 0.0


func fully_aimed() -> bool:
	return progress >= 1.0


func _lerp_key(key: String) -> float:
	return lerpf(1.0, float(_cfg.get(key, 1.0)), amount())


## Magnification of the view now (1 = none).
func zoom() -> float:
	return maxf(1.0, _lerp_key("zoom"))


## The camera's field of view (degrees) for a base field of view, narrowed by the zoom.
func fov(base_deg: float) -> float:
	return rad_to_deg(2.0 * atan(tan(deg_to_rad(base_deg) * 0.5) / zoom()))


## Multiplier on a shot's spread now.
func spread_mult() -> float:
	return clampf(_lerp_key("spread"), 0.0, 1.0)


## Multiplier on the arms' sway, breathing and bob now.
func sway_mult() -> float:
	return clampf(_lerp_key("sway"), 0.0, 1.0)


## Multiplier on walking speed now.
func move_mult() -> float:
	return clampf(_lerp_key("move"), 0.05, 1.0)


## Multiplier on mouse look now: turning is as fast across the screen when zoomed in.
func look_mult() -> float:
	return 1.0 / zoom()


## The scope picture is up: a scoped gun almost all the way to the eye.
func scoped() -> bool:
	return bool(_cfg.get("scope", false)) and progress >= float(_cfg.get("scope_from", 0.92))


func _physics_process(delta: float) -> void:
	if player == null or player.state == null:
		return
	var eq: PlayerEquipment = player.equipment
	var item: StringName = eq.current if eq != null else &""
	var want: bool = player.input_enabled and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and Input.is_action_pressed(&"aim")
	update(delta, want and not _blocked(eq), item)
	_present(eq)


## What keeps the gun down: a reload, building, the tether up, sprinting.
func _blocked(eq: PlayerEquipment) -> bool:
	if eq == null:
		return true
	if eq.is_reloading() or eq.call(&"_building_busy"):
		return true
	if eq.viewmodel != null and eq.viewmodel.tether_raised():
		return true
	return player.sprinting


func _present(eq: PlayerEquipment) -> void:
	var scope: bool = scoped()
	if eq != null and eq.viewmodel != null:
		eq.viewmodel.set_aim(amount(), 1.0 - sway_mult(), scope)
	if scope and _overlay == null:
		_overlay = ScopeOverlay.new()
		add_child(_overlay)
	if _overlay != null:
		_overlay.visible = scope
