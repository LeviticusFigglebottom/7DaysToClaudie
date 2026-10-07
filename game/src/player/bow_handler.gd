class_name BowHandler
extends RefCounted
## The bow in hand (ADR-0057), for PlayerEquipment: hold Attack to draw (equip.draw_time to full),
## let go to loose (from min_draw up; damage and arrow speed scale with how far it was drawn).
## Letting go short of min_draw, pressing Block while drawn, or running out of stamina holding a
## full draw past full_hold_free lets the string down without loosing: the draw plays back to the
## ready over let_down_time and the arrow stays on the string. A fresh press is needed to draw
## again after a shot or a let-down.
##
## Arrows are what the bow's equip.arrows names (first carried wins, in that order): each with its
## damage, dismember and break chance. The draw is the arms' fp_draw_bow frozen at the draw
## fraction (so a let-down is the draw played back); a held full draw loops fp_bow_drawn (a slight
## tremble); a release plays fp_release_bow over release_time, which also nocks the next arrow.
## Data: game/data/items/hunting.json hunting_bow.

## The draw anim's length at the arms' 30 fps (viewmodel.json uses.draw_bow.frames).
const FPS: float = 30.0

var eq: PlayerEquipment
## Drawing now (or letting down); the draw fraction 0..1.
var drawing: bool = false
var letting_down: bool = false
var frac: float = 0.0
## Seconds held at full draw.
var full_t: float = 0.0
## Seconds left of the release (follow-through and the next nock).
var release_left: float = -1.0
## Attack must be let go before the next draw.
var need_press: bool = false
var _looping_full: bool = false


func _init(p_eq: PlayerEquipment = null) -> void:
	eq = p_eq


# --- Pure rules (tests) --------------------------------------------------------------------------

static func is_bow(def: ItemDef) -> bool:
	return def != null and str(def.equip.get("kind", "")) == "bow"


## How far drawn after `held_s` seconds of a draw that takes `draw_time` to full.
static func draw_fraction(held_s: float, draw_time: float) -> float:
	return clampf(held_s / maxf(draw_time, 0.01), 0.0, 1.0)


static func _pair(def: ItemDef, key: String, lo: float, hi: float) -> Vector2:
	var v: Variant = def.equip.get(key, [lo, hi])
	if v is Array and (v as Array).size() == 2:
		return Vector2(float(v[0]), float(v[1]))
	return Vector2(float(v), float(v)) if v is float or v is int else Vector2(lo, hi)


## Launch speed (m/s) at draw fraction f: equip.speed [at the least draw, at full].
static func shot_speed(def: ItemDef, f: float) -> float:
	var s: Vector2 = _pair(def, "speed", 14.0, 50.0)
	return lerpf(s.x, s.y, clampf(f, 0.0, 1.0))


## The arrow's stats on this bow (equip.arrows.<id>), {} if it can't shoot it.
static func arrow_stats(def: ItemDef, arrow: StringName) -> Dictionary:
	return (def.equip.get("arrows", {}) as Dictionary).get(String(arrow), {}) if def != null else {}


## Damage of `arrow` loosed at draw fraction f: its damage x equip.damage_scale [least, full] x the
## bow's quality (and the ranged damage perk).
static func shot_damage(def: ItemDef, arrow: StringName, f: float, quality: int = 0, prog: Progression = null) -> float:
	var sc: Vector2 = _pair(def, "damage_scale", 0.25, 1.0)
	var dmg: float = float(arrow_stats(def, arrow).get("damage", 0.0)) * lerpf(sc.x, sc.y, clampf(f, 0.0, 1.0))
	if quality > 0:
		dmg *= ItemStack.quality_damage_mult(quality)
	if prog != null:
		dmg *= 1.0 + prog.modifier("ranged_damage_mult")
	return dmg


## How far (radians, each axis) the arrow may wander: a full draw is steady (spread_deg), a part
## draw wobbles up to spread_deg + draw_spread_deg; halved crouched, less with Steady Aim.
static func shot_spread(def: ItemDef, f: float, crouching: bool, prog: Progression = null) -> float:
	var steady: float = maxf(0.1, 1.0 + prog.modifier("ranged_spread_mult")) if prog != null else 1.0
	var deg: float = def.equip_num("spread_deg", 0.35) + def.equip_num("draw_spread_deg", 2.5) * (1.0 - clampf(f, 0.0, 1.0))
	return deg_to_rad(deg) * (0.5 if crouching else 1.0) * steady


## The arrow the bow will shoot from `inv`: the first of equip.arrows carried, &"" if none.
static func arrow_for(def: ItemDef, inv: Inventory) -> StringName:
	if def == null or inv == null:
		return &""
	for k: Variant in (def.equip.get("arrows", {}) as Dictionary).keys():
		if inv.has(StringName(str(k))):
			return StringName(str(k))
	return &""


# --- Per frame -----------------------------------------------------------------------------------

## Called every physics frame by PlayerEquipment while anything is in hand. `attack` is the
## attack button held, `can` whether the player may start a draw now (captured mouse, no guard,
## no cooldown).
func update(delta: float, attack: bool, can: bool) -> void:
	var def: ItemDef = Content.item(eq.current) if eq != null else null
	if not is_bow(def):
		if drawing:
			cancel()
		return
	if not attack:
		need_press = false
	if release_left >= 0.0:
		release_left -= delta
		if release_left < 0.0:
			_show_nock(def)
	if not drawing:
		if attack and can and not need_press and release_left < 0.0:
			_start(def)
		return
	var draw_time: float = def.equip_num("draw_time", 0.85)
	if letting_down:
		frac -= delta / maxf(def.equip_num("let_down_time", 0.35), 0.05)
		if frac <= 0.0:
			_end_draw()
			return
		_pose(def)
		return
	if attack:
		frac = minf(1.0, frac + delta / maxf(draw_time, 0.01))
		if frac >= 1.0:
			full_t += delta
			if full_t > def.equip_num("full_hold_free", 2.5) and not eq.player.state.stats.spend_stamina(def.equip_num("hold_stamina", 4.0) * delta):
				Events.player_status_message.emit("Your arms shake; you let the string down.", &"warning")
				let_down()
				return
		_pose(def)
		return
	if frac >= def.equip_num("min_draw", 0.2):
		loose(def)
	else:
		let_down()


func _start(def: ItemDef) -> void:
	var arrow: StringName = arrow_for(def, eq.player.state.inventory)
	need_press = true
	if arrow == &"":
		Events.player_status_message.emit("No arrows.", &"warning")
		eq._cooldown = 0.5
		_show_nock(def)
		return
	if not eq.player.state.stats.spend_stamina(def.equip_num("stamina", 4.0)):
		return
	drawing = true
	letting_down = false
	frac = 0.0
	full_t = 0.0
	_looping_full = false
	var rig: BowRig = _rig()
	if rig != null:
		rig.set_arrow_item(arrow)
		rig.nocked = true
	Audio.play_3d(&"sfx/swing_whoosh", eq.player.global_position + Vector3.UP * 1.4, {"volume_db": -24.0, "pitch": 0.5, "occlusion": false})
	_pose(def)


## Lets the string down without loosing (Block while drawn, a short draw, tired arms).
func let_down() -> void:
	if not drawing:
		return
	letting_down = true
	_looping_full = false
	need_press = true


## Puts the bow away mid-draw (changing items, the tether): no shot, no animation.
func cancel() -> void:
	drawing = false
	letting_down = false
	frac = 0.0
	_looping_full = false
	if eq != null and eq.viewmodel != null:
		eq.viewmodel.release_action()


func _end_draw() -> void:
	drawing = false
	letting_down = false
	frac = 0.0
	_looping_full = false
	if eq.viewmodel != null:
		eq.viewmodel.release_action()


## The arms at the draw: fp_draw_bow frozen at the fraction; a held full draw loops fp_bow_drawn.
func _pose(def: ItemDef) -> void:
	var vm: ViewModel = eq.viewmodel
	if vm == null:
		return
	if frac >= 1.0 and not letting_down:
		if not _looping_full and vm.has_action(&"fp_bow_drawn"):
			vm.play_action(&"fp_bow_drawn")
			_looping_full = true
		return
	_looping_full = false
	var frames: float = float(((ViewModelHolds.config().get("uses", {}) as Dictionary).get("draw_bow", {}) as Dictionary).get("frames", 24))
	vm.freeze_action(&"fp_draw_bow", frac * frames / FPS)


## Looses the arrow at the current draw: it leaves from the eye along the view (so it flies where
## the crosshair is), wobbled by the draw's spread.
func loose(def: ItemDef) -> void:
	var p: Player = eq.player
	var inv: Inventory = p.state.inventory
	var arrow: StringName = arrow_for(def, inv)
	var f: float = frac
	drawing = false
	letting_down = false
	frac = 0.0
	_looping_full = false
	need_press = true
	if arrow == &"":
		_end_draw()
		return
	inv.remove(arrow, 1)
	var cam: Camera3D = p.camera
	var spread: float = shot_spread(def, f, p.crouching, p.state.progression)
	var b: Basis = cam.global_transform.basis
	var dir: Vector3 = (-b.z).rotated(b.x, randf_range(-spread, spread)).rotated(Vector3.UP, randf_range(-spread, spread))
	var stats: Dictionary = arrow_stats(def, arrow)
	var bow_stack: ItemStack = inv.first(eq.current)
	var opts: Dictionary = {
		"damage": shot_damage(def, arrow, f, bow_stack.quality if bow_stack != null else 0, p.state.progression),
		"dismember": float(stats.get("dismember", 0.0)), "break": float(stats.get("break", 0.0)),
		"gravity": def.equip_num("gravity", 9.8), "noise": def.equip_num("impact_noise", 6.0),
		"stuck_seconds": def.equip_num("stuck_seconds", 900.0), "shooter": String(p.state.id),
		"origin": cam.global_position, "exclude": [p.get_rid()],
	}
	var parent: Node = p.get_tree().current_scene if p.get_tree().current_scene != null else p.get_parent()
	Arrow.launch(parent, arrow, cam.global_position + dir * 0.3, dir * shot_speed(def, f) + p.velocity * 0.3, opts)
	Audio.play_3d(&"sfx/swing_whoosh", p.global_position + Vector3.UP * 1.4, {"volume_db": -10.0, "pitch": 1.6, "occlusion": false})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(p.global_position, def.equip_num("noise", 4.0), &"impact", p.state.id)
	release_left = def.equip_num("release_time", 0.7)
	eq._cooldown = release_left
	var rig: BowRig = _rig()
	if rig != null:
		rig.nocked = false
	if eq.viewmodel != null:
		eq.viewmodel.release_action()
		eq.viewmodel.play_use(&"release_bow", release_left)
	eq._wear(def)
	Events.inventory_changed.emit(p.state.id)


## The next arrow is on the string (or the string is bare: none carried).
func _show_nock(def: ItemDef) -> void:
	var rig: BowRig = _rig()
	if rig == null:
		return
	var arrow: StringName = arrow_for(def, eq.player.state.inventory)
	if arrow != &"":
		rig.set_arrow_item(arrow)
	rig.nocked = arrow != &""


func _rig() -> BowRig:
	return BowRig.of(eq.viewmodel.held_item()) if eq != null and eq.viewmodel != null else null


## Equipping the bow: nock what is carried.
func on_equipped() -> void:
	cancel()
	release_left = -1.0
	var def: ItemDef = Content.item(eq.current) if eq != null else null
	if is_bow(def):
		_show_nock(def)
