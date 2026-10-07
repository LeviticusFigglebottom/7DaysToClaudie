class_name ThrownItem
extends RigidBody3D
## A thrown stone/spear/molotov: damages what it hits once, then becomes a pickup.
## Where it first lands it makes a noise (ADR-0057): the item's equip.noise as a Stimuli sound of
## kind `distraction` at the landing point, so the Hollowed in earshot go to look there (not at
## the thrower) and wildlife bolt from it at their bolt_loudness. A breakable throwable
## (equip.ground_fire: the molotov) shatters on that first contact instead of coming to rest, and
## if its rag was lit it leaves a GroundFire where it broke.

## Stimuli kind of a landing throwable (sound heard where it lands, not where it came from).
const NOISE_KIND: StringName = &"distraction"
## Loudness (m) of a throwable without equip.noise.
const DEFAULT_NOISE: float = 9.0

var item_id: StringName = &"stone"
## The thrown item itself (quality, durability); a plain one of item_id when unset.
var stack: ItemStack = null
var thrower: StringName = &""
var damage: float = 10.0
## Where it was thrown from: what a struck Hollow turns toward (and wakes facing).
var origin := Vector3.ZERO
## A molotov's rag is burning: it bursts into flames where it breaks.
var lit: bool = false
var _armed: bool = true
var _life: float = 0.0


func _ready() -> void:
	collision_layer = 1 << 13
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 9) | (1 << 12)
	contact_monitor = true
	max_contacts_reported = 2
	mass = 0.8
	var cs := CollisionShape3D.new()
	var sh := SphereShape3D.new()
	sh.radius = 0.08
	cs.shape = sh
	add_child(cs)
	var model: Node3D = _flight_model()
	add_child(model)
	if lit:
		_light_rag(model)
	body_entered.connect(_on_hit)


func _process(delta: float) -> void:
	_life += delta
	if _life > 3.0 and linear_velocity.length() < 0.3:
		ItemDrop.spawn(get_tree().current_scene, stack if stack != null else ItemStack.make(item_id, 1), global_position)
		queue_free()


## How loud its landing is (m): the item's equip.noise.
static func landing_noise(id: StringName) -> float:
	var def: ItemDef = Content.item(id)
	return def.equip_num("noise", DEFAULT_NOISE) if def != null else DEFAULT_NOISE


## The ground fire it breaks into (equip.ground_fire), or &"" for one that lands whole.
static func ground_fire_of(id: StringName) -> StringName:
	var def: ItemDef = Content.item(id)
	return StringName(str(def.equip.get("ground_fire", ""))) if def != null else &""


func _on_hit(body: Node) -> void:
	impact(body)


## The first contact: damage to what it struck, the landing noise and (molotov) the shatter.
## Public so tests can land a throw without simulating its flight.
func impact(body: Node) -> void:
	if not _armed:
		return
	_armed = false
	var def: ItemDef = Content.item(item_id)
	var dtype: StringName = StringName(str(def.equip.get("damage_type", "blunt"))) if def != null else &"blunt"
	var q: float = ItemStack.quality_damage_mult(stack.quality) if stack != null else 1.0
	var info := DamageInfo.make(damage * q * clampf(linear_velocity.length() / 15.0, 0.3, 1.2), dtype, &"thrown", thrower)
	info.hit_pos = global_position
	info.source_pos = origin
	info.direction = linear_velocity.normalized()
	info.collider = body
	info.stagger = 0.4
	var r: Object = PlayerEquipment._damage_receiver(body) if body != null else null
	if r != null:
		r.call(&"take_damage", info)
	var fire: StringName = ground_fire_of(item_id)
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, landing_noise(item_id), NOISE_KIND, thrower)
	if fire == &"":
		Audio.play_3d(&"sfx/hit_stone", global_position, {"volume_db": -6.0})
		return
	_shatter(fire)


## The bottle breaks: glass and a splash of fuel, flames if the rag was lit; nothing to pick up.
func _shatter(fire: StringName) -> void:
	Audio.play_3d(&"sfx/glass_break", global_position, {"volume_db": 2.0})
	var parent: Node = get_parent()
	FxLibrary.burst(parent, "water", global_position, Vector3.UP, 0.6)
	if lit and parent != null:
		FxLibrary.burst(parent, "sparks", global_position, Vector3.UP, 1.0)
		GroundFire.spawn(parent, global_position, fire, thrower, origin)
	_armed = false
	set_deferred(&"freeze", true)
	queue_free()


## What flies: a lit molotov is its viewmodel (the ground model drops the rag's flame socket),
## anything else its ground model.
func _flight_model() -> Node3D:
	var def: ItemDef = Content.item(item_id)
	var vm: String = str(def.equip.get("viewmodel", "")) if def != null and lit else ""
	if vm != "" and ResourceLoader.exists(ViewModel.VM_PATH % vm):
		var ps: PackedScene = load(ViewModel.VM_PATH % vm) as PackedScene
		if ps != null:
			return ps.instantiate() as Node3D
	return ItemVisuals.make_model(item_id)


## A lit molotov flies with its rag burning (and lighting the ground under it at night).
func _light_rag(model: Node3D) -> void:
	var sock: Node3D = model.find_child("socket_flame", true, false) as Node3D
	var at: Node3D = sock if sock != null else model
	if DisplayServer.get_name() != "headless":
		at.add_child(ViewModel.build_flame(item_id))
	var l := FlickerLight.new()
	l.light_color = Color(1.0, 0.6, 0.28)
	l.light_energy = 1.2
	l.omni_range = 6.0
	l.flicker = 0.45
	at.add_child(l)
