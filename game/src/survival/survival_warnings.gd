class_name SurvivalWarnings
extends RefCounted
## Says when a need is getting dangerous, before it does real damage. First-week audit W7: a
## player outside with no fire froze to death overnight with nothing but the tether's vitals to
## say so; W18: one who stopped drinking died of thirst the same way. One ladder per stat, all
## from survival.json `warnings` (`<id>: {stat, levels, repeat_minutes, worse_by, reset_above}`):
## each level speaks as the stat falls below it; while it lasts the current one is said again only
## when the stat has fallen a further `worse_by` since the last line, or after `repeat_minutes` of
## game time (a level may set its own, longer, `repeat_minutes`), whichever comes first (mid-game
## audit M7: "You're freezing" every 90 minutes all night, the body no colder than at dusk); and
## nothing again until the stat is back above `reset_above`. Every step of a
## ladder is said once and in order, even when the stat drops past several at once (W19: waking
## in a blizzard went straight to "freezing"); the StatusFeed spaces them. Quiet while asleep (the
## lines come on waking) and while dead.

var _ladders: Array[Ladder] = []


func _init() -> void:
	var cfg: Dictionary = Content.config(&"survival").get("warnings", {})
	for id: String in cfg:
		if id.begins_with("_"):
			continue
		_ladders.append(Ladder.new(StringName(id), cfg[id] as Dictionary))


## The ladder with this id (cold, thirst, hunger), or null.
func ladder(id: StringName) -> Ladder:
	for l: Ladder in _ladders:
		if l.id == id:
			return l
	return null


## Called after each survival tick. Returns the lines due now, in order: [{text, kind, stat}].
func update(stats: SurvivalStats, minutes: float, quiet: bool = false) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for l: Ladder in _ladders:
		out.append_array(l.lines(stats, minutes, quiet))
	return out


## One stat's warnings.
class Ladder:
	extends RefCounted

	## The SurvivalStats properties a ladder may watch (a typo in the data is an error, not silence).
	const STATS: Array[StringName] = [&"body_temp", &"hydration", &"fullness", &"rest", &"health"]

	var id: StringName
	## The level last spoken (0 = none).
	var level: int = 0
	var _stat: StringName
	var _since: float = INF
	var _levels: Array = []
	var _repeat: float = 90.0
	var _worse_by: float = INF
	var _reset_above: float = 0.0
	## The stat's value at the last line.
	var _said_at: float = 0.0

	func _init(ladder_id: StringName, cfg: Dictionary) -> void:
		id = ladder_id
		_stat = StringName(str(cfg.get("stat", "")))
		_levels = cfg.get("levels", [])
		_repeat = float(cfg.get("repeat_minutes", _repeat))
		_worse_by = float(cfg.get("worse_by", _worse_by))
		_reset_above = float(cfg.get("reset_above", _reset_above))
		if not _stat in STATS:
			push_error("SurvivalWarnings: '%s' watches unknown stat '%s'" % [id, _stat])
			_levels = []

	## Every line due now, in order (all the steps a sudden drop went past, one after another).
	func lines(stats: SurvivalStats, minutes: float, quiet: bool = false) -> Array[Dictionary]:
		var out: Array[Dictionary] = []
		var line: Dictionary = update(stats, minutes, quiet)
		while not line.is_empty():
			out.append(line)
			line = update(stats, 0.0, quiet)
		return out

	## Advances the clock by `minutes` and returns the next line due ({text, kind, stat}), or {}.
	## A stat below several unspoken levels gets the first of them; call again for the next.
	func update(stats: SurvivalStats, minutes: float, quiet: bool = false) -> Dictionary:
		if not stats.alive:
			level = 0
			_since = INF
			return {}
		_since += minutes
		var value: float = float(stats.get(_stat))
		var now: int = 0
		for i: int in _levels.size():
			if value < float((_levels[i] as Dictionary).get("below", 0.0)):
				now = i + 1
		if now == 0:
			if value >= _reset_above:
				level = 0
			return {}
		if quiet or (now <= level and not _repeat_due(value)):
			return {}
		# Deeper than last said: the next step down, not the deepest (each said once, in order).
		level = now if now <= level else level + 1
		_since = 0.0
		_said_at = value
		var l: Dictionary = _levels[level - 1]
		return {"text": str(l.get("text", "")), "kind": StringName(str(l.get("kind", "warning"))), "stat": id}

	## Whether the level last said is due again: the stat a further worse_by down since then, or
	## its repeat interval (the level's own repeat_minutes, else the ladder's) gone by.
	func _repeat_due(value: float) -> bool:
		if level <= 0:
			return true
		if value <= _said_at - _worse_by:
			return true
		var l: Dictionary = _levels[level - 1]
		return _since >= float(l.get("repeat_minutes", _repeat))
