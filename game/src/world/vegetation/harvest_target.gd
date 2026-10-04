class_name HarvestTarget
extends RefCounted
## Interaction proxy for a scattered plant / stone pile / deadfall (they have no physics body).
## Returned by VegetationManager.pick_harvestable(); implements the interactable protocol.

var manager: VegetationManager
var key: Vector2i
var inst: VegetationScatter.Instance


func same_as(k: Vector2i, i: VegetationScatter.Instance) -> bool:
	return k == key and inst != null and i != null and i.index == inst.index


func species() -> SpeciesDef:
	return Content.get_def(&"species", inst.species) as SpeciesDef


func interact_text(_player: Player) -> String:
	var sp: SpeciesDef = species()
	if sp == null:
		return ""
	match sp.veg_kind:
		"rock":
			return "Gather %s" % sp.display_name
		"deadfall":
			return "Gather sticks"
		"mushroom":
			return "Pick %s" % sp.display_name
	return "Harvest %s" % sp.display_name


func interact_hold_time(_player: Player) -> float:
	var sp: SpeciesDef = species()
	return 0.0 if sp == null else clampf(sp.hp * 0.08, 0.0, 1.2)


func interact(player: Player) -> void:
	if manager != null and is_instance_valid(manager):
		manager.harvest(key, inst, player)
