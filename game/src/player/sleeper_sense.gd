class_name SleeperSense
extends Node
## The Sleeper Sense perk (Keen): dormant Hollowed within `sleeper_sense_range` metres of the
## player show a faint outline, through walls, so a room can be read before the door opens. Held
## ambush groups show too (that is the perk's point), and a POI guardian (ADR-0018) gets the warm
## guardian rim. Pure presentation: it only toggles EnemyVisual.set_sensed().

const INTERVAL: float = 0.4

var player: Player
var _t: float = 0.0
## Enemy -> true for the bodies currently outlined.
var _sensed: Dictionary = {}


func _process(delta: float) -> void:
	_t += delta
	if _t < INTERVAL:
		return
	_t = 0.0
	var reach: float = 0.0
	if player != null and player.state != null and player.state.stats.alive:
		reach = player.state.progression.modifier("sleeper_sense_range")
	var now: Dictionary = {}
	if reach > 0.0:
		var pp: Vector3 = player.global_position
		for n: Node in get_tree().get_nodes_in_group(&"enemies"):
			var e: Enemy = n as Enemy
			if e != null and e.state == Enemy.State.SLEEP and e.global_position.distance_to(pp) <= reach:
				now[e] = true
	for e: Variant in _sensed.keys():
		if not now.has(e) and is_instance_valid(e):
			(e as Enemy).visual.set_sensed(false)
	for e: Variant in now.keys():
		if not _sensed.has(e):
			(e as Enemy).visual.set_sensed(true, (e as Enemy).guardian)
	_sensed = now
