class_name ColdWarnings
extends RefCounted
## Says when the body is getting cold, before the cold does real damage (first-week audit W7: a
## player outside with no fire froze to death overnight, and nothing but the tether's vitals had
## said so). Levels and lines come from survival.json `temperature.warnings`: each level speaks
## once as the body temperature falls past it, the current one again after `repeat_minutes` of
## game time while it lasts, and nothing again until the body has warmed past `reset_above`.
## Quiet while asleep (the line comes on waking) and while dead.

## The level last spoken (0 = none).
var level: int = 0
var _since: float = INF
var _levels: Array = []
var _repeat: float = 90.0
var _reset_above: float = 36.6


func _init() -> void:
	var cfg: Dictionary = (Content.config(&"survival").get("temperature", {}) as Dictionary).get("warnings", {})
	_levels = cfg.get("levels", [])
	_repeat = float(cfg.get("repeat_minutes", _repeat))
	_reset_above = float(cfg.get("reset_above", _reset_above))


## Called after each survival tick. Returns {text, kind} when a line is due, else {}.
func update(stats: SurvivalStats, minutes: float, quiet: bool = false) -> Dictionary:
	if not stats.alive:
		level = 0
		_since = INF
		return {}
	_since += minutes
	var now: int = 0
	for i: int in _levels.size():
		if stats.body_temp < float((_levels[i] as Dictionary).get("below", 0.0)):
			now = i + 1
	if now == 0:
		if stats.body_temp >= _reset_above:
			level = 0
		return {}
	if quiet or (now <= level and _since < _repeat):
		return {}
	level = now
	_since = 0.0
	var l: Dictionary = _levels[now - 1]
	return {"text": str(l.get("text", "")), "kind": StringName(str(l.get("kind", "warning")))}
