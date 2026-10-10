class_name ThrowHand
extends RefCounted
## Throwing from the hand (ADR-0057), for PlayerEquipment. Pressing attack with a throwable draws
## the arm back (the `throw_<hold>` use, else `throw`, played up to its `windup` frame and held
## there); holding it charges the throw over equip.charge_time and letting go throws at a speed
## between equip.throw_speed [tap, full]. A tap still winds up before it lets go, so the stone
## never leaves a hand still at rest. A molotov (equip.needs_light) is lit first: attack (or the
## light key) with an igniter in the pack (a lighter or a torch) lights its rag, which then burns
## equip.fuse seconds; held that long, it bursts in the hand into its ground fire at the
## thrower's feet.

const DEFAULT_TIME: float = 0.55
const DEFAULT_SPEED: float = 17.0

var equipment: PlayerEquipment
var charging: bool = false
## Seconds the button has been held on this throw.
var charge_t: float = 0.0
## Seconds left on a lit molotov's rag (-1 = none burning).
var fuse_left: float = -1.0
var _item: StringName = &""
var _use: StringName = &""
var _release_pending: bool = false


func _init(p_equipment: PlayerEquipment = null) -> void:
	equipment = p_equipment


static func needs_light(def: ItemDef) -> bool:
	return def != null and bool(def.equip.get("needs_light", false))


## 0..1: how far a throw held `held_s` seconds is charged.
static func charge_power(def: ItemDef, held_s: float) -> float:
	return clampf(held_s / maxf(def.equip_num("charge_time", 0.7), 0.05), 0.0, 1.0) if def != null else 1.0


## Launch speed (m/s) of a throw at `power` 0..1 (equip.throw_speed [tap, full]).
static func throw_speed(def: ItemDef, power: float) -> float:
	var s: Variant = def.equip.get("throw_speed", null) if def != null else null
	if s is Array and (s as Array).size() == 2:
		return lerpf(float(s[0]), float(s[1]), clampf(power, 0.0, 1.0))
	return DEFAULT_SPEED


## Seconds the whole throw motion takes (equip.attack_time).
static func throw_time(def: ItemDef) -> float:
	return def.equip_num("attack_time", DEFAULT_TIME) if def != null else DEFAULT_TIME


## The arms use a throw plays for `hold`: its own `throw_<hold>` if viewmodel.json has one.
static func use_for(hold: StringName, cfg: Dictionary) -> StringName:
	var own := StringName("throw_%s" % hold)
	return own if (cfg.get("uses", {}) as Dictionary).has(String(own)) else &"throw"


## The fraction of a throw use at which the arm is drawn right back (uses.<use>.windup frame).
static func windup_fraction(use: StringName, cfg: Dictionary) -> float:
	var u: Dictionary = (cfg.get("uses", {}) as Dictionary).get(String(use), {})
	return float(u.get("windup", 9)) / maxf(float(u.get("frames", 24)), 1.0)


## A throw of `def` starts (attack pressed): the arm draws back. No-op while one is under way.
func begin(def: ItemDef) -> void:
	if charging or def == null:
		return
	charging = true
	charge_t = 0.0
	_release_pending = false
	_item = def.id
	var vm: ViewModel = equipment.viewmodel if equipment != null else null
	_use = use_for(vm.hold_class, vm.cfg) if vm != null else &"throw"
	if vm != null:
		vm.play_use(_use, throw_time(def))


## Every physics frame: the charge (attack still `held`), the release, a molotov's fuse.
func update(delta: float, held: bool) -> void:
	_burn_fuse(delta)
	if not charging:
		return
	if equipment == null or equipment.current != _item:
		cancel()
		return
	var def: ItemDef = Content.item(_item)
	var vm: ViewModel = equipment.viewmodel
	var cfg: Dictionary = vm.cfg if vm != null else ViewModelHolds.config()
	var frac: float = windup_fraction(_use, cfg)
	var windup_s: float = throw_time(def) * frac
	charge_t += delta
	if vm != null:
		var frames: float = float(((cfg.get("uses", {}) as Dictionary).get(String(_use), {}) as Dictionary).get("frames", 24))
		vm.hold_action_at(frames * frac / 30.0)
	if not held:
		_release_pending = true
	if _release_pending and charge_t >= windup_s:
		charging = false
		if vm != null:
			vm.resume_action(throw_time(def) * (1.0 - frac))
		equipment._throw(def, throw_speed(def, charge_power(def, charge_t)))


func cancel() -> void:
	if not charging:
		return
	charging = false
	if equipment != null and equipment.viewmodel != null:
		equipment.viewmodel.release_action()


## Lights a molotov's rag in hand (needs a lighter or a torch in the pack).
func light(def: ItemDef) -> bool:
	if equipment == null or def == null:
		return false
	var p: Player = equipment.player
	if p == null or p.state == null or not StructurePiece.has_igniter(p.state):
		Events.player_status_message.emit("You need a lighter or a torch to light the %s." % def.display_name.to_lower(), &"warning")
		return false
	equipment._set_light(true)
	fuse_left = def.equip_num("fuse", 25.0)
	Audio.play_3d(&"sfx/lighter_flick", p.global_position, {"volume_db": -8.0, "occlusion": false})
	Audio.play_3d(&"sfx/torch_ignite", p.global_position, {"volume_db": -6.0, "occlusion": false})
	# A lighter does it when there is one (a torch otherwise): it shows in the other hand and wears.
	var lighter: ItemStack = p.state.inventory.find_tool("lighter")
	if lighter != null:
		wear_lighter(p.state, lighter)
	if equipment.viewmodel != null:
		var use := StringName("light_%s" % equipment.viewmodel.hold_class)
		equipment.viewmodel.play_use(use)
		if lighter != null:
			equipment.viewmodel.show_offhand(lighter.item_id, equipment.viewmodel.use_length(use))
	return true


## One flick's wear on a lighter (its durability, in uses); spent, it is gone.
static func wear_lighter(p: PlayerState, lighter: ItemStack) -> void:
	var d: ItemDef = lighter.def()
	if d == null or d.durability <= 0.0:
		return
	lighter.durability -= 1.0
	if lighter.durability <= 0.0:
		p.inventory.take_from(lighter, 1)
		Events.player_status_message.emit("The %s is spent." % d.display_name.to_lower(), &"warning")
	Events.inventory_changed.emit(p.id)


## A lit rag burns down; snuffed (light key) or put away it stops; burnt down, it bursts.
func _burn_fuse(delta: float) -> void:
	if fuse_left < 0.0:
		return
	var def: ItemDef = Content.item(equipment.current) if equipment != null else null
	if not needs_light(def) or not equipment.has_light_on():
		fuse_left = -1.0
		return
	fuse_left -= delta
	if fuse_left > 0.0:
		return
	fuse_left = -1.0
	cancel()
	_burst_in_hand(def)


func _burst_in_hand(def: ItemDef) -> void:
	var p: Player = equipment.player
	equipment._set_light(false)
	p.state.inventory.take(def.id, 1)
	Events.inventory_changed.emit(p.state.id)
	Events.player_status_message.emit("The %s bursts in your hand!" % def.display_name.to_lower(), &"warning")
	Audio.play_3d(&"sfx/glass_break", p.global_position + Vector3.UP, {"volume_db": 2.0})
	var fire: StringName = StringName(str(def.equip.get("ground_fire", "")))
	if fire != &"":
		GroundFire.spawn(p.get_tree().current_scene, p.global_position + Vector3.UP * 0.5, fire, p.state.id, p.global_position)
