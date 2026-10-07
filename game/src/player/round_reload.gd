class_name RoundReload
extends RefCounted
## Round-by-round reloading (ADR-0057) for a gun with equip.reload_per_round (the bolt-action
## rifle): the bolt opens (reload_open_time, use reload_<hold>_open), each round is thumbed in on
## its own (reload_time, use reload_<hold>; the round goes in when its motion ends) until the
## magazine (mag_size) is full or the ammo runs out, then the bolt closes (reload_close_time, use
## reload_<hold>_close). Firing during the open or a round stops it: the rounds already in stay and
## the bolt closes first. Changing what is in hand cancels it outright (no round half-loaded).
## A plain gun (the revolver) reloads all at once in PlayerEquipment instead.

enum Phase { NONE, OPEN, ROUND, CLOSE }

var phase: Phase = Phase.NONE
## Seconds left in the current phase.
var left: float = 0.0
## The gun being loaded.
var item: StringName = &""
## Rounds put in since the reload began.
var loaded: int = 0


static func per_round(def: ItemDef) -> bool:
	return def != null and bool(def.equip.get("reload_per_round", false))


func active() -> bool:
	return phase != Phase.NONE


func start(def: ItemDef, eq: PlayerEquipment) -> bool:
	if active() or def == null or int(eq.call(&"_rounds_to_load", def)) <= 0:
		return false
	item = def.id
	loaded = 0
	_enter(Phase.OPEN, def, eq)
	return true


## Fire pressed mid-reload: stop after closing the bolt. True if that stopped a reload.
func interrupt(eq: PlayerEquipment) -> bool:
	if phase != Phase.OPEN and phase != Phase.ROUND:
		return false
	_enter(Phase.CLOSE, Content.item(item), eq)
	return true


func cancel() -> void:
	phase = Phase.NONE
	left = 0.0
	item = &""


func step(delta: float, eq: PlayerEquipment) -> void:
	if phase == Phase.NONE:
		return
	if eq.current != item:
		cancel()
		return
	left -= delta
	if left > 0.0:
		return
	var def: ItemDef = Content.item(item)
	match phase:
		Phase.OPEN:
			_enter(Phase.ROUND if int(eq.call(&"_rounds_to_load", def)) > 0 else Phase.CLOSE, def, eq)
		Phase.ROUND:
			loaded += eq.load_rounds(def, 1)
			_enter(Phase.ROUND if int(eq.call(&"_rounds_to_load", def)) > 0 else Phase.CLOSE, def, eq)
		Phase.CLOSE:
			cancel()


## Seconds each phase takes for a gun.
static func phase_time(def: ItemDef, p: Phase) -> float:
	match p:
		Phase.OPEN:
			return def.equip_num("reload_open_time", 0.4)
		Phase.ROUND:
			return def.equip_num("reload_time", 0.6)
		Phase.CLOSE:
			return def.equip_num("reload_close_time", 0.4)
	return 0.0


func _enter(p: Phase, def: ItemDef, eq: PlayerEquipment) -> void:
	phase = p
	left = phase_time(def, p)
	var vm: ViewModel = eq.viewmodel
	var suffix: String = {Phase.OPEN: "_open", Phase.ROUND: "", Phase.CLOSE: "_close"}[p]
	if vm != null:
		vm.play_use(StringName("reload_%s%s" % [vm.hold_class, suffix]), left)
	var snd: String = str((def.equip.get("reload_sounds", {}) as Dictionary).get(["", "open", "round", "close"][p], ""))
	if snd != "" and eq.player != null:
		Audio.play_3d(StringName(snd), eq.player.global_position, {"volume_db": -6.0, "occlusion": false})
