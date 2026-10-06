class_name WaterSource
extends RefCounted
## Open water as an interactable. PlayerInteraction offers it where the look ray meets a lake or
## river within reach. Holding interact drinks straight from it (thirst, at a small health cost:
## stream water is not clean) or, when carrying empty bottles, fills them with stream water for a
## campfire to boil. Both go through the command bus (world.drink_water / world.fill_water).

const DRINK_TIME: float = 1.0
const FILL_TIME: float = 1.5

## Where the ray met the surface (the commands re-check it against the water system).
var point := Vector3.ZERO


func interact_text(player: Player) -> String:
	if _can_fill(player):
		return "Fill bottles with stream water"
	return "Drink stream water"


func interact_hold_time(player: Player) -> float:
	return FILL_TIME if _can_fill(player) else DRINK_TIME


func interact(player: Player) -> void:
	var cmd: StringName = &"world.fill_water" if _can_fill(player) else &"world.drink_water"
	Game.execute(cmd, {"player": player.state.id, "pos": [point.x, point.y, point.z]})


## Carrying an empty bottle or bucket (ADR-0049: a bucket waters a garden bed).
static func _can_fill(player: Player) -> bool:
	return player.state.inventory.has(&"water_bottle_empty") or player.state.inventory.has(&"bucket")
