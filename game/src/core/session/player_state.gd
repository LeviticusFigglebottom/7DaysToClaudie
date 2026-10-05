class_name PlayerState
extends RefCounted
## Authoritative per-player state (serializable). The Player node presents/drives it.

var id: StringName = &"p:1"
var display_name: String = "Salvager 4471"
var position: Vector3 = Vector3.ZERO
var yaw: float = 0.0
var pitch: float = 0.0
var stats: SurvivalStats
var inventory: Inventory
## Toolbelt slots hold item ids; the stacks themselves live in `inventory`.
var toolbelt: Array[StringName] = []
var equipped_slot: int = -1
var progression: Progression
var spawn_point: Vector3 = Vector3.ZERO
var has_spawn_point: bool = false
var read_notes: Dictionary = {}
var deaths: int = 0
var kills: Dictionary = {}


func _init() -> void:
	stats = SurvivalStats.new()
	var pcfg: Dictionary = Content.config(&"player")
	inventory = Inventory.new(id, 0, float(pcfg.get("base_bulk", 40.0)), true)
	progression = Progression.new()
	progression.spent.connect(refresh_derived.bind(true))
	toolbelt.resize(int(pcfg.get("toolbelt_slots", 6)))
	toolbelt.fill(&"")
	refresh_derived()


## Recomputes what attributes and perks change on the character: pack capacity (Sinew,
## Packhorse), shoulder logs (Timberwright), max health (Grit) and stamina regen (Grit, Second
## Wind). Derived values are never trusted from a save, so retuned perk data applies to old saves.
## `grow`: points were just spent (new health is filled in).
func refresh_derived(grow: bool = false) -> void:
	var pcfg: Dictionary = Content.config(&"player")
	inventory.max_bulk = float(pcfg.get("base_bulk", 40.0)) + progression.modifier("carry_bulk")
	inventory.carry_bonus = {&"log": int(progression.modifier("log_carry"))}
	stats.set_bonuses(progression.modifier("max_health"), 1.0 + progression.modifier("stamina_regen_mult"), grow)


func equipped_item() -> StringName:
	if equipped_slot < 0 or equipped_slot >= toolbelt.size():
		return &""
	var item_id: StringName = toolbelt[equipped_slot]
	return item_id if inventory.has(item_id) else &""


func to_dict() -> Dictionary:
	var tb: Array = []
	for t: StringName in toolbelt:
		tb.append(String(t))
	return {
		"id": String(id), "name": display_name, "pos": [position.x, position.y, position.z], "yaw": yaw, "pitch": pitch,
		"stats": stats.to_dict(), "inventory": inventory.to_dict(), "toolbelt": tb, "equipped": equipped_slot,
		"progression": progression.to_dict(), "spawn": [spawn_point.x, spawn_point.y, spawn_point.z],
		"has_spawn": has_spawn_point, "notes": read_notes.keys(), "deaths": deaths, "kills": kills,
	}


func from_dict(d: Dictionary) -> void:
	id = StringName(str(d.get("id", id)))
	display_name = str(d.get("name", display_name))
	var p: Array = d.get("pos", [0, 0, 0])
	position = Vector3(float(p[0]), float(p[1]), float(p[2]))
	yaw = float(d.get("yaw", 0.0))
	pitch = float(d.get("pitch", 0.0))
	stats.from_dict(d.get("stats", {}))
	inventory = Inventory.from_dict(d.get("inventory", {}))
	inventory.owner_id = id
	var tb: Array = d.get("toolbelt", [])
	for i: int in toolbelt.size():
		toolbelt[i] = StringName(str(tb[i])) if i < tb.size() else &""
	equipped_slot = int(d.get("equipped", -1))
	progression.from_dict(d.get("progression", {}))
	var sp: Array = d.get("spawn", [0, 0, 0])
	spawn_point = Vector3(float(sp[0]), float(sp[1]), float(sp[2]))
	has_spawn_point = bool(d.get("has_spawn", false))
	read_notes.clear()
	for n: Variant in d.get("notes", []):
		read_notes[StringName(str(n))] = true
	deaths = int(d.get("deaths", 0))
	kills = d.get("kills", {})
	refresh_derived()
